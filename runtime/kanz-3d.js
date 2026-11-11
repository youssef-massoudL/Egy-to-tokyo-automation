/* Kanz 3D (2026-10-14): three CSS-3D components picked by Ahmed from projects/_3d-demo
 * (techniques from freefrontend.com/css-3d-examples, rebuilt as seekable GSAP tweens). Load after kanz-look.js.
 * Rejected in the same review, do not rebuild: coin toss, isometric 3D bars, depth camera (layers at depth).
 *
 *   K.flip(parent, front, back, {x, y, w, h, at, flip, back: "lav"|"paper", size})
 *       paper card that turns over on a word: myth -> fact, question -> answer, before -> after.
 *       front/back: {label, text} or an HTML string.
 *   K.browser(parent, src, {x, y, w, at, url, source, sway, out})
 *       GENUINE screenshot in a browser frame that rises from lying flat and sways slowly in 3D.
 *       K.pageOval(win, x, y, rx, ry, {at}) / K.pageMark(win, x, y, w, h, {at}) draw on the tilted page
 *       in the screenshot's own pixels. url = the address bar, source = "site · capture date" line.
 *   K.fold(parent, {x, y, w, h, cover, top, bottom, at, open, torn})
 *       folded paper note (torn zig-zag bottom edge) that opens toward the camera on a word.
 */
