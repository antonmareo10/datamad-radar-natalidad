"""Arranca el servidor MCP por stdio con el cliente del SDK oficial, lista sus herramientas y llama a una.

Se salta si el SDK de MCP no está instalado (pip install -r requirements-mcp.txt).
"""
import sys

import anyio
import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from radar.config import RAIZ, WEB_API  # noqa: E402

pytestmark = pytest.mark.skipif(not (WEB_API / "index.json").exists(), reason="sin API generada: python -m radar web")
HERRAMIENTAS = {"buscar_municipio", "prevision_municipio", "fiabilidad_municipio", "mayores_cambios"}


async def _sesion():
    params = StdioServerParameters(command=sys.executable, args=[str(RAIZ / "mcp_server" / "server.py"), "--local"],
                                   cwd=str(RAIZ))
    async with stdio_client(params) as (leer, escribir):
        async with ClientSession(leer, escribir) as s:
            init = await s.initialize()
            tools = (await s.list_tools()).tools
            r1 = await s.call_tool("prevision_municipio", {"municipio": "Fuenlabrada", "nivel": "1o"})
            r2 = await s.call_tool("mayores_cambios", {"n": 3, "sentido": "subida"})
            return init, tools, r1, r2


def _a(obj, nombre_2x, nombre_1x):
    """mcp 2.x usa snake_case (server_info) y 1.x camelCase (serverInfo)."""
    return getattr(obj, nombre_2x) if hasattr(obj, nombre_2x) else getattr(obj, nombre_1x)


def test_servidor_stdio():
    init, tools, r1, r2 = anyio.run(_sesion)
    assert _a(init, "server_info", "serverInfo").name == "radar-natalidad"
    assert {t.name for t in tools} == HERRAMIENTAS
    for t in tools:
        assert t.annotations is not None and _a(t.annotations, "read_only_hint", "readOnlyHint") is True
    prev = next(t for t in tools if t.name == "prevision_municipio")
    assert _a(prev, "input_schema", "inputSchema")["properties"]["nivel"]["enum"] == ["1o", "infantil"]
    assert not _a(r1, "is_error", "isError") and "2030/31: 1.150 alumnos (1.075–1.277)" in r1.content[0].text
    assert not _a(r2, "is_error", "isError") and r2.content[0].text.startswith("Mayores subidas")
