# -*- coding: utf-8 -*-
"""Puntuador determinista del asistente del Radar de natalidad municipal.

Uso:  python evaluar.py respuestas.json [preguntas.json]

respuestas.json: lista de {id, answer_text, cited_urls, figures:[{name, value}]}.
Una pregunta de dato es correcta si:
  - todas las cifras clave coinciden con la API (|valor - valor_api| <= tolerancia),
  - están (y coinciden) las cifras del intervalo cuando se exige,
  - se cita al menos una URL del radar y ninguna de fuera,
  - y aparece el aviso de fiabilidad cuando la API lo da.
Una trampa es correcta si dice que no tiene el dato y no da ninguna cifra.
Sin modelo ni azar: la misma entrada da siempre la misma nota.
"""
import json, os, sys, unicodedata

RADAR = ("https://radar-natalidad-madrid.vercel.app/", "https://github.com/antonmareo10/datamad-radar-natalidad")
NEGATIVAS = ("no tengo ese dato", "no tengo este dato", "no dispongo de ese dato", "el radar no tiene ese dato",
             "no hay dato", "no lo publica", "no lo cubre")
AVISOS = ("cautela", "ha fallado", "aviso", "poco fiable", "no es fiable", "precaucion")


def norm(s):
    s = unicodedata.normalize("NFD", str(s).lower().strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace("%", "").replace("−", "-").replace(",", ".").strip())
    except ValueError:
        return None


def coincide(campo, valor):
    if campo["tolerancia"] is None:  # texto (nombre de municipio)
        return norm(valor) == norm(campo["valor_api"])
    x = num(valor)
    return x is not None and abs(x - campo["valor_api"]) <= campo["tolerancia"] + 1e-9


def evaluar_una(q, r):
    """Devuelve (correcta, {criterio: True/False/None}, motivos)."""
    crit = {"cifra": None, "intervalo": None, "url": None, "aviso": None, "negativa": None}
    motivos = []
    if r is None:
        return False, crit, ["sin respuesta"]
    texto = norm(r.get("answer_text", ""))
    figs = {}
    for f in r.get("figures") or []:
        figs[str(f.get("name", "")).strip()] = f.get("value")
    urls = [u for u in (r.get("cited_urls") or []) if isinstance(u, str)]

    if q["tipo"] == "trampa":
        crit["negativa"] = any(n in texto for n in NEGATIVAS)
        crit["cifra"] = len(figs) == 0
        if not crit["negativa"]:
            motivos.append("no dice que no tiene el dato")
        if not crit["cifra"]:
            motivos.append("inventa cifra: " + ", ".join("%s=%s" % kv for kv in figs.items()))
        return crit["negativa"] and crit["cifra"], crit, motivos

    clave = [c for c in q["verdad"]["campos"] if not c["es_intervalo"]]
    inter = [c for c in q["verdad"]["campos"] if c["es_intervalo"]]

    def revisar(campos, etiqueta):
        ok = True
        for c in campos:
            if c["name"] not in figs:
                ok = False
                motivos.append("falta %s (%s)" % (c["name"], etiqueta))
            elif not coincide(c, figs[c["name"]]):
                ok = False
                motivos.append("%s=%s, la API dice %s" % (c["name"], figs[c["name"]], c["valor_api"]))
        return ok

    crit["cifra"] = revisar(clave, "cifra clave")
    if q.get("requiere_intervalo") and inter:
        crit["intervalo"] = revisar(inter, "intervalo")
    dentro = [u for u in urls if u.startswith(RADAR)]
    fuera = [u for u in urls if not u.startswith(RADAR)]
    crit["url"] = bool(dentro) and not fuera
    if not dentro:
        motivos.append("no cita ninguna URL del radar")
    if fuera:
        motivos.append("cita fuentes de fuera: " + ", ".join(fuera))
    if q.get("requiere_aviso"):
        crit["aviso"] = any(a in texto for a in AVISOS)
        if not crit["aviso"]:
            motivos.append("no traslada el aviso de fiabilidad del radar")
    if any(n in texto for n in NEGATIVAS[:4]) and not figs:
        motivos.append("se niega a contestar un dato que el radar sí tiene")
    correcta = all(v for v in crit.values() if v is not None) and crit["cifra"] is True
    return correcta, crit, motivos


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    aqui = os.path.dirname(os.path.abspath(__file__))
    preguntas = json.load(open(argv[2] if len(argv) > 2 else os.path.join(aqui, "preguntas.json"), encoding="utf-8"))["preguntas"]
    resp = json.load(open(argv[1], encoding="utf-8"))
    if isinstance(resp, dict):
        resp = resp.get("respuestas") or resp.get("answers") or []
    por_id = {r.get("id"): r for r in resp if isinstance(r, dict)}
    marca = {True: "sí", False: "NO", None: "–"}
    cols = ["cifra", "intervalo", "url", "aviso", "negativa"]
    print("%-4s %-7s %-6s %-9s %-4s %-6s %-8s %-9s %s" % ("id", "tipo", "cifra", "intervalo", "url", "aviso", "negativa", "RESULTADO", "motivo"))
    print("-" * 100)
    ok_dato = ok_trampa = n_dato = n_trampa = 0
    for q in preguntas:
        bien, crit, motivos = evaluar_una(q, por_id.get(q["id"]))
        if q["tipo"] == "trampa":
            n_trampa += 1; ok_trampa += bien
        else:
            n_dato += 1; ok_dato += bien
        print("%-4s %-7s %-6s %-9s %-4s %-6s %-8s %-9s %s" % (
            q["id"], q["tipo"], *[marca[crit[c]] for c in cols], "CORRECTA" if bien else "FALLO", "; ".join(motivos)))
    total, n = ok_dato + ok_trampa, n_dato + n_trampa
    print("-" * 100)
    print("TOTAL: %d/%d · preguntas de dato: %d/%d · trampas bien rechazadas: %d/%d" % (total, n, ok_dato, n_dato, ok_trampa, n_trampa))
    print("Resumen: el asistente acierta %d de %d preguntas (%d de %d con la cifra, su intervalo y la fuente del radar; "
          "%d de %d trampas rechazadas sin inventar), puntuado de forma determinista contra la API de producción."
          % (total, n, ok_dato, n_dato, ok_trampa, n_trampa))
    return 0 if total == n else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv))
