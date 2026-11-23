"""Demostración sin asistente ni conexión: llama a las cuatro herramientas del servidor MCP e imprime la respuesta.

    python mcp_server/demo.py                 # con los JSON locales de web/api/v1 (no necesita internet)
    python mcp_server/demo.py --url URL       # contra una copia publicada de la API, p. ej. https://.../api/v1/
    python mcp_server/demo.py --municipio Getafe

Usa las mismas funciones que el servidor (mcp_server/herramientas.py), sin el transporte MCP, así que
no necesita tener instalado el SDK de MCP.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from mcp_server import herramientas as H


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", help="URL base de la API (por defecto, los JSON locales de web/api/v1)")
    ap.add_argument("--municipio", default="Fuenlabrada", help="municipio de ejemplo (por defecto, Fuenlabrada)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # tildes y símbolos también en la consola de Windows
    radar = H.Radar(a.url or H.API_LOCAL)
    llamadas = [
        ("buscar_municipio", dict(texto=a.municipio[:5]), lambda: H.buscar_municipio(radar, a.municipio[:5])),
        ("prevision_municipio", dict(municipio=a.municipio, nivel="1o"), lambda: H.prevision_municipio(radar, a.municipio, "1o")),
        ("prevision_municipio", dict(municipio=a.municipio, nivel="infantil"), lambda: H.prevision_municipio(radar, a.municipio, "infantil")),
        ("fiabilidad_municipio", dict(municipio=a.municipio), lambda: H.fiabilidad_municipio(radar, a.municipio)),
        ("mayores_cambios", dict(n=5, sentido="bajada"), lambda: H.mayores_cambios(radar, 5, "bajada")),
        ("mayores_cambios", dict(n=3, sentido="subida"), lambda: H.mayores_cambios(radar, 3, "subida")),
    ]
    print(f"Origen de los datos: {radar.origen}\n")
    for nombre, args, f in llamadas:
        firma = ", ".join(f"{k}={v!r}" for k, v in args.items())
        print(f"=== {nombre}({firma})")
        try:
            print(f())
        except H.ErrorRadar as e:
            print(f"ERROR: {e}")
            sys.exit(1)
        print()


if __name__ == "__main__":
    main()
