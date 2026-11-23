"""API abierta estática (radar/api.py): formato y avisos como la web, y JSON generados fieles a resultados/."""
import json

import pandas as pd
import pytest

from radar import api as A
from radar.config import MANIFIESTO, RESULTADOS, WEB_API, WEB_DATOS

NBSP = " "


# ------------------------------------------------------------------ formato: el de web/app.js
def test_enteros_como_math_round():
    assert A.ent(1074.5) == "1.075"
    assert A.ent(1074.49) == "1.074"
    assert A.ent(-2.5) == "−2"          # Math.round(-2.5) = -2
    assert A.ent(999) == "999"
    assert A.ent(58859) == "58.859"
    assert A.ent(None) == "—"


def test_porcentajes_como_la_web():
    assert A.pct(-35.9, 1) == "−35,9" + NBSP + "%"
    assert A.pct(12.04, 1) == "+12,0" + NBSP + "%"
    assert A.pct(0.00001) == "0" + NBSP + "%"
    assert A.pct(-26.5) == "−26" + NBSP + "%"     # signo del valor, Math.round del número
    assert A.pct_abs(38.9, 1) == "38,9" + NBSP + "%"
    assert A._f(2.675, 2) == "2,68"  # Intl redondea la representación corta, no el binario (2.67499...)


# ------------------------------------------------------------------ avisos
RESUMEN = {"backtest_1o": {"mdape": {"pequeño": {1: {"radar": 14.7}, 6: {"radar": 22.5}}}}}


def _muni(**kw):
    m = {"n": "X", "col": True, "nac": [10, 12], "g": "mediano", "gi": "mediano", "pi": [[1, 1, 1]], "bt": []}
    m.update(kw)
    return m


def test_sin_avisos_si_todo_normal():
    assert A.avisos(_muni(), RESUMEN, 2024) == []


def test_aviso_sin_colegio():
    (a,) = A.avisos(_muni(col=False, nac=[3, 7]), RESUMEN, 2024)
    assert a["tipo"] == "sin_colegio" and a["etapa"] is None
    assert a["texto"].endswith("En 2024 nacieron aquí 7 niños.")


def test_aviso_pequeno_usa_el_error_de_su_grupo():
    (a,) = A.avisos(_muni(g="pequeño"), RESUMEN, 2024)
    assert a["tipo"] == "municipio_pequeno" and a["etapa"] == "1o"
    assert "del 14,7" + NBSP + "% al 22,5" + NBSP + "%" in a["texto"]


def test_aviso_infantil_pequeno_solo_con_prevision_de_infantil():
    assert [a["tipo"] for a in A.avisos(_muni(gi="pequeño"), RESUMEN, 2024)] == ["infantil_pequeno"]
    assert A.avisos(_muni(gi="pequeño", pi=None), RESUMEN, 2024) == []


def test_error_propio_como_la_ficha():
    # filas [base, h, real, radar, ingenuo]; la de h = 1 no cuenta y con menos de 3 no hay aviso
    bt = [[2018, 1, 100, 10, 100], [2018, 2, 100, 60, 100], [2019, 2, 100, 70, 100], [2018, 3, 100, 120, 100]]
    e = A.error_propio(bt)
    assert e["n"] == 3 and e["mediana_abs_pct"] == pytest.approx(30) and e["media_pct"] == pytest.approx(-50 / 3)
    (a,) = A.avisos(_muni(bt=bt), RESUMEN, 2024)
    assert a["tipo"] == "error_propio_alto"
    assert "error mediano del 30,0" + NBSP + "% en sus 3 previsiones" in a["texto"] and "se quedó corto (−16,7" in a["texto"]
    assert A.error_propio(bt[:3]) is None


def test_json_compacto_es_json_valido():
    obj = {"a": 1, "b": [{"x": 1, "y": None}, {"x": 2, "y": "ñ"}], "c": {"d": [1, 2]}, "e": []}
    txt = A._json(obj)
    assert json.loads(txt) == obj
    assert '{"x": 1, "y": null}' in txt and '"d": [1, 2]' in txt


# ------------------------------------------------------------------ los JSON generados (web/api/v1)
hay_api = pytest.mark.skipif(not (WEB_API / "index.json").exists(), reason="sin API generada: python -m radar web")


def _leer(ruta):
    return json.loads((WEB_API / ruta).read_text(encoding="utf-8"))


