"""Las previsiones de 1.º de primaria en el estándar Smart Data Models (FIWARE): modelo SDMX «Observation».

Escribe web/api/v1/sdm/observaciones_1o.json: una entidad NGSI-LD por municipio con colegio y curso
previsto, en la representación keyValues que describe el JSON Schema oficial del modelo
(https://github.com/smart-data-models/dataModel.SDMX/tree/master/Observation). Las cifras salen de los
mismos diccionarios que web/api/v1/municipios/{cmun}.json. Por qué este modelo y qué queda fuera de
él: docs/SMART_DATA_MODELS.md.
"""
from __future__ import annotations

import pathlib

from .config import REPO

CONTEXTO_SDMX = "https://raw.githubusercontent.com/smart-data-models/dataModel.SDMX/master/context.jsonld"
# Propiedades que el modelo no tiene (documentadas en docs/SMART_DATA_MODELS.md). license es dct:license;
# predictionInterval no tiene término estándar y queda en el vocabulario por defecto de NGSI-LD.
CONTEXTO = [CONTEXTO_SDMX, {"license": "http://purl.org/dc/terms/license"}]
LICENCIA = "https://creativecommons.org/licenses/by/4.0/"
PROVEEDOR = "Radar de natalidad municipal"
DOC = f"{REPO}/blob/master/docs/SMART_DATA_MODELS.md"
FICHERO_1O = "observaciones_1o.json"


def observacion_1o(d: dict, p: dict, url_api: str) -> dict:
    """Entidad Observation (keyValues) para la previsión de 1.º de un municipio (d, de municipios/{cmun}.json) y un curso (p)."""
    cm, t = d["cmun"], p["t"]
    return {
        "id": f"urn:ngsi-ld:Observation:radar-natalidad:1o:{cm}:{t}",
        "type": "Observation",
        "identifier": f"radar-natalidad-1o-{cm}-{t}",
        "title": f"{url_api}/sdm/{FICHERO_1O}#{cm}-{t}",
        "name": f"Alumnos de 1.º de primaria previstos en {d['municipio']}, curso {p['curso']}",
        "description": f"Previsión del Radar de natalidad municipal para 1.º de primaria en {d['municipio']} (código INE {cm}) "
                       f"en el curso {p['curso']}, hecha con {p['h']} {'curso' if p['h'] == 1 else 'cursos'} de antelación "
                       f"desde {d['base']}. predictionInterval es el intervalo del 80 %.",
        "obsValue": p["prevision"],
        "obsStatus": "F",   # SDMX CL_OBS_STATUS: F = Forecast value
        "confStatus": "F",  # SDMX CL_CONF_STATUS: F = Free
        "decimals": 3,
        "unitMult": 0,
        "freq": "A",        # SDMX CL_FREQ: A = Annual (un valor por curso)
        "refArea": cm,      # código INE del municipio (CL_AREA solo llega a países y regiones)
        "timePeriod": str(t),  # año en que empieza el curso, como el campo t de la API; el curso va en dimensions
        "dimensions": [{"key": "cmun", "value": cm}, {"key": "nivel", "value": "1o"},
                       {"key": "curso", "value": p["curso"]}, {"key": "h", "value": str(p["h"])}],
        "address": {"addressLocality": d["municipio"], "addressRegion": "Comunidad de Madrid", "addressCountry": "ES"},
        "source": f"{url_api}/municipios/{cm}.json",
        "dataProvider": PROVEEDOR,
        "seeAlso": [d["ficha_web"], DOC],
        "predictionInterval": {"lowerBound": p["p10"], "upperBound": p["p90"], "level": 0.8},
        "license": LICENCIA,
        "@context": CONTEXTO,
    }


def observaciones_1o(fichas: dict[str, dict], url_api: str) -> list[dict]:
    """Todas las previsiones de 1.º, ordenadas por código INE y curso."""
    return [observacion_1o(d, p, url_api)
            for cm, d in sorted(fichas.items()) if d.get("primero_primaria")
            for p in d["primero_primaria"]["prevision"]]


def exportar_sdm(fichas: dict[str, dict], destino: pathlib.Path, url_api: str, escribir) -> pathlib.Path:
    destino.mkdir(parents=True, exist_ok=True)
    obs = observaciones_1o(fichas, url_api)
    out = destino / FICHERO_1O
    escribir(out, obs)
    print(f"sdm: {out} ({len(obs)} observaciones SDMX de 1.º)")
    return out

