"""Servidor MCP de solo lectura del Radar de natalidad municipal (transporte stdio).

Cualquier asistente compatible con MCP (Claude Desktop, Claude Code y otros) puede consultar la
previsión de alumnos de cada municipio de la Comunidad de Madrid con cuatro herramientas:
buscar_municipio, prevision_municipio, fiabilidad_municipio y mayores_cambios.

Uso:
    python mcp_server/server.py                  # lee la API publicada (por defecto)
    python mcp_server/server.py --local          # lee los JSON de web/api/v1 (sin conexión)
    python mcp_server/server.py --url URL        # otra copia de la API (por ejemplo, una preview)

También se puede fijar el origen con la variable RADAR_API (URL o carpeta).
Requiere el SDK oficial de MCP para Python: pip install -r requirements-mcp.txt
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Literal

if __package__ in (None, ""):  # ejecutado como script: python mcp_server/server.py
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from mcp.types import ToolAnnotations

try:  # SDK oficial: mcp 2.x llama MCPServer a lo que en 1.x era FastMCP
    from mcp.server.mcpserver import MCPServer as _Servidor
except ImportError:  # pragma: no cover - mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Servidor

from mcp_server import herramientas as H

INSTRUCCIONES = (
    "Previsión abierta de alumnos de 1.º de primaria (hasta 2030/31) e infantil de 3 a 5 años (hasta 2027/28) en los "
    "municipios de la Comunidad de Madrid, con intervalos del 80 % calibrados con un backtest. Datos abiertos de la "
    "Comunidad de Madrid (CC BY 4.0). Al responder, da siempre la previsión junto con su intervalo y los avisos de "
    "fiabilidad, y cita la fuente."
)
SOLO_LECTURA = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)


def crear_servidor(origen: str | None = None) -> _Servidor:
    radar = H.Radar(origen)
    mcp = _Servidor("radar-natalidad", instructions=INSTRUCCIONES)

    @mcp.tool(annotations=SOLO_LECTURA)
    def buscar_municipio(texto: str) -> str:
        """Busca municipios de la Comunidad de Madrid por nombre (sin importar tildes ni mayúsculas) o por código INE
        de 5 dígitos. Devuelve el nombre oficial, el código INE, el área y si tiene colegio de primaria."""
        return H.buscar_municipio(radar, texto)

    @mcp.tool(annotations=SOLO_LECTURA)
    def prevision_municipio(municipio: str, nivel: Literal["1o", "infantil"] = "1o") -> str:
        """Previsión de alumnos de un municipio, curso a curso, con su intervalo del 80 % y el cambio frente al último
        curso con matrícula publicada. nivel="1o": 1.º de primaria (hasta 2030/31); nivel="infantil": infantil de
        3 a 5 años (hasta 2027/28). municipio: nombre o código INE."""
        return H.prevision_municipio(radar, municipio, nivel)

    @mcp.tool(annotations=SOLO_LECTURA)
    def fiabilidad_municipio(municipio: str) -> str:
        """Cuánto se puede fiar uno de la previsión de un municipio: error del método en su grupo de tamaño, su propio
        error en el backtest, cómo habría acertado el último curso, señal de llegada de familias y avisos.
        municipio: nombre o código INE."""
        return H.fiabilidad_municipio(radar, municipio)

    @mcp.tool(annotations=SOLO_LECTURA)
    def mayores_cambios(n: int = 10, sentido: Literal["bajada", "subida"] = "bajada") -> str:
        """Municipios (con 100 alumnos de 1.º o más) donde más baja o más sube el alumnado de 1.º de primaria previsto
        para el último curso del horizonte, con su intervalo del 80 %. n: cuántos (1 a 52)."""
        return H.mayores_cambios(radar, n, sentido)

    return mcp


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Servidor MCP (stdio) del Radar de natalidad municipal")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--local", nargs="?", const=str(H.API_LOCAL), metavar="CARPETA",
                   help=f"leer los JSON de una carpeta (por defecto {H.API_LOCAL})")
    g.add_argument("--url", help=f"URL base de la API (por defecto {H.URL_API} o la variable RADAR_API)")
    a = ap.parse_args(argv)
    crear_servidor(a.local or a.url).run(transport="stdio")


if __name__ == "__main__":
    main()
