"""Cargadores de las fuentes descargadas, con las comprobaciones de formato que importan.

Convención de años: s = año en que empieza el curso (2024/25 -> s = 2024).
  - Consejería de Educación: CURSO_ACADEMICO «2024/2025» -> s = 2024.
  - Instituto de Estadística: el año de la tabla es el último del curso -> s = año - 1.
Códigos: el Instituto de Estadística usa 4 dígitos (3 del municipio + dígito de control);
el código INE de 5 dígitos es «28» + los 3 primeros. La Consejería ya usa el de 5 dígitos.
"""
from __future__ import annotations

import pathlib
import re
import unicodedata

import pandas as pd

from .config import CAPITAL


# --------------------------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------------------------
def codigo_ine(cod_cm: str) -> str:
    """'0091' (código de 4 dígitos del Instituto de Estadística) -> '28009'."""
    c = str(cod_cm).strip()
    if not re.fullmatch(r"\d{4}", c):
        raise ValueError(f"Código municipal inesperado: {cod_cm!r}")
    return "28" + c[:3]


def curso_a_s(curso: str) -> int:
    """'2024/2025' -> 2024."""
    m = re.fullmatch(r"(\d{4})/(\d{4})", str(curso).strip())
    if not m or int(m.group(2)) != int(m.group(1)) + 1:
        raise ValueError(f"Curso inesperado: {curso!r}")
    return int(m.group(1))


def etiqueta_curso(s: int) -> str:
    return f"{s}/{str(s + 1)[-2:]}"


def nombre_legible(nombre: str) -> str:
    """'Rozas de Madrid (Las)' -> 'Las Rozas de Madrid'; 'Álamo (El)' -> 'El Álamo'."""
    m = re.fullmatch(r"(.+?)\s*\((El|La|Los|Las)\)\s*", str(nombre))
    return f"{m.group(2)} {m.group(1)}" if m else str(nombre).strip()


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def leer_ie(ruta: pathlib.Path) -> pd.DataFrame:
    """CSV del Instituto de Estadística (latin-1, ';'). Columnas normalizadas y valor numérico."""
    df = pd.read_csv(ruta, sep=";", encoding="latin-1", dtype=str, keep_default_na=False)
    df.columns = [_sin_tildes(c.strip()) for c in df.columns]
    ren = {"ano": "anio", "tipo territorio": "tipo", "codigo territorio": "cod", "territorio": "territorio",
           "valor": "valor_txt", "unidad": "unidad", "estado dato": "estado", "concepto": "concepto"}
    df = df.rename(columns=ren)
    df["anio"] = pd.to_numeric(df["anio"], errors="raise").astype(int)
    # '-' es secreto estadístico o dato no disponible; se deja como NaN
    df["valor"] = pd.to_numeric(df["valor_txt"].str.replace(",", ".", regex=False), errors="coerce")
    return df


def _municipios(df: pd.DataFrame) -> pd.DataFrame:
    m = df[(df["tipo"] == "Municipios") & df["cod"].str.fullmatch(r"\d{4}") & (df["cod"] != "9999")].copy()
    m["cmun"] = m["cod"].map(codigo_ine)
    return m


def leer_consejeria(ruta: pathlib.Path) -> pd.DataFrame:
    df = pd.read_csv(ruta, sep=";", dtype=str, encoding="utf-8-sig", keep_default_na=False)
    df["DATO"] = pd.to_numeric(df["DATO"], errors="raise")
    df["s"] = df["CURSO_ACADEMICO"].map(curso_a_s)
    df["cmun"] = df["ACOD_MUNICIPIO"].str.strip()
    assert df["cmun"].str.fullmatch(r"28\d{3}").all(), "código de municipio inesperado en la Consejería"
    return df


# --------------------------------------------------------------------------------------------
# Fuentes
# --------------------------------------------------------------------------------------------
def nacidos(ruta: pathlib.Path) -> tuple[pd.DataFrame, pd.Series]:
    """Nacidos vivos por residencia de la madre: (DataFrame cmun x año, nombres)."""
    d = _municipios(leer_ie(ruta))
    d = d[d["sexo"] == "Total"]
    tabla = d.pivot_table(index="cmun", columns="anio", values="valor", aggfunc="sum")
    nombres = d.drop_duplicates("cmun").set_index("cmun")["territorio"].map(nombre_legible)
    return tabla, nombres


