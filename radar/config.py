"""Rutas y parámetros fijos del radar."""
import os
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MANIFIESTO = RAIZ / "fuentes" / "manifiesto.json"
RESULTADOS = RAIZ / "resultados"
WEB_DATOS = RAIZ / "web" / "datos"

CAPITAL = "28079"          # código INE de Madrid capital
EDAD_1O = 6                # un niño de 1º en el curso s/s+1 cumple 6 años en s: nació en s-6
EDADES_INFANTIL = (3, 5)   # infantil de 2º ciclo: nacidos en s-5, s-4 y s-3
LAMBDA_ZONA = 100          # peso (en nacidos) del prior de zona en el factor contraído; fijado a priori
ESPEC_1O = "p_finfk"       # especificación elegida para 1º: (b5)
ESPEC_INF = "p_f1"         # especificación para infantil de 2º ciclo: razón del último curso
Q_BAJO, Q_ALTO = 0.10, 0.90  # intervalo del 80 %


def dir_datos(arg: str | None = None) -> pathlib.Path:
    """Carpeta de datos pesados: argumento --datos, variable RADAR_DATOS o ./datos."""
    p = pathlib.Path(arg or os.environ.get("RADAR_DATOS") or (RAIZ / "datos"))
    p.mkdir(parents=True, exist_ok=True)
    return p
