# API abierta del Radar de natalidad municipal

Las mismas cifras que enseña la web, en JSON: la previsión de alumnos de 1.º de primaria (hasta 2030/31) y de infantil de 3 a 5 años (hasta 2027/28) en cada municipio de la Comunidad de Madrid, con su intervalo del 80 % y el error medido en el backtest.

- **URL base:** `https://radar-natalidad-madrid.vercel.app/api/v1/`
- **Sin claves ni registro.** Son ficheros estáticos: se pueden pedir con `curl`, desde el navegador o desde cualquier lenguaje. Se sirven con `Content-Type: application/json` y `Access-Control-Allow-Origin: *`, así que también se pueden leer desde una página de otro dominio.
- **Licencias:** datos con CC BY 4.0 (cita: «Radar de natalidad municipal, a partir de datos abiertos de la Comunidad de Madrid (datos.comunidad.madrid)»); código con licencia MIT.
- **Cómo se generan:** `python -m radar web` escribe `web/api/v1/` a la vez que `web/datos/radar.js` y a partir del mismo diccionario ([`radar/api.py`](../radar/api.py)), así que la API y la web no pueden dar cifras distintas. Los tests (`tests/test_api.py`) comprueban que coinciden con las tablas de [`resultados/`](../resultados/).
- **Actualización:** una vez al año, cuando la Consejería publica la matrícula del curso nuevo y el Instituto de Estadística los nacimientos del año. Dentro de `v1` solo se añadirán campos; un cambio incompatible irá a `v2`.
- **Asistentes de IA:** el servidor MCP de [`mcp_server/`](../mcp_server/) lee esta API.
- **Smart Data Models (FIWARE):** las previsiones de 1.º también se publican como observaciones del modelo SDMX `Observation` de Smart Data Models, listas para plataformas NGSI-LD. Ver [`SMART_DATA_MODELS.md`](SMART_DATA_MODELS.md).

## Endpoints

