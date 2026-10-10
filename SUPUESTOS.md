# AquaFiordo — supuestos y decisiones

Esta bitácora documenta los criterios utilizados en `main.py` para integrar las fuentes de 2025 y calcular los indicadores de alimento y mortalidad. Corresponde a las decisiones adoptadas por Romina, persona 1, durante el trabajo del 9 de octubre de 2026. Las inferencias y supuestos se distinguen de las observaciones de los datos y no se presentan como definiciones confirmadas por la contraparte.

El enunciado exige una bitácora con el supuesto, su motivo, el efecto sobre el resultado si fuera falso y quién lo decidió y cuándo, página 3. También exige comparar las dos definiciones de la métrica, página 2. Este documento registra esos criterios; la cobertura cuantitativa se consulta en `output/cobertura.csv` y en el README de reproducción.

## Alcance y unidad de análisis

La pregunta de trabajo es: **en el centro con mayor costo estimado de alimento por kg de crecimiento reportado, ¿el problema se relaciona con un FCR peor, con la mortalidad durante un evento sanitario o con ambas cosas?** Corresponde a la segunda pregunta del README del caso, con una definición explícita de costo.

Se consideran únicamente costos de alimento, porque el CSV entrega precios de alimento. El indicador principal es CLP por kg de crecimiento reportado, no gasto operacional total. El gasto estimado acumulado de alimento queda disponible como un dato adicional.

**Una fila es una observación diaria de una combinación de fecha, centro, jaula y lote.** Los costos y las cantidades se suman antes de calcular las razones por centro o por centro y mes. Las cosechas y los eventos sanitarios conservan su propia unidad de análisis y no se suman directamente a las filas diarias.

## Bitácora de supuestos que afectan las cifras

La columna «decidido por y fecha» identifica a quien adoptó el criterio para esta implementación. La validación futura con la contraparte puede reemplazar un supuesto; para hacerlo deben recalcularse los resultados.

