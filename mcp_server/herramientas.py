"""Lógica de las cuatro herramientas del servidor MCP del radar. Sin dependencias: solo la biblioteca estándar.

Lee la API abierta estática (web/api/v1, esquema en docs/API.md), por defecto la publicada en
https://radar-natalidad-madrid.vercel.app/api/v1/, o una carpeta local con los mismos JSON.
Cada función devuelve un texto en español; toda previsión va con su intervalo del 80 %.
"""
from __future__ import annotations

import difflib
import json
import math
import os
import pathlib
import re
import unicodedata
import urllib.error
import urllib.request

URL_API = "https://radar-natalidad-madrid.vercel.app/api/v1/"
API_LOCAL = pathlib.Path(__file__).resolve().parent.parent / "web" / "api" / "v1"
UA = "radar-natalidad-mcp/1.0 (+https://github.com/antonmareo10/datamad-radar-natalidad)"
NIVELES = {"1o": "1o", "1": "1o", "primero": "1o", "primaria": "1o", "1oprimaria": "1o",
           "infantil": "infantil", "inf": "infantil", "35": "infantil", "3-5": "infantil"}
SENTIDOS = {"bajada": "bajada", "baja": "bajada", "caida": "bajada", "subida": "subida", "sube": "subida"}


class ErrorRadar(Exception):
    """Error con un mensaje en español pensado para el usuario final."""


# ------------------------------------------------------------------ acceso a los datos
class Radar:
    """Lee los JSON de la API (por URL o de una carpeta) y los guarda en memoria durante la sesión."""

    def __init__(self, origen: str | os.PathLike | None = None, timeout: float = 20):
        origen = origen or os.environ.get("RADAR_API") or URL_API
        texto = str(origen)
        self.remoto = texto.startswith(("http://", "https://"))
        self.origen = (texto.rstrip("/") + "/") if self.remoto else pathlib.Path(texto)
        self.timeout = timeout
        self._cache: dict[str, dict] = {}

    def __repr__(self) -> str:
        return f"Radar({str(self.origen)!r})"

    def leer(self, ruta: str) -> dict:
        if ruta not in self._cache:
            self._cache[ruta] = self._leer_remoto(ruta) if self.remoto else self._leer_local(ruta)
        return self._cache[ruta]

    def _leer_remoto(self, ruta: str) -> dict:
        url = self.origen + ruta
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            pista = (" Ese despliegue pide autenticación (las previews de Vercel suelen estar protegidas): "
                     "usa la URL pública o --local.") if e.code in (401, 403) else ""
            raise ErrorRadar(f"La API del radar respondió {e.code} al pedir {url}.{pista}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ErrorRadar(f"No se pudo conectar con la API del radar ({url}): {e}. "
                             "Sin conexión, arranca el servidor con --local.") from e
        except json.JSONDecodeError as e:
            raise ErrorRadar(f"La respuesta de {url} no es JSON válido.") from e

    def _leer_local(self, ruta: str) -> dict:
        p = self.origen / ruta
        if not p.is_file():
            raise ErrorRadar(f"No existe {p}. Genera la API con `python -m radar web`.")
        return json.loads(p.read_text(encoding="utf-8"))

    def indice(self) -> dict:
        return self.leer("index.json")

    def region(self) -> dict:
        return self.leer("region.json")

    def municipio(self, cmun: str) -> dict:
        return self.leer(f"municipios/{cmun}.json")


# ------------------------------------------------------------------ formato (como la web)
MENOS, NBSP = "−", " "


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def ent(v) -> str:
    """Entero con separador de miles, redondeando la mitad hacia arriba como Math.round de la web."""
    if v is None:
        return "—"
    n = math.floor(v + 0.5)
    return (MENOS if n < 0 else "") + _miles(abs(n))


def dec(v, d: int = 1) -> str:
    if v is None:
        return "—"
    s = f"{abs(v):.{d}f}"
    e, _, f = s.partition(".")
    return (MENOS if v < 0 and float(s) != 0 else "") + _miles(int(e)) + ("," + f if f else "")


