/* Youssef Lab (2026-10-16): registry for draft components, styles and animations. Everything registered here is an
 * unapproved draft until Ahmed approves it; it is not used in final Kanz output until then.
 * Load after kanz-look.js / kanz-pace.js / kanz-3d.js.
 *
 *   K.lab.add("name", fn)      register a draft component: fn(parent, opts) -> element
 *   K.lab.use("name", parent, opts)   build it in a scene
 *   K.lab.style("name", css)   inject a named style block once; returns the <style> element
 *   K.lab.has("name")          true when a component is registered
 *
 * Document each addition in docs/YOUSSEF-LAB.md and library/youssef/manifest.json.
 */
(function () {
  const K = window.K;
  const reg = {}, styles = {};
  K.lab = {
    add(name, fn) { reg[name] = fn; return fn; },
    has: (name) => !!reg[name],
    use(name, parent, o = {}) {
      if (!reg[name]) throw new Error("Youssef Lab: component not registered: " + name);
      return reg[name](parent, o);
    },
    style(name, css) {
      if (styles[name]) return styles[name];
      const s = document.createElement("style");
      s.dataset.lab = name;
      s.textContent = css;
      document.head.appendChild(s);
      return (styles[name] = s);
    },
  };

  // ---- drafts (unapproved, Youssef 2026-10-16) ----
  // irisDive: a lavender-ringed iris swells from the centre, swallows the frame and fades into the next board
  // (storyboard scene 2 -> 3). Seekable tweens only. o: { at (start of the dive), dur (to full frame), src }
  K.lab.add("irisDive", function (parent, o = {}) {
    const ov = document.getElementById("overlay"), tl = K.tl, t0 = o.at, d = o.dur || 0.6;
    const e = K.el("img", "abs", ov);
    e.src = o.src || "../../library/youssef/objects/youssef-iris-v01.svg";
    gsap.set(e, { left: 540, top: 960, width: 900, height: 900, xPercent: -50, yPercent: -50, autoAlpha: 0, pointerEvents: "none" });
    tl.fromTo(e, { scale: 0.05, autoAlpha: 0, rotation: -25 }, { scale: 2.6, autoAlpha: 1, rotation: 0, duration: d, ease: "power3.in", immediateRender: false }, t0);
    tl.to(e, { scale: 9, duration: 0.45, ease: "power2.in" }, t0 + d);
    tl.to(e, { autoAlpha: 0, duration: 0.3, ease: "none" }, t0 + d + 0.25);
    K.sfx(t0, "whoosh", 0.4);
    return e;
  });

  // eye: the hook hero, a painted neutral eye with a candlestick chart in the pupil (SVG, seekable, cheap; the three.js
  // version in library/youssef/3d/eye/ is the 3D study of the same drawing). o: { x, y, w, at, blink (t), dilate (t), build (t of first candle) }
  K.lab.add("eye", function (parent, o = {}) {
    const NS = "http://www.w3.org/2000/svg", tl = K.tl, A = 1.1, N = 40;
    const w = o.w || 600, box = K.el("div", "abs", parent);
    gsap.set(box, { left: o.x, top: o.y, width: w, height: w * 0.9, xPercent: -50, yPercent: -50 });
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "-1.6 -1.35 3.2 2.7"); svg.setAttribute("width", w); svg.setAttribute("height", w * 2.7 / 3.2); svg.style.overflow = "visible";
    svg.style.position = "absolute"; svg.style.left = "0"; svg.style.top = "0"; box.appendChild(svg);
    const mk = (tag, at, par) => { const e = document.createElementNS(NS, tag); Object.entries(at || {}).forEach(([k, v]) => e.setAttribute(k, v)); (par || svg).appendChild(e); return e; };
    mk("defs", {}).innerHTML = '<radialGradient id="eyeIris"><stop offset="0" stop-color="#d8d4de"/><stop offset=".55" stop-color="#a8a2b3"/><stop offset="1" stop-color="#58525f"/></radialGradient>' +
      '<clipPath id="eyeClip"><path id="eyeClipPath"/></clipPath><clipPath id="pupilClip"><circle r=".4"/></clipPath>';
    const cx = (x) => Math.max(0, 1 - (x / A) * (x / A));
    const upY = (x, b) => -((0.56 - 0.7 * b) * Math.pow(cx(x), 0.8)), loY = (x, b) => (0.42 - 0.28 * b) * Math.pow(cx(x), 0.9); // SVG y is down
    const xs = Array.from({ length: N + 1 }, (_, i) => -A + (2 * A * i) / N);
    const line = (f, b) => "M" + xs.map((x) => x.toFixed(3) + " " + f(x, b).toFixed(3)).join(" L");
    const almond = (b) => line(upY, b) + " L" + xs.slice().reverse().map((x) => x.toFixed(3) + " " + loY(x, b).toFixed(3)).join(" L") + " Z";
    mk("path", { d: "M-1.2 -0.8 Q0 -1.1 1.2 -0.8", fill: "none", stroke: "#6c6676", "stroke-width": ".17", "stroke-linecap": "round" });
    const scl = mk("path", { fill: "#dad7de", stroke: "none" });
    const inner = mk("g", { "clip-path": "url(#eyeClip)" });
    const gaze = mk("g", {}, inner);
    mk("circle", { r: ".62", fill: "url(#eyeIris)" }, gaze);
    for (let i = 0; i < 28; i++) { const a = (i / 28) * 6.283; mk("line", { x1: Math.cos(a) * 0.46, y1: Math.sin(a) * 0.46, x2: Math.cos(a) * 0.58, y2: Math.sin(a) * 0.58, stroke: i % 3 ? "#3a3441" : "#ffffff", "stroke-opacity": i % 3 ? ".5" : ".35", "stroke-width": ".014", "stroke-linecap": "round" }, gaze); }
    mk("circle", { r: ".6", fill: "none", stroke: "#0a080d", "stroke-width": ".04" }, gaze);
    mk("circle", { r: ".47", fill: "none", stroke: "#d5adef", "stroke-width": ".03" }, gaze);
    const pup = mk("g", {}, gaze), pbg = mk("circle", { r: ".4", fill: "#08060b" }, pup), candles = mk("g", { "clip-path": "url(#pupilClip)" }, pup);
    mk("circle", { r: ".4", fill: "none", stroke: "#0a080d", "stroke-width": ".02" }, pup);
    mk("circle", { cx: -0.2, cy: -0.2, r: ".055", fill: "#fff" }, gaze);
    const shade = mk("path", { fill: "#6c6676", "fill-opacity": ".38" }, inner);
    const upL = mk("path", { fill: "none", stroke: "#0a080d", "stroke-width": ".065", "stroke-linecap": "round" }), loL = mk("path", { fill: "none", stroke: "#0a080d", "stroke-width": ".03", "stroke-linecap": "round" });
    const lashes = Array.from({ length: 9 }, () => mk("line", { stroke: "#120d18", "stroke-width": ".05", "stroke-linecap": "round" }));
    const series = []; let p = 100; [3, 5, -1, 6, 4, 7, -2, 5, 8, -6, -9, -7, -11, -8].forEach((m, i) => { const o2 = p; p += m; series.push({ o: o2, c: p, h: Math.max(o2, p) + 1.5 + (i * 7 % 3), l: Math.min(o2, p) - 1.5 - (i * 5 % 3) }); });
    const st = { b: 0, t: 0, dil: 1 };
    const draw = () => {
      const b = st.b, d = almond(b);
      scl.setAttribute("d", d); document.getElementById("eyeClipPath").setAttribute("d", d);
      upL.setAttribute("d", line(upY, b)); loL.setAttribute("d", line(loY, b));
      shade.setAttribute("d", line(upY, b) + " L" + xs.slice().reverse().map((x) => x.toFixed(3) + " " + (upY(x, b) + 0.2 * Math.pow(cx(x), 0.7) * (1 - 0.6 * b)).toFixed(3)).join(" L") + " Z");
      lashes.forEach((l, i) => { const f = i / 8, x = -0.7 + f * 1.4, y = upY(x, b), ang = (f - 0.5) * 0.9 + b * 0.5, len = (0.13 + 0.05 * (i % 2)) * (1 - 0.4 * b);
        l.setAttribute("x1", x); l.setAttribute("y1", y); l.setAttribute("x2", x + Math.sin(ang) * len); l.setAttribute("y2", y - Math.cos(ang) * len); });
      pup.setAttribute("transform", `scale(${st.dil})`);
      let h = "";
      const cw = 0.8 / (series.length + 1.2), lo = 84, hi = 128, Y = (v) => 0.36 - ((v - lo) / (hi - lo)) * 0.72;
      series.forEach((s, i) => {
        const k = Math.min(1, Math.max(0, (st.t - (-0.9 + i * 0.3)) / 0.28)); if (k <= 0) return;
        const X = -0.4 + (i + 0.9) * cw, col = s.c >= s.o ? "#d5adef" : "#e5534b", c = s.o + (s.c - s.o) * k, hh = s.o + (s.h - s.o) * k, ll = s.o + (s.l - s.o) * k;
        h += `<line x1="${X}" x2="${X}" y1="${Y(hh)}" y2="${Y(ll)}" stroke="${col}" stroke-width=".012" stroke-linecap="round"/>` +
             `<rect x="${X - cw * 0.28}" width="${cw * 0.56}" y="${Y(Math.max(s.o, c))}" height="${Math.max(0.012, Math.abs(Y(Math.min(s.o, c)) - Y(Math.max(s.o, c))))}" fill="${col}"/>`;
      });
      candles.innerHTML = h;
    };
    draw();
    const t0 = o.at || 0, dur = 6;
    tl.to(st, { t: dur, duration: dur, ease: "none", onUpdate: draw }, o.build != null ? o.build : 0);
    tl.set(st, { t: 0 }, 0);
    if (o.blink != null) {
      tl.to(st, { b: 1, duration: 0.16, ease: "power2.inOut", onUpdate: draw }, o.blink);
      tl.to(st, { b: 0, duration: 0.18, ease: "power2.inOut", onUpdate: draw }, o.blink + 0.16);
    }
    if (o.dilate != null) {
      tl.to(st, { dil: 1.12, duration: 0.3, ease: "power2.out", onUpdate: draw }, o.dilate);
      tl.to(st, { dil: 1, duration: 0.9, ease: "power2.inOut", onUpdate: draw }, o.dilate + 0.3);
    }
    tl.to(gaze, { x: 0.07, duration: 0.12, ease: "power2.out" }, (o.blink || 3) - 1.2);
    return box;
  });
})();
