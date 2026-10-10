from __future__ import annotations
import argparse
import bisect
import collections
import csv
import datetime as datetime_lib
import hashlib
import json
import math
import re
import sqlite3
import time
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent
# estos supuestos y criterios determinan las exclusiones los precios y las métricas
DEFAULT_CONFIG = {
    'anio': 2025,
    'mezcla_alimento': {
        'engorda100': 0.3333333333333333,
        'engorda200': 0.3333333333333333,
        'pigmentado': 0.3333333333333333,
    },
    'precios_faltantes': 'promedio_anual_por_tipo_alimento',
    'fcr_diario_minimo_calidad': 0.1,
    'fcr_diario_maximo_advertencia': 10.0,
    'tolerancia_balance_poblacion_peces': 0,
    'zonas_inferidas_por_centro': {'7': 3},
    'basal': 'por_lote_dias_sin_eventos_sanitarios',
    'fcr_principal': 'alimento_dividido_por_crecimiento_reportado',
    'fcr_alternativo': 'alimento_dividido_por_crecimiento_menos_mortalidad_estimada',
    'peso_muertos': 'peso_promedio_vivos_estimado_por_biomasa_dividida_por_poblacion',
    'ranking_centro': 'costo_alimento_clp_dividido_por_crecimiento_reportado_kg',
}
MONTHS = {
    'ene': '01',
    'feb': '02',
    'mar': '03',
    'abr': '04',
    'may': '05',
    'jun': '06',
    'jul': '07',
    'ago': '08',
    'sep': '09',
    'oct': '10',
    'nov': '11',
    'dic': '12',
}
OPERATION_NUMERIC_FIELDS = ('alimento_kg', 'mortalidad_n', 'biomasa_kg', 'crecimiento_kg', 'temperatura_agua')
OPERATION_KEY_FIELDS = ('fecha', 'centro_id', 'jaula_id', 'lote_id')
FEED_ALIASES = {
    'engorda100': 'engorda100',
    'eng100': 'engorda100',
    'engorda200': 'engorda200',
    'eng200': 'engorda200',
    'pigmentado': 'pigmentado',
    'pig': 'pigmentado',
}

def parse_date(value):
    """convierte los formatos de fecha de las fuentes a año mes y día"""
    text = str(value).strip().lower()
    if re.match('^\\d{4}-\\d{2}-\\d{2}t', text):
        return datetime_lib.datetime.fromisoformat(text.replace('z', '+00:00')).date().isoformat()
    for word, number in MONTHS.items():
        text = text.replace(word, number)
    for date_format in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%y', '%d-%m-%Y'):
        try:
            return datetime_lib.datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f'Fecha no reconocida: {value!r}')

def parse_number(value):
    """interpreta cantidades con separadores de miles y decimales"""
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace('$', '').replace(' ', '')
        if text.lower() in ('', 'sindato', 'na', 'n/a', 'null', '-'):
            raise ValueError(f'Número ausente: {value!r}')
        if ',' in text:
            text = text.replace('.', '').replace(',', '.')
        elif re.fullmatch('[+-]?\\d{1,3}(\\.\\d{3})+', text):
            text = text.replace('.', '')
        number = float(text)
    if not math.isfinite(number):
        raise ValueError('Número no finito')
    return number

def write_json(file_path, value):
    """guarda datos en un archivo json legible"""
    file_path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def write_csv(file_path, rows, fields=None):
    """guarda registros en csv conservando las columnas de salida"""
    if fields is None:
        fields = list(dict.fromkeys((key for row in rows for key in row)))
    with file_path.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})

class Audit:
    """registra decisiones de calidad y cobertura por fuente"""

    def __init__(self):
        """inicializa el registro de incidencias y cobertura"""
        self.rows = []
        self.excluded = collections.defaultdict(set)
        self.counts = {}

    def add(self, source, index, reason, action='advertencia', detail=''):
        """registra una incidencia y cuenta una sola vez cada fila excluida"""
        self.rows.append({'fuente': source, 'registro': index, 'motivo': reason, 'accion': action, 'detalle': detail})
        if action == 'excluido':
            self.excluded[source].add(index)

    def coverage(self):
        """calcula cantidad y porcentaje de exclusiones por fuente"""
        result = []
        for source, total in self.counts.items():
            excluded = len(self.excluded[source])
            result.append({
                'fuente': source,
                'registros_entrada': total,
                'registros_excluidos': excluded,
                'registros_conservados': total - excluded,
                'porcentaje_excluido': 100 * excluded / total if total else 0,
            })
        return result