def pct(v, d: int = 1) -> str:
    """Porcentaje con signo: +3,5 % / −12,0 % (sin signo si redondea a cero)."""
    if v is None:
        return "—"
    return ("+" if round(v, d) > 0 else "") + dec(v, d) + NBSP + "%"


def pct_abs(v, d: int = 1) -> str:
    return "—" if v is None else dec(abs(v), d) + NBSP + "%"


def intervalo(lo, hi) -> str:
    return f"{ent(lo)}–{ent(hi)}"


# ------------------------------------------------------------------ búsqueda de municipios
def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9ñ ]+", " ", s.replace("ñ", "n"))
    return re.sub(r"\s+", " ", s).strip()


_ARTICULOS = ("el ", "la ", "los ", "las ")


def _sin_articulo(s: str) -> str:
    for a in _ARTICULOS:
        if s.startswith(a):
            return s[len(a):]
    return s


def buscar(radar: Radar, texto: str, limite: int = 10) -> tuple[list[dict], bool]:
    """Municipios que casan con el texto (nombre o código INE). Devuelve (lista, es_aproximada)."""
    munis = radar.indice()["municipios"]
    q = normalizar(texto)
    if not q:
        return [], False
    if re.fullmatch(r"\d{5}", q):
        return [m for m in munis if m["cmun"] == q], False
    if q in ("madrid capital", "capital"):
        q = "madrid"
    nombres = {m["cmun"]: normalizar(m["municipio"]) for m in munis}
    exactos = [m for m in munis if nombres[m["cmun"]] == q or _sin_articulo(nombres[m["cmun"]]) == _sin_articulo(q)]
    if exactos:
        return exactos, False
    qs = _sin_articulo(q)
    contienen = [m for m in munis if re.search(r"\b" + re.escape(qs), nombres[m["cmun"]])]
    contienen.sort(key=lambda m: (not nombres[m["cmun"]].startswith(qs), _sin_articulo(nombres[m["cmun"]]).find(qs), len(nombres[m["cmun"]])))
    if contienen:
        return contienen[:limite], False
    por_nombre = {_sin_articulo(v): k for k, v in nombres.items()}
    cerca = difflib.get_close_matches(qs, list(por_nombre), n=limite, cutoff=0.72)
    por_cmun = {m["cmun"]: m for m in munis}
    return [por_cmun[por_nombre[c]] for c in cerca], True


def resolver(radar: Radar, municipio: str) -> tuple[dict | None, str]:
    """Un único municipio para el texto dado, o (None, mensaje explicando por qué no)."""
    lista, aprox = buscar(radar, municipio)
    if len(lista) == 1 and not aprox:
        return lista[0], ""
    if len(lista) > 1 and not aprox:
        q = _sin_articulo(normalizar(municipio))
        empiezan = [m for m in lista if _sin_articulo(normalizar(m["municipio"])).startswith(q)]
        if len(empiezan) == 1:
            otros = ", ".join(m["municipio"] for m in lista if m is not empiezan[0])
            return empiezan[0], f"(Tomo {empiezan[0]['municipio']}; también contienen «{municipio}»: {otros}.)\n"
    if aprox and lista:
        q = _sin_articulo(normalizar(municipio))
        mejor = difflib.SequenceMatcher(None, q, _sin_articulo(normalizar(lista[0]["municipio"]))).ratio()
        segundo = difflib.SequenceMatcher(None, q, _sin_articulo(normalizar(lista[1]["municipio"]))).ratio() if len(lista) > 1 else 0
        if mejor >= 0.85 and mejor - segundo >= 0.08:
            return lista[0], f"(Interpreto «{municipio}» como {lista[0]['municipio']}.)\n"
    if not lista:
        return None, (f"No encuentro ningún municipio de la Comunidad de Madrid que se llame «{municipio}». "
                      "Prueba con buscar_municipio y parte del nombre o con el código INE de 5 dígitos.")
    opciones = "; ".join(f"{m['municipio']} ({m['cmun']})" for m in lista)
    return None, (f"«{municipio}» puede ser varios municipios: {opciones}. "
                  "Repite la consulta con el nombre completo o el código INE.")


