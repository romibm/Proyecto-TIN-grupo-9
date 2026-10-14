import csv
import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

# Supuesto de precio: la operación diaria no trae el tipo de alimento, por eso el precio del mes
# es el promedio simple de los tipos con precio válido ese mes. La alternativa solo usa Engorda 100.
PRECIO_ALTERNATIVO = 'Engorda 100'


def leer_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


def precios_por_mes(precios_path):
    """devuelve el precio CLP/kg por mes: promedio simple de tipos y solo Engorda 100"""
    por_mes = defaultdict(list)
    alternativo = {}
    for fila in leer_csv(precios_path):
        precio = float(fila['precio_clp_kg'])
        por_mes[fila['mes']].append(precio)
        if fila['tipo_alimento'] == PRECIO_ALTERNATIVO:
            alternativo[fila['mes']] = precio
    promedio = {mes: sum(v) / len(v) for mes, v in por_mes.items()}
    return promedio, alternativo


def leer_operacion(db_path):
    with closing(sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)) as con:
        con.row_factory = sqlite3.Row
        filas = [dict(r) for r in con.execute(
            "SELECT o.fecha, o.mes, o.centro_id, c.nombre AS centro, o.jaula_id, o.alimento_kg, "
            "o.mortalidad_n, o.poblacion, o.biomasa_kg, o.crecimiento_kg "
            "FROM operacion_limpia o JOIN centros c ON c.centro_id = o.centro_id "
            "WHERE o.fecha >= '2025-01-01' AND o.fecha < '2026-01-01'")]
    for f in filas:
        f['biomasa_muerta_kg'] = f['mortalidad_n'] * f['biomasa_kg'] / f['poblacion']
    return filas


def costo_por_centro(filas, precios):
    """alimento, crecimiento, biomasa muerta y costo de alimento por centro"""
    centros = {}
    for f in filas:
        c = centros.setdefault(f['centro_id'], dict(centro_id=f['centro_id'], centro=f['centro'],
                                                    A=0.0, G=0.0, M=0.0, costo=0.0))
        c['A'] += f['alimento_kg']
        c['G'] += f['crecimiento_kg']
        c['M'] += f['biomasa_muerta_kg']
        c['costo'] += f['alimento_kg'] * precios[f['mes']]
    for c in centros.values():
        c['N'] = c['G'] - c['M']
        c['precio_medio'] = c['costo'] / c['A']
        c['fcr_bruto'] = c['A'] / c['G']
        c['fcr_neto'] = c['A'] / c['N']
        c['costo_kg_bruto'] = c['costo'] / c['G']
        c['costo_kg_neto'] = c['costo'] / c['N']
    return centros


def descomponer(centros, objetivo):
    """descompone la brecha de costo por kg neto del centro objetivo contra los demás centros
    ln(costo_obj / costo_ref) = efecto precio + efecto FCR bruto + efecto mortalidad (G/N)"""
    ref_c = [c for c in centros.values() if c['centro_id'] != objetivo]
    o = centros[objetivo]
    A = sum(c['A'] for c in ref_c); G = sum(c['G'] for c in ref_c)
    N = sum(c['N'] for c in ref_c); costo = sum(c['costo'] for c in ref_c)
    ref = dict(precio=costo / A, fcr=A / G, g_n=G / N, costo_kg=costo / N)
    obj = dict(precio=o['precio_medio'], fcr=o['fcr_bruto'], g_n=o['G'] / o['N'], costo_kg=o['costo_kg_neto'])
    logs = {k: math.log(obj[k] / ref[k]) for k in ('precio', 'fcr', 'g_n')}
    total_log = sum(logs.values())
    brecha = obj['costo_kg'] - ref['costo_kg']
    res = {k: dict(log=v, parte=v / total_log, pesos_kg=brecha * v / total_log) for k, v in logs.items()}
    return ref, obj, brecha, res, o['N'] * brecha


