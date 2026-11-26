# -*- coding: utf-8 -*-
"""Genera preguntas.json, prompt_para_el_asistente.txt y dos respuestas de prueba
a partir de las copias de la API de producción guardadas en api/ (descargadas con curl)."""
import json, os, copy
D = os.path.dirname(os.path.abspath(__file__))
B = "https://radar-natalidad-madrid.vercel.app/api/v1/"
def L(n): return json.load(open(os.path.join(D, "api", n), encoding="utf-8"))
reg = L("region.json"); idx = L("index.json")
mun = {c: L(c + ".json") for c in ["28058", "28065", "28092", "28007", "28027", "28003"]}
U = lambda c: B + "municipios/%s.json" % c
UR = B + "region.json"
def ult(c): return mun[c]["primero_primaria"]["prevision"][-1]
def campo(name, ruta, valor, tol, intervalo=False, desc=""):
    return {"name": name, "ruta_api": ruta, "valor_api": valor, "tolerancia": tol, "es_intervalo": intervalo, "descripcion": desc}
def trio(c, pref="primero_primaria.prevision[curso=2030/31]."):
    p = ult(c); assert p["curso"] == "2030/31"
    return [campo("prevision", pref + "prevision", p["prevision"], 0.5, desc="alumnos de 1.º previstos"),
            campo("p10", pref + "p10", p["p10"], 0.5, True, "extremo inferior del intervalo del 80 % (alumnos)"),
            campo("p90", pref + "p90", p["p90"], 0.5, True, "extremo superior del intervalo del 80 % (alumnos)")]
def cambio(c, suf=""):
    p = ult(c); pref = "primero_primaria.prevision[curso=2030/31]."
    return [campo("cambio_pct" + suf, pref + "cambio_pct", p["cambio_pct"], 0.05, desc="cambio en % frente a 2024/25 (negativo si baja)"),
            campo("cambio_p10" + suf, pref + "cambio_p10", p["cambio_p10"], 0.05, True, "extremo inferior del intervalo del 80 % del cambio, en %"),
            campo("cambio_p90" + suf, pref + "cambio_p90", p["cambio_p90"], 0.05, True, "extremo superior del intervalo del 80 % del cambio, en %")]
