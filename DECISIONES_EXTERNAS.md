# Decisiones de limpieza de precios, eventos sanitarios y dólar — Antonia

Este registro documenta los criterios y supuestos aplicados a la limpieza del CSV de precios, el JSON de eventos sanitarios y la API del dólar en esta implementación.

Se conservan los archivos originales. Las exclusiones retiran registros del análisis sin borrarlos de la fuente. El nombre original del alimento (`tipo_original`) y el número de fila del CSV (`fila_csv`) se mantienen para trazabilidad, y cada exclusión o corrección queda en los archivos `incidencias_*.csv`.

## Criterios generales

| Criterio o supuesto | Motivo | Efecto si fuera falso o se eligiera otro criterio | Quién y cuándo |
| --- | --- | --- | --- |
| Analizar solo 2025 en las tres fuentes | Período del caso, igual que en SQLite | Incluir otros meses o años cambia el período y los promedios | Antonia · 11-10-2026 |
| Definir "registro fuera" como un registro leído que se excluye por una regla de calidad | Hace comparable el porcentaje entre las tres fuentes | Contar también filas descartadas o meses faltantes subiría el porcentaje y mezclaría conceptos distintos | Antonia · 11-10-2026 |
| Calcular el porcentaje total sumando los registros de las tres fuentes, y publicar también el porcentaje de cada una | El total queda dominado por la fuente más grande y el detalle evita una lectura engañosa | Si se leyera solo el total, parecería que el 12 % de todos los datos es defectuoso, cuando el 50 % de los eventos lo es | Antonia · 11-10-2026 |
| Reportar aparte la cobertura de precios por tipo y mes (33 de 36) | Los meses sin fila en el CSV no son registros excluidos, pero igual son información que falta | Si no se reportara, la cobertura de precios se vería mejor de lo que es | Antonia · 11-10-2026 |

## Precios (CSV)

| Criterio o supuesto | Motivo | Efecto si fuera falso o se eligiera otro criterio | Quién y cuándo |
| --- | --- | --- | --- |
| Leer el archivo como UTF-8 y, si falla, como Windows-1252 | El archivo original viene en Windows-1252 y con UTF-8 los acentos se rompen | Una codificación equivocada altera glosas y proveedores, no los precios | Antonia · 11-10-2026 |
| No contar como registros el encabezado repetido a mitad del archivo ni la fila `TOTAL` | No describen un precio de un tipo y un mes | Si se contaran, el total de registros sería 36 en vez de 34 y el porcentaje excluido bajaría | Antonia · 11-10-2026 |
| Unificar `engorda100`, `Engorda 100` y `ENG-100` como Engorda 100; igual con Engorda 200 (`ENG-200`) y Pigmentado (`PIG`) | Son escrituras distintas del mismo producto | Si fueran productos distintos, habría más de tres series y menos precios por serie | Antonia · 11-10-2026 |
| Leer `$1.050` y `1.021,00` como 1050 y 1021 (punto como separador de miles, coma como decimal) | Los precios están en pesos chilenos por kilo y no tienen decimales reales | Si el punto fuera decimal, esos precios serían mil veces menores | Antonia · 11-10-2026 |
| Excluir el precio `sin dato` (Engorda 100, mayo) y no estimarlo | No hay evidencia para inventar un valor | Imputarlo mejoraría la cobertura, pero mezclaría un dato estimado con datos observados | Antonia · 11-10-2026 |
| No rellenar los meses sin fila (Engorda 200 en julio, Pigmentado en febrero) y mostrarlos como huecos en el gráfico | La fuente no los trae | Interpolar daría una línea continua, pero mostraría un precio que no existe en la fuente | Antonia · 11-10-2026 |
| Usar un solo precio por tipo y mes, y excluir los duplicados tipo-mes | El precio se compara por tipo y mes; no se usan proveedor ni glosa | Si hubiera varios proveedores por mes, habría que promediar o elegir uno (con estos datos no ocurre) | Antonia · 11-10-2026 |
| Excluir monedas distintas de CLP | La columna se llama `precio_clp_kg` | Un precio en otra moneda se compararía mal con los demás (con estos datos no ocurre) | Antonia · 11-10-2026 |

## Eventos sanitarios (JSON)

| Criterio o supuesto | Motivo | Efecto si fuera falso o se eligiera otro criterio | Quién y cuándo |
| --- | --- | --- | --- |
| Excluir eventos cuyo centro no existe en el catálogo de centros (EV-900, EV-901, EV-902, EV-903) | No se puede asociar el evento a ningún centro ni a su operación | Si fueran centros reales fuera del catálogo, se perdería información sanitaria y el porcentaje excluido sería menor | Antonia · 11-10-2026 |
| Excluir eventos con jaulas afectadas vacías o que no pertenecen al centro | No se puede medir la mortalidad en las jaulas del evento | Si la lista vacía significara "todo el centro", se excluirían eventos aprovechables | Antonia · 11-10-2026 |
| Leer `15/10/2025` (EV-8001) como día/mes/año y corregirlo a `2025-10-15` | Es el único formato coherente con las demás fechas, y el 15 de octubre cae dentro del período del evento | Si fuera mes/día, la fecha no existiría | Antonia · 11-10-2026 |
| Aceptar la mortalidad declarada como texto o número (`"1500"` y `70399`) | El JSON mezcla tipos para el mismo campo | Un texto no numérico se excluiría como evento inválido (con estos datos no ocurre) | Antonia · 11-10-2026 |
| Medir la mortalidad observada con `operacion_limpia`, tanto en las jaulas afectadas como en todo el centro | Es la operación diaria que ya pasó los criterios de calidad acordados | Esa base excluye filas, así que la mortalidad observada puede ser menor que la real y la diferencia con el JSON se sobreestimaría | Antonia · 11-10-2026 |
| Mostrar la mortalidad declarada al lado de la observada, sin corregir el JSON | No hay evidencia de cuál de las dos cifras es la correcta | Si se tomara una como verdadera, se ocultaría la diferencia entre fuentes | Antonia · 11-10-2026 |

## Dólar (API de mindicador.cl)

| Criterio o supuesto | Motivo | Efecto si fuera falso o se eligiera otro criterio | Quién y cuándo |
| --- | --- | --- | --- |
| Usar `https://mindicador.cl/api/dolar/2025` y guardar la respuesta cruda en `dolar_2025_crudo.json` | La consigna pide el dólar de 2025 y el archivo permite reproducir la ejecución | Sin ese archivo, dos ejecuciones podrían dar valores distintos si la API cambia | Antonia · 11-10-2026 |
| Si la API no responde, usar el archivo guardado; si tampoco existe, dejar la fuente sin datos | Evita detener todo el análisis por una caída de internet | Un archivo guardado antiguo podría no coincidir con la API actual | Antonia · 11-10-2026 |
| Excluir registros del dólar con fecha fuera de 2025, valor no positivo o fecha repetida | Son valores inválidos o ambiguos | Con otra regla cambiaría el promedio mensual | Antonia · 11-10-2026 |
| Si la fuente no tiene datos, no contarla en el porcentaje total ni dibujar los gráficos del dólar | No se puede calcular un porcentaje sobre cero registros | Contarla como 100 % fuera distorsionaría el resultado | Antonia · 11-10-2026 |
| Convertir el precio a dólares con el promedio simple del mes (gráfico 5) | Los precios son mensuales y el dólar es diario | Usar el dólar de un día puntual cambiaría el valor en dólares, no el precio en pesos | Antonia · 11-10-2026 |