def _etiqueta(m: dict) -> str:
    zona = f", área {m['zona']}" if m.get("zona") else ""
    return f"{m['municipio']} (código INE {m['cmun']}{zona})"


def _pie(d: dict) -> str:
    return (f"Ficha en la web: {d['ficha_web']}\n"
            "Fuente: Radar de natalidad municipal, a partir de datos abiertos de la Comunidad de Madrid (CC BY 4.0).")


# ------------------------------------------------------------------ herramientas
def buscar_municipio(radar: Radar, texto: str) -> str:
    lista, aprox = buscar(radar, texto)
    if not lista:
        return (f"No hay ningún municipio de la Comunidad de Madrid que case con «{texto}». "
                "Escribe parte del nombre (sin importar tildes) o el código INE de 5 dígitos.")
    cab = (f"No hay coincidencias exactas con «{texto}»; los nombres más parecidos son:" if aprox
           else f"{len(lista)} municipio{'s' if len(lista) > 1 else ''} para «{texto}»:")
    filas = []
    for m in lista:
        extra = "con colegio de primaria" if m["tiene_colegio"] else "sin colegio de primaria (sus niños van a municipios vecinos)"
        filas.append(f"- {_etiqueta(m)}: {extra}")
    return "\n".join([cab, *filas, "Usa el nombre o el código en prevision_municipio o fiabilidad_municipio."])


def prevision_municipio(radar: Radar, municipio: str, nivel: str = "1o") -> str:
    clave = NIVELES.get(normalizar(nivel or "1o").replace(" ", "")) or NIVELES.get(str(nivel).strip().lower())
    if clave is None:
        return f"Nivel «{nivel}» no válido: usa \"1o\" (1º de primaria) o \"infantil\" (infantil de 3 a 5 años)."
    m, nota = resolver(radar, municipio)
    if m is None:
        return nota
    d = radar.municipio(m["cmun"])
    if not d["tiene_colegio"]:
        return nota + "\n".join([_etiqueta(m) + ":", *(a["texto"] for a in d["fiabilidad"]["avisos"]),
                                 "No hay previsión propia: sus alumnos cuentan en las previsiones de los municipios donde se escolarizan.",
                                 _pie(d)])
    etapa = "1º de primaria" if clave == "1o" else "infantil de 3 a 5 años"
    bloque = d.get("primero_primaria" if clave == "1o" else "infantil_3_5")
    if not bloque:
        return nota + f"{_etiqueta(m)} no tiene alumnado de {etapa} publicado, así que el radar no hace previsión de esa etapa.\n" + _pie(d)
    base = d["base"]
    lineas = [f"{nota}{_etiqueta(m)} · {etapa}.",
              f"Último curso con matrícula publicada: {base}, con {ent(bloque['alumnos_base'])} alumnos.",
              "",
              "Previsión del radar (entre paréntesis, el intervalo del 80 %):"]
    for p in bloque["prevision"]:
        lineas.append(f"- {p['curso']}: {ent(p['prevision'])} alumnos ({intervalo(p['p10'], p['p90'])}); "
                      f"frente a {base}, {pct(p['cambio_pct'])} ({pct(p['cambio_p10'])} a {pct(p['cambio_p90'])}).")
    lineas.append("")
    grupo = bloque.get("grupo")
    tam = "de la capital (usa los errores de los municipios grandes)" if grupo == "Madrid capital" else f"{grupo}s"
    if clave == "1o":
        lineas.append(f"Cómo se calcula: nacidos en el municipio seis años antes × su factor ({dec(bloque['factor'], 2)} alumnos de 1º "
                      f"por cada niño nacido aquí, medido en su matrícula de infantil de {base}). El intervalo sale de los errores "
                      f"reales del backtest en municipios {tam} con la misma antelación.")
    else:
        lineas.append(f"Cómo se calcula: nacidos de las tres cohortes que estarán en infantil × alumnos por nacido del municipio "
                      f"en {base} ({dec(bloque['factor'], 3)}). El intervalo sale de los errores reales del backtest de infantil "
                      f"en municipios {tam} con la misma antelación.")
    avisos = [a["texto"] for a in d["fiabilidad"].get("avisos", []) if a["etapa"] in (clave, None)]
    senal = d.get("senal_llegada_familias")
    if clave == "1o" and senal and senal["ninos_0_4_por_100_nacidos"] >= 105:
        avisos.append(f"Señal de llegada de familias: {ent(senal['ninos_0_4_por_100_nacidos'])} niños de 0 a 4 años censados "
                      f"por cada 100 nacidos. {senal['lectura']}")
    lineas.append("Avisos de fiabilidad:" + (" ninguno." if not avisos else ""))
    lineas += [f"- {a}" for a in avisos]
    lineas += ["", _pie(d)]
    return "\n".join(lineas)