def mortalidad_evento(filas, evento, tasa_basal_ref=None):
    """mortalidad en las jaulas afectadas durante el evento contra la mortalidad basal esperada.
    Basal A: tasa diaria (muertos / población) de las mismas jaulas fuera del evento.
    Basal B: tasa diaria de los demás centros durante las mismas fechas del evento."""
    jaulas = {int(j) for j in evento['jaulas_afectadas'].split()}
    ini, fin = evento['fecha_inicio'], evento['fecha_fin']
    dentro = [f for f in filas if f['jaula_id'] in jaulas and ini <= f['fecha'] <= fin]
    fuera = [f for f in filas if f['jaula_id'] in jaulas and not ini <= f['fecha'] <= fin]
    otros = [f for f in filas if f['centro_id'] != int(evento['centro_id']) and ini <= f['fecha'] <= fin]
    obs = sum(f['mortalidad_n'] for f in dentro)
    pob = sum(f['poblacion'] for f in dentro)
    tasa_a = sum(f['mortalidad_n'] for f in fuera) / sum(f['poblacion'] for f in fuera)
    tasa_b = sum(f['mortalidad_n'] for f in otros) / sum(f['poblacion'] for f in otros)
    fcr_dentro = sum(f['alimento_kg'] for f in dentro) / sum(f['crecimiento_kg'] for f in dentro)
    fcr_fuera = sum(f['alimento_kg'] for f in fuera) / sum(f['crecimiento_kg'] for f in fuera)
    peso_muerto = sum(f['biomasa_muerta_kg'] for f in dentro) / obs if obs else 0
    # sensibilidad: todo el centro durante la ventana, contra su propia tasa fuera de la ventana
    c_dentro = [f for f in filas if f['centro_id'] == int(evento['centro_id']) and ini <= f['fecha'] <= fin]
    c_fuera = [f for f in filas if f['centro_id'] == int(evento['centro_id']) and not ini <= f['fecha'] <= fin]
    tasa_c = sum(f['mortalidad_n'] for f in c_fuera) / sum(f['poblacion'] for f in c_fuera)
    c_obs = sum(f['mortalidad_n'] for f in c_dentro)
    c_atrib = c_obs - tasa_c * sum(f['poblacion'] for f in c_dentro)
    return dict(
        evento_id=evento['evento_id'], centro=evento['centro'], tipo=evento['tipo'],
        fecha_inicio=ini, fecha_fin=fin, filas_dentro=len(dentro),
        mortalidad_declarada_json_n=int(evento['mortalidad_declarada_json_n']),
        mortalidad_observada_jaulas_n=obs,
        tasa_diaria_evento=obs / pob, tasa_diaria_basal_propias_jaulas=tasa_a, tasa_diaria_basal_otros_centros=tasa_b,
        mortalidad_basal_A_n=tasa_a * pob, mortalidad_basal_B_n=tasa_b * pob,
        mortalidad_atribuible_A_n=obs - tasa_a * pob, mortalidad_atribuible_B_n=obs - tasa_b * pob,
        fcr_bruto_dentro_evento=fcr_dentro, fcr_bruto_fuera_evento=fcr_fuera,
        mortalidad_observada_centro_n=c_obs, mortalidad_atribuible_centro_n=c_atrib,
        peso_medio_muerto_kg=peso_muerto)


def efecto_evento(centros, objetivo, atribuible_n, peso_kg):
    """costo por kg neto del centro objetivo si se quitara la mortalidad atribuible al evento"""
    c = centros[objetivo]
    muerta_evento = atribuible_n * peso_kg
    n_sin = c['N'] + muerta_evento
    costo_sin = c['costo'] / n_sin
    return dict(biomasa_evento_kg=muerta_evento, fcr_neto_sin_evento=c['A'] / n_sin,
                costo_kg_sin_evento=costo_sin, efecto_clp_kg=c['costo_kg_neto'] - costo_sin,
                efecto_anual_clp=(c['costo_kg_neto'] - costo_sin) * c['N'])


def dolar_por_mes(dolar_path):
    """promedio simple mensual del dólar observado (CLP por USD); vacío si el archivo no existe"""
    if not dolar_path.exists():
        return {}
    por_mes = defaultdict(list)
    for fila in leer_csv(dolar_path):
        por_mes[fila['fecha'][:7]].append(float(fila['clp_por_usd']))
    return {mes: sum(v) / len(v) for mes, v in por_mes.items()}


