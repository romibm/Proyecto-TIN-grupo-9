"""Pruebas de las reglas de FCR y mortalidad basal."""

import unittest
import pandas as pd
import math
import sqlite3
from contextlib import closing
from capa_semantica import (
    SIN_EVENTO,
    BASAL_PRINCIPAL,
    BASAL_ALTERNATIVA,
    calcular_fcr,
    preparar_operacion,
    aplicar_basal,
)


class PropiedadesSemanticas(unittest.TestCase):

    def datos_basal(self):
        """Ejemplo pequeño con días anteriores, durante y posteriores."""
        operacion = pd.DataFrame({
            "fecha": pd.to_datetime([
                "2025-01-01",
                "2025-02-01",
                "2025-02-02",
                "2025-03-01",
            ]),
            "centro_id": [1, 1, 1, 1],
            "jaula_id": [1, 1, 1, 1],
            "lote_id": [1, 1, 1, 1],
            "poblacion": [100, 100, 100, 100],
            "mortalidad_n": [1, 0, 4, 9],
            "biomasa_kg": [100, 100, 100, 100],
            "alimento_kg": [10, 10, 10, 10],
            "crecimiento_kg": [10, 10, 10, 10],
            "peso_kg": [1, 1, 1, 1],
            "muertos_kg": [1, 0, 4, 9],
            "evento_id": [
                SIN_EVENTO, "EV", "EV", SIN_EVENTO
            ],
        })

        eventos = pd.DataFrame([{
            "evento_id": "EV",
            "centro_id": 1,
            "fecha_inicio": "2025-02-01",
            "fecha_fin": "2025-02-02",
            "jaulas_afectadas": "1",
        }])

        return operacion, eventos

    def test_fcr_es_razon_de_sumas(self):
        primero = calcular_fcr(100, 100, 0)
        segundo = calcular_fcr(20, 10, 0)
        conjunto = calcular_fcr(120, 110, 0)

        self.assertAlmostEqual(
            conjunto["fcr_bruto"],
            120 / 110,
        )

        promedio_simple = (
            primero["fcr_bruto"] + segundo["fcr_bruto"]
        ) / 2

        self.assertNotAlmostEqual(
            conjunto["fcr_bruto"],
            promedio_simple,
        )

    def test_neto_y_denominadores_invalidos(self):
        resultado = calcular_fcr(150, 100, 25)

        self.assertEqual(resultado["fcr_bruto"], 1.5)
        self.assertEqual(resultado["fcr_neto_estimado"], 2.0)

        self.assertIsNone(
            calcular_fcr(150, 100, 100)["fcr_neto_estimado"]
        )

        with self.assertRaises(ValueError):
            calcular_fcr(150, 0, 0)

    def test_basal_previa_y_exceso_sin_truncar(self):
        operacion, eventos = self.datos_basal()

        principal = aplicar_basal(
            operacion, eventos, BASAL_PRINCIPAL
        )
        previa = aplicar_basal(
            operacion, eventos, BASAL_ALTERNATIVA
        )

        seleccion = previa["evento_id"].eq("EV")

        # La basal previa utiliza solo la muerte del día anterior.
        self.assertAlmostEqual(
            previa.loc[seleccion, "muertes_esperadas"].sum(),
            2.0,
        )

        # Conserva -1 en el primer día y +3 en el segundo.
        self.assertEqual(
            previa.loc[seleccion, "exceso_n"].tolist(),
            [-1.0, 3.0],
        )

        self.assertAlmostEqual(
            previa.loc[seleccion, "exceso_n"].sum(),
            2.0,
        )

        # La principal también utiliza la historia posterior.
        self.assertAlmostEqual(
            principal.loc[seleccion, "muertes_esperadas"].sum(),
            10.0,
        )

    def test_basal_sin_historia_bloquea(self):
        operacion, eventos = self.datos_basal()

        sin_historia_previa = operacion[
            operacion["fecha"] > pd.Timestamp("2025-01-01")
        ]

        with self.assertRaisesRegex(ValueError, "sin historia"):
            aplicar_basal(
                sin_historia_previa,
                eventos,
                BASAL_ALTERNATIVA,
            )

    def test_eventos_superpuestos_bloquean(self):
        operacion, eventos = self.datos_basal()

        superpuestos = pd.concat([
            eventos,
            eventos.assign(evento_id="OTRO"),
        ], ignore_index=True)

        precios = pd.DataFrame({
            "mes": ["2025-01", "2025-02", "2025-03"],
            "precio_clp_kg": [1, 1, 1],
        })

        with self.assertRaisesRegex(ValueError, "superpuestos"):
            preparar_operacion(
                operacion,
                precios,
                superpuestos,
            )

