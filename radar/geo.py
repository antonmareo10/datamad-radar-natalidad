"""Límites municipales para el mapa, sin dependencias geográficas.

Lee el shapefile oficial (dentro del zip descargado), funde los 21 distritos de Madrid capital en
un único polígono, simplifica las líneas (Douglas-Peucker) y devuelve trazados SVG ya proyectados.
Las coordenadas vienen en ETRS89 / UTM 30N (metros), así que basta con escalar y voltear el eje y.
"""
from __future__ import annotations

import io
import math
import struct
import zipfile
from collections import defaultdict

Punto = tuple[float, float]
Anillo = list[Punto]


# --------------------------------------------------------------------------------------------
# Lectura de shapefile (tipos 5 y 15: polígonos) y dbf
# --------------------------------------------------------------------------------------------
def leer_shp(datos: bytes) -> list[list[Anillo]]:
    """Devuelve, por registro, la lista de anillos (cada anillo, lista de puntos x, y)."""
    if struct.unpack(">i", datos[0:4])[0] != 9994:
        raise ValueError("No es un fichero .shp")
    pos, fin = 100, len(datos)
    registros = []
    while pos + 8 <= fin:
        _, largo = struct.unpack(">ii", datos[pos:pos + 8])
        cuerpo = datos[pos + 8: pos + 8 + 2 * largo]
        pos += 8 + 2 * largo
        tipo = struct.unpack("<i", cuerpo[0:4])[0]
        if tipo == 0:
            registros.append([])
            continue
        if tipo not in (5, 15, 25):
            raise ValueError(f"Tipo de geometría no soportado: {tipo}")
        n_partes, n_puntos = struct.unpack("<ii", cuerpo[36:44])
        partes = list(struct.unpack(f"<{n_partes}i", cuerpo[44:44 + 4 * n_partes]))
        base = 44 + 4 * n_partes
        xy = struct.unpack(f"<{2 * n_puntos}d", cuerpo[base:base + 16 * n_puntos])
        puntos = [(xy[2 * i], xy[2 * i + 1]) for i in range(n_puntos)]
        partes.append(n_puntos)
        registros.append([puntos[partes[i]:partes[i + 1]] for i in range(n_partes)])
    return registros


def leer_dbf(datos: bytes, codificacion: str = "latin-1") -> list[dict]:
    n = struct.unpack("<I", datos[4:8])[0]
    cabecera, largo = struct.unpack("<HH", datos[8:12])
    campos, i = [], 32
    while datos[i] != 0x0D:
        nombre = datos[i:i + 11].split(b"\0")[0].decode("ascii")
        campos.append((nombre, chr(datos[i + 11]), datos[i + 16]))
        i += 32
    filas, pos = [], cabecera
    for _ in range(n):
        reg = datos[pos + 1: pos + largo]
        pos += largo
        fila, p = {}, 0
        for nombre, tipo, ln in campos:
            v = reg[p:p + ln].decode(codificacion).strip()
            p += ln
            if tipo in "NF":
                v = float(v) if v else None
            fila[nombre] = v
        filas.append(fila)
    return filas


def leer_zip(ruta) -> tuple[list[list[Anillo]], list[dict]]:
    with zipfile.ZipFile(ruta) as z:
        shp = next(n for n in z.namelist() if n.lower().endswith(".shp"))
        dbf = shp[:-4] + ".dbf"
        cod = "latin-1"
        cpg = shp[:-4] + ".cpg"
        if cpg in z.namelist():
            txt = z.read(cpg).decode("ascii", "ignore").strip().lower()
            cod = "utf-8" if "utf" in txt else "latin-1"
        return leer_shp(z.read(shp)), leer_dbf(z.read(dbf), cod)


# --------------------------------------------------------------------------------------------
# Geometría
# --------------------------------------------------------------------------------------------
def area_firmada(anillo: Anillo) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(anillo, anillo[1:] + anillo[:1]):
        s += x1 * y2 - x2 * y1
    return s / 2


