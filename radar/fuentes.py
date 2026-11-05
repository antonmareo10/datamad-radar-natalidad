"""Registro de fuentes: cada dataset con su página y su URL oficial de descarga.

Todas salen del catálogo de datos abiertos de la Comunidad de Madrid (datos.comunidad.madrid,
API CKAN). Si el portal cambiara la URL de un recurso, el descargador lo busca por su nombre
dentro del dataset (campo `recurso`).
"""
from dataclasses import dataclass

PORTAL = "https://datos.comunidad.madrid"
API = PORTAL + "/api/3/action/"


@dataclass(frozen=True)
class Fuente:
    clave: str        # nombre corto que usa el código
    dataset: str      # identificador CKAN del dataset
    titulo: str       # título del dataset en el catálogo
    recurso: str      # nombre del recurso dentro del dataset
    url: str          # URL oficial de descarga del recurso
    fichero: str      # nombre con el que se guarda en disco
    editor: str
    uso: str          # para qué lo usa el radar

    @property
    def pagina(self) -> str:
        return f"{PORTAL}/dataset/{self.dataset}"


FUENTES = [
    Fuente(
        clave="nacidos",
        dataset="mnp_nacidos_vivos_por_residencia_y_sexo",
        titulo="Nacidos vivos por lugar de residencia de la madre y sexo. Municipios",
        recurso="Nacidos vivos por lugar de residencia de la madre y sexo. Municipios",
        url=PORTAL + "/dataset/12b40587-add2-4467-b2a0-205b8b99af7d/resource/00a2fcf4-671f-4ea8-8cde-ac56d2dd352f"
                     "/download/nacidos-vivos-por-lugar-de-residencia-de-la-madre-y-sexo.-municipios.csv",
        fichero="nacidos_residencia_madre_municipios.csv",
        editor="Instituto de Estadística de la Comunidad de Madrid",
        uso="Cohortes de nacidos por municipio (1985-2024): los niños que entrarán en el colegio.",
    ),
    Fuente(
        clave="primaria_curso",
        dataset="spacm_estadisticas_alumnos",
        titulo="Estadísticas de alumnos de centros educativos de la Comunidad de Madrid",
        recurso="Alumnos matriculados en Educación Primaria por curso y sexo",
        url=PORTAL + "/dataset/5dd00f2c-2147-4550-b40e-adb5a0b2001c/resource/9073f828-f094-4914-a3a9-69431703b6ef"
                     "/download/alumnos_primaria_por_curso_y_sexo.csv",
        fichero="alumnos_primaria_por_curso_y_sexo.csv",
        editor="Consejería de Educación, Ciencia y Universidades",
        uso="Alumnos de 1º de primaria por municipio (cursos 2018/19-2024/25): lo que se predice y se contrasta.",
    ),
    Fuente(
        clave="ensenanzas_titularidad",
        dataset="spacm_estadisticas_alumnos",
        titulo="Estadísticas de alumnos de centros educativos de la Comunidad de Madrid",
        recurso="Alumnos matriculados en Enseñanzas de Régimen General por enseñanzas, titularidad y régimen de financiación",
        url=PORTAL + "/dataset/5dd00f2c-2147-4550-b40e-adb5a0b2001c/resource/2fd0545c-4da7-447a-9009-57c64399a49e"
                     "/download/alumnos_regimen_general_por_titularidad_y_financiacion.csv",
        fichero="alumnos_regimen_general_por_titularidad_y_financiacion.csv",
        editor="Consejería de Educación, Ciencia y Universidades",
        uso="Alumnos de infantil de 2º ciclo (3-5 años) por municipio: factor del modelo y segunda previsión.",
    ),
    Fuente(
        clave="primaria_region",
        dataset="alumnos_matriculados_primaria_por_curso_titularidad_y_sexo",
        titulo="Alumnos matriculados en educación primaria por curso, titularidad del centro y sexo",
        recurso="Alumnos matriculados en educación primaria por curso, titularidad del centro y sexo",
        url=PORTAL + "/dataset/baeeb634-fec7-4ac5-b065-f8ea25d28f9f/resource/efc9bf2d-d760-44d5-94f7-0d9ed0e26a45"
                     "/download/alumnos-matriculados-en-educacion-primaria-por-curso-titularidad-del-centro-y-sexo.csv",
        fichero="alumnos_primaria_region_por_curso.csv",
        editor="Instituto de Estadística de la Comunidad de Madrid",
        uso="1º de primaria regional 1999/00-2025/26: backtest largo con cambios de ciclo y dato de 2025/26 que el modelo no ve.",
    ),
    Fuente(
        clave="censo_edad",
        dataset="poblacion_censada_por_edad_nacionalidad_y_sexo",
        titulo="Población censada por edad, nacionalidad y sexo. Censo anual. Municipios",
        recurso="Población censada por edad, nacionalidad y sexo. Censo anual. Municipios",
        url=PORTAL + "/dataset/0a14fbfe-783e-4de3-81b1-ff3792bfd402/resource/bab16922-8df1-49b5-9791-aed4edf8ced1"
                     "/download/poblacion-censada-por-edad-nacionalidad-y-sexo.-censo-anual.-municipios.csv",
        fichero="censo_anual_edad_municipios.csv",
        editor="Instituto de Estadística de la Comunidad de Madrid",
        uso="Niños de 0-4 años censados frente a nacidos: señal de llegada o salida de familias.",
    ),
    Fuente(
        clave="padron",
        dataset="padron_por_sexo",
        titulo="Población empadronada por sexo. Municipios",
        recurso="Población empadronada por sexo. Municipios",
        url=PORTAL + "/dataset/bf0b4159-21f8-42fa-835c-d0dc6bc5fadf/resource/bc69f395-1f96-4fc2-a115-025c55b905ad"
                     "/download/poblacion-empadronada-por-sexo.-municipios.csv",
        fichero="padron_por_sexo_municipios.csv",
        editor="Instituto de Estadística de la Comunidad de Madrid",
        uso="Habitantes de cada municipio (contexto en la ficha).",
    ),
    Fuente(
        clave="limites",
        dataset="covid19_tia_muni_y_distritos",
        titulo="Covid 19 - TIA por Municipios y Distritos de Madrid (recurso cartográfico)",
        recurso="Municipios y Distritos de Madrid (2020)",
        url=PORTAL + "/dataset/6c63b14c-9f5d-414f-958f-b8a9c53d69fc/resource/3f4435b7-ecdb-4c1e-961a-dd55506c2e10"
                     "/download/municipios_y_distritos_madrid_20.zip",
        fichero="municipios_y_distritos_madrid_20.zip",
        editor="Consejería de Sanidad (Red de Vigilancia Epidemiológica)",
        uso="Límites de los municipios (shapefile) para el mapa. Los distritos de la capital se funden en uno.",
    ),
]

POR_CLAVE = {f.clave: f for f in FUENTES}
