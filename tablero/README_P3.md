# Prototipo E2 — Persona 3 (tablero)

Tablero de una pantalla que responde la pregunta de negocio del caso salmonera
AquaFiordo: **qué centro concentra el sobrecosto de alimento y de dónde viene.**
Toda la parte del prototipo vive en esta carpeta `tablero/`.

## Archivos

- `generar_tablero.py` — genera el tablero desde las salidas de la cadena.
- `tablero.html` — el tablero (archivo autocontenido, doble clic).
- `tablero_app.py` + `requirements_tablero.txt` — misma pantalla en Streamlit.
- `CHECKLIST_CLASE7.md` — verificación de la anatomía (6 líneas).
- `PRUEBA_DE_USO.md` — protocolo y planilla de la prueba con 2 personas ajenas.
- `INFORME_seccion_prototipo.md` — sección del prototipo para el Google Doc.

## De dónde salen los números (modelo nuevo del equipo)

El tablero no tiene datos pegados a mano. `generar_tablero.py` lee:

- `output_modelo/componentes_costos.csv` → **reparto del sobrecosto por causa**
  (A por peor FCR, B por peces muertos del evento, traslape y unión A∪B), con una
  fila por **referencia basal**.
- `output_costo/costo_mortalidad.xlsx`, hoja `por_centro` → costo/kg y FCR por centro.
- `output_persona2/precios_limpios.csv` → cobertura de precios.

Son las mismas salidas que alimentan el informe, por eso el número de la pantalla
es el del informe. Está enganchado a `main.py` (corre al final de la cadena):

```powershell
py main.py
```

O solo el tablero, si las salidas ya existen:

```powershell
py tablero/generar_tablero.py
```

## Selectores

- **Definición del FCR:** bruto o neto estimado (cambia costo/kg, gráfico y FCR).
- **Centro:** cualquiera de los 7.
- **Referencia basal:** las dos basales del modelo (`lote sin evento` /
  `lote previa al evento`); cambia el exceso y el reparto del sobrecosto.

## Cómo abrirlo (y la copia local para el viernes 20)

Doble clic en `tablero/tablero.html`. Abre en cualquier navegador, sin instalar
nada ni internet. Ese archivo **es la copia local** para la sala.

## Audiencia, frecuencia y decisión (adopción)

- **Audiencia:** Jefatura de Producción / Gerencia de Operaciones.
- **Frecuencia:** mensual, al cierre de cada mes.
- **Decisión:** dónde priorizar el control sanitario y de alimentación.

## Dos formas de ver el mismo tablero

### A) HTML (recomendado para la sala)

`tablero/tablero.html` — doble clic, offline, sin servidor.

### B) Streamlit (tablero "BI", no-HTML)

Reusa la misma lógica de datos. Desde la raíz del repo:

```powershell
py -m pip install -r tablero/requirements_tablero.txt
py -m streamlit run tablero/tablero_app.py
```

#### Cómo funciona Streamlit (no genera un archivo)

- `streamlit run` **levanta un servidor local** y abre una pestaña en el navegador
  (en `localhost:8501`).
- La página queda **"viva"**: cada vez que mueves un selector, vuelve a correr el
  Python y se actualiza al momento.
- Mientras la terminal esté corriendo, el tablero funciona; se cierra con **Ctrl+C**.
- **No queda ningún archivo** para abrir después: hay que tener el servidor
  corriendo. Por eso, para la sala, el `tablero.html` es más práctico de llevar.
