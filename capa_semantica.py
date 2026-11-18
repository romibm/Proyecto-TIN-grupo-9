"""Definiciones compartidas de las métricas de AquaFiordo."""

import math
import pandas as pd
import sqlite3
from contextlib import closing

DEFINICIONES = {
    "fcr_bruto": {
        "nombre": "FCR bruto",
        "formula": "SUM(alimento_kg) / SUM(crecimiento_kg)",
        "unidad": "kg alimento/kg crecimiento bruto",
        "principal": True,
    },
    "fcr_neto_estimado": {
        "nombre": "FCR neto estimado",
        "formula": (
            "SUM(alimento_kg) / "
            "(SUM(crecimiento_kg) - SUM(muertos_kg))"
        ),
        "unidad": "kg alimento/kg crecimiento neto estimado",
        "principal": False,
    },
}


def calcular_fcr(alimento, crecimiento, muertos):
    """Calcula ambos FCR a partir de los componentes ya sumados."""
    componentes = (alimento, crecimiento, muertos)

    if not all(math.isfinite(float(valor)) for valor in componentes):
        raise ValueError("Los componentes del FCR deben ser finitos")

    if alimento < 0 or crecimiento <= 0 or muertos < 0:
        raise ValueError("Los componentes del FCR están fuera de rango")

    bruto = alimento / crecimiento
    crecimiento_neto = crecimiento - muertos

    neto = (
        alimento / crecimiento_neto
        if crecimiento_neto > 0
        else None
    )

    return {
        "fcr_bruto": bruto,
        "fcr_neto_estimado": neto,
        "diferencia_fcr": (
            neto - bruto if neto is not None else None
        ),
        "cambio_porcentual_fcr": (
            (neto / bruto - 1) * 100
            if neto is not None and bruto > 0
            else None
        ),
    }

SIN_EVENTO = "SIN_EVENTO"


def preparar_operacion(operacion, precios, eventos):
    """Enriquece la operación conservando una fila por observación."""
    op = operacion.copy()
    op["fecha"] = pd.to_datetime(op["fecha"])
    op["mes"] = op["fecha"].dt.month

    # Precio de referencia: promedio de los tipos disponibles del mes.
    pr = precios.copy()
    pr["mes_numero"] = pd.to_datetime(pr["mes"]).dt.month
    precio_mensual = pr.groupby("mes_numero")["precio_clp_kg"].mean()

    op["precio_clp_kg"] = op["mes"].map(precio_mensual)

    if not op["precio_clp_kg"].gt(0).all():
        raise ValueError("Hay observaciones sin precio mensual positivo")

    op["costo_clp"] = op["alimento_kg"] * op["precio_clp_kg"]
    op["peso_kg"] = op["biomasa_kg"] / op["poblacion"]
    op["muertos_kg"] = op["mortalidad_n"] * op["peso_kg"]

    # Cada observación recibe un evento o el miembro SIN_EVENTO.
    op["evento_id"] = SIN_EVENTO

    for evento in eventos.itertuples(index=False):
        jaulas = [
            int(jaula)
            for jaula in str(evento.jaulas_afectadas).split()
        ]

        coincide = (
            op["centro_id"].eq(evento.centro_id)
            & op["jaula_id"].isin(jaulas)
            & op["fecha"].between(
                pd.Timestamp(evento.fecha_inicio),
                pd.Timestamp(evento.fecha_fin),
            )
        )

        if op.loc[coincide, "evento_id"].ne(SIN_EVENTO).any():
            raise ValueError(
                "Hay eventos superpuestos sobre una misma observación"
            )

        op.loc[coincide, "evento_id"] = evento.evento_id

    return op

def leer_operacion(carpeta):
    """Lee las observaciones preparadas del modelo dimensional."""
    modelo = carpeta / "output_modelo" / "modelo_analitico.sqlite"

    with closing(sqlite3.connect(
        modelo.resolve().as_uri() + "?mode=ro",
        uri=True,
    )) as conexion:
        op = pd.read_sql(
            """
            SELECT *
            FROM fact_operacion
            ORDER BY fecha, centro_id, jaula_id, lote_id
            """,
            conexion,
        )

    op["fecha"] = pd.to_datetime(op["fecha"])
    op["mes"] = op["fecha"].dt.month
    op["en_evento"] = op["evento_id"].ne(SIN_EVENTO)

    return op

BASAL_PRINCIPAL = "lote_sin_evento"
BASAL_ALTERNATIVA = "lote_previa_evento"

DEFINICIONES.update({
    BASAL_PRINCIPAL: {
        "nombre": "Basal por lote sin evento",
        "formula": (
            "SUM(mortalidad_n) / SUM(poblacion), "
            "por lote en días sin evento de 2025"
        ),
        "unidad": "muertes/pez-día",
        "principal": True,
    },
    BASAL_ALTERNATIVA: {
        "nombre": "Basal por lote previa al evento",
        "formula": (
            "SUM(mortalidad_n) / SUM(poblacion), "
            "por lote en días sin evento de 2025 "
            "anteriores al inicio del evento evaluado"
        ),
        "unidad": "muertes/pez-día",
        "principal": False,
    },
})

