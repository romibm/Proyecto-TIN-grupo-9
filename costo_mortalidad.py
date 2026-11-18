"""Costos y mortalidad a partir del modelo dimensional de AquaFiordo."""
import sqlite3
from pathlib import Path
import pandas as pd
from capa_semantica import (
    calcular_fcr,
    leer_operacion,
    SIN_EVENTO,
    aplicar_basal,
    BASAL_PRINCIPAL,
)
from contextlib import closing

CARPETA = Path(__file__).resolve().parent
SALIDA = CARPETA / 'output_costo'

# Operación y catálogos del modelo dimensional.
op = leer_operacion(CARPETA)

modelo = CARPETA / "output_modelo" / "modelo_analitico.sqlite"

with closing(sqlite3.connect(
    modelo.resolve().as_uri() + "?mode=ro",
    uri=True,
)) as conexion:
    cen = pd.read_sql(
        """
        SELECT DISTINCT
            centro_id,
            nombre_centro AS nombre,
            zona
        FROM dim_ubicacion
        """,
        conexion,
    )

    ev = pd.read_sql(
        """
        SELECT
            e.*,
            c.nombre_centro AS centro
        FROM dim_evento AS e
        JOIN (
            SELECT DISTINCT centro_id, nombre_centro
            FROM dim_ubicacion
        ) AS c
            ON c.centro_id = e.centro_id
        WHERE e.evento_id <> ?
        """,
        conexion,
        params=[SIN_EVENTO],
    )

precio_mes = op.groupby("mes")["precio_clp_kg"].first()

# Referencia principal definida en la capa semántica.
op = aplicar_basal(op, ev, BASAL_PRINCIPAL)


def fcr_bruto_grupo(g):
    """Obtiene el FCR bruto de un grupo mediante la definición común."""
    resultado = calcular_fcr(
        g.alimento_kg.sum(),
        g.crecimiento_kg.sum(),
        g.muertos_kg.sum(),
    )
    return resultado["fcr_bruto"]


def resumen(g):
    A = g.alimento_kg.sum()
    G = g.crecimiento_kg.sum()
    M = g.muertos_kg.sum()
    C = g.costo_clp.sum()

    fcr = calcular_fcr(A, G, M)
    neto = fcr["fcr_neto_estimado"]

    return pd.Series({
        "alimento_kg": A,
        "crecimiento_bruto_kg": G,
        "mortalidad_n": g.mortalidad_n.sum(),
        "mortalidad_kg": M,
        "crecimiento_neto_kg": G - M,
        "tasa_mortalidad_diaria_pct": (
            100 * g.mortalidad_n.sum() / g.poblacion.sum()
        ),
        "exceso_mortalidad_n": g.exceso_n.sum(),
        "exceso_mortalidad_kg": g.exceso_kg.sum(),
        "fcr_bruto": fcr["fcr_bruto"],
        "fcr_neto_estimado": (
            neto if neto is not None else float("nan")
        ),
        "costo_alimento_mm_clp": C / 1e6,
        "costo_kg_bruto_clp": C / G,
        "costo_kg_neto_clp": (
            C / (G - M) if G > M else float("nan")
        ),
    })

por_centro = op.groupby('centro_id').apply(resumen).reset_index().merge(cen, on='centro_id')
top = int(por_centro.sort_values('costo_kg_bruto_clp').centro_id.iloc[-1])
resto_df = op[op.centro_id != top]
resto = resumen(resto_df)
por_centro = pd.concat([por_centro, resto.to_frame().T.assign(centro_id=0, nombre='Resto (sin centro top)', zona='')])

mensual = op[op.centro_id == top].groupby('mes').apply(resumen)
mensual['precio_clp_kg'] = precio_mes
mensual['dias_jaula_en_evento'] = op[(op.centro_id == top) & op.en_evento].groupby('mes').size()
mensual = mensual.join(resto_df.groupby('mes').apply(resumen)[['fcr_bruto', 'tasa_mortalidad_diaria_pct', 'costo_kg_bruto_clp']].add_suffix('_resto')).fillna({'dias_jaula_en_evento': 0}).reset_index()

eventos = op[op.en_evento].groupby('evento_id').agg(muertes_observadas=('mortalidad_n', 'sum'),
          muertes_esperadas_basal=('muertes_esperadas', 'sum'), exceso_n=('exceso_n', 'sum'), exceso_kg=('exceso_kg', 'sum'),
          dias_jaula=('mortalidad_n', 'size')).join(ev.set_index('evento_id')[['centro', 'tipo', 'mortalidad_declarada_json_n']]).reset_index()

