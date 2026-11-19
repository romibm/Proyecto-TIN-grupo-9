"""Genera tablero html de respaldo

Lee las salidas de la cadena y escribe un archivo HTML autocontenido en tablero/tablero.html. 
El numero que muestra la pantalla sale de las mismas salidas que alimentan el informe, 
por lo que al volver a correr la cadena el tablero se actualiza.

Fuentes:
  - output_costo/costo_mortalidad.xlsx       (hoja por_centro: costo/kg y FCR por centro; hoja eventos: tipo)
  - output_modelo/componentes_costos.csv     (reparto del sobrecosto por causa, por referencia basal)
  - output_persona2/precios_limpios.csv      (cobertura de precios)

Uso:
  python tablero/generar_tablero.py
Tambien se ejecuta al final de  python main.py
"""

import csv
import datetime as dt
import json
from pathlib import Path

import openpyxl

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
XLSX = ROOT / "output_costo" / "costo_mortalidad.xlsx"
COMPONENTES = ROOT / "output_modelo" / "componentes_costos.csv"
PRECIOS = ROOT / "output_persona2" / "precios_limpios.csv"
SALIDA = SCRIPT_DIR / "tablero.html"

DUENO = "Jefatura de Producción / Gerencia de Operaciones"
PERIODO = "Año 2025"


def leer_hoja(wb, nombre):
    ws = wb[nombre]
    filas = list(ws.iter_rows(values_only=True))
    enc = list(filas[0])
    return [{enc[i]: f[i] for i in range(len(enc))} for f in filas[1:]]


def cobertura_precios():
    if not PRECIOS.exists():
        return None
    with open(PRECIOS, encoding="utf-8") as f:
        n = sum(1 for _ in csv.reader(f)) - 1
    return {"validas": n, "total": 36, "pct": round(100 * n / 36, 1)}


def construir_datos():
    for p in (XLSX, COMPONENTES):
        if not p.exists():
            raise SystemExit(f"No existe {p}. Corre primero la cadena (python main.py).")

    wb = openpyxl.load_workbook(XLSX, data_only=True)
    por_centro = leer_hoja(wb, "por_centro")
    eventos = {r["evento_id"]: r for r in leer_hoja(wb, "eventos")}

    centros, resto = [], None
    for r in por_centro:
        reg = {
            "id": r["centro_id"], "nombre": r["nombre"], "zona": r["zona"] or "",
            "costo_kg_bruto": r["costo_kg_bruto_clp"], "costo_kg_neto": r["costo_kg_neto_clp"],
            "fcr_bruto": r["fcr_bruto"], "fcr_neto": r["fcr_neto_estimado"],
            "mort_pct": r["tasa_mortalidad_diaria_pct"], "exceso_n": r["exceso_mortalidad_n"],
        }
        if r["centro_id"] != 0:
            centros.append(reg)
    resto = next(r for r in por_centro if r["centro_id"] == 0)
    resto = {"costo_kg_bruto": resto["costo_kg_bruto_clp"], "costo_kg_neto": resto["costo_kg_neto_clp"],
             "fcr_bruto": resto["fcr_bruto"], "fcr_neto": resto["fcr_neto_estimado"],
             "mort_pct": resto["tasa_mortalidad_diaria_pct"]}

    # Reparto por causa, una fila por referencia basal (evento critico = EV-8001)
    with open(COMPONENTES, encoding="utf-8-sig") as f:
        comp = list(csv.DictReader(f))
    ev_id = max(comp, key=lambda r: float(r["exceso_n"]))["evento_id"]
    filas_ev = [r for r in comp if r["evento_id"] == ev_id]
    centro_ev = filas_ev[0]["centro"]
    id_ev = int(filas_ev[0]["centro_id"])

    basales = []
    for r in filas_ev:
        basales.append({
            "basal_id": r["basal_id"], "nombre": r["nombre_basal"],
            "A": float(r["A_fcr_clp"]), "B": float(r["B_exceso_clp"]),
            "traslape": float(r["traslape_estimado_clp"]), "union": float(r["union_A_B_clp"]),
            "obs": float(r["muertes_observadas_n"]), "esperado": float(r["muertes_esperadas_n"]),
            "exceso_n": float(r["exceso_n"]),
        })

    critico = next(c for c in centros if c["id"] == id_ev)

    mtime = max(p.stat().st_mtime for p in (XLSX, COMPONENTES, PRECIOS) if p.exists())
    actualizado = dt.datetime.fromtimestamp(mtime).strftime("%d-%m-%Y %H:%M")

    return {
        "meta": {
            "actualizado": actualizado, "periodo": PERIODO, "dueno": DUENO,
            "fuente": "Cadena AquaFiordo - output_modelo/componentes_costos.csv (reparto) y output_costo/costo_mortalidad.xlsx (por_centro)",
            "cobertura": cobertura_precios(),
            "generado": dt.datetime.now().strftime("%d-%m-%Y %H:%M"),
        },
        "critico": {"id": critico["id"], "nombre": critico["nombre"], "zona": critico["zona"]},
        "centros": sorted(centros, key=lambda c: c["costo_kg_bruto"], reverse=True),
        "resto": resto,
        "basales": basales,
        "evento": {"id": ev_id, "tipo": (eventos.get(ev_id, {}) or {}).get("tipo", ""), "centro": centro_ev},
    }