def fundir(poligonos: list[list[Anillo]], decimales: int = 3) -> list[Anillo]:
    """Une polígonos vecinos eliminando las aristas compartidas.

    Funciona cuando los vecinos comparten exactamente los mismos vértices en su frontera, como
    ocurre con los distritos de una misma capa oficial. Devuelve los anillos del contorno.
    """
    def k(p):
        return (round(p[0], decimales), round(p[1], decimales))

    aristas = defaultdict(int)
    for anillos in poligonos:
        for a in anillos:
            pts = [k(p) for p in a]
            if pts[0] != pts[-1]:
                pts.append(pts[0])
            for p, q in zip(pts, pts[1:]):
                if p != q:
                    aristas[(p, q)] += 1
    # una arista recorrida en los dos sentidos es interior
    libres = {}
    for (p, q), n in aristas.items():
        neto = n - aristas.get((q, p), 0)
        if neto > 0:
            libres.setdefault(p, []).append(q)
    anillos = []
    while libres:
        inicio = next(iter(libres))
        anillo, actual = [inicio], inicio
        while True:
            siguientes = libres.get(actual)
            if not siguientes:
                break
            nxt = siguientes.pop()
            if not siguientes:
                del libres[actual]
            if nxt == inicio:
                break
            anillo.append(nxt)
            actual = nxt
        if len(anillo) >= 3:
            anillos.append(anillo)
    return anillos


def _dist_segmento(p: Punto, a: Punto, b: Punto) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def douglas_peucker(linea: list[Punto], tolerancia: float) -> list[Punto]:
    """Simplificación clásica, iterativa. Conserva siempre el primer y el último punto."""
    if len(linea) < 3:
        return list(linea)
    conservar = [False] * len(linea)
    conservar[0] = conservar[-1] = True
    pila = [(0, len(linea) - 1)]
    while pila:
        i, j = pila.pop()
        dmax, imax = -1.0, -1
        for k in range(i + 1, j):
            d = _dist_segmento(linea[k], linea[i], linea[j])
            if d > dmax:
                dmax, imax = d, k
        if dmax > tolerancia:
            conservar[imax] = True
            pila += [(i, imax), (imax, j)]
    return [p for p, c in zip(linea, conservar) if c]


def simplificar_anillo(anillo: Anillo, tolerancia: float) -> Anillo:
    if len(anillo) and anillo[0] == anillo[-1]:
        anillo = anillo[:-1]
    if len(anillo) < 4:
        return anillo
    # se parte el anillo por su punto más lejano al primero para que DP tenga dos extremos estables
    lejos = max(range(len(anillo)), key=lambda i: (anillo[i][0] - anillo[0][0]) ** 2 + (anillo[i][1] - anillo[0][1]) ** 2)
    a = douglas_peucker(anillo[:lejos + 1], tolerancia)
    b = douglas_peucker(anillo[lejos:] + [anillo[0]], tolerancia)
    return a[:-1] + b[:-1]


# --------------------------------------------------------------------------------------------
# Mapa
# --------------------------------------------------------------------------------------------
def codigo_ine(fila: dict) -> str | None:
    """codigo_geo trae 3 dígitos de municipio + 3 de distrito (079603) o el municipio solo."""
    c = str(fila.get("codigo_geo") or "").strip()
    if not c:
        return None
    return "28" + c[:3]


def construir_mapa(ruta_zip, ancho: float = 1000.0, tolerancia_m: float = 90.0) -> dict:
    """Devuelve {'viewBox': ..., 'municipios': {cmun: {'d': path, 'nombre': ...}}}."""
    registros, filas = leer_zip(ruta_zip)
    grupos = defaultdict(list)
    nombres = {}
    for geom, fila in zip(registros, filas):
        cm = codigo_ine(fila)
        if cm is None or not geom:
            continue
        grupos[cm].append(geom)
        nombres.setdefault(cm, fila.get("municipio_"))
    xs = [p[0] for g in grupos.values() for pol in g for a in pol for p in a]
    ys = [p[1] for g in grupos.values() for pol in g for a in pol for p in a]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    escala = ancho / (x1 - x0)
    alto = (y1 - y0) * escala

    def proy(p):
        return ((p[0] - x0) * escala, (y1 - p[1]) * escala)

    salida = {}
    for cm, pols in grupos.items():
        anillos = fundir(pols) if len(pols) > 1 else pols[0]
        partes = []
        for a in anillos:
            s = simplificar_anillo(a, tolerancia_m)
            if len(s) < 3 or abs(area_firmada(s)) < (tolerancia_m ** 2):
                continue
            pts = [proy(p) for p in s]
            partes.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
        cx = sum(p[0] for pol in pols for a in pol for p in a) / sum(len(a) for pol in pols for a in pol)
        cy = sum(p[1] for pol in pols for a in pol for p in a) / sum(len(a) for pol in pols for a in pol)
        px, py = proy((cx, cy))
        salida[cm] = {"d": "".join(partes), "cx": round(px, 1), "cy": round(py, 1),
                      "nombre_capa": "Madrid" if cm == "28079" else nombres.get(cm)}
    return {"viewBox": f"0 0 {ancho:.0f} {alto:.0f}", "municipios": salida}
