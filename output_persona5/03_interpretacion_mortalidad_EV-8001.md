# Mortalidad diaria y evento sanitario: Centro Skyring

**Pregunta:** ¿Cómo se comporta la mortalidad registrada en las jaulas afectadas antes, durante y después del intervalo sanitario declarado?

**Origen:** observado en la operación limpia; fechas y jaulas del evento tomadas de la fuente sanitaria.

## Lectura de la figura

La línea superior suma mortalidad_n por fecha en las jaulas 37, 38, 39, 40 de Centro Skyring. Se mantiene ese mismo conjunto de jaulas durante todo 2025. El sombreado identifica EV-8001 (Caligus), desde 2025-08-01 hasta 2025-10-15, ambos días incluidos.

Durante ese intervalo se registran 45,862 muertes en las jaulas seleccionadas. Es una cantidad observada durante el evento, no una estimación de muertes causadas por él. En 61 de 76 días hay datos de las 4 jaulas seleccionadas.

El panel inferior muestra la cantidad de jaulas con observaciones conservadas cada día. Con menos jaulas, la suma de mortalidad es parcial; una caída puede reflejar menor disponibilidad de información. Un día sin registros queda vacío en la mortalidad, no se transforma en cero.

## Qué permite concluir

La figura permite identificar coincidencia temporal entre la evolución de la mortalidad registrada y el intervalo sanitario declarado. La explicación del exceso requiere una referencia basal y considerar cambios de población y disponibilidad de observaciones.

## Alcance y límites

- Una fila del CSV generado representa un día, un centro y el conjunto de jaulas del evento seleccionado.
- Se utilizan las operaciones limpias de las jaulas seleccionadas; no se imputa mortalidad ni se corrigen las fechas del evento.
- Mortalidad_n mide peces muertos, no kg de biomasa ni una tasa sobre la población.
- La misma cantidad de jaulas con datos no garantiza la misma población expuesta.
- Tener menos jaulas con datos no permite distinguir, con esta figura sola, entre días ausentes, filas excluidas por limpieza o jaulas sin registros operacionales.
- No se determina aquí mortalidad atribuible, costo/kg ni impacto económico.

## Reproducción

Después de generar las salidas de las personas 1 y 2, ejecutar:

```bash
python3 graficos_mortalidad.py --evento EV-8001
```

Fuentes: origen_acuicultura.sqlite (tabla operacion_limpia de output_persona1/datos_sqlite_limpios.sqlite) y origen_eventos_sanitarios.json (fechas y jaulas de output_persona2/eventos_limpios.csv). Los totales se recalculan desde la base SQLite actual, no se reutilizan los totales de mortalidad del CSV de eventos.

Uso de IA: ChatGPT ayudó a preparar y revisar la visualización y esta explicación.