@hay_api
def test_indice_y_ficheros():
    idx = _leer("index.json")
    assert idx["fuentes"] == json.loads(MANIFIESTO.read_text(encoding="utf-8"))["recursos"]
    assert idx["licencias"]["datos"]["nombre"] == "CC BY 4.0" and idx["licencias"]["codigo"]["nombre"] == "MIT"
    cms = [m["cmun"] for m in idx["municipios"]]
    assert len(cms) == len(set(cms))
    assert sorted(p.stem for p in (WEB_API / "municipios").glob("*.json")) == sorted(cms)
    for m in idx["municipios"]:
        assert m["url"].endswith(f"/api/v1/municipios/{m['cmun']}.json")
    con = sum(m["tiene_colegio"] for m in idx["municipios"])
    assert con == json.loads((RESULTADOS / "resumen.json").read_text(encoding="utf-8"))["proyeccion_1o"]["municipios_con_colegio"]


@hay_api
@pytest.mark.parametrize("csv,bloque", [("proyeccion_1o_primaria.csv", "primero_primaria"),
                                         ("proyeccion_infantil_3_5.csv", "infantil_3_5")])
def test_previsiones_identicas_a_resultados(csv, bloque):
    P = pd.read_csv(RESULTADOS / csv, dtype={"cmun": str})
    for cm, g in P.groupby("cmun"):
        prev = {p["t"]: p for p in _leer(f"municipios/{cm}.json")[bloque]["prevision"]}
        assert set(prev) == set(g.t)
        for r in g.itertuples():
            p = prev[r.t]
            assert (p["prevision"], p["p10"], p["p90"]) == (r.prevision, r.p10, r.p90)
            assert p["p10"] <= p["prevision"] <= p["p90"]
            assert p["cambio_pct"] == pytest.approx((r.prevision / r.alumnos_base - 1) * 100, abs=0.051)


@hay_api
def test_region_y_ranking_identicos_a_resultados():
    reg, res = _leer("region.json"), json.loads((RESULTADOS / "resumen.json").read_text(encoding="utf-8"))
    assert reg["primero_primaria"]["prevision"] == res["proyeccion_1o"]["region"]
    assert reg["infantil_3_5"]["prevision"] == res["proyeccion_infantil"]["region"]
    rk = pd.read_csv(RESULTADOS / "ranking_ultimo_curso.csv", dtype={"cmun": str})
    filas = reg["ranking_1o"]["municipios"]
    assert [f["cmun"] for f in filas] == list(rk.cmun)
    assert [f["cambio_pct"] for f in filas] == list(rk.cambio_pct)
    # redondeadas a entero, las del ranking de la API coinciden con las del resumen (las que enseña la web)
    por_nombre = {f["municipio"]: f for f in filas}
    for r in res["ranking"]["mas_caen"] + res["ranking"]["mas_suben"]:
        f = por_nombre[r["municipio"]]
        assert [A.ent(f[k]) for k in ("prevision", "p10", "p90")] == [A.ent(r[k]) for k in ("prevision", "p10", "p90")]


@hay_api
def test_error_por_municipio_identico_a_donde_falla():
    df = pd.read_csv(RESULTADOS / "donde_falla_por_municipio.csv", dtype={"cmun": str})
    for r in df.itertuples():
        d = _leer(f"municipios/{r.cmun}.json")["fiabilidad"]["donde_falla"]
        assert (d["err_medio"], d["ape_medio"]) == (r.err_medio, r.ape_medio)


@hay_api
def test_api_y_web_dan_las_mismas_cifras():
    txt = (WEB_DATOS / "radar.js").read_text(encoding="utf-8")
    R = json.loads(txt[txt.index("=") + 1:].rstrip().rstrip(";"))
    for cm, m in R["municipios"].items():
        d = _leer(f"municipios/{cm}.json")
        assert d["municipio"] == m["n"] and d["tiene_colegio"] == m["col"]
        if m["col"]:
            assert [[p["prevision"], p["p10"], p["p90"]] for p in d["primero_primaria"]["prevision"]] == m["p1"]
            assert [s["alumnos"] for s in d["primero_primaria"]["serie_observada"]] == m["y1"]
        if m.get("pi"):
            assert [[p["prevision"], p["p10"], p["p90"]] for p in d["infantil_3_5"]["prevision"]] == m["pi"]
