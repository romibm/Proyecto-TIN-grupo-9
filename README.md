# AquaFiordo

`main.py` ejecuta el proceso completo de la Entrega 1, en este orden:

1. Limpieza de SQLite mediante la función `clean_sqlite()`
2. Limpieza de precios, eventos sanitarios y dólar mediante `limpieza_externas.py`
3. Cálculo del FCR bruto y neto estimado mediante `metricas_fcr.py`
4. Cálculo de costos y mortalidad basal mediante `costo_mortalidad.py`
5. Generación de los cuatro gráficos del informe mediante `graficos_costos.py`, `graficos_fcr.py`, `graficos_mortalidad.py` y `graficos_basal.py`

Cada etapa utiliza las salidas de las anteriores. Si un script falla, la ejecución se detiene.

Las fuentes originales se conservan intactas.

## Requisitos e instalación

Se necesita Python 3.10 o superior. El proceso fue verificado con Python 3.12 y las versiones de dependencias indicadas en `requirements.txt`.

Desde la carpeta que contiene `main.py`, instalar las dependencias una vez por entorno.

En Windows:

```powershell
py -m pip install -r requirements.txt
```

En Linux o macOS:

```bash
python3 -m pip install -r requirements.txt
```

## Fuentes necesarias

Los siguientes archivos deben estar dentro de `archivos/`:

| Archivo | Contenido |
| --- | --- |
| `origen_acuicultura.sqlite` | Operación diaria y catálogos |
| `origen_costos_alimento.csv` | Precios del alimento |
| `origen_eventos_sanitarios.json` | Eventos sanitarios |

El dólar se consulta en `https://mindicador.cl/api/dolar/2025`.

Si la API no responde, se utiliza la respuesta cruda guardada en `output_persona2/dolar_2025_crudo.json`. Para reproducir el proceso sin conexión, conservar ese archivo. Los resultados calculados previamente no son necesarios.

## Ejecutar el proceso completo

Abrir una terminal en la carpeta que contiene `main.py`.

En Windows:

```powershell
py main.py
```

En Linux o macOS:

```bash
python3 main.py
```

Este comando ejecuta la limpieza, los cálculos y los gráficos. No es necesario ejecutar los demás scripts por separado.

## Resultados esperados

| Carpeta | Contenido generado |
| --- | --- |
| `output_persona1/` | Base SQLite limpia y registro de incidencias |
| `output_persona2/` | Precios, eventos y dólar limpios, cobertura y gráficos complementarios |
| `output_persona3/` | FCR bruto y neto estimado por centro y su comparación |
| `output_costo/` | Excel con costos, mortalidad basal y valoraciones económicas |
| `output_persona5/` | Cuatro gráficos del informe, sus datos e interpretaciones |

Con los archivos incluidos se esperan:

- 13.157 filas de operación conservadas y 42 cosechas válidas
- 33 precios válidos y cuatro eventos sanitarios válidos
- 248 observaciones del dólar al utilizar la respuesta guardada
- FCR bruto y neto estimado para siete centros

Al finalizar aparece:

```text
OK cadena completa, resultados y gráficos generados
```

Las pruebas del proceso completo tardaron aproximadamente entre 11 y 31 segundos, con las dependencias instaladas y utilizando la respuesta guardada del dólar. La duración depende del equipo y de la disponibilidad de la API. No incluye la instalación de dependencias.

Los criterios y supuestos se documentan en `DECISIONES_SQLITE.md`, `DECISIONES_EXTERNAS.md` y `FICHA_FCR.md`.

# Parte 1 — Limpieza de SQLite

La función `clean_sqlite()` de `main.py` lee `origen_acuicultura.sqlite`, aplica las decisiones de limpieza acordadas y genera `output_persona1/datos_sqlite_limpios.sqlite`. Es la primera etapa del proceso completo.

Con la base incluida, la salida esperada es:

```text
OK SQLite: 13,157 filas de operación conservadas; 42 cosechas válidas
Archivo: <ruta del proyecto>/output_persona1/datos_sqlite_limpios.sqlite
```

`13,157` significa 13.157 filas. Este mensaje corresponde a la limpieza de SQLite; después continúan las demás etapas.

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

# Parte 2 — Precios, eventos sanitarios y dólar

`limpieza_externas.py` lee el CSV de precios, el JSON de eventos y la API del dólar. Crea la carpeta `output_persona2/`. Si falta la base de la parte 1, el script se detiene porque necesita validar los eventos contra sus centros, jaulas y operación diaria.

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

## Cobertura de datos

Un registro queda fuera cuando se lee de la fuente y una regla de calidad lo excluye. Las filas que no son registros (encabezado repetido y `TOTAL`) y los meses sin fila no se cuentan como excluidos.

| Fuente | Registros leídos | Excluidos | % fuera | Motivo |
| --- | --- | --- | --- | --- |
| Precios (CSV) | 34 | 1 | 2,9 % | Un precio `sin dato` |
| Eventos (JSON) | 8 | 4 | 50,0 % | Cuatro eventos de centros que no existen (90 a 93) |
| Dólar (API) | 248 | 0 | 0 % | La ejecución de verificación tuvo acceso a la API |
| **Total** | **290** | **5** | **1,7 %** | |

Además, hay precio válido en 33 de las 36 combinaciones de tipo de alimento y mes (91,7 %). Faltan Engorda 100 en mayo, Engorda 200 en julio y Pigmentado en febrero. Los dos últimos meses ni siquiera aparecen como fila en el CSV.

## Limitaciones

- La mortalidad observada usa `operacion_limpia`, que ya excluyó filas según los criterios de la parte 1. Puede ser menor que la real, de modo que la diferencia con el JSON podría estar sobreestimada.
- Los meses sin precio se muestran como huecos y no se estiman.

# Parte 3 — FCR bruto y neto estimado

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

# Parte 4 — Costo por kg, mortalidad basal e impacto en pesos

`costo_mortalidad.py` usa `operacion_limpia` (paso 1) y `precios_limpios.csv` y `eventos_limpios.csv` (paso 2).

- Costo por kg = Σ(alimento_kg × precio del mes) ÷ Σ crecimiento_kg. El precio del mes es el promedio de los tipos con precio observado ese mes (no se imputan faltantes).
- Mortalidad basal por lote = muertes ÷ población en días sin evento. Exceso = muertes observadas en días de evento − tasa basal × población.
- Impacto en pesos = alimento extra por FCR peor + alimento invertido en peces muertos por el evento, al precio medio pagado.

Genera `output_costo/costo_mortalidad.xlsx`. Durante esta etapa aparece:

```text
OK costo y mortalidad. Centro top: 7
```

# Parte 5 — Gráficos e interpretación

`main.py` ejecuta automáticamente los cuatro scripts de gráficos después de generar los resultados de limpieza, FCR, costos y mortalidad:

- `graficos_costos.py`
- `graficos_fcr.py`
- `graficos_mortalidad.py`
- `graficos_basal.py`

Los gráficos de mortalidad y basal utilizan el evento EV-8001, que es la selección predeterminada de esos scripts.

Los cuatro scripts de gráficos generan imágenes PNG, los datos utilizados en CSV y su interpretación en Markdown dentro de `output_persona5/`.

Se comparan el costo de alimento por centro, el FCR bruto y neto estimado, la evolución diaria de mortalidad y la mortalidad observada frente a la basal del evento EV-8001.

Los gráficos de costos y basal utilizan `output_costo/costo_mortalidad.xlsx`, generado por `costo_mortalidad.py`. La referencia basal se calcula por lote con observaciones sin evento; el exceso estimado no demuestra atribución causal.


# Uso de IA

- Claude: Apoyo en partes del código e identificar fallas generales.
- ChatGPT: Documentación de código en README y apoyo en partes código.
