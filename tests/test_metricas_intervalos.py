import numpy as np
import pandas as pd
import pytest

from radar import backtest as BT
from radar import intervalos as I


def test_metricas_a_mano():
    g = pd.DataFrame({"y": [100.0, 200.0, 50.0, 0.0], "p": [110.0, 180.0, 50.0, 7.0]})
    m = BT.metricas(g, ["p"])
    assert m["n"] == 3  # la fila con 0 alumnos reales no cuenta
    assert m["p|MAPE"] == pytest.approx((10 + 10 + 0) / 3)
    assert m["p|MdAPE"] == pytest.approx(10)
    assert m["p|WAPE"] == pytest.approx((10 + 20 + 0) / 350 * 100)
    assert m["p|sesgo"] == pytest.approx((10 - 20 + 0) / 350 * 100)


def test_grupo_tamano():
    s = pd.Series({"28079": 25000, "28005": 2000, "28006": 120, "28007": 30, "28008": np.nan})
    g = BT.grupo_tamano(s)
    assert g.to_dict() == {"28079": "Madrid capital", "28005": "grande", "28006": "mediano",
                           "28007": "pequeño", "28008": "pequeño"}
    assert BT.grupo_tamano(pd.Series({"28005": 249}))["28005"] == "mediano"
    assert BT.grupo_tamano(pd.Series({"28005": 250}))["28005"] == "grande"


def _res(n=200, sd=0.1, g="grande"):
    rng = np.random.default_rng(1)
    return pd.DataFrame({"g": g, "h": rng.integers(1, 7, n), "b": rng.integers(2018, 2024, n),
                         "lr": rng.normal(0, sd, n)})


def test_cuantiles_y_vecinos():
    res = _res()
    lo, hi, n = I.cuantiles(res, "grande", 3)
    sel = res[(res.h - 3).abs() <= 1]
    assert n == len(sel)
    assert lo == pytest.approx(sel.lr.quantile(0.1))
    assert hi == pytest.approx(sel.lr.quantile(0.9))
    assert lo < 0 < hi
    assert I.cuantiles(res, "otro", 3) == (pytest.approx(np.nan, nan_ok=True), pytest.approx(np.nan, nan_ok=True), 0)


def test_intervalo_mas_ancho_si_el_error_pasado_es_mayor():
    res = pd.concat([_res(sd=0.05, g="grande"), _res(sd=0.30, g="pequeño")])
    lo_g, hi_g, _ = I.cuantiles(res, "grande", 2)
    lo_p, hi_p, _ = I.cuantiles(res, "pequeño", 2)
    assert (hi_p - lo_p) > 3 * (hi_g - lo_g)
    a, b = I.intervalo(100.0, lo_p, hi_p)
    assert a < 100 < b


def test_residuos_capital_usa_grandes():
    df = pd.DataFrame({"y": [100, 50, 0], "p": [90, 60, 5], "grupo": ["Madrid capital", "pequeño", "grande"], "h": 1, "b": 2020})
    r = I.residuos(df, "p")
    assert list(r.g) == ["grande", "pequeño"]
    assert r.lr.iloc[0] == pytest.approx(np.log(100 / 90))


def test_cobertura_cerca_del_80_en_datos_estables():
    res = _res(n=3000)
    c = I.cobertura_validada(res)
    assert 75 < c.loc["todos", "cobertura_pct"] < 85
