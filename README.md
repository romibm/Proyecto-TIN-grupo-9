# AquaFiordo — reproducción del código

Este README explica cómo ejecutar `main.py` desde cero y verificar las salidas. Cubre lo solicitado en el componente B del enunciado, página 2: instalación, comando de ejecución, duración y resultado esperado. Los supuestos y decisiones están en `SUPUESTOS.md`.

## Qué hace el programa

Integra las cuatro fuentes del caso: SQLite de acuicultura, CSV de precios de alimento, JSON de eventos sanitarios y API del dólar observado de mindicador. Aplica los criterios de calidad acordados, conserva trazabilidad y produce una base SQLite y archivos CSV con los resultados.

La comparación principal entre centros usa **costo estimado de alimento en CLP por kg de crecimiento reportado**. Las salidas incluyen también gasto acumulado de alimento, FCR principal, FCR alternativo, diferencias entre ambos, mortalidad basal y exceso durante eventos sanitarios. El detalle de estas definiciones está en `SUPUESTOS.md`.

## 1. Requisitos e instalación

- Python 3.10 o superior, la reproducción documentada se verificó con Python 3.12.14.
- No se necesitan paquetes externos ni ejecutar `pip install`, el programa utiliza la biblioteca estándar de Python.
- Acceso a internet si se necesita descargar el dólar por primera vez o actualizarlo.
- Los archivos de entrada en la carpeta `archivos`, junto a `main.py`.

En Windows, comprobar Python desde PowerShell:

```powershell
py --version
```

Si Python no está instalado, instalarlo y volver a abrir la terminal. VS Code puede usarse como editor, pero no es necesario para ejecutar el programa.

## 2. Preparar los archivos

La carpeta del proyecto debe contener estos archivos con los nombres indicados:

| Ruta relativa a la carpeta del proyecto | Uso |
| --- | --- |
| `main.py` | Programa que se ejecuta |
| `README.md` | Instrucciones de reproducción |
| `SUPUESTOS.md` | Bitácora de supuestos y decisiones |
| `archivos/origen_acuicultura.sqlite` | Base original de operaciones y catálogos |
| `archivos/origen_costos_alimento.csv` | Precios originales de alimento |
| `archivos/origen_eventos_sanitarios.json` | Eventos sanitarios originales |
| `archivos/dolar_2025.json` | Respuesta conservada de la API, necesaria para reproducir exactamente la ejecución documentada sin internet |
| `archivos/dolar_2025_metadata.json` | Datos de la consulta de dólar, cuando fueron generados |

Si la base descargada se llama `origen_acuicultura(1).sqlite`, renombrarla a `origen_acuicultura.sqlite`. No cambiar el contenido de las fuentes. El CSV se lee con separador punto y coma y codificación `cp1252`.

La carpeta `output` se crea automáticamente. No se necesitan salidas previas para ejecutar el programa.

## 3. Ejecutar en Windows

Abrir PowerShell en la carpeta donde está `main.py`. Si es necesario, entrar primero a esa carpeta, reemplazando la ruta del ejemplo por la propia:

```powershell
cd "C:\ruta"
```

Ejecutar:

```powershell
py main.py
```

Ese es el único comando necesario para procesar los datos y generar las salidas. El programa busca la carpeta `archivos` junto al archivo `main.py` y guarda los resultados en `output` junto al mismo archivo.

En Linux o macOS, desde la carpeta del proyecto:

```bash
python3 main.py
```

## 4. Cómo se usa la API y cómo reproducir la misma ejecución

La fuente del dólar es `https://mindicador.cl/api/dolar/2025`.

Si existe `archivos/dolar_2025.json`, el programa reutiliza esa respuesta conservada. Esto permite reproducir los resultados sin conexión y mantener exactamente las mismas cotizaciones. El archivo se valida antes de usarlo: debe contener la serie del dólar de 2025, con fechas únicas y valores positivos.

Si ese archivo no existe, `py main.py` consulta la API y guarda tanto `dolar_2025.json` como `dolar_2025_metadata.json`. La descarga requiere conexión a internet. Reutilizar después la respuesta guardada sigue incorporando la cuarta fuente, la API, con la versión conservada de sus datos.

Para consultar nuevamente la API y reemplazar la respuesta guardada:

```powershell
py main.py --actualizar-dolar
```