# impacto en pesos del centro top
T = op[op.centro_id == top]; r = resumen(T)
precio_pagado = T.costo_clp.sum() / T.alimento_kg.sum()
afect = T.jaula_id.isin([int(j) for s in ev[ev.centro_id == top].jaulas_afectadas for j in str(s).split()])
imp = {
    'centro_top': top,
    'precio_medio_pagado_clp_kg': precio_pagado,
    'A_sobrecosto_por_fcr_clp': (r.fcr_bruto - resto.fcr_bruto) * r.crecimiento_bruto_kg * precio_pagado,
    'B_alimento_en_peces_muertos_por_evento_clp': r.exceso_mortalidad_kg * r.fcr_bruto * precio_pagado,
    'brecha_costo_kg_bruto_clp': r.costo_kg_bruto_clp - resto.costo_kg_bruto_clp,
    'brecha_costo_kg_neto_clp': r.costo_kg_neto_clp - resto.costo_kg_neto_clp,
    'fcr_bruto_jaulas_afectadas_en_evento': fcr_bruto_grupo(T[T.en_evento]),
    'fcr_bruto_jaulas_afectadas_fuera_evento': fcr_bruto_grupo(T[afect & ~T.en_evento]),
    'fcr_bruto_jaulas_no_afectadas': fcr_bruto_grupo(T[~afect]),
}
imp['A_mas_B_clp'] = imp['A_sobrecosto_por_fcr_clp'] + imp['B_alimento_en_peces_muertos_por_evento_clp']
imp['parte_mortalidad_en_brecha_neta_clp_kg'] = imp['brecha_costo_kg_neto_clp'] - imp['brecha_costo_kg_bruto_clp']
especie = (
    op.groupby(["centro_id", "especie_id"])
    .apply(fcr_bruto_grupo)
    .unstack()
)

# verificación: ¿crecimiento_kg es bruto?  biomasa(mañana) - biomasa(hoy) vs crecimiento(mañana) - muertos_kg(hoy)
s = op.sort_values(['lote_id', 'fecha'])
nxt = s.groupby('lote_id').shift(-1)
ok = (nxt.fecha - s.fecha).dt.days == 1
dif = (nxt.biomasa_kg - s.biomasa_kg) - (nxt.crecimiento_kg - s.muertos_kg)
imp['verificacion_crecimiento_bruto_pct_dias_cuadran_10kg'] = 100 * (dif[ok].abs() <= 10).mean()

SALIDA.mkdir(exist_ok=True)
with pd.ExcelWriter(SALIDA / 'costo_mortalidad.xlsx') as w:
    por_centro.round(3).to_excel(w, sheet_name='por_centro', index=False)
    mensual.round(3).to_excel(w, sheet_name=f'mensual_centro_{top}', index=False)
    eventos.round(1).to_excel(w, sheet_name='eventos', index=False)
    pd.Series(imp).rename('valor').to_frame().to_excel(w, sheet_name='impacto')
    especie.round(3).to_excel(w, sheet_name='fcr_por_especie')
    precio_mes.rename('precio_promedio_clp_kg').to_excel(w, sheet_name='precio_mes')
# Componentes económicos para comparar ambas referencias basales.
carpeta_modelo = CARPETA / "output_modelo"

basales = pd.read_csv(
    carpeta_modelo / "basales_eventos.csv"
)

componentes = basales[
    basales["centro_id"].eq(top)
].copy()

componentes["precio_medio_pagado_clp_kg"] = precio_pagado
componentes["fcr_centro"] = r.fcr_bruto
componentes["fcr_referencia_resto"] = resto.fcr_bruto

componentes["A_fcr_clp"] = imp["A_sobrecosto_por_fcr_clp"]

componentes["B_exceso_clp"] = (
    componentes["exceso_kg"]
    * r.fcr_bruto
    * precio_pagado
)

componentes["basal_evento_clp"] = (
    componentes["biomasa_basal_kg"]
    * r.fcr_bruto
    * precio_pagado
)

componentes["traslape_estimado_clp"] = (
    componentes["exceso_kg"]
    * (r.fcr_bruto - resto.fcr_bruto)
    * precio_pagado
)

componentes["union_A_B_clp"] = (
    componentes["A_fcr_clp"]
    + componentes["B_exceso_clp"]
    - componentes["traslape_estimado_clp"]
)

componentes.to_csv(
    carpeta_modelo / "componentes_costos.csv",
    index=False,
    encoding="utf-8-sig",
)
print('OK costo y mortalidad. Centro top:', top)
if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.float_format', lambda v: f'{v:,.3f}')
    print(por_centro.to_string()); print(mensual.to_string()); print(eventos.to_string())
    for k, v in imp.items(): print(k, f'{v:,.3f}')
    print(especie.round(3)); print(precio_mes)