| Supuesto o decisión | Por qué se adoptó | Qué cambia si resulta falso o se usa otra definición | Decidido por y fecha |
| --- | --- | --- | --- |
| El período de análisis es 2025 y se excluyen operaciones de otros años | Es el período del caso y de las fuentes de precios y dólar | Incluir otros períodos cambia el alimento, crecimiento, mortalidad y costos acumulados, y requiere precios y dólar de esos períodos | Romina, persona 1 · 09-10-2026 |
| El centro de mayor costo se identifica por costo estimado de alimento por kg de crecimiento reportado | Permite comparar el costo por kg entre centros de distinto tamaño con los datos disponibles | Ordenar por gasto acumulado puede elegir otro centro, un ranking de costo operacional total requeriría gastos adicionales | Romina, persona 1 · 09-10-2026 |
| Cada tipo de alimento representa un tercio de los kg suministrados, `engorda100`, `engorda200` y `pigmentado` | La operación entrega alimento total y no una distribución diaria por tipo | Si la mezcla real es distinta, cambian el costo estimado en CLP y USD y posiblemente el ranking, el FCR basado en kg totales no cambia | Romina, persona 1 · 09-10-2026 |
| Un precio faltante se estima con el promedio aritmético de los precios válidos observados del mismo alimento durante 2025 | Se eligió una referencia anual por alimento ante la ausencia del precio mensual | Si el precio real del mes difiere, cambia el costo de ese mes y los acumulados, no cambian los kg de alimento, crecimiento ni el FCR | Romina, persona 1 · 09-10-2026 |
| Las relaciones diarias `alimento_kg / crecimiento_kg` inferiores a `0,1` se consideran ruido y se excluyen | Se observaron cantidades de alimento extremadamente bajas frente al crecimiento reportado | Si esas observaciones fueran reales, su exclusión elimina crecimiento con poco alimento y puede aumentar el FCR y el costo por kg calculados | Romina, persona 1 · 09-10-2026 |
| `poblacion` representa un conteo comparable entre días consecutivos del mismo lote y no existen entradas o salidas de peces sin registrar | Permite contrastar la mortalidad con la disminución de población | Si hubo traslados, cosechas u otros movimientos no registrados, la regla puede excluir operaciones reales y cambiar mortalidad, crecimiento, costos y FCR | Romina, persona 1 · 09-10-2026 |
| Centro Skyring pertenece a Magallanes, inferencia | Su `zona_id` original no existe en el catálogo y Magallanes es la etiqueta predominante de sus operaciones | Si la inferencia fuera incorrecta, cambia la asignación regional de sus resultados, no cambian sus cantidades ni su ranking por centro | Romina, persona 1 · 09-10-2026 |
| El catálogo de centros tiene prioridad sobre la etiqueta `operacion_diaria.zona`, con la inferencia acordada para Skyring | Se necesita una región consistente por centro ante etiquetas contradictorias | Si el catálogo fuera incorrecto, los resultados por región quedarían mal asignados, los totales por centro se conservan | Romina, persona 1 · 09-10-2026 |
| Se conservan operaciones anteriores a `fecha_siembra` con una advertencia | No hay evidencia suficiente para determinar cuál de las fechas está equivocada | Si esas operaciones no pertenecen realmente al lote, su inclusión afecta los acumulados y la tasa basal del lote | Romina, persona 1 · 09-10-2026 |
| En días sin cotización se utiliza el último dólar disponible del mismo día o de una fecha anterior | Permite convertir el costo diario sin excluir operaciones por falta de publicación | Una cotización diaria distinta cambia los costos en USD, no cambia los costos en CLP ni el ranking principal | Romina, persona 1 · 09-10-2026 |
| Si al inicio del año no existe una cotización anterior, se utiliza la primera disponible del año | Resuelve los primeros días sin una referencia previa en la serie de 2025 | El costo en USD de esos días utiliza una observación posterior y puede diferir de una conversión con otra referencia | Romina, persona 1 · 09-10-2026 |
| Un evento sanitario se vincula por su centro, las jaulas listadas y las fechas de inicio y fin, ambas incluidas | El JSON entrega ese alcance y permite localizar las observaciones diarias expuestas | Fechas o jaulas incorrectas cambian qué días se consideran con evento sanitario, la basal y el exceso estimado | Romina, persona 1 · 09-10-2026 |
| Para calcular la mortalidad basal, observada y en exceso se usa `operacion_diaria.mortalidad_n`, la mortalidad declarada del JSON se conserva por separado | La fuente diaria permite una comparación reproducible entre días con y sin eventos sanitarios | Si el registro diario tiene errores o cobertura incompleta, cambia la estimación, las dos fuentes pueden tener alcances distintos y no deben forzarse a coincidir | Romina, persona 1 · 09-10-2026 |
| Los días conservados sin eventos sanitarios registrados representan la mortalidad habitual del mismo lote | La referencia del propio lote evita usar una mortalidad común para grupos de peces distintos | Si hubo eventos sanitarios no registrados u otros cambios en el lote, la basal puede estar sesgada y sobreestimar o subestimar el exceso | Romina, persona 1 · 09-10-2026 |
| La tasa basal diaria es muertes totales divididas por la suma de poblaciones de los días conservados sin eventos sanitarios, usando todos esos días de 2025 | Ajusta por la población expuesta y aprovecha la información disponible del lote | Una referencia de otro período, solo previa al evento sanitario o ajustada por otras condiciones puede producir otro exceso estimado | Romina, persona 1 · 09-10-2026 |
| El exceso sobre la basal aproxima el efecto del evento sanitario, bajo ese supuesto | Se necesita separar mortalidad habitual y mortalidad adicional durante el evento sanitario | Otros factores simultáneos también pueden explicar el exceso, por lo que no demuestra que todas esas muertes hayan sido causadas por el evento sanitario | Romina, persona 1 · 09-10-2026 |
| `crecimiento_kg` se interpreta como crecimiento antes de descontar la biomasa perdida por mortalidad, inferencia | El contraste de días consecutivos en el balance de biomasa respalda esa lectura, no es una definición confirmada por el cliente | Si el crecimiento ya descontara la mortalidad, el FCR alternativo la descontaría por segunda vez y sobreestimaría el alimento por kg neto | Romina, persona 1 · 09-10-2026 |
| El peso de los peces muertos se estima con el peso promedio de los vivos del mismo registro, `biomasa_kg / poblacion` | No se dispone del peso individual de los peces muertos | Si los muertos pesan menos, se sobreestima la biomasa perdida y el FCR alternativo, si pesan más ocurre lo contrario, el FCR principal no cambia | Romina, persona 1 · 09-10-2026 |
| Se conserva como principal el FCR sin descuento adicional de mortalidad y se reporta también el FCR alternativo con descuento estimado | Permite mostrar la sensibilidad a la definición, como exige el enunciado y como se propuso al grupo | Elegir solo una definición oculta cuánto depende la conclusión del tratamiento de la biomasa perdida | Romina, persona 1 · 09-10-2026 |