def primaria(ruta: pathlib.Path) -> tuple[pd.DataFrame, pd.Series]:
    """Alumnos de 1º de primaria por municipio y curso (cmun x s) y área territorial de cada municipio.

    Madrid capital solo viene por sus 21 distritos: se suman.
    """
    p = leer_consejeria(ruta)
    p = p[p["VALOR2"] == "Total"]
    assert set(p.loc[p.cmun == CAPITAL, "DISTRITO_MUNICIPAL"]) != {"-"}, "la capital debería venir por distritos"
    assert (p.loc[p.cmun != CAPITAL, "DISTRITO_MUNICIPAL"] == "-").all(), "solo la capital tiene distritos"
    primero = p[p["VALOR1"] == "Primero"].pivot_table(index="cmun", columns="s", values="DATO", aggfunc="sum")
    zona = p.drop_duplicates("cmun").set_index("cmun")["SUBDIVTERR"].map(_zona_legible)
    return primero, zona


def _zona_legible(z: str) -> str:
    return {"C-CAPITAL": "Capital", "C-CENTRO": "Capital", "N-NORTE": "Norte", "S-SUR": "Sur", "E-ESTE": "Este", "O-OESTE": "Oeste"}.get(z, z)


def zonas(ruta: pathlib.Path) -> pd.Series:
    """Área territorial de cada municipio según el fichero de enseñanzas (incluye los que solo tienen infantil)."""
    t = leer_consejeria(ruta)
    return t.drop_duplicates("cmun").set_index("cmun")["SUBDIVTERR"].map(_zona_legible)


def infantil_segundo_ciclo(ruta: pathlib.Path) -> pd.DataFrame:
    """Alumnos de infantil de 2º ciclo (3-5 años) por municipio y curso (cmun x s), todas las titularidades."""
    t = leer_consejeria(ruta)
    t = t[t["ENSENANZA"] == "E. Infantil Segundo Ciclo"]
    assert len(t), "no aparece «E. Infantil Segundo Ciclo» en el fichero de enseñanzas"
    return t.pivot_table(index="cmun", columns="s", values="DATO", aggfunc="sum")


def primero_region(ruta: pathlib.Path) -> tuple[pd.Series, list[int]]:
    """1º de primaria, total regional, por curso (s), y lista de cursos provisionales."""
    d = leer_ie(ruta)
    d = d[(d["sexo"] == "Total") & d["concepto"].str.contains("primero del primer ciclo")
          & d["concepto"].str.contains("centros escolares")]
    assert d["anio"].is_unique, "debería haber un valor por año"
    s = d["anio"] - 1
    serie = pd.Series(d["valor"].to_numpy(), index=s.to_numpy(), name="primero_region").sort_index()
    serie.index.name = "s"
    provisionales = sorted(s[d["estado"].str.contains("Provisional", case=False)].tolist())
    return serie, provisionales


def censo_ninos(ruta: pathlib.Path) -> pd.DataFrame:
    """Censados a 1 de enero de 0-4 y 5-9 años por municipio (índice cmun, año; columnas p04, p59)."""
    c = _municipios(leer_ie(ruta))
    c = c[(c["sexo"] == "Total") & (c["nacionalidad"] == "Total")]
    # ojo: «0-4» también aparece dentro de «De 40-44 años»; se filtra por el inicio exacto
    c = c[c["edad"].str.startswith("De 0-4 ") | c["edad"].str.startswith("De 5-9 ")].copy()
    c["g"] = c["edad"].map(lambda x: "p04" if x.startswith("De 0-4 ") else "p59")
    return c.pivot_table(index=["cmun", "anio"], columns="g", values="valor", aggfunc="sum")


def padron(ruta: pathlib.Path) -> pd.DataFrame:
    """Población empadronada total (cmun x año)."""
    d = _municipios(leer_ie(ruta))
    d = d[d["sexo"] == "Total"]
    return d.pivot_table(index="cmun", columns="anio", values="valor", aggfunc="sum")
