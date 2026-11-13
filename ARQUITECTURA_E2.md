# AquaFiordo · Entrega 2 · Persona 1, componente B

Arquitectura y operación de la cadena existente. Entrada única: `python main.py`.
No se incorpora un modelo nuevo ni se implementa el prototipo.

## Capas y diagrama

Diagrama [editable en diagrams.net](docs/arquitectura.drawio) y [exportación SVG](docs/arquitectura.svg).

| Capa | Elementos reales y propósito |
| --- | --- |
| Orígenes | SQLite operativo y catálogos, CSV de precios, JSON sanitario entregados y API mindicador.cl para actualización explícita del dólar de 2025 |
| Cruda | `archivos/origen_acuicultura.sqlite`, `origen_costos_alimento.csv`, `origen_eventos_sanitarios.json`, `dolar_2025_crudo.json`; entradas conservadas, separadas de resultados regenerables |
| Depurada | `clean_sqlite()` en `main.py` produce `output_persona1/datos_sqlite_limpios.sqlite`; `limpieza_externas.py` produce CSV, incidencias y cobertura en `output_persona2/` |
| Modelo analítico existente | `metricas_fcr.py` agrupa por centro en `output_persona3/fcr_por_centro.csv`; `costo_mortalidad.py` calcula las hojas del Excel `output_costo/costo_mortalidad.xlsx`. Esta capa describe esos cálculos, sin agregar tablas |
| Consumo | Cuatro scripts `graficos_*.py`: PNG, CSV y Markdown en `output_persona5/`; gráficos complementarios en `output_persona2/graficos/`; informe. Prototipo únicamente como consumo previsto |

`main.py` coordina las etapas mediante el mismo intérprete y directorio del proyecto.
`calidad.py` comprueba las entradas, las filas depuradas, los denominadores y los
productos requeridos. Su JSON es evidencia de P1, sin contrato para el prototipo.

## Tres decisiones de operación

1. **ETL local, con cruda persistida.** Se extraen los archivos y se transforman
   en Python antes de cargar la base depurada y los CSV. Las agregaciones permanecen
   en los scripts actuales, usando SQL y pandas. Mantener las reglas junto a sus
   transformaciones permite repetir el proceso sin montar otra plataforma ni
   modificar las definiciones de los indicadores.
2. **Recarga completa.** En cada invocación se releen las fuentes y se sustituyen
   las salidas, sin anexar registros. SQLite se escribe en un temporal y se
   reemplaza con la conexión cerrada. Después de comprobar SQLite se retiran
   los productos posteriores requeridos de la ejecución anterior, para que una
   etapa que no los genere no pueda acreditarse con archivos antiguos.
   La captura cruda no se regenera, salvo
   solicitud explícita. Es suficiente para el volumen anual entregado y evita
   gestionar incrementales, marcas de avance y duplicados.
3. **Fallas según dependencia real.** SQLite, precios y eventos son esenciales:
   ausencia, estructura ilegible o datos depurados que invalidan los cálculos
   bloquean la ejecución con código 1. El dólar es opcional: su ausencia advierte
   y omite el dólar mensual y los precios en USD; no afecta el FCR ni los costos
   en CLP. La API se consulta solo con `--actualizar-dolar`, con timeout de 15 s.
   Se valida identidad, estructura, fechas únicas de 2025 y valores positivos de
   toda la respuesta nueva antes de sustituir la captura mediante un temporal.
   Si falla, se usa la captura válida conservada; sin ella no se inventan datos.

Una exclusión aplicada por las reglas de limpieza se registra como advertencia,
no como un fallo del cálculo. No se alteraron esos criterios para conseguir más
cobertura. Una salida inválida o una etapa fallida impide anunciar éxito.
No hay transacción global: una falla tardía puede dejar productos parciales o
anteriores en disco; solo el informe de estado y las etapas completadas acreditan
la ejecución. Esos productos nunca sustituyen una fuente cruda ausente.

