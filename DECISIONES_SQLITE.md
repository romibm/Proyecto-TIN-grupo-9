# Decisiones de limpieza de SQLite — persona 1

Este registro documenta los criterios y supuestos aplicados a la limpieza de SQLite en esta implementación.

Se conserva el SQLite original. Las exclusiones retiran filas del análisis sin borrarlas de la fuente. Las fechas y el mes originales, y las etiquetas de zona previas a una corrección, se mantienen para trazabilidad.

| Criterio o supuesto | Motivo | Efecto si fuera falso o se eligiera otro criterio | Quién y cuándo |
| --- | --- | --- | --- |
| Analizar operaciones de 2025 | Período del caso | Incluir otros años cambia el período y las cantidades consideradas | Romina, persona 1 · 09-10-2026 |
| Una observación diaria por fecha, centro, jaula y lote, conservar una copia de duplicados con medidas coincidentes | Evitar contar dos veces la misma operación | Si fueran observaciones distintas de un día, conservar una sola perdería información | Romina, persona 1 · 09-10-2026 |
| Excluir filas cuyo mes original no coincide con el mes de su fecha | Inconsistencia temporal considerada ruido | Si solo el mes estuviera mal, se excluirían observaciones aprovechables, no se corrige sin evidencia | Romina, persona 1 · 09-10-2026 |
| Excluir relaciones diarias de alimento sobre crecimiento inferiores a `0,1` | Se consideran ruido por alimento extremadamente bajo frente al crecimiento registrado | Si fueran reales, excluirlas cambiaría las cantidades consideradas y la relación entre alimento y crecimiento | Romina, persona 1 · 09-10-2026 |
| Conservar relaciones alimento sobre crecimiento altas, con advertencia si superan `10` | Pueden reflejar ineficiencia real | Excluirlas automáticamente puede ocultar el problema de negocio | Romina, persona 1 · 09-10-2026 |
| Población de hoy menos mortalidad de hoy debe coincidir con población de mañana para el mismo lote, sin tolerancia | Se supone que no hubo movimientos de peces no registrados y que los conteos son comparables | Entradas, traslados o cosechas no registradas pueden hacer que se excluyan filas reales | Romina, persona 1 · 09-10-2026 |
| Comparar población solo entre fechas consecutivas disponibles | No se conoce cómo se distribuyen las muertes o movimientos de días ausentes | Las inconsistencias que dependan de un día ausente no pueden detectarse con esta regla | Romina, persona 1 · 09-10-2026 |
| Inferir que Centro Skyring pertenece a Magallanes | El identificador original de zona no existe y la etiqueta predominante de sus operaciones es Magallanes | Una inferencia incorrecta asignaría sus datos a otra región, no altera sus cantidades por centro | Romina, persona 1 · 09-10-2026 |
| Usar la zona del catálogo de centros con la inferencia acordada para Skyring | Mantener una región consistente por centro | Si el catálogo es incorrecto, los resultados regionales estarán mal asignados | Romina, persona 1 · 09-10-2026 |
| Conservar operaciones anteriores a la fecha de siembra, con advertencia | No sabemos qué fecha está equivocada | Si no pertenecieran al lote, se incorporarían cantidades a un grupo incorrecto | Romina, persona 1 · 09-10-2026 |
| Excluir cosechas con lotes inexistentes | No se puede identificar correctamente el lote de la cosecha | Reduce la información de cosechas disponible, no elimina operaciones diarias | Romina, persona 1 · 09-10-2026 |