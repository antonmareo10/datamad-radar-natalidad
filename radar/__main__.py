"""Línea de órdenes: python -m radar {descargar,calcular,web,todo} [--datos DIR] [--forzar]."""
import argparse

from . import config


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m radar", description=__doc__)
    ap.add_argument("orden", choices=["descargar", "calcular", "web", "todo"])
    ap.add_argument("--datos", help="carpeta para los datos descargados (por defecto RADAR_DATOS o ./datos)")
    ap.add_argument("--forzar", action="store_true", help="volver a descargar aunque haya copia local")
    a = ap.parse_args(argv)
    datos = config.dir_datos(a.datos)
    if a.orden in ("descargar", "todo"):
        from .descargar import descargar
        descargar(datos, config.MANIFIESTO, forzar=a.forzar)
    if a.orden == "calcular":
        from .calcular import calcular
        calcular(datos)
    if a.orden in ("web", "todo"):  # la exportación web recalcula todo antes de escribir
        from .web import exportar
        exportar(datos)


if __name__ == "__main__":
    main()