## Comprobaciones automáticas

Referencia común: `output_calidad/ultima_ejecucion.json`, lista `comprobaciones`,
identificada por `nombre`; conteos en `conteos`, procedencia y SHA-256 en `fuentes`.
Cada comprobación incluye `resultado`, `severidad` y `detalle`. `error` bloquea;
`advertencia` permite continuar. Si una comprobación bloquea, las posteriores no
se presentan como ejecutadas. Las excepciones también quedan registradas.

| Qué se verifica | Política | Nombre del resultado |
| --- | --- | --- |
| Presencia de cada fuente esencial e integridad física SQLite | Bloquea | `fuente_sqlite`, `fuente_precios`, `fuente_eventos`, `integridad_sqlite` |
| Columnas de precios y estructura JSON de eventos | Bloquea | `estructura_precios`, `estructura_eventos` |
| Leídos = conservados + excluidos; encabezado repetido y TOTAL separados | Bloquea si no concilia; exclusiones advierten | `conciliacion_*`, `exclusiones_*`, `conteos` |
| Catálogos únicos y referencias válidas entre catálogos y operación | Bloquea | `catalogos_unicos`, `referencias_catalogos`, `referencias_operacion` |
| Clave única fecha-centro-jaula-lote | Bloquea | `clave_operacion` |
| Fechas en 2025, mes coherente, cantidades finitas, positivas según reglas, mortalidad entre cero y población | Bloquea | `periodo_operacion`, `cantidades_operacion` |
| Referencias, fechas y kilos válidos de cosechas | Bloquea | `cosechas_validas` |
| Advertencias que la limpieza conserva, como operación antes de siembra | Advierte | `advertencias_limpieza_sqlite`; detalle por fila en `incidencias_sqlite` |
| Precio positivo, tipo, período y unicidad tipo-mes; al menos un precio en cada mes operativo | Bloquea | `precios_validos`, `precio_meses_operacion` |
| Cobertura de las 36 combinaciones de tres alimentos y doce meses | Advierte; no imputa | `cobertura_tipo_mes`, `conteos.completitud_precios` |
| Eventos únicos, fechas ordenadas, mortalidad no negativa y jaulas del centro; observaciones disponibles y EV-8001 para gráficos | Bloquea | `eventos_validos`, `observaciones_<evento_id>`, `evento_graficos` |
| Dólar disponible, procedencia y fallo de API; dólar depurado con fechas únicas y valor finito positivo | Ausencia/API fallida advierte; salida depurada inválida bloquea | `disponibilidad_dolar`, `actualizacion_api`, `dolar_valido` cuando está disponible |
| Población fuera de eventos por lote; alimento, población y crecimiento en grupos usados por los indicadores; pares consecutivos para la verificación existente | Bloquea | `denominador_basal`, `denominadores_indicadores`, `denominador_verificacion_crecimiento` |
| Crecimiento neto positivo por centro, exigido por el FCR actual | Bloquea | `denominador_fcr_neto_centros` |
| Neto no positivo en resúmenes de costos que ya contemplan resultado vacío | Advierte; conserva el vacío definido en el script | `netos_no_definidos_costo` |
| Archivos necesarios de todas las etapas, incluidos gráficos complementarios según disponibilidad del dólar | Bloquea si faltan o están vacíos | `salidas_requeridas`, `etapas` |

## Linaje de campos de las métricas actuales

Las reglas detalladas siguen en `DECISIONES_SQLITE.md`, `DECISIONES_EXTERNAS.md`
y `FICHA_FCR.md`. No se redefinen fórmulas ni se anticipan reglas de P2.

