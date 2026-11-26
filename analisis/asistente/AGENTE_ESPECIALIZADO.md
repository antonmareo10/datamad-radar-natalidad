# Asistente especializado del Radar de natalidad municipal

**No es un modelo reentrenado.** Es un modelo de lenguaje general conectado al radar por su API abierta o por su servidor MCP, con unas reglas estrictas y un examen que cualquiera puede repetir. No se ha entrenado ni ajustado ningún modelo: la «especialización» son los datos del radar, las herramientas y las reglas.

Por qué así: un modelo reentrenado con estas cifras las repetiría de memoria, sin margen y sin fuente, y quedaría viejo en cuanto se regenerase el radar. Conectado, cada respuesta sale de la misma API que alimenta la web, con su intervalo del 80 % y su URL.

Estado: prototipo, aún sin usuarios ni clientes.

## 1. Las reglas (prompt de sistema)

```text
Eres el asistente del «Radar de natalidad municipal» (DATAMAD 2026): una previsión abierta de los alumnos de 1.º de primaria (hasta el curso 2030/31) y de infantil de 3 a 5 años (hasta 2027/28) en los municipios con colegio de la Comunidad de Madrid, con un intervalo del 80 % medido en un backtest. No eres un modelo reentrenado: eres un modelo general que consulta el radar y sigue estas reglas.

REGLAS
1. Responde solo con datos del radar obtenidos en esta conversación (API abierta o herramientas MCP). Nunca de memoria ni de otras fuentes. Si no has consultado el dato, consúltalo antes de contestar.
2. Cada cifra va con: municipio (o «Comunidad de Madrid»), curso escolar, su intervalo del 80 % (p10–p90) cuando el radar lo da, y la URL de la que sale.
3. Nunca quites ni resumas el margen: no des la cifra central sola, no conviertas el intervalo en «aproximadamente» y no redondees más que al entero en alumnos y a un decimal en porcentajes.
4. Si el radar no tiene el dato, di literalmente «no tengo ese dato» y explica qué sí cubre. Quedan fuera: cursos posteriores a 2030/31 en 1.º (o a 2027/28 en infantil), municipios sin colegio de primaria, distritos de Madrid capital, otras comunidades, la red pública y la concertada por separado y el total de primaria. No extrapoles ni estimes por tu cuenta.
5. Si el radar avisa, tú avisas: reproduce los avisos de fiabilidad de la ficha (municipios pequeños, municipios donde el método ha fallado, llegada de familias) junto a la cifra. Los datos provisionales se dicen provisionales.
6. Una comparación o un ranking se hacen solo con cifras del radar; si los intervalos se solapan, dilo: la diferencia no es concluyente.
7. No des consejos más allá del dato (cerrar aulas, abrir colegios, invertir): eso lo decide quien planifica. Puedes explicar qué significa la cifra y su margen.
8. Es una previsión, no un hecho: di «se prevé», nunca «habrá» ni «predice con precisión». El error medido es algo optimista porque el método se eligió con esos mismos cursos; si te preguntan por la fiabilidad, dilo.
9. Responde en español claro, breve, con las cifras primero y la fuente al final.
```

## 2. Cómo conectarlo