def fiabilidad_municipio(radar: Radar, municipio: str) -> str:
    m, nota = resolver(radar, municipio)
    if m is None:
        return nota
    d = radar.municipio(m["cmun"])
    if not d["tiene_colegio"]:
        return nota + "\n".join([_etiqueta(m) + ":", *(a["texto"] for a in d["fiabilidad"]["avisos"]), _pie(d)])
    f, p1 = d["fiabilidad"], d["primero_primaria"]
    g = f["grupo"]
    md = f["error_mediano_grupo_pct"] or {}
    desc = {"Madrid capital": "Madrid capital (sus intervalos usan los errores de los municipios grandes)",
            "grande": "municipio grande (250 alumnos de 1º o más en el primer curso del backtest)",
            "mediano": "municipio mediano (de 50 a 249 alumnos de 1º en el primer curso del backtest)",
            "pequeño": "municipio pequeño (menos de 50 alumnos de 1º en el primer curso del backtest)"}.get(g, g)
    lineas = [f"{nota}Fiabilidad de la previsión de 1º de primaria en {_etiqueta(m)}.", f"Grupo: {desc}.", ""]
    hs = sorted(md, key=int)
    if hs:
        lineas.append("Error mediano del radar en su grupo, según los cursos de antelación (entre paréntesis, suponer que nada cambia):")
        lineas.append("; ".join(f"{h} {'curso' if h == '1' else 'cursos'}: {pct_abs(md[h]['radar'])} ({pct_abs(md[h]['ingenuo'])})"
                                for h in hs) + ".")
    if f.get("cobertura_intervalos_grupo_pct") is not None:
        lineas.append(f"Los intervalos del 80 % de los municipios {f['grupo_intervalos']}s contuvieron el dato real en el "
                      f"{pct_abs(f['cobertura_intervalos_grupo_pct'])} de los casos del backtest (calculados sin la base evaluada).")
    ult = p1["prevision"][-1]
    lineas.append(f"Previsión para {ult['curso']}: {ent(ult['prevision'])} alumnos (intervalo del 80 %: {intervalo(ult['p10'], ult['p90'])}); "
                  f"el intervalo mide un {pct_abs(f['ancho_intervalo_ultimo_curso_pct'])} de la previsión.")
    lineas.append("")
    e, df = f.get("error_propio"), f.get("donde_falla")
    if e:
        lineas.append(f"En este municipio, sus {e['n']} previsiones pasadas hechas con dos o más cursos de antelación tuvieron un error "
                      f"mediano del {pct_abs(e['mediana_abs_pct'])} y un error medio con signo del {pct(e['media_pct'])} "
                      f"({'se quedó corto' if e['media_pct'] < 0 else 'se pasó'} en media).")
    if df:
        lineas.append(f"En el análisis de dónde falla el método (previsiones con 2 a 4 cursos de antelación): error medio con signo "
                      f"{pct(df['err_medio'], 2)}, error absoluto medio {pct_abs(df['ape_medio'], 2)}.")
    pasadas = [x for x in f.get("previsiones_pasadas", []) if x["t"] == max(y["t"] for y in f["previsiones_pasadas"])]
    if pasadas:
        real = pasadas[0]
        lineas.append(f"Cómo habría acertado {real['curso']} (hubo {ent(real['y'])} alumnos de 1º):")
        for x in sorted(pasadas, key=lambda y: y["b"]):
            lineas.append(f"- Previsión hecha en {x['curso_base']} ({x['h']} {'curso' if x['h'] == 1 else 'cursos'} antes): "
                          f"{ent(x['prevision'])} (error {pct(x['error_pct'])}); suponer que nada cambia daba {ent(x['p_naive'])} "
                          f"(error {pct(x['error_naive_pct'])}).")
    senal = d.get("senal_llegada_familias")
    if senal:
        lineas += ["", f"Señal de llegada de familias: a 1 de enero de {senal['anio_censo']} vivían aquí {ent(senal['ninos_0_4'])} niños "
                       f"de 0 a 4 años, {ent(senal['ninos_0_4_por_100_nacidos'])} por cada 100 nacidos en {senal['nacidos_desde']}-"
                       f"{senal['nacidos_hasta']}. {senal['lectura']}"]
    inf = f.get("infantil")
    if inf and inf.get("error_mediano_grupo_pct"):
        mi = inf["error_mediano_grupo_pct"]
        lineas += ["", "Infantil de 3 a 5 años, error mediano en su grupo (entre paréntesis, nada cambia): " +
                   "; ".join(f"{h} {'curso' if h == '1' else 'cursos'}: {pct_abs(mi[h]['radar'])} ({pct_abs(mi[h]['ingenuo'])})"
                             for h in sorted(mi, key=int)) + "."]
    avisos = [a["texto"] for a in f.get("avisos", [])]
    lineas += ["", "Avisos de fiabilidad:" + (" ninguno." if not avisos else "")]
    lineas += [f"- {a}" for a in avisos]
    lineas += ["", _pie(d)]
    return "\n".join(lineas)


