# AquaFiordo

`main.py` ejecuta el proceso completo de la Entrega 1, en este orden:

1. Limpieza de SQLite mediante la función `clean_sqlite()`
2. Limpieza de precios, eventos sanitarios y dólar mediante `limpieza_externas.py`
3. Cálculo del FCR bruto y neto estimado mediante `metricas_fcr.py`
4. Cálculo de costos y mortalidad basal mediante `costo_mortalidad.py`
5. Generación de los cuatro gráficos del informe mediante `graficos_costos.py`, `graficos_fcr.py`, `graficos_mortalidad.py` y `graficos_basal.py`

Cada etapa utiliza las salidas de las anteriores. Se realiza una recarga completa, sin acumular registros. Si una etapa o comprobación crítica falla, la ejecución se detiene con código distinto de cero y registra la falla en `output_calidad/ultima_ejecucion.json`.

Las fuentes originales se conservan intactas.

## Requisitos e instalación

Se necesita Python 3.10 o superior. El proceso fue verificado con Python 3.12.10 y las versiones exactas de `requirements.txt`, ya instaladas, sin añadir dependencias.

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
| `dolar_2025_crudo.json` | Captura cruda del dólar de 2025, opcional para los cálculos en USD |

Por defecto se utiliza `archivos/dolar_2025_crudo.json`, trasladada desde `output_persona2/` para separarla de las salidas regenerables. La ejecución normal no consulta la red. Conservar esta captura permite repetir las cifras; no se usan resultados calculados anteriormente como fuente.

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

Para solicitar una actualización del dólar desde `https://mindicador.cl/api/dolar/2025`:

```powershell
py main.py --actualizar-dolar
```

En Linux/macOS: `python3 main.py --actualizar-dolar`. Se aplica timeout de 15 segundos y se valida toda la respuesta antes de reemplazar la captura. Si la API falla o la respuesta es inválida, se conserva y utiliza la captura válida existente. El informe registra la procedencia y la advertencia.

SQLite, precios y eventos son esenciales: si faltan o invalidan los cálculos, se bloquea la cadena. El dólar es opcional: si tampoco hay captura válida, se advierte y se omiten su CSV y los dos gráficos de dólar/precios en USD, retirando esas salidas antiguas. Las exclusiones de limpieza, los huecos tipo-mes y los netos mensuales no definidos previstos por la fórmula se registran como advertencias; no se cambian las reglas ni se imputan datos. Los demás errores bloquean. Una falla puede dejar archivos parciales; revisar siempre el estado del informe antes de consumir resultados.

## Resultados esperados

| Carpeta | Contenido generado |
| --- | --- |
| `output_persona1/` | Base SQLite limpia y registro de incidencias |
| `output_persona2/` | Precios, eventos y dólar limpios, cobertura y gráficos complementarios |
| `output_persona3/` | FCR bruto y neto estimado por centro y su comparación |
| `output_costo/` | Excel con costos, mortalidad basal y valoraciones económicas |
| `output_persona5/` | Cuatro gráficos del informe, sus datos e interpretaciones |
| `output_calidad/` | `ultima_ejecucion.json`: fecha UTC, estado, fuentes, conteos, comprobaciones y fallas; `verificacion_e2.json`: evidencia de las pruebas controladas |

Con los archivos incluidos se esperan:

- 13.157 filas de operación conservadas y 42 cosechas válidas
- 33 precios válidos y cuatro eventos sanitarios válidos
- 248 observaciones del dólar al utilizar la respuesta guardada
- FCR bruto y neto estimado para siete centros

Al finalizar aparece:

```text
OK cadena completa, resultados y gráficos generados
```

Con las entradas incluidas, el estado esperado es `ok_con_advertencias`: existen exclusiones acordadas, tres combinaciones tipo-mes sin precio y un neto mensual no definido. El mensaje de éxito solo aparece después de completar las etapas y comprobar las salidas necesarias.

La última recarga verificada en copia temporal tardó aproximadamente 8 segundos, sin red y con las dependencias instaladas. La duración depende del equipo; no incluye instalación.

