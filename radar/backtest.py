"""Backtest con origen móvil: se hace la previsión como si estuviéramos en el curso b y se compara
con lo que pasó de verdad en b + h. Ninguna previsión usa datos posteriores a su base.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import modelo as M
from .config import CAPITAL

ESPECS_1O = {
    "p_naive": "(c) ingenuo: los alumnos de 1º del curso base",
    "p_births": "(a) nacidos seis años antes",
    "p_births_reg": "(a') nacidos × razón regional alumnos/nacidos",
    "p_f1": "(b2) nacidos × razón de 1º del municipio, último curso",
    "p_f2": "(b2) ídem, dos últimos cursos",
    "p_f3": "(b2) ídem, tres últimos cursos",
    "p_f3s": "(b3) ídem tres cursos, contraída hacia su área (λ = 100 nacidos)",
    "p_finf": "(b4) nacidos × razón de infantil 3-5 del municipio",
    "p_finfk": "(b5) ídem (b4) × corrección regional 1º/infantil [elegida]",
    "p_combo": "(b6) media de (b2, tres cursos) y (b5)",
}
ESPECS_INF = {
    "p_naive": "(c) ingenuo: alumnos de infantil del curso base",
    "p_births": "(a) nacidos de las tres cohortes",
    "p_f1": "(b2) nacidos × razón de infantil del municipio, último curso [elegida]",
    "p_f3": "(b2) ídem, tres últimos cursos",
}
GRUPOS = ["Madrid capital", "grande", "mediano", "pequeño"]


def grupo_tamano(serie_inicial: pd.Series, cortes=(49, 249)) -> pd.Series:
    """Grupo fijo por tamaño en el primer curso (no usa información futura). La capital, aparte."""
    g = pd.cut(serie_inicial, [-1, cortes[0], cortes[1], 1e12], labels=["pequeño", "mediano", "grande"])
    g = g.astype(object).where(serie_inicial.notna(), "pequeño")
    g[g.index == CAPITAL] = "Madrid capital"
    return g.astype(str)


# --------------------------------------------------------------------------------------------
# 1º de primaria por municipio
# --------------------------------------------------------------------------------------------
def backtest_primero(Y1: pd.DataFrame, INF2: pd.DataFrame, B: pd.DataFrame, zona: pd.Series,
                     hmax: int = 6) -> pd.DataFrame:
    cursos = sorted(Y1.columns)
    primero = cursos[0]
    filas = []
    for b in cursos:
        fac = M.factores_base(Y1, INF2, B, zona, b, primero)
        for m in Y1.index:
            f = fac.loc[m]
            for h in range(1, hmax + 1):
                t = b + h
                if t not in Y1.columns:
                    continue
                c = M.cohorte_1o(t)
                if c > b:
                    raise M.FugaDelFuturo(f"base {b}, curso {t}")
                nac = M.valor(B, m, c)
                filas.append(dict(
                    cmun=m, b=b, h=h, t=t, y=M.valor(Y1, m, t), yb=M.valor(Y1, m, b), nacidos=nac,
                    p_naive=M.valor(Y1, m, b), p_births=nac, p_births_reg=nac * f.reg,
                    p_f1=nac * f.f1, p_f2=nac * f.f2, p_f3=nac * f.f3, p_f3s=nac * f.f3s,
                    p_finf=nac * f.finf, p_finfk=nac * f.finfk,
                ))
    df = pd.DataFrame(filas)
    df["p_combo"] = (df["p_f3"] + df["p_finfk"]) / 2
    df["grupo"] = df["cmun"].map(grupo_tamano(Y1[primero]))
    df["zona"] = df["cmun"].map(zona)
    return df


def muestra_comun(df: pd.DataFrame, especs) -> pd.DataFrame:
    """Filas en las que todas las especificaciones tienen previsión: se comparan sobre lo mismo."""
    return df.dropna(subset=list(especs) + ["y"])


# --------------------------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------------------------
def metricas(g: pd.DataFrame, especs, ycol: str = "y") -> pd.Series:
    """MAPE, MdAPE, WAPE y sesgo (en %) sobre las filas con alumnos reales > 0."""
    g = g[g[ycol] > 0]
    out = {"n": len(g)}
    for s in especs:
        e = g[s] - g[ycol]
        ape = e.abs() / g[ycol] * 100
        out[f"{s}|MAPE"] = ape.mean()
        out[f"{s}|MdAPE"] = ape.median()
        out[f"{s}|WAPE"] = e.abs().sum() / g[ycol].sum() * 100
        out[f"{s}|sesgo"] = e.sum() / g[ycol].sum() * 100
    return pd.Series(out)


def tabla(df: pd.DataFrame, especs, por) -> pd.DataFrame:
    return df.groupby(por).apply(lambda g: metricas(g, especs), include_groups=False)


def seleccion(comun: pd.DataFrame, especs) -> pd.Series:
    """Criterio declarado: MdAPE medio de h = 2 a 6 en municipios con 50 alumnos de 1º o más."""
    sel = comun[comun["grupo"].isin(["grande", "mediano", "Madrid capital"]) & (comun["h"] >= 2)]
    t = tabla(sel, especs, ["h"])
    md = t[[f"{s}|MdAPE" for s in especs]].mean()
    md.index = [i.split("|")[0] for i in md.index]
    return md.sort_values()


def agregar(df: pd.DataFrame, especs, clave: str) -> pd.DataFrame:
    """Suma previsiones y reales a un nivel superior (área o región) para medir el error ahí."""
    cols = ["y"] + list(especs)
    return df.groupby([clave, "b", "h", "t"])[cols].sum(min_count=1).reset_index()


# --------------------------------------------------------------------------------------------
# 1º de primaria regional, serie larga (1999/00-2025/26)
# --------------------------------------------------------------------------------------------
def backtest_region(r1: pd.Series, B: pd.DataFrame, provisionales=(), hmax: int = 6) -> pd.DataFrame:
    breg = B.sum()
    filas = []
    for b in r1.index:
        for h in range(1, hmax + 1):
            t = b + h
            if t not in r1.index or M.cohorte_1o(t) > b:
                continue
            f1 = r1[b] / breg[M.cohorte_1o(b)]
            ks = [s for s in range(b - 2, b + 1) if s in r1.index]
            f3 = sum(r1[s] for s in ks) / sum(breg[M.cohorte_1o(s)] for s in ks)
            nac = breg[M.cohorte_1o(t)]
            filas.append(dict(b=b, h=h, t=t, y=r1[t], p_naive=r1[b], p_births=nac, p_f1=nac * f1, p_f3=nac * f3,
                              provisional=t in set(provisionales)))
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------------
# Infantil de 2º ciclo (3-5 años) por municipio
# --------------------------------------------------------------------------------------------
def backtest_infantil(INF2: pd.DataFrame, B: pd.DataFrame, hmax: int = 3) -> pd.DataFrame:
    cursos = sorted(INF2.columns)
    primero = cursos[0]

    def coh(m, s):
        return M.suma_nacidos(B, m, M.cohortes_infantil(s))

    filas = []
    for b in cursos:
        for m in INF2.index:
            yb = M.valor(INF2, m, b)
            if np.isnan(yb):
                continue
            acum = {}
            for k in (1, 3):
                num = den = 0.0
                for s in range(max(primero, b - k + 1), b + 1):
                    y, c = M.valor(INF2, m, s), coh(m, s)
                    if np.isnan(y) or np.isnan(c):
                        continue
                    num += y
                    den += c
                acum[k] = M.cociente(num, den)
            for h in range(1, hmax + 1):
                t = b + h
                y = M.valor(INF2, m, t)
                if np.isnan(y):
                    continue
                if max(M.cohortes_infantil(t)) > b:
                    continue
                c = coh(m, t)
                filas.append(dict(cmun=m, b=b, h=h, t=t, y=y, yb=yb, nacidos=c,
                                  p_naive=yb, p_births=c, p_f1=c * acum[1], p_f3=c * acum[3]))
    df = pd.DataFrame(filas)
    df["grupo"] = df["cmun"].map(grupo_tamano(INF2[primero], cortes=(99, 749)))
    return df
