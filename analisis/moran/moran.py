"""Diagnóstico espacial de los errores del backtest del Radar de natalidad municipal (I de Moran).

Recalcula todo desde el código del repositorio (solo lectura) y los ficheros crudos descargados:

    python moran.py [--repo RUTA_REPO] [--datos RUTA_DATOS] [--perm 9999] [--semilla 20261126]

- Residuo: error relativo con signo de la especificación elegida (config.ESPEC_1O = p_finfk),
  err = (previsto - real) / real * 100, el mismo que usa radar/calcular.py en «dónde falla».
  Una cifra por municipio = media de err sobre las bases del backtest en el horizonte indicado.
- Pesos: contigüidad de reina (comparten al menos un punto de frontera) entre los municipios del
  shapefile «Municipios y Distritos de Madrid (2020)», con los 21 distritos de la capital fundidos
  en una unidad (28079), como hace la previsión. Estandarizados por filas. Los municipios sin
  ningún vecino dentro de la muestra (islas) se excluyen y se cuentan.
- Contraste: 9 999 permutaciones aleatorias de los valores entre municipios (semilla fija).
  pseudo-p = (nº de permutaciones tan extremas o más + 1) / (permutaciones + 1).

Solo necesita numpy, pandas y matplotlib (no shapely ni pysal). No escribe nada en el repo.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "2")

import argparse
import json
import pathlib
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

AQUI = pathlib.Path(__file__).resolve().parent
REPO_DEF = AQUI.parents[1]  # raíz del repositorio
DATOS_DEF = REPO_DEF / "datos"  # se descargan con `python -m radar todo`; o pásalo con --datos
TOL_M = 1.0  # dos municipios se tocan si sus fronteras quedan a 1 m o menos


# ------------------------------------------------------------------------------------------
# 1. Residuos del backtest, con el código del repo
# ------------------------------------------------------------------------------------------
def residuos_backtest(repo: pathlib.Path, datos: pathlib.Path):
    sys.path.insert(0, str(repo))
    sys.dont_write_bytecode = True
    from radar import backtest as BT
    from radar import calcular as CA
    from radar.config import CAPITAL, ESPEC_1O

    D = CA.cargar_todo(datos)  # solo lee
    bt = BT.backtest_primero(D["Y1"], D["INF2"], D["B"], D["zona"])
    bt["municipio"] = bt["cmun"].map(D["nombres"])
    comun = BT.muestra_comun(bt, list(BT.ESPECS_1O))
    comun = comun[comun["y"] > 0].copy()
    comun["err"] = (comun[ESPEC_1O] - comun["y"]) / comun["y"] * 100
    comun["err_naive"] = (comun["p_naive"] - comun["y"]) / comun["y"] * 100
    comun["lr"] = np.where(comun[ESPEC_1O] > 0, np.log(comun["y"] / comun[ESPEC_1O].where(comun[ESPEC_1O] > 0)), np.nan)
    # misma muestra que «dónde falla» (radar/calcular.py, sección 2)
    falla = bt[bt.h.between(2, 4) & (bt.y > 0) & bt[ESPEC_1O].notna()
               & bt.grupo.isin(["grande", "mediano", "Madrid capital"])].copy()
    falla["err"] = (falla[ESPEC_1O] - falla.y) / falla.y * 100
    return comun, falla, CAPITAL, ESPEC_1O


# ------------------------------------------------------------------------------------------
# 2. Geometría y contigüidad de reina (sin shapely)
# ------------------------------------------------------------------------------------------
def leer_municipios(repo: pathlib.Path, datos: pathlib.Path):
    from radar import geo
    from radar.fuentes import POR_CLAVE

    registros, filas = geo.leer_zip(datos / "crudos" / POR_CLAVE["limites"].fichero)
    anillos = defaultdict(list)
    for geom, fila in zip(registros, filas):
        cm = geo.codigo_ine(fila)
        if cm is None or not geom:
            continue
        for a in geom:
            anillos[cm].append(np.asarray(a, dtype=float))
    # contorno fundido (para dibujar la capital sin las rayas de los distritos)
    por_reg = defaultdict(list)
    for geom, fila in zip(registros, filas):
        cm = geo.codigo_ine(fila)
        if cm is not None and geom:
            por_reg[cm].append(geom)
    dibujo = {cm: [np.asarray(a, dtype=float) for a in (geo.fundir(p) if len(p) > 1 else p[0])]
              for cm, p in por_reg.items()}
    return dict(anillos), dibujo


def _segmentos(lista_anillos):
    a = np.concatenate([r[:-1] for r in lista_anillos])
    b = np.concatenate([r[1:] for r in lista_anillos])
    return a, b


def _dist_min_puntos_segmentos(P, A, B, bloque=400):
    """Distancia mínima entre un conjunto de puntos y un conjunto de segmentos."""
    mejor = np.inf
    d = B - A
    l2 = np.maximum((d ** 2).sum(1), 1e-12)
    for i in range(0, len(P), bloque):
        p = P[i:i + bloque, None, :]
        t = np.clip(((p - A[None]) * d[None]).sum(2) / l2[None], 0, 1)
        q = A[None] + t[..., None] * d[None]
        mejor = min(mejor, float(np.sqrt(((p - q) ** 2).sum(2).min())))
        if mejor <= 1e-9:
            break
    return mejor


def contiguidad_reina(anillos: dict, tol: float = TOL_M):
    """Vecinos = fronteras a `tol` metros o menos (incluye tocarse en un solo punto: reina)."""
    cms = sorted(anillos)
    pts = {c: np.concatenate(anillos[c]) for c in cms}
    seg = {c: _segmentos(anillos[c]) for c in cms}
    caja = {c: (pts[c].min(0), pts[c].max(0)) for c in cms}
    vec = {c: set() for c in cms}
    for i, a in enumerate(cms):
        for b in cms[i + 1:]:
            (a0, a1), (b0, b1) = caja[a], caja[b]
            if (a0 > b1 + tol).any() or (b0 > a1 + tol).any():
                continue
            lo, hi = np.maximum(a0, b0) - 50, np.minimum(a1, b1) + 50  # zona común de las cajas
            toca = False
            for x, y in ((a, b), (b, a)):
                P = pts[x]
                P = P[((P >= lo) & (P <= hi)).all(1)]
                A, B = seg[y]
                m = ((np.maximum(A, B) >= lo) & (np.minimum(A, B) <= hi)).all(1)
                if len(P) and m.any() and _dist_min_puntos_segmentos(P, A[m], B[m]) <= tol:
                    toca = True
                    break
            if toca:
                vec[a].add(b)
                vec[b].add(a)
    return vec


def vertices_compartidos(anillos: dict, decimales: int = 0):
    """Comprobación independiente: vecinos = comparten algún vértice (redondeado al metro)."""
    donde = defaultdict(set)
    for c, rs in anillos.items():
        for r in rs:
            for k in map(tuple, np.round(r, decimales)):
                donde[k].add(c)
    vec = {c: set() for c in anillos}
    for s in donde.values():
        if len(s) > 1:
            for a in s:
                vec[a] |= s - {a}
    return vec


def centroide(lista_anillos):
    """Centroide por áreas del anillo mayor (solo para rotular y para el control k-vecinos)."""
    def area_c(r):
        x, y = r[:, 0], r[:, 1]
        c = x[:-1] * y[1:] - x[1:] * y[:-1]
        a = c.sum() / 2
        if abs(a) < 1e-9:
            return 0.0, r.mean(0)
        return a, np.array([((x[:-1] + x[1:]) * c).sum(), ((y[:-1] + y[1:]) * c).sum()]) / (6 * a)
    a, c = max((area_c(r) for r in lista_anillos), key=lambda t: abs(t[0]))
    return c


# ------------------------------------------------------------------------------------------
# 3. I de Moran global y local con permutaciones
# ------------------------------------------------------------------------------------------
def matriz_w(cms, vec):
    idx = {c: i for i, c in enumerate(cms)}
    W = np.zeros((len(cms), len(cms)))
    for c in cms:
        for v in vec[c]:
            if v in idx:
                W[idx[c], idx[v]] = 1.0
    return W


def moran_global(x, W, perm, rng, estratos=None):
    """W binaria sin islas; se estandariza por filas aquí. Devuelve I, E[I], pseudo-p.

    Con `estratos`, los valores solo se permutan dentro de su estrato (grupo de tamaño): la hipótesis
    nula pasa a ser «dado el tamaño del municipio, el sitio no importa»."""
    n = len(x)
    Ws = W / W.sum(1, keepdims=True)
    z = x - x.mean()
    den = (z ** 2).sum()
    I = float(z @ Ws @ z / den)  # con filas estandarizadas S0 = n, así que n/S0 = 1
    if estratos is None:
        P = np.array([rng.permutation(z) for _ in range(perm)])
    else:
        P = np.tile(z, (perm, 1))
        for e in np.unique(estratos):
            j = np.nonzero(estratos == e)[0]
            for k in range(perm):
                P[k, j] = z[rng.permutation(j)]
    Ip = np.einsum("ij,ij->i", P @ Ws.T, P) / den
    EI = -1.0 / (n - 1) if estratos is None else float(Ip.mean())
    mayores = int((Ip >= I).sum())
    p_sup = (mayores + 1) / (perm + 1)                                  # cola superior: agrupación
    p_unil = (min(mayores, perm - mayores) + 1) / (perm + 1)            # convención de PySAL (p_sim)
    p_bil = (int((np.abs(Ip - EI) >= abs(I - EI)).sum()) + 1) / (perm + 1)  # dos colas
    return dict(n=n, I=I, EI=EI, media_perm=float(Ip.mean()), dt_perm=float(Ip.std(ddof=1)),
                z_perm=float((I - Ip.mean()) / Ip.std(ddof=1)), p_superior=p_sup, p_una_cola_pysal=p_unil,
                p_dos_colas=p_bil, enlaces=int(W.sum() / 2), vecinos_medios=float(W.sum(1).mean()))


def moran_local(x, W, perm, rng):
    """LISA (Anselin 1995) con permutaciones condicionadas."""
    n = len(x)
    Ws = W / W.sum(1, keepdims=True)
    z = (x - x.mean()) / x.std()
    lag = Ws @ z
    Ii = z * lag
    p = np.empty(n)
    for i in range(n):
        otros = np.delete(z, i)
        w = np.delete(Ws[i], i)
        k = int((w > 0).sum())
        wv = w[w > 0]
        # basta sortear k valores sin reemplazo de los otros n-1
        muestras = np.array([rng.choice(otros, size=k, replace=False) for _ in range(perm)])
        lp = z[i] * (muestras @ wv)
        mayores = int((lp >= Ii[i]).sum())
        p[i] = (min(mayores, perm - mayores) + 1) / (perm + 1)
    cuad = np.where(z >= 0, np.where(lag >= 0, "AA", "AB"), np.where(lag >= 0, "BA", "BB"))
    return Ii, p, cuad, lag


def bh(p, q=0.05):
    """Benjamini-Hochberg: devuelve máscara de significativos con FDR q."""
    o = np.argsort(p)
    m = len(p)
    ok = p[o] <= q * (np.arange(1, m + 1) / m)
    sig = np.zeros(m, bool)
    if ok.any():
        sig[o[: np.max(np.nonzero(ok)[0]) + 1]] = True
    return sig


def knn_w(cms, cen, k=4):
    X = np.array([cen[c] for c in cms])
    d = np.sqrt(((X[:, None] - X[None]) ** 2).sum(2))
    np.fill_diagonal(d, np.inf)
    W = np.zeros_like(d)
    for i in range(len(cms)):
        W[i, np.argsort(d[i])[:k]] = 1.0
    return W


def analizar(nombre, serie: pd.Series, vec, cen, perm, semilla, definicion, grupo=None):
    """serie: índice cmun, valor = residuo por municipio."""
    serie = serie.dropna()
    cms = [c for c in sorted(serie.index) if c in vec]
    sin_geo = sorted(set(serie.index) - set(cms))
    W = matriz_w(cms, vec)
    islas = [c for c, g in zip(cms, W.sum(1)) if g == 0]
    queda = [c for c in cms if c not in islas]
    W = matriz_w(queda, vec)
    x = serie.loc[queda].to_numpy(float)
    out = dict(nombre=nombre, definicion=definicion, n_con_residuo=int(len(serie)), sin_geometria=sin_geo,
               islas=islas, n=len(queda))
    out["con_signo"] = moran_global(x, W, perm, np.random.default_rng(semilla))
    out["absoluto"] = moran_global(np.abs(x), W, perm, np.random.default_rng(semilla + 1))
    # control: rangos (robusto a valores extremos) y k = 4 vecinos más próximos (sin islas)
    out["con_signo_rangos"] = moran_global(pd.Series(x).rank().to_numpy(), W, perm, np.random.default_rng(semilla + 2))
    out["absoluto_rangos"] = moran_global(pd.Series(np.abs(x)).rank().to_numpy(), W, perm, np.random.default_rng(semilla + 3))
    if grupo is not None:
        est = np.array([{"Madrid capital": "grande"}.get(grupo[c], grupo[c]) for c in queda])
        if len(set(est)) > 1:
            out["absoluto_dentro_de_tamano"] = moran_global(np.abs(x), W, perm, np.random.default_rng(semilla + 6), est)
            out["absoluto_rangos_dentro_de_tamano"] = moran_global(pd.Series(np.abs(x)).rank().to_numpy(), W, perm,
                                                                   np.random.default_rng(semilla + 7), est)
            out["con_signo_dentro_de_tamano"] = moran_global(x, W, perm, np.random.default_rng(semilla + 8), est)
            out["mediana_abs_por_tamano"] = {g: round(float(np.median(np.abs(x[est == g]))), 2) for g in sorted(set(est))}
    xk = serie.loc[cms].to_numpy(float)
    Wk = knn_w(cms, cen, 4)
    out["knn4_con_signo"] = moran_global(xk, Wk, perm, np.random.default_rng(semilla + 4))
    out["knn4_absoluto"] = moran_global(np.abs(xk), Wk, perm, np.random.default_rng(semilla + 5))
    return out, queda, W, x


# ------------------------------------------------------------------------------------------
# 4. Mapa
# ------------------------------------------------------------------------------------------
PIZARRA, TIZA = "#1f3c34", "#f3f0e7"
ROJO, AZUL, NEUTRO, SIN, RAYA = "#c8452f", "#2f6f9f", "#e4dcc6", "#f3f0e7", "#cdc6b3"


def mapa(ruta, dibujo, cen, paneles, titulo, subtitulo, pie):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path

    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    cmap = LinearSegmentedColormap.from_list("radar", [AZUL, "#9fc0d6", NEUTRO, "#e3a392", ROJO])
    fig = plt.figure(figsize=(16, 10.4), dpi=100, facecolor=TIZA)
    fig.text(0.035, 0.962, titulo, fontsize=27, fontweight="bold", color=PIZARRA, va="top")
    fig.text(0.035, 0.905, subtitulo, fontsize=13.5, color=PIZARRA, va="top", alpha=0.85, linespacing=1.4)

    def camino(anillos):
        vs, cs = [], []
        for r in anillos:
            vs.extend(r.tolist())
            cs.extend([Path.MOVETO] + [Path.LINETO] * (len(r) - 2) + [Path.CLOSEPOLY])
        return Path(vs, cs)

    n = len(paneles)
    for k, pn in enumerate(paneles):
        ax = fig.add_axes([0.03 + k * (0.94 / n), 0.125, 0.94 / n - 0.02, 0.645], facecolor=TIZA)
        vals, lim = pn["valores"], pn["lim"]
        norm = TwoSlopeNorm(0, -lim, lim)
        for cm, an in dibujo.items():
            v = vals.get(cm)
            hay = not (v is None or np.isnan(v))
            ax.add_patch(PathPatch(camino(an), facecolor=cmap(norm(np.clip(v, -lim, lim))) if hay else SIN,
                                   edgecolor="#fbfaf5" if hay else RAYA, linewidth=0.8 if hay else 0.5,
                                   zorder=2 if hay else 1))
        for cm, an in dibujo.items():
            if cm in pn.get("marcados", {}):
                ax.add_patch(PathPatch(camino(an), facecolor="none", edgecolor=PIZARRA, linewidth=2.6, zorder=5))
        for cm, txt in pn.get("rotulos", {}).items():
            ax.annotate(txt, cen[cm], fontsize=9.5, color=PIZARRA, ha="center", va="center", zorder=6,
                        fontweight="bold")
        ax.autoscale_view()
        ax.set_aspect("equal")
        ax.axis("off")
        ax.text(0.0, 1.075, pn["titulo"], transform=ax.transAxes, fontsize=16, color=PIZARRA, va="bottom", fontweight="bold")
        ax.text(0.0, 1.025, pn["dato"], transform=ax.transAxes, fontsize=13, color=PIZARRA, va="bottom")
        cax = fig.add_axes([0.06 + k * (0.94 / n), 0.135, 0.19, 0.014])
        cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
        cb.outline.set_visible(False)
        cb.set_ticks([-lim, 0, lim])
        cb.set_ticklabels([f"−{lim:.0f} % o menos\nse quedó corto", "0", f"+{lim:.0f} % o más\nprevió de más"])
        cb.ax.tick_params(labelsize=10.5, colors=PIZARRA, length=0)
    fig.text(0.035, 0.014, pie, fontsize=10.5, color=PIZARRA, alpha=0.8, va="bottom", linespacing=1.45)
    fig.savefig(ruta, dpi=100, facecolor=TIZA)
    plt.close(fig)


# ------------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=str(REPO_DEF))
    ap.add_argument("--datos", default=str(DATOS_DEF))
    ap.add_argument("--perm", type=int, default=9999)
    ap.add_argument("--semilla", type=int, default=20261126)
    ap.add_argument("--sin-mapa", action="store_true")
    a = ap.parse_args(argv)
    repo, datos = pathlib.Path(a.repo), pathlib.Path(a.datos)

    comun, falla, CAPITAL, ESPEC = residuos_backtest(repo, datos)
    nombres = comun.drop_duplicates("cmun").set_index("cmun")["municipio"].to_dict()
    grupo = comun.drop_duplicates("cmun").set_index("cmun")["grupo"].to_dict()

    # comprobación contra las cifras congeladas (no se tocan, solo se verifica que el recálculo coincide)
    g5 = comun[(comun.grupo == "grande") & (comun.h == 5)]
    control = dict(
        espec=ESPEC,
        mdape_grande_h5_radar=round(float(g5.err.abs().median()), 2),
        mdape_grande_h5_ingenuo=round(float(g5.err_naive.abs().median()), 2),
        n_grande_h5=int(len(g5)), municipios_grande=int(g5.cmun.nunique()), bases_h5=sorted(int(b) for b in g5.b.unique()),
        cursos_reales_h5=sorted(int(t) for t in g5.t.unique()),
    )
    csv = pd.read_csv(repo / "resultados" / "donde_falla_por_municipio.csv", dtype={"cmun": str}).set_index("cmun")
    pm = falla.groupby("cmun")["err"].mean()
    control["donde_falla_municipios"] = int(len(pm))
    control["donde_falla_max_dif_con_csv"] = round(float((pm.round(2) - csv["err_medio"].reindex(pm.index)).abs().max()), 3)

    anillos, dibujo = leer_municipios(repo, datos)
    vec = contiguidad_reina(anillos)
    vec2 = vertices_compartidos(anillos)
    cen = {c: centroide(dibujo[c]) for c in dibujo}
    pares = {tuple(sorted((x, y))) for x in vec for y in vec[x]}
    pares2 = {tuple(sorted((x, y))) for x in vec2 for y in vec2[x]}
    control["geometria"] = dict(unidades=len(anillos), enlaces_reina=len(pares), enlaces_vertice_compartido=len(pares2),
                                solo_en_distancia=sorted(pares - pares2), solo_en_vertices=sorted(pares2 - pares),
                                sin_vecinos=[c for c in vec if not vec[c]], vecinos_capital=len(vec[CAPITAL]))

    def media(df, col="err"):
        return df.groupby("cmun")[col].mean()

    gr = ["grande"]
    grc = ["grande", "Madrid capital"]
    series = [
        ("A_grandes36_h5", media(comun[comun.grupo.isin(gr) & (comun.h == 5)]),
         "36 municipios grandes (250 alumnos de 1.º o más en 2018/19, sin la capital); h = 5 cursos; "
         "media por municipio de err = (previsto − real)/real × 100 sobre las 2 bases con h = 5"),
        ("A2_grandes36_y_capital_h5", media(comun[comun.grupo.isin(grc) & (comun.h == 5)]),
         "ídem A añadiendo Madrid capital (37 unidades)"),
        ("B_donde_falla_81_h2a4", pm,
         "definición del repo (resultados/donde_falla_por_municipio.csv, columna err_medio): municipios grandes, "
         "medianos y capital; media de err en h = 2 a 4"),
        ("C_todos_h5", media(comun[comun.h == 5]), "todos los municipios con backtest; h = 5; media de err por municipio"),
        ("D_todos_h1a6", media(comun), "todos los municipios con backtest; media de err en h = 1 a 6"),
        ("E_todos_h1a6_log", -media(comun, "lr") * 100,
         "todos; media de −log(real/previsto) × 100 en h = 1 a 6 (el residuo logarítmico de los intervalos, "
         "con el signo de err)"),
        ("F_grandes_y_medianos_h5", media(comun[comun.grupo.isin(["grande", "mediano", "Madrid capital"]) & (comun.h == 5)]),
         "grandes, medianos y capital; h = 5"),
    ]
    resultados, guardado = [], {}
    for k, (nombre, s, definicion) in enumerate(series):
        r, queda, W, x = analizar(nombre, s, vec, cen, a.perm, a.semilla + 100 * k, definicion, grupo)
        resultados.append(r)
        guardado[nombre] = (s, queda, W, x)

    # LISA en las dos series que se dibujan
    lisa = {}
    for nombre in ("A_grandes36_h5", "D_todos_h1a6"):
        s, queda, W, x = guardado[nombre]
        Ii, p, cuad, lag = moran_local(x, W, a.perm, np.random.default_rng(a.semilla + 7))
        fdr = bh(p)
        tabla = pd.DataFrame(dict(cmun=queda, municipio=[nombres.get(c, c) for c in queda], grupo=[grupo.get(c) for c in queda],
                                  residuo=np.round(x, 2), retardo_espacial_z=np.round(lag, 3), I_local=np.round(Ii, 3),
                                  p=np.round(p, 4), cuadrante=cuad, sig_005=p < 0.05, sig_fdr_005=fdr))
        tabla.to_csv(AQUI / f"lisa_{nombre}.csv", index=False, encoding="utf-8")
        lisa[nombre] = tabla
        for r in resultados:
            if r["nombre"] == nombre:
                r["lisa"] = dict(
                    p_menor_005=int((p < 0.05).sum()), esperados_por_azar=round(0.05 * len(p), 1),
                    significativos_fdr_005=int(fdr.sum()),
                    nucleos_005=[dict(municipio=t.municipio, cuadrante=t.cuadrante, residuo=t.residuo, p=t.p)
                                 for t in tabla[tabla.sig_005].sort_values("p").itertuples()])

    # residuos por municipio usados (para la lista de verificación)
    todos = pd.DataFrame({n: s for n, s, _ in series})
    todos.insert(0, "municipio", [nombres.get(c, c) for c in todos.index])
    todos.insert(1, "grupo", [grupo.get(c) for c in todos.index])
    todos.insert(2, "n_vecinos_reina", [len(vec.get(c, ())) for c in todos.index])
    todos.round(3).to_csv(AQUI / "residuos_por_municipio.csv", encoding="utf-8")

    salida = dict(control=control, permutaciones=a.perm, semilla=a.semilla, tolerancia_contacto_m=TOL_M, resultados=resultados)
    (AQUI / "resultado.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps(control, ensure_ascii=False, indent=1))
    for r in resultados:
        print(f"\n== {r['nombre']}  n={r['n']} (con residuo {r['n_con_residuo']}, islas {len(r['islas'])}, sin geometría {len(r['sin_geometria'])})")
        for k in ("con_signo", "absoluto", "con_signo_rangos", "absoluto_rangos", "knn4_con_signo", "knn4_absoluto",
                  "con_signo_dentro_de_tamano", "absoluto_dentro_de_tamano", "absoluto_rangos_dentro_de_tamano"):
            if k not in r:
                continue
            m = r[k]
            print(f"   {k:32s} n={m['n']:3d} I={m['I']:+.4f} E[I]={m['EI']:+.4f} z={m['z_perm']:+.2f} "
                  f"p_sup={m['p_superior']:.4f} p_2colas={m['p_dos_colas']:.4f} enlaces={m['enlaces']}")
        if "lisa" in r:
            print("   LISA:", json.dumps(r["lisa"], ensure_ascii=False))
        if "mediana_abs_por_tamano" in r:
            print("   mediana |residuo| por tamaño:", r["mediana_abs_por_tamano"])

    if not a.sin_mapa:
        dibujar(resultados, guardado, lisa, dibujo, cen, nombres, a.perm)
    return salida


def _f(v, d=2):
    return f"{v:+.{d}f}".replace("-", "−").replace(".", ",")


def _p(v):
    return f"{v:.3f}".replace(".", ",")


def dibujar(resultados, guardado, lisa, dibujo, cen, nombres, perm):
    R = {r["nombre"]: r for r in resultados}
    paneles = []
    for nombre, tit, lim in (("A_grandes36_h5", "A cinco cursos · 36 municipios grandes", 15),
                             ("D_todos_h1a6", "Todos los horizontes (1-6 cursos) · todos los municipios", 40)):
        s, queda, W, x = guardado[nombre]
        r, t = R[nombre], lisa[nombre]
        marc = {c: 1 for c in t[t.sig_fdr_005].cmun}
        paneles.append(dict(
            titulo=tit, lim=lim, valores={c: float(v) for c, v in zip(queda, x)}, marcados=marc,
            dato=(f"I de Moran = {_f(r['con_signo']['I'])} (esperado {_f(r['con_signo']['EI'])}), "
                  f"p = {_p(r['con_signo']['p_dos_colas'])} · n = {r['n']}"
                  + (f" ({len(r['islas'])} sin vecino, fuera)" if r["islas"] else ""))))
    pA, pD = R["A_grandes36_h5"]["con_signo"]["p_dos_colas"], R["D_todos_h1a6"]["con_signo"]["p_dos_colas"]
    if pA >= 0.05 and pD >= 0.05:
        titulo = "Los errores del backtest no se agrupan en el mapa"
    elif pA >= 0.05:
        titulo = "A cinco cursos, los errores de los municipios grandes no se agrupan en el mapa"
    else:
        titulo = "Los errores del backtest se agrupan en el espacio"
    sub = ("Error medio con signo de la previsión de 1.º de primaria en cursos ya cerrados (2018/19-2024/25): "
           "(previsto − real) / real.\nI de Moran con vecindad de reina y pesos estandarizados por filas; "
           "contraste con " + f"{perm:,}".replace(",", " ") + " permutaciones.")
    ab, abt = R["D_todos_h1a6"]["absoluto"], R["D_todos_h1a6"]["absoluto_dentro_de_tamano"]
    nfdr = sum(int(lisa[k].sig_fdr_005.sum()) for k in lisa)
    pie = ("Solo contorno: sin residuo en esa muestra o sin vecino dentro de ella. "
           + ("Ningún núcleo local (LISA) es significativo tras corregir por comparaciones múltiples (FDR 5 %).\n" if nfdr == 0
              else "Contorno oscuro: núcleo local (LISA) significativo con FDR 5 %.\n")
           + f"El tamaño del error (valor absoluto) sí se parece algo entre vecinos en el conjunto (I = {_f(ab['I'])}, "
           f"p = {_p(ab['p_dos_colas'])}), pero es efecto del tamaño del municipio: permutando solo entre municipios "
           f"del mismo tamaño, p = {_p(abt['p_dos_colas'])}.\n"
           "Fuente: Radar de natalidad municipal, backtest de la especificación elegida; límites «Municipios y Distritos "
           "de Madrid (2020)», Comunidad de Madrid. Madrid capital, una sola unidad.")
    mapa(AQUI / "mapa_residuos.png", dibujo, cen, paneles, titulo, sub, pie)
    print("\nmapa:", AQUI / "mapa_residuos.png")


if __name__ == "__main__":
    main()
