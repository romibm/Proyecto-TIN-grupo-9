# Comparación del FCR bruto y neto estimado

**Pregunta:** ¿Cómo cambia el FCR por centro al descontar la biomasa muerta estimada?

**Origen del hallazgo:** medido en los resultados del cálculo, condicionado por los supuestos de la ficha FCR.

## Interpretación

Centro Skyring presenta el mayor FCR bajo ambas definiciones. En Centro Skyring, pasa de 1,551 a 2,004 kg/kg, un aumento de 29,23% respecto del bruto. En los otros centros, el aumento va de 7,94% a 8,97%.

El cambio corresponde a dos definiciones aplicadas a las mismas observaciones. No es un empeoramiento entre dos fechas. El alimento total se mantiene y el denominador se reduce al descontar la biomasa muerta estimada.

## Definición y alcance

- FCR bruto: suma de alimento / suma de crecimiento, interpretando crecimiento_kg como bruto.
- FCR neto estimado: suma de alimento / (suma de crecimiento - biomasa muerta estimada).
- Biomasa muerta estimada: suma de mortalidad_n × biomasa_kg / poblacion, calculada por observación.
- Una fila de la tabla de resultados es un centro para las observaciones conservadas de 2025.
- La figura muestra todos los centros del CSV, sin seleccionar solo el centro con mayor FCR.

## Límites

La estimación supone que crecimiento_kg es bruto y que los peces muertos tenían el peso promedio registrado en su jaula y lote. Si el crecimiento ya fuera neto, descontar mortalidad nuevamente duplicaría el ajuste. Este gráfico usa toda la mortalidad registrada: no determina qué parte corresponde a un evento sanitario ni identifica el centro con mayor costo/kg.

## Reproducción

Ejecutar desde la carpeta del repositorio:

```bash
python3 main.py
python3 metricas_fcr.py
python3 graficos_fcr.py
```

Fuente: origen_acuicultura.sqlite; tablas operacion_limpia y centros; cálculo de metricas_fcr.py. Entrada de la figura: output_persona3/fcr_por_centro.csv. La copia de los datos usados queda en output_persona5/02_datos_fcr.csv.

Uso de IA: se utilizó ChatGPT para preparar y revisar el script de visualización y el texto de interpretación.
