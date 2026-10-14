"""Costo por kg, FCR bruto/neto, mortalidad basal, exceso por evento e impacto en pesos.
Usa SOLO las salidas de main.py (output_persona1) y limpieza_externas.py (output_persona2)."""
import sqlite3
from pathlib import Path
import pandas as pd

CARPETA = Path(__file__).resolve().parent
SALIDA = CARPETA / 'output_costo'

# operación limpia y catálogos
con = sqlite3.connect(CARPETA / 'output_persona1' / 'datos_sqlite_limpios.sqlite')
op = pd.read_sql('SELECT * FROM operacion_limpia', con)
cen = pd.read_sql('SELECT c.centro_id, c.nombre, z.zona FROM centros c LEFT JOIN zonas z USING(zona_id)', con)
op['fecha'] = pd.to_datetime(op.fecha)
op['mes'] = op.fecha.dt.month
op['peso_kg'] = op.biomasa_kg / op.poblacion            
op['muertos_kg'] = op.mortalidad_n * op.peso_kg

# precio del mes = promedio de los tipos con precio observado ese mes (no se imputan faltantes)
pr = pd.read_csv(CARPETA / 'output_persona2' / 'precios_limpios.csv', encoding='utf-8-sig')
pr['mes'] = pr.mes.str[5:].astype(int)
precio_mes = pr.groupby('mes').precio_clp_kg.mean()
op['precio_clp_kg'] = op.mes.map(precio_mes)
op['costo_clp'] = op.alimento_kg * op.precio_clp_kg

# días en evento sanitario: jaulas afectadas entre fecha_inicio y fecha_fin
ev = pd.read_csv(CARPETA / 'output_persona2' / 'eventos_limpios.csv', encoding='utf-8-sig')
op['evento_id'] = None
for _, e in ev.iterrows():
    jaulas = [int(j) for j in str(e.jaulas_afectadas).split()]
    m = (op.centro_id == e.centro_id) & op.jaula_id.isin(jaulas) & op.fecha.between(e.fecha_inicio, e.fecha_fin)
    op.loc[m, 'evento_id'] = e.evento_id
op['en_evento'] = op.evento_id.notna()

# mortalidad basal por lote (días sin evento) y exceso en días de evento
b = op[~op.en_evento].groupby('lote_id')[['mortalidad_n', 'poblacion']].sum()
op['tasa_basal'] = op.lote_id.map(b.mortalidad_n / b.poblacion)
op['muertes_esperadas'] = op.tasa_basal * op.poblacion
op['exceso_n'] = (op.mortalidad_n - op.muertes_esperadas).where(op.en_evento, 0)
op['exceso_kg'] = op.exceso_n * op.peso_kg

def resumen(g):
    A, G, M, C = g.alimento_kg.sum(), g.crecimiento_kg.sum(), g.muertos_kg.sum(), g.costo_clp.sum()
    return pd.Series({'alimento_kg': A, 'crecimiento_bruto_kg': G, 'mortalidad_n': g.mortalidad_n.sum(),
                      'mortalidad_kg': M, 'crecimiento_neto_kg': G - M,
                      'tasa_mortalidad_diaria_pct': 100 * g.mortalidad_n.sum() / g.poblacion.sum(),
                      'exceso_mortalidad_n': g.exceso_n.sum(), 'exceso_mortalidad_kg': g.exceso_kg.sum(),
                      'fcr_bruto': A / G, 'fcr_neto': A / (G - M) if G > M else float('nan'),
                      'costo_alimento_mm_clp': C / 1e6,
                      'costo_kg_bruto_clp': C / G, 'costo_kg_neto_clp': C / (G - M) if G > M else float('nan')})

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
    'fcr_bruto_jaulas_afectadas_en_evento': (lambda g: g.alimento_kg.sum() / g.crecimiento_kg.sum())(T[T.en_evento]),
    'fcr_bruto_jaulas_afectadas_fuera_evento': (lambda g: g.alimento_kg.sum() / g.crecimiento_kg.sum())(T[afect & ~T.en_evento]),
    'fcr_bruto_jaulas_no_afectadas': (lambda g: g.alimento_kg.sum() / g.crecimiento_kg.sum())(T[~afect]),
}
imp['A_mas_B_clp'] = imp['A_sobrecosto_por_fcr_clp'] + imp['B_alimento_en_peces_muertos_por_evento_clp']
imp['parte_mortalidad_en_brecha_neta_clp_kg'] = imp['brecha_costo_kg_neto_clp'] - imp['brecha_costo_kg_bruto_clp']
especie = op.groupby(['centro_id', 'especie_id']).apply(lambda g: g.alimento_kg.sum() / g.crecimiento_kg.sum()).unstack()

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
print('OK costo y mortalidad. Centro top:', top)
if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.float_format', lambda v: f'{v:,.3f}')
    print(por_centro.to_string()); print(mensual.to_string()); print(eventos.to_string())
    for k, v in imp.items(): print(k, f'{v:,.3f}')
    print(especie.round(3)); print(precio_mes)
