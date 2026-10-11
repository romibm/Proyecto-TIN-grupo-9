import collections
import datetime as datetime_lib
import math
import re
import sqlite3
from contextlib import closing
from pathlib import Path

YEAR = 2025
MIN_FEED_GROWTH_RATIO = 0.1
HIGH_FEED_GROWTH_RATIO = 10.0
INFERRED_ZONE_BY_CENTER = {7: 3}
MONTHS = {
    'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04',
    'may': '05', 'jun': '06', 'jul': '07', 'ago': '08',
    'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12',
}
OPERATION_NUMERIC_FIELDS = (
    'alimento_kg', 'mortalidad_n', 'biomasa_kg',
    'crecimiento_kg', 'temperatura_agua',
)
OPERATION_KEY_FIELDS = ('fecha', 'centro_id', 'jaula_id', 'lote_id')
REQUIRED_TABLES = ('centros', 'zonas', 'jaulas', 'lotes', 'especies', 'operacion_diaria', 'cosechas')

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

class Audit:
    """registra incidencias de sqlite y las filas excluidas por cada regla"""

    def __init__(self):
        """inicializa el registro de incidencias y los identificadores excluidos"""
        self.rows = []
        self.excluded = collections.defaultdict(set)

    def add(self, source, index, reason, action='advertencia', detail=''):
        """registra una incidencia y conserva los identificadores de las filas excluidas"""
        self.rows.append({'fuente': source, 'registro': index, 'motivo': reason, 'accion': action, 'detalle': detail})
        if action == 'excluido':
            self.excluded[source].add(index)

