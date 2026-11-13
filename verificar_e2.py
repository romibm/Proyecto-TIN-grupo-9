"""verifica la operación de p1 en una copia temporal sin modificar las fuentes originales"""

import csv
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

from openpyxl import load_workbook


def data_snapshot(project_folder):
    """compara datos tabulares y celdas sin comparar bytes de excel ni imágenes"""
    result = {}
    datos_sqlite_path = project_folder / 'output_persona1' / 'datos_sqlite_limpios.sqlite'
    with closing(sqlite3.connect(datos_sqlite_path)) as connection:
        names = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for name in names:
            result['sqlite/' + name] = sorted(connection.execute('SELECT * FROM "' + name + '"').fetchall(), key=repr)
        count, distinct = connection.execute('SELECT COUNT(*), COUNT(DISTINCT fecha || char(0) || centro_id || char(0) || jaula_id || char(0) || lote_id) FROM operacion_limpia').fetchone()
        assert count == distinct, 'Aparecieron claves duplicadas'
    for output_folder in ('output_persona2', 'output_persona3', 'output_persona5'):
        for nombre_archivo_path in sorted((project_folder / output_folder).glob('*.csv')):
            with nombre_archivo_path.open(encoding='utf-8-sig', newline='') as stream:
                result[nombre_archivo_path.relative_to(project_folder).as_posix()] = list(csv.reader(stream))
    costo_mortalidad_path = project_folder / 'output_costo' / 'costo_mortalidad.xlsx'
    workbook = load_workbook(costo_mortalidad_path, read_only=True, data_only=True)
    try:
        for sheet in workbook:
            result['excel/' + sheet.title] = list(sheet.values)
    finally:
        workbook.close()
    return result


def run_chain(project_folder, api_failure=False, skip_stage=False):
    """ejecuta la entrada única y permite simular una api inaccesible sin red"""
    command = [sys.executable, 'main.py']
    # la sustitución se limita al proceso hijo que consulta la api
    code = f'simulate_api = {api_failure}\nskip_stage = {skip_stage}\n' + """
import runpy, subprocess, sys
original_run = subprocess.run
def controlled_run(command, **kwargs):
    if skip_stage and len(command) > 1 and command[1].endswith('graficos_fcr.py'):
        return subprocess.CompletedProcess(command, 0, stdout='', stderr='')
    if len(command) > 1 and command[1].endswith('limpieza_externas.py'):
        child_code = "import runpy,sys; from unittest.mock import patch; from urllib.error import URLError; "
        child_code += "sys.argv=" + repr(['limpieza_externas.py'] + (['--actualizar-dolar'] if simulate_api else [])) + "; "
        child_code += "handler=patch('urllib.request.urlopen',side_effect=" + ("URLError('fallo controlado')" if simulate_api else "AssertionError('consulta API no autorizada')") + "); handler.start(); runpy.run_path('limpieza_externas.py',run_name='__main__')"
        command = [sys.executable, '-c', child_code]
    return original_run(command, **kwargs)
subprocess.run = controlled_run
sys.argv = ['main.py'] + (['--actualizar-dolar'] if simulate_api else [])
runpy.run_path('main.py', run_name='__main__')
"""
    command = [sys.executable, '-c', code]
    return subprocess.run(command, cwd=project_folder, capture_output=True, text=True,
                          encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})