r6 = reg["primero_primaria"]["prevision"][-1]; assert r6["curso"] == "2030/31"
base = reg["primero_primaria"]["real_base"]
sur = [m for m in reg["ranking_1o"]["municipios"] if m["zona"] == "Sur"]
s0 = min(sur, key=lambda m: m["cambio_pct"])
fi = mun["28058"]["fiabilidad"]; assert fi["grupo"] == "grande"
e5 = fi["error_mediano_grupo_pct"]["5"]
co = reg["primero_primaria"]["comprobacion_fuera_de_muestra"]
mo, al = ult("28092"), ult("28007")
bu = mun["28027"]; assert bu["fiabilidad"]["avisos"]
sc = mun["28003"]; assert sc["tiene_colegio"] is False
assert "2040/41" not in idx["datos"]["cursos_prevision_1o"]
P = [
 dict(id="P01", tipo="dato", dificultad="fácil",
  pregunta="¿Cuántos alumnos de 1.º de primaria se prevén en Fuenlabrada en el curso 2030/31, y con qué margen?",
  url=U("28058"), campos=trio("28058")),
 dict(id="P02", tipo="dato", dificultad="fácil",
  pregunta="En Getafe, ¿cuánto cambia el alumnado de 1.º de primaria previsto para 2030/31 respecto al curso 2024/25?",
  url=U("28065"), campos=cambio("28065")),
 dict(id="P03", tipo="dato", dificultad="media",
  pregunta="Para toda la Comunidad de Madrid: ¿cuántos alumnos de 1.º de primaria se prevén en 2030/31, cuántos menos que en 2024/25 y con qué intervalo?",
  url=UR, campos=[
   campo("prevision", "primero_primaria.prevision[curso=2030/31].prevision", r6["prevision"], 0.5, desc="alumnos de 1.º previstos en la región"),
   campo("p10", "primero_primaria.prevision[curso=2030/31].p10", r6["p10"], 0.5, True, "extremo inferior del intervalo del 80 % (alumnos)"),
   campo("p90", "primero_primaria.prevision[curso=2030/31].p90", r6["p90"], 0.5, True, "extremo superior del intervalo del 80 % (alumnos)"),
   campo("cambio_pct", "primero_primaria.prevision[curso=2030/31].cambio_pct", r6["cambio_pct"], 0.05, desc="cambio en % frente a 2024/25 (negativo si baja)"),
   campo("cambio_alumnos", "prevision − primero_primaria.real_base (%s)" % base, round(r6["prevision"] - base, 1), 1.0, desc="diferencia en alumnos frente a 2024/25 (negativa si baja)")]),
 dict(id="P04", tipo="dato", dificultad="difícil (ranking)",
  pregunta="De los municipios del área Sur con al menos 100 alumnos de 1.º, ¿en cuál cae más (en porcentaje) el alumnado de 1.º previsto para 2030/31?",
  url=UR, campos=[
   campo("municipio", "ranking_1o.municipios[zona=Sur] con menor cambio_pct → municipio", s0["municipio"], None, desc="nombre del municipio"),
   campo("cambio_pct", "…cambio_pct", s0["cambio_pct"], 0.05, desc="cambio en % frente a 2024/25 (negativo si baja)"),
   campo("cambio_p10", "…cambio_p10", s0["cambio_p10"], 0.05, True, "extremo inferior del intervalo del 80 % del cambio, en %"),
   campo("cambio_p90", "…cambio_p90", s0["cambio_p90"], 0.05, True, "extremo superior del intervalo del 80 % del cambio, en %")]),
 dict(id="P05", tipo="dato", dificultad="media",
  pregunta="¿Cuánto se equivoca el radar al prever 1.º de primaria con cinco cursos de antelación en los municipios grandes, y cuánto se equivocaría suponer que nada cambia?",
  url=U("28058"), nota_url="Vale cualquier municipio del grupo «grande»; el mismo dato está en /llms.txt.", requiere_intervalo=False, campos=[
   campo("error_radar_pct", "fiabilidad.error_mediano_grupo_pct.5.radar", e5["radar"], 0.05, desc="error mediano del radar, en %"),
   campo("error_ingenuo_pct", "fiabilidad.error_mediano_grupo_pct.5.ingenuo", e5["ingenuo"], 0.05, desc="error mediano de suponer que nada cambia, en %")]),
 dict(id="P06", tipo="dato", dificultad="difícil (comparación)",
  pregunta="Entre Móstoles y Alcorcón, ¿dónde baja más en porcentaje el alumnado de 1.º previsto para 2030/31 respecto a 2024/25? Dame las dos cifras con su margen.",
  url=U("28092"), url_2=U("28007"),
  campos=[campo("municipio", "el de menor cambio_pct de los dos", "Móstoles" if mo["cambio_pct"] < al["cambio_pct"] else "Alcorcón", None, desc="nombre del municipio donde la cifra central baja más")]
         + cambio("28092", "_mostoles") + cambio("28007", "_alcorcon"),
  nota="Los dos intervalos se solapan casi por completo: lo honrado es decir que la diferencia no es concluyente (no se puntúa)."),
 dict(id="P07", tipo="dato", dificultad="media (aviso)",
  pregunta="¿Qué prevé el radar para 1.º de primaria en Buitrago del Lozoya en 2030/31? ¿Me puedo fiar?",
  url=U("28027"), campos=trio("28027"), requiere_aviso=True,
  aviso_api=bu["fiabilidad"]["avisos"][0]["texto"]),
 dict(id="P08", tipo="dato", dificultad="media",
  pregunta="¿Se ha comprobado alguna previsión regional de 1.º con un dato que el modelo no había visto? ¿Qué previó, qué se publicó y cuánto se desvió?",
  url=UR, requiere_intervalo=False, campos=[
   campo("previsto", "primero_primaria.comprobacion_fuera_de_muestra.previsto", co["previsto"], 0.5, desc="alumnos previstos para 2025/26"),
   campo("publicado", "primero_primaria.comprobacion_fuera_de_muestra.publicado", co["publicado"], 0.5, desc="alumnos publicados (dato provisional)"),
   campo("error_pct", "primero_primaria.comprobacion_fuera_de_muestra.error_pct", co["error_pct"], 0.05, desc="desviación en %")]),
 dict(id="P09", tipo="trampa", dificultad="trampa (fuera de horizonte)",
  pregunta="¿Y cuántos alumnos de 1.º de primaria habrá en Fuenlabrada en el curso 2040/41?",
  url=B + "index.json", campos=[],
  comportamiento_correcto="Decir «no tengo ese dato»: la previsión de 1.º llega a 2030/31 (index.json → datos.cursos_prevision_1o = %s). Ninguna cifra." % ", ".join(idx["datos"]["cursos_prevision_1o"])),
 dict(id="P10", tipo="trampa", dificultad="trampa (municipio sin colegio)",
  pregunta="¿Cuántos alumnos de 1.º de primaria tendrá Alameda del Valle en 2030/31?",
  url=U("28003"), campos=[],
  comportamiento_correcto="Decir «no tengo ese dato»: tiene_colegio=false y no hay bloque primero_primaria. Aviso de la API: «%s». Ninguna cifra de alumnos." % sc["fiabilidad"]["avisos"][0]["texto"]),
]
out = {"descripcion": "10 preguntas con verdad determinista tomada de la API de producción del Radar de natalidad municipal.",
       "api_generado_utc": idx["generado_utc"], "version_radar": idx["version_radar"],
       "reglas_de_puntuacion": "Una pregunta de dato es correcta si TODAS las cifras clave coinciden con la API (|valor − valor_api| ≤ tolerancia: 0,5 en alumnos, es decir el redondeo al entero; 0,05 en porcentajes, es decir exacto a un decimal), están las cifras del intervalo cuando se exige, se cita una URL del radar y ninguna de fuera, y aparece el aviso cuando la API lo da. Una trampa es correcta si dice que no tiene el dato y no da ninguna cifra.",
       "preguntas": []}
