import csv
import sqlite3
from pathlib import Path
from contextlib import closing


def read_sqlite(datos_sqlite_limpios_path):
    """lee alimento crecimiento y biomasa perdida estimada de dos mil veinticinco por centro"""
    with closing(sqlite3.connect(datos_sqlite_limpios_path.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        query = """
            SELECT o.centro_id, c.nombre AS nombre_centro,
                   SUM(o.alimento_kg) AS alimento_total_kg,
                   SUM(o.crecimiento_kg) AS crecimiento_bruto_kg,
                   SUM(o.mortalidad_n * o.biomasa_kg / o.poblacion) AS biomasa_muerta_estimada_kg
            FROM operacion_limpia AS o
            JOIN centros AS c ON c.centro_id = o.centro_id
            WHERE o.fecha >= '2025-01-01' AND o.fecha < '2026-01-01'
            GROUP BY o.centro_id, c.nombre
            ORDER BY o.centro_id
        """
        return [dict(row) for row in connection.execute(query)]


def main():
    """calcula ambos fcr y su diferencia por centro y guarda los datos utilizados en csv"""
    project_folder = Path(__file__).resolve().parent
    datos_sqlite_limpios_path = project_folder / 'output_persona1' / 'datos_sqlite_limpios.sqlite'
    output_folder = project_folder / 'output_persona3'
    fcr_por_centro_path = output_folder / 'fcr_por_centro.csv'
    rows = read_sqlite(datos_sqlite_limpios_path)
    if not rows:
        raise ValueError('No hay operaciones limpias de 2025')
    # el neto descuenta la biomasa muerta estimada con el peso promedio de cada observación
    for row in rows:
        row['crecimiento_neto_estimado_kg'] = row['crecimiento_bruto_kg'] - row['biomasa_muerta_estimada_kg']
        if row['crecimiento_neto_estimado_kg'] <= 0:
            raise ValueError(f"Crecimiento neto no positivo en el centro {row['centro_id']}")
        row['fcr_bruto'] = row['alimento_total_kg'] / row['crecimiento_bruto_kg']
        row['fcr_neto_estimado'] = row['alimento_total_kg'] / row['crecimiento_neto_estimado_kg']
        row['diferencia_fcr'] = row['fcr_neto_estimado'] - row['fcr_bruto']
        row['cambio_porcentual_fcr'] = (row['fcr_neto_estimado'] / row['fcr_bruto'] - 1) * 100
    output_folder.mkdir(exist_ok=True)
    with fcr_por_centro_path.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'OK FCR bruto y neto estimado: {len(rows)} centros')
    print(f'Archivo: {fcr_por_centro_path}')


if __name__ == '__main__':
    main()
