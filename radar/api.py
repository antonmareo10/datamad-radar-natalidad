"""API abierta estática: escribe en web/api/v1/ los mismos datos que enseña la web, en JSON.

Sin servidor: son ficheros que se publican junto a la web. Se generan a la vez que
web/datos/radar.js (`python -m radar web`) y a partir del mismo diccionario, así que la web, la API
y el servidor MCP (mcp_server/) dan siempre las mismas cifras. El esquema está en docs/API.md.

- index.json                metadatos, licencias, fuentes y lista de municipios
- region.json               totales regionales: serie, previsión con intervalos y ranking
- municipios/{cmun}.json    un fichero por municipio (código INE de 5 dígitos)
"""
from __future__ import annotations

import json
import math
import pathlib
import shutil
import statistics
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd

from . import __version__
from .config import CAPITAL, MANIFIESTO, REPO, RESULTADOS, URL_WEB, WEB_API
from .sdm import exportar_sdm

VERSION_API = "1"
URL_API = f"{URL_WEB}/api/v1"
INTERVALO = "Intervalo del 80 %: p10 y p90 son los cuantiles del 10 % y del 90 % de los errores reales del backtest " \
            "en municipios del mismo grupo de tamaño y con la misma antelación."

# ------------------------------------------------------------------ formato, igual que web/app.js
# Los avisos se escriben con el mismo texto que la ficha de la web (función ficha() de app.js).
MENOS, NBSP = "−", " "


def _redondeo_js(v: float) -> int:
    """Math.round de JavaScript (la mitad, hacia arriba)."""
    return math.floor(v + 0.5)


def _miles(s: str) -> str:
    ent, _, dec = s.partition(".")
    ent = f"{int(ent):,}".replace(",", ".")
    return ent + ("," + dec if dec else "")


