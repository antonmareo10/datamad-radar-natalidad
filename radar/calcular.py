"""Backtest, intervalos y proyección. Escribe las tablas en resultados/ y un resumen.json.

Todo se recalcula a partir de los ficheros descargados. La base de la proyección es siempre el
último curso con alumnado publicado y el horizonte llega hasta donde hay nacidos publicados, así
que cuando salgan datos nuevos basta con volver a ejecutar `python -m radar todo`.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

from . import backtest as BT
from . import cargar as C
from . import intervalos as I
from . import modelo as M
from .config import CAPITAL, EDAD_1O, ESPEC_1O, ESPEC_INF, RESULTADOS
from .fuentes import POR_CLAVE


def ruta(datos: pathlib.Path, clave: str) -> pathlib.Path:
    p = datos / "crudos" / POR_CLAVE[clave].fichero
    if not p.exists():
        raise FileNotFoundError(f"Falta {p}. Ejecuta antes: python -m radar descargar")
    return p


def cargar_todo(datos: pathlib.Path) -> dict:
    B, nombres = C.nacidos(ruta(datos, "nacidos"))
    Y1, zona = C.primaria(ruta(datos, "primaria_curso"))
    zona_todas = C.zonas(ruta(datos, "ensenanzas_titularidad"))
    INF2 = C.infantil_segundo_ciclo(ruta(datos, "ensenanzas_titularidad"))
    r1, prov = C.primero_region(ruta(datos, "primaria_region"))
    censo = C.censo_ninos(ruta(datos, "censo_edad"))
    pob = C.padron(ruta(datos, "padron"))
    # comprobaciones de coherencia entre fuentes
    assert set(Y1.index) <= set(B.index), "hay municipios con alumnos y sin nacidos"
    assert set(INF2.index) <= set(B.index)
    comunes = sorted(set(Y1.columns) & set(r1.index))
    dif = {s: float(Y1[s].sum() - r1[s]) for s in comunes}
    return dict(B=B, nombres=nombres, Y1=Y1, zona=zona, INF2=INF2, r1=r1, prov=prov, censo=censo, pob=pob, zona_todas=zona_todas.combine_first(zona),
                coherencia_1o_consejeria_vs_ie=dif)


def _redondear(df: pd.DataFrame, d: int = 2) -> pd.DataFrame:
    return df.apply(lambda c: c.round(d) if c.dtype.kind == "f" else c)


def calcular(datos: pathlib.Path) -> dict:
    D = cargar_todo(datos)
    B, Y1, INF2, zona, nombres = D["B"], D["Y1"], D["INF2"], D["zona"], D["nombres"]
    salidas = datos / "salidas"
    salidas.mkdir(exist_ok=True)
    RESULTADOS.mkdir(exist_ok=True)
    resumen: dict = {"coherencia_1o_consejeria_menos_ie": D["coherencia_1o_consejeria_vs_ie"]}

    # ---------------------------------------------------------------- 1. Backtest 1º de primaria
    bt = BT.backtest_primero(Y1, INF2, B, zona)
    bt["municipio"] = bt["cmun"].map(nombres)
    bt.to_csv(salidas / "backtest_1o_predicciones.csv", index=False)
    especs = list(BT.ESPECS_1O)
    comun = BT.muestra_comun(bt, especs)
    t_h = BT.tabla(comun, especs, ["h"])
    t_gh = BT.tabla(comun, especs, ["grupo", "h"])
    zonas = BT.tabla(BT.agregar(comun, especs, "zona"), especs, ["h"])
    sel = BT.seleccion(comun, especs)
    _redondear(t_h).to_csv(RESULTADOS / "backtest_1o_por_horizonte.csv")
    _redondear(t_gh).to_csv(RESULTADOS / "backtest_1o_por_grupo_y_horizonte.csv")
    _redondear(zonas).to_csv(RESULTADOS / "backtest_1o_sumando_por_areas.csv")
    sel.round(2).rename("MdAPE_medio_h2_6").to_frame().assign(
        descripcion=[BT.ESPECS_1O[s] for s in sel.index]).to_csv(RESULTADOS / "seleccion_especificacion.csv")
    grupos_n = comun[comun.h == 1].groupby("grupo")["cmun"].nunique().to_dict()

    def md(grupo, h, s):
        return round(float(t_gh.loc[(grupo, h), f"{s}|MdAPE"]), 1)

    resumen["backtest_1o"] = {
        "cursos": [int(min(Y1.columns)), int(max(Y1.columns))],
        "municipios_por_grupo": grupos_n,
        "mdape": {g: {int(h): {"radar": md(g, h, ESPEC_1O), "ingenuo": md(g, h, "p_naive"), "nacidos": md(g, h, "p_births"),
                               "n": int(t_gh.loc[(g, h), "n"])}
                      for h in sorted(comun.h.unique()) if (g, h) in t_gh.index}
                  for g in BT.GRUPOS},
        "sesgo_radar": {g: {int(h): round(float(t_gh.loc[(g, h), f"{ESPEC_1O}|sesgo"]), 1)
                            for h in sorted(comun.h.unique()) if (g, h) in t_gh.index} for g in BT.GRUPOS},
        "wape_areas": {int(h): {"radar": round(float(zonas.loc[h, f"{ESPEC_1O}|WAPE"]), 1),
                                "ingenuo": round(float(zonas.loc[h, "p_naive|WAPE"]), 1)} for h in zonas.index},
        "seleccion_mdape_medio": {k: round(float(v), 2) for k, v in sel.items()},
    }

    # ---------------------------------------------------------------- 2. Dónde falla
    e = bt[bt.h.between(2, 4) & (bt.y > 0) & bt[ESPEC_1O].notna() & bt.grupo.isin(["grande", "mediano", "Madrid capital"])].copy()
    e["err_pct"] = (e[ESPEC_1O] - e.y) / e.y * 100
    pm = e.groupby("cmun").agg(municipio=("municipio", "first"), grupo=("grupo", "first"), zona=("zona", "first"),
                               err_medio=("err_pct", "mean"), ape_medio=("err_pct", lambda x: x.abs().mean()))
    b0 = int(D["censo"].index.get_level_values("anio").min())
    pm["ninos_0_4_por_100_nacidos"] = [
        cen / M.suma_nacidos(B, m, range(b0 - 5, b0)) * 100 if (m, b0) in D["censo"].index else np.nan
        for m, cen in zip(pm.index, [D["censo"]["p04"].get((m, b0), np.nan) for m in pm.index])]
    pm["alumnos_1o_por_nacido_inicial"] = Y1[min(Y1.columns)].reindex(pm.index) / B[M.cohorte_1o(min(Y1.columns))].reindex(pm.index)
    _redondear(pm.sort_values("ape_medio", ascending=False)).to_csv(RESULTADOS / "donde_falla_por_municipio.csv")
    ok = pm.dropna(subset=["ninos_0_4_por_100_nacidos"])
    resumen["donde_falla"] = {
        "municipios": int(len(pm)),
        "anio_censo": b0,
        "spearman_error_con_signo_vs_ninos_0_4": round(float(ok["err_medio"].corr(ok["ninos_0_4_por_100_nacidos"], method="spearman")), 2),
        "spearman_error_absoluto_vs_ninos_0_4": round(float(ok["ape_medio"].corr(ok["ninos_0_4_por_100_nacidos"], method="spearman")), 2),
        "por_area_mediana_ape": {z: round(float(v), 1) for z, v in pm.groupby("zona")["ape_medio"].median().items()},
        "peores": [dict(municipio=r.municipio, error_medio_pct=round(float(r.err_medio), 1))
                   for r in pm.sort_values("ape_medio", ascending=False).head(8).itertuples()],
    }

    # ---------------------------------------------------------------- 3. Intervalos y su cobertura
    res1 = I.residuos(bt, ESPEC_1O)
    cob1 = I.cobertura_validada(res1)
    _redondear(cob1).to_csv(RESULTADOS / "cobertura_intervalos_1o.csv")

    # ---------------------------------------------------------------- 4. Regional, serie larga
    R = BT.backtest_region(D["r1"], B, D["prov"])
    R.to_csv(salidas / "backtest_region_predicciones.csv", index=False)
    Rh = BT.tabla(R, ["p_naive", "p_births", "p_f1", "p_f3"], ["h"])
    _redondear(Rh).to_csv(RESULTADOS / "backtest_region_serie_larga.csv")
    R["lr"] = np.log(R.y / R.p_f1)
    R["periodo"] = pd.cut(R.t, [1990, 2008, 2015, 2100], labels=["2000-2008", "2009-2015", "2016-en adelante"])
    Rp = BT.tabla(R, ["p_naive", "p_f1"], ["periodo", "h"])
    _redondear(Rp).to_csv(RESULTADOS / "backtest_region_por_periodo.csv")
    por_periodo = {}
    for per, sub in Rp.groupby(level=0, observed=True):
        por_periodo[str(per)] = {"mdape_min": round(float(sub["p_f1|MdAPE"].min()), 1), "mdape_max": round(float(sub["p_f1|MdAPE"].max()), 1),
                                 "sesgo_min": round(float(sub["p_f1|sesgo"].min()), 1), "sesgo_max": round(float(sub["p_f1|sesgo"].max()), 1),
                                 "ingenuo_mdape_max": round(float(sub["p_naive|MdAPE"].max()), 1)}
    razon = (D["r1"] / pd.Series({s: B[M.cohorte_1o(s)].sum() for s in D["r1"].index if M.cohorte_1o(s) in B.columns}))
    resumen["region_serie_larga"] = {
        "cursos": [int(D["r1"].index.min()), int(D["r1"].index.max())],
        "mdape_razon_regional": {int(h): round(float(Rh.loc[h, "p_f1|MdAPE"]), 1) for h in Rh.index},
        "mdape_ingenuo": {int(h): round(float(Rh.loc[h, "p_naive|MdAPE"]), 1) for h in Rh.index},
        "mdape_nacidos": {int(h): round(float(Rh.loc[h, "p_births|MdAPE"]), 1) for h in Rh.index},
        "razon_1o_por_nacido": {int(s): round(float(v), 3) for s, v in razon.dropna().items()},
        "por_periodo_razon_regional": por_periodo,
    }

    # ---------------------------------------------------------------- 5. Infantil de 2º ciclo
    bi = BT.backtest_infantil(INF2, B)
    bi["municipio"] = bi["cmun"].map(nombres)
    bi.to_csv(salidas / "backtest_infantil_predicciones.csv", index=False)
    ei = list(BT.ESPECS_INF)
    ci = BT.muestra_comun(bi, ei)
    ti = BT.tabla(ci, ei, ["grupo", "h"])
    _redondear(ti).to_csv(RESULTADOS / "backtest_infantil_por_grupo_y_horizonte.csv")
    tih = BT.tabla(ci, ei, ["h"])
    _redondear(tih).to_csv(RESULTADOS / "backtest_infantil_por_horizonte.csv")
    resumen["backtest_infantil"] = {
        "mdape": {g: {int(h): {"radar": round(float(ti.loc[(g, h), f"{ESPEC_INF}|MdAPE"]), 1),
                               "ingenuo": round(float(ti.loc[(g, h), "p_naive|MdAPE"]), 1), "n": int(ti.loc[(g, h), "n"])}
                      for h in sorted(ci.h.unique()) if (g, h) in ti.index} for g in BT.GRUPOS},
        "mdape_todos": {int(h): {"radar": round(float(tih.loc[h, f"{ESPEC_INF}|MdAPE"]), 1),
                                 "ingenuo": round(float(tih.loc[h, "p_naive|MdAPE"]), 1)} for h in tih.index},
    }
    resi = I.residuos(bi, ESPEC_INF)
    _redondear(I.cobertura_validada(resi)).to_csv(RESULTADOS / "cobertura_intervalos_infantil.csv")

    # ---------------------------------------------------------------- 6. Proyección
    b = int(max(Y1.columns))
    ultimo_nacido = int(max(B.columns))
    fac = M.factores_base(Y1, INF2, B, zona, b, int(min(Y1.columns)))
    f, tipo = M.factor_proyeccion(fac)
    grupo1 = BT.grupo_tamano(Y1[int(min(Y1.columns))])
    proy = []
    for t in range(b + 1, ultimo_nacido + EDAD_1O + 1):  # la última cohorte publicada entra en 1º seis años después
        h = t - b
        p = M.prever_1o(B, f, b, t)
        for m in Y1.index:
            g = grupo1.get(m, "pequeño")
            lo, hi, n = I.cuantiles(res1, "grande" if g == "Madrid capital" else g, h)
            v = p[m]
            proy.append(dict(cmun=m, municipio=nombres.get(m), zona=zona.get(m), grupo=g, curso=C.etiqueta_curso(t), t=t, h=h,
                             nacidos=M.valor(B, m, M.cohorte_1o(t)), factor=f[m], tipo_factor=tipo[m],
                             prevision=v, p10=v * np.exp(lo), p90=v * np.exp(hi), n_residuos=n,
                             alumnos_base=M.valor(Y1, m, b)))
    P = pd.DataFrame(proy)
    _redondear(P, 3).to_csv(RESULTADOS / "proyeccion_1o_primaria.csv", index=False)

    # total regional con la incertidumbre del backtest regional largo (incluye cambios de ciclo)
    tot = P.groupby("t")["prevision"].sum()
    real_b = float(Y1[b].sum())
    reg = []
    for t, v in tot.items():
        h = t - b
        lr = R[R.h == h]["lr"]
        lo, hi = lr.quantile(0.10), lr.quantile(0.90)
        reg.append(dict(curso=C.etiqueta_curso(t), t=int(t), h=int(h), nacidos_region=float(B[M.cohorte_1o(t)].sum()),
                        prevision=float(v), p10=float(v * np.exp(lo)), p90=float(v * np.exp(hi)), n=int(len(lr)),
                        cambio_pct=float((v / real_b - 1) * 100)))
    REG = pd.DataFrame(reg)
    _redondear(REG, 1).to_csv(RESULTADOS / "proyeccion_region.csv", index=False)
    comprob = None
    if (b + 1) in D["r1"].index:
        publicado = float(D["r1"][b + 1])
        comprob = dict(curso=C.etiqueta_curso(b + 1), previsto=round(float(tot[b + 1])), publicado=round(publicado),
                       provisional=(b + 1) in D["prov"], error_pct=round(float((tot[b + 1] / publicado - 1) * 100), 1),
                       dentro_intervalo=bool(REG.iloc[0].p10 <= publicado <= REG.iloc[0].p90))
    ult = REG.iloc[-1]
    cap = P[(P.cmun == CAPITAL) & (P.t == ult.t)].iloc[0]
    resto = P[(P.cmun != CAPITAL) & (P.t == ult.t)]
    por_area = P[P.t == ult.t].groupby("zona")["prevision"].sum() / P[P.t == ult.t].groupby("zona")["alumnos_base"].sum() * 100 - 100
    resumen["proyeccion_1o"] = {
        "base": C.etiqueta_curso(b), "ultimo_ano_nacidos": ultimo_nacido,
        "real_base": round(real_b), "nacidos_base_cohorte": float(B[M.cohorte_1o(b)].sum()),
        "region": REG.round(1).to_dict(orient="records"),
        "comprobacion_fuera_de_muestra": comprob,
        "capital": {"base": float(cap.alumnos_base), "prevision": round(float(cap.prevision)),
                    "cambio_pct": round(float((cap.prevision / cap.alumnos_base - 1) * 100), 1)},
        "resto": {"base": float(resto.alumnos_base.sum()), "prevision": round(float(resto.prevision.sum())),
                  "cambio_pct": round(float((resto.prevision.sum() / resto.alumnos_base.sum() - 1) * 100), 1)},
        "por_area_cambio_pct": {z: round(float(v), 1) for z, v in por_area.items()},
        "municipios_con_colegio": int(len(Y1.index)),
        "municipios_que_caen": int((P[P.t == ult.t].prevision < P[P.t == ult.t].alumnos_base).sum()),
        "factor_respaldo": int((tipo != "infantil 3-5 corregido").sum()),
        "kinf": round(float(fac["kinf"].iloc[0]), 4),
    }
    # ranking en el último curso proyectado, municipios con 100 alumnos de 1º o más en la base
    k = P[P.t == ult.t].set_index("cmun").copy()
    k["cambio_pct"] = (k.prevision / k.alumnos_base - 1) * 100
    k["cambio_p10"] = (k.p10 / k.alumnos_base - 1) * 100
    k["cambio_p90"] = (k.p90 / k.alumnos_base - 1) * 100
    kk = k[k.alumnos_base >= 100].sort_values("cambio_pct")
    _redondear(kk[["municipio", "zona", "grupo", "alumnos_base", "nacidos", "prevision", "p10", "p90",
                   "cambio_pct", "cambio_p10", "cambio_p90"]], 1).to_csv(RESULTADOS / "ranking_ultimo_curso.csv")
    resumen["ranking"] = {
        "curso": ult.curso, "municipios": int(len(kk)), "caen": int((kk.cambio_pct < 0).sum()),
        "caen_mas_10": int((kk.cambio_pct < -10).sum()), "caida_segura": int((kk.cambio_p90 < 0).sum()),
        "subida_segura": int((kk.cambio_p10 > 0).sum()),
        "mas_caen": [dict(municipio=r.municipio, base=r.alumnos_base, prevision=round(r.prevision), p10=round(r.p10),
                          p90=round(r.p90), cambio_pct=round(r.cambio_pct)) for r in kk.head(8).itertuples()],
        "mas_suben": [dict(municipio=r.municipio, base=r.alumnos_base, prevision=round(r.prevision), p10=round(r.p10),
                           p90=round(r.p90), cambio_pct=round(r.cambio_pct)) for r in kk.tail(6).iloc[::-1].itertuples()],
    }
    anchos = P[P.t == ult.t].assign(ancho=lambda x: (x.p90 - x.p10) / x.prevision * 100).groupby("grupo")["ancho"].median()
    resumen["ancho_intervalo_ultimo_curso_pct"] = {g: round(float(v)) for g, v in anchos.items()}
    resumen["cobertura_intervalos_1o_pct"] = {g: round(float(v), 1) for g, v in cob1["cobertura_pct"].items()}

    # infantil de 2º ciclo: hasta donde hay nacidos de las tres cohortes
    fi = M.factor_infantil_simple(INF2, B, b)
    grupo_i = BT.grupo_tamano(INF2[int(min(INF2.columns))], cortes=(99, 749))
    pi = []
    for t in range(b + 1, ultimo_nacido + 3 + 1):
        h = t - b
        p = M.prever_infantil(B, fi, b, t)
        for m in INF2.index:
            g = grupo_i.get(m, "pequeño")
            lo, hi, n = I.cuantiles(resi, "grande" if g == "Madrid capital" else g, h)
            v = p[m]
            pi.append(dict(cmun=m, municipio=nombres.get(m), zona=zona.get(m), grupo=g, curso=C.etiqueta_curso(t), t=t, h=h,
                           nacidos_3_cohortes=M.suma_nacidos(B, m, M.cohortes_infantil(t)), factor=fi[m],
                           prevision=v, p10=v * np.exp(lo), p90=v * np.exp(hi), n_residuos=n,
                           alumnos_base=M.valor(INF2, m, b)))
    PI = pd.DataFrame(pi)
    _redondear(PI, 3).to_csv(RESULTADOS / "proyeccion_infantil_3_5.csv", index=False)
    toti = PI.groupby("t")["prevision"].sum()
    resumen["proyeccion_infantil"] = {
        "base": C.etiqueta_curso(b), "real_base": round(float(INF2[b].sum())),
        "region": [dict(curso=C.etiqueta_curso(t), prevision=round(float(v)), cambio_pct=round(float((v / INF2[b].sum() - 1) * 100), 1))
                   for t, v in toti.items()],
    }
    resumen["nacidos_region"] = {int(a): int(B[a].sum()) for a in B.columns if a >= 2000}

    (RESULTADOS / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: resumen[k] for k in ["proyeccion_1o"]}, ensure_ascii=False, indent=1, default=float)[:3000])
    return dict(D=D, bt=bt, bi=bi, P=P, PI=PI, REG=REG, resumen=resumen, res1=res1, resi=resi, R=R, fac=fac, tipo=tipo)
