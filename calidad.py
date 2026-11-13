"""comprobaciones y evidencia de la última ejecución del componente b"""

import collections
import csv
import datetime as dt
import hashlib
import json
import math
import sqlite3
import time
from contextlib import closing


class QualityReport:
    """registra comprobaciones sin cambiar las reglas de limpieza ni las métricas"""

    def __init__(self, project_folder):
        self.project_folder = project_folder
        self.started = time.monotonic()
        self.data = {'fecha': dt.datetime.now(dt.timezone.utc).isoformat(),
                     'estado': 'en_ejecucion', 'fuentes': {}, 'conteos': {},
                     'comprobaciones': [], 'etapas': []}

    def check(self, name, valid, detail, severity='error'):
        """registra el resultado y detiene la cadena si una salida sería inválida"""
        self.data['comprobaciones'].append({
            'nombre': name, 'resultado': 'cumple' if valid else 'no_cumple',
            'severidad': severity, 'detalle': detail})
        if not valid and severity == 'error':
            raise ValueError(f'{name}: {detail}')

    def save(self, error=None):
        """sustituye el informe anterior incluso cuando una etapa falla"""
        if error is not None:
            self.data['comprobaciones'].append({'nombre': 'ejecucion', 'resultado': 'no_cumple',
                'severidad': 'error', 'detalle': f'{type(error).__name__}: {error}'})
        failures = [row for row in self.data['comprobaciones'] if row['resultado'] == 'no_cumple']
        self.data['estado'] = ('fallida' if error is not None else
                               'ok_con_advertencias' if failures else 'ok')
        self.data['duracion_segundos'] = round(time.monotonic() - self.started, 3)
        self.data['fin'] = dt.datetime.now(dt.timezone.utc).isoformat()
        ultima_ejecucion_path = self.project_folder / 'output_calidad' / 'ultima_ejecucion.json'
        ultima_ejecucion_path.parent.mkdir(exist_ok=True)
        ultima_temporal_path = ultima_ejecucion_path.with_suffix('.tmp.json')
        ultima_temporal_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2,
                                                   allow_nan=False) + '\n', encoding='utf-8')
        ultima_temporal_path.replace(ultima_ejecucion_path)

    def source(self, name, nombre_archivo_path):
        """identifica el archivo realmente utilizado sin copiar sus datos al informe"""
        self.data['fuentes'][name] = {'ruta': nombre_archivo_path.relative_to(self.project_folder).as_posix(),
            'disponible': nombre_archivo_path.is_file()}
        if nombre_archivo_path.is_file():
            self.data['fuentes'][name]['sha256'] = hashlib.sha256(nombre_archivo_path.read_bytes()).hexdigest()

    def preflight(self):
        """comprueba las fuentes esenciales antes de regenerar resultados"""
        sources = {'sqlite': ('origen_acuicultura.sqlite', 'FCR, costos, basal y gráficos'),
                   'precios': ('origen_costos_alimento.csv', 'costos y gráficos de costos y basal'),
                   'eventos': ('origen_eventos_sanitarios.json', 'basal, exceso y gráficos sanitarios')}
        for name, (file_name, affected) in sources.items():
            nombre_archivo_path = self.project_folder / 'archivos' / file_name
            self.source(name, nombre_archivo_path)
            self.check(f'fuente_{name}', nombre_archivo_path.is_file(),
                       f'{file_name}; si falta o es inválida afecta {affected}')
        origen_acuicultura_path = self.project_folder / 'archivos' / 'origen_acuicultura.sqlite'
        with closing(sqlite3.connect(origen_acuicultura_path.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
            self.check('integridad_sqlite', connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok',
                       'integridad física de la fuente operativa')
        origen_costos_path = self.project_folder / 'archivos' / 'origen_costos_alimento.csv'
        content = origen_costos_path.read_bytes()
        try:
            content = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            content = content.decode('cp1252')
        fields = csv.DictReader(content.splitlines(), delimiter=';').fieldnames or []
        self.check('estructura_precios', {'tipo_alimento', 'mes', 'moneda', 'precio_clp_kg', 'proveedor'} <= set(fields),
                   'columnas necesarias para limpiar precios')
        origen_eventos_path = self.project_folder / 'archivos' / 'origen_eventos_sanitarios.json'
        payload = json.loads(origen_eventos_path.read_text(encoding='utf-8'))
        self.check('estructura_eventos', isinstance(payload, dict) and isinstance(payload.get('eventos'), list)
                   and bool(payload['eventos']), 'lista de eventos presente y no vacía')

    def sqlite_checks(self, tables, datasets, audit):
        """verifica las filas conservadas y separa las exclusiones de los errores"""
        operation = datasets['operacion_limpia']
        for name, rows in tables.items():
            kept = len(datasets.get(name, operation if name == 'operacion_diaria' else []))
            excluded = len(audit.excluded[name])
            self.data['conteos'][name] = {'leidos': len(rows), 'conservados': kept, 'excluidos': excluded}
            self.check(f'exclusiones_{name}', excluded == 0, f'{excluded} filas excluidas por reglas existentes', 'advertencia')
            self.check(f'conciliacion_{name}', len(rows) == kept + excluded,
                       f'{len(rows)} leídos = {kept} conservados + {excluded} excluidos')
        catalogs = {name: {row[key]: row for row in datasets[name]} for name, key in
                    [('centros', 'centro_id'), ('zonas', 'zona_id'), ('jaulas', 'jaula_id'),
                     ('lotes', 'lote_id'), ('especies', 'especie_id')]}
        self.check('catalogos_unicos', all(len(catalogs[name]) == len(datasets[name]) for name in catalogs),
                   'identificadores únicos en los cinco catálogos')
        self.check('referencias_catalogos',
                   all(row['zona_id'] in catalogs['zonas'] for row in datasets['centros']) and
                   all(row['centro_id'] in catalogs['centros'] for row in datasets['jaulas']) and
                   all(row['centro_id'] in catalogs['centros'] and row['jaula_id'] in catalogs['jaulas']
                       and row['especie_id'] in catalogs['especies']
                       and catalogs['jaulas'][row['jaula_id']]['centro_id'] == row['centro_id']
                       for row in datasets['lotes']), 'referencias de centros, jaulas, lotes y especies depuradas')
        keys = [(row['fecha'], row['centro_id'], row['jaula_id'], row['lote_id']) for row in operation]
        self.check('clave_operacion', len(keys) == len(set(keys)), 'unicidad fecha-centro-jaula-lote')
        self.check('referencias_operacion', all(
            row['centro_id'] in catalogs['centros'] and row['jaula_id'] in catalogs['jaulas'] and
            row['lote_id'] in catalogs['lotes'] and row['especie_id'] in catalogs['especies'] and
            catalogs['jaulas'][row['jaula_id']]['centro_id'] == row['centro_id'] and
            all(row[key] == catalogs['lotes'][row['lote_id']][key] for key in ('centro_id', 'jaula_id', 'especie_id'))
            for row in operation), 'operación vinculada al centro, jaula, lote y especie correspondientes')
        self.check('periodo_operacion', all(dt.date.fromisoformat(row['fecha']).year == 2025 and
                   row['mes'] == row['fecha'][:7] for row in operation), 'fechas de 2025 y mes coherente')
        self.check('cantidades_operacion', all(
            all(math.isfinite(row[key]) and row[key] > 0 for key in
                ('alimento_kg', 'crecimiento_kg', 'biomasa_kg', 'poblacion')) and
            math.isfinite(row['temperatura_agua']) and 0 <= row['mortalidad_n'] <= row['poblacion'] and
            row['alimento_kg'] / row['crecimiento_kg'] >= 0.1 for row in operation),
            'cantidades finitas y límites existentes; población positiva protege el peso medio')
        self.check('cosechas_validas', bool(datasets['cosechas']) and all(
            row['lote_id'] in catalogs['lotes'] and
            row['centro_id'] == catalogs['lotes'][row['lote_id']]['centro_id'] and
            dt.date.fromisoformat(row['fecha']).year == 2025 and
            0 < row['kilos_producto'] <= row['kilos_vivos'] for row in datasets['cosechas']),
            'referencias, fechas y kilos de cosechas')
        actions = collections.Counter(row['accion'] for row in audit.rows if row['accion'] != 'excluido')
        self.data['conteos']['incidencias_no_excluyentes_sqlite'] = dict(actions)
        self.check('advertencias_limpieza_sqlite', actions['advertencia'] == 0,
                   f"{actions['advertencia']} advertencias conservadas según las decisiones existentes", 'advertencia')

    def external_checks(self):
        """comprueba las fuentes depuradas antes de permitir los cálculos"""
        import pandas as pd

        def read_rows(file_name):
            nombre_archivo_path = self.project_folder / 'output_persona2' / file_name
            if not nombre_archivo_path.is_file():
                return []
            with nombre_archivo_path.open(encoding='utf-8-sig', newline='') as stream:
                return list(csv.DictReader(stream))

        prices = read_rows('precios_limpios.csv')
        events = read_rows('eventos_limpios.csv')
        dollars = read_rows('dolar_limpio.csv')
        origen_costos_path = self.project_folder / 'archivos' / 'origen_costos_alimento.csv'
        content = origen_costos_path.read_bytes()
        try:
            content = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            content = content.decode('cp1252')
        price_count = sum((row['tipo_alimento'] or '').strip() != 'tipo_alimento' and
                          (row['tipo_alimento'] or '').strip().upper() != 'TOTAL'
                          for row in csv.DictReader(content.splitlines(), delimiter=';'))
        origen_eventos_path = self.project_folder / 'archivos' / 'origen_eventos_sanitarios.json'
        event_count = len(json.loads(origen_eventos_path.read_text(encoding='utf-8'))['eventos'])
        raw_counts = {'precios': price_count, 'eventos': event_count}
        if dollars or read_rows('incidencias_dolar.csv'):
            dolar_crudo_path = self.project_folder / 'archivos' / 'dolar_2025_crudo.json'
            raw_counts['dolar'] = len(json.loads(dolar_crudo_path.read_text(encoding='utf-8'))['serie'])
        for name, rows in [('precios', prices), ('eventos', events), ('dolar', dollars)]:
            issues = read_rows(f'incidencias_{name}.csv')
            excluded = sum(row['accion'] == 'excluido' for row in issues)
            read_count = raw_counts.get(name, 0)
            self.data['conteos'][name] = {'leidos': read_count,
                'conservados': len(rows), 'excluidos': excluded,
                'no_registros': sum(row['accion'] == 'descartada' for row in issues)}
            self.check(f'exclusiones_{name}', excluded == 0,
                       f'{excluded} excluidos por limpieza; no son errores en las salidas', 'advertencia')
            self.check(f'conciliacion_{name}', read_count == len(rows) + excluded,
                       f'{read_count} leídos = {len(rows)} conservados + {excluded} excluidos')
        self.check('precios_validos', bool(prices) and all(
            math.isfinite(float(row['precio_clp_kg'])) and float(row['precio_clp_kg']) > 0 and
            row['tipo_alimento'] in ('Engorda 100', 'Engorda 200', 'Pigmentado') and
            len(row['mes']) == 7 and dt.date.fromisoformat(row['mes'] + '-01').year == 2025
            for row in prices) and len(prices) == len({(row['tipo_alimento'], row['mes']) for row in prices}),
            'precio positivo, mes válido, tipo conocido y unicidad tipo-mes')
        self.data['conteos']['completitud_precios'] = {'esperados': 36, 'observados': len(prices),
                                                      'porcentaje': 100 * len(prices) / 36}
        self.check('cobertura_tipo_mes', len(prices) == 36, f'{len(prices)}/36 combinaciones observadas; sin imputación', 'advertencia')
        cobertura_path = self.project_folder / 'output_persona2' / 'cobertura.txt'
        status = next(line.removeprefix('Dólar: ') for line in cobertura_path.read_text(encoding='utf-8').splitlines()
                      if line.startswith('Dólar: '))
        dolar_crudo_path = self.project_folder / 'archivos' / 'dolar_2025_crudo.json'
        self.source('dolar', dolar_crudo_path)
        self.data['fuentes']['dolar']['utilizada'] = status
        self.check('disponibilidad_dolar', bool(dollars),
                   status + '; afecta dólar mensual y precio del alimento en USD', 'advertencia')
        self.check('actualizacion_api', 'API fallida' not in status, status, 'advertencia')
        if dollars:
            self.check('dolar_valido', all(dt.date.fromisoformat(row['fecha']).year == 2025 and
                math.isfinite(float(row['clp_por_usd'])) and float(row['clp_por_usd']) > 0 for row in dollars)
                and len(dollars) == len({row['fecha'] for row in dollars}), 'fechas únicas de 2025 y CLP/USD positivo')
        datos_sqlite_path = self.project_folder / 'output_persona1' / 'datos_sqlite_limpios.sqlite'
        with closing(sqlite3.connect(datos_sqlite_path.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
            operation = pd.read_sql('SELECT * FROM operacion_limpia', connection)
            cages = set(connection.execute('SELECT centro_id, jaula_id FROM jaulas'))
        self.check('eventos_validos', bool(events) and len(events) == len({row['evento_id'] for row in events}) and all(
            dt.date(2025, 1, 1) <= dt.date.fromisoformat(row['fecha_inicio']) <=
            dt.date.fromisoformat(row['fecha_fin']) <= dt.date(2025, 12, 31) and
            math.isfinite(float(row['mortalidad_declarada_json_n'])) and float(row['mortalidad_declarada_json_n']) >= 0 and
            bool(row['jaulas_afectadas'].split()) and all((int(row['centro_id']), int(cage)) in cages
                for cage in row['jaulas_afectadas'].split()) for row in events),
            'identificadores únicos, fechas ordenadas, mortalidad y jaulas válidas')
        self.check('evento_graficos', sum(row['evento_id'] == 'EV-8001' for row in events) == 1,
                   'EV-8001 necesario para los gráficos actuales de mortalidad y basal')
        self.check('precio_meses_operacion', set(operation.fecha.str[:7]) <= {row['mes'] for row in prices},
                   'cada mes operativo tiene al menos un precio para el promedio existente')
        operation['evento_id'] = None
        for event in events:
            mask = ((operation.centro_id == int(event['centro_id'])) &
                    operation.jaula_id.isin(map(int, event['jaulas_afectadas'].split())) &
                    operation.fecha.between(event['fecha_inicio'], event['fecha_fin']))
            self.check('observaciones_' + event['evento_id'], bool(mask.any()), 'operación conservada en las jaulas y fechas del evento')
            operation.loc[mask, 'evento_id'] = event['evento_id']
        operation['muertos_kg'] = operation.mortalidad_n * operation.biomasa_kg / operation.poblacion
        baseline = operation[operation.evento_id.isna()].groupby('lote_id').poblacion.sum()
        self.check('denominador_basal', all(baseline.get(lot, 0) > 0 for lot in operation.lote_id.unique()),
                   'cada lote utilizado dispone de población acumulada positiva fuera de eventos')
        monthly_prices = pd.DataFrame(prices).assign(price=lambda frame: frame.precio_clp_kg.astype(float)).groupby('mes').price.mean()
        operation['costo_clp'] = operation.alimento_kg * operation.fecha.str[:7].map(monthly_prices)
        center_cost = operation.groupby('centro_id').costo_clp.sum() / operation.groupby('centro_id').crecimiento_kg.sum()
        top = center_cost.sort_values().index[-1]
        selected = operation[operation.centro_id == top]
        rest = operation[operation.centro_id != top]
        groups = list(operation.groupby('centro_id')) + list(selected.groupby(selected.fecha.str[:7])) + list(rest.groupby(rest.fecha.str[:7]))
        groups += list(operation.groupby(['centro_id', 'especie_id'])) + [('resto', rest)]
        affected = {int(cage) for row in events if int(row['centro_id']) == top for cage in row['jaulas_afectadas'].split()}
        groups += [('evento_top', selected[selected.evento_id.notna()]),
                   ('afectadas_fuera_evento', selected[selected.jaula_id.isin(affected) & selected.evento_id.isna()]),
                   ('no_afectadas', selected[~selected.jaula_id.isin(affected)])]
        invalid = [str(name) for name, frame in groups if frame.empty or
                   frame.poblacion.sum() <= 0 or frame.alimento_kg.sum() <= 0 or
                   frame.crecimiento_kg.sum() <= 0]
        self.check('denominadores_indicadores', not invalid,
                   f'grupos de centros, meses, resto, especies y jaulas del centro top; inválidos: {invalid}')
        self.check('denominador_fcr_neto_centros', all(
            frame.crecimiento_kg.sum() - frame.muertos_kg.sum() > 0
            for _, frame in operation.groupby('centro_id')),
            'crecimiento neto positivo por centro exigido por metricas_fcr.py')
        net_groups = [('resto', rest)] + list(selected.groupby(selected.fecha.str[:7])) + list(rest.groupby(rest.fecha.str[:7]))
        undefined = [str(name) for name, frame in net_groups if frame.crecimiento_kg.sum() - frame.muertos_kg.sum() <= 0]
        self.check('netos_no_definidos_costo', not undefined,
                   f'costo_mortalidad.py deja FCR y costo netos vacíos cuando G <= M; grupos: {undefined}', 'advertencia')
        ordered = operation.sort_values(['lote_id', 'fecha'])
        next_dates = ordered.groupby('lote_id').fecha.shift(-1)
        self.check('denominador_verificacion_crecimiento', bool(((pd.to_datetime(next_dates) - pd.to_datetime(ordered.fecha)).dt.days == 1).any()),
                   'hay pares consecutivos para la comprobación de crecimiento ya existente')
        return bool(dollars)

    def required_outputs(self, dollar_available):
        """enumera únicamente los productos que la cadena actual genera"""
        required = ['output_persona1/datos_sqlite_limpios.sqlite', 'output_persona2/precios_limpios.csv',
                    'output_persona2/eventos_limpios.csv', 'output_persona2/cobertura.txt',
                    'output_persona3/fcr_por_centro.csv', 'output_costo/costo_mortalidad.xlsx']
        for stem in ('01_costo_alimento_por_centro', '02_fcr_bruto_vs_neto',
                     '03_mortalidad_diaria_EV-8001', '04_mortalidad_vs_basal_EV-8001'):
            required.append('output_persona5/' + stem + '.png')
        for stem in ('01_datos_costos', '02_datos_fcr', '03_datos_mortalidad_EV-8001', '04_datos_basal_EV-8001'):
            required.append('output_persona5/' + stem + '.csv')
        for stem in ('01_interpretacion_costos', '02_interpretacion_fcr',
                     '03_interpretacion_mortalidad_EV-8001', '04_interpretacion_basal_EV-8001'):
            required.append('output_persona5/' + stem + '.md')
        for file_name in ('1_precio_alimento_mensual.png', '2_cobertura_por_fuente.png', '3_mortalidad_declarada_vs_observada.png'):
            required.append('output_persona2/graficos/' + file_name)
        if dollar_available:
            required += ['output_persona2/dolar_limpio.csv', 'output_persona2/graficos/4_dolar_mensual.png',
                         'output_persona2/graficos/5_precio_alimento_usd.png']
        return required

    def prepare_outputs(self):
        """retira productos anteriores para que no acrediten una etapa incompleta"""
        for file_name in self.required_outputs(True):
            # la base sqlite ya fue sustituida y comprobada en esta ejecución
            if file_name.startswith('output_persona1/'):
                continue
            nombre_archivo_path = self.project_folder / file_name
            nombre_archivo_path.unlink(missing_ok=True)

    def outputs(self, dollar_available):
        """exige los productos de todas las etapas de la ejecución actual"""
        required = self.required_outputs(dollar_available)
        missing = [name for name in required if not (self.project_folder / name).is_file()
                   or (self.project_folder / name).stat().st_size == 0]
        self.check('salidas_requeridas', not missing, f'ausentes o vacías: {missing}')