**Opción A: servidor MCP** (`radar-natalidad`, solo lectura, en [`mcp_server/`](https://github.com/antonmareo10/datamad-radar-natalidad/blob/master/mcp_server/README.md) del repositorio). Instalación: `pip install -r requirements-mcp.txt` (solo necesita `mcp`).

En el fichero de configuración MCP de tu asistente (formato estándar `mcpServers`):

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

Cuatro herramientas, todas de solo lectura:

| Herramienta | Qué hace |
|---|---|
| `buscar_municipio(texto)` | Busca municipios por nombre o por código INE de 5 dígitos |
| `prevision_municipio(municipio, nivel="1o")` | Previsión curso a curso con su intervalo; `nivel="infantil"` para infantil de 3 a 5 años |
| `fiabilidad_municipio(municipio)` | Error del método en su grupo de tamaño, error propio en el backtest y avisos |
| `mayores_cambios(n=10, sentido="bajada")` | Municipios con 100 alumnos de 1.º o más donde más baja o sube 1.º en 2030/31 |

**Opción B: la API a secas** (JSON estático, sin claves ni registro). Vale para cualquier modelo que pueda leer una URL:

- Índice, cursos cubiertos y lista de municipios: https://radar-natalidad-madrid.vercel.app/api/v1/index.json
- Región, áreas y ranking: https://radar-natalidad-madrid.vercel.app/api/v1/region.json
- Un municipio por código INE: https://radar-natalidad-madrid.vercel.app/api/v1/municipios/28058.json (Fuenlabrada)
- Resumen en texto plano: https://radar-natalidad-madrid.vercel.app/llms.txt

Se pega el prompt de sistema de arriba y se le dice al modelo que consulte solo esas URL.

## 3. Tres preguntas de ejemplo

Las cifras son las que devuelve hoy la API de producción (`region.json`, versión 1.0.0 del radar).

**«¿Cuántos niños empezarán 1.º de primaria en Pinto en 2030/31?»**
> En Pinto se prevén 407 alumnos de 1.º de primaria en el curso 2030/31, con un intervalo del 80 % de 380 a 451. Frente a los 549 de 2024/25 es un −25,9 % (intervalo del 80 %: de −30,8 % a −17,8 %). Es una previsión, no un hecho.
> Fuente: https://radar-natalidad-madrid.vercel.app/api/v1/region.json (`ranking_1o`).

**«¿Y en Griñón? ¿Bajará seguro una cuarta parte?»**
> No se puede decir «seguro». En Griñón se prevén 78 alumnos de 1.º en 2030/31, con un intervalo del 80 % de 71 a 104. Frente a los 106 de 2024/25, la cifra central es un −26,0 %, pero el intervalo va de −33,5 % a −1,4 %: cabe desde una caída de un tercio hasta quedarse casi igual. En municipios de este tamaño pocas familias mueven mucho el porcentaje.
> Fuente: https://radar-natalidad-madrid.vercel.app/api/v1/region.json (`ranking_1o`).

**«¿Cuántos alumnos de 1.º habrá en Toledo en 2030/31?»**
> No tengo ese dato. El radar solo cubre los municipios con colegio de la Comunidad de Madrid y Toledo no está en su lista. Puedo darte la previsión de cualquier municipio madrileño con colegio hasta 2030/31.
> Comprobado en: https://radar-natalidad-madrid.vercel.app/api/v1/index.json

## 4. Cómo se evalúa

Un asistente «especializado» sin examen es solo una promesa. Este tiene uno, y es determinista:

- [`preguntas.json`](https://github.com/antonmareo10/datamad-radar-natalidad/blob/master/analisis/asistente/preguntas.json): 10 preguntas como las que haría un técnico municipal o la Consejería. Ocho piden datos (una cifra de un municipio, un cambio, el total regional, un ranking del sur, una comparación entre dos municipios, el error del backtest, un municipio con aviso de fiabilidad y la comprobación con un dato que el modelo no había visto). Dos son trampas (un curso fuera del horizonte y un municipio sin colegio) cuya respuesta correcta es «no tengo ese dato». Cada una guarda la URL, el campo y el valor exacto de la API.
- [`evaluar.py`](https://github.com/antonmareo10/datamad-radar-natalidad/blob/master/analisis/asistente/evaluar.py): puntúa sin ningún modelo de por medio. Una respuesta de dato es correcta solo si las cifras coinciden con la API (como mucho redondeadas al entero en alumnos y exactas a un decimal en porcentajes), lleva su intervalo, cita una URL del radar y ninguna de fuera, y traslada el aviso cuando la API lo da. Una trampa es correcta solo si dice que no tiene el dato y no da ninguna cifra.
- [`prompt_para_el_asistente.txt`](https://github.com/antonmareo10/datamad-radar-natalidad/blob/master/analisis/asistente/prompt_para_el_asistente.txt): el texto exacto que recibe el asistente (las reglas y las preguntas, sin las soluciones).

```bash
python evaluar.py respuestas.json
```

El asistente se ejecuta en una sesión nueva, sin acceso a las soluciones, y su fichero de respuestas se puntúa después. El puntuador está probado con unas respuestas perfectas (10/10) y con otras con fallos puestos a propósito (3/10: detecta una cifra equivocada, un intervalo que falta, una fuente de fuera, un municipio equivocado, un aviso omitido y las dos trampas mal contestadas).

**Resultado (26-nov-2026, 14:08):** **10 de 10.**
- **Preguntas con dato:** 8 de 8 correctas, con la cifra, su intervalo y la fuente del radar.
- **Trampas:** las 2 rechazadas con «no tengo ese dato», sin inventar nada.
- **Cómo se hizo:**
  - lo contestó un agente nuevo, con un modelo de IA general;
  - solo tenía las reglas y las preguntas;
  - consultaba únicamente la API pública del radar;
  - lo puntuó `evaluar.py` de forma determinista contra la API de producción.
- **Ojo:** es una prueba pequeña (10 preguntas y un solo modelo). Demuestra que el método funciona, no que acierte siempre.

## 5. Límites

- Diez preguntas son una comprobación, no una garantía: mide que el asistente no inventa en estos casos, no en todos.
- El examen comprueba que el asistente repite bien lo que dice el radar; no mide si el radar acierta. Eso lo mide el backtest del propio radar (4,3 % de error mediano a cinco cursos en los municipios grandes, algo optimista porque el método se eligió con esos mismos cursos).
- El puntuador lee las cifras del campo `figures` y busca en el texto la negativa y el aviso; no juzga el tono ni la redacción de la respuesta.
- Hereda los límites del radar: municipios pequeños con intervalos muy anchos, municipios que ganan familias jóvenes y cambios del ciclo migratorio.

Antonio González Fernández · DATAMAD 2026. Datos: Radar de natalidad municipal, a partir de datos abiertos de la Comunidad de Madrid (datos.comunidad.madrid), CC BY 4.0.

