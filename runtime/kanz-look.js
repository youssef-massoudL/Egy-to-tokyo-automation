/* Kanz look v2 (2026-10-10): opt-in components for new videos, loaded after kanz.js.
 *
 * Finished projects do not load this file, so their re-renders stay byte-identical. New projects
 * (copied from projects/_template) load it and call K.look() before the first K.cam(). The
 * full guide, with the reasons and the safe-zone sources, is docs/LOOK-V2.md.
 *
 *   K.look()                     safe-zone layout, key light, deeper vignette, contact shadows on every K.img
 *   K.board(id, x, y, {h})       taller boards (camera centres on the board's real height)
 *   K.img(..., {shadow, glow, float, depth, ground})   extra options on the existing component
 *   K.shadow / K.glow            contact shadow on the ground, lavender light behind the focus
 *   K.fg / K.bgObj / K.depth     parallax layers: blurred foreground, faint background, any element
 *   K.doc / K.docMark / K.docFocus   genuine screenshot on paper, lavender highlight on the spoken phrase
 *   K.photo                      real photo in the approved grayscale treatment, slow push, credit line
 *   K.map / K.pin / K.outline    grayscale base map, lavender pins with labels, drawn region outlines
 *   K.count / K.pile / K.stack   numbers that count up, objects that pile up, bars built from objects
 *   K.swap / K.walk              change state or pose on a word; two-frame walk between two points
 *   K.SAFE / K.safeGuide         platform safe zones (engine/lint.py checks every frame against them)
 */
