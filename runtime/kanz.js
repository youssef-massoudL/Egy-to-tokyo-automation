/* Kanz motion runtime: a deterministic, seekable GSAP timeline for 1080x1920 Reels.
 *
 * Scenes call the component helpers below with absolute times (seconds in the final voice).
 * The renderer calls K.seek(t) for every frame; graphics are stepped at K.fps (12, "on twos").
 * Every component registers its sound cue in K.cues, which the renderer mixes under the voice.
 * Positions inside a board are element centres in board pixels (board = 1000 x 860).
 */
(function () {
  const ns = "http://www.w3.org/2000/svg";
  const K = (window.K = {
    fps: 12, W: 1080, H: 1920, view: { x: 540, y: 960 }, zoom: 1.06,
    tl: gsap.timeline({ paused: true, defaults: { ease: "power3.out" } }),
    cues: [], boards: {}, duration: (window.DURATION || 10) + 1.6,
  });
  const tl = K.tl;
  const stage = document.getElementById("stage");
  const world = document.getElementById("world");
  const overlay = document.getElementById("overlay");

  // ---------- word anchors ----------
  const norm = (s) => s.replace(/[ً-ْـ*%٪،؟?!.,:؛«»…]/g, "").replace(/[إأآ]/g, "ا").replace(/ى/g, "ي").replace(/ة/g, "ه").trim();
  K.T = function (word, after = 0, which = 0) {
    const n = norm(word);
    const hits = (window.TOKENS || []).filter((t) => t.start >= after - 1e-6 && norm(t.w).includes(n));
    if (!hits[which]) { console.error("anchor not found:", word, after); return after; }
    return hits[which].start;
  };

  // Sequential anchor: finds `word` after the previous K.N() hit, so a scene can be written in script
  // order before the voice exists (no hand-entered seconds). K.N.at(t) moves the cursor.
  K.cursor = 0;
  K.N = function (word, which = 0) { const t = K.T(word, K.cursor, which); K.cursor = t; return t; };
  K.N.at = (t) => { K.cursor = t; };

  // ---------- small DOM helpers ----------
  K.el = function (tag, cls, parent, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    (parent || stage).appendChild(e);
    return e;
  };
  K.num = (s) => `<bdi class="num">${s}</bdi>`;
  // K.cue(o.sfx, default): with K.mix = 2 (new videos), sfx: false really means silent; older scenes keep
  // the old behaviour (false fell back to the default sound) so their re-renders are unchanged.
  K.cue = (v, d) => (v === false && K.mix === 2 ? null : v || d);
  K.sfx = function (t, cat, gain = 0.45, pick) {
    if (!cat) return;
    K.cues.push({ t: Math.max(0, t), cat, gain, pick: pick == null ? K.cues.length : pick });
  };
  function place(e, x, y) { gsap.set(e, { left: x, top: y, xPercent: -50, yPercent: -50 }); }
  function hide(e) { tl.set(e, { autoAlpha: 0 }, 0); }

  // ---------- world & camera ----------
  K.board = function (id, x, y) {
    const b = K.el("div", "board", world);
    gsap.set(b, { left: x, top: y });
    K.boards[id] = { el: b, x, y };
    return b;
  };
  K.camAt = function (id, o = {}) {
    const b = K.boards[id], s = o.scale || K.zoom;
    const cx = b.x + 500 + (o.dx || 0), cy = b.y + 430 + (o.dy || 0);
    return { x: K.view.x - cx * s, y: K.view.y - cy * s, scale: s };
  };
  K.cam = function (t, id, o = {}) {
    const to = K.camAt(id, o);
    const from = K._cam || to;
    K._cam = to;
    if (t <= 0) { tl.set(world, to, 0); return; }
    const dur = o.dur || 0.75;
    if (o.via) { // pull back half way, over the midpoint of both boards: reveals the world between them
      const centre = (c) => ({ x: (K.view.x - c.x) / c.scale, y: (K.view.y - c.y) / c.scale });
      const a = centre(from), b = centre(to), s = o.via;
      const mid = { x: K.view.x - ((a.x + b.x) / 2) * s, y: K.view.y - ((a.y + b.y) / 2) * s, scale: s };
      tl.to(world, { ...mid, duration: dur / 2, ease: "power2.in" }, t);
      tl.to(world, { ...to, duration: dur / 2, ease: "power2.out" }, t + dur / 2);
    } else {
      tl.to(world, { ...to, duration: dur, ease: "power3.inOut" }, t);
    }
    if (o.sfx !== false) K.sfx(t + 0.05, "whoosh", 0.32);
  };
  K.push = function (t, id, scale, dur = 2.5, o = {}) { // slow push-in on a board
    const to = K.camAt(id, { ...o, scale });
    K._cam = to;
    tl.to(world, { ...to, duration: dur, ease: "sine.inOut" }, t);
  };

  // ---------- text ----------
  K.text = function (parent, html, o) {
    const e = K.el("div", "t " + (o.head ? "head " : "") + (o.cls || ""), parent, html);
    gsap.set(e, { fontSize: o.size || 44, color: o.color || "#fff", fontWeight: o.weight || (o.head ? 700 : 500) });
    if (o.w) gsap.set(e, { width: o.w, whiteSpace: "normal", textAlign: "center" });
    place(e, o.x, o.y);
    if (o.at != null) {
      hide(e);
      const from = o.from || "up";
      const v = from === "pop" ? { scale: 0.6, autoAlpha: 0 } : from === "fade" ? { autoAlpha: 0 } : { y: 34, autoAlpha: 0 };
      tl.fromTo(e, v, { scale: 1, y: 0, autoAlpha: 1, duration: 0.42, ease: from === "pop" ? "back.out(2)" : "power3.out", immediateRender: false }, o.at);
      if (o.sfx) K.sfx(o.at, o.sfx, o.gain || 0.4);
    }
    if (o.out != null) tl.to(e, { autoAlpha: 0, y: -20, duration: 0.3, ease: "power2.in" }, o.out);
    return e;
  };
  K.tag = function (parent, html, o) {
    const e = K.el("div", "tag " + (o.lav ? "lav" : ""), parent, html);
    if (o.size) gsap.set(e, { fontSize: o.size });
    place(e, o.x, o.y);
    gsap.set(e, { rotation: o.rot || 0 });
    if (o.at != null) {
      hide(e);
      tl.fromTo(e, { scale: 0.7, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.3, ease: "back.out(2.2)", immediateRender: false }, o.at);
      K.sfx(o.at, K.cue(o.sfx, "click"), o.gain || 0.35);
    }
    if (o.out != null) tl.to(e, { autoAlpha: 0, duration: 0.25 }, o.out);
    return e;
  };

  // ---------- objects ----------
  K.img = function (parent, src, o) {
    const e = K.el("img", "obj", parent);
    e.src = src;
    gsap.set(e, { width: o.w });
    place(e, o.x, o.y);
    gsap.set(e, { rotation: o.rot || 0 });
    if (o.at != null) {
      hide(e);
      tl.fromTo(e, { y: 60, scale: 0.9, autoAlpha: 0 }, { y: 0, scale: 1, autoAlpha: 1, duration: 0.5, ease: "back.out(1.6)", immediateRender: false }, o.at);
      K.sfx(o.at, K.cue(o.sfx, "pop"), o.gain || 0.35);
    }
    if (o.out != null) tl.to(e, { autoAlpha: 0, y: 30, duration: 0.3, ease: "power2.in" }, o.out);
    return e;
  };
  K.card = function (parent, html, o) {
    const e = K.el("div", "card", parent, html);
    gsap.set(e, { width: o.w, height: o.h, rotation: o.rot == null ? -1.5 : o.rot, padding: 0 });
    place(e, o.x, o.y);
    if (o.tape !== false) K.el("div", "tape", e);
    if (o.at != null) {
      hide(e);
      tl.fromTo(e, { y: 90, rotation: (o.rot || -1.5) + 5, autoAlpha: 0 }, { y: 0, rotation: o.rot == null ? -1.5 : o.rot, autoAlpha: 1, duration: 0.55, ease: "power3.out", immediateRender: false }, o.at);
      K.sfx(o.at, "paper", 0.5);
      if (o.tape !== false) K.sfx(o.at + 0.35, "tape", 0.3);
    }
    return e;
  };
  K.fadeTo = (e, t, opacity, o = {}) => tl.to(e, { opacity, scale: o.scale == null ? 1 : o.scale, duration: o.dur || 0.45, ease: "power2.inOut" }, t);
  K.out = (e, t, dur = 0.3) => tl.to(e, { autoAlpha: 0, duration: dur, ease: "power2.in" }, t);

  // ---------- hand-drawn marks (pen + boil) ----------
  function svgIn(parent) {
    const s = document.createElementNS(ns, "svg");
    s.setAttribute("class", "mk"); s.setAttribute("width", 1000); s.setAttribute("height", 860);
    s.setAttribute("filter", "url(#boil)");
    parent.appendChild(s);
    return s;
  }
  function draw(parent, d, o) {
    const s = svgIn(parent);
    const p = document.createElementNS(ns, "path");
    p.setAttribute("d", d); p.setAttribute("fill", "none");
    p.setAttribute("stroke", o.color || "#d5adef"); p.setAttribute("stroke-width", o.width || 7);
    p.setAttribute("stroke-linecap", "round"); p.setAttribute("stroke-linejoin", "round");
    if (o.dash) p.setAttribute("stroke-dasharray", o.dash);
    s.appendChild(p);
    if (o.at != null) {
      const L = p.getTotalLength();
      if (o.dash) { // dashed lines reveal with a clip instead of dashoffset
        hide(s);
        tl.fromTo(s, { autoAlpha: 0, clipPath: "inset(0 0 0 100%)" }, { autoAlpha: 1, clipPath: "inset(0 0 0 0%)", duration: o.dur || 0.6, ease: "power2.inOut", immediateRender: false }, o.at);
      } else {
        // round caps draw a dot even at zero length, so keep the mark hidden until its pen starts
        hide(s);
        tl.set(s, { autoAlpha: 1 }, o.at);
        gsap.set(p, { strokeDasharray: L, strokeDashoffset: L });
        tl.to(p, { strokeDashoffset: 0, duration: o.dur || 0.55, ease: "power1.inOut" }, o.at);
      }
      K.sfx(o.at, K.cue(o.sfx, "marker"), o.gain || 0.3);
    }
    if (o.out != null) tl.to(s, { autoAlpha: 0, duration: 0.25 }, o.out);
    return s;
  }
  const rnd = (i, s) => Math.sin(i * 12.9898 + s * 78.233) * 0.5;
  K.oval = function (parent, cx, cy, rx, ry, o = {}) {
    const pts = [], n = 56, turns = 1.13, a0 = -Math.PI * 0.62, seed = o.seed || 1;
    for (let i = 0; i <= n; i++) {
      const a = a0 - (i / n) * Math.PI * 2 * turns; // counter-clockwise, like a right-handed pen in RTL
      const r = 1 + 0.035 * rnd(i, seed) + (i / n) * 0.07;
      pts.push([cx + Math.cos(a) * rx * r, cy + Math.sin(a) * ry * r]);
    }
    return draw(parent, "M" + pts.map((p) => p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" L"), { dur: 0.6, ...o });
  };
  K.underline = function (parent, x1, x2, y, o = {}) { // drawn right -> left
    const pts = [], n = 10;
    for (let i = 0; i <= n; i++) pts.push([x2 - (x2 - x1) * (i / n), y + 3 * rnd(i, o.seed || 3) + (i / n) * 4]);
    return draw(parent, "M" + pts.map((p) => p.join(" ")).join(" L"), { dur: 0.45, ...o });
  };
  K.strike = function (parent, x1, y1, x2, y2, o = {}) {
    return draw(parent, `M${x1} ${y1} Q ${(x1 + x2) / 2 + 12} ${(y1 + y2) / 2 - 18} ${x2} ${y2}`, { dur: 0.4, width: 9, ...o });
  };
  K.arrow = function (parent, x1, y1, x2, y2, o = {}) {
    const mx = (x1 + x2) / 2 + (o.bend || 60), my = (y1 + y2) / 2 - (o.bend || 60);
    const ang = Math.atan2(y2 - my, x2 - mx), h = 26;
    const d = `M${x1} ${y1} Q ${mx} ${my} ${x2} ${y2} M${x2 - h * Math.cos(ang - 0.5)} ${y2 - h * Math.sin(ang - 0.5)} L${x2} ${y2} L${x2 - h * Math.cos(ang + 0.5)} ${y2 - h * Math.sin(ang + 0.5)}`;
    return draw(parent, d, { dur: 0.5, ...o });
  };
  K.rect = function (parent, x, y, w, h, o = {}) { // hand-drawn frame, starts top-right (RTL)
    const j = (i) => 3 * rnd(i, o.seed || 7);
    const d = `M${x + w} ${y + j(1)} L${x + j(2)} ${y + j(3)} L${x + j(4)} ${y + h + j(5)} L${x + w + j(6)} ${y + h} L${x + w + j(8)} ${y - 6}`;
    return draw(parent, d, { dur: 0.8, width: 5, ...o });
  };
  K.dot = function (parent, x, y, o) {
    const e = K.el("div", "abs", parent);
    gsap.set(e, { left: x - 14, top: y - 14, width: 28, height: 28, borderRadius: "50%", background: o.color || "#d5adef",
      boxShadow: "0 0 0 10px rgba(213,173,239,.25)" });
    hide(e);
    tl.fromTo(e, { scale: 0, autoAlpha: 1 }, { scale: 1, autoAlpha: 1, duration: 0.35, ease: "back.out(3)", immediateRender: false }, o.at);
    K.sfx(o.at, "pop", 0.35);
    return e;
  };
  K.dashed = function (parent, x1, y1, x2, y2, o = {}) {
    return draw(parent, `M${x1} ${y1} L${x2} ${y2}`, { dash: "14 12", width: 4, sfx: "click", gain: 0.2, ...o });
  };

  // ---------- charts (time runs left -> right, like market charts) ----------
  K.line = function (parent, pts, o) {
    const s = document.createElementNS(ns, "svg");
    s.setAttribute("class", "mk"); s.setAttribute("width", 1000); s.setAttribute("height", 860);
    parent.appendChild(s);
    if (o.fill) {
      const f = document.createElementNS(ns, "path");
      f.setAttribute("d", "M" + pts.map((p) => p.join(" ")).join(" L") + ` L${pts[pts.length - 1][0]} ${o.base} L${pts[0][0]} ${o.base} Z`);
      f.setAttribute("fill", o.fill); s.appendChild(f);
      hide(f);
      tl.fromTo(f, { autoAlpha: 0, clipPath: "inset(0 100% 0 0)" }, { autoAlpha: 1, clipPath: "inset(0 0% 0 0)", duration: o.fillDur || 0.8, ease: "power2.inOut", immediateRender: false }, o.fillAt);
    }
    const p = document.createElementNS(ns, "path");
    p.setAttribute("d", "M" + pts.map((q) => q.join(" ")).join(" L"));
    p.setAttribute("fill", "none"); p.setAttribute("stroke", o.color || "#fff"); p.setAttribute("stroke-width", o.width || 7);
    p.setAttribute("stroke-linejoin", "round"); p.setAttribute("stroke-linecap", "round");
    s.appendChild(p);
    const L = p.getTotalLength();
    gsap.set(p, { strokeDasharray: L, strokeDashoffset: L });
    hide(p);
    tl.set(p, { autoAlpha: 1 }, o.at);
    tl.to(p, { strokeDashoffset: 0, duration: o.dur || 1.6, ease: o.ease || "none" }, o.at);
    if (o.out != null) tl.to(s, { autoAlpha: 0, duration: 0.3 }, o.out);
    return s;
  };
  K.axis = function (parent, x1, x2, y, o = {}) {
    return draw(parent, `M${x2} ${y} L${x1} ${y}`, { color: "rgba(255,255,255,.45)", width: 3, dur: 0.5, sfx: "click", gain: 0.15, ...o });
  };
  // Bars drawn to scale (2026-10-11). A scale maps values to board px on a zero baseline:
  //   const S = K.scale(1200000, 390);            // the largest value on this board -> 390 px
  //   K.bar(b, { x, y, w, value: 1100000, scale: S, at });
  // Old scenes that pass a hand-entered `h` render exactly as before; engine/lint.py flags them
  // when two or more sit on one board. `illustrative: true` marks a bar that stands for no number.
  K.bars = [];
  let scales = 0;
  K.scale = function (max, px) {
    if (!(max > 0) || !(px > 0)) console.error("K.scale needs a positive max value and px:", max, px);
    return { id: ++scales, max, px, h: (v) => (v / max) * px };
  };
  K.bar = function (parent, o) { // grows upward (or downward when o.down)
    if (o.value != null) {
      if (!o.scale) console.error("K.bar: `value` needs `scale: K.scale(max, px)`", o);
      else o = { ...o, h: o.scale.h(o.value) };
    }
    if (!parent.dataset.kboard) parent.dataset.kboard = String(K.bars.length + 1) + ":" + (parent.id || "board");
    K.bars.push({ board: parent.dataset.kboard, value: o.value ?? null, scale: o.scale ? o.scale.id : null,
                  h: o.h, x: o.x, at: o.at, illustrative: !!o.illustrative });
    const e = K.el("div", "abs", parent);
    gsap.set(e, { left: o.x - o.w / 2, top: o.down ? o.y : o.y - o.h, width: o.w, height: o.h, background: o.color || "#c7c2cc",
      border: o.outline ? "4px solid rgba(255,255,255,.55)" : "none", boxSizing: "border-box", transformOrigin: o.down ? "50% 0%" : "50% 100%" });
    hide(e);
    tl.fromTo(e, { scaleY: 0, autoAlpha: 1 }, { scaleY: 1, autoAlpha: 1, duration: o.dur || 0.7, ease: "power3.out", immediateRender: false }, o.at);
    K.sfx(o.at, K.cue(o.sfx, "pop"), 0.3);
    e.kbar = o;
    return e;
  };
  // A bracket between the tops of two scaled bars, so a small true difference stays readable
  // without stretching the bars. x: where the bracket stands; label: optional tag beside it.
  K.delta = function (parent, a, b, o = {}) {
    const A = a.kbar, B = b.kbar;
    const top = (q) => (q.down ? q.y + q.h : q.y - q.h);
    const y1 = Math.min(top(A), top(B)), y2 = Math.max(top(A), top(B)), x = o.x, arm = o.arm || 22;
    const s = draw(parent, `M${x - arm} ${y1} L${x} ${y1} L${x} ${y2} L${x - arm} ${y2}`, { width: 5, sfx: "click", gain: 0.2, dur: 0.4, ...o });
    if (o.label) K.tag(parent, o.label, { x: x + (o.labelDx || 90), y: (y1 + y2) / 2, lav: true, size: o.size || 32, at: o.at != null ? o.at + 0.2 : null, sfx: "click", gain: 0.15 });
    return s;
  };

  // ---------- charts with weight (approved 2026-10-11) ----------
  // Value-based, time left -> right. The box is centred at (x, y) with size w x h in board px.
  let chartN = 0;
  function chartSvg(parent) {
    const s = document.createElementNS(ns, "svg");
    s.setAttribute("class", "mk"); s.setAttribute("width", 1000); s.setAttribute("height", 860);
    parent.appendChild(s);
    return s;
  }
  function svgEl(s, tag, attrs) {
    const e = document.createElementNS(ns, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    s.appendChild(e);
    return e;
  }
  // K.area(board, { x, y, w, h, data: [values], min, max, at, dur, grid: 3, color, marker: { i, label }, end: { html, lav } })
  // A line that draws itself with a lavender area under it, a glow and a dot riding its head.
  K.area = function (parent, o) {
    const d = o.data, n = d.length, id = "kc" + ++chartN, col = o.color || "#d5adef";
    const lo = o.min != null ? o.min : Math.min(...d), hi = o.max != null ? o.max : Math.max(...d);
    const X0 = o.x - o.w / 2, Y0 = o.y + o.h / 2;
    const px = (i) => X0 + (o.w * i) / (n - 1), py = (v) => Y0 - (o.h * (v - lo)) / (hi - lo || 1);
    const pts = d.map((v, i) => `${px(i).toFixed(1)},${py(v).toFixed(1)}`).join(" ");
    const s = chartSvg(parent);
    const defs = svgEl(s, "defs", {});
    defs.innerHTML = `<linearGradient id="${id}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${col}" stop-opacity=".42"/>` +
      `<stop offset="1" stop-color="${col}" stop-opacity="0"/></linearGradient><filter id="${id}b"><feGaussianBlur stdDeviation="9"/></filter>` +
      `<clipPath id="${id}c"><rect x="${X0}" y="${Y0 - o.h - 60}" width="0" height="${o.h + 60}"/></clipPath>`;
    const clip = defs.querySelector("rect");
    for (let g = 1; g <= (o.grid ?? 3); g++) svgEl(s, "line", { x1: X0, x2: X0 + o.w, y1: Y0 - (o.h * g) / (o.grid ?? 3), y2: Y0 - (o.h * g) / (o.grid ?? 3), stroke: "rgba(255,255,255,.07)", "stroke-width": 2 });
    svgEl(s, "line", { x1: X0, x2: X0 + o.w, y1: Y0, y2: Y0, stroke: "rgba(255,255,255,.4)", "stroke-width": 3 });
    svgEl(s, "polygon", { points: `${X0},${Y0} ${pts} ${X0 + o.w},${Y0}`, fill: `url(#${id}g)`, "clip-path": `url(#${id}c)` });
    const glow = svgEl(s, "polyline", { points: pts, fill: "none", stroke: col, "stroke-width": 22, opacity: 0.35, "stroke-linejoin": "round", filter: `url(#${id}b)` });
    const line = svgEl(s, "polyline", { points: pts, fill: "none", stroke: "#f4e8fb", "stroke-width": o.width || 10, "stroke-linejoin": "round", "stroke-linecap": "round" });
    const halo = svgEl(s, "circle", { r: 40, fill: col, opacity: 0.25 }), dot = svgEl(s, "circle", { r: 16, fill: "#fff" });
    const L = line.getTotalLength();
    [line, glow].forEach((p) => { p.setAttribute("stroke-dasharray", L); });
    const render = (p) => {
      [line, glow].forEach((e) => e.setAttribute("stroke-dashoffset", L * (1 - p)));
      clip.setAttribute("width", o.w * p);
      const q = line.getPointAtLength(L * p);
      [halo, dot].forEach((c) => { c.setAttribute("cx", q.x); c.setAttribute("cy", q.y); });
    };
    render(o.at == null ? 1 : 0);
    if (o.at != null) {
      const dur = o.dur || 1.6, pr = { p: 0 };
      hide(s);
      tl.set(s, { autoAlpha: 1 }, o.at);
      tl.fromTo(pr, { p: 0 }, { p: 1, duration: dur, ease: "none", immediateRender: false, onUpdate: () => render(pr.p) }, o.at);
      K.sfx(o.at, K.cue(o.sfx, "marker"), o.gain || 0.25);
      if (o.marker) {
        const mx = px(o.marker.i), mt = o.at + (dur * o.marker.i) / (n - 1);
        draw(parent, `M${mx} ${Y0 - o.h - 30} L${mx} ${Y0}`, { dash: "14 12", width: 4, at: mt, dur: 0.3, sfx: "click", gain: 0.15 });
        if (o.marker.label) K.tag(parent, o.marker.label, { x: mx, y: Y0 - o.h - 70, lav: true, size: o.marker.size || 34, at: mt + 0.1 });
      }
      if (o.end) K.tag(parent, o.end.html, { x: px(n - 1) - (o.end.dx ?? 0), y: py(d[n - 1]) - (o.end.dy ?? 80), lav: o.end.lav !== false, size: o.end.size || 40, at: o.at + dur });
    }
    // real data (2026-10-13): `source` puts the source line under the chart, e.g. "FRED · FEDFUNDS · ١٣/١٠/٢٠٢٦"
    let src = null;
    if (o.source) {
      src = K.el("div", "ksrc", parent, o.source);
      gsap.set(src, { fontSize: 24 });
      place(src, o.x, Y0 + 48);
      if (o.at != null) { hide(src); tl.fromTo(src, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3, immediateRender: false }, o.at + 0.2); }
    }
    if (o.out != null) tl.to(src ? [s, src] : s, { autoAlpha: 0, duration: 0.3 }, o.out);
    return { svg: s, x: px, y: py, at: o.at, dur: o.dur || 1.6 };
  };
  // K.candles(board, { x, y, w, h, data: [[open, high, low, close], ...], min, max, at, dur })
  // Candles appear left -> right; light bodies rise, dark outlined bodies fall. Returns x(i), y(v) to annotate swings.
  K.candles = function (parent, o) {
    const d = o.data, n = d.length;
    const lo = o.min != null ? o.min : Math.min(...d.map((c) => c[2])), hi = o.max != null ? o.max : Math.max(...d.map((c) => c[1]));
    const X0 = o.x - o.w / 2, Y0 = o.y + o.h / 2, step = o.w / n, bw = Math.min(34, step * 0.55);
    const px = (i) => X0 + step * (i + 0.5), py = (v) => Y0 - (o.h * (v - lo)) / (hi - lo || 1);
    const s = chartSvg(parent);
    svgEl(s, "line", { x1: X0, x2: X0 + o.w, y1: Y0, y2: Y0, stroke: "rgba(255,255,255,.35)", "stroke-width": 3 });
    const dur = o.dur || 1.8;
    d.forEach(([op, h, l, c], i) => {
      const up = c >= op, col = up ? "#e9dff0" : "#6d6575", g = svgEl(s, "g", {});
      svgEl(g, "line", { x1: px(i), x2: px(i), y1: py(h), y2: py(l), stroke: col, "stroke-width": 5, "stroke-linecap": "round" });
      svgEl(g, "rect", { x: px(i) - bw / 2, y: py(Math.max(op, c)), width: bw, height: Math.max(6, Math.abs(py(op) - py(c))), rx: 3,
        fill: up ? col : "#2a2630", stroke: col, "stroke-width": 4 });
      if (o.at != null) {
        hide(g);
        const t = o.at + (dur * i) / n;
        tl.fromTo(g, { autoAlpha: 0, y: 16 }, { autoAlpha: 1, y: 0, duration: 0.25, immediateRender: false }, t);
        if (i % 4 === 0) K.sfx(t, "click", 0.08);
      }
    });
    if (o.out != null) tl.to(s, { autoAlpha: 0, duration: 0.3 }, o.out);
    return { svg: s, x: px, y: py, at: o.at, dur };
  };
  K.highlight = function (parent, x, y, w, h, o) { // sweeps right -> left, behind text
    const e = K.el("div", "abs", parent);
    gsap.set(e, { left: x - w / 2, top: y - h / 2, width: w, height: h, background: o.color || "rgba(213,173,239,.55)", transformOrigin: "100% 50%", zIndex: 0 });
    hide(e);
    tl.fromTo(e, { scaleX: 0, autoAlpha: 1 }, { scaleX: 1, autoAlpha: 1, duration: o.dur || 0.5, ease: "power1.inOut", immediateRender: false }, o.at);
    K.sfx(o.at, "marker", 0.28);
    return e;
  };

  // ---------- effects ----------
  // Brand-coloured fire (lavender core -> deep plum), rising from baseY between cx +- w/2. Flicker, embers and glow are
  // all timeline tweens, so frames stay deterministic. o: { at, out, h, n (flame tongues), embers, sfx (default true) }
  K.fire = function (parent, cx, baseY, w, o = {}) {
    const h = o.h || w * 0.8, t0 = o.at, end = o.out != null ? o.out : (window.DURATION || 60) + 2;
    const box = K.el("div", "abs", parent);
    gsap.set(box, { left: cx - w / 2, top: baseY - h, width: w, height: h, pointerEvents: "none", mixBlendMode: "screen" });
    const glow = K.el("div", "abs", box);
    gsap.set(glow, { left: -w * 0.15, top: h * 0.25, width: w * 1.3, height: h * 0.95,
      background: "radial-gradient(ellipse at 50% 85%, rgba(213,173,239,.55) 0%, rgba(120,60,160,.35) 35%, rgba(56,16,77,0) 70%)" });
    const n = o.n || 9, flames = [];
    for (let i = 0; i < n; i++) {
      const r = rnd(i, 3) + 0.5, r2 = rnd(i, 9) + 0.5; // 0..1
      const fw = w * (0.16 + 0.12 * r), fh = h * (0.45 + 0.5 * r2);
      const f = K.el("div", "abs", box);
      gsap.set(f, { left: (w - fw) * Math.min(1, Math.max(0, (i + 0.5) / n + (rnd(i, 17) * 0.14))), top: h - fh, width: fw, height: fh,
        transformOrigin: "50% 100%", borderRadius: "50% 50% 45% 45% / 70% 70% 30% 30%", filter: "blur(5px)",
        background: "radial-gradient(ellipse at 50% 88%, #ffffff 0%, #f1e2fb 14%, #d5adef 34%, rgba(150,85,200,.75) 55%, rgba(56,16,77,0) 74%)" });
      flames.push(f);
      const d = 0.16 + 0.14 * r;
      tl.to(f, { scaleY: 0.62 + 0.55 * r2, scaleX: 0.8 + 0.3 * r, x: (r - 0.5) * 18, duration: d, yoyo: true,
        repeat: Math.max(1, Math.ceil((end - t0) / d)), ease: "sine.inOut" }, t0);
    }
    const ne = o.embers == null ? 14 : o.embers;
    for (let i = 0; i < ne; i++) {
      const r = rnd(i, 21) + 0.5, r2 = rnd(i, 33) + 0.5, d = 1.1 + 0.9 * r;
      const e = K.el("div", "abs", box);
      gsap.set(e, { left: w * (0.2 + 0.6 * r2), top: h * 0.85, width: 6 + 4 * r, height: 6 + 4 * r, borderRadius: "50%",
        background: "#ead6f7", boxShadow: "0 0 10px 3px rgba(213,173,239,.7)" });
      hide(e);
      tl.fromTo(e, { y: 0, x: 0, autoAlpha: 1 }, { y: -h * (0.7 + 0.5 * r), x: (r2 - 0.5) * 80, autoAlpha: 0, duration: d,
        repeat: Math.max(0, Math.ceil((end - t0 - r * d) / d)), ease: "power1.out", immediateRender: false }, t0 + r * d);
    }
    hide(box);
    tl.fromTo(box, { autoAlpha: 0, scaleY: 0.2, transformOrigin: "50% 100%" }, { autoAlpha: 1, scaleY: 1, duration: 0.6, ease: "power2.out", immediateRender: false }, t0);
    tl.to(glow, { opacity: 0.65, duration: 0.5, yoyo: true, repeat: Math.max(1, Math.ceil((end - t0) / 0.5)), ease: "sine.inOut" }, t0);
    if (o.out != null) tl.to(box, { autoAlpha: 0, duration: 0.4 }, o.out);
    if (o.sfx !== false) { K.sfx(t0, "fire", 0.7, 0); K.sfx(t0, "whoosh", 0.4); }
    return box;
  };

  // ---------- full-frame moments ----------
  K.headline = function (parts, o) { // parts: [{html, at}] appear word-group by word-group
    const h = document.getElementById("headline");
    const box = K.el("div", "", h);
    parts.forEach((p) => {
      const s = K.el("span", "w " + (p.kw ? "kw" : ""), box, p.html);
      if (p.at == null) return; // no `at`: on screen from frame 1 (complete first frame, 2026-10-11)
      hide(s);
      tl.fromTo(s, { y: 30, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.35, immediateRender: false }, p.at);
    });
    if (o && o.out != null) tl.to(box, { autoAlpha: 0, y: -24, duration: 0.3, ease: "power2.in" }, o.out);
    return box;
  };
  K.punch = function (html, t0, t1, o = {}) { // dims everything and shows one line big
    const dim = K.el("div", "abs", overlay);
    gsap.set(dim, { left: 0, top: 0, width: 1080, height: 1920, background: "rgba(8,7,11,.93)" });
    const e = K.el("div", "t head", overlay, html);
    gsap.set(e, { fontSize: o.size || 150, left: 540, top: 960, xPercent: -50, yPercent: -50 });
    hide(dim); hide(e);
    tl.fromTo(dim, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.12, immediateRender: false }, t0);
    tl.fromTo(e, { scale: 1.25, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.25, ease: "power4.out", immediateRender: false }, t0);
    tl.to([dim, e], { autoAlpha: 0, duration: 0.15 }, t1);
    // riser (2026-10-13): one per video at most, for the key reveal. The generated swell ends in its own low thud
    // on t0, so it replaces the hit. Without the option the punch sounds exactly as before.
    if (o.riser) K.sfx(t0 - 1.55, "riser", o.riser === true ? 0.4 : o.riser);
    else K.sfx(t0, "hit", 0.5);
  };
  K.wipe = function (t, o = {}) { // deep-purple wave rises from the bottom, holds, clears upward
    const e = K.el("div", "abs", overlay);
    gsap.set(e, { left: -60, width: 1200, top: 0, height: 2400, background: o.color || "#38104d", borderRadius: "48% 52% 0 0 / 7% 9% 0 0" });
    hide(e);
    tl.fromTo(e, { y: 2100, autoAlpha: 1 }, { y: -260, autoAlpha: 1, duration: 0.5, ease: "power3.inOut", immediateRender: false }, t);
    // clear fully: the wave is 2,400 px tall, so -2,200 left a 200 px band at the top of the frame (fixed 2026-10-13)
    if (!o.hold) tl.to(e, { y: -2500, duration: 0.5, ease: "power3.inOut" }, t + 0.5 + (o.pause || 0.1))
      .set(e, { autoAlpha: 0 }, t + 1.0 + (o.pause || 0.1));
    K.sfx(t, "whoosh", 0.4);
    return e;
  };

  // ---------- captions, grain, boil (driven per frame) ----------
  const capBox = document.getElementById("captions");
  let capShown = -2;
  function captions(t) {
    const caps = window.CAPTIONS || [];
    let idx = -1;
    for (let i = 0; i < caps.length; i++) if (t >= caps[i].start && t < caps[i].end) { idx = i; break; }
    if (t < K.captionsFrom || t > K.captionsTo) idx = -1;
    if (idx === capShown) return;
    capShown = idx;
    capBox.innerHTML = idx < 0 ? "" : '<span class="box">' + caps[idx].words.map((w) => { const h = numFix(w.w); return w.key ? `<span class="kw">${h}</span>` : h; }).join(" ") + "</span>";
  }
  // isolate numbers so "10%." does not render as ".10%" inside right-to-left text
  function numFix(w) { const m = w.match(/^(.*?)([+−-]?[\d.,]*\d%?)(.*)$/); return m ? `${m[1]}<bdi class="num">${m[2]}</bdi>${m[3]}` : w; }
  K.captionsFrom = 0; K.captionsTo = 1e9;
  const grain = document.getElementById("grain");
  const turb = document.querySelectorAll("feTurbulence.boil");

  K.seek = function (t) {
    const q = Math.floor(t * K.fps + 1e-6) / K.fps;
    // a seek to exactly 0 skips the zero-duration sets placed at 0 (hide/initial states), so the first two
    // frames showed later scenes (found 2026-10-11 in every delivered Reel); start a hair past 0 instead
    // K.camSmooth (Ahmed 2026-10-11, new videos via the template): the camera follows the exact time while
    // everything else stays on twos, so pans and pushes glide; engine/render.py then captures at 24 fps.
    let cam = null;
    if (K.camSmooth) {
      tl.seek(Math.max(t, 1e-4), false);
      cam = { x: gsap.getProperty(world, "x"), y: gsap.getProperty(world, "y"), scale: gsap.getProperty(world, "scaleX") };
    }
    tl.seek(Math.max(q, 1e-4), false);
    if (cam) gsap.set(world, cam);
    const step = Math.floor(q * K.fps);
    turb.forEach((f) => f.setAttribute("seed", String((Math.floor(q * 8) % 40) + 1)));
    if (grain) grain.style.transform = `translate(${(step * 37) % 40 - 20}px, ${(step * 53) % 40 - 20}px)`;
    captions(t);
  };

  // procedural grain tile (no external texture needed)
  (function makeGrain() {
    if (!grain) return;
    const c = document.createElement("canvas"); c.width = c.height = 256;
    const g = c.getContext("2d"), img = g.createImageData(256, 256);
    let s = 1234567;
    for (let i = 0; i < img.data.length; i += 4) {
      s = (s * 16807) % 2147483647; const v = 128 + ((s / 2147483647) - 0.5) * 255;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    grain.style.backgroundImage = `url(${c.toDataURL()})`;
  })();
})();