(function () {
  const K = window.K, tl = K.tl;
  const INK = "#141217", LAV = "#d5adef", PAPER = "#ece8ee";
  const hide = (e) => tl.set(e, { autoAlpha: 0 }, 0);
  const loaded = (img, fn) => { if (img.complete && img.naturalWidth) fn(); else img.addEventListener("load", fn, { once: true }); };

  const css = document.createElement("style");
  css.textContent = `
.k3face{position:absolute;left:0;top:0;width:100%;height:100%;backface-visibility:hidden;-webkit-backface-visibility:hidden;
  display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;box-sizing:border-box;padding:24px}
.k3label{font-size:38px;color:#6b6570;margin-bottom:22px}
.k3big{font-family:var(--head);font-weight:700;color:${INK};line-height:1.15}
.k3bar{height:46px;display:flex;align-items:center;gap:10px;padding:0 18px;direction:ltr;box-sizing:border-box}
.k3bar i{width:13px;height:13px;border-radius:50%}
.k3bar span{margin-left:24px;flex:1;background:#1b1920;border-radius:8px;padding:5px 14px;font:24px var(--body);color:#bdb6c4}`;
  document.head.appendChild(css);

  // a 3D stage: perspective on the wrapper (centred on x, y), preserve-3d on the returned inner element
  function stage3d(parent, x, y, w, h, p) {
    const wrap = K.el("div", "abs", parent);
    gsap.set(wrap, { left: x - w / 2, top: y - h / 2, width: w, height: h, perspective: p || 1600 });
    const inner = K.el("div", "abs", wrap);
    gsap.set(inner, { left: 0, top: 0, width: w, height: h, transformStyle: "preserve-3d" });
    inner._wrap = wrap;
    return inner;
  }
  const content = (c, size, labelColor) => typeof c === "string" ? c :
    (c.label ? `<div class="k3label"${labelColor ? ` style="color:${labelColor}"` : ""}>${c.label}</div>` : "") +
    `<div class="k3big" style="font-size:${c.size || size}px">${c.text}</div>`;
  const enter = (e, at) => { // the K.card entrance: rises with a slight turn, paper sound
    hide(e);
    tl.fromTo(e, { y: 90, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.5, ease: "power3.out", immediateRender: false }, at);
    K.sfx(at, "paper", 0.5);
  };

  // ---------- card flip ----------
  K.flip = function (parent, front, back, o) {
    const w = o.w || 640, h = o.h || 560, size = o.size || 92;
    const card = stage3d(parent, o.x, o.y, w, h, 1600);
    K.el("div", "card k3face", card, content(front, size));
    const b = K.el("div", "card k3face", card, content(back, size, INK));
    gsap.set(b, { rotationY: 180, background: o.back === "paper" ? PAPER : LAV });
    if (o.rot) gsap.set(card._wrap, { rotation: o.rot });
    if (o.at != null) enter(card, o.at);
    if (o.flip != null) {
      tl.to(card, { rotationY: -180, duration: 0.8, ease: "back.out(1.3)" }, o.flip);
      tl.to(card, { scale: 1.08, duration: 0.4, ease: "power2.out", yoyo: true, repeat: 1 }, o.flip);
      K.sfx(o.flip, "whoosh", 0.35); K.sfx(o.flip + 0.3, "paper", 0.45);
    }
    if (o.out != null) tl.to(card, { autoAlpha: 0, duration: 0.3 }, o.out);
    return card;
  };

  // ---------- tilted browser screenshot ----------
  K.browser = function (parent, src, o) {
    const W = o.w || 900, BAR = 46;
    const win = stage3d(parent, o.x, o.y, W, o.h || 650, 1500);
    const frame = K.el("div", "abs", win);
    gsap.set(frame, { left: 0, top: 0, width: W, borderRadius: 14, overflow: "hidden", background: "#2a2730",
      boxShadow: "0 40px 80px rgba(0,0,0,.6), 0 0 0 2px rgba(255,255,255,.12)" });
    K.el("div", "k3bar", frame, '<i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i>' +
      `<span>${o.url || ""}</span>`);
    const page = K.el("div", "", frame);
    page.style.cssText = `position:relative;width:${W}px`;
    const im = K.el("img", "", page); im.src = src;
    im.style.cssText = `display:block;width:${W}px`;
    win._page = page; win._k = 0; win._pending = [];
    let s;
    if (o.source) s = K.tag(parent, o.source, { x: o.x, y: o.y + (o.h || 650) / 2 + 60, size: 30, at: o.at == null ? null : o.at + 0.8, sfx: false });
    loaded(im, () => { // centre the frame on its real height once the screenshot's size is known
      win._k = W / im.naturalWidth;
      const H = BAR + im.naturalHeight * win._k;
      gsap.set([win._wrap, win], { height: H }); gsap.set(win._wrap, { top: o.y - H / 2 });
      if (s) gsap.set(s, { top: o.y + H / 2 + 60 });
      win._pending.splice(0).forEach((f) => f());
    });
    const rest = { rotationX: 10, rotationY: -16 };
    if (o.at != null) {
      hide(win);
      tl.fromTo(win, { rotationX: 62, rotationY: 0, y: 180, autoAlpha: 0 }, { ...rest, y: 0, autoAlpha: 1, duration: 1.0, ease: "power3.out", immediateRender: false }, o.at);
      K.sfx(o.at, "whoosh", 0.3);
    } else gsap.set(win, rest);
    if (o.sway !== false) {
      const t0 = (o.at || 0) + 1.0, dur = o.sway || (o.out != null ? Math.max(1.5, o.out - t0) : 3.6);
      tl.to(win, { rotationY: 9, rotationX: 4, duration: dur, ease: "sine.inOut" }, t0);
    }
    if (o.out != null) tl.to(s ? [win, s] : win, { autoAlpha: 0, duration: 0.3 }, o.out);
    return win;
  };
  const onPage = (win, fn) => (win._k ? fn() : win._pending.push(fn));
  K.pageOval = function (win, x, y, rx, ry, o = {}) { // screenshot pixels
    onPage(win, () => { const k = win._k; K.oval(win._page, x * k, y * k, rx * k, ry * k, { color: LAV, width: 8, ...o }); });
  };
  K.pageMark = function (win, x, y, w, h, o = {}) { // highlighter sweeping right -> left behind a phrase
    onPage(win, () => {
      const k = win._k, m = K.el("div", "", win._page);
      gsap.set(m, { position: "absolute", left: x * k, top: y * k, width: w * k, height: h * k, background: LAV,
        mixBlendMode: "multiply", opacity: 0.55, transformOrigin: "100% 50%", scaleX: 0 });
      tl.to(m, { scaleX: 1, duration: o.dur || 0.55, ease: "power1.inOut" }, o.at);
      K.sfx(o.at, "marker", 0.3);
    });
  };

  // ---------- folded note ----------
  K.fold = function (parent, o) {
    const W = o.w || 620, Hh = (o.h || 660) / 2, size = o.size || 110, zig = 22;
    const note = stage3d(parent, o.x, o.y, W, Hh * 2, 1700);
    const lowerWrap = K.el("div", "abs", note); // drop shadow on the wrapper, so the zig-zag mask does not clip it
    gsap.set(lowerWrap, { left: 0, top: Hh, width: W, height: Hh + (o.torn === false ? 0 : zig), filter: "drop-shadow(0 26px 30px rgba(0,0,0,.5))" });
    const lower = K.el("div", "k3face", lowerWrap, content(o.bottom, size));
    gsap.set(lower, { background: PAPER, backfaceVisibility: "visible", borderRadius: o.torn === false ? "0 0 6px 6px" : 0 });
    if (o.torn !== false) {
      const m = "conic-gradient(from -45deg at bottom, #0000, #000 1deg 89deg, #0000 90deg) 50% / 44px 100%";
      gsap.set(lower, { paddingBottom: zig, webkitMask: m, mask: m });
    }
    const upper = K.el("div", "abs", note);
    gsap.set(upper, { left: 0, top: 0, width: W, height: Hh, transformStyle: "preserve-3d", transformOrigin: "50% 100%" });
    const inside = K.el("div", "k3face", upper, content(o.top, size));
    gsap.set(inside, { background: PAPER, borderRadius: "6px 6px 0 0", boxShadow: "inset 0 -12px 18px -12px rgba(0,0,0,.25)" });
    const shade = K.el("div", "k3face", upper);
    gsap.set(shade, { background: "#000", opacity: 0.55, borderRadius: "6px 6px 0 0" });
    const cover = K.el("div", "k3face", upper, content(o.cover || { text: "" }, 80));
    gsap.set(cover, { rotationX: 180, background: PAPER, borderRadius: "0 0 6px 6px" });
    if (o.at != null) enter(note, o.at);
    tl.set(upper, { rotationX: -179.5 }, 0);
    if (o.open != null) {
      tl.to(upper, { rotationX: 0, duration: 1.1, ease: "power2.inOut" }, o.open);
      tl.to(shade, { opacity: 0, duration: 1.1, ease: "power2.in" }, o.open);
      K.sfx(o.open, "paper", 0.55);
    }
    if (o.out != null) tl.to(note, { autoAlpha: 0, duration: 0.3 }, o.out);
    return note;
  };
})();
