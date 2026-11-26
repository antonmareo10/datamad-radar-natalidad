# Servidor MCP del Radar de natalidad municipal

Servidor [MCP](https://modelcontextprotocol.io) de solo lectura para que un asistente de IA (cualquier cliente MCP) consulte el radar: cuántos alumnos entrarán en 1.º de primaria y en infantil en cada municipio de la Comunidad de Madrid, con su intervalo del 80 % y lo fiable que ha sido el método allí.

- **Nombre del servidor:** `radar-natalidad`. Transporte stdio.
- **Datos:** lee la [API abierta](../docs/API.md) publicada (`https://radar-natalidad-madrid.vercel.app/api/v1/`) o, con `--local`, los mismos JSON de `web/api/v1/` sin conexión. No escribe nada ni necesita claves.
- **Respuestas:** en español; toda previsión va con su intervalo del 80 % y con los avisos de fiabilidad que enseña la ficha de la web.
- **SDK:** el oficial de MCP para Python (`mcp`): `MCPServer` en la serie 2.x, que en la 1.x se llamaba `FastMCP`; el servidor funciona con las dos.

## Herramientas

| Herramienta | Qué hace |
|---|---|
| `buscar_municipio(texto)` | Busca municipios por nombre (sin importar tildes ni mayúsculas) o por código INE de 5 dígitos |
| `prevision_municipio(municipio, nivel="1o")` | Previsión curso a curso con su intervalo y el cambio frente al último curso publicado. `nivel="1o"`: 1.º de primaria hasta 2030/31; `nivel="infantil"`: infantil de 3 a 5 años hasta 2027/28 |
| `fiabilidad_municipio(municipio)` | Error del método en su grupo de tamaño, error propio en el backtest, cómo habría acertado el último curso, señal de llegada de familias y avisos |
| `mayores_cambios(n=10, sentido="bajada")` | Municipios con 100 alumnos de 1.º o más donde más baja (`"bajada"`) o sube (`"subida"`) el alumnado de 1.º previsto para 2030/31 |

`municipio` admite el nombre (`"Fuenlabrada"`, `"las rozas"`) o el código INE (`"28058"`). Las cuatro están marcadas como de solo lectura (`readOnlyHint`).

## Instalación

Desde la raíz del repositorio, con Python 3.10 o posterior:

```bash
python -m venv .venv
.venv/Scripts/activate          # en Linux o macOS: source .venv/bin/activate
pip install -r requirements-mcp.txt
```

El servidor solo necesita `mcp`; no hace falta instalar pandas ni descargar los datos.

## Añadirlo a un asistente

En el fichero de configuración MCP de tu cliente (formato estándar `mcpServers`), con el Python del entorno donde instalaste `mcp` (por ejemplo `/ruta/al/repo/.venv/Scripts/python.exe` en Windows o `/ruta/al/repo/.venv/bin/python` en Linux y macOS), y reinicia el cliente:

```json
{
  "mcpServers": {
    "radar-natalidad": {
      "command": "C:/ruta/al/repo/.venv/Scripts/python.exe",
      "args": ["C:/ruta/al/repo/mcp_server/server.py"]
    }
  }
}
```

Sin conexión, añade `"--local"` al final de `args` para leer los JSON de `web/api/v1/`. Con `"--url", "https://otra-copia/api/v1/"` lee otra copia de la API (también vale la variable de entorno `RADAR_API`).

## Ejemplo

Pregunta a un asistente con el servidor conectado: *«¿Cuántos niños empezarán 1.º de primaria en Fuenlabrada en los próximos cursos?»*. El asistente llama a `prevision_municipio(municipio="Fuenlabrada", nivel="1o")`, que responde esto (salida real de `python mcp_server/demo.py`, con los datos de esta versión; un test comprueba que sigue coincidiendo):

<!-- ejemplo-demo:inicio -->
```text
Fuenlabrada (código INE 28058, área Sur) · 1.º de primaria.
Último curso con matrícula publicada: 2024/25, con 1.560 alumnos.

Previsión del radar (entre paréntesis, el intervalo del 80 %):
- 2025/26: 1.542 alumnos (1.459–1.669); frente a 2024/25, −1,1 % (−6,5 % a +7,0 %).
- 2026/27: 1.397 alumnos (1.321–1.519); frente a 2024/25, −10,4 % (−15,3 % a −2,6 %).
- 2027/28: 1.273 alumnos (1.199–1.386); frente a 2024/25, −18,4 % (−23,1 % a −11,1 %).
- 2028/29: 1.269 alumnos (1.188–1.399); frente a 2024/25, −18,7 % (−23,8 % a −10,3 %).
- 2029/30: 1.191 alumnos (1.113–1.318); frente a 2024/25, −23,7 % (−28,7 % a −15,5 %).
- 2030/31: 1.150 alumnos (1.075–1.277); frente a 2024/25, −26,3 % (−31,1 % a −18,2 %).

Cómo se calcula: nacidos en el municipio seis años antes × su factor (1,016 alumnos de 1.º por cada niño nacido aquí, medido en su matrícula de infantil de 2024/25). El intervalo sale de los errores reales del backtest en municipios grandes con la misma antelación.
Avisos de fiabilidad: ninguno.

Ficha en la web: https://radar-natalidad-madrid.vercel.app/#municipio=28058
Fuente: Radar de natalidad municipal, a partir de datos abiertos de la Comunidad de Madrid (CC BY 4.0).
```
<!-- ejemplo-demo:fin -->

Con esa respuesta el asistente puede contestar, por ejemplo, que se esperan unos 1.150 alumnos en 2030/31 (entre 1.075 y 1.277), un 26 % menos que los 1.560 de 2024/25. Para un municipio donde el método ha fallado, como Buitrago del Lozoya, `fiabilidad_municipio` devuelve el aviso de la ficha («Aquí el radar ha fallado bastante en el pasado…») junto con sus errores.

## Probarlo sin asistente

```bash
python mcp_server/demo.py                    # las cuatro herramientas con los JSON locales (sin internet)
python mcp_server/demo.py --municipio Getafe
python mcp_server/demo.py --url https://radar-natalidad-madrid.vercel.app/api/v1/
```

`demo.py` llama a las mismas funciones que el servidor ([`herramientas.py`](herramientas.py)) e imprime lo que devuelven; no necesita el SDK de MCP.

## Tests

```bash
python -m pytest tests/test_mcp_herramientas.py tests/test_mcp_stdio.py
```

`test_mcp_herramientas.py` prueba las funciones contra los JSON locales. `test_mcp_stdio.py` arranca el servidor por stdio con el cliente del SDK oficial, comprueba que anuncia exactamente estas cuatro herramientas, de solo lectura, y llama a dos (se salta si `mcp` no está instalado).