Para reproducir las cifras del informe, conservar en el repositorio las tres fuentes originales, la respuesta del dólar utilizada y su archivo de metadatos si está disponible. Una actualización de la API puede cambiar la serie y requiere volver a generar las cifras. `output/ejecucion.json` registra si se consultó la API o se reutilizó la respuesta y los hashes SHA-256 de los archivos de entrada.

## 5. Cuánto demora

La ejecución completa con la respuesta del dólar ya guardada demora aproximadamente **1 a 3 segundos en el entorno de verificación**. En otro equipo puede tardar más. La primera consulta o una actualización de la API añade el tiempo de red; la petición tiene un límite de espera de 30 segundos.

La duración medida por el programa se registra en `output/ejecucion.json`, campo `duracion_segundos`.

## 6. Qué se espera ver al terminar

Con las mismas fuentes y respuesta de dólar utilizadas para esta versión, la consola debe mostrar:

```text
OK: 13,158 filas integradas; 4 eventos sanitarios válidos; 248 observaciones de dólar.
Salidas: <ruta de tu proyecto>\output
operacion_diaria: 1251/14409 excluidos (8.68%).
costos_alimento: 2/36 excluidos (5.56%).
eventos_sanitarios: 4/8 excluidos (50.00%).
dolar_api: 0/248 excluidos (0.00%).
cosechas: 6/48 excluidos (12.50%).
Resultados sujetos a los supuestos registrados en config_utilizada.json y ejecucion.json
```

Las comas de la primera línea separan miles: `13,158` significa 13.158 filas.

La cobertura se calcula por fuente y sin contar dos veces una fila con varios motivos de exclusión:

| Fuente | Filas de entrada | Filas excluidas | Filas conservadas | Porcentaje excluido |
| --- | ---: | ---: | ---: | ---: |
| Operación diaria | 14.409 | 1.251 | 13.158 | 8,68 % |
| Precios de alimento | 36 | 2 | 34 | 5,56 % |
| Eventos sanitarios | 8 | 4 | 4 | 50,00 % |
| Dólar observado | 248 | 0 | 248 | 0,00 % |
| Cosechas | 48 | 6 | 42 | 12,50 % |

Estos porcentajes corresponden a cada fuente; no deben sumarse. Los precios preparados tienen 36 combinaciones de mes y alimento porque se completan precios ausentes para el año. Eso no contradice las 34 filas originales de precios conservadas, una de las cuales contiene un precio sin dato que se estima.

Los motivos de exclusión son registros fuera del período, duplicados, relaciones alimento sobre crecimiento consideradas ruido, balances de población incompatibles, diferencias entre mes y fecha, referencias inexistentes y filas que no son datos en el CSV. `incidencias_calidad.csv` permite ver el motivo correspondiente a cada fila; `SUPUESTOS.md` explica los criterios y sus límites.

## 7. Archivos generados

Todos se guardan en `output`:

| Archivo | Contenido y uso |
| --- | --- |
| `datos_integrados.sqlite` | Base con operación integrada, catálogos, cosechas, precios, dólar, eventos sanitarios, puente de exposición, resúmenes, cobertura e incidencias |
| `operacion_integrada.csv` | Datos diarios conservados con costos, cotización utilizada, exposición a eventos sanitarios y estimación de biomasa perdida |
| `precios_alimento.csv` | Precios observados y estimados por alimento y mes, con método de estimación |
| `mezcla_mensual.csv` | Precio de la mezcla asumida y escenarios mínimo y máximo por mes |
| `basal_por_lote.csv` | Tasa basal de cada lote calculada con días sin eventos sanitarios |
| `resumen_eventos_sanitarios.csv` | Mortalidad observada durante cada evento sanitario, esperada según basal, exceso estimado y cifra declarada en el JSON |
| `resumen_centros.csv` | Resultados por centro y ranking de costo estimado de alimento por kg |
| `resumen_centro_mes.csv` | Los mismos indicadores agregados por centro y mes |
| `cobertura.csv` | Cantidad y porcentaje de exclusiones por fuente |
| `incidencias_calidad.csv` | Fuente, fila original, motivo, acción y detalle de cada incidencia |
| `config_utilizada.json` | Parámetros efectivamente utilizados |
| `verificacion_crecimiento.json` | Evidencia del contraste de biomasa usado para interpretar el crecimiento reportado |
| `ejecucion.json` | Duración, origen y modo de uso del dólar, hashes de entrada y cantidad de filas por tabla |

