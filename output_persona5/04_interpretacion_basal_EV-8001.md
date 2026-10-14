# Mortalidad observada frente a basal — EV-8001

**Pregunta:** ¿Cuántas muertes se observaron en las jaulas del evento frente a las esperadas bajo la referencia basal?

## Interpretación

En Centro Skyring, durante EV-8001 (Caligus), se observaron 45.862 muertes en las jaulas 37, 38, 39, 40, entre 2025-08-01 y 2025-10-15, ambos días incluidos. Aplicando la basal del equipo a las mismas observaciones se esperan 6.740,5 muertes. El exceso estimado es 39.121,5 peces.

El observado es un conteo de registros conservados. El esperado y el exceso dependen de la referencia escogida. No se demuestra que todas las muertes del exceso fueran causadas por el evento.

## Fórmulas de persona 4

- Tasa basal por lote = suma de mortalidad_n / suma de poblacion en observaciones sin evento sanitario registrado.
- Muertes esperadas durante el evento = suma de tasa_basal_del_lote × poblacion de cada observación del evento.
- Exceso = muertes observadas - muertes esperadas.

La suma de población corresponde a exposición acumulada entre observaciones diarias, no a peces únicos. La tasa basal se aplica por lote; no se promedian tasas diarias con el mismo peso.

## Alcance y límites

Una fila de la tabla utilizada es un evento sanitario y sus observaciones de jaulas afectadas. El contraste utiliza las observaciones disponibles en la base limpia. No se imputa mortalidad para días o jaulas sin registros. Las filas excluidas por limpieza pueden cambiar los resultados.

Se supone que la tasa de los días sin evento representa la mortalidad esperable para ese lote durante el intervalo. La referencia incluye días previos y posteriores, por lo que describe una comparación retrospectiva. La ausencia de un evento registrado no garantiza ausencia de enfermedad.

El gráfico contiene dos cantidades comparables; el exceso se informa como su diferencia y no como una tercera cantidad que deba sumarse. El Excel conserva la tabla de eventos con un decimal y el CSV copia esa precisión.

## Reproducción

Con las salidas de limpieza disponibles:

```bash
python costo_mortalidad.py
python graficos_basal.py --evento EV-8001
```

Entrada: output_costo/costo_mortalidad.xlsx, hoja eventos. Fechas y jaulas: output_persona2/eventos_limpios.csv. Salidas: output_persona5/04_mortalidad_vs_basal_EV-8001.png, 04_datos_basal_EV-8001.csv y 04_interpretacion_basal_EV-8001.md.

Uso de IA: ChatGPT ayudó a preparar y revisar la visualización y su interpretación.
