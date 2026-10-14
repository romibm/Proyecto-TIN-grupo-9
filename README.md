# AquaFiordo

El trabajo tiene tres scripts que se ejecutan en este orden:

1. `main.py` (Romina) limpia la base SQLite y genera `output_persona1/datos_sqlite_limpios.sqlite`.
2. `limpieza_externas.py` (Antonia) limpia el CSV de precios, el JSON de eventos sanitarios y la API del dólar, calcula la cobertura y hace los gráficos. Necesita la base del paso 1 para validar los eventos.
3. `metricas_fcr.py` (Romina) calcula el FCR bruto y neto estimado por centro, su diferencia absoluta y el cambio porcentual. Utiliza la base limpia del paso 1.

Las fuentes originales se abren en modo de solo lectura y se conservan intactas.

## Ejecutar

Se necesita Python 3.10 o superior. `main.py` y `metricas_fcr.py` no necesitan paquetes adicionales. `limpieza_externas.py` necesita `matplotlib` solo para los gráficos (`pip install matplotlib`) y acceso a internet para consultar la API del dólar.

Descomprimir este paquete en una carpeta nueva y abrir una terminal en la carpeta que contiene los scripts. En Windows:

```powershell
py main.py
py limpieza_externas.py
py metricas_fcr.py
```

En Linux o macOS:

```bash
python3 main.py
python3 limpieza_externas.py
python3 metricas_fcr.py
```

Los archivos originales deben estar en la carpeta `archivos/`:

| Archivo | Lo usa |
| --- | --- |
| `origen_acuicultura.sqlite` | `main.py` |
| `origen_costos_alimento.csv` | `limpieza_externas.py` |
| `origen_eventos_sanitarios.json` | `limpieza_externas.py` |

Los criterios y supuestos están en `DECISIONES_SQLITE.md` (Romina) y `DECISIONES_EXTERNAS.md` (Antonia). Los valores utilizados en `main.py` están al principio del archivo.

# Parte 1 — Limpieza de SQLite (Romina)

`main.py` lee `origen_acuicultura.sqlite`, aplica las decisiones de limpieza acordadas y guarda una base limpia. El script crea `output_persona1/datos_sqlite_limpios.sqlite`.

Con la base incluida, la salida esperada es:

```text
OK SQLite: 13,157 filas de operación conservadas; 42 cosechas válidas
Archivo: <ruta del proyecto>/output_persona1/datos_sqlite_limpios.sqlite
```

`13,157` significa 13.157 filas. La ejecución tarda aproximadamente uno a dos segundos en el entorno de verificación.

## Trabajo realizado

Se unifican las fechas y cantidades, se revisan referencias entre tablas y se aplican las reglas acordadas sobre período, duplicados, mes, alimento y balance de población. Se preparan centros, lotes y cosechas y se conserva la trazabilidad de los valores modificados.

La zona de Skyring se asigna mediante la inferencia acordada. Las etiquetas de zona inconsistentes se corrigen conservando su valor original.

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

# Parte 2 — Precios, eventos sanitarios y dólar (Antonia)

`limpieza_externas.py` lee el CSV de precios, el JSON de eventos y la API del dólar. Crea la carpeta `output_persona2/`. Si falta la base de la Romina, el script se detiene porque necesita validar los eventos contra sus centros, jaulas y operación diaria.

## Trabajo realizado

**Precios (CSV).** El archivo está en Windows-1252 y separado por punto y coma. Se descarta un encabezado repetido a mitad del archivo y la fila `TOTAL`, que no son registros. Se unifican los nombres del alimento (`engorda100`, `Engorda 100` y `ENG-100` pasan a ser Engorda 100, y lo mismo con Engorda 200 y Pigmentado) y se leen precios escritos como `$1.050`, `1.021,00` o `950`. El precio `sin dato` se excluye y no se estima.

**Eventos sanitarios (JSON).** Se validan el centro, las fechas, la mortalidad declarada y las jaulas afectadas contra la base limpia. Se excluyen los eventos de centros que no existen. La fecha `15/10/2025` de EV-8001 se corrige a formato ISO. Para cada evento válido se compara la mortalidad declarada en el JSON con la observada en la operación diaria, en las jaulas afectadas y en todo el centro.

**Dólar (API).** Se consulta `https://mindicador.cl/api/dolar/2025`, se guarda la respuesta cruda para poder repetir la ejecución y se excluyen los registros inválidos. Si la API no responde se usa la respuesta guardada; si tampoco existe, la fuente queda sin datos y el script lo informa.

## Resultados

| Archivo (en `output_persona2/`) | Contenido |
| --- | --- |
| `precios_limpios.csv` | Un precio por tipo de alimento y mes, con el nombre original y la fila del CSV |
| `eventos_limpios.csv` | Eventos válidos con mortalidad declarada y observada |
| `dolar_limpio.csv` | Dólar diario de 2025 (solo si la API o la respuesta guardada estuvo disponible) |
| `incidencias_precios.csv`, `incidencias_eventos.csv`, `incidencias_dolar.csv` | Fila u origen, motivo, acción (excluido, corregido o descartado) y detalle |
| `dolar_2025_crudo.json` | Respuesta de la API guardada |
| `cobertura.txt` | Registros excluidos por fuente y en total |
| `graficos/` | Gráficos del informe |

## Cobertura de datos

Un registro queda fuera cuando se lee de la fuente y una regla de calidad lo excluye. Las filas que no son registros (encabezado repetido y `TOTAL`) y los meses sin fila no se cuentan como excluidos.

