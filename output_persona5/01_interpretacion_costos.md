# Costo estimado de alimento por centro

**Pregunta:** ¿Qué centro tiene mayor costo de alimento por kg de crecimiento bruto?

**Origen del hallazgo:** medido bajo las reglas de valorización del alimento adoptadas por el equipo.

## Interpretación

Centro Skyring tiene el mayor costo estimado de alimento por kg de crecimiento bruto: $1.741,83/kg. El resto agrupado presenta $1.410,71/kg. La brecha es $331,12/kg, equivalente a 23,47% sobre la referencia.

La referencia agrupa costo y crecimiento del resto de los centros antes de dividir. No es el promedio simple de sus costos/kg. La figura utiliza crecimiento bruto, que es la definición usada por costo_mortalidad.py para seleccionar el centro de mayor costo. La tabla de datos conserva también el costo por crecimiento neto estimado.

## Fórmula y supuestos

Costo/kg bruto = suma(alimento_kg × precio mensual de referencia) / suma(crecimiento_kg).

La operación no identifica el tipo de alimento consumido. Se usa, por tanto, un precio mensual de referencia: promedio simple de los tipos con precio válido ese mes. Los tipos faltantes no se imputan, pero su ausencia puede modificar la composición de ese promedio. Se utiliza el mismo precio mensual en todos los centros. Se interpreta crecimiento_kg como bruto, según la ficha del FCR.

## Límites

El resultado incluye únicamente alimento. No contiene todos los costos operacionales ni demuestra por sí solo la causa del mayor costo. Los importes del gráfico se muestran redondeados a pesos; porcentajes y brechas se calculan a partir de los valores disponibles en el Excel, guardados con tres decimales.

## Reproducción

Con las salidas de limpieza actualizadas, ejecutar:

```bash
python costo_mortalidad.py
python graficos_costos.py
```

Entrada: output_costo/costo_mortalidad.xlsx, hoja por_centro. Salidas: output_persona5/01_costo_alimento_por_centro.png, 01_datos_costos.csv y 01_interpretacion_costos.md.

Uso de IA: ChatGPT ayudó a preparar y revisar la visualización y su interpretación.
