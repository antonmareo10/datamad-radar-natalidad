"""Intervalos de incertidumbre empíricos: salen de los errores reales del backtest.

Para cada grupo de tamaño y horizonte se toman los cuantiles del 10 % y del 90 % del error
logarítmico log(real / previsto) de las previsiones ya contrastadas (agrupando el horizonte con
sus vecinos ±1 para tener más casos). Así, un municipio pequeño recibe un intervalo ancho porque
en el pasado los pequeños fallaron mucho, no porque lo diga una fórmula.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Q_ALTO, Q_BAJO


def residuos(df: pd.DataFrame, espec: str, grupo_col: str = "grupo") -> pd.DataFrame:
    r = df[(df["y"] > 0) & (df[espec] > 0)].copy()
    r["lr"] = np.log(r["y"] / r[espec])
    # la capital no tiene casos suficientes por sí sola: usa los de los municipios grandes
    r["g"] = r[grupo_col].replace({"Madrid capital": "grande"})
    return r


def cuantiles(res: pd.DataFrame, g: str, h: int, vecinos: int = 1, excluir_base: int | None = None,
              q=(Q_BAJO, Q_ALTO)) -> tuple[float, float, int]:
    sel = res[(res["g"] == g) & ((res["h"] - h).abs() <= vecinos)]
    if excluir_base is not None:
        sel = sel[sel["b"] != excluir_base]
    if len(sel) == 0:
        return np.nan, np.nan, 0
    return float(sel["lr"].quantile(q[0])), float(sel["lr"].quantile(q[1])), len(sel)


def intervalo(prevision, lo_log: float, hi_log: float):
    return prevision * np.exp(lo_log), prevision * np.exp(hi_log)


def cobertura_validada(res: pd.DataFrame, vecinos: int = 1) -> pd.DataFrame:
    """¿Cuántos reales caen dentro de un intervalo calculado sin su propia base? (objetivo: 80 %)."""
    filas = []
    for (g, h, b), sub in res.groupby(["g", "h", "b"]):
        lo, hi, n = cuantiles(res, g, h, vecinos, excluir_base=b)
        if n == 0:
            continue
        dentro = ((sub["lr"] >= lo) & (sub["lr"] <= hi)).sum()
        filas.append(dict(g=g, h=h, b=b, n=len(sub), dentro=int(dentro)))
    c = pd.DataFrame(filas)
    out = c.groupby("g")[["n", "dentro"]].sum()
    out["cobertura_pct"] = out["dentro"] / out["n"] * 100
    tot = c[["n", "dentro"]].sum()
    out.loc["todos"] = [tot["n"], tot["dentro"], tot["dentro"] / tot["n"] * 100]
    return out