def read_sqlite(origen_acuicultura_path):
    """lee las tablas de sqlite en modo lectura y conserva la fila de origen"""
    with closing(sqlite3.connect(origen_acuicultura_path.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        return {name: [dict(row) for row in connection.execute('SELECT rowid AS origen_fila, * FROM ' + quote_identifier(name))] for name in REQUIRED_TABLES}

def prepare_dimensions(tables, audit):
    """prepara centros y lotes conservando los identificadores originales"""
    zones = {record['zona_id']: record for record in tables['zonas']}
    centers = {record['centro_id']: dict(record) for record in tables['centros']}
    for center_id, center in centers.items():
        center['zona_id_original'] = center['zona_id']
        center['zona_inferida'] = 0
        if center['zona_id'] not in zones:
            inferred_zone = INFERRED_ZONE_BY_CENTER.get(center_id)
            if inferred_zone in zones:
                center['zona_id'] = inferred_zone
                center['zona_inferida'] = 1
                audit.add('centros', center['origen_fila'], 'zona_inexistente', 'inferido', f"Inferencia acordada: {zones[inferred_zone]['zona']}; identificador original conservado")
            else:
                center['zona_id'] = None
                audit.add('centros', center['origen_fila'], 'zona_no_resuelta')
    lots = {record['lote_id']: dict(record) for record in tables['lotes']}
    for lot in lots.values():
        lot['fecha_siembra_original'] = lot['fecha_siembra']
        lot['fecha_siembra'] = parse_date(lot['fecha_siembra'])
    return (centers, lots)

def prepare_operation(tables, centers, lots, audit):
    """unifica formatos de fechas y números y aplica los criterios de calidad acordados para sqlite"""
    source = 'operacion_diaria'
    zones = {record['zona_id']: record['zona'] for record in tables['zonas']}
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
        if datetime_lib.date.fromisoformat(row['fecha']).year != YEAR:
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
    result = []
    for row in deduped:
        index = row['origen_fila']
        current = datetime_lib.date.fromisoformat(row['fecha'])
        tomorrow = lookup.get((row['lote_id'], (current + datetime_lib.timedelta(days=1)).isoformat()))
        if tomorrow:
            observed_loss = row['poblacion'] - tomorrow['poblacion']
            if observed_loss != row['mortalidad_n']:
                audit.add(source, index, 'mortalidad_incompatible_con_balance', 'excluido', f"mortalidad={row['mortalidad_n']}; caída de población siguiente={observed_loss}; se supone ausencia de movimientos no registrados")
        ratio = row['alimento_kg'] / row['crecimiento_kg']
        if ratio < MIN_FEED_GROWTH_RATIO:
            audit.add(source, index, 'alimento_crecimiento_demasiado_bajo', 'excluido', f'Razón diaria={ratio}; no considerada por ruido en los datos.')
        elif ratio > HIGH_FEED_GROWTH_RATIO:
            audit.add(source, index, 'alimento_crecimiento_alto', 'advertencia', f'Razón diaria={ratio}; se conserva porque puede representar baja eficiencia real.')
        if index in audit.excluded[source]:
            continue
        # corregimos la etiqueta de zona según el criterio acordado y guardamos el valor anterior
        row['zona_original'] = row['zona']
        row['zona'] = zones.get(centers[row['centro_id']]['zona_id'], row['zona'])
        if row['zona'] != row['zona_original']:
            audit.add(source, index, 'etiqueta_zona_no_coincide', 'corregido', 'Se utiliza la zona del centro y se conserva zona_original')
        result.append(row)
    return result

def prepare_harvests(tables, lots, audit):
    """prepara cosechas y verifica sus lotes período y kilos"""
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
            if row['fecha'][:4] != str(YEAR) or not 0 < row['kilos_producto'] <= row['kilos_vivos']:
                raise ValueError('Período o kilos inconsistentes')
        except (ValueError, KeyError) as error:
            audit.add('cosechas', row['origen_fila'], 'cosecha_invalida', 'excluido', str(error))
            continue
        result.append(row)
    return result

def quote_identifier(value):
    """protege los nombres de tablas y columnas usados en las consultas sqlite"""
    return '"' + value.replace('"', '""') + '"'

def save_sqlite(datos_sqlite_limpios_path, datasets):
    """guarda los datos limpios y las incidencias en una base separada de la original"""
    temporary_path = datos_sqlite_limpios_path.with_suffix('.tmp.sqlite')
    temporary_path.unlink(missing_ok=True)
    with closing(sqlite3.connect(temporary_path)) as connection, connection:
        for name, rows in datasets.items():
            if not rows:
                continue
            fields = list(rows[0])
            definitions = []
            for field in fields:
                value = next((row[field] for row in rows if row[field] is not None), None)
                kind = 'INTEGER' if isinstance(value, int) else 'REAL' if isinstance(value, float) else 'TEXT'
                definitions.append(f'{quote_identifier(field)} {kind}')
            connection.execute(f'CREATE TABLE {quote_identifier(name)} ({", ".join(definitions)})')
            placeholders = ','.join('?' for field in fields)
            connection.executemany(f'INSERT INTO {quote_identifier(name)} VALUES ({placeholders})', [[row[field] for field in fields] for row in rows])
        connection.execute('CREATE UNIQUE INDEX clave_operacion ON operacion_limpia(fecha,centro_id,jaula_id,lote_id)')
    # cerramos la conexión antes de sustituir la salida anterior para evitar bloqueos en windows
    temporary_path.replace(datos_sqlite_limpios_path)

def main():
    """lee sqlite aplica la limpieza acordada y guarda la base limpia"""
    project_folder = Path(__file__).resolve().parent
    origen_acuicultura_path = project_folder / 'archivos' / 'origen_acuicultura.sqlite'
    output_folder = project_folder / 'output_persona1'
    datos_sqlite_limpios_path = output_folder / 'datos_sqlite_limpios.sqlite'
    tables = read_sqlite(origen_acuicultura_path)
    audit = Audit()
    centers, lots = prepare_dimensions(tables, audit)
    operation = prepare_operation(tables, centers, lots, audit)
    harvests = prepare_harvests(tables, lots, audit)
    if not operation:
        raise ValueError('No quedó operación válida')
    datasets = {name: tables[name] for name in ('zonas', 'jaulas', 'especies')}
    datasets.update({'centros': list(centers.values()), 'lotes': list(lots.values()), 'cosechas': harvests, 'operacion_limpia': operation, 'incidencias_sqlite': audit.rows})
    output_folder.mkdir(exist_ok=True)
    save_sqlite(datos_sqlite_limpios_path, datasets)
    print(f'OK SQLite: {len(operation):,} filas de operación conservadas; {len(harvests)} cosechas válidas')
    print(f'Archivo: {datos_sqlite_limpios_path}')

if __name__ == '__main__':
    main()
