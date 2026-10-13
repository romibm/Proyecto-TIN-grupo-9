# FCR bruto y neto estimado por centro

Este cálculo presenta ambas definiciones del factor de conversión alimenticia y cuantifica su diferencia. Se utilizan las mismas observaciones limpias de 2025 para las dos definiciones.

## Fórmulas y unidad

Para cada centro, se definen:

- `A`: suma de `alimento_kg`, en kg de alimento
- `G`: suma de `crecimiento_kg`, en kg de crecimiento bruto según el supuesto de esta implementación
- `M`: suma de `mortalidad_n × biomasa_kg / poblacion`, en kg de biomasa muerta estimada, calculando el peso promedio por observación antes de sumar
- `N`: crecimiento neto estimado, `G − M`, en kg

| Resultado | Fórmula | Unidad |
| --- | --- | --- |
| FCR bruto | `A / G` | kg de alimento por kg de crecimiento bruto |
| FCR neto estimado | `A / N` | kg de alimento por kg de crecimiento neto estimado |
| Diferencia absoluta | FCR neto estimado − FCR bruto | kg de alimento por kg de crecimiento |
| Cambio porcentual | `(FCR neto estimado / FCR bruto − 1) × 100` | % respecto del bruto |

Se divide la suma de alimento entre la suma del denominador correspondiente. No se promedian las razones diarias, porque ese promedio daría el mismo peso a días con cantidades distintas.

## Fuente, filtros y grano

Fuente: `output_persona1/datos_sqlite_limpios.sqlite`, tablas `operacion_limpia` y `centros`.

Se utilizan las observaciones conservadas con fecha desde 2025-01-01 hasta 2025-12-31. No se excluyen filas adicionales en este cálculo. El grano del resultado es una fila por centro para el período 2025.

## Definiciones y supuestos

El bruto conserva todo el crecimiento registrado. El neto estimado descuenta la biomasa perdida por mortalidad del mismo conjunto de observaciones.

| Supuesto | Motivo | Efecto si fuera falso | Registro |
| --- | --- | --- | --- |
| `crecimiento_kg` representa ganancia bruta antes de descontar mortalidad | Permite evaluar el denominador conservando el crecimiento o descontando las pérdidas | Si el campo ya fuera neto, descontar de nuevo la mortalidad duplicaría el ajuste y la definición debe revisarse | Implementación del FCR · 13-10-2026 |
| Los peces muertos tienen el peso promedio estimado de su jaula y lote en ese día | La fuente tiene número de muertos, biomasa y población, pero no el peso de los peces muertos | Peces muertos más livianos reducen la pérdida estimada y el FCR neto, peces muertos más pesados lo aumentan | Implementación del FCR · 13-10-2026 |

`biomasa_kg / poblacion` se utiliza como peso promedio estimado en kg por pez. Por eso la biomasa muerta y el FCR neto se identifican como estimados. Se emplea toda la mortalidad registrada en las observaciones conservadas, sin atribuirla a un evento sanitario.

El crecimiento neto estimado debe ser mayor que cero. Si no lo es, el script informa el centro y detiene el cálculo, en vez de producir un FCR sin interpretación válida.

## Resultados reproducidos

| Centro | FCR bruto (kg/kg) | FCR neto estimado (kg/kg) | Diferencia (kg/kg) | Cambio respecto del bruto |
| --- | ---: | ---: | ---: | ---: |
| Centro Reloncaví | 1,258 | 1,371 | 0,113 | 8,97 % |
| Centro Calbuco | 1,291 | 1,396 | 0,105 | 8,13 % |
| Centro Quellón | 1,236 | 1,344 | 0,107 | 8,67 % |
| Centro Melinka | 1,251 | 1,355 | 0,104 | 8,35 % |
| Centro Cisnes | 1,225 | 1,331 | 0,106 | 8,64 % |
| Centro Puyuhuapi | 1,254 | 1,354 | 0,100 | 7,94 % |
| Centro Skyring | 1,551 | 2,004 | 0,453 | 29,23 % |

El FCR neto estimado es mayor porque utiliza el mismo alimento y un denominador menor después de descontar las pérdidas. La diferencia cuantifica el efecto de cambiar la definición del denominador, no una diferencia en el alimento suministrado.

Skyring tiene el FCR más alto bajo ambas definiciones. Su cambio porcentual también es el mayor: descontar la biomasa muerta estimada modifica más su denominador. Esto describe el efecto de la mortalidad registrada en el cálculo, sin demostrar por sí solo qué parte corresponde a un evento sanitario.

## Cómo ejecutar

Colocar `metrics_fcr.py` junto a `main.py` y ejecutar:

```powershell
py main.py
py metrics_fcr.py
```

La salida es `output_persona3/fcr_por_centro.csv`. Incluye los totales usados, el crecimiento neto y la biomasa muerta estimados, ambos FCR, la diferencia absoluta y el cambio porcentual.

Los resultados describen las observaciones conservadas por la limpieza. Los valores de la tabla se muestran redondeados, mientras que el CSV conserva la precisión del cálculo.
