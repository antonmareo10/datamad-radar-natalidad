"""Tests del modelo de cohortes y del backtest con datos sintéticos cuyo resultado se conoce."""
import numpy as np
import pandas as pd
import pytest

from radar import backtest as BT
from radar import modelo as M

CURSOS = list(range(2018, 2025))
ANIOS = list(range(2005, 2025))


def sintetico(factor_a=1.10, factor_b=0.90, factor_inf_a=None):
    """Dos municipios con colegio (A, B) y uno sin colegio (C).

    Los alumnos de 1º son exactamente factor × nacidos seis años antes, y los de infantil,
    factor × nacidos de las tres cohortes, así que un método de cohorte bien hecho no debe fallar.
    """
    rng = np.random.default_rng(0)
    B = pd.DataFrame({a: {"28001": 1000 - 20 * (a - 2005) + rng.integers(-30, 30),
                          "28002": 300 + 5 * (a - 2005) + rng.integers(-10, 10),
                          "28003": 20} for a in ANIOS})
    f = {"28001": factor_a, "28002": factor_b}
    fi = {"28001": factor_inf_a or factor_a, "28002": factor_b}
    Y1 = pd.DataFrame({s: {m: f[m] * B.at[m, s - 6] for m in f} for s in CURSOS})
    INF2 = pd.DataFrame({s: {m: fi[m] * B.loc[m, [s - 5, s - 4, s - 3]].sum() for m in f} for s in CURSOS})
    zona = pd.Series({"28001": "Sur", "28002": "Sur"})
    return B, Y1, INF2, zona


def test_cohortes():
    assert M.cohorte_1o(2030) == 2024
    assert M.cohortes_infantil(2027) == [2022, 2023, 2024]


def test_factor_infantil_y_correccion():
    B, Y1, INF2, zona = sintetico()
    b = 2024
    fac = M.factores_base(Y1, INF2, B, zona, b, 2018)
    assert fac.loc["28001", "finf"] == pytest.approx(1.10)
    assert fac.loc["28002", "finf"] == pytest.approx(0.90)
    # la razón regional de 1º incluye en el denominador al municipio sin colegio
    reg = Y1[b].sum() / B[b - 6].sum()
    assert fac.loc["28001", "reg"] == pytest.approx(reg)
    r_inf = INF2[b].sum() / B[[b - 5, b - 4, b - 3]].sum().sum()
    assert fac.loc["28001", "kinf"] == pytest.approx(reg / r_inf)


def test_metodo_de_cohortes_acierta_cuando_la_razon_es_estable():
    B, Y1, INF2, zona = sintetico()
    bt = BT.backtest_primero(Y1, INF2, B, zona)
    err = (bt.p_f3 - bt.y).abs() / bt.y
    assert err.max() < 1e-9  # la razón de 1º es constante: error cero
    # el ingenuo falla en cuanto la cohorte cambia de tamaño
    assert ((bt.p_naive - bt.y).abs() / bt.y).max() > 0.05


def test_correccion_regional_quita_el_sesgo_entre_infantil_y_1o():
    # infantil escolariza un 10 % más que 1º en A: (b4) sobreestima, (b5) lo corrige en media regional
    B, Y1, INF2, zona = sintetico(factor_a=1.0, factor_b=1.0, factor_inf_a=1.1)
    INF2.loc["28002"] = INF2.loc["28002"] * 1.1
    bt = BT.backtest_primero(Y1, INF2, B, zona)
    sesgo_b4 = (bt.p_finf - bt.y).sum() / bt.y.sum()
    sesgo_b5 = (bt.p_finfk - bt.y).sum() / bt.y.sum()
    assert sesgo_b4 == pytest.approx(0.10, abs=0.01)
    assert abs(sesgo_b5) < abs(sesgo_b4)


def test_sin_fuga_del_futuro():
    """Cambiar todo lo posterior a la base no puede cambiar ninguna previsión hecha en esa base."""
    B, Y1, INF2, zona = sintetico()
    b = 2020
    bt = BT.backtest_primero(Y1, INF2, B, zona)
    B2, Y12, INF22 = B.copy(), Y1.copy(), INF2.copy()
    B2.loc[:, [a for a in ANIOS if a > b]] *= 3
    Y12.loc[:, [s for s in CURSOS if s > b]] *= 5
    INF22.loc[:, [s for s in CURSOS if s > b]] *= 7
    bt2 = BT.backtest_primero(Y12, INF22, B2, zona)
    cols = [c for c in bt.columns if c.startswith("p_")]
    a = bt[bt.b == b].set_index(["cmun", "h"])[cols]
    c = bt2[bt2.b == b].set_index(["cmun", "h"])[cols]
    pd.testing.assert_frame_equal(a, c)


def test_prever_rechaza_cohortes_no_nacidas():
    B, Y1, INF2, zona = sintetico()
    f = pd.Series({"28001": 1.0, "28002": 1.0})
    M.prever_1o(B, f, 2024, 2030)  # nacidos en 2024: permitido
    with pytest.raises(M.FugaDelFuturo):
        M.prever_1o(B, f, 2024, 2031)
    M.prever_infantil(B, f, 2024, 2027)
    with pytest.raises(M.FugaDelFuturo):
        M.prever_infantil(B, f, 2024, 2028)


def test_factor_de_respaldo_si_no_hay_infantil():
    B, Y1, INF2, zona = sintetico()
    INF2 = INF2.drop(index="28002")
    fac = M.factores_base(Y1, INF2, B, zona, 2024, 2018)
    f, tipo = M.factor_proyeccion(fac)
    assert tipo["28002"] == "1º de primaria, 3 cursos"
    assert f["28002"] == pytest.approx(0.90)
    assert tipo["28001"] == "infantil 3-5 corregido"


def test_backtest_infantil_horizonte_maximo():
    B, Y1, INF2, zona = sintetico()
    bi = BT.backtest_infantil(INF2, B)
    assert bi.h.max() == 3
    assert (bi.t - 3 <= bi.b).all()  # la cohorte más joven ya había nacido en la base
    assert ((bi.p_f1 - bi.y).abs() / bi.y).max() < 1e-9


def test_backtest_region():
    B, Y1, INF2, zona = sintetico()
    r1 = Y1.sum()
    R = BT.backtest_region(r1, B)
    assert (R.t - 6 <= R.b).all()
    fila = R[(R.b == 2018) & (R.h == 1)].iloc[0]
    breg = B.sum()
    assert fila.p_f1 == pytest.approx(breg[2013] * r1[2018] / breg[2012])