def mayores_cambios(radar: Radar, n: int = 10, sentido: str = "bajada") -> str:
    s = SENTIDOS.get(normalizar(sentido))
    if s is None:
        return f"Sentido «{sentido}» no válido: usa \"bajada\" o \"subida\"."
    rk = radar.region()["ranking_1o"]
    filas = sorted(rk["municipios"], key=lambda x: x["cambio_pct"], reverse=(s == "subida"))
    try:
        n = max(1, min(int(n), len(filas)))
    except (TypeError, ValueError):
        n = 10
    base = radar.region()["base"]
    titulo = "Mayores bajadas" if s == "bajada" else "Mayores subidas"
    lineas = [f"{titulo} previstas en 1º de primaria de {base} a {rk['curso']}, entre los {len(filas)} municipios con 100 "
              f"alumnos de 1º o más en {base} (entre paréntesis, el intervalo del 80 %):"]
    for i, x in enumerate(filas[:n], 1):
        zona = f", {x['zona']}" if x.get("zona") else ""
        lineas.append(f"{i}. {x['municipio']} ({x['cmun']}{zona}): de {ent(x['alumnos_base'])} a {ent(x['prevision'])} alumnos "
                      f"({intervalo(x['p10'], x['p90'])}), {pct(x['cambio_pct'])} ({pct(x['cambio_p10'])} a {pct(x['cambio_p90'])}).")
    caen = sum(x["cambio_pct"] < 0 for x in filas)
    clara_b = sum(x["cambio_p90"] < 0 for x in filas)
    clara_s = sum(x["cambio_p10"] > 0 for x in filas)
    lineas.append("")
    lineas.append(f"De los {len(filas)}, caen {caen} y suben {len(filas) - caen}. La caída es clara incluso en el extremo alto del "
                  f"intervalo en {clara_b}; la subida es clara en {clara_s}.")
    if s == "subida":
        lineas.append("Las subidas están donde llegan familias, que es justo donde el método tiende a quedarse corto: podrían ser mayores.")
    lineas.append("Fuente: Radar de natalidad municipal, a partir de datos abiertos de la Comunidad de Madrid (CC BY 4.0).")
    return "\n".join(lineas)
