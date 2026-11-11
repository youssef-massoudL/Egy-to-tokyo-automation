/* Kanz pace (2026-10-13): opt-in pacing layer, loaded after kanz-look.js. K.pace() turns it on.
 *
 * From the short-form pacing study (Kanz repo: reports/shorts-pacing-study-2026-10-13/FINDINGS.md):
 * conversion.doc, Vox Shorts and 0x100x never show an empty frame, never fully stop moving, change scene
 * inside the voice's breath, and carry one object from beat to beat. Finished projects do not load this
 * file, so their re-renders are unchanged. Guide: docs/PACE.md.
 *
 *   K.pace({drift, bed})        24 fps motion (grain + boil stay stepped), smooth camera, mix 2, room-tone bed,
 *                               camera drift between moves, 0.5 s moves
 *   K.go(tWord, id, o)          move to a board inside the pause before tWord; returns {start, arrive, lead}:
 *                               put the board's first element `at: g.lead` so it lands with the camera
 *   K.frame(t, id, o)           reframe on the same board (start close on the first object, then pull out)
 *   K.finish()                  call last: adds the drift between camera moves
 *   K.img(..., {enter: "fly"})  hero entrance from oversized (1.9x, from below) settling in ~0.85 s
 *   K.settle(el, t, o)          an element already on screen settles from oversized (the hook hero, frame 1)
 *   K.carry(el, toId, t, o)     move an object from its board to a spot on another board during a camera move
 *   K.dim(els, t, op)           dim to `op` (default 0.3) instead of clearing: never an empty board
 *   K.snap(t, f, hold)          one-frame snap zoom on an emphasis word, snaps back after `hold`
 *   K.pointer(board)            one lavender ring that hops between targets: p.to(t, x, y, w, h), p.out(t)
 */
