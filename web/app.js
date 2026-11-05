/* Radar de natalidad municipal · lógica de la página. Sin librerías: funciona abriendo index.html. */
(function () {
  "use strict";
  const R = window.RADAR;
  if (!R) {
    document.getElementById("cifras").innerHTML = '<p class="aviso">No se encuentra <code>datos/radar.js</code>. Genéralo con <code>python -m radar web</code>.</p>';
    return;
  }
  const $ = (s, el = document) => el.querySelector(s);
  const MUN = R.municipios;
  const CAP = R.capital;
  const BASE = R.base_s;
  const CY = R.cursos_y; // cursos con matrícula real (año de inicio)
  const NAC0 = R.nac_desde;
  const SVGNS = "http://www.w3.org/2000/svg";

  // ------------------------------------------------------------------ formato
  const f0 = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0, useGrouping: "always" });
  const f1 = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const f2 = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const MENOS = "−", NBSP = " ";
  const ent = v => (v == null || isNaN(v) ? "—" : f0.format(Math.round(v)).replace("-", MENOS));
  const signo = v => (v > 0.0001 ? "+" : v < -0.0001 ? MENOS : "");
  const pct = (v, d = 0) => (v == null || isNaN(v) ? "—" : signo(v) + (d ? f1 : f0).format(Math.abs(d ? v : Math.round(v))) + NBSP + "%");
  const pctAbs = (v, d = 0) => (v == null || isNaN(v) ? "—" : (d ? f1 : f0).format(Math.abs(d ? v : Math.round(v))) + NBSP + "%");
  const curso = s => `${s}/${String(s + 1).slice(-2)}`;
  const cursoCorto = s => `${String(s).slice(-2)}/${String(s + 1).slice(-2)}`;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fecha = iso => {
    if (!iso) return "—";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleDateString("es-ES", { day: "numeric", month: "long", year: "numeric" });
  };

  const fechaCorta = iso => {
    const d = new Date(iso);
    return isNaN(d) ? (iso || "—") : d.toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric" });
  };

  function get(obj, ruta) {
    return ruta.split(".").reduce((o, k) => {
      if (o == null) return undefined;
      if (Array.isArray(o) && /^-?\d+$/.test(k)) { const i = +k; return o[i < 0 ? o.length + i : i]; }
      return o[k];
    }, obj);
  }

  // ------------------------------------------------------------------ valores derivados para la prosa
  const nacAnios = Object.keys(R.region.nac).map(Number).sort((a, b) => a - b);
  const ultNac = nacAnios[nacAnios.length - 1];
  const peor = (R.resumen.donde_falla.peores || []).find(p => /Buitrago/.test(p.municipio));
  const fuente = clave => R.fuentes.find(f => f.clave === clave) || {};
  const derivados = {
    nac_ultimo_anio: ultNac,
    nac_ultimo: ent(R.region.nac[ultNac]),
    nac_2008: ent(R.region.nac[2008]),
    curso_inicial: curso(CY[0]),
    peor_error: peor ? pct(peor.error_medio_pct) : "—",
    fecha_primaria: fecha(fuente("primaria_curso").modificado_en_portal),
    fecha_nacidos: fecha(fuente("nacidos").modificado_en_portal),
    generado: fecha(R.generado_utc),
  };
  document.querySelectorAll("[data-r]").forEach(el => {
    const ruta = el.dataset.r;
    let v = ruta in derivados ? derivados[ruta] : get(R, ruta);
    const f = el.dataset.f;
    if (f === "int") v = ent(v);
    else if (f === "pct") v = pct(v);
    else if (f === "pct1") v = pct(v, 1);
    else if (f === "pctabs") v = pctAbs(v);
    else if (f === "pct1abs") v = pctAbs(v, 1);
    else if (f === "dec") v = (v < 0 ? MENOS : "") + f2.format(Math.abs(v));
    el.textContent = v == null ? "—" : v;
  });

  // ------------------------------------------------------------------ cifras de cabecera
  (function cifras() {
    const P = R.resumen.proyeccion_1o, ult = P.region[P.region.length - 1], c = P.comprobacion_fuera_de_muestra;
    const bt = R.resumen.backtest_1o.mdape.grande;
    const menos = P.real_base - ult.prevision;
    const html = [
      `<div class="cifra"><span class="cifra-valor">${ent(menos)} <span class="cifra-unidad">alumnos menos</span></span>
       <span class="cifra-texto">en 1º de primaria en ${esc(ult.curso)} que en ${esc(P.base)} (${ent(P.real_base)}), un ${pctAbs(ult.cambio_pct, 1)} menos. Intervalo del 80 %: entre ${ent(P.real_base - ult.p90)} y ${ent(P.real_base - ult.p10)} menos.</span></div>`,
      `<div class="cifra"><span class="cifra-valor">${pctAbs(bt[5].radar, 1)} <span class="cifra-unidad">de error mediano</span></span>
       <span class="cifra-texto">al prever 1º de primaria con cinco cursos de antelación en los municipios grandes, contrastado con cursos ya cerrados. Suponer que nada cambia falla un ${pctAbs(bt[5].ingenuo, 1)}.</span></div>`,
      c ? `<div class="cifra"><span class="cifra-valor">${ent(c.previsto)} <span class="cifra-unidad">previstos</span></span>
       <span class="cifra-texto">para ${esc(c.curso)} sin usar ese dato. La cifra ${c.provisional ? "provisional " : ""}publicada es ${ent(c.publicado)}: una diferencia del ${pct(c.error_pct, 1)}.</span></div>` : "",
    ];
    document.getElementById("cifras").innerHTML = html.join("");
  })();

  // ------------------------------------------------------------------ estado
  const estado = { nivel: "p1", modo: "cambio", iP1: R.cursos_p1.length - 1, iPI: R.cursos_pi.length - 1, sel: CAP, orden: { col: "cambio", dir: 1 } };

  const GRUPO_TXT = {
    "Madrid capital": "su intervalo usa los errores de los municipios grandes",
    grande: "municipio grande: 250 alumnos de 1º o más en " + curso(CY[0]),
    mediano: "municipio mediano: de 50 a 249 alumnos de 1º en " + curso(CY[0]),
    pequeño: "municipio pequeño: menos de 50 alumnos de 1º en " + curso(CY[0]),
  };

  // valor que colorea el mapa para un municipio y el estado actual
  function dato(m, nivel = estado.nivel) {
    const i = nivel === "p1" ? estado.iP1 : estado.iPI;
    const prev = nivel === "p1" ? m.p1 : m.pi;
    const real = nivel === "p1" ? m.y1 : m.inf;
    if (!prev || !real) return null;
    const p = prev[i], base = real[real.length - 1];
    if (!p || p[0] == null || !base) return null;
    return { p: p[0], lo: p[1], hi: p[2], base, cambio: (p[0] / base - 1) * 100, ancho: (p[2] - p[1]) / p[0] * 100 };
  }

  // ------------------------------------------------------------------ escalas de color
  const DIV = { cortes: [-30, -20, -10, -3, 3, 10, 20, 30],
    colores: ["#8f2a24", "#c2453b", "#e2786b", "#f3b6ab", "#e6e4dd", "#c3dbf7", "#86b6ef", "#3987e5", "#1c5cab"],
    etiquetas: ["−30 % o más", "−30 a −20", "−20 a −10", "−10 a −3", "±3 %", "+3 a +10", "+10 a +20", "+20 a +30", "+30 % o más"] };
  const ANCHO = { cortes: [20, 40, 80], colores: ["#e3e7ed", "#b3bdca", "#7a889b", "#455269"],
    etiquetas: ["menos del 20 %", "20 a 40 %", "40 a 80 %", "80 % o más"] };
  const clase = (v, cortes) => { let i = 0; while (i < cortes.length && v >= cortes[i]) i++; return i; };
  function colorDe(m) {
    const d = dato(m);
    if (!d) return "url(#rayado)";
    return estado.modo === "cambio" ? DIV.colores[clase(d.cambio, DIV.cortes)] : ANCHO.colores[clase(d.ancho, ANCHO.cortes)];
  }

  // ------------------------------------------------------------------ mapa
  const svg = document.getElementById("svg-mapa");
  svg.setAttribute("viewBox", R.mapa.viewBox);
  const defs = document.createElementNS(SVGNS, "defs");
  defs.innerHTML = '<pattern id="rayado" patternUnits="userSpaceOnUse" width="7" height="7" patternTransform="rotate(45)"><rect width="7" height="7" fill="#f1efea"/><line x1="0" y1="0" x2="0" y2="7" stroke="#c8c5bc" stroke-width="2.4"/></pattern>';
  svg.appendChild(defs);
  const capa = document.createElementNS(SVGNS, "g");
  svg.appendChild(capa);
  const caminos = {};
  Object.keys(R.mapa.d).forEach(cm => {
    const p = document.createElementNS(SVGNS, "path");
    p.setAttribute("d", R.mapa.d[cm]);
    p.setAttribute("class", "m");
    p.dataset.cm = cm;
    capa.appendChild(p);
    caminos[cm] = p;
  });
  const halo = document.createElementNS(SVGNS, "path"); halo.setAttribute("class", "sel-halo");
  const marco = document.createElementNS(SVGNS, "path"); marco.setAttribute("class", "sel");
  svg.appendChild(halo); svg.appendChild(marco);

  const tip = document.getElementById("tooltip");
  const caja = document.getElementById("mapa-caja");
  function textoTip(cm) {
    const m = MUN[cm];
    const d = dato(m);
    const etapa = estado.nivel === "p1" ? "1º de primaria" : "Infantil 3-5";
    const c = estado.nivel === "p1" ? R.cursos_p1[estado.iP1] : R.cursos_pi[estado.iPI];
    if (!d) return `<strong>${esc(m.n)}</strong><span class="t-sec">${m.col ? "Sin alumnado de infantil de 2º ciclo" : "Sin colegio de primaria"}</span>`;
    return `<strong>${esc(m.n)}</strong>${etapa}, ${esc(c)}: ${ent(d.p)} <span class="t-sec">(${ent(d.lo)}–${ent(d.hi)})</span><br>` +
      (estado.modo === "cambio" ? `Cambio frente a ${esc(R.base)}: ${pct(d.cambio)}` : `Ancho del intervalo: ${pctAbs(d.ancho)} de la previsión`);
  }
  let tocando = false;
  svg.addEventListener("pointerdown", e => { tocando = e.pointerType === "touch"; });
  svg.addEventListener("pointermove", e => {
    const cm = e.target.dataset && e.target.dataset.cm;
    if (!cm || e.pointerType === "touch") { tip.hidden = true; return; }
    tip.innerHTML = textoTip(cm);
    tip.hidden = false;
    const r = caja.getBoundingClientRect();
    let x = e.clientX - r.left + 14, y = e.clientY - r.top + 14;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    if (x + w > r.width) x = e.clientX - r.left - w - 14;
    if (y + h > r.height) y = e.clientY - r.top - h - 14;
    tip.style.left = Math.max(0, x) + "px"; tip.style.top = Math.max(0, y) + "px";
  });
  svg.addEventListener("pointerleave", () => { tip.hidden = true; });
  svg.addEventListener("click", e => {
    const cm = e.target.dataset && e.target.dataset.cm;
    if (!cm) return;
    seleccionar(cm, true);
    if (tocando && window.matchMedia("(max-width: 959px)").matches) {
      document.getElementById("ficha").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });

  function pintarMapa() {
    Object.entries(caminos).forEach(([cm, p]) => {
      const m = MUN[cm], g = estado.nivel === "p1" ? m.g : m.gi;
      p.setAttribute("fill", colorDe(m));
      p.setAttribute("fill-opacity", estado.modo === "cambio" && g === "pequeño" && dato(m) ? "0.42" : "1");
    });
    const sel = caminos[estado.sel];
    halo.setAttribute("d", sel ? sel.getAttribute("d") : "");
    marco.setAttribute("d", sel ? sel.getAttribute("d") : "");
    // leyenda
    const esc_ = estado.modo === "cambio" ? DIV : ANCHO;
    const c = estado.nivel === "p1" ? R.cursos_p1[estado.iP1] : R.cursos_pi[estado.iPI];
    const etapa = estado.nivel === "p1" ? "1º de primaria" : "infantil de 3 a 5 años";
    const titulo = estado.modo === "cambio"
      ? `Cambio previsto en ${etapa}, ${c} frente a ${R.base}`
      : `Ancho del intervalo del 80 % en ${etapa}, ${c}, en % de la previsión (más oscuro, más incierto)`;
    document.getElementById("leyenda").innerHTML = `<span class="ley-titulo">${esc(titulo)}</span>` +
      esc_.colores.map((col, i) => `<span class="ley-item"><span class="sw" style="background:${col}"></span>${esc(esc_.etiquetas[i])}</span>`).join("") +
      `<span class="ley-item"><span class="sw rayado"></span>${estado.nivel === "p1" ? "sin colegio de primaria" : "sin infantil de 2º ciclo"}</span>` +
      (estado.modo === "cambio" ? `<span class="ley-item"><span class="sw" style="background:${DIV.colores[1]};opacity:.42"></span>color atenuado: municipio pequeño, intervalo muy ancho</span>` : "");
    const sinCol = Object.values(MUN).filter(m => !dato(m)).length;
    document.getElementById("nota-mapa").textContent = estado.modo === "cambio"
      ? `Los municipios pequeños salen atenuados porque su intervalo es muy ancho; «Incertidumbre» lo muestra para todos. ${sinCol} municipios no tienen ${estado.nivel === "p1" ? "colegio de primaria" : "alumnado de infantil de 2º ciclo"}; sus niños se escolarizan en los vecinos.`
      : "El intervalo sale de los errores reales del pasado en municipios de tamaño parecido y con la misma antelación.";
    $("#mapa-desc").textContent = titulo + ". La misma información está en la tabla de municipios, debajo del mapa.";
  }

  // ------------------------------------------------------------------ controles
  const selCurso = document.getElementById("sel-curso");
  const selMuni = document.getElementById("sel-muni");
  function opcionesCurso() {
    const lista = estado.nivel === "p1" ? R.cursos_p1 : R.cursos_pi;
    const i = estado.nivel === "p1" ? estado.iP1 : estado.iPI;
    selCurso.innerHTML = lista.map((c, k) => `<option value="${k}"${k === i ? " selected" : ""}>${c}</option>`).join("");
  }
  const ordenNombres = Object.keys(MUN).sort((a, b) => MUN[a].n.localeCompare(MUN[b].n, "es"));
  selMuni.innerHTML = ordenNombres.map(cm => `<option value="${cm}">${esc(MUN[cm].n)}${MUN[cm].col ? "" : " (sin colegio)"}</option>`).join("");
  document.querySelectorAll('input[name="nivel"]').forEach(r => r.addEventListener("change", e => {
    estado.nivel = e.target.value; opcionesCurso(); actualizar();
  }));
  document.querySelectorAll('input[name="modo"]').forEach(r => r.addEventListener("change", e => { estado.modo = e.target.value; actualizar(); }));
  selCurso.addEventListener("change", () => {
    if (estado.nivel === "p1") estado.iP1 = +selCurso.value; else estado.iPI = +selCurso.value;
    actualizar();
  });
  selMuni.addEventListener("change", () => seleccionar(selMuni.value, true));

  function seleccionar(cm, anunciar) {
    if (!MUN[cm]) return;
    estado.sel = cm;
    selMuni.value = cm;
    try { history.replaceState(null, "", "#municipio=" + cm); } catch (e) { /* file:// en algunos navegadores */ }
    pintarMapa();
    ficha();
    if (anunciar) document.getElementById("anuncio").textContent = "Ficha de " + MUN[cm].n + " actualizada.";
  }

  function actualizar() { pintarMapa(); ficha(); tablaMunicipios(); }

  // ------------------------------------------------------------------ gráfico de líneas con banda
  function pasoBonito(v) {
    const e = Math.pow(10, Math.floor(Math.log10(v))), f = v / e;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * e;
  }
  function grafico(el, cfg) {
    let ancho = 0;
    function dibujar() {
      const W = Math.max(260, el.clientWidth);
      if (W === ancho) return;
      ancho = W;
      const H = Math.round(Math.max(210, Math.min(290, W * 0.56)));
      const mg = { l: 48, r: 12, t: 12, b: 28 };
      const xs = [cfg.x0, cfg.x1];
      let ymax = 0;
      cfg.series.forEach(s => s.pts.forEach(p => { if (p[1] != null) ymax = Math.max(ymax, p[1]); }));
      if (cfg.banda) cfg.banda.pts.forEach(p => { if (p[2] != null) ymax = Math.max(ymax, p[2]); });
      if (ymax <= 0) ymax = 1;
      const paso = Math.max(1, pasoBonito(ymax / 4));
      ymax = Math.ceil(ymax / paso) * paso;
      const sx = x => mg.l + (x - xs[0]) / (xs[1] - xs[0]) * (W - mg.l - mg.r);
      const sy = y => mg.t + (1 - y / ymax) * (H - mg.t - mg.b);
      let s = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(cfg.aria)}">`;
      s += '<g class="rejilla">';
      for (let v = 0; v <= ymax + 1e-9; v += paso) {
        s += `<line x1="${mg.l}" x2="${W - mg.r}" y1="${sy(v)}" y2="${sy(v)}"/><text x="${mg.l - 6}" y="${sy(v) + 4}" text-anchor="end">${ent(v)}</text>`;
      }
      s += "</g>";
      const nx = xs[1] - xs[0];
      const pasoX = W < 420 ? (nx > 20 ? 10 : 4) : (nx > 20 ? 5 : 2);
      s += '<g class="eje">';
      s += `<line x1="${mg.l}" x2="${W - mg.r}" y1="${sy(0)}" y2="${sy(0)}"/>`;
      for (let x = Math.ceil(xs[0] / pasoX) * pasoX; x <= xs[1]; x += pasoX) {
        s += `<line x1="${sx(x)}" x2="${sx(x)}" y1="${sy(0)}" y2="${sy(0) + 4}"/><text x="${sx(x)}" y="${H - 8}" text-anchor="middle">${cursoCorto(x)}</text>`;
      }
      s += "</g>";
      if (cfg.hoy != null) {
        const xh = sx(cfg.hoy + 0.5);
        s += `<line class="hoy" x1="${xh}" x2="${xh}" y1="${mg.t}" y2="${sy(0)}"/><text class="hoy-txt" x="${xh + 5}" y="${mg.t + 10}">previsión</text>`;
      }
      if (cfg.banda && cfg.banda.pts.length) {
        const b = cfg.banda.pts.filter(p => p[1] != null);
        const d = "M" + b.map(p => `${sx(p[0])},${sy(p[2])}`).join("L") + "L" + b.slice().reverse().map(p => `${sx(p[0])},${sy(p[1])}`).join("L") + "Z";
        s += `<path d="${d}" fill="${cfg.banda.color}" stroke="none"/>`;
      }
      cfg.series.forEach(se => {
        const pts = se.pts.filter(p => p[1] != null);
        if (!pts.length) return;
        s += `<path class="linea" d="M${pts.map(p => `${sx(p[0])},${sy(p[1])}`).join("L")}" stroke="${se.color}"${se.disc ? ' stroke-dasharray="6 4"' : ""}${se.fino ? ' stroke-width="1.5"' : ""}/>`;
        if (se.marc) pts.forEach(p => {
          const hueco = se.huecos && se.huecos.includes(p[0]);
          s += `<circle cx="${sx(p[0])}" cy="${sy(p[1])}" r="${se.fino ? 2.6 : 3.4}" fill="${hueco ? "#fdfdfc" : se.color}" stroke="${hueco ? se.color : "#fdfdfc"}" stroke-width="${hueco ? 1.6 : 1.2}"/>`;
        });
      });
      s += `<line class="cruz" x1="0" x2="0" y1="${mg.t}" y2="${sy(0)}" visibility="hidden"/>`;
      s += `<rect class="capa-hover" x="${mg.l}" y="${mg.t}" width="${W - mg.l - mg.r}" height="${sy(0) - mg.t}" fill="transparent"/>`;
      s += "</svg>";
      const ley = cfg.series.filter(x => x.nombre).map(se => `<span><i class="${se.disc ? "disc" : ""}" style="border-color:${se.color}"></i>${esc(se.nombre)}</span>`).join("") +
        (cfg.banda ? `<span><i class="banda" style="background:${cfg.banda.color}"></i>${esc(cfg.banda.nombre)}</span>` : "");
      el.innerHTML = `<div class="leyenda-graf">${ley}</div>${s}<div class="tooltip" hidden></div>`;
      const svgEl = el.querySelector("svg"), cruz = el.querySelector(".cruz"), tt = el.querySelector(".tooltip"), capaH = el.querySelector(".capa-hover");
      const mover = e => {
        const r = svgEl.getBoundingClientRect();
        const px = e.clientX - r.left;
        const x = Math.max(xs[0], Math.min(xs[1], Math.round(xs[0] + (px - mg.l) / (W - mg.l - mg.r) * (xs[1] - xs[0]))));
        cruz.setAttribute("x1", sx(x)); cruz.setAttribute("x2", sx(x)); cruz.setAttribute("visibility", "visible");
        let filas = cfg.series.map(se => { const p = se.pts.find(q => q[0] === x && q[1] != null); return p ? `${esc(se.nombreTip || se.nombre)}: ${ent(p[1])}${se.huecos && se.huecos.includes(x) ? " (provisional)" : ""}` : null; }).filter(Boolean);
        if (cfg.banda) { const p = cfg.banda.pts.find(q => q[0] === x && q[1] != null); if (p) filas.push(`Intervalo del 80 %: ${ent(p[1])}–${ent(p[2])}`); }
        if (!filas.length) { tt.hidden = true; return; }
        tt.innerHTML = `<strong>Curso ${curso(x)}</strong>${filas.join("<br>")}`;
        tt.hidden = false;
        const top = svgEl.offsetTop;
        let left = sx(x) + 12;
        if (left + tt.offsetWidth > W) left = sx(x) - tt.offsetWidth - 12;
        tt.style.left = Math.max(0, left) + "px"; tt.style.top = top + mg.t + "px";
      };
      capaH.addEventListener("pointermove", mover);
      capaH.addEventListener("pointerdown", mover);
      capaH.addEventListener("pointerleave", () => { tt.hidden = true; cruz.setAttribute("visibility", "hidden"); });
    }
    dibujar();
    if ("ResizeObserver" in window) {
      const ro = new ResizeObserver(() => dibujar());
      ro.observe(el);
      el._ro && el._ro.disconnect();
      el._ro = ro;
    }
  }

  // ------------------------------------------------------------------ ficha de municipio
  function ficha() {
    const cm = estado.sel, m = MUN[cm];
    const el = document.getElementById("ficha");
    const partes = [];
    const meta = [m.z ? (m.z === "Capital" ? "Área Capital" : "Área " + m.z) : null, m.pob ? `${ent(m.pob)} habitantes (${R.anio_pob})` : null,
      m.g ? GRUPO_TXT[m.g] : null].filter(Boolean).join(" · ");
    partes.push(`<h3 id="ficha-titulo">${esc(m.n)}</h3><p class="meta">${esc(meta)}</p>`);
    if (!m.col) {
      const n = m.nac[m.nac.length - 1];
      partes.push(`<div class="aviso"><p>No tiene colegio de primaria: sus niños se escolarizan en municipios vecinos y cuentan en las previsiones de esos municipios. En ${ultNac} nacieron aquí ${ent(n)} niños.</p></div>`);
      partes.push(`<h4>Nacimientos por año</h4><div class="grafico" id="g-nac"></div>`);
      el.innerHTML = partes.join("");
      grafico(document.getElementById("g-nac"), {
        x0: NAC0 + 6, x1: ultNac + 6, aria: `Nacidos en ${m.n} por año, desplazados al curso en que entrarían en 1º de primaria`,
        series: [{ nombre: "Nacidos seis años antes (curso en que entrarían en 1º)", nombreTip: "Nacidos seis años antes", color: "#6f6c64", marc: true, fino: true, pts: m.nac.map((v, k) => [NAC0 + k + 6, v]) }],
      });
      return;
    }
    const d1 = dato(m, "p1"), di = dato(m, "pi");
    const kpi = (etq, d, base, cursoTxt) => d ? `<div class="kpi"><span class="kpi-etq">${esc(etq)} · ${esc(cursoTxt)}</span><span class="kpi-valor">${ent(d.p)}</span>
      <span class="kpi-rango">entre ${ent(d.lo)} y ${ent(d.hi)} (intervalo del 80 %)</span>
      <span class="kpi-cambio ${d.cambio < -0.5 ? "baja" : d.cambio > 0.5 ? "sube" : ""}">${pct(d.cambio)} frente a ${esc(R.base)} (${ent(base)})</span></div>` : "";
    partes.push(`<div class="kpis">${kpi("1º de primaria", d1, d1 && d1.base, R.cursos_p1[estado.iP1])}${kpi("Infantil de 3 a 5 años", di, di && di.base, R.cursos_pi[estado.iPI])}</div>`);
    if (m.g === "pequeño") {
      const md = R.resumen.backtest_1o.mdape["pequeño"];
      partes.push(`<div class="aviso"><p>Municipio pequeño: con tan pocos alumnos, dos o tres familias cambian mucho el porcentaje. En este grupo el error mediano del método va del ${pctAbs(md[1].radar, 1)} al ${pctAbs(md[6].radar, 1)}, y por eso el intervalo es ancho. Conviene leerlo junto a los municipios de su zona.</p></div>`);
    }
    const propios = (m.bt || []).filter(r => r[1] >= 2 && r[2] > 0 && r[3] != null).map(r => (r[3] / r[2] - 1) * 100);
    if (propios.length >= 3) {
      const abs = propios.map(Math.abs).sort((a, b) => a - b), med = abs.length % 2 ? abs[(abs.length - 1) / 2] : (abs[abs.length / 2 - 1] + abs[abs.length / 2]) / 2;
      const media = propios.reduce((a, b) => a + b, 0) / propios.length;
      if (med > 15) partes.push(`<div class="aviso"><p>Aquí el radar ha fallado bastante en el pasado: error mediano del ${pctAbs(med, 1)} en sus ${propios.length} previsiones hechas con dos o más cursos de antelación, y en media ${media < 0 ? "se quedó corto" : "se pasó"} (${pct(media, 1)}). El intervalo es el de su grupo de tamaño y no recoge ese sesgo propio: tómalo con cautela.</p></div>`);
    }
    if (cm === CAP) partes.push(`<p>No se puede bajar a los distritos: el catálogo regional no publica nacimientos por distrito, aunque sí el alumnado.</p>`);
    partes.push(`<h4>1º de primaria: alumnos y nacidos seis años antes</h4><div class="grafico" id="g-1o"></div>
      <details class="desplegable-mini"><summary>Ver los datos en una tabla</summary><div class="tabla-scroll" id="t-1o"></div></details>`);
    partes.push(`<p>Factor del municipio: ${f2.format(m.f)} alumnos de 1º por cada niño nacido aquí, medido en su matrícula de infantil de ${R.base}. Por encima de 1, el municipio escolariza a más niños de los que nacen en él.</p>`);
    // backtest del municipio
    const bt = (m.bt || []).filter(r => r[0] + r[1] === BASE && r[2] > 0).sort((a, b) => a[0] - b[0]);
    if (bt.length) {
      const g = m.g === "Madrid capital" ? "Madrid capital" : m.g;
      const mdg = R.resumen.backtest_1o.mdape[g];
      const filas = bt.map(r => {
        const er = (r[3] / r[2] - 1) * 100, en = (r[4] / r[2] - 1) * 100;
        return `<tr><td>${curso(r[0])}</td><td>${r[1]}</td><td>${ent(r[3])}</td><td>${pct(er, 1)}</td><td>${ent(r[4])}</td><td>${pct(en, 1)}</td></tr>`;
      }).join("");
      partes.push(`<h4>¿Cómo habría acertado?</h4><p>Previsiones para ${curso(BASE)}, cuando hubo ${ent(bt[0][2])} alumnos de 1º, hechas en cursos anteriores con los datos de cada momento.</p>
        <div class="tabla-scroll"><table class="tabla compacta"><thead><tr><th>Hecha en</th><th>Cursos antes</th><th>Radar</th><th>Error</th><th>Nada cambia</th><th>Error</th></tr></thead><tbody>${filas}</tbody></table></div>
        <p class="nota">En el grupo de ${g === "Madrid capital" ? "la capital" : "municipios " + g + "s"}, el error mediano del radar a 3 y 5 cursos es del ${pctAbs(mdg[3].radar, 1)} y el ${mdg[5] ? pctAbs(mdg[5].radar, 1) : "—"}; suponiendo que nada cambia, del ${pctAbs(mdg[3].ingenuo, 1)} y el ${mdg[5] ? pctAbs(mdg[5].ingenuo, 1) : "—"}.</p>`);
    }
    if (m.cen != null) {
      let lectura = "La población infantil se mueve poco respecto a los nacimientos.";
      if (m.cen >= 105) lectura = "Llegan familias con niños pequeños. En municipios así el método tiende a quedarse corto: el dato real puede acercarse al extremo alto del intervalo.";
      else if (m.cen <= 95) lectura = "Se van más familias con niños pequeños de las que llegan.";
      partes.push(`<h4>Señal de llegada de familias</h4><p>A 1 de enero de ${R.anio_censo} vivían aquí ${ent(m.cen_n)} niños de 0 a 4 años: ${ent(m.cen)} por cada 100 nacidos en el municipio en ${R.anio_censo - 5}-${R.anio_censo - 1}. ${lectura}</p>`);
    }
    if (m.pi) {
      partes.push(`<h4>Infantil de 3 a 5 años</h4><div class="grafico" id="g-inf"></div>
        <details class="desplegable-mini"><summary>Ver los datos en una tabla</summary><div class="tabla-scroll" id="t-inf"></div></details>`);
      if (m.gi === "pequeño") partes.push(`<p class="nota">En infantil, en los municipios pequeños, el método no mejora a suponer que nada cambia: tómalo como orientativo.</p>`);
    }
    el.innerHTML = partes.join("");

    // gráfico 1º
    const x0 = NAC0 + 6, x1 = BASE + R.cursos_p1.length;
    const reales = CY.map((s, k) => [s, m.y1[k]]);
    const prev = m.p1.map((p, k) => [BASE + 1 + k, p[0], p[1], p[2]]);
    grafico(document.getElementById("g-1o"), {
      x0, x1, hoy: BASE, aria: `Alumnos de 1º de primaria en ${m.n}: reales de ${curso(CY[0])} a ${curso(BASE)} y previstos hasta ${curso(x1)}, junto a los nacidos seis años antes`,
      series: [
        { nombre: "Nacidos seis años antes", color: "#8a877e", fino: true, marc: true, pts: m.nac.map((v, k) => [NAC0 + k + 6, v]) },
        { nombre: "Alumnos de 1º", color: "#2a78d6", marc: true, pts: reales },
        { nombre: "Previsión", color: "#2a78d6", disc: true, pts: [[BASE, m.y1[m.y1.length - 1]]].concat(prev.map(p => [p[0], p[1]])), nombreTip: "Previsión" },
      ],
      banda: { nombre: "Intervalo del 80 %", color: "rgba(42,120,214,0.16)", pts: prev.map(p => [p[0], p[2], p[3]]) },
    });
    const filasT = [];
    for (let s = x0; s <= x1; s++) {
      const k = s - CY[0], j = s - BASE - 1, n = m.nac[s - 6 - NAC0];
      filasT.push(`<tr><td>${curso(s)}</td><td>${ent(n)}</td><td>${k >= 0 && k < CY.length ? ent(m.y1[k]) : ""}</td><td>${j >= 0 ? ent(m.p1[j][0]) : ""}</td><td>${j >= 0 ? ent(m.p1[j][1]) + "–" + ent(m.p1[j][2]) : ""}</td></tr>`);
    }
    document.getElementById("t-1o").innerHTML = `<table class="tabla compacta"><thead><tr><th>Curso</th><th>Nacidos 6 años antes</th><th>Alumnos de 1º</th><th>Previsión</th><th>Intervalo del 80 %</th></tr></thead><tbody>${filasT.join("")}</tbody></table>`;

    if (m.pi) {
      const xi1 = BASE + R.cursos_pi.length;
      const coh = s => { const a = [s - 5, s - 4, s - 3].map(y => m.nac[y - NAC0]); return a.some(v => v == null) ? null : a.reduce((x, y) => x + y, 0); };
      const realesI = CY.map((s, k) => [s, m.inf[k]]);
      const prevI = m.pi.map((p, k) => [BASE + 1 + k, p[0], p[1], p[2]]);
      const cohs = []; for (let s = CY[0]; s <= xi1; s++) cohs.push([s, coh(s)]);
      grafico(document.getElementById("g-inf"), {
        x0: CY[0], x1: xi1, hoy: BASE, aria: `Alumnos de infantil de 3 a 5 años en ${m.n}, reales y previstos`,
        series: [
          { nombre: "Nacidos de las tres cohortes", color: "#8a877e", fino: true, marc: true, pts: cohs },
          { nombre: "Alumnos de infantil 3-5", color: "#2a78d6", marc: true, pts: realesI },
          { nombre: "Previsión", color: "#2a78d6", disc: true, pts: [[BASE, m.inf[m.inf.length - 1]]].concat(prevI.map(p => [p[0], p[1]])) },
        ],
        banda: { nombre: "Intervalo del 80 %", color: "rgba(42,120,214,0.16)", pts: prevI.map(p => [p[0], p[2], p[3]]) },
      });
      const ft = [];
      for (let s = CY[0]; s <= xi1; s++) {
        const k = s - CY[0], j = s - BASE - 1;
        ft.push(`<tr><td>${curso(s)}</td><td>${ent(coh(s))}</td><td>${k < CY.length ? ent(m.inf[k]) : ""}</td><td>${j >= 0 ? ent(m.pi[j][0]) : ""}</td><td>${j >= 0 ? ent(m.pi[j][1]) + "–" + ent(m.pi[j][2]) : ""}</td></tr>`);
      }
      document.getElementById("t-inf").innerHTML = `<table class="tabla compacta"><thead><tr><th>Curso</th><th>Nacidos de las tres cohortes</th><th>Alumnos</th><th>Previsión</th><th>Intervalo del 80 %</th></tr></thead><tbody>${ft.join("")}</tbody></table>`;
    }
  }

  // ------------------------------------------------------------------ tabla de municipios
  function tablaMunicipios() {
    const t = document.getElementById("tabla-municipios");
    const etapa = estado.nivel === "p1" ? "1º de primaria" : "infantil de 3 a 5 años";
    const c = estado.nivel === "p1" ? R.cursos_p1[estado.iP1] : R.cursos_pi[estado.iPI];
    $("#tabla-caption").textContent = `${etapa[0].toUpperCase() + etapa.slice(1)}: alumnos en ${R.base} y previsión para ${c}. Municipios con alumnado.`;
    const cols = [["nombre", "Municipio"], ["zona", "Área"], ["base", `Alumnos ${R.base}`], ["p", `Previsión ${c}`], ["int", "Intervalo del 80 %"], ["cambio", "Cambio"]];
    const o = estado.orden;
    t.tHead.innerHTML = "<tr>" + cols.map(([k, n]) => {
      const ordenable = k !== "int";
      const aria = o.col === k ? ` aria-sort="${o.dir > 0 ? "ascending" : "descending"}"` : "";
      return `<th scope="col"${aria} class="${k === "nombre" || k === "zona" ? "txt" : ""}">${ordenable ? `<button type="button" class="orden" data-col="${k}">${esc(n)}</button>` : esc(n)}</th>`;
    }).join("") + "</tr>";
    const filas = Object.entries(MUN).map(([cm, m]) => ({ cm, m, d: dato(m) })).filter(x => x.d);
    const val = (x, k) => k === "nombre" ? x.m.n : k === "zona" ? (x.m.z || "") : x.d[k];
    filas.sort((a, b) => {
      const va = val(a, o.col), vb = val(b, o.col);
      return (typeof va === "string" ? va.localeCompare(vb, "es") : va - vb) * o.dir;
    });
    t.tBodies[0].innerHTML = filas.map(x => `<tr><td class="txt"><button type="button" class="ir" data-cm="${x.cm}">${esc(x.m.n)}</button>${x.m.g === "pequeño" ? ' <span class="nota">(pequeño)</span>' : ""}</td><td class="txt">${esc(x.m.z || "")}</td><td>${ent(x.d.base)}</td><td class="destacado">${ent(x.d.p)}</td><td>${ent(x.d.lo)}–${ent(x.d.hi)}</td><td class="${x.d.cambio < -0.5 ? "baja" : x.d.cambio > 0.5 ? "sube" : ""}">${pct(x.d.cambio)}</td></tr>`).join("");
  }
  document.getElementById("tabla-municipios").addEventListener("click", e => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.col) {
      const k = b.dataset.col;
      estado.orden = { col: k, dir: estado.orden.col === k ? -estado.orden.dir : 1 };
      tablaMunicipios();
      const nb = document.querySelector(`#tabla-municipios button[data-col="${k}"]`);
      nb && nb.focus();
    } else if (b.dataset.cm) {
      seleccionar(b.dataset.cm, true);
      document.getElementById("mapa").scrollIntoView({ behavior: "smooth" });
    }
  });

  // ------------------------------------------------------------------ región
  (function region() {
    const G = R.region;
    const ys = Object.keys(G.y1).map(Number).sort((a, b) => a - b);
    const prev = G.p1.map((p, k) => [BASE + 1 + k, p[1], p[2], p[3]]);
    const x0 = ys[0], x1 = BASE + G.p1.length;
    grafico(document.getElementById("graf-region"), {
      x0, x1, hoy: BASE, aria: `Alumnos de 1º de primaria en la Comunidad de Madrid de ${curso(x0)} a ${curso(BASE)}, previsión hasta ${curso(x1)} y nacidos seis años antes`,
      series: [
        { nombre: "Nacidos seis años antes", color: "#8a877e", fino: true, marc: true, pts: Object.keys(G.nac).map(Number).filter(a => a + 6 >= x0).map(a => [a + 6, G.nac[a]]) },
        { nombre: "Alumnos de 1º (hueco: provisional)", nombreTip: "Alumnos de 1º", color: "#2a78d6", marc: true, huecos: G.provisionales, pts: ys.map(s => [s, G.y1[s]]) },
        { nombre: "Previsión", color: "#2a78d6", disc: true, pts: [[BASE, G.suma_municipios_base]].concat(prev.map(p => [p[0], p[1]])) },
      ],
      banda: { nombre: "Intervalo del 80 %", color: "rgba(42,120,214,0.16)", pts: prev.map(p => [p[0], p[2], p[3]]) },
    });
    const filas = [];
    for (let s = x0; s <= x1; s++) {
      const j = s - BASE - 1;
      filas.push(`<tr><td>${curso(s)}</td><td>${ent(G.nac[s - 6])}</td><td>${G.y1[s] != null ? ent(G.y1[s]) + (G.provisionales.includes(s) ? " (prov.)" : "") : ""}</td><td>${j >= 0 ? ent(prev[j][1]) : ""}</td><td>${j >= 0 ? ent(prev[j][2]) + "–" + ent(prev[j][3]) : ""}</td></tr>`);
    }
    document.getElementById("tabla-region").innerHTML = `<table class="tabla compacta"><thead><tr><th>Curso</th><th>Nacidos 6 años antes</th><th>Alumnos de 1º</th><th>Previsión</th><th>Intervalo del 80 %</th></tr></thead><tbody>${filas.join("")}</tbody></table>`;
    const nombreA = n => Object.keys(MUN).find(cm => MUN[cm].n === n);
    const item = r => { const cm = nombreA(r.municipio); return `<li><button type="button" data-cm="${cm}">${esc(r.municipio)}</button> <span class="rk-cifra">${ent(r.base)} → ${ent(r.prevision)} (${pct(r.cambio_pct)})</span></li>`; };
    document.getElementById("rk-caen").innerHTML = R.resumen.ranking.mas_caen.map(item).join("");
    document.getElementById("rk-suben").innerHTML = R.resumen.ranking.mas_suben.map(item).join("");
    document.querySelectorAll(".lista-rk").forEach(l => l.addEventListener("click", e => {
      const b = e.target.closest("button[data-cm]");
      if (!b) return;
      seleccionar(b.dataset.cm, true);
      document.getElementById("mapa").scrollIntoView({ behavior: "smooth" });
    }));
  })();

  // ------------------------------------------------------------------ tabla de error
  (function tablaError() {
    const M = R.resumen.backtest_1o.mdape;
    const hs = [1, 2, 3, 4, 5, 6];
    const nombres = { "Madrid capital": "Madrid capital", grande: "Grandes", mediano: "Medianos", pequeño: "Pequeños" };
    const nmun = R.resumen.backtest_1o.municipios_por_grupo;
    let h = `<thead><tr><th scope="col">Grupo y método</th>${hs.map(x => `<th scope="col">${x} ${x === 1 ? "curso" : "cursos"}</th>`).join("")}</tr></thead><tbody>`;
    Object.keys(nombres).forEach(g => {
      if (!M[g]) return;
      h += `<tr class="grupo-fila"><th colspan="7" scope="rowgroup">${nombres[g]}${nmun[g] ? ` (${nmun[g]} ${nmun[g] === 1 ? "municipio" : "municipios"})` : ""}</th></tr>`;
      [["radar", "Radar"], ["ingenuo", "Nada cambia"], ["nacidos", "Solo nacidos"]].forEach(([k, n]) => {
        h += `<tr><th scope="row" class="txt" style="font-weight:${k === "radar" ? 650 : 400}">${n}</th>${hs.map(x => `<td class="${k === "radar" ? "destacado" : ""}">${M[g][x] ? pctAbs(M[g][x][k], 1) : "—"}</td>`).join("")}</tr>`;
      });
    });
    document.getElementById("tabla-error").innerHTML = h + "</tbody>";
  })();

  // ------------------------------------------------------------------ fuentes
  (function fuentes() {
    const h = `<thead><tr><th scope="col" class="txt">Dataset</th><th scope="col" class="txt">Editor</th><th scope="col" class="txt">Para qué</th><th scope="col" class="txt">Descarga</th><th scope="col" class="txt">Licencia</th></tr></thead><tbody>` +
      R.fuentes.map(f => `<tr><td class="txt"><a href="${esc(f.pagina)}">${esc(f.titulo)}</a>${f.recurso && f.recurso !== f.titulo ? `<br><span class="nota">${esc(f.recurso)}</span>` : ""}</td><td class="txt">${esc(f.editor)}</td><td class="txt">${esc(f.uso)}</td><td class="txt"><a href="${esc(f.url)}" aria-label="Descargar el fichero oficial: ${esc(f.recurso || f.titulo)}">${/\.zip$/i.test(f.url) ? "ZIP" : "CSV"}</a><br><span class="nota">${esc(fechaCorta(f.fecha_descarga_utc))}</span></td><td class="txt"><abbr title="${esc(f.licencia_titulo || "")}">${/attribution/i.test(f.licencia_titulo || "") ? "CC BY" : esc(f.licencia_titulo || "")}</abbr></td></tr>`).join("") + "</tbody>";
    document.getElementById("tabla-fuentes").innerHTML = h;
  })();

  // ------------------------------------------------------------------ arranque
  const m = /municipio=(\d{5})/.exec(location.hash);
  if (m && MUN[m[1]]) estado.sel = m[1];
  opcionesCurso();
  selMuni.value = estado.sel;
  actualizar();
})();
