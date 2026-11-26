# Análisis complementarios (26-nov-2026)

- **[moran/](moran/):** diagnóstico espacial de los residuos del backtest (I de Moran, vecindad de reina, 9.999 permutaciones).
  - Los errores con signo no se agrupan en el mapa: I = −0,02, p = 0,98 en los 36 municipios grandes a cinco cursos.
  - Resultado y cautelas en [moran/RESULTADO.md](moran/RESULTADO.md).
  - Se reproduce con `python analisis/moran/moran.py --datos <carpeta de datos>`; los datos se descargan con `python -m radar todo`.
- **[asistente/](asistente/):** asistente de IA especializado, sin reentrenar: un modelo general conectado al radar por API/MCP, con reglas.
  - Evaluado con 10 preguntas: 10/10. Son 8/8 de dato con cifra, intervalo y fuente, y 2/2 trampas rechazadas.
  - Lo respondió un agente nuevo con un modelo de IA general, y lo puntuó [asistente/evaluar.py](asistente/evaluar.py) de forma determinista contra la API de producción.
  - Es una prueba pequeña: demuestra el método, no que acierte siempre.

- **[verificar_cifras.py](verificar_cifras.py):** contrasta con la API de producción cada cifra que aparece en las diapositivas, la ficha y el guion, redondeando una sola vez. Termina con error si alguna no coincide (`python analisis/verificar_cifras.py`).

