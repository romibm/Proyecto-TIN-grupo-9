# AquaFiordo · Entrega 2 · Persona 3, componente D (prototipo probado)

El prototipo es la capa de consumo sobre el modelo analítico. No agrega tablas ni
redefine indicadores: lee las salidas que produce `python main.py`
(`output_modelo/componentes_costos.csv` y `output_costo/costo_mortalidad.xlsx`) y
las presenta en una sola pantalla para apoyar una decisión. Por eso el número de
la pantalla es el mismo del informe, y al correr la cadena el tablero se regenera.

## Pregunta y decisión

¿Qué centro concentra el sobrecosto de alimento del año y de dónde viene? La
decisión que habilita es dónde priorizar el control sanitario y de alimentación
para reducir ese sobrecosto.

## Anatomía de la pantalla

Una pregunta, una pantalla, una decisión: título con la pregunta y selectores de
período, centro, definición del FCR y referencia basal; cifra principal con
comparación y cobertura; reparto del sobrecosto que suma; gráfico que explica la
cifra con el centro crítico destacado; corte por centro y detalle en tabla
trazable; y pie con fuente, última actualización y dueño, con el respaldo del
dólar a la vista.

## La cifra y su lectura

Centro Skyring concentra el sobrecosto. Su costo de alimento es $1.742/kg frente a
$1.411/kg del resto (+23,5%). El sobrecosto anual atribuido al centro es la unión
de dos causas, descontando lo que se cuenta en ambas:

- **A · $408,2 MM** por peor FCR.
- **B · $198,9 MM** por el alimento invertido en los peces muertos del evento
  sanitario EV-8001 (Caligus).
- **− $38,3 MM** de traslape (alimento contado en A y en B).
- **= $568,8 MM** de unión A∪B, el total atribuido al centro.

El tablero permite elegir entre las dos referencias basales del modelo (lote sin
evento y lote previo al evento); el exceso de mortalidad y el componente B cambian
levemente según cuál se use. Con la definición de FCR neto estimado, el costo por
kg del centro sube a $2.251/kg.

## Definición seleccionable (vínculo con el componente C)

El denominador del FCR (bruto o neto estimado) es un selector del tablero: la
definición alternativa de la E1 vive dentro del prototipo, no en un anexo. Las
cifras salen del modelo unificado de la cadena, de modo que la pantalla y el
informe no mantienen cálculos independientes.

## Actualización y trazabilidad

`tablero/generar_tablero.py` construye el tablero desde las salidas de la cadena,
sin datos pegados a mano, y está incorporado a `main.py` como última etapa. La
última actualización se toma del archivo de origen más reciente, no del reloj.

## Adopción

- **Audiencia:** Jefatura de Producción / Gerencia de Operaciones.
- **Frecuencia:** mensual, al cierre de cada mes.
- **Decisión:** dónde priorizar el control sanitario y de alimentación.

## Prueba de uso

Se probó con dos personas que no lo construyeron, que respondieron tres preguntas
del caso sin ayuda, midiendo tiempo y dificultad.

- Persona 1: _[rol]_ — respondió _[n/3]_ en _[tiempo]_; dudó en _[__]_.
- Persona 2: _[rol]_ — respondió _[n/3]_ en _[tiempo]_; dudó en _[__]_.
- Cambios aplicados tras la prueba: _[__]_.

## Entorno y copia local

Se entrega como HTML autocontenido (`tablero/tablero.html`), que abre en cualquier
navegador sin instalar nada, y sirve como copia local para la presentación. Existe
además una versión en Streamlit (`tablero/tablero_app.py`) que reusa la misma
lógica de datos.

## Límites

El costo considera solo alimento. El exceso de mortalidad describe la brecha contra
la referencia basal y no prueba por sí solo la causa del evento. La cobertura de
precios es de 33 de 36 combinaciones tipo-mes (91,7%); los meses sin precio no se
imputan.
