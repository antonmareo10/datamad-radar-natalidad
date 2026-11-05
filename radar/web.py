"""Exporta lo que necesita la web estática a web/datos/radar.js (un único fichero, sin servidor).

Se usa un .js con `window.RADAR = {...}` y no un .json para que la página funcione abriéndola
directamente desde la carpeta (file://), donde los navegadores bloquean fetch().
"""
from __future__ import annotations

import datetime as dt
import json
import math
import pathlib

import numpy as np

from . import cargar as C
from . import modelo as M
from .calcular import calcular, ruta
from .config import CAPITAL, ESPEC_1O, MANIFIESTO, WEB_DATOS
from .geo import construir_mapa


def _n(x, d=1):
    if x is None:
        return None
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        if isinstance(x, (np.floating,)) and not np.isfinite(x):
            return None
    except TypeError:
        return None
    v = round(float(x), d)
    return int(v) if d == 0 else v


def exportar(datos: pathlib.Path) -> pathlib.Path:
    r = calcular(datos)
    D, bt, P, PI = r["D"], r["bt"], r["P"], r["PI"]
    B, Y1, INF2, zona, nombres, censo, pob = D["B"], D["Y1"], D["INF2"], D["zona"], D["nombres"], D["censo"], D["pob"]
    b = int(max(Y1.columns))
    cursos_y = sorted(int(s) for s in Y1.columns)
    anio_pob = int(max(pob.columns))
    anio_censo = int(censo.index.get_level_values("anio").max())
    mapa = construir_mapa(ruta(datos, "limites"))
    sin_geo = sorted(set(B.index) - set(mapa["municipios"]))
    assert not sin_geo, f"municipios sin geometría: {sin_geo}"

    p1 = {m: g.sort_values("t") for m, g in P.groupby("cmun")}
    pinf = {m: g.sort_values("t") for m, g in PI.groupby("cmun")}
    bt_m = {m: g for m, g in bt[bt[ESPEC_1O].notna() & bt.y.notna()].groupby("cmun")}
    grupo1 = P.drop_duplicates("cmun").set_index("cmun")["grupo"]
    grupo_i = PI.drop_duplicates("cmun").set_index("cmun")["grupo"]

    munis = {}
    for m in sorted(B.index):
        e = {
            "n": nombres.get(m), "z": D["zona_todas"].get(m), "pob": _n(pob.at[m, anio_pob] if m in pob.index else None, 0),
            "nac": [_n(B.at[m, a], 0) for a in range(2008, int(max(B.columns)) + 1)],
            "col": m in Y1.index,
        }
        if (m, anio_censo) in censo.index:
            n04 = M.suma_nacidos(B, m, range(anio_censo - 5, anio_censo))
            e["cen"] = _n(censo.at[(m, anio_censo), "p04"] / n04 * 100 if n04 and n04 > 0 else None, 0)
            e["cen_n"] = _n(censo.at[(m, anio_censo), "p04"], 0)
        if m in Y1.index:
            e["g"] = grupo1.get(m)
            e["y1"] = [_n(M.valor(Y1, m, s), 0) for s in cursos_y]
            e["p1"] = [[_n(x.prevision), _n(x.p10), _n(x.p90)] for x in p1[m].itertuples()]
            e["f"] = _n(p1[m].factor.iloc[0], 3)
            if m in bt_m:
                g = bt_m[m].sort_values(["t", "h"])
                e["bt"] = [[int(x.b), int(x.h), _n(x.y, 0), _n(getattr(x, ESPEC_1O), 1), _n(x.p_naive, 0)] for x in g.itertuples()]
        if m in INF2.index:
            e["gi"] = grupo_i.get(m)
            e["inf"] = [_n(M.valor(INF2, m, s), 0) for s in cursos_y]
            if m in pinf:
                e["pi"] = [[_n(x.prevision), _n(x.p10), _n(x.p90)] for x in pinf[m].itertuples()]
        munis[m] = e

    res = r["resumen"]
    r1 = D["r1"]
    region = {
        "y1": {int(s): int(v) for s, v in r1.items()},
        "provisionales": [int(s) for s in D["prov"]],
        "nac": {int(a): int(B[a].sum()) for a in B.columns if a >= 1993},
        "p1": [[x["curso"], _n(x["prevision"], 0), _n(x["p10"], 0), _n(x["p90"], 0)] for x in res["proyeccion_1o"]["region"]],
        "suma_municipios_base": int(Y1[b].sum()),
    }
    manif = json.loads(MANIFIESTO.read_text(encoding="utf-8"))["recursos"]
    fuentes = [{k: e[k] for k in ("clave", "titulo", "recurso", "editor", "pagina", "url", "fecha_descarga_utc", "licencia_titulo",
                                  "modificado_en_portal", "uso")} for e in manif]
    salida = {
        "generado_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "base": C.etiqueta_curso(b), "base_s": b, "cursos_y": cursos_y,
        "cursos_p1": [C.etiqueta_curso(t) for t in sorted(P.t.unique())],
        "cursos_pi": [C.etiqueta_curso(t) for t in sorted(PI.t.unique())],
        "anio_pob": anio_pob, "anio_censo": anio_censo, "nac_desde": 2008,
        "resumen": res, "region": region, "municipios": munis, "fuentes": fuentes,
        "mapa": {"viewBox": mapa["viewBox"], "d": {m: v["d"] for m, v in mapa["municipios"].items()}},
        "capital": CAPITAL,
    }
    WEB_DATOS.mkdir(parents=True, exist_ok=True)
    out = WEB_DATOS / "radar.js"
    txt = json.dumps(salida, ensure_ascii=False, separators=(",", ":"), default=float)
    out.write_text("/* Generado por `python -m radar web`. No editar a mano. */\nwindow.RADAR=" + txt + ";\n", encoding="utf-8")
    print(f"web: {out} ({out.stat().st_size / 1024:.0f} KB, {len(munis)} municipios)")
    return out