def write_evidence(project_folder, evidence):
    """guarda únicamente evidencia de pruebas sin escribir el informe local"""
    verificacion_e2_path = project_folder / 'output_calidad' / 'verificacion_e2.json'
    verificacion_e2_path.parent.mkdir(exist_ok=True)
    verificacion_e2_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def verify():
    """comprueba recarga reproducible y fallas controladas conservando evidencia breve"""
    project_folder = Path(__file__).resolve().parent
    local_report_path = project_folder / 'output_calidad' / 'ultima_ejecucion.json'
    previous_report = local_report_path.read_bytes() if local_report_path.exists() else None
    original_capture_path = project_folder / 'archivos' / 'dolar_2025_crudo.json'
    previous_capture = original_capture_path.read_bytes()
    with tempfile.TemporaryDirectory(prefix='aquafiordo_e2_') as temporary_folder:
        copy_folder = Path(temporary_folder)
        for nombre_archivo_path in project_folder.glob('*.py'):
            shutil.copy2(nombre_archivo_path, copy_folder / nombre_archivo_path.name)
        shutil.copy2(project_folder / 'requirements.txt', copy_folder / 'requirements.txt')
        shutil.copytree(project_folder / 'archivos', copy_folder / 'archivos')
        assert not list(copy_folder.glob('output_*')), 'La copia contiene salidas previas'
        first = run_chain(copy_folder)
        assert first.returncode == 0, first.stderr
        expected = data_snapshot(copy_folder)
        second = run_chain(copy_folder)
        assert second.returncode == 0, second.stderr
        assert expected == data_snapshot(copy_folder), 'Los datos difieren al repetir la recarga'
        ultima_ejecucion_path = copy_folder / 'output_calidad' / 'ultima_ejecucion.json'
        baseline_report = json.loads(ultima_ejecucion_path.read_text(encoding='utf-8'))
        dolar_crudo_path = copy_folder / 'archivos' / 'dolar_2025_crudo.json'
        original_hash = hashlib.sha256(dolar_crudo_path.read_bytes()).hexdigest()
        failed_api = run_chain(copy_folder, api_failure=True)
        assert failed_api.returncode == 0, failed_api.stderr
        assert original_hash == hashlib.sha256(dolar_crudo_path.read_bytes()).hexdigest()
        assert expected == data_snapshot(copy_folder), 'El respaldo de la API cambió las cifras'
        failed_api_report = json.loads(ultima_ejecucion_path.read_text(encoding='utf-8'))
        assert 'API fallida' in failed_api_report['fuentes']['dolar']['utilizada']
        assert failed_api_report['estado'] == 'ok_con_advertencias'
        # comprobamos rechazo de una actualización inválida sin sustituir la captura
        code = """
from unittest.mock import patch, MagicMock
import limpieza_externas as external
response = MagicMock()
response.__enter__.return_value.read.return_value = b'{"codigo":"dolar","unidad_medida":"Pesos","serie":[{"fecha":"2025-01-02","valor":-1}]}'
with patch('urllib.request.urlopen', return_value=response) as request:
    rows, issues, count, status = external.limpiar_dolar(True)
    assert rows and 'API fallida' in status and 'captura' in status
    assert request.call_args.kwargs['timeout'] == 15
"""
        invalid_update = subprocess.run([sys.executable, '-c', code], cwd=copy_folder, capture_output=True, text=True)
        assert invalid_update.returncode == 0, invalid_update.stderr
        assert original_hash == hashlib.sha256(dolar_crudo_path.read_bytes()).hexdigest()
        # una fuente esencial ausente debe bloquear aun con resultados de la ejecución anterior
        origen_costos_path = copy_folder / 'archivos' / 'origen_costos_alimento.csv'
        origen_costos_path.unlink()
        missing = run_chain(copy_folder)
        assert missing.returncode != 0 and 'OK cadena completa' not in missing.stdout
        missing_report = json.loads(ultima_ejecucion_path.read_text(encoding='utf-8'))
        assert missing_report['estado'] == 'fallida'
        assert any(row['nombre'] == 'fuente_precios' and row['resultado'] == 'no_cumple'
                   for row in missing_report['comprobaciones'])
        shutil.copy2(project_folder / 'archivos' / 'origen_costos_alimento.csv', origen_costos_path)
        skipped = run_chain(copy_folder, skip_stage=True)
        assert skipped.returncode != 0 and 'OK cadena completa' not in skipped.stdout
        skipped_report = json.loads(ultima_ejecucion_path.read_text(encoding='utf-8'))
        assert any(row['nombre'] == 'salidas_requeridas' and row['resultado'] == 'no_cumple'
                   for row in skipped_report['comprobaciones'])
        # sin dólar se advierte y se retiran los productos opcionales antiguos
        dolar_crudo_path.unlink()
        no_dollar = run_chain(copy_folder)
        assert no_dollar.returncode == 0, no_dollar.stderr
        assert not (copy_folder / 'output_persona2' / 'dolar_limpio.csv').exists()
        assert not (copy_folder / 'output_persona2' / 'graficos' / '4_dolar_mensual.png').exists()
        no_dollar_report = json.loads(ultima_ejecucion_path.read_text(encoding='utf-8'))
        assert no_dollar_report['estado'] == 'ok_con_advertencias'
        shutil.copy2(project_folder / 'archivos' / 'dolar_2025_crudo.json', dolar_crudo_path)
        final = run_chain(copy_folder)
        assert final.returncode == 0, final.stderr
        assert expected == data_snapshot(copy_folder), 'La ejecución final difiere de la inicial'
        baseline_report = json.loads(ultima_ejecucion_path.read_text(encoding='utf-8'))
        # guardamos la evidencia temporal sin sustituir el informe de ejecución local
        quality_folder = project_folder / 'output_calidad'
        quality_folder.mkdir(exist_ok=True)
        baseline_report['verificacion_en_copia_temporal'] = True
        evidence = {'fecha': baseline_report['fecha'], 'dependencias': {},
                    'procedencia': 'copia temporal sin outputs previos; dependencias del intérprete invocante',
                    'informe_temporal': baseline_report,
                    'pruebas': ['copia sin outputs previos', 'recarga sin duplicados',
                               'igualdad de todas las tablas SQLite, CSV y celdas Excel',
                               'API fallida con respaldo y mismas cifras', 'actualización inválida rechazada',
                               'fuente esencial ausente bloquea con resultados anteriores presentes',
                               'etapa sin productos bloquea aun con retorno cero',
                               'dólar ausente advierte y retira salidas opcionales antiguas'],
                    'conteos': baseline_report['conteos'], 'resultado': 'cumple',
                    'escenarios': {'api_fallida': {'estado': failed_api_report['estado'],
                        'fuente_dolar': failed_api_report['fuentes']['dolar']['utilizada']},
                        'fuente_esencial_ausente': {'codigo': missing.returncode, 'estado': missing_report['estado']},
                        'etapa_sin_productos': {'codigo': skipped.returncode, 'estado': skipped_report['estado']},
                        'dolar_ausente': {'estado': no_dollar_report['estado']}}}
        evidence['informes_escenarios'] = {'api_fallida': failed_api_report,
            'fuente_esencial_ausente': missing_report, 'etapa_sin_productos': skipped_report,
            'dolar_ausente': no_dollar_report}
        assert 'API' not in skipped_report['fuentes']['dolar']['utilizada']
        assert previous_capture == original_capture_path.read_bytes(), 'Se alteró la captura original'
        assert (local_report_path.read_bytes() if local_report_path.exists() else None) == previous_report, 'Se alteró el informe local'
        evidence['pruebas'] += ['modo normal y etapa omitida con API prohibida',
                               'captura original e informe local intactos']
        import importlib.metadata
        for name in ('matplotlib', 'pandas', 'openpyxl'):
            evidence['dependencias'][name] = importlib.metadata.version(name)
        write_evidence(project_folder, evidence)
        print(json.dumps({'resultado': 'cumple', 'pruebas': evidence['pruebas'],
                          'conteos': baseline_report['conteos']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    verify()
