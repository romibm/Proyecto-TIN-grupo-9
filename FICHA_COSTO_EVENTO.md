# Costo por kg y mortalidad atribuible al evento sanitario

Complementa `FICHA_FCR.md` (FCR bruto y neto estimado). Responde la pregunta priorizada: en el centro con más costo, ¿la causa es la mortalidad de un evento sanitario, un FCR peor, o ambas? Todo sale de las observaciones limpias de 2025 y se reproduce con `metricas_evento_costo.py`.

## Fórmulas y unidades

Por centro: `A` = kg de alimento, `G` = kg de crecimiento bruto, `M` = kg de biomasa muerta estimada (`mortalidad_n × biomasa_kg / poblacion`, por observación), `N = G − M`. `P` = precio del alimento del mes (CLP/kg); `C = Σ alimento_kg × P` por observación.

| Resultado | Fórmula | Unidad |
| --- | --- | --- |
| Costo por kg, biomasa bruta | `C / G` | CLP por kg de crecimiento bruto |
| Costo por kg, biomasa neta | `C / N` | CLP por kg de crecimiento neto estimado |
| Mortalidad atribuible al evento | `muertos observados en el evento − tasa basal diaria × población-día del evento` | peces |
| Efecto del evento en el costo | `C/N − C/(N + muertos atribuibles × peso medio del muerto)` | CLP por kg neto |

Descomposición de la brecha de un centro contra el resto: `ln(costo/kg neto) = ln(P) + ln(A/G) + ln(G/N)`. Cada término es la parte de la brecha por precio, por FCR bruto y por mortalidad. Es independiente del orden de los factores.

Solo es costo de alimento. No incluye smolts, sanidad, mano de obra ni merma.

## Fuente, filtros y grano

Fuentes: `operacion_limpia` y `centros` (SQLite limpio), `precios_limpios.csv` y `eventos_limpios.csv` (Antonia). Período 2025, sin exclusiones adicionales. Grano: una fila por centro (costo y FCR), y una fila por evento válido (mortalidad). El dólar (`dolar_limpio.csv`, promedio simple del mes) solo agrega las columnas en USD de la tabla integrada; las cifras de costo y de brecha de esta ficha están en CLP.

## Decisiones de definición y cuánto cambian

| Decisión | Alternativas | Elegida | Efecto |
| --- | --- | --- | --- |
| Biomasa del denominador | Bruta `G` / neta `G − M` | Se muestran ambas; la brecha se mide sobre la neta | Costo/kg de Skyring: 1.742 (bruta) vs 2.251 (neta), +29 %. En los otros centros sube entre 7,9 % y 8,7 % |
| Mortalidad basal | A: mismas jaulas fuera del evento · B: otros centros en las mismas fechas | A | 39.125 vs 39.068 peces atribuibles a EV-8001: la elección casi no cambia el resultado |
| Alcance de la mortalidad del evento | Solo jaulas afectadas / todo el centro | Jaulas afectadas | 39.125 vs 56.493 peces. El evento explica 33,8 % de la brecha (jaulas) o 46,5 % (centro) |
| Precio del alimento | Promedio simple de tipos del mes / solo Engorda 100 | Promedio simple | Brecha anual de Skyring: 679 vs 622 millones de CLP. El ranking de centros no cambia |

La operación diaria no indica el tipo de alimento, por eso se usa el precio promedio del mes. En mayo no hay Engorda 100; la alternativa usa el promedio de ese mes.

## Resultados

Costo de alimento por kg neto (CLP/kg): Skyring 2.251; los otros seis centros entre 1.503 y 1.566 (conjunto: 1.530). Brecha de Skyring: 721 CLP/kg, unos 679 millones de CLP en 2025.

| Factor | Parte de la brecha | CLP por kg neto |
| --- | ---: | ---: |
| FCR bruto peor (1,55 vs 1,25) | 55,4 % | 399 |
| Mortalidad (`G/N`) | 45,4 % | 327 |
| Precio | −0,8 % | −6 |