Los precios estimados se identifican en `precios_alimento`. La mezcla asumida y los meses que contienen precios estimados se identifican en `mezcla_mensual` y `operacion_integrada`. El código también calcula costos mínimos y máximos usando el precio más bajo y más alto de los tipos considerados en cada mes; son escenarios de mezcla, no intervalos de confianza.

## Decisiones de calidad y trazabilidad

Estos criterios se aplican a las fuentes originales, que se conservan sin modificar. Una exclusión retira la fila del análisis, no la borra del archivo de origen. Los motivos quedan en `incidencias_calidad` y la cobertura se calcula contando una sola vez cada fila excluida por fuente.

| Criterio aplicado | Motivo | Efecto y límite del criterio | Decidido por y fecha |
| --- | --- | --- | --- |
| Conservar una copia por fecha, centro, jaula y lote cuando coinciden las medidas normalizadas y la etiqueta de zona, se elige la menor fila de origen | Evitar duplicar cantidades y costos por un registro repetido | Si fueran observaciones distintas de un día, conservar una sola perdería información, se adopta el grano diario declarado | Romina, persona 1 · 09-10-2026 |
| Excluir filas cuyo `mes` original no coincide con el mes de la fecha normalizada | Inconsistencia temporal considerada ruido | Si solo `mes` estuviera mal y el resto fuera correcto, se excluirían observaciones utilizables, no se corrige sin evidencia | Romina, persona 1 · 09-10-2026 |
| Excluir la fila de hoy si `poblacion_hoy - mortalidad_hoy` difiere de `poblacion_mañana` para el mismo lote | Incompatibilidad con el balance de población asumido | Se comparan solo fechas consecutivas disponibles, la tolerancia es cero peces y no se inventan observaciones para días ausentes | Romina, persona 1 · 09-10-2026 |
| Conservar las relaciones alimento sobre crecimiento altas, con advertencia si superan `10` | Pueden representar ineficiencia real o efectos de mortalidad | Excluirlas automáticamente podría ocultar precisamente el problema que se busca analizar | Romina, persona 1 · 09-10-2026 |
| Excluir eventos sanitarios de centros inexistentes en las fuentes operacionales | No pueden vincularse a operaciones conocidas y no hay evidencia para corregir el identificador | Se limita el análisis sanitario a centros identificables, no se excluyen operaciones por esta regla | Romina, persona 1 · 09-10-2026 |
| Excluir cosechas de lotes inexistentes | Falta una referencia de lote válida y no hay evidencia para corregirla | Se limita la cobertura de cosechas, no se excluyen operaciones por esta regla | Romina, persona 1 · 09-10-2026 |
| Excluir el encabezado repetido y la fila `TOTAL` vacía del CSV | No son observaciones de precio por alimento y mes | No se consideran precios, se conservan los archivos originales para revisar el descarte | Romina, persona 1 · 09-10-2026 |

Además, la implementación verifica formatos, referencias y cantidades válidas, rechaza cotizaciones de dólar repetidas o inválidas y excluye duplicados diarios que tengan medidas contradictorias. Estos son controles preventivos del código, no hallazgos que se atribuyan al cliente. No se encontraron duplicados diarios conflictivos en las operaciones válidas del período.

La detección de discrepancias de mes se registra antes de quitar duplicados. El balance de población se compara con las observaciones disponibles del día siguiente antes de aplicar las exclusiones de calidad. Así, una fila excluida todavía permite verificar el balance del día anterior. Finalmente se aplica la unión de motivos, evitando contar la misma fila más de una vez.

## Definiciones exactas de los indicadores

En las expresiones siguientes, `d` representa una fila diaria conservada y `S` las filas de un centro o de un centro y mes. Los kg son cantidades reportadas o estimadas según se indica.

### Costo estimado de alimento

```text
precio_mezcla_mes = (precio_engorda100 + precio_engorda200 + precio_pigmentado) / 3
costo_alimento_d_clp = alimento_kg_d * precio_mezcla_mes
costo_alimento_S_clp = suma(costo_alimento_d_clp)
costo_por_kg_S = costo_alimento_S_clp / suma(crecimiento_kg_d)
costo_alimento_S_usd = suma(costo_alimento_d_clp / dolar_utilizado_d)
```