def tabla_integrada(filas, precios, eventos, dolar=None):
    """una fila es la operación diaria de una jaula y lote en un centro y fecha, con precio, costo y evento"""
    ventanas = [(e['evento_id'], int(e['centro_id']), {int(j) for j in e['jaulas_afectadas'].split()},
                 e['fecha_inicio'], e['fecha_fin']) for e in eventos]
    salida = []
    for f in sorted(filas, key=lambda f: (f['fecha'], f['centro_id'], f['jaula_id'])):
        evento = next((v[0] for v in ventanas if v[1] == f['centro_id'] and f['jaula_id'] in v[2] and v[3] <= f['fecha'] <= v[4]), '')
        salida.append(dict(
            fecha=f['fecha'], mes=f['mes'], centro_id=f['centro_id'], centro=f['centro'], jaula_id=f['jaula_id'],
            alimento_kg=f['alimento_kg'], crecimiento_kg=f['crecimiento_kg'], mortalidad_n=f['mortalidad_n'],
            poblacion=f['poblacion'], biomasa_kg=f['biomasa_kg'], biomasa_muerta_estimada_kg=f['biomasa_muerta_kg'],
            precio_clp_kg_mes=precios[f['mes']], costo_alimento_clp=f['alimento_kg'] * precios[f['mes']],
            dolar_clp_usd_mes=dolar.get(f['mes'], ''),
            precio_usd_kg_mes=precios[f['mes']] / dolar[f['mes']] if f['mes'] in dolar else '',
            costo_alimento_usd=f['alimento_kg'] * precios[f['mes']] / dolar[f['mes']] if f['mes'] in dolar else '',
            evento_id=evento, en_evento=1 if evento else 0))
    return salida


def detalle_mensual(filas, precios, centro_id):
    meses = {}
    for f in filas:
        if f['centro_id'] != centro_id:
            continue
        m = meses.setdefault(f['mes'], dict(mes=f['mes'], A=0.0, G=0.0, M=0.0, costo=0.0, muertos=0, pob=0))
        m['A'] += f['alimento_kg']; m['G'] += f['crecimiento_kg']; m['M'] += f['biomasa_muerta_kg']
        m['costo'] += f['alimento_kg'] * precios[f['mes']]; m['muertos'] += f['mortalidad_n']; m['pob'] += f['poblacion']
    res = []
    for mes in sorted(meses):
        m = meses[mes]; N = m['G'] - m['M']
        res.append(dict(mes=mes, alimento_kg=m['A'], crecimiento_bruto_kg=m['G'], biomasa_muerta_kg=m['M'], crecimiento_neto_kg=N,
                        mortalidad_n=m['muertos'], tasa_mortalidad_diaria=m['muertos'] / m['pob'],
                        fcr_bruto=m['A'] / m['G'], fcr_neto=m['A'] / N, costo_alimento_clp=m['costo'],
                        costo_kg_bruto=m['costo'] / m['G'], costo_kg_neto=m['costo'] / N))
    return res