Dentro de la mortalidad, el evento EV-8001 (Caligus, 1-ago a 15-oct, jaulas 37 a 40) aporta 39.125 peces sobre la mortalidad basal, unos 114 mil kg. Equivale a 41 % de la biomasa muerta de Skyring, a 243 CLP/kg (33,8 % de la brecha) y a unos 229 millones de CLP. Sin ese exceso, el FCR neto de Skyring sería 1,788 en vez de 2,004 (resto de centros: 1,358).

Los otros tres eventos válidos no muestran mortalidad sobre la basal: Cisnes +17, Melinka +16 y Calbuco −27 peces en las jaulas afectadas, contra 6.487, 2.112 y 6.394 declarados en el JSON.

## Hallazgos

1. Son ambas causas y sí se pueden separar: alrededor de un tercio de la brecha corresponde al evento y más de la mitad a un FCR bruto peor. Es una estimación aproximada (la descomposición logarítmica y la secuencial no coinciden al decimal).
2. El FCR bruto de Skyring es 1,55 todos los meses, también antes y después del evento y en las jaulas no afectadas (41 y 42: 1,549; afectadas: 1,552). No hay evidencia de que el evento deteriore el FCR (dentro 1,548, fuera 1,553). El FCR peor es permanente y no sanitario.
3. Fuera de la ventana del evento, la mortalidad diaria de Skyring (0,039 %) es igual a la del resto (0,039 %).
4. La mortalidad declarada en el JSON (70.399 en EV-8001) supera a la observada (45.862 en las jaulas, 66.153 en el centro). No se corrige ninguna de las dos.

## Supuestos

| Supuesto | Motivo | Efecto si fuera falso | Registro |
| --- | --- | --- | --- |
| El precio del mes es el promedio simple de los tipos con precio | La operación no trae el tipo de alimento | Con solo Engorda 100 la brecha baja de 679 a 622 millones de CLP | Persona 3 · 14-10-2026 |
| La tasa basal de las jaulas afectadas fuera del evento es la mortalidad normal | No hay otra referencia sin evento; coincide con la de otros centros | Si esas jaulas ya venían con mortalidad anormal, el evento se subestima | Persona 3 · 14-10-2026 |
| Los peces muertos pesan lo mismo que el promedio de su jaula (2,92 kg por pez en el evento) | La fuente no trae el peso del pez muerto | Más livianos reducen el efecto en pesos; más pesados lo aumentan | Persona 3 · 14-10-2026 |
| La mortalidad observada usa solo filas conservadas por la limpieza | Es la base acordada | Si las filas excluidas tenían mortalidad del evento, está subestimada | Persona 3 · 14-10-2026 |

## Límites

- El FCR bruto de Skyring es casi constante (1,54 a 1,56) todo el año y en todas las jaulas. Conviene confirmar con la contraparte si es operación real o un artefacto del dato antes de la presentación.
- El costo es solo de alimento y no incluye el costo de los peces muertos más allá del alimento ya gastado.

## Detalle mensual de Skyring

En `detalle_mensual_centro_mayor_costo.csv`, el FCR neto de agosto a octubre no es interpretable: en agosto la biomasa muerta supera al crecimiento bruto del mes, el crecimiento neto es negativo y el cociente sale negativo (−24) o inflado (28 en septiembre). Para graficar el mes a mes conviene usar el FCR bruto (1,54 a 1,56 todo el año) y la tasa de mortalidad diaria (0,04 % fuera del evento y 0,27 % en agosto y septiembre). El FCR neto se reporta solo en el total anual.

## Precio y meses sin precio

Cada mes tiene precio válido de al menos dos de los tres tipos de alimento, por eso el promedio simple del mes existe para los 12 meses y no se imputa ni interpola ningún precio. Los huecos de Engorda 100 (mayo), Engorda 200 (julio) y Pigmentado (febrero) solo cambian de qué tipos se promedia ese mes.

## Cómo ejecutar

Después de `main.py` y `limpieza_externas.py`:

```powershell
py metricas_evento_costo.py
```

Genera en `output_persona3/`: `tabla_integrada.csv` (una fila por fecha, centro y jaula, con precio, costo y evento), `costo_por_kg_por_centro.csv`, `mortalidad_evento.csv`, `descomposicion_costo.csv`, `efecto_evento_skyring.csv` y `detalle_mensual_centro_mayor_costo.csv`. Los CSV conservan la precisión completa; las tablas de esta ficha están redondeadas.