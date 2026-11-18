"""Tablero de la Entrega 2 (prototipo, Persona 3) en Streamlit.

Misma pantalla y datos que tablero/tablero.html, pero servido por Streamlit.
Reusa construir_datos() de generar_tablero.py (mismo origen que el informe), por
lo que el numero se mantiene y se actualiza al volver a correr la cadena.

Correr desde la raiz del repo:
    py -m pip install -r tablero/requirements_tablero.txt
    py -m streamlit run tablero/tablero_app.py
"""

import altair as alt
import pandas as pd
import streamlit as st

from generar_tablero import construir_datos


def clp(x):
    return f"{x:,.0f}".replace(",", ".")


def mm(x):
    s = f"{abs(x) / 1e6:,.1f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return ("-$ " if x < 0 else "$ ") + s + " MM"


def pct1(x):
    return f"{x:.1f}".replace(".", ",")


st.set_page_config(page_title="AquaFiordo - Sobrecosto por centro", layout="wide")

datos = construir_datos()
meta, critico, resto = datos["meta"], datos["critico"], datos["resto"]
centros, basales, ev = datos["centros"], datos["basales"], datos["evento"]


def costo_kg(c, modo):
    return c["costo_kg_bruto"] if modo == "bruto" else c["costo_kg_neto"]


def fcr(c, modo):
    return c["fcr_bruto"] if modo == "bruto" else c["fcr_neto"]


st.markdown("**AQUAFIORDO · CASO SALMONERA · GRUPO 9**")
st.title("¿Qué centro concentra el sobrecosto de alimento este año, y de dónde viene?")

c1, c2, c3, c4 = st.columns([1.3, 1.2, 1.4, 0.8])
with c1:
    modo_lbl = st.radio("Definición del denominador", ["FCR bruto", "FCR neto estimado"], horizontal=True)
    modo = "bruto" if modo_lbl == "FCR bruto" else "neto"
with c2:
    nombres = [c["nombre"] for c in sorted(centros, key=lambda x: x["costo_kg_bruto"], reverse=True)]
    centro_sel = st.selectbox("Centro", nombres, index=nombres.index(critico["nombre"]))
with c3:
    basal_nom = st.selectbox("Referencia basal", [b["nombre"] for b in basales])
with c4:
    st.metric("Período", meta["periodo"])

centro = next(c for c in centros if c["nombre"] == centro_sel)
basal = next(b for b in basales if b["nombre"] == basal_nom)

k1, k2 = st.columns(2)
with k1:
    ck, cr = costo_kg(centro, modo), costo_kg(resto, modo)
    st.subheader(f"Costo de alimento del centro · {modo_lbl.lower()}")
    st.metric(label=f"{centro['nombre']} (CLP/kg)", value=clp(ck),
              delta=f"+{pct1(100*(ck/cr-1))}% vs. resto ({clp(cr)} CLP/kg)", delta_color="inverse")
    cob = meta["cobertura"]
    nota = (f" · precio válido en {cob['validas']}/{cob['total']} combinaciones tipo-mes "
            f"({pct1(cob['pct'])}%)") if cob else ""
    st.caption(f"Cobertura: 7/7 centros, {meta['periodo'].lower()}{nota}")

with k2:
    st.subheader("Sobrecosto anual del centro crítico · reparto por causa")
    st.metric(label=f"Unión A∪B · total atribuido a {critico['nombre']}", value=f"{mm(basal['union'])} / año")
    st.markdown(
        f"- **A · Sobrecosto por peor FCR:** {mm(basal['A'])}\n"
        f"- **B · Alimento en peces muertos del evento {ev['id']}:** {mm(basal['B'])}\n"
        f"- **− Traslape (alimento contado en A y en B):** −{mm(basal['traslape'])}\n"
        f"- **= Unión A∪B:** {mm(basal['union'])}"
    )

st.subheader(f"Costo de alimento por kg y centro ({modo_lbl.lower()})")
df = pd.DataFrame([{
    "Centro": c["nombre"], "Costo_kg": round(costo_kg(c, modo)),
    "Grupo": "Centro crítico" if c["id"] == critico["id"] else "Otros centros",
} for c in centros]).sort_values("Costo_kg", ascending=False)
barras = alt.Chart(df).mark_bar().encode(
    x=alt.X("Costo_kg:Q", title="CLP por kg de crecimiento"),
    y=alt.Y("Centro:N", sort="-x", title=None),
    color=alt.Color("Grupo:N", scale=alt.Scale(domain=["Centro crítico", "Otros centros"],
                    range=["#9a3324", "#c9d2cc"]), legend=alt.Legend(title=None, orient="bottom")),
    tooltip=["Centro", "Costo_kg"])
regla = alt.Chart(pd.DataFrame({"resto": [round(costo_kg(resto, modo))]})).mark_rule(
    strokeDash=[4, 4], color="#14181f").encode(x="resto:Q")
st.altair_chart(barras + regla, use_container_width=True)
st.caption(f"Línea punteada: resto de centros ({clp(costo_kg(resto, modo))} CLP/kg). "
           f"Barra destacada: {critico['nombre']}.")

st.subheader("Detalle por centro")
tabla = pd.DataFrame([{
    "Centro": c["nombre"], "Zona": c["zona"], "Costo/kg (CLP)": round(costo_kg(c, modo)),
    f"FCR {modo}": round(fcr(c, modo), 3), "Mortalidad diaria (%)": round(c["mort_pct"], 3),
    "Exceso muertes (evento)": round(c["exceso_n"]),
} for c in sorted(centros, key=lambda x: costo_kg(x, modo), reverse=True)])
st.dataframe(tabla, use_container_width=True, hide_index=True)

st.caption(
    f"Evento {ev['id']} ({ev['tipo']}) en {ev['centro']}, {basal['nombre'].lower()}: "
    f"{clp(basal['obs'])} muertes observadas vs {clp(basal['esperado'])} esperadas → exceso estimado "
    f"{clp(basal['exceso_n'])} peces. El exceso describe la brecha contra la referencia basal; "
    f"no prueba por sí solo causalidad."
)

st.info(f"**Audiencia:** {meta['dueno']}.  **Frecuencia:** mensual, al cierre de cada mes.  "
        f"**Decide:** dónde priorizar el control sanitario y de alimentación para reducir el sobrecosto.")

st.divider()
st.caption(
    f"**Fuente:** {meta['fuente']}  \n"
    f"**Última actualización de datos:** {meta['actualizado']}  ·  **Dueño:** {meta['dueno']}  \n"
    f"**Respaldo:** dólar desde API mindicador.cl; si no responde se usa la respuesta guardada fechada.  ·  "
    f"Tablero generado por la cadena, sin datos pegados a mano."
)
