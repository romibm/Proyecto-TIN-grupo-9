"""Construcción del modelo dimensional de AquaFiordo."""

import sqlite3
from contextlib import closing
from pathlib import Path
import pandas as pd
from capa_semantica import (
    SIN_EVENTO,
    preparar_operacion,
    resumir_basales,
)


DDL = """
CREATE TABLE dim_tiempo (
    fecha TEXT PRIMARY KEY,
    anio INTEGER,
    mes INTEGER,
    dia INTEGER,
    trimestre INTEGER,
    semana_iso INTEGER,
    anio_iso INTEGER
);

CREATE TABLE dim_ubicacion (
    jaula_id INTEGER PRIMARY KEY,
    centro_id INTEGER NOT NULL,
    nombre_centro TEXT,
    zona_id INTEGER,
    zona TEXT,
    capacidad INTEGER,
    zona_id_original INTEGER,
    zona_inferida INTEGER,
    UNIQUE (jaula_id, centro_id)
);

CREATE TABLE dim_lote (
    lote_id INTEGER PRIMARY KEY,
    fecha_siembra TEXT,
    smolts_sembrados INTEGER
);

CREATE TABLE dim_especie (
    especie_id INTEGER PRIMARY KEY,
    especie TEXT
);

CREATE TABLE dim_evento (
    evento_id TEXT PRIMARY KEY,
    centro_id INTEGER,
    tipo TEXT,
    fecha_inicio TEXT,
    fecha_fin TEXT,
    tratamiento TEXT,
    jaulas_afectadas TEXT,
    mortalidad_declarada_json_n INTEGER
);

CREATE TABLE fact_operacion (
    fecha TEXT NOT NULL,
    centro_id INTEGER NOT NULL,
    jaula_id INTEGER NOT NULL,
    lote_id INTEGER NOT NULL,
    especie_id INTEGER NOT NULL,
    evento_id TEXT NOT NULL,
    origen_fila INTEGER NOT NULL,

    alimento_kg REAL NOT NULL CHECK (alimento_kg > 0),
    crecimiento_kg REAL NOT NULL CHECK (crecimiento_kg > 0),
    mortalidad_n INTEGER NOT NULL
        CHECK (mortalidad_n >= 0 AND mortalidad_n <= poblacion),
    poblacion INTEGER NOT NULL CHECK (poblacion > 0),
    biomasa_kg REAL NOT NULL CHECK (biomasa_kg > 0),
    temperatura_agua REAL NOT NULL,
    precio_clp_kg REAL NOT NULL CHECK (precio_clp_kg > 0),
    costo_clp REAL NOT NULL,
    peso_kg REAL NOT NULL,
    muertos_kg REAL NOT NULL,

    PRIMARY KEY (fecha, centro_id, jaula_id, lote_id),

    FOREIGN KEY (fecha)
        REFERENCES dim_tiempo (fecha),

    FOREIGN KEY (jaula_id, centro_id)
        REFERENCES dim_ubicacion (jaula_id, centro_id),

    FOREIGN KEY (lote_id)
        REFERENCES dim_lote (lote_id),

    FOREIGN KEY (especie_id)
        REFERENCES dim_especie (especie_id),

    FOREIGN KEY (evento_id)
        REFERENCES dim_evento (evento_id)
);
"""


def crear_estructura(conexion):
    """Crea las dimensiones y el hecho con sus restricciones."""
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.executescript(DDL)