def _f(v: float, d: int) -> str:
    """Intl.NumberFormat('es-ES') con d decimales (redondeo «halfExpand» sobre la representación corta)."""
    q = Decimal(repr(float(abs(v)))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    return _miles(f"{q:.{d}f}")


def ent(v) -> str:
    if v is None:
        return "—"
    n = _redondeo_js(v)
    return (MENOS if n < 0 else "") + _miles(str(abs(n)))


def _signo(v: float) -> str:
    return "+" if v > 0.0001 else MENOS if v < -0.0001 else ""


def pct(v, d: int = 0) -> str:
    if v is None:
        return "—"
    return _signo(v) + (_f(v, 1) if d else _miles(str(abs(_redondeo_js(v))))) + NBSP + "%"


def pct_abs(v, d: int = 0) -> str:
    if v is None:
        return "—"
    return (_f(v, 1) if d else _miles(str(abs(_redondeo_js(v))))) + NBSP + "%"


def _r(x, d: int = 1):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    v = round(float(x), d)
    return int(v) if d == 0 else v


# ------------------------------------------------------------------ avisos (los mismos que la ficha)
def error_propio(bt: list | None) -> dict | None:
    """Error del radar en sus propias previsiones hechas con 2 o más cursos de antelación (como la ficha)."""
    propios = [(r[3] / r[2] - 1) * 100 for r in (bt or []) if r[1] >= 2 and r[2] is not None and r[2] > 0 and r[3] is not None]
    if len(propios) < 3:
        return None
    return {"n": len(propios), "mediana_abs_pct": statistics.median(abs(x) for x in propios),
            "media_pct": sum(propios) / len(propios)}


def avisos(m: dict, resumen: dict, ultimo_anio_nacidos: int) -> list[dict]:
    """Avisos de fiabilidad de la ficha: [{tipo, etapa, texto}]. etapa es "1o", "infantil" o None (general)."""
    def aviso(tipo, etapa, texto):
        return {"tipo": tipo, "etapa": etapa, "texto": texto}
    if not m["col"]:
        return [aviso("sin_colegio", None,
                      f"No tiene colegio de primaria: sus niños se escolarizan en municipios vecinos y cuentan en las previsiones "
                      f"de esos municipios. En {ultimo_anio_nacidos} nacieron aquí {ent(m['nac'][-1])} niños.")]
    out = []
    if m.get("g") == "pequeño":
        md = resumen["backtest_1o"]["mdape"]["pequeño"]
        out.append(aviso("municipio_pequeno", "1o",
                         f"Municipio pequeño: con tan pocos alumnos, dos o tres familias cambian mucho el porcentaje. En este grupo "
                         f"el error mediano del método va del {pct_abs(_clave(md, 1)['radar'], 1)} al "
                         f"{pct_abs(_clave(md, 6)['radar'], 1)}, y por eso el intervalo es ancho. "
                         f"Conviene leerlo junto a los municipios de su zona."))
    e = error_propio(m.get("bt"))
    if e and e["mediana_abs_pct"] > 15:
        out.append(aviso("error_propio_alto", "1o",
                         f"Aquí el radar ha fallado bastante en el pasado: error mediano del {pct_abs(e['mediana_abs_pct'], 1)} en sus "
                         f"{e['n']} previsiones hechas con dos o más cursos de antelación, y en media "
                         f"{'se quedó corto' if e['media_pct'] < 0 else 'se pasó'} ({pct(e['media_pct'], 1)}). El intervalo es el de "
                         f"su grupo de tamaño y no recoge ese sesgo propio: tómalo con cautela."))
    if m.get("pi") and m.get("gi") == "pequeño":
        out.append(aviso("infantil_pequeno", "infantil",
                         "En infantil, en los municipios pequeños, el método no mejora a suponer que nada cambia: tómalo como orientativo."))
    return out


def lectura_censo(cen) -> str | None:
    if cen is None:
        return None
    if cen >= 105:
        return ("Llegan familias con niños pequeños. En municipios así el método tiende a quedarse corto: el dato real puede "
                "acercarse al extremo alto del intervalo.")
    if cen <= 95:
        return "Se van más familias con niños pequeños de las que llegan."
    return "La población infantil se mueve poco respecto a los nacimientos."


# ------------------------------------------------------------------ piezas
def _clave(d: dict, k):
    """Los diccionarios del resumen llegan con claves int (en memoria) o str (leídos de JSON)."""
    return d.get(k, d.get(str(k))) if isinstance(d, dict) else None


def _por_h(d: dict | None) -> dict | None:
    return None if d is None else {str(k): v for k, v in d.items()}


def _r3(x):
    """3 decimales con el redondeo de numpy, el mismo que resultados/proyeccion_*.csv (Series.round)."""
    return _r(np.round(x, 3), 3)


def _prevision(filas: pd.DataFrame, nacidos_col: str) -> list[dict]:
    out = []
    for x in filas.sort_values("t").itertuples():
        base = x.alumnos_base
        cambio = (lambda v: _r((v / base - 1) * 100)) if base and base > 0 else (lambda v: None)
        out.append({"curso": x.curso, "t": int(x.t), "h": int(x.h), nacidos_col: _r(getattr(x, nacidos_col), 0),
                    "prevision": _r3(x.prevision), "p10": _r3(x.p10), "p90": _r3(x.p90),
                    "cambio_pct": cambio(x.prevision), "cambio_p10": cambio(x.p10), "cambio_p90": cambio(x.p90),
                    "n_residuos": int(x.n_residuos)})
    return out


def _serie(cursos: list[int], valores: list | None, etiqueta) -> list[dict]:
    return [{"curso": etiqueta(s), "t": s, "alumnos": v} for s, v in zip(cursos, valores or [])]


def _etiqueta(s: int) -> str:
    return f"{s}/{str(s + 1)[-2:]}"


def _municipio(cm: str, m: dict, salida: dict, P: dict, PI: dict, falla: dict, url_ficha: str) -> dict:
    res = salida["resumen"]
    cursos = salida["cursos_y"]
    ult_nac = salida["nac_desde"] + len(m["nac"]) - 1
    out = {
        "cmun": cm, "municipio": m["n"], "zona": m["z"], "tiene_colegio": bool(m["col"]),
        "poblacion": {"anio": salida["anio_pob"], "habitantes": m.get("pob")},
        "base": salida["base"], "ficha_web": url_ficha,
        "nacidos": [{"anio": salida["nac_desde"] + k, "nacidos": v} for k, v in enumerate(m["nac"])],
    }
    if m["col"] and m.get("cen") is not None:  # como la ficha: solo en municipios con colegio
        out["senal_llegada_familias"] = {"anio_censo": salida["anio_censo"], "ninos_0_4": m.get("cen_n"),
                                         "ninos_0_4_por_100_nacidos": m["cen"],
                                         "nacidos_desde": salida["anio_censo"] - 5, "nacidos_hasta": salida["anio_censo"] - 1,
                                         "lectura": lectura_censo(m["cen"])}
    if m["col"]:
        p1 = P[cm]
        out["primero_primaria"] = {
            "grupo": m.get("g"), "alumnos_base": _r(p1.alumnos_base.iloc[0], 0),
            "factor": m.get("f"), "tipo_factor": p1.tipo_factor.iloc[0],
            "serie_observada": _serie(cursos, m.get("y1"), _etiqueta),
            "prevision": _prevision(p1, "nacidos"),
        }
        if cm in PI:
            pi = PI[cm]
            out["infantil_3_5"] = {
                "grupo": m.get("gi"), "alumnos_base": _r(pi.alumnos_base.iloc[0], 0), "factor": _r(pi.factor.iloc[0], 3),
                "serie_observada": _serie(cursos, m.get("inf"), _etiqueta),
                "prevision": _prevision(pi, "nacidos_3_cohortes"),
            }
        g = m.get("g")
        g_int = "grande" if g == "Madrid capital" else g
        e = error_propio(m.get("bt"))
        ult = out["primero_primaria"]["prevision"][-1]
        fi = {
            "grupo": g,
            "error_mediano_grupo_pct": _por_h(_clave(res["backtest_1o"]["mdape"], g)),
            "sesgo_grupo_pct": _por_h(_clave(res["backtest_1o"]["sesgo_radar"], g)),
            "grupo_intervalos": g_int,
            "cobertura_intervalos_grupo_pct": _clave(res["cobertura_intervalos_1o_pct"], g_int),
            "ancho_intervalo_ultimo_curso_pct": _r((ult["p90"] - ult["p10"]) / ult["prevision"] * 100) if ult["prevision"] else None,
            "error_propio": None if e is None else {"n": e["n"], "mediana_abs_pct": _r(e["mediana_abs_pct"]),
                                                    "media_pct": _r(e["media_pct"])},
            "donde_falla": falla.get(cm),
            "previsiones_pasadas": [
                {"b": r[0], "curso_base": _etiqueta(r[0]), "h": r[1], "t": r[0] + r[1], "curso": _etiqueta(r[0] + r[1]),
                 "y": r[2], "prevision": r[3], "p_naive": r[4],
                 "error_pct": _r((r[3] / r[2] - 1) * 100) if r[2] and r[3] is not None else None,
                 "error_naive_pct": _r((r[4] / r[2] - 1) * 100) if r[2] and r[4] is not None else None}
                for r in sorted(m.get("bt") or [], key=lambda r: (r[0] + r[1], r[1]))],
            "avisos": avisos(m, res, ult_nac),
        }
        if "infantil_3_5" in out:
            fi["infantil"] = {"grupo": m.get("gi"),
                              "error_mediano_grupo_pct": _por_h(_clave(res["backtest_infantil"]["mdape"], m.get("gi")))}
        out["fiabilidad"] = fi
    else:
        out["fiabilidad"] = {"avisos": avisos(m, res, ult_nac)}
    if cm == CAPITAL:
        out["notas"] = ["No se puede bajar a los distritos: el catálogo regional no publica nacimientos por distrito, aunque sí el alumnado."]
    return out


def _region(salida: dict, ranking: pd.DataFrame) -> dict:
    res, reg = salida["resumen"], salida["region"]
    p1, pi, larga = res["proyeccion_1o"], res["proyeccion_infantil"], res["region_serie_larga"]
    return {
        "base": salida["base"], "intervalo": INTERVALO,
        "primero_primaria": {
            "real_base": p1["real_base"],
            "serie_observada": [{"curso": _etiqueta(s), "t": s, "alumnos": v, "provisional": s in reg["provisionales"]}
                                for s, v in sorted(reg["y1"].items())],
            "prevision": p1["region"],
            "nota_intervalo": "El intervalo del total regional sale de los errores de la serie regional larga "
                              f"({_etiqueta(larga['cursos'][0])}-{_etiqueta(larga['cursos'][1])}), que incluye cambios de ciclo migratorio.",
            "comprobacion_fuera_de_muestra": p1["comprobacion_fuera_de_muestra"],
            "capital": p1["capital"], "resto": p1["resto"], "por_area_cambio_pct": p1["por_area_cambio_pct"],
            "municipios_con_colegio": p1["municipios_con_colegio"], "municipios_que_caen": p1["municipios_que_caen"],
        },
        "infantil_3_5": {
            "real_base": pi["real_base"],
            "prevision": pi["region"],
            "nota_intervalo": "El radar no calcula intervalo para el total regional de infantil; los intervalos de infantil "
                              "son por municipio (municipios/{cmun}.json).",
        },
        "nacidos": [{"anio": a, "nacidos": v} for a, v in sorted(reg["nac"].items())],
        "ranking_1o": {
            "curso": res["ranking"]["curso"],
            "criterio": f"Municipios con 100 alumnos de 1º o más en {salida['base']}, ordenados por el cambio previsto "
                        f"de {salida['base']} a {res['ranking']['curso']}.",
            "municipios": [{k: (None if pd.isna(v) else int(v) if k in ("alumnos_base", "nacidos") else v) for k, v in fila.items()}
                           for fila in ranking.reset_index().to_dict(orient="records")],
        },
    }


def _plano(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(", ", ": "), default=float)


def _json(obj, nivel: int = 0) -> str:
    """JSON legible y compacto: los objetos y listas sin nada anidado van en una sola línea."""
    hijos = obj.values() if isinstance(obj, dict) else obj if isinstance(obj, list) else ()
    if not any(isinstance(v, (dict, list)) for v in hijos):
        return _plano(obj)
    sang, dentro = "  " * nivel, "  " * (nivel + 1)
    if isinstance(obj, dict):
        partes = [f"{dentro}{_plano(str(k))}: {_json(v, nivel + 1)}" for k, v in obj.items()]
        return "{\n" + ",\n".join(partes) + f"\n{sang}}}"
    return "[\n" + ",\n".join(dentro + _json(v, nivel + 1) for v in obj) + f"\n{sang}]"


def _escribir(ruta: pathlib.Path, obj) -> None:
    ruta.write_text(_json(obj) + "\n", encoding="utf-8")


def exportar_api(salida: dict, P: pd.DataFrame, PI: pd.DataFrame, destino: pathlib.Path = WEB_API) -> pathlib.Path:
    """Escribe index.json, region.json y municipios/{cmun}.json a partir del mismo diccionario que radar.js."""
    lee = dict(dtype={"cmun": str}, keep_default_na=True)
    falla = {r.pop("cmun"): {k: (None if pd.isna(v) else v) for k, v in r.items() if k not in ("municipio", "zona")}
             for r in pd.read_csv(RESULTADOS / "donde_falla_por_municipio.csv", **lee).to_dict(orient="records")}
    for d in falla.values():
        d.update(horizontes=[2, 4], anio_censo=salida["resumen"]["donde_falla"]["anio_censo"],
                 definicion="Error medio con signo (err_medio) y en valor absoluto (ape_medio), en % del real, de las previsiones "
                            "de 1º hechas con 2 a 4 cursos de antelación en el backtest. Solo municipios con 50 alumnos de 1º o más.")
    ranking = pd.read_csv(RESULTADOS / "ranking_ultimo_curso.csv", **lee).set_index("cmun")
    # selección y orden del CSV; previsión e intervalo con la precisión de proyeccion_1o_primaria.csv (3 decimales),
    # para que al redondear a enteros salga lo mismo que en la ficha y en la web
    ult = P[P.t == P.t.max()].set_index("cmun")
    for c in ("prevision", "p10", "p90"):
        ranking[c] = ult.loc[ranking.index, c].round(3)
    porP = {m: g for m, g in P.groupby("cmun")}
    porPI = {m: g for m, g in PI.groupby("cmun")}

    dir_m = destino / "municipios"
    if dir_m.exists():
        shutil.rmtree(dir_m)  # sin ficheros huérfanos si cambia la lista de municipios
    dir_m.mkdir(parents=True)

    munis = salida["municipios"]
    lista, fichas = [], {}
    for cm in sorted(munis, key=lambda c: munis[c]["n"]):
        m = munis[cm]
        fichas[cm] = _municipio(cm, m, salida, porP, porPI, falla, f"{URL_WEB}/#municipio={cm}")
        _escribir(dir_m / f"{cm}.json", fichas[cm])
        lista.append({"cmun": cm, "municipio": m["n"], "zona": m["z"], "tiene_colegio": bool(m["col"]),
                      "url": f"{URL_API}/municipios/{cm}.json"})
    _escribir(destino / "region.json", _region(salida, ranking))
    exportar_sdm(fichas, destino / "sdm", URL_API, _escribir)  # las mismas cifras en Smart Data Models (FIWARE)

    manif = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    descargas = sorted(f["fecha_descarga_utc"] for f in manif["recursos"])
    index = {
        "nombre": "Radar de natalidad municipal · API abierta",
        "descripcion": "Previsión de alumnos de 1º de primaria e infantil (3 a 5 años) en cada municipio de la Comunidad de "
                       "Madrid, con intervalos del 80 % calibrados con un backtest. Ficheros JSON estáticos: sin claves ni registro.",
        "version": VERSION_API, "version_radar": __version__,
        "generado_utc": salida["generado_utc"],
        "datos": {"curso_base": salida["base"], "cursos_prevision_1o": salida["cursos_p1"],
                  "cursos_prevision_infantil": salida["cursos_pi"],
                  "ultimo_anio_nacidos": salida["resumen"]["proyeccion_1o"]["ultimo_ano_nacidos"],
                  "descarga_fuentes_utc": [descargas[0], descargas[-1]]},
        "licencias": {
            "datos": {"nombre": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/deed.es",
                      "atribucion": "Radar de natalidad municipal, a partir de datos abiertos de la Comunidad de Madrid "
                                    "(datos.comunidad.madrid)."},
            "codigo": {"nombre": "MIT", "url": f"{REPO}/blob/master/LICENSE"},
            "datos_de_origen": "Comunidad de Madrid, licencia Creative Commons Attribution según los metadatos de cada dataset.",
        },
        "intervalo": INTERVALO,
        "url_base": URL_API + "/",
        "endpoints": {"index": "index.json", "region": "region.json", "municipio": "municipios/{cmun}.json",
                      "sdm_observaciones_1o": "sdm/observaciones_1o.json"},
        "documentacion": f"{REPO}/blob/master/docs/API.md",
        "web": URL_WEB, "repositorio": REPO,
        "portal": manif.get("portal"),
        "fuentes": manif["recursos"],
        "municipios": lista,
    }
    _escribir(destino / "index.json", index)
    print(f"api: {destino} (index.json, region.json y {len(lista)} municipios)")
    return destino