def escribir(path, filas):
    with path.open('w', encoding='utf-8-sig', newline='') as file:
        w = csv.DictWriter(file, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def main():
    carpeta = Path(__file__).resolve().parent
    db = carpeta / 'output_persona1' / 'datos_sqlite_limpios.sqlite'
    precios_path = carpeta / 'output_persona2' / 'precios_limpios.csv'
    eventos_path = carpeta / 'output_persona2' / 'eventos_limpios.csv'
    salida = carpeta / 'output_persona3'
    salida.mkdir(exist_ok=True)

    filas = leer_operacion(db)
    promedio, alternativo = precios_por_mes(precios_path)
    faltan = {f['mes'] for f in filas} - set(alternativo)
    if faltan:
        print('Aviso: sin precio de Engorda 100 en', sorted(faltan), '; la alternativa usa el promedio de esos meses')
    alternativo = {m: alternativo.get(m, promedio[m]) for m in promedio}

    base = costo_por_centro(filas, promedio)
    alt = costo_por_centro(filas, alternativo)
    objetivo = max(base.values(), key=lambda c: c['costo_kg_neto'])['centro_id']
    ref, obj, brecha, desc, pesos_anual = descomponer(base, objetivo)
    ref_alt, obj_alt, brecha_alt, desc_alt, pesos_alt = descomponer(alt, objetivo)

    cols = ['centro_id', 'centro', 'A', 'G', 'M', 'N', 'precio_medio', 'fcr_bruto', 'fcr_neto', 'costo_kg_bruto', 'costo_kg_neto']
    escribir(salida / 'costo_por_kg_por_centro.csv',
             [{**{k: c[k] for k in cols}, 'costo_kg_neto_precio_alt': alt[c['centro_id']]['costo_kg_neto']}
              for c in sorted(base.values(), key=lambda c: c['centro_id'])])

    eventos = leer_csv(eventos_path)
    ev = [mortalidad_evento(filas, e) for e in eventos]
    escribir(salida / 'mortalidad_evento.csv', ev)

    descomp = []
    for nombre, d, b, p in (('precio promedio de tipos', desc, brecha, pesos_anual), ('precio solo Engorda 100', desc_alt, brecha_alt, pesos_alt)):
        for k, v in d.items():
            descomp.append(dict(definicion_precio=nombre, centro=base[objetivo]['centro'], factor=k,
                                parte_de_la_brecha=v['parte'], clp_por_kg_neto=v['pesos_kg'],
                                brecha_total_clp_por_kg=b, brecha_anual_clp=p))
    escribir(salida / 'descomposicion_costo.csv', descomp)

    print(f"Centro con mayor costo por kg neto: {base[objetivo]['centro']}")
    for c in sorted(base.values(), key=lambda c: c['centro_id']):
        print(f"  {c['centro']:<18} costo/kg bruto {c['costo_kg_bruto']:7.1f}  neto {c['costo_kg_neto']:7.1f}  (alt {alt[c['centro_id']]['costo_kg_neto']:7.1f})")
    print(f"Referencia (otros 6): {ref['costo_kg']:.1f} CLP/kg neto; objetivo {obj['costo_kg']:.1f}; brecha {brecha:.1f}")
    for k, v in desc.items():
        print(f"  {k:7s} {v['parte']*100:6.1f} %  {v['pesos_kg']:7.1f} CLP/kg")
    print(f"Brecha anual alimento: {pesos_anual:,.0f} CLP (alt {pesos_alt:,.0f})")
    for e in ev:
        print(e['evento_id'], e['centro'], 'decl', e['mortalidad_declarada_json_n'], 'obs', e['mortalidad_observada_jaulas_n'],
              'atrib A', round(e['mortalidad_atribuible_A_n']), 'atrib B', round(e['mortalidad_atribuible_B_n']),
              'FCR dentro/fuera', round(e['fcr_bruto_dentro_evento'], 3), round(e['fcr_bruto_fuera_evento'], 3))
    e_obj = next(e for e in ev if e['centro'] == base[objetivo]['centro'])
    sal = []
    for nombre, n in (('jaulas afectadas', e_obj['mortalidad_atribuible_A_n']), ('todo el centro', e_obj['mortalidad_atribuible_centro_n'])):
        r = efecto_evento(base, objetivo, n, e_obj['peso_medio_muerto_kg'])
        sal.append(dict(base_mortalidad_atribuible=nombre, muertos_atribuibles_n=n, **r,
                        brecha_clp_kg=brecha, parte_de_brecha=r['efecto_clp_kg'] / brecha))
        print(f"Evento {e_obj['evento_id']} ({nombre}): {n:,.0f} peces, FCR neto sin evento {r['fcr_neto_sin_evento']:.3f}, "
              f"efecto {r['efecto_clp_kg']:.0f} CLP/kg = {r['efecto_clp_kg']/brecha*100:.1f} % de la brecha, {r['efecto_anual_clp']:,.0f} CLP")
    escribir(salida / 'efecto_evento_skyring.csv', sal)
    escribir(salida / 'tabla_integrada.csv', tabla_integrada(filas, promedio, eventos, dolar_por_mes(carpeta / 'output_persona2' / 'dolar_limpio.csv')))
    escribir(salida / 'detalle_mensual_centro_mayor_costo.csv', detalle_mensual(filas, promedio, objetivo))
    print(f"OK: archivos en {salida}")


if __name__ == '__main__':
    main()