/* Radar de natalidad municipal · menú, capítulos y movimiento.
   No cambia ninguna cifra: solo cómo se llega a ellas. Lo que se mueve se activa con la clase «mov» de <html>
   (index.html no la pone en ?demo ni con «reducir movimiento»); sin ella quedan el menú, los capítulos y la página quieta.
   Librerías locales (MIT): vendor/lenis.min.js (scroll suave) y vendor/scrollama.min.js (pasos del relato). */
(function () {
  "use strict";
  const doc = document.documentElement;
  const $ = (s, c) => (c || document).querySelector(s);
  const $$ = (s, c) => Array.from((c || document).querySelectorAll(s));
  const MOV = doc.classList.contains("mov"), PIN = doc.classList.contains("mov-pin"), DEMO = doc.classList.contains("demo");
  const R = window.RADAR;
  const entre = v => (v < 0 ? 0 : v > 1 ? 1 : v);
  let lenis = null;

  const cab = $(".cabecera"), heroe = $(".heroe"), barra = $("#barra"), sillas = $(".aula-sillas");
  const tramoMapa = $(".tramo-mapa"), menu = $("#menu"), botonMenu = $("#menu-boton");
  if (!cab || !heroe || !barra) return;

  // ------------------------------------------------------------------ ir a un sitio de la página
  function ir(el, foco) {
    const suave = MOV ? "smooth" : "auto";
    if (foco && cab.classList.contains("pin")) { if (lenis) lenis.scrollTo(0, { duration: 1.1 }); else window.scrollTo({ top: 0, behavior: suave }); }
    else if (foco) foco.scrollIntoView({ behavior: suave, block: "center" });
    else if (lenis) lenis.scrollTo(el, { duration: 1.3 });
    else el.scrollIntoView({ behavior: suave, block: "start" });
    if (foco) setTimeout(() => foco.focus({ preventScroll: true }), MOV ? 750 : 0);
  }
  document.addEventListener("click", e => {
    const a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a || e.defaultPrevented || a.hasAttribute("data-ir") || a.classList.contains("saltar") || e.metaKey || e.ctrlKey || e.shiftKey) return;
    const id = a.getAttribute("href").slice(1), el = id && document.getElementById(id);
    if (!el) return;
    e.preventDefault();
    ir(el, a.dataset.foco ? document.getElementById(a.dataset.foco) : null);
    try { history.replaceState(null, "", "#" + id); } catch (err) { /* file:// en algunos navegadores */ }
  });

  // ------------------------------------------------------------------ menú a pantalla completa
  if (menu && botonMenu) {
    let abierto = false, cierre = null;
    const enlaces = $$("a", menu);
    const abrir = () => {
      abierto = true; clearTimeout(cierre);
      menu.hidden = false; void menu.offsetWidth; menu.classList.add("abierto");
      botonMenu.setAttribute("aria-expanded", "true"); botonMenu.setAttribute("aria-label", "Cerrar el menú");
      doc.classList.add("menu-abierto"); barra.classList.remove("oculta");
      if (lenis) lenis.stop();
      if (enlaces[0]) enlaces[0].focus({ preventScroll: true });
    };
    const cerrar = devolverFoco => {
      if (!abierto) return;
      abierto = false; menu.classList.remove("abierto");
      botonMenu.setAttribute("aria-expanded", "false"); botonMenu.setAttribute("aria-label", "Abrir el menú");
      doc.classList.remove("menu-abierto");
      if (lenis) lenis.start();
      cierre = setTimeout(() => { menu.hidden = true; }, MOV ? 620 : 0);
      if (devolverFoco) botonMenu.focus({ preventScroll: true });
    };
    botonMenu.addEventListener("click", () => (abierto ? cerrar(true) : abrir()));
    menu.addEventListener("click", e => { if (e.target.closest("a")) cerrar(false); }, true);  // antes de que el enlace mueva la página
    menu.addEventListener("wheel", e => e.preventDefault(), { passive: false });
    menu.addEventListener("touchmove", e => e.preventDefault(), { passive: false });
    document.addEventListener("keydown", e => {
      if (!abierto) return;
      if (e.key === "Escape") { e.preventDefault(); cerrar(true); return; }
      if (e.key !== "Tab") return;  // el foco no sale del menú mientras está abierto
      const f = [botonMenu].concat(enlaces), i = f.indexOf(document.activeElement);
      e.preventDefault();
      f[(i < 0 ? 0 : i + (e.shiftKey ? -1 : 1) + f.length) % f.length].focus();
    });
  }

  // ------------------------------------------------------------------ capítulos: el desplegable salta y, al bajar, dice dónde estás
  const capitulo = $("#capitulo");
  if (capitulo) {
    capitulo.addEventListener("change", () => {
      const o = capitulo.selectedOptions[0];
      let el = o && document.getElementById(o.dataset.irA);
      if (!el) return;
      if (el.tagName === "H2") el = el.closest("section") || el;  // el tramo entero, no solo su título
      if (o.value === "sillas") { if (lenis) lenis.scrollTo(0); else window.scrollTo({ top: 0, behavior: MOV ? "smooth" : "auto" }); }
      else ir(el, o.value === "municipio" ? document.getElementById("tm-buscar") : null);
      capitulo.blur();
    });
    if (window.scrollama) {
      try {
        window.scrollama().setup({ step: "[data-cap]", offset: 0.5 }).onStepEnter(r => { if (document.activeElement !== capitulo) capitulo.value = r.element.dataset.cap; });
      } catch (err) { /* sin IntersectionObserver: el desplegable sigue saltando */ }
    }
  }

  // ------------------------------------------------------------------ tarjeta fija: el siguiente paso
  const proximo = $("#proximo");
  let proximoVisto = false;
  if (proximo && !DEMO) {
    let cerrada = false;
    try { cerrada = sessionStorage.getItem("radar-proximo") === "0"; } catch (err) { /* sin almacenamiento */ }
    if (!cerrada) {
      proximo.classList.add("fuera"); proximo.hidden = false; proximoVisto = true;
      $("#proximo-cerrar").addEventListener("click", () => {
        proximo.hidden = true; proximoVisto = false;
        try { sessionStorage.setItem("radar-proximo", "0"); } catch (err) { /* sin almacenamiento */ }
      });
    }
  }
  const tarjetaFija = () => { if (proximoVisto) proximo.classList.toggle("fuera", window.scrollY < cab.offsetHeight - 60 || doc.classList.contains("menu-abierto")); };
  if (!MOV) { if (proximoVisto) { window.addEventListener("scroll", tarjetaFija, { passive: true }); tarjetaFija(); } return; }

  // ================================================================== a partir de aquí, solo con movimiento
  const FINO = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  if (window.Lenis && FINO) {  // con el dedo, el scroll del sistema ya es suave
    try { lenis = new window.Lenis({ autoRaf: true, lerp: 0.11, allowNestedScroll: true }); } catch (err) { lenis = null; }
  }

  // ------------------------------------------------------------------ fondo: los términos municipales como líneas de nivel
  if (R && R.mapa && R.mapa.d) {
    const d = Object.keys(R.mapa.d).map(k => R.mapa.d[k]).join("");
    const svg = `<svg class="curvas" viewBox="120 260 620 620" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false"><path d="${d}"/></svg>`;
    heroe.insertAdjacentHTML("afterbegin", svg);
    const dec = $(".declaracion");
    if (dec) dec.insertAdjacentHTML("afterbegin", svg);
  }

  // ------------------------------------------------------------------ títulos: las palabras suben desde su máscara al llegar
  function partir(el) {
    let w = 0;
    const pal = nodo => { const a = document.createElement("span"), b = document.createElement("span"); a.className = "pal"; a.style.setProperty("--w", w++); b.appendChild(nodo); a.appendChild(b); return a; };
    Array.from(el.childNodes).forEach(n => {
      if (n.nodeType === 3) {
        const f = document.createDocumentFragment();
        n.textContent.split(/([ \n\t]+)/).forEach(t => { if (!t) return; f.appendChild(/^[ \n\t]+$/.test(t) ? document.createTextNode(" ") : pal(document.createTextNode(t))); });
        el.replaceChild(f, n);
      } else if (n.nodeType === 1) { const hueco = document.createComment(""); el.replaceChild(hueco, n); el.replaceChild(pal(n), hueco); }
    });
  }
  if ("IntersectionObserver" in window) {
    const ioT = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { ioT.unobserve(e.target); e.target.classList.remove("por-subir"); e.target.classList.add("subido"); } }), { threshold: 0.25 });
    $$("main h2").forEach(h => {
      if (h.closest("#ficha") || h.getBoundingClientRect().top < window.innerHeight) return;
      partir(h); h.classList.add("por-subir"); ioT.observe(h);
    });
    // el color del fondo pasa de un tramo al siguiente sin corte
    const ioF = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) document.body.style.backgroundColor = e.target.matches(".alterno, .tramo-fiable") ? "#efede7" : ""; }), { rootMargin: "-50% 0px -50% 0px" });
    $$("main > section").forEach(s => ioF.observe(s));
  }

  // ------------------------------------------------------------------ la clase: de 2024/25 a 2030/31 con el scroll, el puntero o el botón
  const T_FIN = 3100, conM = /[?&]m=/.test(location.search), mira = $("#mira");
  let tAct = 0, tObj = 0, tope = 200, enBucle = false, tScroll = 0, en2030 = false, encima = false, pinH = false, pinM = false;
  const guiada = !!sillas && !conM;
  function rotuloMira() {
    if (!mira) return;
    const fin = tObj > T_FIN / 2;
    mira.textContent = pinH && !en2030 ? (FINO ? "Mueve el ratón o baja para ver 2030" : "Baja para ver 2030") : fin ? "Volver a 2024/25" : (FINO ? "Mueve o toca para ver 2030" : "Toca para ver 2030");
    mira.setAttribute("aria-pressed", fin ? "true" : "false");
  }
  function pasoT() {
    const d = tObj - tAct;
    if (Math.abs(d) < 2) { tAct = tObj; enBucle = false; }
    else { tAct += Math.sign(d) * Math.min(Math.abs(d), Math.max(Math.abs(d) * 0.2, 4), tope); requestAnimationFrame(pasoT); }
    sillas.style.setProperty("--t", tAct.toFixed(0) + "ms");
    cab.classList.toggle("fin", tAct > 2300);
  }
  function apuntar(t, maximo) { tObj = t; tope = maximo || 200; rotuloMira(); if (!enBucle) { enBucle = true; requestAnimationFrame(pasoT); } }
  const base = () => Math.max(pinH ? tScroll : 0, en2030 ? T_FIN : 0);
  if (guiada) {
    cab.classList.add("guia");
    sillas.addEventListener("pointermove", e => {
      if (e.pointerType !== "mouse" || sillas.classList.contains("re")) return;
      const r = sillas.getBoundingClientRect();
      encima = true; apuntar(entre((e.clientX - r.left - r.width * 0.08) / (r.width * 0.84)) * T_FIN);
    });
    sillas.addEventListener("pointerleave", () => { if (encima) { encima = false; apuntar(base()); } });
    if (mira) mira.addEventListener("click", () => { en2030 = !(tObj > T_FIN / 2); if (!en2030 && pinH && tScroll > T_FIN / 2) return rotuloMira(); apuntar(en2030 ? T_FIN : (pinH ? tScroll : 0), 26); });
  } else if (mira) mira.style.visibility = "hidden";

  // ------------------------------------------------------------------ tramos fijados (escritorio): se miden y, si no caben, se quedan como están
  const rejMapa = tramoMapa && $(".tramo-mapa-rejilla", tramoMapa), figMapa = tramoMapa && $(".heroe-mapa", tramoMapa);
  const lineaA = $(".linea-a"), lineaB = $(".linea-b"), tarjetas = $$(".tarjeta-paso"), svgP = $("#svg-portada");
  let surG = null, pasos = null;
  function trazoSur() {  // el contorno de los municipios del área Sur, para dibujarlo al bajar
    if (surG || !svgP || !R || !R.mapa || !R.municipios) return;
    const cms = Object.keys(R.municipios).filter(cm => R.municipios[cm].z === "Sur" && R.mapa.d[cm]);
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", "sur-trazo"); g.setAttribute("aria-hidden", "true");
    g.innerHTML = ["halo", "trazo"].map(c => cms.map(cm => `<path class="${c}" pathLength="1" d="${R.mapa.d[cm]}"/>`).join("")).join("");
    svgP.insertBefore(g, $(".etiquetas", svgP) || null);
    surG = g;
  }
  // la cifra del área Sur sale de su tarjeta y viaja hasta su sitio en el mapa: el ojo la sigue de un paso al siguiente
  let surLlego = false;
  function volarSur() {
    const fin = () => { if (surLlego) tramoMapa.classList.add("sur-fin"); };
    try {
      const o = $(".paso-sur strong"), t = svgP && $$(".etiquetas text", svgP).find(x => x.textContent.trim().indexOf("Sur") === 0);
      const dst = t && $(".e-cifra", t);
      if (!o || !dst || !o.animate) return fin();
      const a = o.getBoundingClientRect(), b = dst.getBoundingClientRect();
      if (!a.height || !b.height || a.bottom < 0 || a.top > window.innerHeight) return fin();
      const v = document.createElement("span"), cs = getComputedStyle(o);
      v.textContent = o.textContent; v.setAttribute("aria-hidden", "true");
      v.style.cssText = `position:fixed;left:${a.left}px;top:${a.top}px;z-index:20;pointer-events:none;white-space:nowrap;transform-origin:0 0;font:${cs.font};letter-spacing:${cs.letterSpacing};color:${cs.color};line-height:${a.height}px`;
      document.body.appendChild(v);
      const k = b.height / a.height;
      const an = v.animate([{ transform: "translate(0,0) scale(1)" }, { transform: `translate(${(b.left - a.left).toFixed(1)}px,${(b.top - a.top).toFixed(1)}px) scale(${k.toFixed(3)})` }], { duration: 720, easing: "cubic-bezier(.5,0,.2,1)" });
      an.onfinish = an.oncancel = () => { if (v.parentNode) v.parentNode.removeChild(v); fin(); };
    } catch (err) { fin(); }
  }
  function medir() {
    const ancho = PIN && window.matchMedia("(min-width: 900px) and (min-height: 620px)").matches;
    cab.classList.remove("pin"); if (tramoMapa) tramoMapa.classList.remove("pin", "sur-fin");
    pinH = ancho && guiada && heroe.scrollHeight <= window.innerHeight - 70;
    cab.classList.toggle("pin", pinH);
    pinM = !!(ancho && tramoMapa && figMapa && tarjetas.length === 3);
    if (pinM) {
      tramoMapa.classList.add("pin");
      if (figMapa.scrollHeight > window.innerHeight + 2 || tarjetas.some(t => t.offsetHeight > window.innerHeight * 0.8)) { tramoMapa.classList.remove("pin"); pinM = false; }
    }
    if (pinM) {
      trazoSur();
      if (!pasos && window.scrollama) {
        try {
          pasos = window.scrollama();
          pasos.setup({ step: ".tramo-mapa .tarjeta-paso", offset: 0.62 })
            .onStepEnter(r => { tarjetas.forEach(t => t.classList.toggle("activa", t === r.element)); });
        } catch (err) { pasos = null; }
      }
      if (!pasos) tarjetas.forEach(t => t.classList.add("activa"));
      else pasos.resize();
    } else if (surG) surG.style.setProperty("--s", "1");
    if (!pinH && guiada && !en2030 && !medir.hecho) {  // sin portada fijada (móvil): la clase pasa a 2030 sola, una vez
      setTimeout(() => { if (!encima && !sillas.classList.contains("re")) { en2030 = true; apuntar(T_FIN, 24); } }, 1300);
    }
    medir.hecho = true;
    rotuloMira();
  }

  // ------------------------------------------------------------------ el mapa grande: el curso avanza al bajar (una vez; el botón ▶ y el control siguen mandando)
  const Tm = window.radarTiempo, rejGrande = $(".rejilla-mapa");
  let guiado = PIN && Tm && rejGrande ? null : false, idxAnt = -1;
  const controles = $("#controles");
  if (controles) controles.addEventListener("change", () => { if (guiado) Tm.anima(false); guiado = false; });

  // ------------------------------------------------------------------ números grandes con un punto de paralaje
  const nums = $$(".paso-num, .bf-num"), aLaVista = new Set();
  if ("IntersectionObserver" in window) {
    const ioN = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) aLaVista.add(e.target); else aLaVista.delete(e.target); }), { rootMargin: "60px 0px" });
    nums.forEach(n => ioN.observe(n));
  }

  // ------------------------------------------------------------------ un solo cuadro por scroll
  let yAnt = window.scrollY, pedido = false;
  function cuadro() {
    pedido = false;
    const y = window.scrollY, vh = window.innerHeight;
    if (!doc.classList.contains("menu-abierto")) {  // la barra se esconde al bajar y vuelve al subir
      if (y > yAnt + 6 && y > 140) { barra.classList.add("oculta"); yAnt = y; }
      else if (y < yAnt - 6 || y < 80) { barra.classList.remove("oculta"); yAnt = y; }
    }
    tarjetaFija();
    if (pinH) {
      const r = cab.getBoundingClientRect(), p = entre(-r.top / Math.max(1, r.height - vh));
      tScroll = p <= 0.02 ? 0 : 800 + entre((p - 0.02) / 0.68) * (T_FIN - 800);
      cab.classList.toggle("ya", p > 0.03);
      if (!encima && !sillas.classList.contains("re")) apuntar(base());
    }
    if (pinM) {
      const r = tramoMapa.getBoundingClientRect(), p = entre((vh - r.top) / (r.height + vh));
      if (lineaA) lineaA.style.transform = `translate3d(${(-8 - p * 55).toFixed(2)}vw,0,0)`;
      if (lineaB) lineaB.style.transform = `translate3d(${(-150 + p * 55).toFixed(2)}vw,0,0)`;
      const s = entre((vh * 0.72 - tarjetas[2].getBoundingClientRect().top) / (vh * 0.5));
      if (surG) surG.style.setProperty("--s", s.toFixed(3));
      if (s > 0.92) { if (!surLlego) { surLlego = true; volarSur(); } }
      else { surLlego = false; tramoMapa.classList.remove("sur-fin"); }
    }
    if (guiado !== false) {
      const p = entre((vh * 0.85 - rejGrande.getBoundingClientRect().top) / (vh * 0.65));
      if (guiado === null && p > 0) {
        if (p >= 1 || !Tm.libre()) guiado = false;
        else { guiado = true; Tm.anima(true); }
      }
      if (guiado === true) {
        if (!Tm.libre()) { guiado = false; Tm.anima(false); }
        else {
          const i = Math.round(p * Tm.N);
          if (i !== idxAnt) { idxAnt = i; Tm.fotograma(i); }
          if (p >= 1) { guiado = false; setTimeout(Tm.fin, 650); }
        }
      }
    }
    aLaVista.forEach(n => {
      const r = n.getBoundingClientRect();
      n.style.transform = `translate3d(0,${(((r.top + r.height / 2 - vh / 2) / vh) * -22).toFixed(1)}px,0)`;
    });
  }
  const pedir = () => { if (!pedido) { pedido = true; requestAnimationFrame(cuadro); } };
  window.addEventListener("scroll", pedir, { passive: true });
  barra.addEventListener("focusin", () => barra.classList.remove("oculta"));
  let espera = null;
  window.addEventListener("resize", () => { clearTimeout(espera); espera = setTimeout(() => { medir(); pedir(); }, 160); });

  medir();
  if (location.hash.length > 1 && location.hash.indexOf("=") < 0) {  // con tramos fijados la página es más alta: se vuelve a ir al ancla
    const el = document.getElementById(location.hash.slice(1));
    if (el) el.scrollIntoView();
  }
  cuadro();

  // ------------------------------------------------------------------ con ratón: botones que tiran un poco del puntero y un aro que lo acompaña
  if (FINO) {
    $$(".boton, .pildora, .menu-boton, .tm-ver, .tiempo-play, .mira").forEach(b => {
      b.addEventListener("pointermove", e => {
        const r = b.getBoundingClientRect();
        b.style.transform = `translate(${((e.clientX - r.left - r.width / 2) * 0.2).toFixed(1)}px,${((e.clientY - r.top - r.height / 2) * 0.28).toFixed(1)}px)`;
      });
      b.addEventListener("pointerleave", () => { b.style.transform = ""; });
    });
    const c = document.createElement("div");
    c.className = "cursor"; c.setAttribute("aria-hidden", "true");
    document.body.appendChild(c);
    let x = 0, yy = 0, cx = 0, cy = 0, vivo = false;
    const sigue = () => {
      cx += (x - cx) * 0.24; cy += (yy - cy) * 0.24;
      c.style.transform = `translate3d(${cx.toFixed(1)}px,${cy.toFixed(1)}px,0)`;
      if (Math.abs(x - cx) + Math.abs(yy - cy) > 0.3) requestAnimationFrame(sigue); else vivo = false;
    };
    document.addEventListener("pointermove", e => {
      if (e.pointerType !== "mouse") return;
      x = e.clientX; yy = e.clientY;
      if (!c.classList.contains("activo")) { cx = x; cy = yy; c.classList.add("activo"); }
      c.classList.toggle("sobre", !!(e.target.closest && e.target.closest("a, button, label, select, input, summary, [data-cm], .aula-sillas")));
      if (!vivo) { vivo = true; requestAnimationFrame(sigue); }
    }, { passive: true });
    doc.addEventListener("mouseleave", () => c.classList.remove("activo"));
  }
})();
