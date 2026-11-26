# Diagnóstico espacial de los residuos del backtest (I de Moran)

Calculado el 26-nov-2026 con `moran.py` (semilla 20261126, 9 999 permutaciones). Dos ejecuciones seguidas dan el mismo `resultado.json` (mismo MD5). No se ha tocado el repositorio.

## Conclusión (una frase)

> Los errores del backtest no se agrupan en el espacio: a cinco cursos, en los 36 municipios grandes, I de Moran = −0,02 (esperado −0,03; p = 0,98 con 9 999 permutaciones), así que el radar no falla sistemáticamente hacia el mismo lado en ninguna zona.

Matiz que hay que decir si preguntan: el **tamaño** del error (valor absoluto) sí se parece algo entre vecinos cuando entran todos los municipios (I = +0,10; p = 0,046; n = 132), pero es el efecto del tamaño del municipio, no del sitio: los pequeños fallan más y son vecinos entre sí. Permutando solo entre municipios del mismo grupo de tamaño, desaparece (p = 0,64). Eso ya está cubierto: los intervalos se calculan por grupo de tamaño y los de los pequeños son más anchos (README, «Dónde falla»: ancho mediano del 108 % frente al 18 % en los grandes).

## Cifras nuevas, con su definición exacta

Residuo por municipio: `err = (previsto − real) / real × 100` de la especificación elegida (`config.ESPEC_1O = p_finfk`), el mismo que usa `radar/calcular.py` en «dónde falla»; una cifra por municipio = media de `err` sobre las bases del backtest en el horizonte indicado. Positivo = el radar previó de más. Pesos: reina, estandarizados por filas. E[I] = −1/(n−1). p a dos colas = (nº de permutaciones con |I* − E[I]| ≥ |I − E[I]| + 1) / 10 000; p superior = (nº con I* ≥ I + 1) / 10 000 (la cola de «se agrupan»).

| Muestra | n | Error | I | E[I] | p dos colas | p superior |
|---|---|---|---|---|---|---|
| **A. 36 grandes, h = 5 cursos** (la cifra del 4,3 %) | 36 | con signo | **−0,024** | −0,029 | **0,977** | 0,469 |
| | 36 | absoluto | +0,114 | −0,029 | 0,283 | 0,143 |
| A2. 36 grandes + Madrid capital, h = 5 | 37 | con signo | +0,008 | −0,028 | 0,762 | 0,359 |
| | 37 | absoluto | +0,128 | −0,028 | 0,183 | 0,096 |
| B. Definición del repo `donde_falla_por_municipio.csv` (`err_medio`: grandes, medianos y capital, h = 2-4) | 79 (81 − 2 islas) | con signo | +0,090 | −0,013 | 0,197 | 0,104 |
| | 79 | absoluto | −0,057 | −0,013 | 0,585 | 0,697 |
| F. Grandes, medianos y capital, h = 5 | 79 | con signo | −0,032 | −0,013 | 0,819 | 0,581 |
| | 79 | absoluto | −0,052 | −0,013 | 0,635 | 0,678 |
| C. Todos los municipios, h = 5 | 131 (134 − 3 islas) | con signo | −0,129 | −0,008 | 0,028 | 0,995 |
| | 131 | absoluto | +0,087 | −0,008 | 0,065 | 0,055 |
| **D. Todos los municipios, h = 1-6** | 132 (135 − 3 islas) | con signo | **−0,047** | −0,008 | **0,440** | 0,768 |
| | 132 | absoluto | +0,099 | −0,008 | 0,046 | 0,043 |
| | 132 | absoluto, permutando dentro del grupo de tamaño | +0,099 | +0,069 (media de las permutaciones) | 0,643 | 0,273 |
| E. Como D con el residuo logarítmico de los intervalos, −log(real/previsto) | 132 | con signo | −0,022 | −0,008 | 0,791 | 0,599 |
| | 132 | absoluto | +0,107 | −0,008 | 0,037 | 0,032 |

Todo lo demás (rangos, k = 4 vecinos más próximos, desviación típica de las permutaciones, enlaces) está en `resultado.json` y `salida_consola.txt`.

Comprobaciones del recálculo contra cifras ya congeladas (no cambian): error mediano a 5 cursos en grandes 4,35 % → 4,3 % (72 previsiones = 36 municipios × bases 2018/19 y 2019/20, reales 2023/24 y 2024/25); ingenuo 16,1 %; los 81 `err_medio` coinciden con el CSV del repo (diferencia máxima 0,00).

## Método