| Fuente | Registros leídos | Excluidos | % fuera | Motivo |
| --- | --- | --- | --- | --- |
| Precios (CSV) | 34 | 1 | 2,9 % | Un precio `sin dato` |
| Eventos (JSON) | 8 | 4 | 50,0 % | Cuatro eventos de centros que no existen (90 a 93) |
| Dólar (API) | sin datos | sin datos | sin datos | La ejecución de verificación no tuvo acceso a la API |
| **Total** | **42** | **5** | **11,9 %** | |

Además, hay precio válido en 33 de las 36 combinaciones de tipo de alimento y mes (91,7 %). Faltan Engorda 100 en mayo, Engorda 200 en julio y Pigmentado en febrero. Los dos últimos meses ni siquiera aparecen como fila en el CSV.

El total está dominado por la fuente más pequeña, los eventos. Debe leerse junto con el desglose por fuente y no como el porcentaje de todos los datos del trabajo.

## Gráficos

| Archivo (en `output_persona2/graficos/`) | Qué muestra |
| --- | --- |
| `1_precio_alimento_mensual.png` | Precio mensual por tipo de alimento. Los huecos son meses sin dato |
| `2_cobertura_por_fuente.png` | Registros usados y excluidos por fuente |
| `3_mortalidad_declarada_vs_observada.png` | Mortalidad de cada evento válido: declarada, observada en las jaulas afectadas y observada en todo el centro |
| `4_dolar_mensual.png` | Dólar promedio mensual (solo con datos de la API) |
| `5_precio_alimento_usd.png` | Precio promedio del alimento en dólares por kilo (solo con datos de la API) |

## Limitaciones

- La mortalidad observada usa `operacion_limpia`, que ya excluyó filas según los criterios de la Romina. Puede ser menor que la real, de modo que la diferencia con el JSON podría estar sobreestimada.
- Los meses sin precio se muestran como huecos y no se estiman.

# Parte 3 — FCR bruto y neto estimado (Romina)

`metricas_fcr.py` utiliza las tablas `operacion_limpia` y `centros` de `output_persona1/datos_sqlite_limpios.sqlite`. Calcula los resultados por centro para las observaciones conservadas de 2025.

## Trabajo realizado

- FCR bruto: alimento total dividido por crecimiento bruto total
- FCR neto estimado: alimento total dividido por crecimiento bruto total menos biomasa muerta estimada
- Comparación: diferencia absoluta y cambio porcentual del FCR neto estimado respecto del bruto

Se interpreta `crecimiento_kg` como crecimiento antes de descontar mortalidad. La biomasa muerta se estima por observación como `mortalidad_n × biomasa_kg / poblacion`, suponiendo que los peces muertos tenían el peso promedio de su jaula y lote en ese día.

Ambos FCR se expresan en kg de alimento por kg de crecimiento. El neto estimado aumenta al descontar las pérdidas porque utiliza el mismo alimento y un denominador menor.

Las fórmulas exactas, filtros, supuestos, resultados y su explicación están en `FICHA_FCR.md`.

## Resultado

Se genera `output_persona3/fcr_por_centro.csv`, con una fila por centro. Incluye los totales de alimento y crecimiento, la biomasa muerta y el crecimiento neto estimados, ambos FCR, su diferencia absoluta y el cambio porcentual.

La salida esperada es:

```text
OK FCR bruto y neto estimado: 7 centros
Archivo: <ruta del proyecto>/output_persona3/fcr_por_centro.csv
```

No se excluyen filas adicionales en este cálculo. Se verificó que los resultados del CSV coincidan con los valores presentados en la ficha.

# Parte 4 — Costo por kg y mortalidad atribuible al evento (Antonia)

`metricas_evento_costo.py` calcula el costo de alimento por kg de crecimiento, la mortalidad atribuible al evento sanitario y la descomposición de la brecha de costo del centro más caro. Usa `output_persona1/datos_sqlite_limpios.sqlite` y, de `output_persona2/`, `precios_limpios.csv`, `eventos_limpios.csv` y `dolar_limpio.csv` (si el dólar no existe, las columnas en USD quedan vacías).

Se ejecuta después de `main.py` y `limpieza_externas.py`. No necesita paquetes adicionales:

```powershell
py metricas_evento_costo.py
```

```bash
python3 metricas_evento_costo.py
```

## Resultado

Se crea `output_persona3/` con:

| Archivo | Contenido |
| --- | --- |
| `tabla_integrada.csv` | Una fila por fecha, centro y jaula: operación diaria, precio del mes, costo del alimento en CLP y USD, y evento sanitario |
| `costo_por_kg_por_centro.csv` | Alimento, crecimiento, biomasa muerta, FCR bruto y neto, y costo por kg bruto y neto por centro |
| `mortalidad_evento.csv` | Por evento válido: mortalidad declarada, observada, basal y atribuible, y FCR dentro y fuera del evento |
| `descomposicion_costo.csv` | Parte de la brecha del centro más caro explicada por precio, FCR bruto y mortalidad |
| `efecto_evento_skyring.csv` | Efecto del evento en CLP por kg y en pesos al año |
| `detalle_mensual_centro_mayor_costo.csv` | Detalle mes a mes del centro más caro |

La salida esperada termina con `OK: archivos en <ruta del proyecto>/output_persona3`. Tarda menos de un segundo.

El precio del alimento de cada mes es el promedio simple de los tipos con precio válido, porque la operación diaria no indica el tipo. El FCR neto mensual de Skyring de agosto a octubre no es interpretable (crecimiento neto negativo en agosto). Las fórmulas, decisiones, supuestos y resultados están en `FICHA_COSTO_EVENTO.md`.

# Uso de IA

Se utilizó IA para ayudar con partes del código y la documentación.