(function () {
  const K = window.K, tl = K.tl;
  const stage = document.getElementById("stage"), world = document.getElementById("world");
  const hide = (e) => tl.set(e, { autoAlpha: 0 }, 0);
  K.PACE = false;
  const moves = []; // {t, end, id, o, to}

  K.pace = function (o = {}) {
    K.PACE = true;
    K.camSmooth = true;
    K.fps = 24; // every frame moves; grain and boil keep their own slower step (see seek below)
    K.mix = 2;
    K.bed = o.bed === undefined ? "room" : o.bed; // engine/render.py mixes a quiet room tone under everything
    K.driftRate = o.drift == null ? 0.02 : o.drift; // scale per second between moves (0x100x: 2-3 %/s)
    K.driftCap = o.driftCap || 0.07; // more crops objects at the board edges (review 2026-10-13)
    K.driftSide = o.driftSide == null ? 8 : o.driftSide; // board px per second, alternating direction
    // snap zooms act on a wrapper so they never fight the camera tweens on #world
    if (!document.getElementById("camwrap")) {
      // K.world() inserts the paper layer before #world, which is about to move into the wrapper: make it now
      if (!document.getElementById("paperworld")) {
        const bg = document.createElement("div"); bg.id = "paperworld"; stage.insertBefore(bg, world);
        tl.set(bg, { autoAlpha: 0 }, 0);
      }
      const w = document.createElement("div");
      w.id = "camwrap";
      w.style.cssText = "position:absolute;inset:0;z-index:1;transform-origin:540px " + K.view.y + "px";
      stage.insertBefore(w, world);
      w.appendChild(world);
    }
  };

  // ---------- frame clock: motion at 24 fps, grain at 12, boil at 8 (hand-made texture stays stepped) ----------
  const seek1 = K.seek;
  const grain = document.getElementById("grain");
  K.seek = function (t) {
    seek1(t);
    if (!K.PACE || !grain) return;
    const step = Math.floor(t * 12 + 1e-6);
    grain.style.transform = `translate(${(step * 37) % 40 - 20}px, ${(step * 53) % 40 - 20}px)`;
  };

  // ---------- camera ----------
  const cam0 = K.cam, push0 = K.push;
  K.cam = function (t, id, o = {}) {
    if (!K.PACE) return cam0(t, id, o);
    const dur = t <= 0 ? 0 : o.dur || 0.5;
    cam0(t, id, { ...o, dur: dur || 0.5 });
    moves.push({ t, end: t + dur, id, o, to: K._cam });
  };
  K.push = function (t, id, scale, dur = 2.5, o = {}) {
    push0(t, id, scale, dur, o);
    if (K.PACE) moves.push({ t, end: t + dur, id, o: { ...o, scale }, to: K._cam });
  };
  K.frame = function (t, id, o = {}) { return K.cam(t, id, { sfx: false, dur: 0.55, ...o }); };

  // start of the pause before the word at tWord (end of the previous spoken word)
  K.pauseBefore = function (tWord) {
    let e = 0;
    (window.TOKENS || []).forEach((tk) => { if (tk.end <= tWord - 0.01 && tk.end > e) e = tk.end; });
    return e;
  };
  K.go = function (tWord, id, o = {}) {
    const dur = o.dur || 0.5;
    let start = Math.max(K.pauseBefore(tWord) + 0.02, tWord - 0.75);
    start = Math.min(start, tWord - 0.3); // land no later than ~0.2 s after the word starts
    K.cam(start, id, { ...o, dur });
    return { start, arrive: start + dur, lead: start + 0.15, word: tWord };
  };

  K.finish = function () {
    if (!K.PACE) return;
    const end = K.duration;
    moves.sort((a, b) => a.t - b.t);
    moves.forEach((m, i) => {
      const next = moves[i + 1] ? moves[i + 1].t : end;
      const gap = next - m.end;
      if (gap < 0.3) return;
      const base = m.to.scale, s = base * (1 + Math.min(K.driftCap, K.driftRate * gap));
      const side = (i % 2 ? 1 : -1) * K.driftSide * gap;
      const to = K.camAt(m.id, { ...m.o, scale: s, dx: (m.o.dx || 0) + side });
      tl.to(world, { ...to, duration: gap, ease: "none" }, m.end);
    });
  };

  // ---------- entrances ----------
  const img1 = K.img;
  K.img = function (parent, src, o = {}) {
    if (o.enter !== "fly" || o.at == null) return img1(parent, src, o);
    const e = img1(parent, src, { ...o, at: null });
    hide(e);
    const fs = o.fromScale || 1.9;
    tl.fromTo(e, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.18, ease: "none", immediateRender: false }, o.at);
    tl.fromTo(e, { scale: fs, x: o.fromX || 0, y: o.fromY == null ? 170 : o.fromY },
      { scale: 1, x: 0, y: 0, duration: o.dur || 0.85, ease: "power3.out", immediateRender: false }, o.at);
    K.sfx(o.at, K.cue(o.sfx, "whoosh"), o.gain || 0.22);
    return e;
  };
  K.settle = function (el, t, o = {}) {
    tl.fromTo(el, { scale: o.fromScale || 1.5, y: o.fromY == null ? 80 : o.fromY },
      { scale: 1, y: 0, duration: o.dur || 1.1, ease: "power3.out", immediateRender: false }, Math.max(t, 1e-4));
  };

  // ---------- continuity ----------
  const boardOf = (el) => { for (const id in K.boards) if (K.boards[id].el.contains(el)) return id; return null; };
  K.carry = function (el, toId, t, o = {}) {
    const from = K.boards[boardOf(el)], to = K.boards[toId];
    const left = parseFloat(el.style.left), top = parseFloat(el.style.top);
    const w0 = parseFloat(el.style.width);
    const dx = to.x + o.x - (from.x + left), dy = to.y + o.y - (from.y + top);
    tl.set(from.el, { zIndex: 6 }, t);
    const v = { x: dx, y: dy, scale: o.w ? o.w / w0 : 1, duration: o.dur || 0.55, ease: "power2.inOut" };
    if (o.rot != null) v.rotation = o.rot;
    if (o.opacity != null) v.opacity = o.opacity;
    tl.to(el, v, t);
    return el;
  };
  K.dim = function (els, t, op = 0.3, dur = 0.4) {
    tl.to([].concat(els), { opacity: op, duration: dur, ease: "power2.inOut" }, t);
  };

  // ---------- emphasis ----------
  K.snap = function (t, f = 1.3, hold = 0.7) {
    const w = document.getElementById("camwrap");
    if (!w) return;
    tl.set(w, { scale: f }, t);
    tl.set(w, { scale: 1 }, t + hold);
    K.sfx(t, "click", 0.25);
  };
  K.pointer = function (parent) {
    const r = K.el("div", "abs kpointer", parent);
    gsap.set(r, { width: 100, height: 100, border: "7px solid #d5adef", borderRadius: "50%", boxSizing: "border-box",
      filter: "url(#boil)", xPercent: -50, yPercent: -50, zIndex: 9 });
    hide(r);
    let shown = false;
    return {
      el: r,
      to(t, x, y, w, h) {
        if (!shown) {
          shown = true;
          gsap.set(r, { left: x, top: y, width: w, height: h || w });
          tl.fromTo(r, { autoAlpha: 0, scale: 1.4 }, { autoAlpha: 1, scale: 1, duration: 0.3, ease: "power3.out", immediateRender: false }, t);
        } else {
          tl.to(r, { left: x, top: y, width: w, height: h || w, duration: 0.28, ease: "power2.inOut" }, t);
        }
        K.sfx(t, "marker", 0.2);
        return this;
      },
      out(t) { tl.to(r, { autoAlpha: 0, duration: 0.25 }, t); return this; },
    };
  };
})();