| Fuente / campos | Transformación existente | Salida y uso |
| --- | --- | --- |
| SQLite `operacion_diaria`: `fecha`, `mes`, `centro_id`, `jaula_id`, `lote_id`, `especie_id` | Formatos de fecha, período, mes consistente, referencias, duplicados y exclusiones acordadas; conserva `origen_fila` y fecha/mes originales | `operacion_limpia`: claves de agrupación, meses de precios y selección de jaulas/días de evento |
| SQLite `alimento_kg`, `crecimiento_kg` | Conversión numérica, cantidades positivas, umbral alimento/crecimiento y limpieza existente | Totales por centro en `fcr_por_centro.csv`; `fcr_bruto = Σ alimento / Σ crecimiento`; Excel: centros, meses y especies |
| SQLite `mortalidad_n`, `biomasa_kg`, `poblacion` | Conversión, balance de población y límites acordados; peso medio `biomasa_kg / poblacion`; biomasa muerta `mortalidad_n × peso medio` | CSV FCR: `biomasa_muerta_estimada_kg`, `crecimiento_neto_estimado_kg`, `fcr_neto_estimado`, `diferencia_fcr`, `cambio_porcentual_fcr`; Excel: mortalidad, tasas y crecimiento neto |
| SQLite `centros.nombre`, `centros.zona_id`, `zonas.zona` | Inferencia de zona acordada para centro 7 y corrección de etiquetas con originales conservados | Nombre y zona en CSV FCR, Excel y gráficos; no cambia las cantidades |
| CSV `tipo_alimento`, `mes`, `precio_clp_kg`, `moneda` | Normalización de tipos, lectura numérica, CLP positivo, exclusiones y unicidad tipo-mes; conserva `tipo_original`, `fila_csv`; media de tipos observados por mes | `precios_limpios.csv`; Excel `precio_mes`, costo `Σ(alimento × precio_mes) / Σ crecimiento`; precio medio pagado `Σ costo / Σ alimento` |
| JSON `evento_id`, `centro_id`, `fecha_inicio`, `fecha_fin`, `jaulas_afectadas`, `mortalidad_asociada` | Fechas ISO y validación; suma de mortalidad de operación en intervalo/jaulas; marca `evento_id` con el orden actual de eventos | `eventos_limpios.csv`: mortalidad declarada y observada; Excel `eventos`; selección de días sin evento por lote para la basal |
| Operación depurada y marca de evento | Basal existente `Σ muertes / Σ población` fuera de eventos por lote; esperadas = basal × población en evento; exceso = observadas − esperadas | Excel `eventos`, `por_centro`, hojas mensuales e `impacto`; gráficos de mortalidad y basal. El exceso no demuestra causalidad |
| Captura dólar `serie[].fecha`, `serie[].valor` | Fecha ISO, positivo, período, duplicados; promedio mensual de observaciones disponibles y conversión de precio CLP a USD | `dolar_limpio.csv`, gráficos complementarios de dólar y alimento en USD; no participa en costos CLP ni FCR |

Los resultados del Excel incluyen las valoraciones económicas ya implementadas;
esta intervención solo protege sus entradas y denominadores. Los datos de
`output_persona5/` alimentan el informe actual. El prototipo es consumo previsto,
sin pantallas, interfaces ni conexión implementadas aquí.

## Acuerdo de servicio propuesto

Objetivos propuestos para acordar con la empresa; no son compromisos ya medidos.

| Dimensión y objetivo numérico propuesto | Justificación y responsable empresarial | Resultado medido |
| --- | --- | --- |
| Frescura: regenerar resultados dentro de **24 horas** de recibir una nueva entrega aprobada de fuentes | La fuente es un corte anual de 2025; interesa incorporar cada entrega. Responsable: jefe de operaciones de datos | No evaluable: falta fecha de recepción/aprobación. La duración de las pruebas en `verificacion_e2.json` mide ejecución, no frescura |
| Completitud operativa: disponer de **al menos 95 % de las observaciones diarias esperadas** | Meta propuesta para limitar huecos de recepción a un 5 %, sujeta a acordar una referencia independiente. Responsable: jefe de control de gestión | **No medible actualmente**: falta un registro empresarial aprobado de días de operación por centro-jaula-lote, con altas, bajas y suspensiones, independiente de las filas recibidas. No se afirma cumplimiento |
| Calidad: **100 % de las comprobaciones bloqueantes aplicables satisfechas** antes de consumir una ejecución | Evita publicar indicadores con claves, referencias o denominadores inválidos. Responsable: jefe de analítica | **0 fallas bloqueantes**; estado `ok_con_advertencias`. Se mantienen las exclusiones, huecos y neto mensual no definido |