También se comprobó una instalación de `requirements.txt` en un entorno virtual nuevo y una ejecución de `main.py` en otra copia sin salidas previas, con código 0. La evidencia adicional está en `verificacion_e2.json`, apartado `instalacion_limpia`. Un informe heredado de la implementación anterior marcado como temporal no acredita ejecución local; se conserva intacto hasta ejecutar `main.py` localmente.

Para repetir las pruebas de P1: `py verificar_e2.py` (o `python3 verificar_e2.py`). Usa una copia temporal sin outputs previos, comprueba repetibilidad entre ejecuciones nuevas y ausencia de duplicados; no compara con una referencia anterior de E1. Simula fallas de fuente/API sin modificar la captura original. El modo normal y la etapa omitida prohíben consultas a la API; solo los escenarios de actualización solicitan esa opción y simulan la respuesta o el error. Guarda el informe temporal y los escenarios exclusivamente en `output_calidad/verificacion_e2.json`, con su procedencia. No crea ni reemplaza `ultima_ejecucion.json`, reservado a `main.py` sobre el proyecto local. No reinstala dependencias. Arquitectura, diagrama, linaje y objetivos de servicio propuestos: [ARQUITECTURA_E2.md](ARQUITECTURA_E2.md).

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

`limpieza_externas.py` lee el CSV de precios, el JSON de eventos y la captura cruda del dólar (API solo con actualización explícita). Crea la carpeta `output_persona2/`. Si falta la base de la parte 1, el script se detiene porque necesita validar los eventos contra sus centros, jaulas y operación diaria.

## Trabajo realizado

**Precios (CSV).** El archivo está en Windows-1252 y separado por punto y coma. Se descarta un encabezado repetido a mitad del archivo y la fila `TOTAL`, que no son registros. Se unifican los nombres del alimento (`engorda100`, `Engorda 100` y `ENG-100` pasan a ser Engorda 100, y lo mismo con Engorda 200 y Pigmentado) y se leen precios escritos como `$1.050`, `1.021,00` o `950`. El precio `sin dato` se excluye y no se estima.

**Eventos sanitarios (JSON).** Se validan el centro, las fechas, la mortalidad declarada y las jaulas afectadas contra la base limpia. Se excluyen los eventos de centros que no existen. La fecha `15/10/2025` de EV-8001 se corrige a formato ISO. Para cada evento válido se compara la mortalidad declarada en el JSON con la observada en la operación diaria, en las jaulas afectadas y en todo el centro.

**Dólar (captura/API).** Se lee por defecto `archivos/dolar_2025_crudo.json` y se aplican las exclusiones existentes. La actualización explícita consulta la API, valida la respuesta completa y sustituye la captura solo si es válida; ante falla utiliza el respaldo. Sin captura utilizable se informa qué productos opcionales quedan omitidos.

## Resultados

| Archivo (en `output_persona2/`) | Contenido |
| --- | --- |
| `precios_limpios.csv` | Un precio por tipo de alimento y mes, con el nombre original y la fila del CSV |
| `eventos_limpios.csv` | Eventos válidos con mortalidad declarada y observada |
| `dolar_limpio.csv` | Dólar diario de 2025 (solo con captura o API utilizables) |
| `incidencias_precios.csv`, `incidencias_eventos.csv`, `incidencias_dolar.csv` | Fila u origen, motivo, acción (excluido, corregido o descartado) y detalle |
| `cobertura.txt` | Registros excluidos por fuente y en total |

La captura cruda se conserva en `archivos/dolar_2025_crudo.json`, fuera de esta tabla de salidas regenerables.

## Cobertura de datos

Un registro queda fuera cuando se lee de la fuente y una regla de calidad lo excluye. Las filas que no son registros (encabezado repetido y `TOTAL`) y los meses sin fila no se cuentan como excluidos.

| Fuente | Registros leídos | Excluidos | % fuera | Motivo |
| --- | --- | --- | --- | --- |
| Precios (CSV) | 34 | 1 | 2,9 % | Un precio `sin dato` |
| Eventos (JSON) | 8 | 4 | 50,0 % | Cuatro eventos de centros que no existen (90 a 93) |
| Dólar (captura) | 248 | 0 | 0 % | Respuesta cruda conservada, sin acceso a la red |
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

Se utilizó IA para ayudar con partes del código y la documentación:

- Claude: Para identificar fallas generales de los códigos
