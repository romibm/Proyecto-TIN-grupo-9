"""Definiciones compartidas de las métricas de AquaFiordo."""

import math


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