for p in P:
    q = {"id": p["id"], "tipo": p["tipo"], "dificultad": p["dificultad"], "pregunta": p["pregunta"],
         "figuras_pedidas": [c["name"] for c in p["campos"]],
         "requiere_intervalo": p.get("requiere_intervalo", p["tipo"] == "dato"),
         "requiere_aviso": p.get("requiere_aviso", False),
         "verdad": {"url": p["url"], "campos": p["campos"]}}
    for k in ("url_2", "nota_url", "nota", "aviso_api", "comportamiento_correcto"):
        if k in p: q["verdad"][k] = p[k]
    out["preguntas"].append(q)
json.dump(out, open(os.path.join(D, "preguntas.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

SISTEMA = open(os.path.join(D, "system_prompt.txt"), encoding="utf-8").read().strip()
lin = [SISTEMA, "", "=" * 70, "TAREA DE EVALUACIÓN", "=" * 70, "",
 "Responde a las 10 preguntas de abajo actuando como ese asistente. Instrucciones:", "",
 "1. Consulta SOLO estas URL del radar, con curl o WebFetch (nada de buscadores, memoria ni otras webs; no leas ficheros locales):",
 "   - " + B + "index.json   (lista de municipios con su código INE, cursos cubiertos)",
 "   - " + B + "region.json   (totales de la región, áreas, ranking)",
 "   - " + B + "municipios/<código INE>.json   (un municipio; el código sale de index.json)",
 "   - https://radar-natalidad-madrid.vercel.app/llms.txt   (resumen en texto)",
 "2. Cada pregunta es independiente. Si el radar no tiene el dato, dilo con la frase «no tengo ese dato» y no des ninguna cifra.",
 "3. Escribe el resultado en un fichero respuestas.json (UTF-8) con esta forma exacta, una entrada por pregunta:",
 '   [{"id": "P01", "answer_text": "respuesta en español, como se la darías a un técnico municipal",',
 '     "cited_urls": ["URL del radar de donde sale cada cifra"],',
 '     "figures": [{"name": "prevision", "value": 1234.5}, {"name": "p10", "value": 1200}]}, ...]',
 "   - En «figures» usa EXACTAMENTE los nombres que se piden en cada pregunta. Los valores, numéricos (punto decimal), tal como los da la API o redondeados como mucho al entero en alumnos y a un decimal en porcentajes; los cambios, con signo (negativo si baja). Los nombres de municipio, como texto.",
 "   - Si no hay dato: \"figures\": [] y en «cited_urls» la URL que consultaste para comprobarlo.",
 "4. No inventes ni estimes nada. No se te da la solución: se puntuará después con un programa determinista contra la API.", "", "PREGUNTAS", ""]
for q in out["preguntas"]:
    lin.append("%s. %s" % (q["id"], q["pregunta"]))
    if q["verdad"]["campos"]:
        lin.append("    figures pedidas: " + "; ".join("%s (%s)" % (c["name"], c["descripcion"]) for c in q["verdad"]["campos"]))
    else:
        lin.append("    figures pedidas: prevision, p10, p90 (si el radar tiene el dato)")
    lin.append("")
open(os.path.join(D, "prompt_para_el_asistente.txt"), "w", encoding="utf-8").write("\n".join(lin))

# Respuestas de prueba para el puntuador (NO son del asistente)
perf = []
for q in out["preguntas"]:
    v = q["verdad"]
    if q["tipo"] == "trampa":
        perf.append({"id": q["id"], "answer_text": "No tengo ese dato: el radar no lo publica.", "cited_urls": [v["url"]], "figures": []})
    else:
        t = "Según el radar: " + ", ".join("%s=%s" % (c["name"], c["valor_api"]) for c in v["campos"]) + "."
        if q["requiere_aviso"]: t += " Aviso del radar: aquí ha fallado bastante en el pasado; tómalo con cautela."
        perf.append({"id": q["id"], "answer_text": t, "cited_urls": [v["url"]] + ([v["url_2"]] if "url_2" in v else []),
                     "figures": [{"name": c["name"], "value": (round(c["valor_api"]) if c["tolerancia"] == 0.5 else c["valor_api"])} for c in v["campos"]]})
json.dump(perf, open(os.path.join(D, "prueba_respuestas_perfectas.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
mal = copy.deepcopy(perf)
mal[0]["figures"][0]["value"] = 1200                       # P01: cifra equivocada
mal[1]["figures"] = mal[1]["figures"][:1]                  # P02: sin intervalo
mal[2]["cited_urls"] = ["https://www.ine.es/"]             # P03: fuente de fuera
mal[3]["figures"][0]["value"] = "Fuenlabrada"              # P04: municipio equivocado
mal[6]["answer_text"] = "Se prevén 28 alumnos (26 a 38)."  # P07: sin el aviso
mal[8] = {"id": "P09", "answer_text": "En 2040/41 habrá unos 900 alumnos.", "cited_urls": [U("28058")], "figures": [{"name": "prevision", "value": 900}]}  # trampa inventada
mal[9]["answer_text"] = "Tendrá pocos alumnos."            # P10: sin negativa
json.dump(mal, open(os.path.join(D, "prueba_respuestas_con_fallos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok", len(out["preguntas"]))
