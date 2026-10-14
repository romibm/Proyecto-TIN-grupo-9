"""Mortalidad diaria registrada en las jaulas de un evento sanitario.

Lee las salidas de personas 1 y 2 sin modificarlas. No calcula mortalidad
atribuible al evento ni identifica el centro de mayor costo.
"""

import argparse
import csv
import datetime as dt
import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evento", default="EV-8001")
    parser.add_argument("--anio", type=int, default=2025)
    args = parser.parse_args()

    carpeta = Path(__file__).resolve().parent
    base = carpeta / "output_persona1" / "datos_sqlite_limpios.sqlite"
    archivo_eventos = carpeta / "output_persona2" / "eventos_limpios.csv"
    for archivo in (base, archivo_eventos):
        if not archivo.is_file():
            raise SystemExit(f"Falta {archivo}. Ejecuta la limpieza correspondiente.")

    with archivo_eventos.open(encoding="utf-8-sig", newline="") as archivo:
        eventos = [fila for fila in csv.DictReader(archivo)
                   if fila["evento_id"] == args.evento]
    if len(eventos) != 1:
        raise SystemExit("El evento debe existir exactamente una vez en eventos_limpios.csv.")
    evento = eventos[0]
    centro_id = int(evento["centro_id"])
    jaulas = sorted(set(map(int, evento["jaulas_afectadas"].split())))
    if not jaulas:
        raise SystemExit("El evento no tiene jaulas afectadas.")
    inicio = dt.date.fromisoformat(evento["fecha_inicio"])
    fin = dt.date.fromisoformat(evento["fecha_fin"])
    if inicio.year != args.anio or fin.year != args.anio or inicio > fin:
        raise SystemExit("El intervalo del evento debe estar dentro del año elegido.")

    # Abrir en modo lectura evita crear o modificar accidentalmente la base limpia.
    with closing(sqlite3.connect(base.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        centro = con.execute("SELECT nombre FROM centros WHERE centro_id=?",
                             (centro_id,)).fetchone()
        catalogo = {fila[0] for fila in con.execute(
            "SELECT jaula_id FROM jaulas WHERE centro_id=?", (centro_id,))}
        if centro is None or not set(jaulas).issubset(catalogo):
            raise SystemExit("El centro o las jaulas no coinciden con el catálogo actual.")
        total_operacion = con.execute("SELECT COUNT(*) FROM operacion_limpia").fetchone()[0]
        marcas = ",".join("?" for _ in jaulas)
        # Se suman muertes registradas en las mismas jaulas durante todo el año.
        # No se reutilizan los totales del CSV: pueden provenir de una base anterior.
        consulta = f"""
            SELECT fecha, SUM(mortalidad_n), COUNT(DISTINCT jaula_id), COUNT(*)
            FROM operacion_limpia
            WHERE centro_id=? AND jaula_id IN ({marcas})
              AND fecha BETWEEN ? AND ?
            GROUP BY fecha ORDER BY fecha
        """
        parametros = (centro_id, *jaulas, f"{args.anio}-01-01", f"{args.anio}-12-31")
        filas = con.execute(consulta, parametros).fetchall()
    if not filas:
        raise SystemExit("No hay operación limpia para ese evento y año.")

    por_fecha = {dt.date.fromisoformat(fecha): (int(muertes), n_jaulas, n_filas)
                 for fecha, muertes, n_jaulas, n_filas in filas}
    fecha = dt.date(args.anio, 1, 1)
    fechas, datos = [], []
    while fecha.year == args.anio:
        muertes, n_jaulas, n_filas = por_fecha.get(fecha, (None, 0, 0))
        fechas.append(fecha)
        datos.append({
            "fecha": fecha.isoformat(), "centro_id": centro_id,
            "evento_id_referencia": args.evento,
            "en_intervalo_evento": int(inicio <= fecha <= fin),
            "mortalidad_observada_n": muertes,
            "jaulas_con_datos_n": n_jaulas, "jaulas_del_evento_n": len(jaulas),
            "filas_operacion_n": n_filas,
        })
        fecha += dt.timedelta(days=1)

    salida = carpeta / "output_persona5"
    salida.mkdir(exist_ok=True)
    ruta_csv = salida / f"03_datos_mortalidad_{args.evento}.csv"
    with ruta_csv.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(datos[0]), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(datos)

    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False})
    fig, (ax, calidad) = plt.subplots(
        2, 1, figsize=(12, 7.4), sharex=True,
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.18})
    muertes = [float("nan") if d["mortalidad_observada_n"] is None
               else d["mortalidad_observada_n"] for d in datos]
    ax.plot(fechas, muertes, color="#27647A", linewidth=1.4,
            label="Muertes registradas en jaulas afectadas")
    for eje in (ax, calidad):
        eje.axvspan(inicio, fin + dt.timedelta(days=1), color="#DDA64A", alpha=0.20)
        eje.grid(axis="y", color="#E5E7EB", linewidth=0.7)
        eje.set_axisbelow(True)
    ax.axvline(inicio, color="#9A6617", linestyle="--", linewidth=1)
    ax.axvline(fin, color="#9A6617", linestyle="--", linewidth=1)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Mortalidad observada (peces/día)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda valor, _: f"{valor:,.0f}".replace(",", ".")))
    ax.set_title(f"{centro[0]}: mortalidad diaria en jaulas del evento (peces/día)",
                 loc="left", fontweight="bold", fontsize=15, pad=42)
    ax.text(0, 1.04,
            f"Observado | {args.anio} | Jaulas {', '.join(map(str, jaulas))} | "
            f"{args.evento}: {evento['tipo']}, {inicio:%d/%m} a {fin:%d/%m}",
            transform=ax.transAxes, fontsize=10, color="#555555")
    ax.legend(loc="upper left", frameon=False, fontsize=10)
    calidad.step(fechas, [d["jaulas_con_datos_n"] for d in datos],
                 where="mid", color="#68727D", linewidth=1.2)
    calidad.set_ylim(-0.1, len(jaulas) + 0.3)
    calidad.set_yticks(range(len(jaulas) + 1))
    calidad.set_ylabel("Jaulas con datos\n(cantidad)")
    calidad.set_xlabel(f"Fecha ({args.anio}); sombreado: intervalo sanitario declarado")
    calidad.set_xlim(dt.date(args.anio, 1, 1), dt.date(args.anio, 12, 31))
    calidad.xaxis.set_major_locator(mdates.MonthLocator())
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    calidad.xaxis.set_major_formatter(FuncFormatter(
        lambda valor, _: meses[mdates.num2date(valor).month - 1]))
    fig.subplots_adjust(left=0.10, right=0.98, top=0.80, bottom=0.19)
    fig.text(0.10, 0.07,
             "Fuente: origen_acuicultura.sqlite (operacion_limpia) y origen_eventos_sanitarios.json (eventos_limpios.csv).\n"
             "Sin registros: hueco en la mortalidad, no cero. Con menos jaulas: suma parcial, sin estimar faltantes.\n"
             "Coincidencia temporal no demuestra causalidad; no se estima aquí mortalidad basal ni costo.",
             fontsize=9, color="#555555", va="bottom")
    ruta_png = salida / f"03_mortalidad_diaria_{args.evento}.png"
    fig.savefig(ruta_png, dpi=200, facecolor="white")
    plt.close(fig)

    dias_evento = [d for d in datos if d["en_intervalo_evento"]]
    observadas = sum(d["mortalidad_observada_n"] or 0 for d in dias_evento)
    completos = sum(d["jaulas_con_datos_n"] == len(jaulas) for d in dias_evento)
    ruta_ficha = salida / f"03_interpretacion_mortalidad_{args.evento}.md"
    # El texto describe las observaciones disponibles; no calcula una basal.
    ficha = f"""# Mortalidad diaria y evento sanitario: {centro[0]}

**Pregunta:** ¿Cómo se comporta la mortalidad registrada en las jaulas afectadas antes, durante y después del intervalo sanitario declarado?

**Origen:** observado en la operación limpia; fechas y jaulas del evento tomadas de la fuente sanitaria.

## Lectura de la figura

La línea superior suma mortalidad_n por fecha en las jaulas {', '.join(map(str, jaulas))} de {centro[0]}. Se mantiene ese mismo conjunto de jaulas durante todo {args.anio}. El sombreado identifica {args.evento} ({evento['tipo']}), desde {inicio.isoformat()} hasta {fin.isoformat()}, ambos días incluidos.

Durante ese intervalo se registran {observadas:,} muertes en las jaulas seleccionadas. Es una cantidad observada durante el evento, no una estimación de muertes causadas por él. En {completos} de {len(dias_evento)} días hay datos de las {len(jaulas)} jaulas seleccionadas.

El panel inferior muestra la cantidad de jaulas con observaciones conservadas cada día. Con menos jaulas, la suma de mortalidad es parcial; una caída puede reflejar menor disponibilidad de información. Un día sin registros queda vacío en la mortalidad, no se transforma en cero.

## Qué permite concluir

La figura permite identificar coincidencia temporal entre la evolución de la mortalidad registrada y el intervalo sanitario declarado. La explicación del exceso requiere una referencia basal y considerar cambios de población y disponibilidad de observaciones.

## Alcance y límites

- Una fila del CSV generado representa un día, un centro y el conjunto de jaulas del evento seleccionado.
- Se utilizan las operaciones limpias de las jaulas seleccionadas; no se imputa mortalidad ni se corrigen las fechas del evento.
- Mortalidad_n mide peces muertos, no kg de biomasa ni una tasa sobre la población.
- La misma cantidad de jaulas con datos no garantiza la misma población expuesta.
- Tener menos jaulas con datos no permite distinguir, con esta figura sola, entre días ausentes, filas excluidas por limpieza o jaulas sin registros operacionales.
- No se determina aquí mortalidad atribuible, costo/kg ni impacto económico.

## Reproducción

Después de generar las salidas de las personas 1 y 2, ejecutar:

```bash
python3 graficos_mortalidad.py --evento {args.evento}
```

Fuentes: origen_acuicultura.sqlite (tabla operacion_limpia de output_persona1/datos_sqlite_limpios.sqlite) y origen_eventos_sanitarios.json (fechas y jaulas de output_persona2/eventos_limpios.csv). Los totales se recalculan desde la base SQLite actual, no se reutilizan los totales de mortalidad del CSV de eventos.

Uso de IA: ChatGPT ayudó a preparar y revisar la visualización y esta explicación.
"""
    ruta_ficha.write_text(ficha, encoding="utf-8")
    print(f"OK mortalidad diaria: {len(datos)} fechas; evento {args.evento}")
    print(f"Base actual: {total_operacion:,} filas de operación limpia")
    print(f"Evento: {args.evento}; {centro[0]}; jaulas {jaulas}")
    print(f"Muertes observadas en jaulas afectadas durante el intervalo: {observadas:,}")
    print(f"Días con datos de todas las jaulas durante el intervalo: {completos} de {len(dias_evento)}")
    print(f"Gráfico: {ruta_png}")
    print(f"Datos del gráfico: {ruta_csv}")
    print(f"Interpretación: {ruta_ficha}")


if __name__ == "__main__":
    main()
