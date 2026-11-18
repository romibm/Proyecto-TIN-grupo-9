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