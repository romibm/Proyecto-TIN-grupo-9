"""Genera la comparación visual de FCR a partir de la salida de metricas_fcr.py."""

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


def decimal_es(valor, decimales=3):
    """Muestra los decimales con coma sin alterar los valores del cálculo."""
    return f"{valor:.{decimales}f}".replace(".", ",")


def leer_resultados(ruta):
    """Lee y valida la tabla por centro, conservando las columnas originales."""
    if not ruta.is_file():
        raise SystemExit(
            "Falta output_persona3/fcr_por_centro.csv. "
            "Primero ejecuta python3 main.py y python3 metricas_fcr.py."
        )
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas = lector.fieldnames or []
        requeridas = {"centro_id", "nombre_centro", "fcr_bruto", "fcr_neto_estimado"}
        if not requeridas.issubset(columnas):
            raise SystemExit("El CSV no contiene las columnas de FCR esperadas.")
        originales = list(lector)
    if not originales:
        raise SystemExit("La tabla de FCR no tiene resultados.")
    vistos, resultados = set(), []
    for original in originales:
        try:
            centro_id = int(original["centro_id"])
            bruto = float(original["fcr_bruto"])
            neto = float(original["fcr_neto_estimado"])
        except (ValueError, TypeError) as error:
            raise SystemExit(f"Hay un valor de FCR o identificador inválido: {error}") from error
        if centro_id in vistos or not original["nombre_centro"].strip():
            raise SystemExit("Hay centros duplicados o sin nombre en la tabla.")
        if not all(math.isfinite(valor) and valor > 0 for valor in (bruto, neto)):
            raise SystemExit(f"El centro {centro_id} tiene un FCR no válido.")
        if neto < bruto - 1e-12:
            raise SystemExit(f"El FCR neto del centro {centro_id} contradice la definición documentada.")
        vistos.add(centro_id)
        resultados.append({"centro_id": centro_id, "nombre": original["nombre_centro"],
                           "bruto": bruto, "neto": neto,
                           "cambio_pct": (neto / bruto - 1) * 100})
    # Las dos barras de cada centro permanecen juntas; se ordena por neto estimado.
    resultados.sort(key=lambda fila: (-fila["neto"], fila["centro_id"]))
    return columnas, originales, resultados


