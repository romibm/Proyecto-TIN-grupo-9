import argparse
import collections
import csv
import datetime as dt
import json
import math
import re
import sqlite3
import urllib.request
from contextlib import closing
from pathlib import Path

YEAR = 2025
API_DOLAR = f"https://mindicador.cl/api/dolar/{YEAR}"
CARPETA = Path(__file__).resolve().parent
SALIDA = CARPETA / "output_persona2"
TIPOS = {"engorda100": "Engorda 100", "eng100": "Engorda 100",
         "engorda200": "Engorda 200", "eng200": "Engorda 200",
         "pigmentado": "Pigmentado", "pig": "Pigmentado"}
TOKENS_VACIOS = ("", "sindato", "na", "n/a", "null", "-")

def buscar(*candidatos):
    for c in candidatos:
        if (CARPETA / c).exists():
            return CARPETA / c
    raise FileNotFoundError(f"No se encontró ninguno de: {candidatos}")

def parse_numero(valor):
    """acepta 1.021,00 / $1.050 / 978,00 / 1383 / 950.5; falla si no hay dato"""
    if isinstance(valor, (int, float)):
        n = float(valor)
    else:
        t = str(valor).strip().replace("$", "").replace(" ", "")
        if t.lower() in TOKENS_VACIOS:
            raise ValueError(f"número ausente: {valor!r}")
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"[+-]?\d{1,3}(\.\d{3})+", t):
            t = t.replace(".", "")
        n = float(t)
    if not math.isfinite(n):
        raise ValueError("número no finito")
    return n

def parse_fecha(valor):
    t = str(valor).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}T", t):
        return dt.datetime.fromisoformat(t.replace("Z", "+00:00")).date()
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d-%m-%y"):
        try:
            return dt.datetime.strptime(t, f).date()
        except ValueError:
            pass
    raise ValueError(f"fecha no reconocida: {valor!r}")

def escribir(nombre, filas):
    SALIDA.mkdir(exist_ok=True)
    if not filas:
        (SALIDA / nombre).unlink(missing_ok=True)
        return
    with (SALIDA / nombre).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)

def limpiar_precios():
    ruta = buscar("archivos/origen_costos_alimento.csv", "origen_costos_alimento.csv")
    texto = ruta.read_bytes()
    try:
        texto = texto.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = texto.decode("cp1252")
    crudas = list(csv.DictReader(texto.splitlines(), delimiter=";"))
    limpias, incidencias, vistos = [], [], {}
    registros = 0
    for i, r in enumerate(crudas, start=2): 
        tipo_crudo = (r["tipo_alimento"] or "").strip()
        if tipo_crudo == "tipo_alimento" or tipo_crudo.upper() == "TOTAL":
            incidencias.append({"fila_csv": i, "motivo": "fila_no_registro", "accion": "descartada", "detalle": tipo_crudo})
            continue
        registros += 1
        clave_tipo = re.sub(r"[\s\-_]", "", tipo_crudo.lower())
        tipo = TIPOS.get(clave_tipo)
        try:
            if tipo is None:
                raise ValueError(f"tipo de alimento desconocido: {tipo_crudo!r}")
            mes = r["mes"].strip()
            if not re.fullmatch(rf"{YEAR}-(0[1-9]|1[0-2])", mes):
                raise ValueError(f"mes fuera de {YEAR}: {mes!r}")
            if (r["moneda"] or "").strip().upper() != "CLP":
                raise ValueError(f"moneda distinta de CLP: {r['moneda']!r}")
            precio = parse_numero(r["precio_clp_kg"])
            if precio <= 0:
                raise ValueError("precio no positivo")
            if (tipo, mes) in vistos:
                raise ValueError("duplicado tipo-mes")
        except ValueError as e:
            incidencias.append({"fila_csv": i, "motivo": "registro_invalido", "accion": "excluido", "detalle": str(e)})
            continue
        vistos[(tipo, mes)] = precio
        limpias.append({"fila_csv": i, "tipo_alimento": tipo, "tipo_original": tipo_crudo, "mes": mes,
                        "precio_clp_kg": precio, "proveedor": r["proveedor"].strip()})
    huecos = [(t, f"{YEAR}-{m:02d}") for t in sorted(set(TIPOS.values())) for m in range(1, 13)
              if (t, f"{YEAR}-{m:02d}") not in vistos]
    return limpias, incidencias, registros, huecos

