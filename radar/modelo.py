"""El modelo de cohortes: de nacidos a alumnos.

Idea: los niños que entrarán en 1º de primaria dentro de seis cursos ya han nacido. Los nacidos se
cuentan por residencia de la madre y los alumnos por municipio del colegio, así que hace falta un
factor propio de cada municipio que recoja la llegada y salida de familias y la escolarización en
municipios vecinos. Ese factor se mide en el propio alumnado del municipio.

Especificación elegida para 1º de primaria, (b5):
    previsión(t) = nacidos(t-6) × [infantil 3-5 en b / nacidos(b-5..b-3)] × k(b)
    k(b) = [1º regional en b / nacidos regionales(b-6)] / [infantil regional en b / nacidos regionales(b-5..b-3)]
El factor de infantil mira a las tres cohortes más jóvenes ya escolarizadas; k corrige, con datos
regionales de la misma base, la diferencia media entre la razón de infantil y la de 1º.

Regla contra la fuga del futuro: en la base b solo se usa alumnado de cursos <= b y nacidos <= b.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import EDAD_1O, LAMBDA_ZONA


class FugaDelFuturo(ValueError):
    """Se ha pedido una previsión que necesitaría datos posteriores a la base."""


def cohorte_1o(t: int) -> int:
    """Año de nacimiento de los niños que empiezan 1º de primaria en el curso t/t+1."""
    return t - EDAD_1O


def cohortes_infantil(t: int) -> list[int]:
    """Años de nacimiento de los alumnos de infantil de 2º ciclo (3, 4 y 5 años) en el curso t/t+1."""
    return [t - 5, t - 4, t - 3]


def valor(df: pd.DataFrame, fila, col) -> float:
    try:
        v = df.at[fila, col]
    except KeyError:
        return np.nan
    return np.nan if pd.isna(v) else float(v)


def suma_nacidos(B: pd.DataFrame, m: str, anios) -> float:
    """Suma de nacidos de m en esos años; NaN si falta alguno."""
    vals = [valor(B, m, a) for a in anios]
    return np.nan if any(np.isnan(v) for v in vals) else float(sum(vals))


def cociente(num: float, den: float) -> float:
    if den is None or np.isnan(den) or den <= 0 or np.isnan(num):
        return np.nan
    return num / den


def razon_acumulada(Y: pd.DataFrame, B: pd.DataFrame, m: str, b: int, k: int, primero: int) -> tuple[float, float]:
    """Σ alumnos de 1º / Σ nacidos seis años antes, en los k últimos cursos <= b (desde `primero`)."""
    num = den = 0.0
    for s in range(max(primero, b - k + 1), b + 1):
        y = valor(Y, m, s)
        if np.isnan(y):
            continue
        num += y
        den += valor(B, m, cohorte_1o(s))  # NaN si falta: invalida el cociente, como debe
    return num, den


def razon_regional_1o(Y1: pd.DataFrame, B: pd.DataFrame, b: int) -> float:
    """Alumnos de 1º de toda la región en b / nacidos de toda la región en b-6.

    El denominador incluye los municipios sin colegio, cuyos niños se escolarizan en otros.
    """
    return Y1[b].sum() / B[cohorte_1o(b)].sum()


def correccion_infantil(Y1: pd.DataFrame, INF2: pd.DataFrame, B: pd.DataFrame, b: int) -> float:
    """k(b): razón regional de 1º dividida por la razón regional de infantil de 2º ciclo."""
    r_inf = INF2[b].sum() / B[cohortes_infantil(b)].sum().sum()
    return razon_regional_1o(Y1, B, b) / r_inf


def factor_infantil(INF2: pd.DataFrame, B: pd.DataFrame, m: str, b: int) -> float:
    """Alumnos de infantil de 2º ciclo del municipio en b / sus nacidos en b-5..b-3."""
    return cociente(valor(INF2, m, b), suma_nacidos(B, m, cohortes_infantil(b)))


def factores_base(Y1: pd.DataFrame, INF2: pd.DataFrame, B: pd.DataFrame, zona: pd.Series, b: int,
                  primero: int) -> pd.DataFrame:
    """Todos los factores de cada municipio con información <= b. Una fila por municipio."""
    reg = razon_regional_1o(Y1, B, b)
    kinf = correccion_infantil(Y1, INF2, B, b)
    munis = list(Y1.index)
    acum3 = {m: razon_acumulada(Y1, B, m, b, 3, primero) for m in munis}
    zr = {}
    for z in set(zona.reindex(munis).dropna()):
        ms = [m for m in munis if zona.get(m) == z]
        n = sum(acum3[m][0] for m in ms if not np.isnan(acum3[m][1]))
        d = sum(acum3[m][1] for m in ms if not np.isnan(acum3[m][1]))
        zr[z] = cociente(n, d)
    filas = []
    for m in munis:
        n1, d1 = razon_acumulada(Y1, B, m, b, 1, primero)
        n2, d2 = razon_acumulada(Y1, B, m, b, 2, primero)
        n3, d3 = acum3[m]
        fz = zr.get(zona.get(m), reg)
        finf = factor_infantil(INF2, B, m, b)
        filas.append(dict(
            cmun=m, b=b, reg=reg, kinf=kinf, fz=fz,
            f1=cociente(n1, d1), f2=cociente(n2, d2), f3=cociente(n3, d3),
            f3s=(n3 + LAMBDA_ZONA * fz) / (d3 + LAMBDA_ZONA) if not np.isnan(d3) else np.nan,
            finf=finf, finfk=finf * kinf,
        ))
    return pd.DataFrame(filas).set_index("cmun")


def factor_proyeccion(fac: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Factor (b5) de cada municipio; si no existe (sin infantil o sin nacidos), el de 1º de 3 cursos."""
    f = fac["finfk"].copy()
    respaldo = f.isna() | ~np.isfinite(f)
    f[respaldo] = fac.loc[respaldo, "f3"]
    tipo = pd.Series(np.where(respaldo, "1º de primaria, 3 cursos", "infantil 3-5 corregido"), index=f.index)
    return f, tipo


def prever_1o(B: pd.DataFrame, factor: pd.Series, b: int, t: int) -> pd.Series:
    """Previsión de alumnos de 1º en el curso t hecha en la base b."""
    c = cohorte_1o(t)
    if c > b:
        raise FugaDelFuturo(f"La cohorte de {t}/{t + 1} nace en {c}, después de la base {b}")
    return B[c].reindex(factor.index) * factor


def factor_infantil_simple(INF2: pd.DataFrame, B: pd.DataFrame, b: int) -> pd.Series:
    return INF2[b] / B[cohortes_infantil(b)].sum(axis=1, min_count=3).reindex(INF2.index)


def prever_infantil(B: pd.DataFrame, factor: pd.Series, b: int, t: int) -> pd.Series:
    """Previsión de alumnos de infantil de 2º ciclo (3-5 años) en el curso t hecha en la base b."""
    cs = cohortes_infantil(t)
    if max(cs) > b:
        raise FugaDelFuturo(f"La cohorte más joven de infantil en {t}/{t + 1} nace en {max(cs)}, después de {b}")
    return B[cs].sum(axis=1, min_count=3).reindex(factor.index) * factor