1. **Residuos.** El script importa el código del repo (`radar.calcular.cargar_todo`, `radar.backtest.backtest_primero`, `muestra_comun`) y recalcula el backtest en memoria desde los ficheros crudos (`datos/crudos`, descargados con `python -m radar descargar`; aquí en `<ruta local>`, porque `datos/` no se sube al repo). Columnas: `p_finfk` (previsión), `y` (real), `h`, `b`, `grupo`, `cmun`.
2. **Unidades y vecindad.** Shapefile «Municipios y Distritos de Madrid (2020)» (`municipios_y_distritos_madrid_20.zip`, leído con `radar.geo.leer_zip`), sin simplificar; los 21 distritos de la capital forman una sola unidad (28079), como en la previsión. 179 unidades, 471 parejas vecinas. Reina = fronteras a 1 m o menos (incluye tocarse en un punto); comprobado con un segundo método independiente (comparten algún vértice): las mismas 471 parejas. Madrid capital tiene 16 vecinos. Ningún municipio queda sin vecinos en el mapa completo.
3. **Islas.** En cada muestra solo cuentan los vecinos que también están en la muestra. Los municipios sin ninguno se excluyen y se cuentan: 0 en A (los 36 grandes tienen todos algún grande al lado; 62 parejas, 3,4 vecinos de media), 2 en B y F (Buitrago del Lozoya y Nuevo Baztán), 3 en C, D y E (28076, 28100 y 28107). Control sin islas con k = 4 vecinos más próximos: misma lectura.
4. **Contraste.** 9 999 permutaciones aleatorias de los valores entre municipios, numpy, semilla fija. Local (LISA, permutaciones condicionadas): en A, 2 municipios con p < 0,05 (por azar se esperan 1,8); en D, 14 (se esperan 6,6); ninguno resiste la corrección por comparaciones múltiples (FDR 5 %). Tablas en `lisa_*.csv`.

## Cautelas (no esconder)

- **n = 36 es poco.** La desviación típica de I bajo permutación es 0,13: solo se detectaría una autocorrelación fuerte (I de +0,23 o más, aproximadamente). «No se detecta agrupación» no es «está demostrado que no la hay». Por eso se da también con todos los municipios (n = 132, desviación 0,05).
- **En C (todos, h = 5) el I con signo es negativo y significativo a dos colas** (−0,13; p = 0,028): vecinos con errores de signo contrario, lo opuesto a agruparse. Lo mueven valores extremos de municipios pequeños: con rangos I = −0,04 (p = 0,60) y con k = 4 vecinos p = 0,23. No se debe presentar como hallazgo ni ocultar.
- En B, con rangos, I = +0,13 (p superior 0,043; dos colas 0,079): indicio débil, no significativo a dos colas ni con los valores originales (p = 0,20).
- Cada municipio aporta la media de previsiones con bases solapadas (2 bases a h = 5; hasta 21 en h = 1-6): no son independientes en el tiempo, pero el contraste es entre municipios, uno por unidad.
- Los errores por municipio de la especificación elegida son algo optimistas (la elección se hizo sobre la misma muestra, ya dicho en el README); eso afecta al tamaño del error, no a su reparto en el mapa.
- Varias muestras y variantes contrastadas (7 muestras × signo/absoluto): los p no están corregidos entre sí. La cifra principal (A, con signo) no se eligió por su resultado: es la muestra y el horizonte del titular del proyecto, fijados en el encargo antes de calcular.

## Textos propuestos (≤ 2 líneas cada uno; no se ha editado ningún documento)

**README, «Resultados»:**
> - Diagnóstico espacial de los residuos: los errores con signo del backtest no se agrupan en el mapa (I de Moran = −0,02 a cinco cursos en los 36 municipios grandes, p = 0,98; −0,05 con todos los municipios y horizontes, n = 132, p = 0,44; vecindad de reina, 9 999 permutaciones). El tamaño del error sí depende del tamaño del municipio, y por eso los intervalos se calculan por grupo.

**Presentación para leer:**
> Los errores no se agrupan en el mapa: I de Moran = −0,02 (p = 0,98; 36 municipios grandes, a cinco cursos, 9 999 permutaciones). El radar no falla siempre hacia el mismo lado en ninguna zona.

**Si el jurado pregunta (oral):** «Hice el I de Moran de los residuos con vecindad de reina: −0,02 con p de 0,98 en los 36 grandes; con los 132, −0,05 y p de 0,44. Lo que sí se agrupa es el tamaño del error, porque los pueblos pequeños son vecinos entre sí; dentro de cada grupo de tamaño desaparece, y por eso el intervalo va por tamaño.»

## Ficheros

- `moran.py` — recalcula todo: `python moran.py [--repo RUTA] [--datos RUTA] [--perm 9999] [--semilla 20261126]` (unos 35 s; solo numpy, pandas y matplotlib).
- `resultado.json` — todas las cifras; `salida_consola.txt` — la salida de la última ejecución.
- `residuos_por_municipio.csv` — el residuo de cada municipio en cada muestra y su número de vecinos.
- `lisa_A_grandes36_h5.csv`, `lisa_D_todos_h1a6.csv` — I local, p y cuadrante por municipio.
- `mapa_residuos.png` — 1600 × 1040 px, dos paneles (A y D).