def comprobar_modelo(carpeta, check):
    """Comprueba los productos y registra sus resultados."""
    salida = carpeta / "output_modelo"

    with closing(sqlite3.connect(
        (salida / "modelo_analitico.sqlite").resolve().as_uri()
        + "?mode=ro",
        uri=True,
    )) as conexion:
        op = pd.read_sql("SELECT * FROM fact_operacion", conexion)

        errores_fk = conexion.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        eventos = pd.read_sql(
            "SELECT evento_id FROM dim_evento WHERE evento_id <> ?",
            conexion,
            params=[SIN_EVENTO],
        )

    with closing(sqlite3.connect(
        (
            carpeta
            / "output_persona1"
            / "datos_sqlite_limpios.sqlite"
        ).resolve().as_uri() + "?mode=ro",
        uri=True,
    )) as conexion:
        original = pd.read_sql(
            """
            SELECT fecha, centro_id, jaula_id, lote_id
            FROM operacion_limpia
            """,
            conexion,
        )

    clave = ["fecha", "centro_id", "jaula_id", "lote_id"]

    check(
        "sem_clave_hecho",
        not op.duplicated(clave).any(),
        "Clave única fecha-centro-jaula-lote",
    )

    check(
        "sem_referencias",
        not errores_fk,
        "Sin referencias huérfanas en las dimensiones",
    )

    check(
        "sem_conservacion_grano",
        len(op) == len(original)
        and set(map(tuple, op[clave].to_numpy()))
        == set(map(tuple, original[clave].to_numpy())),
        "Mismas observaciones que la operación depurada",
    )

    fechas = pd.to_datetime(op["fecha"], errors="coerce")

    check(
        "sem_periodo",
        fechas.notna().all()
        and fechas.between("2025-01-01", "2025-12-31").all(),
        "Fechas válidas dentro de 2025",
    )

    cantidades = op[[
        "alimento_kg", "crecimiento_kg", "mortalidad_n",
        "poblacion", "biomasa_kg", "precio_clp_kg",
        "peso_kg", "muertos_kg", "costo_clp", "temperatura_agua",
    ]]

    finitos = all(
        pd.notna(valor) and math.isfinite(float(valor))
        for valor in cantidades.to_numpy().ravel()
    )

    check(
        "sem_rangos",
        finitos
        and op[[
            "alimento_kg", "crecimiento_kg", "poblacion",
            "biomasa_kg", "precio_clp_kg",
        ]].gt(0).all().all()
        and op["mortalidad_n"].between(0, op["poblacion"]).all(),
        "Cantidades finitas; denominadores positivos; mortalidad válida",
    )

    def cerca(a, b):
        return len(a) == len(b) and all(
            math.isclose(
                float(x), float(y),
                rel_tol=1e-10, abs_tol=1e-7,
            )
            for x, y in zip(a, b)
        )

    check(
        "sem_derivados",
        cerca(op["peso_kg"], op["biomasa_kg"] / op["poblacion"])
        and cerca(
            op["muertos_kg"],
            op["mortalidad_n"] * op["peso_kg"],
        )
        and cerca(
            op["costo_clp"],
            op["alimento_kg"] * op["precio_clp_kg"],
        ),
        "Peso, biomasa muerta y costo coherentes con sus componentes",
    )

    basales = pd.read_csv(salida / "basales_eventos.csv")
    detalle = pd.read_csv(salida / "basales_por_lote.csv")

    referencias = {BASAL_PRINCIPAL, BASAL_ALTERNATIVA}

    pares_esperados = {
        (evento, basal)
        for evento in eventos["evento_id"]
        for basal in referencias
    }

    pares = set(map(
        tuple,
        basales[["evento_id", "basal_id"]].to_numpy(),
    ))

    lotes = op.loc[
        op["evento_id"].ne(SIN_EVENTO),
        ["evento_id", "lote_id"],
    ].drop_duplicates()

    detalle_esperado = {
        (evento, lote, basal)
        for evento, lote in lotes.itertuples(index=False, name=None)
        for basal in referencias
    }

    detalle_actual = set(map(
        tuple,
        detalle[["evento_id", "lote_id", "basal_id"]].to_numpy(),
    ))

    check(
        "sem_basales",
        pares == pares_esperados
        and not basales.duplicated(["evento_id", "basal_id"]).any()
        and detalle_actual == detalle_esperado
        and not detalle.duplicated(
            ["evento_id", "lote_id", "basal_id"]
        ).any()
        and detalle["tasa_basal"].between(0, 1).all()
        and cerca(
            basales["muertes_observadas_n"],
            basales["muertes_esperadas_n"] + basales["exceso_n"],
        )
        and cerca(
            basales["biomasa_observada_kg"],
            basales["biomasa_basal_kg"] + basales["exceso_kg"],
        ),
        "Dos basales por evento, tasas válidas y balance en peces y kg",
    )

    csv = pd.read_csv(
        carpeta / "output_persona3" / "fcr_por_centro.csv"
    ).set_index("centro_id")

    excel = pd.read_excel(
        carpeta / "output_costo" / "costo_mortalidad.xlsx",
        sheet_name="por_centro",
    ).set_index("centro_id")

    centros = set(op["centro_id"])

    top = int((
        op.groupby("centro_id")["costo_clp"].sum()
        / op.groupby("centro_id")["crecimiento_kg"].sum()
    ).idxmax())

    coinciden = (
        csv.index.is_unique
        and excel.index.is_unique
        and set(csv.index) == centros
        and set(excel.index) == centros | {0}
    )

    grupos = list(op.groupby("centro_id"))
    grupos.append((0, op[op["centro_id"].ne(top)]))

    for centro, grupo in grupos:
        fcr = calcular_fcr(
            grupo["alimento_kg"].sum(),
            grupo["crecimiento_kg"].sum(),
            grupo["muertos_kg"].sum(),
        )

        for nombre in ("fcr_bruto", "fcr_neto_estimado"):
            if centro:
                coinciden = coinciden and math.isclose(
                    float(csv.loc[centro, nombre]),
                    fcr[nombre],
                    rel_tol=1e-10,
                )

            coinciden = coinciden and (
                abs(float(excel.loc[centro, nombre]) - fcr[nombre])
                <= 0.000501
            )

    check(
        "sem_fcr_consumidores",
        coinciden,
        "CSV y Excel coinciden con la estrella según su precisión",
    )

    componentes = pd.read_csv(salida / "componentes_costos.csv")

    check(
        "sem_componentes_costos",
        not componentes.empty
        and not componentes.duplicated(
            ["evento_id", "basal_id"]
        ).any()
        and cerca(
            componentes["union_A_B_clp"],
            componentes["A_fcr_clp"]
            + componentes["B_exceso_clp"]
            - componentes["traslape_estimado_clp"],
        ),
        "La unión publicada descuenta el traslape una sola vez",
    )

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        PropiedadesSemanticas
    )
    resultado = unittest.TextTestRunner(verbosity=0).run(suite)

    check(
        "sem_propiedades",
        resultado.wasSuccessful(),
        f"{resultado.testsRun} pruebas de las reglas de cálculo",
    )
if __name__ == "__main__":
    unittest.main(verbosity=2)