def limpiar_eventos():
    ruta = buscar("archivos/origen_eventos_sanitarios.json", "origen_eventos_sanitarios.json")
    eventos = json.loads(ruta.read_text(encoding="utf-8"))["eventos"]
    bd = buscar("output_persona1/datos_sqlite_limpios.sqlite", "datos_sqlite_limpios.sqlite")
    limpios, incidencias = [], []
    with closing(sqlite3.connect(bd.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        centros = {r[0]: r[1] for r in con.execute("SELECT centro_id, nombre FROM centros")}
        jaulas = collections.defaultdict(set)
        for jaula, centro in con.execute("SELECT jaula_id, centro_id FROM jaulas"):
            jaulas[centro].add(jaula)
        for e in eventos:
            eid, cid = e["evento_id"], e["centro_id"]
            try:
                if cid not in centros:
                    raise ValueError(f"el centro {cid} no existe en el catálogo")
                ini, fin = parse_fecha(e["fecha_inicio"]), parse_fecha(e["fecha_fin"])
                if str(e["fecha_fin"]) != fin.isoformat():
                    incidencias.append({"evento_id": eid, "motivo": "fecha_fin_reformateada", "accion": "corregido",
                                        "detalle": f"{e['fecha_fin']} -> {fin.isoformat()}"})
                if not (ini.year == YEAR and fin.year == YEAR and ini <= fin):
                    raise ValueError("fechas fuera de 2025 o fin anterior al inicio")
                declarada = parse_numero(e["mortalidad_asociada"])
                if declarada < 0:
                    raise ValueError("mortalidad declarada negativa")
                afect = list(e.get("jaulas_afectadas") or [])
                if not afect or not set(afect) <= jaulas[cid]:
                    raise ValueError("jaulas afectadas vacías o ajenas al centro")
            except ValueError as err:
                incidencias.append({"evento_id": eid, "motivo": "evento_invalido", "accion": "excluido", "detalle": str(err)})
                continue
            q = "SELECT COALESCE(SUM(mortalidad_n),0), COUNT(*) FROM operacion_limpia WHERE centro_id=? AND fecha BETWEEN ? AND ?"
            args = (cid, ini.isoformat(), fin.isoformat())
            muertes_centro, filas_centro = con.execute(q, args).fetchone()
            marcas = ",".join("?" * len(afect))
            muertes_jaulas, filas_jaulas = con.execute(q + f" AND jaula_id IN ({marcas})", args + tuple(afect)).fetchone()
            limpios.append({"evento_id": eid, "centro_id": cid, "centro": centros[cid], "tipo": e["tipo"],
                            "fecha_inicio": ini.isoformat(), "fecha_fin": fin.isoformat(), "tratamiento": e["tratamiento"],
                            "jaulas_afectadas": " ".join(map(str, afect)),
                            "mortalidad_declarada_json_n": int(declarada),
                            "mortalidad_observada_jaulas_afectadas_n": int(muertes_jaulas),
                            "mortalidad_observada_centro_n": int(muertes_centro),
                            "filas_operacion_jaulas_afectadas": filas_jaulas})
    return limpios, incidencias, len(eventos)

def validate_dollar_payload(payload):
    """valida la identidad y estructura de la captura antes de utilizarla"""
    if not isinstance(payload, dict) or payload.get('codigo') != 'dolar' or payload.get('unidad_medida') != 'Pesos':
        raise ValueError('Respuesta sin identidad de dólar en pesos')
    series = payload.get('serie')
    if not isinstance(series, list) or not series or not all(isinstance(row, dict) for row in series):
        raise ValueError('Serie del dólar vacía o inválida')
    return series


def clean_dollar_payload(payload):
    """conserva las exclusiones existentes para las observaciones del dólar"""
    series = validate_dollar_payload(payload)
    by_date, issues = {}, []
    for index, observation in enumerate(series):
        try:
            date = parse_fecha(observation["fecha"])
            value = parse_numero(observation["valor"])
            if date.year != YEAR or value <= 0:
                raise ValueError("fuera de 2025 o valor no positivo")
            if date in by_date:
                raise ValueError("fecha repetida")
        except (ValueError, KeyError, TypeError) as error:
            issues.append({"registro_api": index, "motivo": "registro_invalido", "accion": "excluido", "detalle": str(error)})
            continue
        by_date[date] = value
    rows = [{"fecha": date.isoformat(), "clp_por_usd": value} for date, value in sorted(by_date.items())]
    return rows, issues, len(series)


def limpiar_dolar(update_dollar=False):
    """usa la captura cruda y solo consulta la api cuando se solicita actualizar"""
    dolar_crudo_path = CARPETA / 'archivos' / f'dolar_{YEAR}_crudo.json'
    errors = []
    if update_dollar:
        try:
            with urllib.request.urlopen(API_DOLAR, timeout=15) as response:
                payload = json.loads(response.read().decode('utf-8'))
            rows, issues, count = clean_dollar_payload(payload)
            # una actualización debe ser íntegra para sustituir una captura válida
            if issues or not rows:
                raise ValueError('La nueva serie contiene registros inválidos')
            dolar_temporal_path = dolar_crudo_path.with_suffix('.tmp.json')
            try:
                dolar_temporal_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
                dolar_temporal_path.replace(dolar_crudo_path)
            finally:
                dolar_temporal_path.unlink(missing_ok=True)
            return rows, issues, count, 'API validada; captura actualizada'
        except (OSError, ValueError, TypeError) as error:
            errors.append(f'API fallida ({type(error).__name__}: {error})')
    try:
        payload = json.loads(dolar_crudo_path.read_text(encoding='utf-8'))
        rows, issues, count = clean_dollar_payload(payload)
        if not rows:
            return rows, issues, count, 'no disponible; captura sin observaciones válidas; ' + '; '.join(errors)
        return rows, issues, count, '; '.join(['captura archivos/dolar_2025_crudo.json', *errors])
    except (OSError, ValueError, TypeError) as error:
        errors.append(f'captura inválida o ausente ({type(error).__name__}: {error})')
        return [], [], 0, 'no disponible; ' + '; '.join(errors)

def main(update_dollar=False):
    SALIDA.mkdir(exist_ok=True)
    precios, inc_p, n_precios, huecos = limpiar_precios()
    eventos, inc_e, n_eventos = limpiar_eventos()
    dolar, inc_d, n_dolar, estado_dolar = limpiar_dolar(update_dollar)
    if not precios or not eventos:
        raise ValueError('Precios o eventos sin registros válidos: costos, basal y gráficos afectados')
    escribir("precios_limpios.csv", precios)
    escribir("eventos_limpios.csv", eventos)
    escribir("dolar_limpio.csv", dolar)
    escribir("incidencias_precios.csv", inc_p)
    escribir("incidencias_eventos.csv", inc_e)
    escribir("incidencias_dolar.csv", inc_d)

    cobertura = [
        {"fuente": "Precios (CSV)", "total": n_precios, "excluidos": sum(i["accion"] == "excluido" for i in inc_p)},
        {"fuente": "Eventos (JSON)", "total": n_eventos, "excluidos": sum(i["accion"] == "excluido" for i in inc_e)},
        {"fuente": "Dólar (API)", "total": n_dolar, "excluidos": sum(i["accion"] == "excluido" for i in inc_d)},
    ]
    total = sum(c["total"] for c in cobertura)
    fuera = sum(c["excluidos"] for c in cobertura)
    lineas = [f"{c['fuente']}: {c['excluidos']} de {c['total']} excluidos" + (f" ({100 * c['excluidos'] / c['total']:.1f}%)" if c["total"] else " (sin datos)")
              for c in cobertura]
    lineas.append(f"TOTAL: {fuera} de {total} registros fuera ({100 * fuera / total:.1f}%)")
    celdas = 3 * 12
    lineas.append(f"Cobertura de precios: {len(precios)} de {celdas} combinaciones tipo-mes con precio válido ({100 * len(precios) / celdas:.1f}%)")
    lineas.append("Combinaciones tipo-mes sin precio: " + "; ".join(f"{t} {m}" for t, m in huecos))
    lineas.append(f"Dólar: {estado_dolar}")
    (SALIDA / "cobertura.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--actualizar-dolar', action='store_true')
    main(parser.parse_args().actualizar_dolar)
