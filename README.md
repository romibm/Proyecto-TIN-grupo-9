# AquaFiordo
`main.py` ejecuta el proceso completo en este orden:

1. Limpieza de SQLite mediante `clean_sqlite()`
2. Limpieza de precios, eventos sanitarios y dólar mediante `limpieza_externas.py`
3. Preparación del modelo semántico mediante `modelo_semantico.py`
4. Cálculo del FCR bruto y neto estimado mediante `metricas_fcr.py`
5. Cálculo de costos y mortalidad basal mediante `costo_mortalidad.py`
6. Generación de los cuatro gráficos del informe mediante `graficos_costos.py`, `graficos_fcr.py`, `graficos_mortalidad.py` y `graficos_basal.py`

La ejecución incorpora controles de calidad y se detiene ante fallas bloqueantes.

Cada etapa utiliza las salidas de las anteriores. Se realiza una recarga completa, sin acumular registros. Si una etapa o comprobación crítica falla, la ejecución se detiene con código distinto de cero y registra la falla en `output_calidad/ultima_ejecucion.json`.

Las fuentes originales se conservan intactas.

## Requisitos e instalación

Se utiliza Python 3.12.x y las versiones de `requirements.txt`. La ejecución local de E2 fue verificada con Python 3.12.16.

Utilizar un entorno virtual creado con Python 3.12. Con el entorno activado, comprobar la versión e instalar las dependencias:

```bash
python --version
python -m pip install -r requirements.txt
```

Los comandos siguientes deben ejecutarse dentro de ese entorno virtual.

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
python main.py
```

Este comando ejecuta la limpieza, los cálculos y los gráficos. No es necesario ejecutar los demás scripts por separado.

Como último paso, la cadena genera el prototipo `tablero/tablero.html` y, si Streamlit está instalado, lo abre en el navegador (`localhost:8501`); esa ventana queda corriendo hasta cerrarla con Ctrl+C. Para correr la cadena sin levantar el tablero en vivo —por ejemplo, para verificar la reproducción— usar `py main.py --sin-tablero`: igual se genera el `tablero.html`. Las dependencias del prototipo (`streamlit`, `altair`) ya están en `requirements.txt`, por lo que la instalación inicial las cubre.

Para solicitar una actualización del dólar desde `https://mindicador.cl/api/dolar/2025`:

```powershell
py main.py --actualizar-dolar
```

En Linux/macOS: `python3 main.py --actualizar-dolar`. Se aplica timeout de 15 segundos y se valida toda la respuesta antes de reemplazar la captura. Si la API falla o la respuesta es inválida, se conserva y utiliza la captura válida existente. El informe registra la procedencia y la advertencia.

SQLite, precios y eventos son esenciales: si faltan o invalidan los cálculos, se bloquea la cadena. El dólar es opcional: si tampoco hay captura válida, se advierte y se omite su CSV, retirando esa salida antigua. Las exclusiones de limpieza, los huecos tipo-mes y los netos mensuales no definidos previstos por la fórmula se registran como advertencias; no se cambian las reglas ni se imputan datos. Los demás errores bloquean. Una falla puede dejar archivos parciales; revisar siempre el estado del informe antes de consumir resultados.

## Resultados esperados

| Carpeta | Contenido generado |
| --- | --- |
| `output_persona1/` | Base SQLite limpia y registro de incidencias |
| `output_persona2/` | Precios, eventos y dólar limpios, incidencias y cobertura |
| `output_persona3/` | FCR bruto y neto estimado por centro y su comparación |
| `output_costo/` | Excel con costos, mortalidad basal y valoraciones económicas |
| `output_persona5/` | Cuatro gráficos del informe, sus datos e interpretaciones |
| `output_calidad/` | `ultima_ejecucion.json`: fecha UTC, estado, fuentes, conteos, comprobaciones y fallas; `verificacion_e2.json`: evidencia de las pruebas controladas |
| `output_modelo/` | `modelo_analitico.sqlite`: tabla de hechos y cinco dimensiones; `basales_eventos.csv` y `basales_por_lote.csv`: ambas referencias de basal; `componentes_costos.csv`: valoraciones y traslape estimado |
| `tablero/` | `tablero.html`: prototipo autocontenido del sobrecosto por centro (se abre con doble clic) |

Con los archivos incluidos se esperan:

- 13.157 filas de operación conservadas y 42 cosechas válidas
- 33 precios válidos y cuatro eventos sanitarios válidos
- 248 observaciones del dólar al utilizar la respuesta guardada
- FCR bruto y neto estimado para siete centros

El modelo dimensional contiene 13.157 hechos, 365 fechas, 42 ubicaciones, 42 lotes, tres especies y cinco miembros de evento sanitario, incluido `SIN_EVENTO`. El resumen de basales contiene ocho combinaciones evento/referencia y el detalle contiene veinte combinaciones evento/lote/referencia.

Al finalizar aparece:

```text
OK cadena completa, resultados y gráficos generados
```

