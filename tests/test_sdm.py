"""Previsiones en Smart Data Models (radar/sdm.py): validan contra el JSON Schema oficial y coinciden con la API v1.

tests/sdm/ guarda copias sin modificar de los esquemas oficiales, para validar sin conexión:
- Observation.schema.json: smart-data-models/dataModel.SDMX, Observation/schema.json (commit 55b4393, 2024-09-18)
- common-schema.json: smart-data-models/data-models, common-schema.json (commit 2a72152, 2026-02-01)
"""
import json
import pathlib

import pytest

jsonschema = pytest.importorskip("jsonschema")
from referencing import Registry, Resource  # noqa: E402  (dependencia de jsonschema)

from radar.config import WEB_API  # noqa: E402
from radar.sdm import CONTEXTO_SDMX, LICENCIA  # noqa: E402

ESQUEMAS = pathlib.Path(__file__).parent / "sdm"
OBS = WEB_API / "sdm" / "observaciones_1o.json"
pytestmark = pytest.mark.skipif(not OBS.exists(), reason="sin API generada: python -m radar web")


@pytest.fixture(scope="module")
def validador():
    assert "uri" in jsonschema.Draft202012Validator.FORMAT_CHECKER.checkers, "falta rfc3986-validator"
    schema = json.loads((ESQUEMAS / "Observation.schema.json").read_text(encoding="utf-8"))
    comun = json.loads((ESQUEMAS / "common-schema.json").read_text(encoding="utf-8"))
    assert schema["$id"] == "https://smart-data-models.github.io/SDMX/Observation/schema.json"
    registro = Registry().with_resource(comun["$id"], Resource.from_contents(comun))
    V = jsonschema.Draft202012Validator
    V.check_schema(schema)
    return V(schema, registry=registro, format_checker=V.FORMAT_CHECKER)


@pytest.fixture(scope="module")
def observaciones():
    return json.loads(OBS.read_text(encoding="utf-8"))


def test_todas_validan_contra_el_esquema_oficial(validador, observaciones):
    errores = [(o["id"], e.message) for o in observaciones for e in validador.iter_errors(o)]
    assert errores == []


def test_la_validacion_no_es_vacia(validador, observaciones):
    """El esquema (con las definiciones comunes resueltas) rechaza valores fuera de sus listas de códigos."""
    o = dict(observaciones[0])
    assert list(validador.iter_errors({**o, "obsStatus": "X"}))
    assert list(validador.iter_errors({**o, "type": "Indicator"}))
    assert list(validador.iter_errors({**o, "id": "con espacios no vale"}))      # GSMA-Commons: ni patrón ni URI
    assert list(validador.iter_errors({**o, "dataProvider": 5}))                # GSMA-Commons
    assert list(validador.iter_errors({**o, "title": "no es una uri"}))          # format: uri
    assert list(validador.iter_errors({**o, "address": {"addressLocality": 5}}))  # definición común Location-Commons


def test_campos_obligatorios_y_contexto(observaciones):
    ids = [o["id"] for o in observaciones]
    assert len(ids) == len(set(ids))
    for o in observaciones:
        assert o["type"] == "Observation" and o["id"].startswith("urn:ngsi-ld:Observation:")
        assert o["@context"][0] == CONTEXTO_SDMX
        assert o["obsStatus"] == "F" and o["license"] == LICENCIA
        assert o["dataProvider"] and o["source"].endswith(f"/api/v1/municipios/{o['refArea']}.json")
        assert o["seeAlso"][0].endswith(f"/#municipio={o['refArea']}")
        dims = {d["key"]: d["value"] for d in o["dimensions"]}
        assert dims["cmun"] == o["refArea"] and dims["nivel"] == "1o" and dims["curso"].startswith(o["timePeriod"] + "/")


def test_cifras_identicas_a_la_api(observaciones):
    por_clave = {(o["refArea"], int(o["timePeriod"])): o for o in observaciones}
    idx = json.loads((WEB_API / "index.json").read_text(encoding="utf-8"))
    assert idx["endpoints"]["sdm_observaciones_1o"] == "sdm/observaciones_1o.json"
    n = 0
    for m in idx["municipios"]:
        d = json.loads((WEB_API / "municipios" / f"{m['cmun']}.json").read_text(encoding="utf-8"))
        for p in (d.get("primero_primaria") or {}).get("prevision", []):
            o = por_clave[(m["cmun"], p["t"])]
            assert o["obsValue"] == p["prevision"]
            assert (o["predictionInterval"]["lowerBound"], o["predictionInterval"]["upperBound"]) == (p["p10"], p["p90"])
            assert o["predictionInterval"]["level"] == 0.8
            assert o["address"]["addressLocality"] == d["municipio"]
            n += 1
    assert n == len(observaciones)