Para comparar ambas definiciones, abrir `resumen_centros.csv` o `resumen_centro_mes.csv` y revisar `fcr_principal`, `fcr_alternativo`, `diferencia_fcr` y `variacion_fcr_porcentaje`. Los costos por kg bajo ambos denominadores también están disponibles.

Para revisar el análisis sanitario, usar `basal_por_lote.csv` y `resumen_eventos_sanitarios.csv`. Las muertes observadas durante el evento sanitario no equivalen automáticamente a muertes causadas por él. El exceso sobre la basal es una estimación condicionada a los supuestos documentados.

## 8. Verificaciones automáticas y reproducción

Antes de escribir las salidas, el código verifica:

- Una sola fila por fecha, centro, jaula y lote.
- Vínculos únicos entre operación y evento sanitario, con identificadores válidos de evento sanitario.
- Conciliación de alimento, crecimiento, mortalidad y costo entre las filas diarias y el resumen por centro.
- Conciliación de filas de entrada, conservadas y excluidas por fuente.
- Costos de la mezcla dentro de los escenarios de precio mínimo y máximo.

La versión entregada se probó en una carpeta nueva, con `main.py` y los archivos de entrada, sin usar salidas previas ni instalar dependencias. Dos ejecuciones consecutivas produjeron los mismos archivos CSV. También se verificaron el cierre de SQLite antes de reemplazar el archivo, las reglas de exclusión acordadas, ambos FCR y la mortalidad observada durante los eventos sanitarios.

Repetir `py main.py` reemplaza las salidas generadas. Si las entradas y la configuración no cambian, las cifras y los CSV se mantienen. La duración de ejecución puede variar, por lo que no se espera que `ejecucion.json` sea idéntico byte a byte.

## 9. Opciones de ejecución

No son necesarias para la ejecución habitual:

```powershell
py main.py --datos "C:\ruta\archivos" --salida "C:\ruta\resultados"
py main.py --config "config_personalizada.json"
py main.py --help
```

`--config` recibe una configuración completa, no un archivo con solo los campos que quieras cambiar. Para preparar una, copiar `output/config_utilizada.json` después de la primera ejecución. Cambiar los parámetros puede cambiar los resultados; algunas definiciones solo admiten la opción implementada y el programa rechaza otras.

## 10. Problemas frecuentes

| Mensaje o problema | Qué revisar |
| --- | --- |
| `py` no se reconoce | Confirmar que Python esté instalado y volver a abrir la terminal, si el ejecutable está disponible como `python`, usar `python main.py` |
| No se encuentra `main.py` | Abrir la terminal en la carpeta que contiene el programa |
| No se encuentra una fuente o SQLite no puede abrirse | Revisar la carpeta `archivos`, los nombres exactos y los permisos de lectura |
| Error de conexión al consultar mindicador | Revisar internet, para reproducir sin conexión usar la respuesta de dólar conservada con las demás fuentes |
| `WinError 32` o archivo utilizado por otro proceso | Cerrar programas que tengan abiertos `output/datos_integrados.sqlite` o su archivo temporal y volver a ejecutar |
| Las cifras no coinciden con las esperadas | Revisar que se usen las mismas fuentes, la misma respuesta del dólar y la configuración documentada, comparar los hashes en `ejecucion.json` |

El programa utiliza una base temporal y cierra la conexión antes de reemplazar la salida para evitar el bloqueo de SQLite observado en Windows. Otro programa que tenga el archivo abierto aún puede impedir el reemplazo.

## Uso en la entrega

El enunciado solicita un **repositorio con el código y este README**, cuyo enlace debe ir en la portada del informe, página 3. La bitácora de `SUPUESTOS.md` se incorpora a los anexos. La cobertura debe aparecer cuantificada en el informe y las dos definiciones de la métrica deben compararse e interpretarse.

Estos archivos documentan la ejecución y los criterios. El grupo debe incorporar además su mandato, modelo dimensional, ficha de métrica, visualizaciones, recomendación, acta y declaración de IA en el informe según el enunciado.

**Uso de IA:** se utilizó ChatGPT, con Codex, para apoyar la construcción y revisión del código y redactar esta documentación, con decisiones revisadas por Romina.