def main():
    carpeta = Path(__file__).resolve().parent
    fuente = carpeta / "output_persona3" / "fcr_por_centro.csv"
    columnas, originales, resultados = leer_resultados(fuente)
    salida = carpeta / "output_persona5"
    salida.mkdir(exist_ok=True)
    ruta_png = salida / "02_fcr_bruto_vs_neto.png"
    ruta_datos = salida / "02_datos_fcr.csv"
    ruta_ficha = salida / "02_interpretacion_fcr.md"
    mayor_neto = max(resultados, key=lambda fila: fila["neto"])
    mayor_bruto = max(resultados, key=lambda fila: fila["bruto"])
    resto = [fila["cambio_pct"] for fila in resultados
             if fila["centro_id"] != mayor_neto["centro_id"]]

    plt.rcParams.update({"font.size": 12, "axes.spines.top": False,
                         "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(12, 7.8))
    posiciones = list(range(len(resultados)))
    alto = 0.32
    ax.barh([y - 0.18 for y in posiciones], [fila["bruto"] for fila in resultados],
            height=alto, color="#D6DBE0", edgecolor="#68727D", hatch="///",
            linewidth=0.5, label="FCR bruto")
    ax.barh([y + 0.18 for y in posiciones], [fila["neto"] for fila in resultados],
            height=alto, color="#27647A", label="FCR neto estimado")
    for y, fila in zip(posiciones, resultados):
        ax.text(fila["bruto"] + 0.025, y - 0.18, decimal_es(fila["bruto"]),
                va="center", fontsize=11, color="#374151")
        ax.text(fila["neto"] + 0.025, y + 0.18, decimal_es(fila["neto"]),
                va="center", fontsize=11, color="#173F4F")
    ax.set_yticks(posiciones, [fila["nombre"].removeprefix("Centro ") for fila in resultados])
    ax.invert_yaxis()
    ax.set_xlim(0, max(fila["neto"] for fila in resultados) * 1.16)
    ax.set_xlabel("FCR (kg de alimento por kg de crecimiento según definición)", labelpad=12)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda valor, _: decimal_es(valor, 1)))
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=10)
    for etiqueta, fila in zip(ax.get_yticklabels(), resultados):
        if fila["centro_id"] == mayor_neto["centro_id"]:
            etiqueta.set_fontweight("bold")
    fig.text(0.17, 0.94, "FCR por centro bajo dos definiciones (kg/kg)",
             fontsize=19, fontweight="bold", ha="left")
    mensaje = (f"{mayor_neto['nombre']}: {decimal_es(mayor_neto['bruto'])} bruto y "
               f"{decimal_es(mayor_neto['neto'])} neto estimado "
               f"(+{decimal_es(mayor_neto['cambio_pct'], 2)}%).")
    fig.text(0.17, 0.90, mensaje, fontsize=12, color="#374151", ha="left")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=2, frameon=False,
              fontsize=11, borderaxespad=0)
    fig.subplots_adjust(left=0.17, right=0.98, top=0.80, bottom=0.22)
    fig.text(0.17, 0.06,
             "Fuente: origen_acuicultura.sqlite, operación limpia de 2025; metricas_fcr.py / fcr_por_centro.csv.\n"
             "Observaciones conservadas de 2025. Orden: FCR neto estimado descendente. Menor FCR indica menos alimento por kg.\n"
             "El neto descuenta biomasa muerta estimada, suponiendo crecimiento bruto. El ajuste usa toda la mortalidad registrada.",
             fontsize=9, color="#555555", ha="left", va="bottom")
    fig.savefig(ruta_png, dpi=200, facecolor="white")
    plt.close(fig)

    # Se guarda la tabla de entrada completa para poder reconstruir cada barra.
    with ruta_datos.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(originales)
    coincidencia = (
        f"{mayor_neto['nombre']} presenta el mayor FCR bajo ambas definiciones."
        if mayor_neto["centro_id"] == mayor_bruto["centro_id"] else
        "El centro con mayor FCR cambia entre las dos definiciones."
    )
    comparacion = (f" En los otros centros, el aumento va de {decimal_es(min(resto), 2)}% "
                   f"a {decimal_es(max(resto), 2)}%." if resto else "")
    ficha = f"""# Comparación del FCR bruto y neto estimado

**Pregunta:** ¿Cómo cambia el FCR por centro al descontar la biomasa muerta estimada?

**Origen del hallazgo:** medido en los resultados del cálculo, condicionado por los supuestos de la ficha FCR.

## Interpretación

{coincidencia} En {mayor_neto['nombre']}, pasa de {decimal_es(mayor_neto['bruto'])} a {decimal_es(mayor_neto['neto'])} kg/kg, un aumento de {decimal_es(mayor_neto['cambio_pct'], 2)}% respecto del bruto.{comparacion}

El cambio corresponde a dos definiciones aplicadas a las mismas observaciones. No es un empeoramiento entre dos fechas. El alimento total se mantiene y el denominador se reduce al descontar la biomasa muerta estimada.

## Definición y alcance

- FCR bruto: suma de alimento / suma de crecimiento, interpretando crecimiento_kg como bruto.
- FCR neto estimado: suma de alimento / (suma de crecimiento - biomasa muerta estimada).
- Biomasa muerta estimada: suma de mortalidad_n × biomasa_kg / poblacion, calculada por observación.
- Una fila de la tabla de resultados es un centro para las observaciones conservadas de 2025.
- La figura muestra todos los centros del CSV, sin seleccionar solo el centro con mayor FCR.

## Límites

La estimación supone que crecimiento_kg es bruto y que los peces muertos tenían el peso promedio registrado en su jaula y lote. Si el crecimiento ya fuera neto, descontar mortalidad nuevamente duplicaría el ajuste. Este gráfico usa toda la mortalidad registrada: no determina qué parte corresponde a un evento sanitario ni identifica el centro con mayor costo/kg.

## Reproducción

Ejecutar desde la carpeta del repositorio:

```bash
python3 main.py
python3 metricas_fcr.py
python3 graficos_fcr.py
```

Fuente: origen_acuicultura.sqlite; tablas operacion_limpia y centros; cálculo de metricas_fcr.py. Entrada de la figura: output_persona3/fcr_por_centro.csv. La copia de los datos usados queda en output_persona5/02_datos_fcr.csv.

Uso de IA: se utilizó ChatGPT para preparar y revisar el script de visualización y el texto de interpretación.
"""
    ruta_ficha.write_text(ficha, encoding="utf-8")
    print(f"OK comparación FCR: {len(resultados)} centros")
    print(mensaje)
    print(f"Gráfico: {ruta_png}")
    print(f"Datos: {ruta_datos}")
    print(f"Interpretación: {ruta_ficha}")


if __name__ == "__main__":
    main()
