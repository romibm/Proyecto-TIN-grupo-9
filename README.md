# AquaFiordo — limpieza de SQLite

`main.py` lee `origen_acuicultura.sqlite`, aplica las decisiones de limpieza acordadas y guarda una base limpia. La fuente original se abre en modo de solo lectura y se conserva intacta.

## Ejecutar

Se necesita Python 3.10 o superior. No hay paquetes adicionales que instalar.

Descomprimir este paquete en una carpeta nueva y abrir una terminal en la carpeta que contiene `main.py`. En Windows:

```powershell
py main.py
```

En Linux o macOS:

```bash
python3 main.py
```

El archivo original debe estar en `archivos/origen_acuicultura.sqlite`. El script crea `output_persona1/datos_sqlite_limpios.sqlite`.

Con la base incluida, la salida esperada es:

```text
OK SQLite: 13,158 filas de operación conservadas; 42 cosechas válidas
Archivo: <ruta del proyecto>/output_persona1/datos_sqlite_limpios.sqlite
```

`13,158` significa 13.158 filas. La ejecución tarda aproximadamente uno a dos segundos en el entorno de verificación.

## Trabajo realizado

Se unifican las fechas y cantidades, se revisan referencias entre tablas y se aplican las reglas acordadas sobre período, duplicados, mes, alimento y balance de población. Se preparan centros, lotes y cosechas y se conserva la trazabilidad de los valores modificados.

La zona de Skyring se asigna mediante la inferencia acordada. Las etiquetas de zona inconsistentes se corrigen conservando su valor original.

Los criterios y supuestos están en `DECISIONES_SQLITE.md`. Los valores utilizados están al principio de `main.py`.

## Base de resultados

| Tabla | Contenido |
| --- | --- |
| `operacion_limpia` | Observaciones diarias conservadas con fechas, cantidades y etiquetas de zona revisadas |
| `centros`, `lotes` | Catálogos preparados, con valores originales conservados |
| `zonas`, `jaulas`, `especies` | Catálogos de la base original |
| `cosechas` | Cosechas con fechas, referencias y cantidades válidas |
| `incidencias_sqlite` | Fuente, fila de origen, motivo, acción y detalle de las incidencias |

Una observación diaria corresponde a una combinación única de fecha, centro, jaula y lote. `origen_fila` identifica la fila original. Las fechas, el mes y las zonas originales se conservan cuando se transforman.

Las incidencias distinguen exclusiones, advertencias, correcciones e inferencias. Una fila puede tener varios motivos registrados. Los registros excluidos permanecen en la fuente original.

Cada ejecución vuelve a generar la base limpia. Se escribe primero una base temporal y se cierra SQLite antes de sustituir la salida anterior. Si Windows informa que la salida está en uso, cerrar la aplicación que tenga abierta esa base y volver a ejecutar.

Se verificó que las filas conservadas coincidan con las decisiones acordadas y que dos ejecuciones produzcan los mismos datos.

## Uso de IA

Se utilizó IA para ayudar con partes del código y la documentación. 