(function () {
  const K = window.K, tl = K.tl, ns = "http://www.w3.org/2000/svg";
  const stage = document.getElementById("stage"), world = document.getElementById("world");
  const place = (e, x, y) => gsap.set(e, { left: x, top: y, xPercent: -50, yPercent: -50 });
  const hide = (e) => tl.set(e, { autoAlpha: 0 }, 0);
  const rnd = (i, s) => Math.sin(i * 12.9898 + s * 78.233) * 0.5; // deterministic -0.5..0.5
  const END = () => (window.DURATION || 60) + 2;
  const loaded = (img, fn) => { if (img.complete && img.naturalWidth) fn(); else img.addEventListener("load", fn, { once: true }); };

  K.lookVersion = "2026-10-10";
  // Organic Reels / TikTok / Shorts / Facebook Reels on 1080x1920, sources in docs/LOOK-V2.md.
  // Text must stay inside: y 270..1440; x 120..960 below y 1000 (action buttons, either side
  // because Arabic UIs mirror them); x 65..1015 above it.
  K.SAFE = { top: 270, bottom: 1440, left: 120, right: 960, upperLeft: 65, upperRight: 1015, upperBottom: 1000 };
  K.LOOK = false;
  K.lookOpts = { shadow: false };

  K.look = function (o = {}) {
    K.LOOK = true;
    stage.classList.add("look2");
    if (!document.getElementById("keylight")) {
      const k = document.createElement("div"); k.id = "keylight"; stage.insertBefore(k, world);
    }
    // centre boards in the space between the top safe line and the captions (270..1260)
    K.view = { x: 540, y: o.viewY || 765 };
    if (o.zoom) K.zoom = o.zoom;
    K.lookOpts = { shadow: o.shadow !== false };
    if (/[?&]safe\b/.test(location.search)) K.safeGuide(true);
  };

  // ---------- boards with a real height ----------
  const board0 = K.board;
  K.board = function (id, x, y, o = {}) {
    const b = board0(id, x, y);
    if (o.h) { b.style.height = o.h + "px"; K.boards[id].h = o.h; }
    return b;
  };
  K.camAt = function (id, o = {}) {
    const b = K.boards[id], s = o.scale || K.zoom;
    const cx = b.x + 500 + (o.dx || 0), cy = b.y + (b.h || 860) / 2 + (o.dy || 0);
    return { x: K.view.x - cx * s, y: K.view.y - cy * s, scale: s };
  };
  const boardOf = (el) => { for (const id in K.boards) if (K.boards[id].el === el || K.boards[id].el.contains(el)) return id; return null; };

  // ---------- per-frame layer: parallax, idle float, followers (shadow/glow track their object) ----------
  const movers = new Map(); // el -> [fn(q, cam) -> [dx, dy]]
  const followers = [];
  const addMover = (el, fn) => { if (!movers.has(el)) movers.set(el, []); movers.get(el).push(fn); };
  const seek0 = K.seek;
  K.seek = function (t) {
    seek0(t);
    const q = Math.floor(t * K.fps + 1e-6) / K.fps;
    const cam = { x: gsap.getProperty(world, "x"), y: gsap.getProperty(world, "y"), s: gsap.getProperty(world, "scaleX") || 1 };
    movers.forEach((fns, el) => {
      let dx = 0, dy = 0;
      fns.forEach((f) => { const d = f(q, cam); dx += d[0]; dy += d[1]; });
      el.style.translate = `${dx.toFixed(1)}px ${dy.toFixed(1)}px`;
    });
    followers.forEach((f) => f(q));
  };

  // depth f > 0 moves faster than the world (foreground), f < 0 slower (background). Measured from the
  // camera framing its board; pass o.frame {dx, dy, scale} when the board is framed off-centre.
  K.depth = function (el, f, o = {}) {
    const id = o.board || boardOf(el.parentNode) || boardOf(el);
    if (!id) return el;
    addMover(el, (q, cam) => {
      const c = K.camAt(id, { ...(o.frame || {}), scale: cam.s });
      return [((cam.x - c.x) * f) / cam.s, ((cam.y - c.y) * f) / cam.s];
    });
    return el;
  };

  // ---------- light ----------
  K.shadow = function (parent, cx, groundY, w, o = {}) {
    const e = K.el("div", "kshadow", parent);
    const h = o.h || w * 0.17;
    gsap.set(e, { left: cx - w / 2, top: groundY - h / 2, width: w, height: h, opacity: o.opacity || 1 });
    if (o.at != null) { hide(e); tl.fromTo(e, { autoAlpha: 0, scaleX: 0.5 }, { autoAlpha: o.opacity || 1, scaleX: 1, duration: 0.5, immediateRender: false }, o.at); }
    if (o.out != null) tl.to(e, { autoAlpha: 0, duration: 0.3 }, o.out);
    return e;
  };
  K.glow = function (parent, cx, cy, size, o = {}) {
    const e = K.el("div", "kglow", parent);
    gsap.set(e, { left: cx - size / 2, top: cy - size / 2, width: size, height: size });
    if (o.at != null) {
      hide(e);
      tl.fromTo(e, { autoAlpha: 0, scale: 0.7 }, { autoAlpha: 1, scale: 1, duration: 0.7, ease: "power2.out", immediateRender: false }, o.at);
      const end = o.out != null ? o.out : END();
      tl.to(e, { opacity: 0.72, duration: 1.1, yoyo: true, repeat: Math.max(1, Math.ceil((end - o.at - 0.7) / 1.1)), ease: "sine.inOut" }, o.at + 0.7);
    }
    if (o.out != null) tl.to(e, { autoAlpha: 0, duration: 0.4 }, o.out);
    return e;
  };

  // K.img gains: shadow (default on under K.look), glow (true or a diameter), float (true or px),
  // depth (parallax factor), ground (board y of the object's base when the image has empty space below).
  const img0 = K.img;
  K.img = function (parent, src, o = {}) {
    const wantShadow = o.shadow != null ? o.shadow : K.lookOpts.shadow;
    let gl, sh;
    if (o.glow) { gl = K.el("div", "kglow", parent); }
    if (wantShadow) { sh = K.el("div", "kshadow", parent); }
    const e = img0(parent, src, o);
    const pulse = (q) => 0.86 + 0.14 * Math.sin(q * 2.3);
    if (gl) {
      const d = o.glow === true ? o.w * 1.45 : o.glow;
      gsap.set(gl, { left: o.x - d / 2, top: o.y - d / 2, width: d, height: d });
    }
    if (sh) {
      const sw = o.shadowW || o.w * 0.82;
      loaded(e, () => {
        const h = (o.w * e.naturalHeight) / e.naturalWidth;
        const gy = o.ground != null ? o.ground : o.y + h / 2 - h * 0.05;
        gsap.set(sh, { left: o.x - sw / 2, top: gy - sw * 0.085, width: sw, height: sw * 0.17 });
      });
    }
    if (gl || sh) followers.push((q) => {
      const c = showing(e, q); // after K.swap the shadow and glow follow the new state
      const op = c.style.visibility === "hidden" ? 0 : parseFloat(c.style.opacity === "" ? 1 : c.style.opacity);
      const dx = gsap.getProperty(c, "x"), dy = gsap.getProperty(c, "y"), sc = gsap.getProperty(c, "scaleX");
      if (sh) {
        const lift = Math.max(0, -dy) / 260;
        sh.style.opacity = String(op * Math.max(0.25, 1 - lift));
        sh.style.transform = `translateX(${dx.toFixed(1)}px) scale(${(sc * (1 - Math.min(0.5, lift))).toFixed(3)})`;
      }
      if (gl) { gl.style.opacity = String(op * pulse(q)); gl.style.transform = `translate(${dx.toFixed(1)}px, ${dy.toFixed(1)}px)`; }
    });
    if (o.float) {
      const amp = o.float === true ? 7 : o.float, t0 = o.at || 0, ph = rnd(src.length, 5) * 6;
      addMover(e, (q) => [0, q < t0 + 0.5 ? 0 : Math.sin((q - t0 - 0.5) * 1.7 + ph) * amp]);
    }
    if (o.depth) { K.depth(e, o.depth); if (sh) K.depth(sh, o.depth, { board: boardOf(parent) }); if (gl) K.depth(gl, o.depth, { board: boardOf(parent) }); }
    return e;
  };

  // blurred, darker object close to the lens: frames the shot and gives depth when the camera moves
  K.fg = function (parent, src, o) {
    const e = img0(parent, src, { x: o.x, y: o.y, w: o.w, rot: o.rot });
    e.classList.add("kfg"); // decorative: lint does not hold it to the safe zones
    gsap.set(e, { zIndex: 8, filter: `blur(${o.blur == null ? 7 : o.blur}px) brightness(${o.dim || 0.5})` });
    if (o.at != null) { hide(e); tl.fromTo(e, { autoAlpha: 0, x: o.fromX || 120 }, { autoAlpha: 1, x: 0, duration: 0.8, ease: "power2.out", immediateRender: false }, o.at); }
    if (o.out != null) tl.to(e, { autoAlpha: 0, duration: 0.4 }, o.out);
    return K.depth(e, o.depth == null ? 0.45 : o.depth);
  };
  // faint object far behind the board: fills empty space without competing with the focus
  K.bgObj = function (parent, src, o) {
    const e = img0(parent, src, { x: o.x, y: o.y, w: o.w, rot: o.rot });
    gsap.set(e, { zIndex: -1, filter: `blur(${o.blur == null ? 2 : o.blur}px) brightness(.8)` });
    const op = o.opacity || 0.22;
    if (o.at != null) { hide(e); tl.fromTo(e, { autoAlpha: 0 }, { autoAlpha: op, duration: 0.8, immediateRender: false }, o.at); }
    else gsap.set(e, { opacity: op });
    if (o.out != null) tl.to(e, { autoAlpha: 0, duration: 0.4 }, o.out);
    return K.depth(e, o.depth == null ? -0.3 : o.depth);
  };

  // ---------- evidence: genuine screenshot on paper ----------
  // Coordinates for marks are in the screenshot's own pixels (measure them in any image viewer).
  K.doc = function (parent, src, o) {
    const pad = 16, d = K.el("div", "kdoc", parent);
    gsap.set(d, { width: o.w, rotation: o.rot == null ? 1.2 : o.rot, boxSizing: "border-box" });
    place(d, o.x, o.y);
    const im = K.el("img", "shot", d); im.src = src;
    if (o.tape !== false) K.el("div", "tape", d);
    d._k = 0; d._pending = []; d._o = o; d._pad = pad;
    let s;
    if (o.source) { s = K.el("div", "ksrc", parent, o.source); d._src = s; }
    loaded(im, () => {
      d._k = (o.w - pad * 2) / im.naturalWidth;
      d._h = pad * 2 + im.naturalHeight * d._k;
      if (s) place(s, o.x, o.y + d._h / 2 + 40);
      d._pending.splice(0).forEach((f) => f());
    });
    if (o.at != null) {
      hide(d);
      tl.fromTo(d, { y: 110, rotation: (o.rot == null ? 1.2 : o.rot) - 5, autoAlpha: 0 },
        { y: 0, rotation: o.rot == null ? 1.2 : o.rot, autoAlpha: 1, duration: 0.6, ease: "power3.out", immediateRender: false }, o.at);
      K.sfx(o.at, "paper", 0.5);
      if (o.tape !== false) K.sfx(o.at + 0.35, "tape", 0.3);
      if (s) { hide(s); tl.fromTo(s, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.4, immediateRender: false }, o.at + 0.45); }
    }
    if (o.out != null) tl.to(s ? [d, s] : d, { autoAlpha: 0, duration: 0.3 }, o.out);
    return d;
  };
  // highlighter (default) or drawn frame ({frame: true}) sweeping right -> left over the spoken phrase
  K.docMark = function (doc, x, y, w, h, o = {}) {
    const m = K.el("div", o.frame ? "kframe" : "kmark", doc), p = o.pad == null ? 6 : o.pad;
    const set = () => { const k = doc._k, P = doc._pad; gsap.set(m, { left: P + x * k - p, top: P + y * k - p * 0.6, width: w * k + 2 * p, height: h * k + 1.2 * p }); };
    doc._k ? set() : doc._pending.push(set);
    hide(m);
    tl.fromTo(m, { scaleX: 0, autoAlpha: 1 }, { scaleX: 1, autoAlpha: 1, duration: o.dur || 0.55, ease: "power1.inOut", immediateRender: false }, o.at);
    K.sfx(o.at, "marker", 0.3);
    if (o.out != null) tl.to(m, { autoAlpha: 0, duration: 0.25 }, o.out);
    return m;
  };
  // slow camera push onto a point of the screenshot (its own pixels). Resolved when the image loads,
  // so do not use {via} on the K.cam() that follows it.
  K.docFocus = function (t, doc, x, y, scale, dur = 1.2) {
    const go = () => {
      const id = boardOf(doc), b = K.boards[id], o = doc._o, k = doc._k;
      const px = o.x - o.w / 2 + doc._pad + x * k, py = o.y - doc._h / 2 + doc._pad + y * k;
      K.push(t, id, scale, dur, { dx: px - 500, dy: py - (b.h || 860) / 2 });
    };
    doc._k ? go() : doc._pending.push(go);
  };

  // ---------- photos ----------
  // o: {x, y, w, h, at, out, credit, graded (true when the file already has the Kanz treatment), pos, kb}
  K.photo = function (parent, src, o) {
    const p = K.el("div", "kphoto" + (o.graded ? "" : " grade"), parent);
    gsap.set(p, { width: o.w, height: o.h, rotation: o.rot || 0 });
    place(p, o.x, o.y);
    const im = K.el("img", "", p); im.src = src;
    if (o.pos) im.style.objectPosition = o.pos;
    let c;
    if (o.credit) { c = K.el("div", "ksrc", parent, o.credit); gsap.set(c, { fontSize: 22 }); place(c, o.x, o.y + o.h / 2 + 34); }
    if (o.at != null) {
      hide(p);
      tl.fromTo(p, { autoAlpha: 0, scale: 0.95, y: 50 }, { autoAlpha: 1, scale: 1, y: 0, duration: 0.6, ease: "power3.out", immediateRender: false }, o.at);
      tl.fromTo(im, { scale: 1 }, { scale: o.kb || 1.08, duration: Math.max(1, (o.out != null ? o.out : END()) - o.at), ease: "none", immediateRender: false }, o.at);
      K.sfx(o.at, K.cue(o.sfx, "shutter"), 0.3); // camera shutter (2026-10-13); was a click
      if (c) { hide(c); tl.fromTo(c, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.4, immediateRender: false }, o.at + 0.4); }
    }
    if (o.out != null) tl.to(c ? [p, c] : p, { autoAlpha: 0, duration: 0.3 }, o.out);
    return p;
  };

  // ---------- maps ----------
  K.map = function (parent, src, o) {
    const e = K.el("img", "kmap", parent); e.src = src;
    gsap.set(e, { width: o.w }); place(e, o.x, o.y);
    if (o.at != null) { hide(e); tl.fromTo(e, { autoAlpha: 0, scale: 1.04 }, { autoAlpha: o.opacity || 1, scale: 1, duration: 0.8, immediateRender: false }, o.at); K.sfx(o.at, "whoosh", 0.25); }
    if (o.out != null) tl.to(e, { autoAlpha: 0, duration: 0.3 }, o.out);
    return e;
  };
  K.pin = function (parent, x, y, label, o = {}) {
    const p = K.el("div", "kpin", parent);
    gsap.set(p, { left: x, top: y });
    hide(p);
    tl.fromTo(p, { y: -70, autoAlpha: 0, scale: 0.6 }, { y: 0, autoAlpha: 1, scale: 1, duration: 0.45, ease: "bounce.out", immediateRender: false }, o.at);
    K.sfx(o.at, "pop", 0.38);
    let t;
    if (label) {
      const dx = o.side === "left" ? -1 : o.side === "right" ? 1 : 0;
      t = K.tag(parent, label, { x: x + dx * 40, y: y - 62, at: o.at + 0.18, lav: o.lav !== false, size: o.size || 34, sfx: "click", gain: 0.2 });
      if (dx) gsap.set(t, { xPercent: dx > 0 ? 0 : -100 });
    }
    if (o.out != null) tl.to(t ? [p, t] : p, { autoAlpha: 0, duration: 0.25 }, o.out);
    return p;
  };
  // region outline from an SVG path in board pixels, drawn on, then a faint lavender fill
  K.outline = function (parent, d, o = {}) {
    const s = document.createElementNS(ns, "svg");
    s.setAttribute("class", "mk"); s.setAttribute("width", 1000); s.setAttribute("height", 860);
    s.setAttribute("filter", "url(#boil)");
    parent.appendChild(s);
    const f = document.createElementNS(ns, "path");
    f.setAttribute("d", d); f.setAttribute("fill", o.fill || "rgba(213,173,239,.16)"); f.setAttribute("stroke", "none");
    const p = document.createElementNS(ns, "path");
    p.setAttribute("d", d); p.setAttribute("fill", "none"); p.setAttribute("stroke", o.color || "#d5adef");
    p.setAttribute("stroke-width", o.width || 6); p.setAttribute("stroke-linejoin", "round"); p.setAttribute("stroke-linecap", "round");
    s.appendChild(f); s.appendChild(p);
    const L = p.getTotalLength(), dur = o.dur || 1.1;
    gsap.set(p, { strokeDasharray: L, strokeDashoffset: L });
    hide(s); hide(f);
    tl.set(s, { autoAlpha: 1 }, o.at);
    tl.to(p, { strokeDashoffset: 0, duration: dur, ease: "power1.inOut" }, o.at);
    tl.fromTo(f, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.5, immediateRender: false }, o.at + dur * 0.8);
    K.sfx(o.at, "marker", 0.3);
    if (o.out != null) tl.to(s, { autoAlpha: 0, duration: 0.3 }, o.out);
    return s;
  };

  // ---------- numbers become things ----------
  // Only numbers the voice says. o: {x, y, from, to, at, dur, size, digits: "ar" | "en", decimals, step, prefix, suffix, color, head}
  K.count = function (parent, o) {
    const e = K.el("div", "kcount" + (o.head === false ? "" : " head"), parent);
    gsap.set(e, { fontSize: o.size || 140, color: o.color || "#fff", fontWeight: o.head === false ? 500 : 700 });
    place(e, o.x, o.y);
    const nf = new Intl.NumberFormat(o.digits === "en" ? "en-US" : "ar-EG",
      { minimumFractionDigits: o.decimals || 0, maximumFractionDigits: o.decimals || 0, useGrouping: o.group !== false });
    const st = { v: o.from || 0 }, step = o.step || 0;
    const paint = () => {
      const v = step ? Math.round(st.v / step) * step : st.v;
      e.innerHTML = (o.prefix || "") + `<bdi class="num">${nf.format(v)}</bdi>` + (o.suffix || "");
    };
    paint();
    hide(e);
    const dur = o.dur || 1.2;
    tl.fromTo(e, { autoAlpha: 0, scale: 0.85 }, { autoAlpha: 1, scale: 1, duration: 0.3, ease: "back.out(2)", immediateRender: false }, o.at);
    tl.fromTo(st, { v: o.from || 0 }, { v: o.to, duration: dur, ease: o.ease || "power2.out", onUpdate: paint, immediateRender: false }, o.at);
    if (o.sfx !== false) {
      for (let i = 0; i < Math.floor(dur * 5); i++) K.sfx(o.at + i * 0.2, "click", 0.1);
      K.sfx(o.at + dur, o.endSfx || "coin", 0.42);
    }
    if (o.out != null) tl.to(e, { autoAlpha: 0, duration: 0.3 }, o.out);
    return e;
  };
  // a heap of n copies dropping in, bottom row first. o: {x, y (base), n, w, at, stagger, out}
  K.pile = function (parent, src, o) {
    const n = o.n, w = o.w || 120, items = [];
    let base = 1; while ((base * (base + 1)) / 2 < n) base++;
    const st = o.stagger == null ? Math.min(0.09, 1.4 / n) : o.stagger;
    if (K.lookOpts.shadow && o.shadow !== false) K.shadow(parent, o.x, o.y + w * 0.22, base * w * 0.85, { at: o.at, out: o.out });
    let i = 0;
    for (let row = 0; i < n; row++) {
      const c = Math.max(1, base - row);
      for (let j = 0; j < c && i < n; j++, i++) {
        const x = o.x + (j - (c - 1) / 2) * w * 0.74 + rnd(i, 3) * w * 0.16;
        const y = o.y - row * w * 0.4 + rnd(i, 5) * w * 0.06, r = rnd(i, 7) * 26;
        const e = img0(parent, src, { x, y, w });
        gsap.set(e, { rotation: r, zIndex: 2 + row });
        hide(e);
        tl.fromTo(e, { y: -280 - row * 40, autoAlpha: 0, rotation: r + 25 }, { y: 0, autoAlpha: 1, rotation: r, duration: 0.42, ease: "power2.in", immediateRender: false }, o.at + i * st);
        if (i % 3 === 0) K.sfx(o.at + i * st + 0.4, K.cue(o.sfx, "coin"), 0.22);
        items.push(e);
      }
    }
    if (o.out != null) tl.to(items, { autoAlpha: 0, duration: 0.3 }, o.out);
    return items;
  };
  // a bar made of objects: n copies stacked upward from (x, y). o: {n, w, step, at, stagger, out}
  K.stack = function (parent, src, o) {
    const w = o.w || 110, step = o.step || w * 0.26, items = [];
    const st = o.stagger == null ? Math.min(0.08, 1.2 / o.n) : o.stagger;
    if (K.lookOpts.shadow && o.shadow !== false) K.shadow(parent, o.x, o.y + w * 0.2, w * 1.1, { at: o.at, out: o.out });
    for (let i = 0; i < o.n; i++) {
      const e = img0(parent, src, { x: o.x + rnd(i, 11) * w * 0.08, y: o.y - i * step, w });
      gsap.set(e, { zIndex: 2 + i, rotation: rnd(i, 13) * 6 });
      hide(e);
      tl.fromTo(e, { y: -160, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.3, ease: "power2.in", immediateRender: false }, o.at + i * st);
      if (i % 2 === 0) K.sfx(o.at + i * st + 0.28, K.cue(o.sfx, "coin"), 0.18);
      items.push(e);
    }
    if (o.out != null) tl.to(items, { autoAlpha: 0, duration: 0.3 }, o.out);
    return items;
  };

  // ---------- states and poses (Codex asset batch 2026-10-10) ----------
  // K.swap(img, src, t): the object or character changes state in place on a word (wallet closed -> open,
  // M01 neutral -> pointing). Same position, size and rotation; its contact shadow and glow carry over.
  K.swap = function (el, src, t, o = {}) {
    const n = K.el("img", "obj", el.parentNode);
    n.src = src;
    gsap.set(n, { left: gsap.getProperty(el, "left"), top: gsap.getProperty(el, "top"), width: el.style.width || gsap.getProperty(el, "width"),
      xPercent: gsap.getProperty(el, "xPercent"), yPercent: gsap.getProperty(el, "yPercent"), rotation: gsap.getProperty(el, "rotation"),
      zIndex: el.style.zIndex || "auto" });
    hide(n);
    tl.set(el, { autoAlpha: 0 }, t);
    tl.fromTo(n, { autoAlpha: 1, scale: o.pop === false ? 1 : 1.04 }, { autoAlpha: 1, scale: 1, duration: 0.25, ease: "power2.out", immediateRender: false }, t);
    (el._swaps = el._swaps || []).push({ t, el: n });
    if (o.sfx !== false) K.sfx(t, K.cue(o.sfx, "pop"), o.gain || 0.25);
    if (o.out != null) tl.to(n, { autoAlpha: 0, duration: 0.3 }, o.out);
    return n;
  };
  // the follower of an element reads whichever state is showing at time q
  const showing = (e, q) => { let cur = e; (e._swaps || []).forEach((s) => { if (q >= s.t) cur = s.el; }); return cur; };

  // K.walk(board, [frameA, frameB], {from: [x, y], to: [x, y], at, dur, w, rest, step, sfx}): a character walks
  // between two board points with the two-frame walk cycle (frames face left; walking right mirrors them).
  // `rest` (e.g. the neutral pose) shows before and after the walk. Returns the wrapper (tween it like any element).
  K.walk = function (parent, frames, o) {
    const w = o.w || 300, step = o.step || 0.25, t0 = o.at, t1 = o.at + o.dur;
    const box = K.el("div", "abs", parent);
    gsap.set(box, { left: o.from[0], top: o.from[1], width: w, height: w, xPercent: -50, yPercent: -50, zIndex: o.z || 4 });
    if (K.lookOpts.shadow && o.shadow !== false) {
      const s = K.el("div", "kshadow", box);
      gsap.set(s, { left: w * 0.3, top: w * 0.935, width: w * 0.4, height: w * 0.07 });
    }
    const imgs = frames.concat(o.rest ? [o.rest] : []).map((src) => {
      const i = K.el("img", "obj", box); i.src = src; gsap.set(i, { left: 0, top: 0, width: w }); return i;
    });
    const mirror = o.to[0] > o.from[0] ? -1 : 1;
    gsap.set(imgs, { scaleX: mirror });
    if (o.appear != null) { hide(box); tl.fromTo(box, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3, immediateRender: false }, o.appear); }
    tl.to(box, { left: o.to[0], top: o.to[1], duration: o.dur, ease: "none" }, t0);
    followers.push((q) => {
      const walking = q >= t0 && q < t1, k = Math.floor((q - t0) / step) % 2;
      const pick = walking ? k : (o.rest ? 2 : 0);
      imgs.forEach((im, j) => { im.style.visibility = j === pick ? "visible" : "hidden"; });
      imgs[pick].style.translate = walking && k === 1 ? "0 -5px" : "0 0";
    });
    if (o.sfx) for (let t = t0; t < t1; t += step) K.sfx(t, o.sfx, o.gain || 0.15);
    if (o.out != null) tl.to(box, { autoAlpha: 0, duration: 0.3 }, o.out);
    return box;
  };

  // ---------- a second world for chapter changes (approved 2026-10-11) ----------
  // K.world(t, "paper") wipes the stage to light paper, right -> left; K.world(t, "charcoal") wipes back.
  // While on paper, text turns ink, lavender text/keywords turn deep purple and chart lines turn ink
  // (kanz-look.css, #stage[data-world=paper]); captions keep their dark pill. Use for 1-2 chapters a video.
  K.INK = "#141217";
  K.world = function (t, name, o = {}) {
    let bg = document.getElementById("paperworld");
    if (!bg) {
      bg = document.createElement("div"); bg.id = "paperworld"; stage.insertBefore(bg, world);
      tl.set(bg, { autoAlpha: 0 }, 0);
    }
    const dur = o.dur || 0.6;
    if (name === "paper") {
      tl.fromTo(bg, { autoAlpha: 1, clipPath: "inset(0 0 0 100%)" }, { autoAlpha: 1, clipPath: "inset(0 0 0 0%)", duration: dur, ease: "power3.inOut", immediateRender: false }, t);
    } else {
      tl.fromTo(bg, { clipPath: "inset(0 0% 0 0)" }, { clipPath: "inset(0 100% 0 0)", duration: dur, ease: "power3.inOut", immediateRender: false }, t);
    }
    tl.set(stage, { attr: { "data-world": name } }, t + dur / 2);
    if (o.sfx !== false) K.sfx(t, K.cue(o.sfx, "paper"), o.gain || 0.4);
  };

  // ---------- ending: the video's thesis, big, held after the last word (approved 2026-10-11) ----------
  // Use words the voice actually says. Pair it with K.cam(t, <hook board>) so the last frame mirrors the first.
  K.takeaway = function (parent, html, o = {}) {
    if (o.glow !== false) K.glow(parent, o.x, o.y, o.glow || 760, { at: o.at });
    return K.text(parent, html, { head: true, size: 120, w: 860, from: "pop", sfx: "hit", gain: 0.3, ...o });
  };

  // ---------- review overlay: red where platform UI covers the video ----------
  K.safeGuide = function (on = true) {
    let g = document.getElementById("safeguide");
    if (!on) { if (g) g.remove(); return; }
    if (g) return;
    g = document.createElement("div"); g.id = "safeguide"; stage.appendChild(g);
    const S = K.SAFE, box = (l, t, w, h, cls) => { const d = document.createElement("div"); if (cls) d.className = cls; Object.assign(d.style, { left: l + "px", top: t + "px", width: w + "px", height: h + "px" }); g.appendChild(d); };
    box(0, 0, 1080, S.top); box(0, S.bottom, 1080, 1920 - S.bottom);
    box(0, S.top, S.upperLeft, S.upperBottom - S.top); box(S.upperRight, S.top, 1080 - S.upperRight, S.upperBottom - S.top);
    box(0, S.upperBottom, S.left, S.bottom - S.upperBottom); box(S.right, S.upperBottom, 1080 - S.right, S.bottom - S.upperBottom);
  };
})();