Con las entradas incluidas, el estado esperado es `ok_con_advertencias`: existen exclusiones acordadas, tres combinaciones tipo-mes sin precio y un neto mensual no definido. El mensaje de éxito solo aparece después de completar las etapas y comprobar las salidas necesarias. Con las dependencias instaladas, la cadena demora del orden de segundos (a lo más algunas decenas, según el equipo); no incluye la instalación ni el servidor de Streamlit, que queda abierto aparte. Tras el mensaje de éxito queda generado `tablero/tablero.html` y, con Streamlit instalado, el tablero se abre en el navegador.

La ejecución local registra 62 controles: 55 satisfechos, siete advertencias y ningún error bloqueante. Incluye diez controles de la capa semántica; uno de ellos ejecuta cinco pruebas de propiedades sobre las fórmulas, los denominadores, las basales y la asignación de eventos.

Para repetir la verificación de reproducibilidad, ejecutar `python verificar_e2.py`. El verificador utiliza copias temporales sin salidas previas, comprueba que las recargas no acumulen duplicados y compara los datos de las tablas SQLite, los CSV y las celdas Excel. También comprueba el comportamiento ante fallas de fuentes y de la API, sin modificar la captura original ni el informe local de `main.py`. Registra la evidencia en `output_calidad/verificacion_e2.json`. Utiliza las dependencias del entorno activo; no las reinstala. Arquitectura, diagrama, linaje y objetivos de servicio propuestos: [ARQUITECTURA_E2.md](ARQUITECTURA_E2.md).

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

`metricas_fcr.py` utiliza `fact_operacion` y `dim_ubicacion` de `output_modelo/modelo_analitico.sqlite`. Calcula los resultados por centro para las observaciones conservadas de 2025 mediante la función compartida `calcular_fcr()` de `capa_semantica.py`, utilizada también por los cálculos de costos.

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

`costo_mortalidad.py` lee la operación preparada desde `output_modelo/modelo_analitico.sqlite`. Utiliza las funciones compartidas de `capa_semantica.py` para calcular el FCR y aplicar la mortalidad basal.

- Costo por kg bruto: suma del costo de alimento dividida por la suma del crecimiento bruto. El precio mensual es el promedio simple de los tipos de alimento con precio disponible, sin imputar faltantes.
- Basal principal (`lote_sin_evento`): muertes divididas por la suma de población en las observaciones sin evento de cada lote.
- Basal alternativa (`lote_previa_evento`): la misma tasa, utilizando únicamente observaciones sin evento anteriores al inicio del evento analizado.
- Exceso: mortalidad observada durante el evento menos mortalidad esperada según la referencia elegida. Se conservan los valores negativos.
- Las referencias basales se calculan con el historial depurado de 2025 antes de aplicar filtros de visualización.
- Los componentes económicos se publican para ambas basales en `output_modelo/componentes_costos.csv`. Las valoraciones A y B no se suman directamente: el archivo incluye el traslape estimado y la unión `A + B − traslape`. Esta unión no constituye por sí sola una atribución causal del sobrecosto ni un ahorro recuperable.

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


# Parte 6 — Prototipo (tablero)

El prototipo es la capa de consumo: una sola pantalla que responde qué centro concentra el sobrecosto de alimento del año y de dónde viene, para apoyar la decisión de dónde priorizar el control sanitario y de alimentación. Todos sus archivos están en `tablero/`.

## Cómo abrir el prototipo

- **HTML (recomendado para presentar):** doble clic en `tablero/tablero.html`. Es autocontenido: abre en cualquier navegador sin instalar nada ni conexión, y sirve como copia local. Se puede enviar ese único archivo para que otra persona lo use.
- **Streamlit (en vivo):** se levanta solo al final de `py main.py`, o a mano con `py -m streamlit run tablero/tablero_app.py` (en `localhost:8501`, Ctrl+C para cerrar). No genera archivo: necesita el servidor corriendo.

## Qué muestra

Título con la pregunta y selectores de definición del FCR (bruto / neto estimado), centro y referencia basal. Cifra principal (costo de alimento por kg del centro con su comparación y cobertura), reparto del sobrecosto por causa que suma (A por peor FCR + B por peces muertos del evento − traslape = unión A∪B), gráfico por centro, detalle en tabla y pie con fuente, última actualización y dueño.

## Datos y actualización

Sin datos pegados a mano: `tablero/generar_tablero.py` lee `output_modelo/componentes_costos.csv` (reparto por causa y referencia basal) y `output_costo/costo_mortalidad.xlsx` (costo/kg y FCR por centro), las mismas salidas que alimentan el informe. Al volver a correr la cadena, el tablero se regenera y la "última actualización" se toma del archivo de origen más reciente.

Audiencia: Jefatura de Producción / Gerencia de Operaciones. Frecuencia: mensual. La documentación de apoyo de esta parte (checklist de la clase 7, protocolo de la prueba de uso y la sección del informe) está en `tablero/`.

# Uso de IA

- Claude: Apoyo en partes del código e identificar fallas generales.
- ChatGPT: Documentación de código en README y apoyo en partes código.