def read_sqlite(origen_acuicultura_path):
    """lee las tablas de sqlite en modo lectura y conserva la fila de origen"""
    with closing(sqlite3.connect(origen_acuicultura_path.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        names = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {name: [dict(row) for row in connection.execute(f'SELECT rowid AS origen_fila, * FROM "{name}"')] for name in names}

def read_csv(origen_costos_alimento_path):
    """lee el csv de precios usando punto y coma y codificación cp1252"""
    with origen_costos_alimento_path.open('r', encoding='cp1252', newline='') as csv_file:
        return list(csv.DictReader(csv_file, delimiter=';'))

def read_json(file_path):
    """lee un archivo json y devuelve sus datos como estructuras de python"""
    with file_path.open('r', encoding='utf-8') as json_file:
        return json.load(json_file)

def prepare_dimensions(tables, config, audit):
    """prepara centros y lotes conservando los identificadores originales"""
    zones = {record['zona_id']: record for record in tables['zonas']}
    centers = {record['centro_id']: dict(record) for record in tables['centros']}
    for center_id, center in centers.items():
        center['zona_id_original'] = center['zona_id']
        center['zona_inferida'] = 0
        if center['zona_id'] not in zones:
            labels = collections.Counter((record['zona'] for record in tables['operacion_diaria'] if record['centro_id'] == center_id))
            candidate, votes = labels.most_common(1)[0] if labels else (None, 0)
            inferred_zone = config['zonas_inferidas_por_centro'].get(str(center_id))
            if inferred_zone in zones:
                center['zona_id'] = inferred_zone
                center['zona_inferida'] = 1
                audit.add('centros', center['origen_fila'], 'zona_inexistente', 'inferido', f"Inferencia acordada: {zones[inferred_zone]['zona']}; etiqueta predominante {candidate}, {votes}/{sum(labels.values())} filas; identificador original conservado.")
            else:
                center['zona_id'] = None
                audit.add('centros', center['origen_fila'], 'zona_no_resuelta')
    lots = {record['lote_id']: dict(record) for record in tables['lotes']}
    for lot in lots.values():
        lot['fecha_siembra_original'] = lot['fecha_siembra']
        lot['fecha_siembra'] = parse_date(lot['fecha_siembra'])
    return (centers, lots)

def prepare_operation(tables, centers, lots, config, audit):
    """unifica formatos de fechas y números, aplica los criterios de calidad acordados y estima la biomasa perdida por mortalidad"""
    source = 'operacion_diaria'
    audit.counts[source] = len(tables[source])
    cages = {record['jaula_id']: record for record in tables['jaulas']}
    species = {record['especie_id'] for record in tables['especies']}
    groups = collections.defaultdict(list)
    for original in tables[source]:
        index = original['origen_fila']
        row = dict(original)
        row['fecha_original'] = row['fecha']
        row['mes_original'] = row['mes']
        try:
            row['fecha'] = parse_date(row['fecha'])
            for key in OPERATION_NUMERIC_FIELDS:
                row[key] = parse_number(row[key])
            for key in ('poblacion', 'mortalidad_n'):
                if row[key] != int(row[key]):
                    raise ValueError(f'{key} no es entero')
                row[key] = int(row[key])
        except (ValueError, TypeError) as error:
            audit.add(source, index, 'formato_invalido', 'excluido', str(error))
            continue
        if datetime_lib.date.fromisoformat(row['fecha']).year != config['anio']:
            audit.add(source, index, 'fuera_del_periodo', 'excluido')
            continue
        lot = lots.get(row['lote_id'])
        cage = cages.get(row['jaula_id'])
        if not lot or not cage or row['centro_id'] not in centers or (row['especie_id'] not in species) or any((row[key] != lot[key] for key in ('centro_id', 'jaula_id', 'especie_id'))) or (cage['centro_id'] != row['centro_id']):
            audit.add(source, index, 'referencia_inconsistente', 'excluido')
            continue
        if min((row[key] for key in ('alimento_kg', 'biomasa_kg', 'crecimiento_kg', 'poblacion'))) <= 0 or row['mortalidad_n'] < 0:
            audit.add(source, index, 'cantidad_invalida', 'excluido')
            continue
        row['mes'] = row['fecha'][:7]
        if int(row['mes_original']) != int(row['fecha'][5:7]):
            audit.add(source, index, 'mes_no_coincide_con_fecha', 'excluido', 'No se considera por inconsistencia entre mes y fecha.')
        if row['fecha'] < lot['fecha_siembra']:
            audit.add(source, index, 'operacion_antes_de_siembra', 'advertencia', 'Se conserva: inconsistencia de calendario del lote, sin evidencia para cambiar fecha.')
        groups[tuple((row[key] for key in OPERATION_KEY_FIELDS))].append(row)
    deduped = []
    compare_fields = ('especie_id', *OPERATION_NUMERIC_FIELDS, 'poblacion', 'zona')
    for key, rows in sorted(groups.items()):
        signatures = {tuple((record[key] for key in compare_fields)) for record in rows}
        if len(signatures) > 1:
            for row in rows:
                audit.add(source, row['origen_fila'], 'duplicado_conflictivo', 'excluido', str(key))
            continue
        rows.sort(key=lambda record: record['origen_fila'])
        deduped.append(rows[0])
        for row in rows[1:]:
            audit.add(source, row['origen_fila'], 'duplicado_identico', 'excluido', str(key))
    # comparamos días consecutivos antes de aplicar las exclusiones acumuladas
    # así una fila excluida todavía permite comprobar el balance del día anterior
    lookup = {(record['lote_id'], record['fecha']): record for record in deduped}
    result, balance_errors = ([], [])
    for row in deduped:
        index = row['origen_fila']
        current = datetime_lib.date.fromisoformat(row['fecha'])
        tomorrow = lookup.get((row['lote_id'], (current + datetime_lib.timedelta(days=1)).isoformat()))
        if tomorrow:
            observed_loss = row['poblacion'] - tomorrow['poblacion']
            if abs(observed_loss - row['mortalidad_n']) > config['tolerancia_balance_poblacion_peces']:
                audit.add(source, index, 'mortalidad_incompatible_con_balance', 'excluido', f"mortalidad={row['mortalidad_n']}; caída de población siguiente={observed_loss}; se supone ausencia de movimientos no registrados")
        ratio = row['alimento_kg'] / row['crecimiento_kg']
        if ratio < config['fcr_diario_minimo_calidad']:
            audit.add(source, index, 'alimento_crecimiento_demasiado_bajo', 'excluido', f'Razón diaria={ratio}; no considerada por ruido en los datos.')
        elif ratio > config['fcr_diario_maximo_advertencia']:
            audit.add(source, index, 'alimento_crecimiento_alto', 'advertencia', f'Razón diaria={ratio}; se conserva porque puede representar baja eficiencia real.')
        if index in audit.excluded[source]:
            continue
        yesterday = lookup.get((row['lote_id'], (current - datetime_lib.timedelta(days=1)).isoformat()))
        if yesterday and yesterday['origen_fila'] not in audit.excluded[source] and yesterday['poblacion'] - yesterday['mortalidad_n'] == row['poblacion']:
            predicted = row['crecimiento_kg'] - yesterday['mortalidad_n'] * yesterday['biomasa_kg'] / yesterday['poblacion']
            balance_errors.append(abs(row['biomasa_kg'] - yesterday['biomasa_kg'] - predicted))
        # estimamos el peso de los muertos con el peso promedio de los peces vivos
        row['peso_promedio_estimado_kg'] = row['biomasa_kg'] / row['poblacion']
        row['mortalidad_biomasa_estimada_kg'] = row['mortalidad_n'] * row['peso_promedio_estimado_kg']
        row['crecimiento_menos_mortalidad_estimado_kg'] = row['crecimiento_kg'] - row['mortalidad_biomasa_estimada_kg']
        result.append(row)
    evidence = {
        'pares_diarios_comparables': len(balance_errors),
        'error_absoluto_mediano_balance_biomasa_kg': sorted(balance_errors)[len(balance_errors) // 2] if balance_errors else None,
        'interpretacion': 'Inferido: crecimiento reportado parece anterior a descontar mortalidad; no es definición confirmada por cliente.',
    }
    return (result, evidence)

def prepare_prices(origen_costos_alimento_path, config, audit):
    """estandariza precios y estima los faltantes y la mezcla de alimento"""
    source = 'costos_alimento'
    encoding = 'cp1252'
    original_rows = read_csv(origen_costos_alimento_path)
    audit.counts[source] = len(original_rows)
    prices = {}
    missing_indexes = {}
    for index, original in enumerate(original_rows, start=2):
        row = dict(original)
        name = row['tipo_alimento']
        if name == 'tipo_alimento' or name.upper() == 'TOTAL':
            audit.add(source, index, 'fila_no_es_dato', 'excluido', name)
            continue
        alias = re.sub('[^a-z0-9]', '', name.lower())
        feed = FEED_ALIASES.get(alias)
        if not feed or row['moneda'].strip().upper() != 'CLP' or (not re.fullmatch(f"{config['anio']}-\\d{{2}}", row['mes'])):
            audit.add(source, index, 'precio_no_integrable', 'excluido')
            continue
        key = (feed, row['mes'])
        if key in prices or key in missing_indexes:
            raise ValueError(f'Precio duplicado, requiere decisión: {key}')
        try:
            price = parse_number(row['precio_clp_kg'])
            if price <= 0:
                raise ValueError('Precio no positivo')
        except ValueError:
            missing_indexes[key] = index
            audit.add(source, index, 'precio_sin_dato', 'estimado', 'promedio anual del mismo tipo de alimento, valor original conservado en archivos')
            continue
        prices[key] = {
            'tipo_alimento': feed,
            'mes': row['mes'],
            'precio_clp_kg': price,
            'precio_estimado': 0,
            'proveedor': row['proveedor'],
            'metodo': 'observado',
            'origen_fila': index,
        }
    # las proporciones de alimento son un supuesto porque la entrevista no entrega cantidades
    weights = config['mezcla_alimento']
    if not weights or any((value < 0 for value in weights.values())) or (not math.isclose(sum(weights.values()), 1, abs_tol=1e-09)):
        raise ValueError('Los pesos de la mezcla deben ser no negativos y sumar 1')
    # usamos solo precios observados del mismo alimento para calcular el promedio anual
    observed = dict(prices)
    for feed in weights:
        available_prices = [
            row['precio_clp_kg']
            for (feed_type, period), row in observed.items()
            if feed_type == feed
        ]
        if not available_prices:
            raise ValueError(f'No hay precios válidos para calcular el promedio de {feed}')
        annual_average = math.fsum(available_prices) / len(available_prices)
        for month in range(1, 13):
            key = (feed, f"{config['anio']}-{month:02d}")
            if key in prices:
                continue
            prices[key] = {
                'tipo_alimento': feed,
                'mes': key[1],
                'precio_clp_kg': annual_average,
                'precio_estimado': 1,
                'proveedor': None,
                'metodo': 'promedio_anual_por_tipo_alimento',
                'origen_fila': missing_indexes.get(key),
            }
            if key not in missing_indexes:
                audit.add(source, f'ausente:{feed}:{key[1]}', 'combinacion_mes_tipo_ausente', 'estimado', 'promedio anual del mismo tipo de alimento')
    mixes = {}
    for month in range(1, 13):
        period = f"{config['anio']}-{month:02d}"
        entries = [prices[feed, period] for feed in weights if weights[feed] > 0]
        mixes[period] = {
            'mes': period,
            'precio_mezcla_clp_kg': sum((weights[entry['tipo_alimento']] * entry['precio_clp_kg'] for entry in entries)),
            'precio_minimo_clp_kg': min((entry['precio_clp_kg'] for entry in entries)),
            'precio_maximo_clp_kg': max((entry['precio_clp_kg'] for entry in entries)),
            'incluye_precio_estimado': int(any((entry['precio_estimado'] for entry in entries))),
            'mezcla_estimada': 1,
        }
    return ([prices[key] for key in sorted(prices)], mixes, encoding)

def prepare_events(origen_eventos_sanitarios_path, tables, config, audit):
    """prepara eventos sanitarios y verifica centros fechas y jaulas"""
    original = read_json(origen_eventos_sanitarios_path)
    audit.counts['eventos_sanitarios'] = len(original['eventos'])
    centers = {record['centro_id'] for record in tables['centros']}
    cages = {record['jaula_id']: record['centro_id'] for record in tables['jaulas']}
    result, seen = ([], set())
    for index, original in enumerate(original['eventos'], start=1):
        row = dict(original)
        row['origen_fila'] = index
        try:
            row['fecha_inicio'] = parse_date(row['fecha_inicio'])
            row['fecha_fin'] = parse_date(row['fecha_fin'])
            row['mortalidad_asociada'] = parse_number(row['mortalidad_asociada'])
            if row['centro_id'] not in centers:
                raise ValueError('Centro inexistente')
            if row['fecha_inicio'] > row['fecha_fin'] or row['mortalidad_asociada'] < 0:
                raise ValueError('Fechas o mortalidad inválidas')
            if any((cages.get(cage_id) != row['centro_id'] for cage_id in row['jaulas_afectadas'])):
                raise ValueError('Jaula no corresponde al centro')
            if row['evento_id'] in seen:
                raise ValueError('ID de evento sanitario duplicado')
        except (ValueError, KeyError) as error:
            audit.add('eventos_sanitarios', index, 'evento_sanitario_no_integrable', 'excluido', str(error))
            continue
        seen.add(row['evento_id'])
        if not row['jaulas_afectadas']:
            audit.add('eventos_sanitarios', index, 'jaulas_sin_especificar', 'advertencia', 'Sin jaulas identificadas no se vinculan filas de operación al evento sanitario.')
        result.append(row)
    return result

def read_api(dolar_2025_path, dolar_2025_metadata_path, year, update=False):
    """consulta el dólar o reutiliza su respuesta guardada para reproducir resultados"""
    url = f'https://mindicador.cl/api/dolar/{year}'
    if update or not dolar_2025_path.exists():
        request = urllib.request.Request(url, headers={'User-Agent': 'AquaFiordo-E1/1.0'})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
        validate_fx(data, year)
        write_json(dolar_2025_path, data)
        write_json(dolar_2025_metadata_path, {
            'url': url,
            'consultado_en': datetime_lib.datetime.now(datetime_lib.timezone.utc).isoformat(),
            'observaciones': len(data['serie']),
        })
    data = read_json(dolar_2025_path)
    validate_fx(data, year)
    return ([{'fecha': parse_date(row['fecha']), 'dolar_clp_por_usd': parse_number(row['valor'])} for row in sorted(data['serie'], key=lambda row: parse_date(row['fecha']))], url)

def validate_fx(data, year):
    """verifica que la serie del dólar tenga fechas únicas y valores positivos"""
    if data.get('codigo') != 'dolar' or not data.get('serie'):
        raise ValueError('Respuesta API inválida o sin serie')
    dates = set()
    for row in data['serie']:
        date = parse_date(row['fecha'])
        if date[:4] != str(year) or date in dates or parse_number(row['valor']) <= 0:
            raise ValueError('Observación de dólar inválida o repetida')
        dates.add(date)

def prepare_harvests(tables, lots, config, audit):
    """prepara cosechas y verifica sus lotes período y kilos"""
    audit.counts['cosechas'] = len(tables['cosechas'])
    result = []
    for original in tables['cosechas']:
        row = dict(original)
        try:
            row['fecha'] = parse_date(row['fecha'])
            row['kilos_vivos'] = parse_number(row['kilos_vivos'])
            row['kilos_producto'] = parse_number(row['kilos_producto'])
            lot = lots.get(row['lote_id'])
            if not lot or lot['centro_id'] != row['centro_id']:
                raise ValueError('Lote inexistente o centro inconsistente')
            if row['fecha'][:4] != str(config['anio']) or not 0 < row['kilos_producto'] <= row['kilos_vivos']:
                raise ValueError('Período o kilos inconsistentes')
        except (ValueError, KeyError) as error:
            audit.add('cosechas', row['origen_fila'], 'cosecha_no_integrable', 'excluido', str(error))
            continue
        result.append(row)
    return result

def integrate(operation, centers, lots, tables, mixes, events, exchange_rates, audit):
    """cruza operación con precios dólar y eventos sanitarios sin multiplicar filas"""
    zones = {record['zona_id']: record['zona'] for record in tables['zonas']}
    species = {record['especie_id']: record['especie'] for record in tables['especies']}
    exchange_rate_dates = [record['fecha'] for record in exchange_rates]
    bridge = []
    for row in operation:
        row['operacion_id'] = f"{row['fecha']}:{row['centro_id']}:{row['jaula_id']}:{row['lote_id']}"
        center = centers[row['centro_id']]
        row['nombre_centro'] = center['nombre']
        row['zona_id'] = center['zona_id']
        row['zona_original'] = row['zona']
        row['zona'] = zones.get(center['zona_id'], row['zona'])
        if row['zona'] != row['zona_original']:
            audit.add('operacion_diaria', row['origen_fila'], 'etiqueta_zona_no_coincide', 'normalizado', 'Se usa zona del centro; etiqueta original conservada.')
        row['zona_inferida'] = center['zona_inferida']
        row['especie'] = species[row['especie_id']]
        row['fecha_siembra'] = lots[row['lote_id']]['fecha_siembra']
        row.update({key: value for key, value in mixes[row['mes']].items() if key != 'mes'})
        row['costo_alimento_estimado_clp'] = row['alimento_kg'] * row['precio_mezcla_clp_kg']
        row['costo_alimento_minimo_clp'] = row['alimento_kg'] * row['precio_minimo_clp_kg']
        row['costo_alimento_maximo_clp'] = row['alimento_kg'] * row['precio_maximo_clp_kg']
        # usamos el último dólar disponible, el inicio del año tiene una regla explícita
        position = bisect.bisect_right(exchange_rate_dates, row['fecha']) - 1
        chosen = exchange_rates[max(0, position)]
        row['fecha_dolar_utilizada'] = chosen['fecha']
        row['dolar_clp_por_usd'] = chosen['dolar_clp_por_usd']
        row['dolar_metodo'] = 'primer_valor_del_anio' if position < 0 else 'mismo_dia' if chosen['fecha'] == row['fecha'] else 'ultimo_dia_disponible'
        row['costo_alimento_estimado_usd'] = row['costo_alimento_estimado_clp'] / row['dolar_clp_por_usd']
        row['evento_sanitario_ids'] = []
        for event in events:
            if row['centro_id'] == event['centro_id'] and event['fecha_inicio'] <= row['fecha'] <= event['fecha_fin'] and row['jaula_id'] in event['jaulas_afectadas']:
                row['evento_sanitario_ids'].append(event['evento_id'])
                bridge.append({'operacion_id': row['operacion_id'], 'evento_id': event['evento_id']})
        row['tiene_evento_sanitario'] = int(bool(row['evento_sanitario_ids']))
        if len(row['evento_sanitario_ids']) > 1:
            audit.add('operacion_diaria', row['origen_fila'], 'eventos_sanitarios_superpuestos', 'advertencia', 'Resumen por centro cuenta la fila una vez; resumen por evento sanitario puede superponerse.')
    return bridge

def calculate_baseline(operation, events):
    """estima mortalidad basal por lote y exceso durante eventos sanitarios"""
    totals = collections.defaultdict(lambda: [0, 0, 0])
    for row in operation:
        if not row['tiene_evento_sanitario']:
            lot_totals = totals[row['lote_id']]
            lot_totals[0] += row['mortalidad_n']
            lot_totals[1] += row['poblacion']
            lot_totals[2] += 1
    # la tasa basal usa días sin eventos sanitarios del mismo lote
    baseline = []
    for lot in sorted({record['lote_id'] for record in operation}):
        deaths, exposure, days = totals[lot]
        baseline.append({
            'lote_id': lot,
            'dias_sin_eventos_sanitarios': days,
            'muertes_sin_eventos_sanitarios': deaths,
            'exposicion_poblacion_dias': exposure,
            'tasa_basal_diaria': deaths / exposure if exposure else None,
        })
    rates = {record['lote_id']: record['tasa_basal_diaria'] for record in baseline}
    # el exceso sobre la basal estima muertes atribuibles al evento sanitario bajo este supuesto
    for row in operation:
        rate = rates[row['lote_id']]
        row['tasa_basal_diaria'] = rate
        row['mortalidad_esperada_basal_n'] = row['poblacion'] * rate if rate is not None else None
        row['exceso_mortalidad_n'] = row['mortalidad_n'] - row['mortalidad_esperada_basal_n'] if row['tiene_evento_sanitario'] and rate is not None else None
    summaries = []
    for event in events:
        rows = [record for record in operation if event['evento_id'] in record['evento_sanitario_ids']]
        usable = bool(rows) and all((record['mortalidad_esperada_basal_n'] is not None for record in rows))
        actual = sum((record['mortalidad_n'] for record in rows))
        expected = sum((record['mortalidad_esperada_basal_n'] for record in rows)) if usable else None
        summaries.append({
            'evento_id': event['evento_id'],
            'centro_id': event['centro_id'],
            'tipo': event['tipo'],
            'fecha_inicio': event['fecha_inicio'],
            'fecha_fin': event['fecha_fin'],
            'filas_operacion_con_evento_sanitario': len(rows),
            'mortalidad_observada_durante_evento_n': actual if rows else None,
            'mortalidad_esperada_basal_n': expected,
            'exceso_mortalidad_estimado_n': actual - expected if expected is not None else None,
            'mortalidad_asociada_declarada_json_n': event['mortalidad_asociada'],
            'interpretacion': 'La mortalidad diaria observada durante el evento sanitario incluye todas las causas, el exceso sobre la basal estima su efecto bajo el supuesto acordado y no demuestra causalidad',
            'estimacion_disponible': int(usable),
        })
    return (baseline, summaries)

def aggregate(rows, keys):
    """suma componentes por grupo y calcula los indicadores después de agregar"""
    groups = collections.defaultdict(list)
    for row in rows:
        groups[tuple((row[key] for key in keys))].append(row)
    result = []
    for key, members in sorted(groups.items()):
        totals = {key: sum((record[key] for record in members)) for key in ('alimento_kg', 'crecimiento_kg', 'mortalidad_n', 'mortalidad_biomasa_estimada_kg', 'crecimiento_menos_mortalidad_estimado_kg', 'costo_alimento_estimado_clp', 'costo_alimento_estimado_usd', 'costo_alimento_minimo_clp', 'costo_alimento_maximo_clp')}
        row = dict(zip(keys, key))
        row['nombre_centro'] = members[0]['nombre_centro']
        row.update(totals)
        row['filas_operacion'] = len(members)
        gross = totals['crecimiento_kg']
        net = totals['crecimiento_menos_mortalidad_estimado_kg']
        row['fcr_principal'] = totals['alimento_kg'] / gross if gross > 0 else None
        row['fcr_alternativo'] = totals['alimento_kg'] / net if net > 0 else None
        row['diferencia_fcr'] = row['fcr_alternativo'] - row['fcr_principal'] if net > 0 and gross > 0 else None
        row['variacion_fcr_porcentaje'] = 100 * row['diferencia_fcr'] / row['fcr_principal'] if row['diferencia_fcr'] is not None and row['fcr_principal'] > 0 else None
        row['costo_alimento_clp_por_kg_crecimiento'] = totals['costo_alimento_estimado_clp'] / gross if gross > 0 else None
        row['costo_alimento_clp_por_kg_crecimiento_alternativo'] = totals['costo_alimento_estimado_clp'] / net if net > 0 else None
        row['costo_minimo_clp_por_kg_crecimiento'] = totals['costo_alimento_minimo_clp'] / gross if gross > 0 else None
        row['costo_maximo_clp_por_kg_crecimiento'] = totals['costo_alimento_maximo_clp'] / gross if gross > 0 else None
        exposed = [record for record in members if record['tiene_evento_sanitario']]
        expected_ok = bool(exposed) and all((record['mortalidad_esperada_basal_n'] is not None for record in exposed))
        row['mortalidad_observada_en_eventos_sanitarios_n'] = sum((record['mortalidad_n'] for record in exposed))
        row['mortalidad_esperada_en_eventos_sanitarios_n'] = sum((record['mortalidad_esperada_basal_n'] for record in exposed)) if expected_ok else None
        row['exceso_mortalidad_eventos_sanitarios_n'] = row['mortalidad_observada_en_eventos_sanitarios_n'] - row['mortalidad_esperada_en_eventos_sanitarios_n'] if expected_ok else None
        row['filas_con_precio_estimado'] = sum((record['incluye_precio_estimado'] for record in members))
        result.append(row)
    return result

def save_database(file_path, datasets):
    """guarda las tablas procesadas en el archivo sqlite de resultados"""
    temporary_path = file_path.with_suffix('.tmp.sqlite')
    temporary_path.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(temporary_path)) as connection, connection:
            for name, rows in datasets.items():
                if not rows:
                    continue
                fields = list(dict.fromkeys((key for row in rows for key in row)))
                definitions = []
                for field in fields:
                    values = [record.get(field) for record in rows if record.get(field) is not None]
                    kind = 'INTEGER' if values and all((isinstance(value, int) for value in values)) else 'REAL' if values and all((isinstance(value, (int, float)) for value in values)) else 'TEXT'
                    definitions.append(f'"{field}" {kind}')
                connection.execute(f'''CREATE TABLE "{name}" ({', '.join(definitions)})''')
                connection.executemany(f'''INSERT INTO "{name}" VALUES ({','.join(('?' for _ in fields))})''', [[json.dumps(record.get(key), ensure_ascii=False) if isinstance(record.get(key), (dict, list)) else record.get(key) for key in fields] for record in rows])
            connection.execute('CREATE UNIQUE INDEX clave_operacion ON operacion_integrada(fecha,centro_id,jaula_id,lote_id)')
            if datasets['puente_eventos_operacion']:
                connection.execute('CREATE UNIQUE INDEX clave_exposicion ON puente_eventos_operacion(operacion_id,evento_id)')
            connection.execute('CREATE INDEX fecha_operacion ON operacion_integrada(fecha)')
        # la conexión ya está cerrada para evitar bloqueo del archivo en windows
        temporary_path.replace(file_path)
    finally:
        temporary_path.unlink(missing_ok=True)

def validate_outputs(operation, summary, bridge, events, coverage):
    """verifica claves cobertura y conciliación de totales"""
    if not operation:
        raise ValueError('No quedó operación válida')
    keys = [tuple((record[key] for key in OPERATION_KEY_FIELDS)) for record in operation]
    assert len(keys) == len(set(keys)), 'Cruces duplicaron operación'
    assert len({(record['operacion_id'], record['evento_id']) for record in bridge}) == len(bridge)
    assert {record['evento_id'] for record in bridge} <= {record['evento_id'] for record in events}
    for column_name in ('alimento_kg', 'crecimiento_kg', 'costo_alimento_estimado_clp', 'mortalidad_n'):
        assert math.isclose(sum((record[column_name] for record in operation)), sum((record[column_name] for record in summary)), rel_tol=1e-09)
    for row in coverage:
        assert row['registros_entrada'] == row['registros_conservados'] + row['registros_excluidos']
    for row in operation:
        assert row['costo_alimento_minimo_clp'] <= row['costo_alimento_estimado_clp'] + 1e-06 <= row['costo_alimento_maximo_clp'] + 1e-05

def run(input_folder, output_folder, config, update_dollar=False):
    """ejecuta la lectura, preparación, integración, verificación y escritura de resultados"""
    started = time.perf_counter()
    # el costo considerado es el de alimento y el ranking usa costo por kg de crecimiento
    expected = {
        'basal': 'por_lote_dias_sin_eventos_sanitarios',
        'fcr_principal': 'alimento_dividido_por_crecimiento_reportado',
        'fcr_alternativo': 'alimento_dividido_por_crecimiento_menos_mortalidad_estimada',
        'peso_muertos': 'peso_promedio_vivos_estimado_por_biomasa_dividida_por_poblacion',
        'ranking_centro': 'costo_alimento_clp_dividido_por_crecimiento_reportado_kg',
        'precios_faltantes': 'promedio_anual_por_tipo_alimento',
    }
    for key, value in expected.items():
        if config[key] != value:
            raise ValueError(f'Opción no implementada: {key}={config[key]}')
    audit = Audit()
    origen_acuicultura_path = input_folder / 'origen_acuicultura.sqlite'
    origen_costos_alimento_path = input_folder / 'origen_costos_alimento.csv'
    origen_eventos_sanitarios_path = input_folder / 'origen_eventos_sanitarios.json'
    dolar_2025_path = input_folder / f"dolar_{config['anio']}.json"
    dolar_2025_metadata_path = input_folder / f"dolar_{config['anio']}_metadata.json"
    tables = read_sqlite(origen_acuicultura_path)
    centers, lots = prepare_dimensions(tables, config, audit)
    operation, evidence = prepare_operation(tables, centers, lots, config, audit)
    prices, mixes, encoding = prepare_prices(origen_costos_alimento_path, config, audit)
    events = prepare_events(origen_eventos_sanitarios_path, tables, config, audit)
    download_dollar = update_dollar or not dolar_2025_path.exists()
    exchange_rates, api_url = read_api(dolar_2025_path, dolar_2025_metadata_path, config['anio'], update_dollar)
    audit.counts['dolar_api'] = len(exchange_rates)
    harvests = prepare_harvests(tables, lots, config, audit)
    bridge = integrate(operation, centers, lots, tables, mixes, events, exchange_rates, audit)
    baseline, event_summary = calculate_baseline(operation, events)
    summary = aggregate(operation, ['centro_id'])
    summary.sort(key=lambda record: record['costo_alimento_clp_por_kg_crecimiento'], reverse=True)
    for rank, row in enumerate(summary, start=1):
        row['puesto_costo_por_kg'] = rank
    monthly = aggregate(operation, ['centro_id', 'mes'])
    coverage = audit.coverage()
    validate_outputs(operation, summary, bridge, events, coverage)
    output_folder.mkdir(parents=True, exist_ok=True)
    # cada tabla mantiene su grano, cosechas y eventos sanitarios quedan separados
    datasets = {
        'operacion_integrada': operation,
        'centros': list(centers.values()),
        'zonas': tables['zonas'],
        'jaulas': tables['jaulas'],
        'lotes': list(lots.values()),
        'especies': tables['especies'],
        'cosechas': harvests,
        'precios_alimento': prices,
        'mezcla_mensual': list(mixes.values()),
        'eventos_sanitarios': events,
        'dolar_observado': exchange_rates,
        'puente_eventos_operacion': bridge,
        'basal_por_lote': baseline,
        'resumen_eventos_sanitarios': event_summary,
        'resumen_centros': summary,
        'resumen_centro_mes': monthly,
        'cobertura': coverage,
        'incidencias_calidad': audit.rows,
    }
    save_database(output_folder / 'datos_integrados.sqlite', datasets)
    for name in ('operacion_integrada', 'precios_alimento', 'mezcla_mensual', 'basal_por_lote', 'resumen_eventos_sanitarios', 'resumen_centros', 'resumen_centro_mes', 'cobertura', 'incidencias_calidad'):
        write_csv(output_folder / f'{name}.csv', datasets[name])
    write_json(output_folder / 'config_utilizada.json', config)
    write_json(output_folder / 'verificacion_crecimiento.json', evidence)
    # los hashes permiten identificar la versión exacta de las fuentes utilizadas
    hashes = {source_path.name: hashlib.sha256(source_path.read_bytes()).hexdigest() for source_path in sorted(input_folder.iterdir()) if source_path.is_file()}
    run_info = {
        'api_url': api_url,
        'api_modo': 'actualizada' if download_dollar else 'respuesta_conservada',
        'csv_codificacion': encoding,
        'supuesto_crecimiento': 'El crecimiento reportado se interpreta como anterior a descontar la biomasa perdida por mortalidad, inferencia no confirmada por el cliente',
        'supuesto_peso_muertos': 'Se estima con el peso promedio de los peces vivos del mismo registro diario',
        'alcance_costos': 'Solo alimento, ranking por costo estimado de alimento por kg de crecimiento reportado',
        'sha256_fuentes': hashes,
        'filas_por_tabla': {name: len(rows) for name, rows in datasets.items()},
        'verificaciones': 'claves únicas; cruces sin multiplicar filas; totales conciliados; cobertura conciliada; costos dentro del rango de mezcla',
        'duracion_segundos': round(time.perf_counter() - started, 3),
    }
    write_json(output_folder / 'ejecucion.json', run_info)
    print(f'OK: {len(operation):,} filas integradas; {len(events)} eventos sanitarios válidos; {len(exchange_rates)} observaciones de dólar.')
    print(f'Salidas: {output_folder}')
    for row in coverage:
        print(f"{row['fuente']}: {row['registros_excluidos']}/{row['registros_entrada']} excluidos ({row['porcentaje_excluido']:.2f}%).")
    print('Resultados sujetos a los supuestos registrados en config_utilizada.json y ejecucion.json')

def main():
    """recibe opciones de ejecución y organiza el proceso completo"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--datos', dest='input_folder', type=Path, default=PROJECT_FOLDER / 'archivos')
    parser.add_argument('--salida', dest='output_folder', type=Path, default=PROJECT_FOLDER / 'output')
    parser.add_argument('--config', dest='config_path', type=Path, default=None)
    parser.add_argument('--actualizar-dolar', dest='update_dollar', action='store_true', help='Consulta mindicador y reemplaza la respuesta conservada.')
    arguments = parser.parse_args()
    try:
        run(arguments.input_folder.resolve(), arguments.output_folder.resolve(), read_json(arguments.config_path) if arguments.config_path else DEFAULT_CONFIG, arguments.update_dollar)
    except (ValueError, OSError, KeyError, sqlite3.Error, urllib.error.URLError) as error:
        parser.exit(1, f'ERROR: {error}\n')


if __name__ == '__main__':
    main()
