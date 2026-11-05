import io
import struct
import zipfile

import pytest

from radar import cargar as C
from radar import geo


# ------------------------------------------------------------------ cargar
def test_codigo_ine():
    assert C.codigo_ine("0091") == "28009"
    assert C.codigo_ine(" 0796 ") == "28079"
    with pytest.raises(ValueError):
        C.codigo_ine("9")


def test_cursos():
    assert C.curso_a_s("2024/2025") == 2024
    assert C.etiqueta_curso(2030) == "2030/31"
    with pytest.raises(ValueError):
        C.curso_a_s("2024/2026")


def test_nombre_legible():
    assert C.nombre_legible("Rozas de Madrid (Las)") == "Las Rozas de Madrid"
    assert C.nombre_legible("Álamo (El)") == "El Álamo"
    assert C.nombre_legible("Fuenlabrada") == "Fuenlabrada"


def test_leer_ie(tmp_path):
    txt = ("Año;Tipo territorio;Código territorio;Territorio;Sexo;Valor;Unidad;Estado dato\n"
           "2024;Comunidad de Madrid;;Comunidad de Madrid;Total;50770;Número;\n"
           "2024;Municipios;0091;Algete;Total;150;Número;\n"
           "2024;Municipios;0014;Acebeda (La);Total;-;Número;\n"
           "2023;Municipios;0091;Algete;Total;160;Número;\n")
    p = tmp_path / "n.csv"
    p.write_bytes(txt.encode("latin-1"))
    B, nombres = C.nacidos(p)
    assert B.at["28009", 2024] == 150
    assert B.at["28009", 2023] == 160
    assert nombres["28001"] == "La Acebeda"
    assert "Comunidad de Madrid" not in nombres.values


# ------------------------------------------------------------------ geo
def test_douglas_peucker_quita_puntos_alineados():
    linea = [(0, 0), (1, 0.01), (2, 0), (3, 0.02), (4, 0)]
    assert geo.douglas_peucker(linea, 0.1) == [(0, 0), (4, 0)]
    assert geo.douglas_peucker(linea, 0.001) == linea


def test_fundir_dos_cuadrados_vecinos():
    a = [[(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]]
    b = [[(1, 0), (1, 1), (2, 1), (2, 0), (1, 0)]]
    anillos = geo.fundir([a, b])
    assert len(anillos) == 1
    assert abs(geo.area_firmada(anillos[0])) == pytest.approx(2.0)
    assert (1, 1) in anillos[0] and (1, 0) in anillos[0]  # quedan como vértices del contorno


def _shp_cuadrado():
    """Shapefile mínimo con un polígono (tipo 5) y su dbf, en memoria."""
    pts = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0), (0.0, 0.0)]
    cuerpo = struct.pack("<i4d2i", 5, 0, 0, 10, 10, 1, len(pts)) + struct.pack("<i", 0)
    cuerpo += b"".join(struct.pack("<2d", *p) for p in pts)
    reg = struct.pack(">2i", 1, len(cuerpo) // 2) + cuerpo
    cab = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, (100 + len(reg)) // 2) + struct.pack("<2i4d4d", 1000, 5, 0, 0, 10, 10, 0, 0, 0, 0)
    shp = cab + reg
    campos = [("codigo_geo", b"C", 10), ("municipio_", b"C", 20)]
    largo = 1 + sum(c[2] for c in campos)
    dbf = struct.pack("<4BIHH20x", 3, 126, 1, 1, 1, 32 + 32 * len(campos) + 1, largo)
    for nombre, tipo, ln in campos:
        dbf += nombre.encode().ljust(11, b"\0") + tipo + b"\0" * 4 + bytes([ln, 0]) + b"\0" * 14
    dbf += b"\r" + b" " + b"0091".ljust(10) + "Algete".encode("latin-1").ljust(20) + b"\x1a"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("m.shp", shp)
        z.writestr("m.dbf", dbf)
    buf.seek(0)
    return buf


def test_leer_zip_y_mapa():
    regs, filas = geo.leer_zip(_shp_cuadrado())
    assert len(regs) == 1 and len(regs[0][0]) == 5
    assert filas[0]["codigo_geo"] == "0091"
    assert geo.codigo_ine(filas[0]) == "28009"
    m = geo.construir_mapa(_shp_cuadrado(), ancho=100, tolerancia_m=0.5)
    assert m["viewBox"] == "0 0 100 100"
    assert m["municipios"]["28009"]["d"].startswith("M")