El costo por kg tiene unidad **CLP/kg de crecimiento reportado**. Los centros se ordenan de mayor a menor por este indicador. La conversión a USD se hace por día antes de sumar, no con un dólar promedio del año.

### FCR principal y alternativo

```text
peso_promedio_estimado_d_kg = biomasa_kg_d / poblacion_d
biomasa_muertos_estimada_d_kg = mortalidad_n_d * peso_promedio_estimado_d_kg
crecimiento_neto_estimado_S_kg = suma(crecimiento_kg_d) - suma(biomasa_muertos_estimada_d_kg)

fcr_principal_S = suma(alimento_kg_d) / suma(crecimiento_kg_d)
fcr_alternativo_S = suma(alimento_kg_d) / crecimiento_neto_estimado_S_kg
diferencia_fcr_S = fcr_alternativo_S - fcr_principal_S
variacion_fcr_porcentaje_S = 100 * diferencia_fcr_S / fcr_principal_S
```

Ambos FCR tienen unidad **kg de alimento/kg de crecimiento**, con crecimiento neto estimado en la alternativa. Se calculan sobre cantidades acumuladas, no promediando los FCR diarios. Si el denominador alternativo no es positivo, el indicador se deja sin valor, no se representa como cero. Los CSV muestran ese valor ausente como una celda vacía y SQLite como `NULL`.

### Mortalidad basal y exceso durante un evento sanitario

```text
tasa_basal_lote = suma(muertes en días sin eventos sanitarios) / suma(poblacion en esos días)
muertes_esperadas_d = poblacion_d * tasa_basal_lote
exceso_d = mortalidad_n_d - muertes_esperadas_d, en días con evento sanitario
exceso_evento_sanitario = suma(exceso_d de las filas vinculadas al evento sanitario)
```

La tasa basal es una tasa diaria por pez expuesto. La mortalidad observada, la esperada y el exceso se expresan en **peces**; la mortalidad esperada y el exceso pueden ser fraccionarios porque son estimaciones. Si un lote no tiene una referencia basal disponible, su exceso no se calcula. Un exceso negativo se conserva y significa que la mortalidad observada está por debajo de la referencia.

Si se superponen eventos sanitarios, una operación puede vincularse a más de uno mediante `puente_eventos_operacion`. El resumen por centro cuenta la operación una sola vez; sumar resúmenes de eventos sanitarios superpuestos podría contar las mismas muertes más de una vez.

## Lectura de las dos fuentes de mortalidad

`mortalidad_observada_durante_evento_n` es la suma de las muertes diarias de las filas conservadas que coinciden con el centro, las jaulas y las fechas del evento sanitario. Incluye las causas de mortalidad registradas durante ese intervalo, sin probar cuál fue la causa de cada muerte.

`mortalidad_asociada_declarada_json_n` conserva la cifra de `mortalidad_asociada` informada por el JSON. Una diferencia entre ambas cifras no demuestra por sí sola un error: el alcance de la declaración y la cobertura de las observaciones diarias pueden ser distintos. El código no reemplaza una cifra por la otra ni las resta para estimar la mortalidad causada por el evento sanitario.

## Evidencia y archivos para revisar los criterios

| Archivo o tabla | Para qué sirve |
| --- | --- |
| `config_utilizada.json` | Registra los parámetros efectivamente usados, como mezcla, umbrales, período y definiciones |
| `incidencias_calidad.csv` | Identifica la fuente, la fila original, el motivo y la acción de cada incidencia |
| `verificacion_crecimiento.json` | Conserva la evidencia del contraste de biomasa que respalda la inferencia sobre crecimiento |
| `ejecucion.json` | Identifica las fuentes mediante sus hashes, el modo de uso de la API y los supuestos de crecimiento y peso de muertos |
| `resumen_centros.csv` y `resumen_centro_mes.csv` | Entregan ambos FCR, sus diferencias y los costos calculados |
| `basal_por_lote.csv` y `resumen_eventos_sanitarios.csv` | Permiten revisar la referencia basal y la comparación entre mortalidad observada, esperada y declarada |

## Declaración de uso de IA

Se utilizó ChatGPT, con Codex, para apoyar la construcción y revisión del código y redactar esta documentación, con decisiones revisadas por Romina.

Esta declaración debe incluirse también al final del informe del grupo, como exige el enunciado, página 3.
