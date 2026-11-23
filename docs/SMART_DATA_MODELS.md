# Las previsiones en Smart Data Models (FIWARE)

Además de la [API propia](API.md), las previsiones de 1.º de primaria se publican siguiendo un modelo de [Smart Data Models](https://smartdatamodels.org), la iniciativa de modelos de datos abiertos de FIWARE, para que cualquier plataforma NGSI-LD o de ciudad inteligente las pueda leer sin adaptar nada.

- **Fichero:** [`https://radar-natalidad-madrid.vercel.app/api/v1/sdm/observaciones_1o.json`](https://radar-natalidad-madrid.vercel.app/api/v1/sdm/observaciones_1o.json)
- **Contenido:** una entidad por municipio con colegio y curso previsto de 1.º de primaria (136 municipios × 6 cursos, de 2025/26 a 2030/31: 816 entidades), en una lista JSON.
- **Cómo se genera:** `python -m radar web`, a partir de los mismos datos que `municipios/{cmun}.json` ([`radar/sdm.py`](../radar/sdm.py)).
- **Validación:** [`tests/test_sdm.py`](../tests/test_sdm.py) valida todas las entidades contra el JSON Schema oficial del modelo y comprueba que las cifras son las de la API v1.

## Modelo elegido: SDMX `Observation`

[`dataModel.SDMX/Observation`](https://github.com/smart-data-models/dataModel.SDMX/tree/master/Observation) es la adaptación a Smart Data Models de SDMX, el estándar de intercambio de datos estadísticos (norma ISO 17369), a partir del vocabulario RDF Data Cube. Encaja por tres motivos:

1. Una previsión de alumnos de un municipio en un curso es una observación estadística: un valor (`obsValue`) para un área (`refArea`) y un periodo (`timePeriod`), descrito por sus dimensiones (`dimensions`).
2. SDMX tiene un código para decir que el valor es una previsión y no un dato observado: `obsStatus` = `F`, «Forecast value» en la lista de códigos de estado de la observación que cita el modelo.
3. Es el estándar con el que publican Eurostat y otras oficinas de estadística, así que las cifras se pueden poner junto a datos oficiales sin traducir conceptos.

Descartados, entre los 106 repositorios de la organización [smart-data-models](https://github.com/smart-data-models) consultados el 23-nov-2026:

- [`KeyPerformanceIndicator`](https://github.com/smart-data-models/dataModel.KeyPerformanceIndicator): mide el desempeño de una organización, un proceso o un producto (`kpiValue`, `organization`, `process`, `currentStanding`). No tiene dimensiones ni forma de marcar un valor como previsión.
- [`SDG/Indicator`](https://github.com/smart-data-models/dataModel.SDG): indicadores ligados a proyectos y acciones de los Objetivos de Desarrollo Sostenible (`refProject`, `expectedValue`).
- [`PredictiveMaintenance/AIPrediction`](https://github.com/smart-data-models/dataModel.PredictiveMaintenance): predicciones de mantenimiento de máquinas; obliga a campos como `laser`, `head` o `anomalyType`.
- No hay un modelo de educación ni de previsiones de población entre esos repositorios. No he revisado los modelos en preparación (repositorios `incubated` y `drafted_models`).

## Cómo se rellena cada entidad

Ejemplo (Fuenlabrada, 2030/31), en la representación keyValues:

```json
{
  "id": "urn:ngsi-ld:Observation:radar-natalidad:1o:28058:2030",
  "type": "Observation",
  "identifier": "radar-natalidad-1o-28058-2030",
  "title": "https://radar-natalidad-madrid.vercel.app/api/v1/sdm/observaciones_1o.json#28058-2030",
  "name": "Alumnos de 1.º de primaria previstos en Fuenlabrada, curso 2030/31",
  "obsValue": 1150.107,
  "obsStatus": "F",
  "confStatus": "F",
  "decimals": 3,
  "unitMult": 0,
  "freq": "A",
  "refArea": "28058",
  "timePeriod": "2030",
  "dimensions": [{"key": "cmun", "value": "28058"}, {"key": "nivel", "value": "1o"}, {"key": "curso", "value": "2030/31"}, {"key": "h", "value": "6"}],
  "address": {"addressLocality": "Fuenlabrada", "addressRegion": "Comunidad de Madrid", "addressCountry": "ES"},
  "source": "https://radar-natalidad-madrid.vercel.app/api/v1/municipios/28058.json",
  "dataProvider": "Radar de natalidad municipal",
  "seeAlso": ["https://radar-natalidad-madrid.vercel.app/#municipio=28058", "https://github.com/antonmareo10/datamad-radar-natalidad/blob/master/docs/SMART_DATA_MODELS.md"],
  "predictionInterval": {"lowerBound": 1074.53, "upperBound": 1276.518, "level": 0.8},
  "license": "https://creativecommons.org/licenses/by/4.0/",
  "@context": ["https://raw.githubusercontent.com/smart-data-models/dataModel.SDMX/master/context.jsonld", {"license": "http://purl.org/dc/terms/license"}]
}
```

(Se omite `description`, un texto que explica la previsión.)

| Campo | Del modelo | Valor |
|---|---|---|
| `id` | Sí | `urn:ngsi-ld:Observation:radar-natalidad:1o:{cmun}:{t}` |
| `type` | Sí | `Observation` |
| `identifier`, `title` | Sí | Identificador y URI de la observación |
| `name`, `description` | Sí (comunes) | Texto en español |
| `obsValue` | Sí | Alumnos previstos (`prevision` de la API, 3 decimales) |
| `obsStatus` | Sí | `F`: valor previsto |
| `confStatus` | Sí | `F`: libre, sin restricciones de confidencialidad |
| `freq` | Sí | `A`: anual, un valor por curso |
| `decimals`, `unitMult` | Sí | 3 decimales; unidades (multiplicador 10⁰) |
| `refArea` | Sí | Código INE del municipio, 5 dígitos |
| `timePeriod` | Sí | Año en que empieza el curso (`"2030"` para 2030/31), como el campo `t` de la API |
| `dimensions` | Sí | `cmun`, `nivel` (`1o`), `curso` (`2030/31`) y `h` (cursos de antelación) |
| `address` | Sí (comunes) | Municipio, Comunidad de Madrid, ES |
| `source` | Sí (comunes) | El fichero del municipio en la API v1, del que sale la cifra |
| `dataProvider` | Sí (comunes) | `Radar de natalidad municipal` |
| `seeAlso` | Sí (comunes) | La ficha del municipio en la web y este documento |
| `predictionInterval` | **No** | Intervalo del 80 % (ver abajo) |
| `license` | **No** | CC BY 4.0 (ver abajo) |
| `@context` | — | El `@context` oficial del modelo y la definición de `license` |

Los códigos `F`, `A` y `F` de `obsStatus`, `freq` y `confStatus` son los de las listas SDMX que cita el esquema; sus etiquetas («Forecast value», «Annual», «Free») están en el vocabulario SDMX-RDF del que deriva el modelo ([`sdmx-code.ttl`](https://github.com/UKGovLD/publishing-statistical-data/blob/master/specs/src/main/vocab/sdmx-code.ttl)).

## Lo que el modelo no cubre

- **Intervalo de la previsión.** `Observation` solo tiene un valor (`obsValue`). El intervalo del 80 % va en una propiedad añadida, `predictionInterval`, con `lowerBound` (p10), `upperBound` (p90) y `level` (0,8). No tiene término en el `@context` oficial: un procesador JSON-LD la expande con el vocabulario por defecto de NGSI-LD.
- **Licencia.** El modelo no tiene licencia por observación; en DCAT-AP la licencia va en la distribución del conjunto de datos. Cada entidad lleva `license` como propiedad añadida, definida en el `@context` como `dct:license`.
- **Fecha.** El modelo no tiene `dateObserved`: el tiempo de la observación es `timePeriod`. SDMX no tiene un formato para un curso escolar, así que `timePeriod` es el año en que empieza y el curso exacto va en `dimensions`. La fecha en que se generaron los datos está en `index.json` (`generado_utc`).
- **Área.** El esquema remite a la lista de áreas de SDMX, que recoge países y agrupaciones de países, no municipios. `refArea` lleva el código INE del municipio y `address` su nombre.
- **Conjunto de datos.** El modelo permite enlazar cada observación con su `dataset` (por ejemplo, una entidad `Dataset` de STAT-DCAT-AP). No publico esa entidad todavía, así que el campo va vacío.
- **Alcance.** Solo 1.º de primaria. Infantil seguiría el mismo patrón con `nivel` = `infantil`.
- **Representación.** Se publica la forma keyValues, que es la que describe y valida el JSON Schema oficial. Los ejemplos oficiales del modelo incluyen también la forma NGSI-LD normalizada (cada atributo dentro de `{"type": "Property", "value": …}`), que no publico. No he cargado las entidades en un context broker.

## Validación

`tests/test_sdm.py` valida las 816 entidades con `jsonschema` (Draft 2020-12, formatos `uri` incluidos) contra copias sin modificar de los esquemas oficiales, guardadas en [`tests/sdm/`](../tests/sdm/) para no depender de la red:

- `Observation.schema.json`, de [smart-data-models/dataModel.SDMX](https://github.com/smart-data-models/dataModel.SDMX/blob/master/Observation/schema.json) (commit `55b4393`, 18-sep-2024);
- `common-schema.json`, de [smart-data-models/data-models](https://github.com/smart-data-models/data-models/blob/master/common-schema.json) (commit `2a72152`, 1-feb-2026), que define los campos comunes.

El test comprueba también que el esquema rechaza valores fuera de las listas de códigos, para asegurar que la validación no pasa en vacío, y que `obsValue` y el intervalo son exactamente los de `municipios/{cmun}.json`.

## Uso

```bash
# previsión de Fuenlabrada para 2030/31 con su intervalo
curl -s https://radar-natalidad-madrid.vercel.app/api/v1/sdm/observaciones_1o.json \
  | jq '.[] | select(.refArea == "28058" and .timePeriod == "2030") | {name, obsValue, predictionInterval}'
```
