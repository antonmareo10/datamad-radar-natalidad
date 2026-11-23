"""Herramientas del servidor MCP (mcp_server/herramientas.py), sin transporte, contra los JSON locales de web/api/v1."""
import json
import re

import pytest

from mcp_server import herramientas as H
from radar.config import RAIZ, RESULTADOS, WEB_API

pytestmark = pytest.mark.skipif(not (WEB_API / "index.json").exists(), reason="sin API generada: python -m radar web")


@pytest.fixture(scope="module")
def radar():
    return H.Radar(WEB_API)


def _json(radar, cm):
    return radar.municipio(cm)


# ------------------------------------------------------------------ buscar_municipio
@pytest.mark.parametrize("texto,cmun", [("Fuenlabrada", "28058"), ("fuenlabrada", "28058"), ("28058", "28058"),
                                        ("alcala", "28005"), ("Madrid", "28079"), ("madrid capital", "28079"),
                                        ("el alamo", "28004"), ("Álamo", "28004"), ("Rozas de Madrid", "28127")])
def test_resolver(radar, texto, cmun):
    m, _ = H.resolver(radar, texto)
    assert m is not None and m["cmun"] == cmun


def test_buscar_varios_y_ninguno(radar):
    txt = H.buscar_municipio(radar, "Rozas")
    assert "Las Rozas de Madrid (código INE 28127" in txt and "Rozas de Puerto Real" in txt
    assert "No hay ningún municipio" in H.buscar_municipio(radar, "qqqqqq")
    m, msg = H.resolver(radar, "Torrejón")
    assert m is None and "puede ser varios municipios" in msg
    m, msg = H.resolver(radar, "Alcalá")  # solo uno empieza así; avisa de los demás
    assert m["cmun"] == "28005" and "Valverde de Alcalá" in msg


def test_errata_se_interpreta(radar):
    txt = H.prevision_municipio(radar, "Fuenlabarda")
    assert txt.startswith("(Interpreto «Fuenlabarda» como Fuenlabrada.)")


def test_buscar_indica_si_no_hay_colegio(radar):
    assert "sin colegio de primaria" in H.buscar_municipio(radar, "28001")


# ------------------------------------------------------------------ prevision_municipio
@pytest.mark.parametrize("nivel,bloque", [("1o", "primero_primaria"), ("infantil", "infantil_3_5")])
def test_prevision_con_intervalo_en_cada_curso(radar, nivel, bloque):
    txt = H.prevision_municipio(radar, "Fuenlabrada", nivel)
    d = _json(radar, "28058")[bloque]
    for p in d["prevision"]:
        linea = next(l for l in txt.splitlines() if l.startswith(f"- {p['curso']}:"))
        assert f"{H.ent(p['prevision'])} alumnos ({H.ent(p['p10'])}–{H.ent(p['p90'])})" in linea
        assert H.pct(p["cambio_p10"]) in linea and H.pct(p["cambio_p90"]) in linea
    assert f"con {H.ent(d['alumnos_base'])} alumnos" in txt
    assert "radar-natalidad-madrid.vercel.app/#municipio=28058" in txt and "CC BY 4.0" in txt


def test_cifras_de_fuenlabrada(radar):
    # las mismas que la ficha de la web y que resultados/proyeccion_1o_primaria.csv (1150,107; 1074,53; 1276,518)
    assert "- 2030/31: 1.150 alumnos (1.075–1.277)" in H.prevision_municipio(radar, "28058")


def test_ninguna_cifra_prevista_sin_intervalo(radar):
    for cm in ("28079", "28058", "28027", "28002", "28104"):
        for nivel in ("1o", "infantil"):
            for l in H.prevision_municipio(radar, cm, nivel).splitlines():
                if re.match(r"- \d{4}/\d{2}:", l):
                    assert re.search(r"alumnos \([\d.]+–[\d.]+\)", l), l


def test_niveles_admitidos(radar):
    assert "infantil de 3 a 5 años" in H.prevision_municipio(radar, "Getafe", "Infantil")
    assert "1.º de primaria" in H.prevision_municipio(radar, "Getafe", "1.º")
    assert "no válido" in H.prevision_municipio(radar, "Getafe", "bachillerato")