| Ruta | Contenido |
|---|---|
| [`index.json`](https://radar-natalidad-madrid.vercel.app/api/v1/index.json) | Metadatos, licencias, fuentes oficiales y lista de municipios con la URL de su fichero |
| [`region.json`](https://radar-natalidad-madrid.vercel.app/api/v1/region.json) | Totales de la Comunidad de Madrid: serie, previsión con intervalo y ranking de cambios |
| [`municipios/{cmun}.json`](https://radar-natalidad-madrid.vercel.app/api/v1/municipios/28058.json) | Un municipio: serie observada, previsión de 1.º y de infantil con intervalos, error del backtest y avisos de fiabilidad |
| [`sdm/observaciones_1o.json`](https://radar-natalidad-madrid.vercel.app/api/v1/sdm/observaciones_1o.json) | Las previsiones de 1.º en el estándar Smart Data Models (FIWARE): una entidad `Observation` (SDMX) por municipio y curso, con su intervalo. Ver [`SMART_DATA_MODELS.md`](SMART_DATA_MODELS.md) |

`{cmun}` es el código INE del municipio, con 5 dígitos (Madrid, `28079`; Fuenlabrada, `28058`). Hay un fichero por cada uno de los 179 municipios de la región; los 43 sin colegio de primaria tienen `"tiene_colegio": false` y no llevan previsión.

## Ejemplos

```bash
# metadatos y lista de municipios
curl -s https://radar-natalidad-madrid.vercel.app/api/v1/index.json

# previsión de 1.º de primaria en Fuenlabrada para el último curso, con su intervalo
curl -s https://radar-natalidad-madrid.vercel.app/api/v1/municipios/28058.json \
  | jq '.primero_primaria.prevision[-1] | {curso, prevision, p10, p90}'

# los cinco municipios donde más cae 1.º de primaria
curl -s https://radar-natalidad-madrid.vercel.app/api/v1/region.json \
  | jq '.ranking_1o.municipios[:5][] | {municipio, alumnos_base, prevision, p10, p90, cambio_pct}'
```

```python
import json, urllib.request
url = "https://radar-natalidad-madrid.vercel.app/api/v1/municipios/28058.json"
d = json.load(urllib.request.urlopen(url))
for p in d["primero_primaria"]["prevision"]:
    print(p["curso"], round(p["prevision"]), f'({round(p["p10"])}-{round(p["p90"])})')
```

```js
const d = await (await fetch("https://radar-natalidad-madrid.vercel.app/api/v1/region.json")).json();
console.log(d.primero_primaria.prevision.at(-1));
```

## Convenciones

- **Cursos:** `curso` es la etiqueta (`"2030/31"`) y `t` el año en que empieza (`2030`). `h` es la antelación en cursos desde la base, el último curso con matrícula publicada (`base`, hoy `"2024/25"`).
- **Previsión e intervalo:** `prevision` es la cifra central; `p10` y `p90`, los extremos del intervalo del 80 %. Salen de los cuantiles del 10 % y del 90 % del error real del backtest en municipios del mismo grupo de tamaño y con la misma antelación. Toda previsión lleva su intervalo, salvo el total regional de infantil, que el método no calcula (se indica en `nota_intervalo`).
- **Precisión:** las previsiones municipales llevan 3 decimales, igual que `resultados/proyeccion_*.csv`; las regionales, 1 decimal, igual que `resultados/resumen.json`. Para mostrarlas, redondea a entero. Los cambios (`cambio_pct`, `cambio_p10`, `cambio_p90`) son % frente a `alumnos_base`, con 1 decimal.
- **Grupos de tamaño:** en 1.º, `grande` (250 alumnos de 1.º o más en 2018/19), `mediano` (50 a 249), `pequeño` (menos de 50) y `Madrid capital`, aparte; la capital usa los intervalos de los grandes. En infantil, según los alumnos de 3 a 5 años en 2018/19: `grande`, 750 o más; `mediano`, de 100 a 749; `pequeño`, menos de 100.
- **Valores que faltan:** `null`.

## `index.json`

| Campo | Contenido |
|---|---|
| `nombre`, `descripcion` | Qué es |
| `version` | Versión de la API (`"1"`) |
| `version_radar` | Versión del código que la generó |
| `generado_utc` | Fecha y hora de la generación |
| `datos` | `curso_base`, `cursos_prevision_1o`, `cursos_prevision_infantil`, `ultimo_anio_nacidos` y `descarga_fuentes_utc` (primera y última descarga de las fuentes) |
| `licencias` | `datos` (CC BY 4.0, con el texto de atribución), `codigo` (MIT) y `datos_de_origen` |
| `intervalo` | Qué significan `p10` y `p90` |
| `url_base`, `endpoints` | Dónde está cada recurso (`index`, `region`, `municipio` y `sdm_observaciones_1o`) |
| `documentacion`, `web`, `repositorio`, `portal` | Enlaces |
| `fuentes` | Los siete recursos del catálogo de la Comunidad de Madrid, tal como están en [`fuentes/manifiesto.json`](../fuentes/manifiesto.json): `clave`, `dataset`, `titulo`, `recurso`, `editor`, `pagina`, `url` (URL oficial de descarga), `fichero`, `fecha_descarga_utc`, `bytes`, `sha256`, `licencia`, `licencia_titulo`, `modificado_en_portal`, `uso` |
| `municipios[]` | `cmun`, `municipio`, `zona` (área territorial: Capital, Norte, Sur, Este u Oeste; `null` si no consta), `tiene_colegio`, `url` |

## `region.json`

| Campo | Contenido |
|---|---|
| `base`, `intervalo` | Curso base y definición del intervalo |
| `primero_primaria.real_base` | Alumnos de 1.º en la región en el curso base |
| `primero_primaria.serie_observada[]` | `curso`, `t`, `alumnos`, `provisional` (1999/00 en adelante; el último curso puede ser provisional y el modelo no lo usa) |
| `primero_primaria.prevision[]` | `curso`, `t`, `h`, `nacidos_region` (cohorte seis años antes), `prevision`, `p10`, `p90`, `n` (errores usados para el intervalo), `cambio_pct` |
| `primero_primaria.nota_intervalo` | De dónde sale el intervalo regional (serie regional larga) |
| `primero_primaria.comprobacion_fuera_de_muestra` | Previsión del curso siguiente a la base frente a la cifra publicada que el modelo no usa: `curso`, `previsto`, `publicado`, `provisional`, `error_pct`, `dentro_intervalo` |
| `primero_primaria.capital`, `.resto` | `base`, `prevision` y `cambio_pct` en el último curso del horizonte |
| `primero_primaria.por_area_cambio_pct` | Cambio previsto por área en el último curso |
| `primero_primaria.municipios_con_colegio`, `.municipios_que_caen` | Recuentos |
| `infantil_3_5` | `real_base`, `prevision[]` (`curso`, `prevision`, `cambio_pct`) y `nota_intervalo` |
| `nacidos[]` | `anio`, `nacidos` en la región |
| `ranking_1o` | `curso`, `criterio` y `municipios[]` con 100 alumnos de 1.º o más en la base, de más caída a más subida: `cmun`, `municipio`, `zona`, `grupo`, `alumnos_base`, `nacidos`, `prevision`, `p10`, `p90`, `cambio_pct`, `cambio_p10`, `cambio_p90` (como [`resultados/ranking_ultimo_curso.csv`](../resultados/ranking_ultimo_curso.csv)) |

## `municipios/{cmun}.json`

| Campo | Contenido |
|---|---|
| `cmun`, `municipio`, `zona`, `tiene_colegio` | Identificación |
| `poblacion` | `anio`, `habitantes` (padrón) |
| `base` | Último curso con matrícula publicada |
| `ficha_web` | Enlace a la ficha del municipio en la web |
| `nacidos[]` | `anio`, `nacidos` (por residencia de la madre), de 2008 en adelante |
| `senal_llegada_familias` | Solo con colegio. `anio_censo`, `ninos_0_4` censados, `ninos_0_4_por_100_nacidos` (frente a los nacidos de `nacidos_desde` a `nacidos_hasta`) y `lectura`. Por encima de 105 llegan familias con niños pequeños y el método tiende a quedarse corto |
| `primero_primaria` | Solo con colegio. `grupo`, `alumnos_base`, `factor` (alumnos de 1.º por cada niño nacido en el municipio; previsión = nacidos seis años antes × factor), `tipo_factor`, `serie_observada[]` (`curso`, `t`, `alumnos`) y `prevision[]` (`curso`, `t`, `h`, `nacidos`, `prevision`, `p10`, `p90`, `cambio_pct`, `cambio_p10`, `cambio_p90`, `n_residuos`) |
| `infantil_3_5` | Igual, para infantil de 3 a 5 años; `nacidos_3_cohortes` en vez de `nacidos` y `factor` = alumnos por nacido de las tres cohortes en la base |
| `fiabilidad` | Ver abajo |
| `notas` | Solo en la capital: por qué no baja a distritos |

`fiabilidad` (en municipios sin colegio solo lleva `avisos`):

| Campo | Contenido |
|---|---|
| `grupo` | Grupo de tamaño en 1.º |
| `error_mediano_grupo_pct` | Por antelación (`"1"` a `"6"`): error mediano del radar (`radar`), de suponer que nada cambia (`ingenuo`) y de contar solo nacidos (`nacidos`), en %, y `n` casos. Es la tabla de error de la web |
| `sesgo_grupo_pct` | Sesgo del radar en el grupo, por antelación: (suma de previstos − suma de reales) / suma de reales, en %. Negativo: se queda corto |
| `grupo_intervalos`, `cobertura_intervalos_grupo_pct` | Grupo cuyos errores dan el intervalo y % de casos del backtest en que el intervalo, calculado sin la base evaluada, contuvo el dato real (objetivo: 80 %) |
| `ancho_intervalo_ultimo_curso_pct` | Ancho del intervalo en el último curso, en % de la previsión |
| `error_propio` | Previsiones del propio municipio hechas con 2 o más cursos de antelación: `n`, `mediana_abs_pct`, `media_pct`. `null` si hay menos de 3 |
| `donde_falla` | Si el municipio está en [`resultados/donde_falla_por_municipio.csv`](../resultados/donde_falla_por_municipio.csv) (50 alumnos de 1.º o más): `err_medio` y `ape_medio` (%, previsiones a 2-4 cursos), `ninos_0_4_por_100_nacidos` (Censo de `anio_censo`), `alumnos_1o_por_nacido_inicial`, `horizontes` y `definicion`. Si no, `null` |
| `previsiones_pasadas[]` | Backtest del municipio: `b`/`curso_base` (cuándo se hizo), `h`, `t`/`curso` (para qué curso), `y` (alumnos reales), `prevision` (radar), `p_naive` (nada cambia), `error_pct`, `error_naive_pct` |
| `avisos[]` | Los avisos que enseña la ficha de la web: `tipo` (`sin_colegio`, `municipio_pequeno`, `error_propio_alto`, `infantil_pequeno`), `etapa` (`"1o"`, `"infantil"` o `null`) y `texto` |
| `infantil` | `grupo` y `error_mediano_grupo_pct` (radar e ingenuo, de 1 a 3 cursos) para infantil |

El aviso `error_propio_alto` aparece cuando la mediana del error absoluto de las previsiones propias a 2 o más cursos supera el 15 %: el intervalo es el del grupo y no recoge ese sesgo.