def materializar(carpeta):
    """Carga la estrella desde las fuentes depuradas."""
    origen = (
        carpeta
        / "output_persona1"
        / "datos_sqlite_limpios.sqlite"
    )

    consultas = {
        "operacion": "SELECT * FROM operacion_limpia",
        "dim_ubicacion": """
            SELECT
                j.jaula_id,
                j.centro_id,
                c.nombre AS nombre_centro,
                c.zona_id,
                z.zona,
                j.capacidad,
                c.zona_id_original,
                c.zona_inferida
            FROM jaulas AS j
            JOIN centros AS c ON c.centro_id = j.centro_id
            JOIN zonas AS z ON z.zona_id = c.zona_id
        """,
        "dim_lote": """
            SELECT lote_id, fecha_siembra, smolts_sembrados
            FROM lotes
        """,
        "dim_especie": """
            SELECT especie_id, especie
            FROM especies
        """,
    }

    with closing(sqlite3.connect(
        origen.resolve().as_uri() + "?mode=ro",
        uri=True,
    )) as conexion:
        datos = {
            nombre: pd.read_sql(consulta, conexion)
            for nombre, consulta in consultas.items()
        }

    precios = pd.read_csv(
        carpeta / "output_persona2" / "precios_limpios.csv"
    )
    eventos = pd.read_csv(
        carpeta / "output_persona2" / "eventos_limpios.csv"
    )

    operacion = preparar_operacion(
        datos["operacion"],
        precios,
        eventos,
    )

    basales, detalle_basales = resumir_basales(
        operacion,
        eventos,
    )

    # Dimensión Tiempo: calendario completo del año.
    fechas = pd.Series(
        pd.date_range("2025-01-01", "2025-12-31")
    )

    tiempo = pd.DataFrame({
        "fecha": fechas.dt.strftime("%Y-%m-%d"),
        "anio": fechas.dt.year,
        "mes": fechas.dt.month,
        "dia": fechas.dt.day,
        "trimestre": fechas.dt.quarter,
        "semana_iso": fechas.dt.isocalendar().week.astype(int),
        "anio_iso": fechas.dt.isocalendar().year.astype(int),
    })

    # Dimensión Evento: eventos válidos y miembro SIN_EVENTO.
    columnas_evento = [
        "evento_id",
        "centro_id",
        "tipo",
        "fecha_inicio",
        "fecha_fin",
        "tratamiento",
        "jaulas_afectadas",
        "mortalidad_declarada_json_n",
    ]

    sin_evento = pd.DataFrame([{
        "evento_id": SIN_EVENTO,
        "tipo": "Sin evento",
    }])

    dimension_evento = pd.concat(
        [sin_evento, eventos[columnas_evento]],
        ignore_index=True,
    )

    # Hecho: campos definidos en el diccionario.
    columnas_hecho = [
        "fecha",
        "centro_id",
        "jaula_id",
        "lote_id",
        "especie_id",
        "evento_id",
        "origen_fila",
        "alimento_kg",
        "crecimiento_kg",
        "mortalidad_n",
        "poblacion",
        "biomasa_kg",
        "temperatura_agua",
        "precio_clp_kg",
        "costo_clp",
        "peso_kg",
        "muertos_kg",
    ]

    hecho = operacion[columnas_hecho].copy()
    hecho["fecha"] = hecho["fecha"].dt.strftime("%Y-%m-%d")

    tablas = {
        "dim_tiempo": tiempo,
        "dim_ubicacion": datos["dim_ubicacion"],
        "dim_lote": datos["dim_lote"],
        "dim_especie": datos["dim_especie"],
        "dim_evento": dimension_evento,
        "fact_operacion": hecho,
    }

    salida = carpeta / "output_modelo"
    salida.mkdir(exist_ok=True)

    destino = salida / "modelo_analitico.sqlite"
    temporal = salida / "modelo_analitico.tmp.sqlite"
    temporal.unlink(missing_ok=True)

    with closing(sqlite3.connect(temporal)) as conexion:
        crear_estructura(conexion)

        for nombre, tabla in tablas.items():
            tabla.to_sql(
                nombre,
                conexion,
                if_exists="append",
                index=False,
            )

        errores = conexion.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if errores:
            raise ValueError(
                f"Hay referencias inválidas en el modelo: {errores}"
            )

        cantidad = conexion.execute(
            "SELECT COUNT(*) FROM fact_operacion"
        ).fetchone()[0]

        if cantidad != len(datos["operacion"]):
            raise ValueError(
                "Cambió el número de observaciones al cargar el modelo"
            )

    # Sustituye la salida después de completar y cerrar la nueva base.
    temporal.replace(destino)

    basales.to_csv(
        salida / "basales_eventos.csv",
        index=False,
        encoding="utf-8-sig",
    )

    detalle_basales.to_csv(
        salida / "basales_por_lote.csv",
        index=False,
        encoding="utf-8-sig",
    )

    for nombre, tabla in tablas.items():
        print(f"{nombre}: {len(tabla)} filas")

    print("OK: modelo dimensional cargado sin referencias inválidas")
    print(f"Archivo: {destino}")


if __name__ == "__main__":
    materializar(Path(__file__).resolve().parent)