def test_prevision_sin_colegio(radar):
    txt = H.prevision_municipio(radar, "La Acebeda")
    assert "No tiene colegio de primaria" in txt and "No hay previsión propia" in txt


def test_prevision_avisos_por_etapa(radar):
    pequenos = [m["cmun"] for m in radar.indice()["municipios"] if m["tiene_colegio"]
                and _json(radar, m["cmun"])["primero_primaria"]["grupo"] == "pequeño"]
    cm = pequenos[0]
    assert "Municipio pequeño" in H.prevision_municipio(radar, cm, "1o")
    assert "Municipio pequeño" not in H.prevision_municipio(radar, cm, "infantil")


# ------------------------------------------------------------------ fiabilidad_municipio
def test_fiabilidad_buitrago_avisa(radar):
    txt = H.fiabilidad_municipio(radar, "Buitrago del Lozoya")
    assert "ha fallado bastante en el pasado" in txt
    assert "error medio con signo −34,11" in txt  # donde_falla_por_municipio.csv


def test_fiabilidad_grande(radar):
    txt = H.fiabilidad_municipio(radar, "Fuenlabrada")
    res = json.loads((RESULTADOS / "resumen.json").read_text(encoding="utf-8"))
    md = res["backtest_1o"]["mdape"]["grande"]
    assert f"5 cursos: {H.pct_abs(md['5']['radar'])} ({H.pct_abs(md['5']['ingenuo'])})" in txt
    assert "Cómo habría acertado 2024/25" in txt and "Avisos de fiabilidad: ninguno." in txt
    assert "1.150 alumnos (intervalo del 80 %: 1.075–1.277)" in txt


# ------------------------------------------------------------------ mayores_cambios
def test_mayores_bajadas_y_subidas(radar):
    res = json.loads((RESULTADOS / "resumen.json").read_text(encoding="utf-8"))["ranking"]
    baja = H.mayores_cambios(radar, 3, "bajada").splitlines()
    for i, r in enumerate(res["mas_caen"][:3], 1):  # mismo orden y mismas cifras que el ranking de la web
        assert baja[i].startswith(f"{i}. {r['municipio']} (") and f"a {H.ent(r['prevision'])} alumnos ({H.ent(r['p10'])}–{H.ent(r['p90'])})" in baja[i]
    sube = H.mayores_cambios(radar, 3, "subida").splitlines()
    for i, r in enumerate(res["mas_suben"][:3], 1):
        assert sube[i].startswith(f"{i}. {r['municipio']} (")
    assert f"caen {res['caen']}" in "\n".join(baja) and f"en {res['caida_segura']};" in "\n".join(baja)


def test_mayores_cambios_limites(radar):
    n = len(radar.region()["ranking_1o"]["municipios"])
    assert sum(bool(re.match(r"\d+\. ", l)) for l in H.mayores_cambios(radar, 1000).splitlines()) == n
    assert sum(bool(re.match(r"\d+\. ", l)) for l in H.mayores_cambios(radar, 0).splitlines()) == 1
    assert "no válido" in H.mayores_cambios(radar, 5, "lateral")


# ------------------------------------------------------------------ origen de los datos
def test_error_de_red_en_espanol():
    r = H.Radar("http://127.0.0.1:9/api/v1/", timeout=3)
    with pytest.raises(H.ErrorRadar, match="No se pudo conectar"):
        r.indice()


def test_carpeta_inexistente():
    with pytest.raises(H.ErrorRadar, match="python -m radar web"):
        H.Radar("no-existe").indice()


def test_ejemplo_del_readme_es_salida_real(radar):
    readme = (RAIZ / "mcp_server" / "README.md").read_text(encoding="utf-8")
    bloque = readme.split("<!-- ejemplo-demo:inicio -->")[1].split("<!-- ejemplo-demo:fin -->")[0]
    ejemplo = bloque.strip().removeprefix("```text").removesuffix("```").strip()
    assert ejemplo == H.prevision_municipio(radar, "Fuenlabrada", "1o").replace(" ", " ")