**Conservación** es conservados / recibidos: operación 13.157/14.409 (**91,31 %**),
cosechas 42/48 (**87,50 %**), precios 33/34 (**97,06 %**), eventos 4/8 (**50 %**)
y dólar 248/248 (**100 %**). Encabezado repetido y TOTAL no son registros.
Estos porcentajes describen la limpieza, sin demostrar que se recibieron todas
las observaciones esperadas. **Completitud** es disponibles / esperados: exige
la referencia independiente descrita en la tabla y no puede inferirse del número
de filas recibidas. No se inventa una malla diaria ni un calendario cambiario.
Por separado, la cobertura conocida de precios es **33/36 combinaciones tipo-mes
(91,67 %)**, sobre tres alimentos y doce meses, sin estimar los tres faltantes.

## Evidencia y límites de la verificación

`python verificar_e2.py` copia código, requisitos y entradas crudas a un directorio
temporal sin `output_*`. Usa Python 3.12.10 y las versiones declaradas en
`requirements.txt`, ya instaladas. Ejecuta la cadena, la repite, compara todas las
tablas SQLite, CSV y valores de todas las hojas Excel, y verifica claves únicas.
No compara bytes de Excel ni imágenes y no modifica las fuentes originales.

Se verificaron también API fallida sin red con respaldo y mismas cifras,
actualización con valor inválido rechazada sin sustituir la captura, timeout
configurado, precios ausentes bloqueando aun con outputs anteriores presentes,
y dólar ausente con advertencia y retirada de sus productos antiguos. Una etapa
que retorna cero sin generar sus archivos también bloqueó el éxito de la cadena.
Finalmente se restauraron las entradas de la copia y se ejecutó otra recarga
válida con los mismos datos que la primera. Esto demuestra repetibilidad entre
ejecuciones nuevas; no es comparación con una referencia anterior de E1.
El informe temporal y los informes de escenarios se guardan exclusivamente en
`output_calidad/verificacion_e2.json`, con su procedencia. El verificador no crea
ni reemplaza `output_calidad/ultima_ejecucion.json`: ese archivo corresponde
exclusivamente a `main.py` ejecutado en el proyecto local.
El modo normal y la etapa omitida prohíben consultas a la API mediante un mock
que provoca un fallo ante cualquier intento; únicamente los escenarios de
actualización usan el indicador explícito y respuestas o errores simulados.

Resultado con las entradas incluidas: **13.157 operaciones, 42 cosechas, 33 precios,
4 eventos, 248 observaciones de dólar y FCR de siete centros**. En agosto del
centro de mayor costo, los indicadores netos del Excel quedan vacíos conforme a
la fórmula existente. Se preservaron los cambios previos del usuario en los
outputs locales. No se probó una actualización real de la API ni se compararon
resultados contra una referencia anterior de E1. La verificación completa se ejecutó una
vez tras las comprobaciones puntuales, con dependencias ya instaladas.
Adicionalmente se creó un entorno virtual nuevo, se instaló `requirements.txt`
y se ejecutó `main.py` en otra copia sin outputs previos: terminó con código 0.
Su informe está en `verificacion_e2.json`, apartado `instalacion_limpia`.
Se comprobó también el caso sin informe local previo ejecutando la lógica de
`verify()` con procesos de cadena simulados: no lo crea; la verificación completa
real conservó el informe preexistente y la captura original byte por byte.
Si permanece un informe heredado marcado como temporal de la implementación
anterior, no acredita ejecución local; se conserva intacto y solo una ejecución
local de `main.py` debe sustituirlo.