def aplicar_basal(
    operacion,
    eventos,
    basal_id=BASAL_PRINCIPAL,
):
    """Estima mortalidad esperada y exceso en observaciones con evento."""
    if basal_id not in (BASAL_PRINCIPAL, BASAL_ALTERNATIVA):
        raise ValueError(f"Referencia basal desconocida: {basal_id}")

    op = operacion.copy()
    op["fecha"] = pd.to_datetime(op["fecha"])
    op["en_evento"] = op["evento_id"].ne(SIN_EVENTO)

    normales = op[~op["en_evento"]].copy()
    op["tasa_basal"] = float("nan")

    for evento in eventos.itertuples(index=False):
        seleccion = op["evento_id"].eq(evento.evento_id)

        if not seleccion.any():
            raise ValueError(
                f"El evento {evento.evento_id} no tiene observaciones"
            )

        referencia = normales

        if basal_id == BASAL_ALTERNATIVA:
            referencia = normales[
                normales["fecha"] < pd.Timestamp(evento.fecha_inicio)
            ]

        totales = referencia.groupby("lote_id")[
            ["mortalidad_n", "poblacion"]
        ].sum()

        lotes_evento = set(op.loc[seleccion, "lote_id"])
        faltantes = lotes_evento - set(totales.index)

        if faltantes:
            raise ValueError(
                f"{evento.evento_id}: lotes sin historia para "
                f"{basal_id}: {sorted(faltantes)}"
            )

        if not totales.loc[
            sorted(lotes_evento), "poblacion"
        ].gt(0).all():
            raise ValueError("La exposición de referencia debe ser positiva")

        tasas = totales["mortalidad_n"] / totales["poblacion"]

        op.loc[seleccion, "tasa_basal"] = (
            op.loc[seleccion, "lote_id"].map(tasas)
        )

    if op.loc[op["en_evento"], "tasa_basal"].isna().any():
        raise ValueError("Hay observaciones de evento sin tasa basal")

    op["muertes_esperadas"] = op["tasa_basal"] * op["poblacion"]

    op["exceso_n"] = (
        op["mortalidad_n"] - op["muertes_esperadas"]
    ).where(op["en_evento"], 0)

    op["exceso_kg"] = op["exceso_n"] * op["peso_kg"]

    return op

def resumir_basales(operacion, eventos):
    """Publica ambas referencias por evento y por lote."""
    resumenes = []
    detalles = []

    columnas_evento = [
        "evento_id",
        "centro_id",
        "centro",
        "fecha_inicio",
        "fecha_fin",
        "mortalidad_declarada_json_n",
    ]

    for basal_id in (BASAL_PRINCIPAL, BASAL_ALTERNATIVA):
        calculada = aplicar_basal(operacion, eventos, basal_id)
        datos = calculada[calculada["en_evento"]].copy()

        datos["biomasa_basal_kg"] = (
            datos["muertes_esperadas"] * datos["peso_kg"]
        )

        resumen = datos.groupby("evento_id").agg(
            muertes_observadas_n=("mortalidad_n", "sum"),
            muertes_esperadas_n=("muertes_esperadas", "sum"),
            exceso_n=("exceso_n", "sum"),
            biomasa_observada_kg=("muertos_kg", "sum"),
            biomasa_basal_kg=("biomasa_basal_kg", "sum"),
            exceso_kg=("exceso_kg", "sum"),
            observaciones_conservadas=("fecha", "size"),
        ).reset_index()

        resumen = resumen.merge(
            eventos[columnas_evento],
            on="evento_id",
            validate="one_to_one",
        )

        resumen["basal_id"] = basal_id
        resumen["nombre_basal"] = DEFINICIONES[basal_id]["nombre"]
        resumen["brecha_json_sqlite_n"] = (
            resumen["mortalidad_declarada_json_n"]
            - resumen["muertes_observadas_n"]
        )

        detalle = datos.groupby(
            ["evento_id", "lote_id"]
        ).agg(
            tasa_basal=("tasa_basal", "first"),
            muertes_observadas_n=("mortalidad_n", "sum"),
            muertes_esperadas_n=("muertes_esperadas", "sum"),
            exceso_n=("exceso_n", "sum"),
            exceso_kg=("exceso_kg", "sum"),
        ).reset_index()

        detalle["basal_id"] = basal_id

        resumenes.append(resumen)
        detalles.append(detalle)

    return (
        pd.concat(resumenes, ignore_index=True),
        pd.concat(detalles, ignore_index=True),
    )