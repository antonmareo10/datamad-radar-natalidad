"""Comprueba cada cifra municipal de las diapositivas, la ficha y la chuleta contra la API en producción
(https://radar-natalidad-madrid.vercel.app/api/v1/), redondeando una sola vez desde el valor de la API.
Termina con código 1 si alguna no coincide.
"""
import json, math, sys, urllib.request

B = "https://radar-natalidad-madrid.vercel.app/api/v1/"


def get(p):
    with urllib.request.urlopen(B + p, timeout=20) as r:
        return json.loads(r.read().decode("utf-8-sig"))


def r1(x):  # redondeo «de toda la vida» (la mitad hacia arriba), una sola vez
    return math.floor(x + 0.5)


def miles(n):
    return f"{n:,}".replace(",", ".")


idx = get("index.json")
cods = {m["municipio"] if "municipio" in m else m.get("nombre"): m.get("cmun") or m.get("codigo") for m in idx["municipios"]}
mun = {c: get(f"municipios/{c}.json") for c in ("28058", "28027", "28079")}

def ult(m, etapa="primero_primaria"):
    return m[etapa]["prevision"][-1]

filas = []
def compara(donde, que, mostrado, api):
    filas.append((donde, que, mostrado, api, mostrado == api))

# Fuenlabrada (diapositivas 4 y 7, ficha, chuleta, demo)
fu = mun["28058"]; p = ult(fu)
compara("4, 7, chuleta", "Fuenlabrada 1º 2030/31", "1.150", miles(r1(p["prevision"])))
compara("4, 7, chuleta", "Fuenlabrada intervalo", "1.075-1.277", f"{miles(r1(p['p10']))}-{miles(r1(p['p90']))}")
compara("4, ficha", "Fuenlabrada cambio", "−26 %", f"−{r1(-p['cambio_pct'])} %")
compara("4, chuleta", "Fuenlabrada 2024/25", "1.560", miles(fu["primero_primaria"]["alumnos_base"]))
pas = [x for x in fu["fiabilidad"]["previsiones_pasadas"] if x["curso"] == "2024/25"]
compara("4, 7, chuleta", "Fuenlabrada acierto radar", "+1,6 a +9,2 %",
        f"+{min(x['error_pct'] for x in pas):.1f} a +{max(x['error_pct'] for x in pas):.1f} %".replace(".", ","))
compara("4", "Fuenlabrada nada cambia", "+10,4 a +28,8 %",
        f"+{min(x['error_naive_pct'] for x in pas):.1f} a +{max(x['error_naive_pct'] for x in pas):.1f} %".replace(".", ","))
compara("4", "Fuenlabrada: previsiones pasadas para 2024/25", "6", str(len(pas)))
nac24 = next(x["nacidos"] for x in fu["nacidos"] if x["anio"] == 2024)
compara("3", "Fuenlabrada nacidos en 2024", "1.132", miles(nac24))
compara("3", "Fuenlabrada factor", "1,016", f"{fu['primero_primaria']['factor']:.3f}".replace(".", ","))
compara("3", "1.132 × 1,016 redondeado", "1.150", miles(r1(nac24 * fu["primero_primaria"]["factor"])))
menos_fu = fu["primero_primaria"]["alumnos_base"] - r1(p["prevision"])
compara("4", "Fuenlabrada: niños menos y aulas de 20", "410 niños, ≈ 20 aulas", f"{menos_fu} niños, ≈ {int(round(menos_fu / 20))} aulas")
pi = ult(fu, "infantil_3_5")
compara("PITCH_FINAL (7:00)", "Fuenlabrada infantil 2027/28", "3.530 (−14 %)", f"{miles(r1(pi['prevision']))} (−{r1(-pi['cambio_pct'])} %)")

# Buitrago del Lozoya (R3 y la demo)
bu = mun["28027"]; p = ult(bu)
compara("R3 (captura)", "Buitrago 1º 2030/31", "28", str(r1(p["prevision"])))
compara("R3 (captura)", "Buitrago intervalo", "26-38", f"{r1(p['p10'])}-{r1(p['p90'])}")
compara("R3 (captura)", "Buitrago cambio y base", "−46 % (53)", f"−{r1(-p['cambio_pct'])} % ({bu['primero_primaria']['alumnos_base']})")
ep = bu["fiabilidad"]["error_propio"]
compara("R3, demo", "Buitrago error propio", "38,9 % en 15; −35,9 %", f"{ep['mediana_abs_pct']:.1f} % en {ep['n']}; −{-ep['media_pct']:.1f} %".replace(".", ","))
compara("demo, chuleta", "Buitrago «un 36 % de media»", "36", str(r1(-ep["media_pct"])))

# Madrid capital (diapositiva 1)
compara("1", "Madrid capital cambio", "−5,7 %", f"−{-ult(mun['28079'])['cambio_pct']:.1f} %".replace(".", ","))

# Región y áreas (diapositiva 1 y ficha)
reg = get("region.json")
print("region.json:", list(reg.keys()))
txt = json.dumps(reg, ensure_ascii=False)
pp_reg = reg["primero_primaria"]
print("  region.json, claves de primero_primaria:", list(pp_reg.keys())[:12])
base_r = pp_reg.get("alumnos_base") or pp_reg.get("real_base")
prev_r = pp_reg["prevision"][-1]["prevision"] if isinstance(pp_reg.get("prevision"), list) else None
if base_r and prev_r:
    menos_r = base_r - r1(prev_r)
    compara("1", "Región: alumnos menos y aulas de 20", "6.812, ≈ 340 aulas", f"{miles(menos_r)}, ≈ {int(round(menos_r / 20, -1))} aulas")
for clave in ("Sur", "-21.0", "52047", "58859"):
    print(f"  ¿aparece {clave!r} en region.json?", clave in txt)

# Ranking (solo en PITCH_FINAL, versión de 7:00)
for nombre, mostrado in (("Paracuellos de Jarama", "−39 %"), ("Guadarrama", "−37 %"), ("Arroyomolinos", "−34 %"),
                         ("Moralzarzal", "+12 %"), ("Villalbilla", "+11 %")):
    c = cods.get(nombre)
    if not c:
        filas.append(("PITCH_FINAL (7:00)", nombre, mostrado, "no encontrado en index.json", False)); continue
    cp = ult(get(f"municipios/{c}.json"))["cambio_pct"]
    compara("PITCH_FINAL (7:00)", nombre, mostrado, f"{'+' if cp > 0 else '−'}{r1(abs(cp))} %")

ancho = max(len(f[1]) for f in filas)
for donde, que, m, a, ok in filas:
    print(f"{'OK ' if ok else 'MAL'} {que:<{ancho}}  mostrado {m:<22} API {a:<22} ({donde})")
sys.exit(0 if all(f[4] for f in filas) else 1)