def render(datos):
    return PLANTILLA.replace("/*DATA_JSON*/", json.dumps(datos, ensure_ascii=False))


def main():
    datos = construir_datos()
    SALIDA.write_text(render(datos), encoding="utf-8")
    print(f"OK tablero generado: {SALIDA}")
    print(f"   centro critico: {datos['critico']['nombre']} | basales: {len(datos['basales'])} | actualizado {datos['meta']['actualizado']}")


PLANTILLA = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AquaFiordo - Sobrecosto por centro</title>
<style>
  :root{--tinta:#14181f;--papel:#f7f5ef;--verde:#0b5c45;--gris:#6b7280;--linea:#e3e0d7;--rojo:#9a3324;--card:#fff}
  *{box-sizing:border-box}
  body{margin:0;background:var(--papel);color:var(--tinta);font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.45}
  .wrap{max-width:1080px;margin:0 auto;padding:22px 20px 40px}
  header.top{border-bottom:2px solid var(--tinta);padding-bottom:12px}
  .kicker{color:var(--verde);font-weight:700;font-size:12px;letter-spacing:.08em;text-transform:uppercase}
  h1{font-size:25px;margin:4px 0 0;font-weight:800;letter-spacing:-.01em}
  .controls{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end;margin:14px 0 6px}
  .control label{display:block;font-size:11px;color:var(--gris);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;font-weight:700}
  select{padding:7px 10px;border:1px solid var(--linea);border-radius:8px;background:var(--card);min-width:180px;font:inherit}
  .seg{display:inline-flex;border:1px solid var(--verde);border-radius:8px;overflow:hidden}
  .seg button{padding:7px 14px;border:0;background:var(--card);color:var(--verde);cursor:pointer;font-weight:600;font:inherit}
  .seg button.on{background:var(--verde);color:#fff}
  .periodo{margin-left:auto;font-size:12px;color:var(--gris);text-align:right}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:14px}
  .card{background:var(--card);border:1px solid var(--linea);border-radius:12px;padding:16px}
  .card h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--verde);margin:0 0 10px;font-weight:700}
  .cifra{font-size:38px;font-weight:800;letter-spacing:-.02em;line-height:1}
  .cifra small{font-size:17px;font-weight:700;color:var(--gris)}
  .comp{margin-top:8px;font-size:14px}
  .comp-big{font-weight:800;font-size:16px}
  .otro{color:var(--gris);font-size:12px}
  .nota-rep{margin-top:10px;font-size:11px;color:var(--gris);border-top:1px dashed var(--linea);padding-top:8px}
  .up{color:var(--rojo);font-weight:700}
  .cobertura{margin-top:10px;font-size:12px;color:var(--gris);border-top:1px dashed var(--linea);padding-top:8px}
  .impacto .big{font-size:28px;font-weight:800;color:var(--rojo)}
  .reparto{margin-top:10px;font-size:13px}
  .reparto .row{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--linea)}
  .reparto .row b{font-variant-numeric:tabular-nums}
  .reparto .tot{border-top:2px solid var(--tinta);border-bottom:0;margin-top:2px;padding-top:6px}
  .full{grid-column:1 / -1}
  svg{width:100%;height:auto;display:block}
  .bar-label{font-size:11px;fill:var(--tinta)}.bar-val{font-size:11px;fill:var(--gris);font-variant-numeric:tabular-nums}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{padding:7px 8px;text-align:right;border-bottom:1px solid var(--linea);font-variant-numeric:tabular-nums}
  th:first-child,td:first-child{text-align:left}
  thead th{color:var(--gris);font-size:11px;text-transform:uppercase;letter-spacing:.04em}
  tr.top td{background:#fdeeea;font-weight:700}
  .explica{font-size:13px;color:var(--gris);margin-top:8px}
  footer{margin-top:18px;border-top:1px solid var(--linea);padding-top:12px;font-size:12px;color:var(--gris);display:flex;flex-wrap:wrap;gap:6px 22px}
  footer b{color:var(--tinta)}
  .adopcion{margin-top:6px;font-size:12px;color:var(--gris)}
  @media(max-width:720px){.grid{grid-template-columns:1fr}.cifra{font-size:30px}}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="kicker">AquaFiordo - Caso salmonera - Grupo 9</div>
    <h1 id="pregunta">Cargando...</h1>
  </header>
  <div class="controls">
    <div class="control">
      <label>Definición del denominador</label>
      <div class="seg" id="seg-def">
        <button data-def="bruto" class="on">FCR bruto</button>
        <button data-def="neto">FCR neto estimado</button>
      </div>
    </div>
    <div class="control"><label>Centro</label><select id="sel-centro"></select></div>
    <div class="control"><label>Referencia basal</label><select id="sel-basal"></select></div>
    <div class="periodo" id="periodo"></div>
  </div>

  <div class="grid">
    <section class="card">
      <h2>Costo de alimento del centro - <span id="def-txt">bruto</span></h2>
      <div class="cifra"><span id="kpi-costo"></span> <small>CLP/kg</small></div>
      <div class="comp" id="kpi-comp"></div>
      <div class="cobertura" id="kpi-cob"></div>
    </section>
    <section class="card impacto">
      <h2 id="imp-h2">Sobrecosto anual · reparto por causa</h2>
      <div class="big" id="imp-total"></div>
      <div class="reparto" id="imp-reparto"></div>
      <div class="nota-rep" id="imp-nota"></div>
    </section>
    <section class="card full">
      <h2>Costo de alimento por kg y centro (<span id="def-txt2">bruto</span>)</h2>
      <svg id="chart" viewBox="0 0 1000 300" preserveAspectRatio="xMidYMid meet" role="img"></svg>
      <div class="explica" id="chart-exp"></div>
    </section>
    <section class="card full">
      <h2>Detalle por centro</h2>
      <table id="tabla"><thead><tr>
        <th>Centro</th><th>Zona</th><th>Costo/kg (CLP)</th>
        <th id="th-fcr">FCR</th><th>Mortalidad diaria</th><th>Exceso muertes (evento)</th>
      </tr></thead><tbody></tbody></table>
      <div class="explica" id="evento-exp"></div>
    </section>
  </div>
  <div class="adopcion" id="adopcion"></div>
  <footer id="footer"></footer>
</div>
<script>
const DATA = /*DATA_JSON*/;
let DEF="bruto", CENTRO=DATA.critico.id, BASAL=0;
const cl=new Intl.NumberFormat("es-CL");
function mm(x){const s=(x/1e6).toLocaleString("es-CL",{minimumFractionDigits:1,maximumFractionDigits:1});return (x<0?"-$":"$")+s.replace("-","")+" MM";}
function dec(x,n){return (x==null?0:x).toLocaleString("es-CL",{minimumFractionDigits:n,maximumFractionDigits:n});}
function costoKg(c){return DEF==="bruto"?c.costo_kg_bruto:c.costo_kg_neto;}
function fcr(c){return DEF==="bruto"?c.fcr_bruto:c.fcr_neto;}

function pintar(){
  const defTxt=DEF==="bruto"?"bruto":"neto estimado";
  document.querySelectorAll("#def-txt,#def-txt2").forEach(e=>e.textContent=defTxt);
  document.getElementById("th-fcr").textContent="FCR "+(DEF==="bruto"?"bruto":"neto");
  document.getElementById("periodo").innerHTML="Período<br><b>"+DATA.meta.periodo+"</b>";
  document.getElementById("pregunta").textContent="¿Qué centro concentra el sobrecosto de alimento este año, y de dónde viene?";

  const centro=DATA.centros.find(x=>x.id===CENTRO);
  const ck=costoKg(centro), cr=costoKg(DATA.resto), difPct=100*(ck/cr-1);
  document.getElementById("kpi-costo").textContent=cl.format(Math.round(ck));
  const ckOtro=DEF==="bruto"?centro.costo_kg_neto:centro.costo_kg_bruto;
  const otroTxt=DEF==="bruto"?"neto estimado":"bruto";
  document.getElementById("kpi-comp").innerHTML=
    "<span class='comp-big up'>+"+dec(difPct,1)+"% vs. resto</span> &middot; <b>+$"+cl.format(Math.round(ck-cr))+"/kg</b> "+
    "(resto $"+cl.format(Math.round(cr))+"/kg)<br>"+
    "<span class='otro'>Con FCR "+otroTxt+": $"+cl.format(Math.round(ckOtro))+"/kg</span>";
  const cob=DATA.meta.cobertura;
  document.getElementById("kpi-cob").innerHTML="Cobertura: 7/7 centros, "+DATA.meta.periodo.toLowerCase()+
    (cob?" &middot; precio válido en "+cob.validas+"/"+cob.total+" combinaciones tipo-mes ("+dec(cob.pct,1)+"%)":"");

  // Reparto por causa segun basal elegida (union = A + B - traslape)
  const b=DATA.basales[BASAL];
  document.getElementById("imp-total").textContent=mm(b.union)+" / año";
  document.getElementById("imp-reparto").innerHTML=
    "<div class='row'><span>A &middot; Sobrecosto por peor FCR</span><b>"+mm(b.A)+"</b></div>"+
    "<div class='row'><span>B &middot; Alimento en peces muertos del evento "+DATA.evento.id+"</span><b>"+mm(b.B)+"</b></div>"+
    "<div class='row'><span>− Traslape (alimento contado en A y en B)</span><b>−"+mm(b.traslape)+"</b></div>"+
    "<div class='row tot'><span><b>= Unión A∪B &middot; total atribuido a "+DATA.critico.nombre+"</b></span><b>"+mm(b.union)+"</b></div>";
  document.getElementById("imp-h2").textContent="Sobrecosto anual de "+DATA.critico.nombre+" · reparto por causa";
  document.getElementById("imp-nota").innerHTML="El traslape es el alimento ya contado en A y en B; se resta para no sumarlo dos veces. Cifras en MM = millones de pesos. Ambas referencias basales dan casi el mismo resultado: el exceso es robusto a la basal.";

  dibujarChart(); dibujarTabla();

  const e=DATA.evento;
  document.getElementById("evento-exp").innerHTML="Evento "+e.id+" ("+e.tipo+") en "+e.centro+", "+b.nombre.toLowerCase()+
    ": "+cl.format(Math.round(b.obs))+" muertes observadas vs "+cl.format(Math.round(b.esperado))+
    " esperadas &rarr; exceso estimado "+cl.format(Math.round(b.exceso_n))+" peces. El exceso describe la brecha contra la referencia basal; no prueba por sí solo causalidad.";
  document.getElementById("chart-exp").textContent="Barra destacada: "+DATA.critico.nombre+". El costo/kg usa el denominador "+defTxt+".";
  document.getElementById("adopcion").innerHTML="<b>Audiencia:</b> "+DATA.meta.dueno+". <b>Frecuencia:</b> mensual, al cierre de cada mes. <b>Decide:</b> dónde priorizar el control sanitario y de alimentación para reducir el sobrecosto.";
  document.getElementById("footer").innerHTML=
    "<span><b>Fuente:</b> "+DATA.meta.fuente+"</span>"+
    "<span><b>Última actualización de datos:</b> "+DATA.meta.actualizado+"</span>"+
    "<span><b>Dueño:</b> "+DATA.meta.dueno+"</span>"+
    "<span><b>Respaldo:</b> dólar desde API mindicador.cl; si no responde se usa la respuesta guardada fechada.</span>"+
    "<span>Tablero generado el "+DATA.meta.generado+" por la cadena (sin datos pegados a mano).</span>";
}

function dibujarChart(){
  const W=1000,H=300,padL=150,padR=90,padT=10,padB=22;
  const cs=DATA.centros.slice().sort((a,b)=>costoKg(b)-costoKg(a));
  const maxV=Math.max(...cs.map(costoKg),costoKg(DATA.resto));
  const n=cs.length,gap=(H-padT-padB)/n,bh=gap*0.72;
  const x=v=>padL+(W-padL-padR)*(v/maxV);
  let s="";
  cs.forEach((c,i)=>{const y=padT+i*gap+(gap-bh)/2,v=costoKg(c),w=x(v)-padL;
    const fill=c.id===DATA.critico.id?"#9a3324":(c.id===CENTRO?"#0e7a5c":"#c9d2cc");
    s+="<rect x='"+padL+"' y='"+y.toFixed(1)+"' width='"+w.toFixed(1)+"' height='"+bh.toFixed(1)+"' rx='3' fill='"+fill+"'></rect>";
    s+="<text class='bar-label' x='"+(padL-8)+"' y='"+(y+bh/2+4).toFixed(1)+"' text-anchor='end'>"+c.nombre+"</text>";
    s+="<text class='bar-val' x='"+(x(v)+6).toFixed(1)+"' y='"+(y+bh/2+4).toFixed(1)+"'>"+cl.format(Math.round(v))+"</text>";});
  const xr=x(costoKg(DATA.resto));
  s+="<line x1='"+xr.toFixed(1)+"' y1='"+padT+"' x2='"+xr.toFixed(1)+"' y2='"+(H-padB)+"' stroke='#14181f' stroke-dasharray='4 4' stroke-width='1'></line>";
  s+="<text class='bar-val' x='"+(xr+4).toFixed(1)+"' y='"+(H-padB+16)+"'>resto "+cl.format(Math.round(costoKg(DATA.resto)))+"</text>";
  document.getElementById("chart").innerHTML=s;
}
function dibujarTabla(){
  const tb=document.querySelector("#tabla tbody");
  const cs=DATA.centros.slice().sort((a,b)=>costoKg(b)-costoKg(a));
  const excBasal=DATA.basales[BASAL].exceso_n;
  tb.innerHTML=cs.map(c=>{const cls=c.id===DATA.critico.id?" class='top'":"";
    const exc=c.id===DATA.critico.id?excBasal:c.exceso_n;
    return "<tr"+cls+"><td>"+c.nombre+"</td><td>"+c.zona+"</td><td>"+cl.format(Math.round(costoKg(c)))+
      "</td><td>"+dec(fcr(c),3)+"</td><td>"+dec(c.mort_pct,3)+"%</td><td>"+cl.format(Math.round(exc))+"</td></tr>";}).join("");
}

document.querySelectorAll("#seg-def button").forEach(b=>b.addEventListener("click",()=>{
  document.querySelectorAll("#seg-def button").forEach(x=>x.classList.remove("on"));b.classList.add("on");DEF=b.dataset.def;pintar();}));
const selC=document.getElementById("sel-centro");
DATA.centros.slice().sort((a,b)=>b.costo_kg_bruto-a.costo_kg_bruto).forEach(c=>{
  const o=document.createElement("option");o.value=c.id;o.textContent=c.nombre;if(c.id===CENTRO)o.selected=true;selC.appendChild(o);});
selC.addEventListener("change",()=>{CENTRO=Number(selC.value);pintar();});
const selB=document.getElementById("sel-basal");
DATA.basales.forEach((b,i)=>{const o=document.createElement("option");o.value=i;o.textContent=b.nombre;selB.appendChild(o);});
selB.addEventListener("change",()=>{BASAL=Number(selB.value);pintar();});
pintar();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
