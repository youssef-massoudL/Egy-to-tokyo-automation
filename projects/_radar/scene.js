/* Kanz Market Radar: the scene shared by every edition (market-radar-daily = Cairo -> Tokyo, market-radar-europe-us = Europe -> New York).
 * Title card, map flight stop by stop with pin + card per index, live counters, ranking, end card. The edition's route is in its config.js
 * (window.RADAR), the day's numbers in its data.js (window.DAY). Lavender = up, red = loss, grey = market closed.
 * 60 fps, camera tweened in map space (lon / lat / log zoom). Map: NASA Blue Marble graded by _radar/make_photo.py, borders from Natural Earth.
 * Silent Reel: the source video's music + SFX (_radar/audio.m4a) is muxed on by _radar/run_edition.py. */
const tl = K.tl;
K.look();
K.camSmooth = false; // the camera is set from map space every frame (applyCam), so no separate camera pass
K.fps = 60;
K.duration = 21.7;

const D = window.DAY;
const stage = document.getElementById("stage");
const world = document.getElementById("world");
const overlay = document.getElementById("overlay");
const NS = "http://www.w3.org/2000/svg";
const C = window.RADAR, KICK = C.kick, TITLE = C.title;
const SY = 745; // screen y of the camera's focus at a stop: the middle of the room between the header and the bottom block
const LAV = "#d5adef", LOSS = "#e5534b", GREY = "#8b8494";

// hazard, as in the source video: a striped wipe sweeps across on the cut from title card to map (1.37), and 38 px bands sit top and bottom with
// stripes scrolling ~29 px/s in opposite directions. Kanz colours: lavender and red stripes. Over the title card, under the end card.
const wipe = K.el("div", "hzw", stage);
gsap.set(wipe, { skewX: 17.5, x: -1900 });
tl.fromTo(wipe, { x: -1900 }, { x: 1750, duration: 0.42, ease: "power1.inOut", immediateRender: false }, 1.16);
const bands = ["top", "bot"].map((w) => K.el("div", "hz " + w, stage));
tl.fromTo(bands[0], { backgroundPositionX: 0 }, { backgroundPositionX: -620, duration: 21.7, ease: "none" }, 0);
tl.fromTo(bands[1], { backgroundPositionX: 0 }, { backgroundPositionX: 620, duration: 21.7, ease: "none" }, 0);
tl.set(bands, { autoAlpha: 0 }, 19.63);

// ---------------------------------------------------------------- the day's data
const MINUS = "−";
const fmtPct = (p) => (p < 0 ? MINUS : "+") + Math.abs(p).toFixed(2) + "%";
const dirOf = (m) => (m.closed ? "cl" : m.pct < 0 ? "dn" : "up");
const MK = D.mk;
const STOPS = C.stops; // order = camera order
const dirs = STOPS.map((s) => dirOf(MK[s.k]));
const nUp = dirs.filter((d) => d === "up").length, nDn = dirs.filter((d) => d === "dn").length;
// country colour: red only when every market there fell, grey when shut, lavender otherwise (a country with one of each stays lavender)
const COUNTRY = C.country;
const cdir = (id) => { const d = COUNTRY[id].map((k) => dirOf(MK[k])); return d.every((x) => x === "dn") ? "dn" : d.every((x) => x === "cl") ? "cl" : "up"; };
const STROKE = { up: "#ecd6ff", dn: "#ff8f87", cl: "#a9a3b2" };

// ---------------------------------------------------------------- map world (Mercator, origin M.LON0 / M.LAT0; the Cairo -> Tokyo map predates those fields)
const M = window.MAP;
const S0 = M.S0, D2R = Math.PI / 180;
const mer = (lat) => Math.log(Math.tan(Math.PI / 4 + (lat * D2R) / 2));
const LON0 = M.LON0 == null ? 15 : M.LON0, LAT0 = M.LAT0 == null ? 52 : M.LAT0;
const P = (lon, lat) => [S0 * (lon - LON0) * D2R, S0 * (mer(LAT0) - mer(lat))];

const svg = document.createElementNS(NS, "svg");
svg.setAttribute("width", M.W); svg.setAttribute("height", M.H);
svg.setAttribute("viewBox", `0 0 ${M.W} ${M.H}`);
svg.style.cssText = "position:absolute;left:0;top:0;overflow:visible";
world.appendChild(svg);
const gBase = document.createElementNS(NS, "g"), gHi = document.createElementNS(NS, "g");
svg.append(gBase, gHi);
const mkPath = (d, attrs) => { const p = document.createElementNS(NS, "path"); p.setAttribute("d", d); for (const k in attrs) p.setAttribute(k, attrs[k]); return p; };
const mkImage = (name, x, y, w, h) => {
  const im = document.createElementNS(NS, "image");
  const href = "assets/photo/" + name + ".jpg";
  im.setAttribute("href", href); im.setAttribute("x", x); im.setAttribute("y", y); im.setAttribute("width", w); im.setAttribute("height", h);
  im.setAttribute("preserveAspectRatio", "none");
  im.setAttribute("decoding", "sync"); // without this a frame can be captured with part of the big map still undecoded (a hole in the map)
  const pre = document.createElement("img"); pre.src = href; pre.style.display = "none"; document.body.appendChild(pre); // render.py waits for document.images
  return im;
};
gBase.appendChild(mkImage("base", 0, 0, M.W, M.H));
M.countries.forEach((c) => gBase.appendChild(mkPath(c.d, { fill: "none", stroke: "rgba(255,255,255,.17)", "stroke-width": 1, "vector-effect": "non-scaling-stroke", "stroke-linejoin": "round" })));
const defs = document.createElementNS(NS, "defs");
svg.insertBefore(defs, gBase);
const hi = {}; // id -> group opacity target
M.countries.filter((c) => c.id && COUNTRY[c.id]).forEach((c) => {
  const dir = cdir(c.id), box = window.PHOTO[c.id];
  const clip = document.createElementNS(NS, "clipPath"); clip.id = "clip-" + c.id;
  clip.appendChild(mkPath(c.d, {}));
  defs.appendChild(clip);
  const im = mkImage(`${c.id}-${dir}`, box.x, box.y, box.w, box.h);
  im.setAttribute("clip-path", `url(#clip-${c.id})`);
  const g = document.createElementNS(NS, "g");
  g.append(mkPath(c.d, { fill: "none", stroke: STROKE[dir], "stroke-opacity": ".22", "stroke-width": 12, "vector-effect": "non-scaling-stroke", "stroke-linejoin": "round" }), im,
    mkPath(c.d, { fill: "none", stroke: STROKE[dir], "stroke-opacity": ".95", "stroke-width": 1.8, "vector-effect": "non-scaling-stroke", "stroke-linejoin": "round" }));
  gHi.appendChild(g);
  hi[c.id] = g;
  gsap.set(g, { opacity: 0 });
});

// camera in map space: focus lon / lat, log zoom and the focus' screen y. Tweening these instead of the world's pixel offset keeps the
// focus on a straight path while the zoom changes (no swoop), and log zoom makes pushes feel even. applyCam() runs on every seek.
const cam = { lon: C.start.lon, lat: C.start.lat, lz: Math.log(C.start.s), sy: SY };
const applyCam = () => { const s = Math.exp(cam.lz), p = P(cam.lon, cam.lat); gsap.set(world, { x: 540 - p[0] * s, y: cam.sy - p[1] * s, scale: s }); };
const move = (t, lon, lat, s, dur = 0.85, sy = SY, ease = "power3.inOut") => tl.to(cam, { lon, lat, lz: Math.log(s), sy, duration: dur, ease }, t);
tl.set(cam, { lon: C.start.lon, lat: C.start.lat, lz: Math.log(C.start.s), sy: SY }, 0);
C.route(move, tl, cam, SY);
// pull back so every market is in one frame, settle while the ranking reads, lean in before the end card
const O = C.overview;
move(13.45, O.lon, O.lat, O.s[0], 0.95, 505);
tl.to(cam, { lz: Math.log(O.s[1]), duration: 4.1, ease: "none" }, 14.4);
tl.to(cam, { lz: Math.log(O.s[2]), sy: 470, duration: 1.13, ease: "power2.in" }, 18.5);

// ---------------------------------------------------------------- pins and cards (screen-space, anchored to lon/lat)
const anchors = [];
const clampX = (x, w) => Math.max(120 + w / 2, Math.min(960 - w / 2, x));
function pin(id, lon, lat, tIn, dir) {
  const el = K.el("div", "mk-pin " + dir, overlay);
  const ring = K.el("div", "ring", el), ring2 = K.el("div", "ring", el), dot = K.el("div", "dot", el);
  gsap.set(el, { autoAlpha: 0 });
  tl.set(el, { autoAlpha: 1 }, tIn);
  tl.fromTo(dot, { scale: 0.2 }, { scale: 1, duration: 0.4, ease: "back.out(2.4)", immediateRender: false }, tIn);
  [ring, ring2].forEach((r, i) => {
    gsap.set(r, { autoAlpha: 0 });
    tl.fromTo(r, { scale: 0.4, autoAlpha: 0.9 }, { scale: 2.4, autoAlpha: 0, duration: 1.5, ease: "power2.out", repeat: 2, repeatDelay: 0.3, immediateRender: false }, tIn + 0.05 + i * 0.5);
  });
  anchors.push({ el, lon, lat, id });
  return el;
}
// card: html, pin id, offset from the pin in screen px (dy < 0 is above), appear / disappear
function card(pinId, o) {
  const el = K.el("div", "mk-card", overlay,
    `<div class="r1"><span class="nm">${o.name}</span><span class="pc ${o.dir}"><bdi>${o.pct}</bdi></span><span class="tri ${o.dir}"></span></div><div class="sub">${o.sub}</div>`);
  gsap.set(el, { autoAlpha: 0 });
  tl.fromTo(el, { autoAlpha: 0, y: 14, scale: 0.94 }, { autoAlpha: 1, y: 0, scale: 1, duration: 0.34, ease: "back.out(1.8)", immediateRender: false }, o.at);
  if (o.out) tl.to(el, { autoAlpha: 0, duration: 0.3 }, o.out);
  const link = K.el("div", "mk-link", overlay);
  gsap.set(link, { autoAlpha: 0 });
  tl.fromTo(link, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3, immediateRender: false }, o.at);
  if (o.out) tl.to(link, { autoAlpha: 0, duration: 0.3 }, o.out);
  const a = { card: el, link, pinId, dx: o.dx || 0, dy: o.dy };
  anchors.push(a);
  return a;
}
const PIN_AT = C.pins; // name -> lon, lat, second it appears
// a pin's colour follows its markets (one pin can carry several)
const pinDir = (name) => { const d = STOPS.map((s, i) => (s.pin === name ? dirs[i] : null)).filter(Boolean); return d.every((x) => x === "dn") ? "dn" : d.every((x) => x === "cl") ? "cl" : "up"; };
const pins = {};
Object.keys(PIN_AT).forEach((name) => { const [lon, lat, t] = PIN_AT[name]; pins[name] = pin(name, lon, lat, t, pinDir(name)); });
const lit = (id, t) => tl.fromTo(hi[id], { opacity: 0 }, { opacity: 1, duration: 0.6, ease: "power2.out", immediateRender: false }, t);
C.lit.forEach(([id, t]) => lit(id, t));

const CARD_T = C.cards; // one per stop: at, out, dy (< 0 = above the pin), dx
STOPS.forEach((s, i) => {
  const m = MK[s.k];
  const sub = [s.code, m.closed ? `مغلق${m.closed === true ? "" : " · " + m.closed}` : m.lvl, s.where].filter(Boolean).join(" · ");
  card(s.pin, { ...CARD_T[i], name: s.name, sub, pct: m.closed ? "مغلق" : fmtPct(m.pct), dir: dirs[i] });
});
anchors.forEach((a) => { if (a.pinId) a.pin = pins[a.pinId]; });

const place = () => {
  const s = gsap.getProperty(world, "scaleX"), wx = gsap.getProperty(world, "x"), wy = gsap.getProperty(world, "y");
  anchors.forEach((a) => {
    if (a.id) { const p = P(a.lon, a.lat); gsap.set(a.el, { x: wx + p[0] * s, y: wy + p[1] * s }); a.sx = wx + p[0] * s; a.sy = wy + p[1] * s; }
  });
  anchors.forEach((a) => {
    if (!a.pinId) return;
    const pa = anchors.find((b) => b.id === a.pinId);
    const w = a.card.offsetWidth || 440, h = a.card.offsetHeight || 104;
    const cx = clampX(pa.sx + a.dx, w), cy = pa.sy + a.dy;
    gsap.set(a.card, { left: cx - w / 2, top: cy - h / 2 });
    const y0 = a.dy > 0 ? pa.sy + 16 : cy + h / 2, y1 = a.dy > 0 ? cy - h / 2 : pa.sy - 16;
    gsap.set(a.link, { left: pa.sx - 1, top: Math.min(y0, y1), height: Math.max(0, Math.abs(y1 - y0)) });
  });
};
const seek0 = K.seek;
const grainEl = document.getElementById("grain");
K.seek = function (t) {
  seek0(t); applyCam(); place();
  // film grain stays at 24 steps a second (as before) even though the picture now moves at 60
  if (grainEl) { const st = Math.floor(t * 24); grainEl.style.transform = `translate(${(st * 37) % 40 - 20}px, ${(st * 53) % 40 - 20}px)`; }
};

// ---------------------------------------------------------------- fixed interface (map chapter)
K.el("div", "shade", overlay); // the map sinks into the background behind the bottom block, as in the source video
const ui = K.el("div", "", overlay); ui.style.cssText = "position:absolute;inset:0";
const hdr = K.el("div", "ui hdr", ui, `<div class="tt">${KICK} · <b>${TITLE}</b></div><img src="../../brand/logos/kanz-white.png" alt="">`);
const chip = (nm, pct, extra = "") => `<span class="nm">${nm}</span><span class="${pct < 0 ? "dn" : "up"}"><bdi>${extra}${fmtPct(pct)}</bdi></span>`;
const strip = K.el("div", "ui strip", ui);   // pill + Brent + gold in one row, laid out by flex
const chipB = K.el("div", "chip2", strip, chip("برنت", D.brent.pct, `$${D.brent.price} · `));
const chipG = K.el("div", "chip2", strip, chip("الذهب", D.gold.pct));
// the pill says what kind of day it was: all red / all up / mixed
const mood = nDn && nUp ? { txt: `${D.weekday} مختلط في الأسواق`, cls: "mix" } : nDn ? { txt: `⚠ ${D.weekday} أحمر في الأسواق`, cls: "" } : { txt: `${D.weekday} صاعد في الأسواق`, cls: "upm" };
const pillL = K.el("div", "pill " + mood.cls, strip, mood.txt);
strip.prepend(pillL);
gsap.set(strip, { right: 120, top: 1170 });
const ttl = K.el("div", "ui ttl", ui, TITLE);
gsap.set(ttl, { right: 120, top: 1226, fontSize: 64 });
const counter = K.el("div", "ui", ui);
gsap.set(counter, { right: 120, top: 1302, width: 840, height: 110 });
const src = K.el("div", "ui src", ui, `إغلاق ${D.date} · المصدر: Kanz Radar<i></i>`);
gsap.set(src, { right: 120, top: 1412 });

// counters: one per direction (a group with nothing in it is left out; a single group sits at the right as in the red-day version)
const T0 = 1.37, EV = C.ev; // a card lands -> the count may change (one beat later)
const groups = [{ dir: "up", n: nUp, label: `مؤشرات<br>في <em class="up">الصعود</em>`, cls: "" },
  { dir: "dn", n: nDn, label: `مؤشرات<br>في <em>الأحمر</em>`, cls: "dn" }].filter((g) => g.n > 0);
const finals = [];
groups.forEach((g, gi) => {
  const off = gi * 360;
  const lbl = K.el("div", "lbl", counter, g.label);
  gsap.set(lbl, { position: "absolute", right: off + 112, top: 12 });
  const els = [];
  for (let i = 0; i <= g.n; i++) {
    const n = K.el("div", "num8 " + g.cls, counter, String(i));
    gsap.set(n, { position: "absolute", right: off, top: -4, width: 104, autoAlpha: 0 });
    els.push(n);
  }
  // times at which this group's value changes: 0 at T0, then one per card of its direction
  const ch = [T0]; dirs.forEach((d, i) => { if (d === g.dir) ch.push(EV[i]); });
  els.forEach((n, i) => {
    const t0 = ch[i], t1 = ch[i + 1];
    tl.fromTo(n, { autoAlpha: 0, y: i ? 26 : 14, scale: i ? 0.85 : 1 }, { autoAlpha: 1, y: 0, scale: 1, duration: 0.22, ease: "back.out(2)", immediateRender: false }, t0 + (i ? 0 : 0.04));
    if (t1 != null) tl.set(n, { autoAlpha: 0 }, t1);
  });
  finals.push(els[g.n]);
});
// the final numbers stay and breathe with the music while the ranking holds
finals.forEach((n) => tl.to(n, { scale: 1.06, duration: 0.6, yoyo: true, repeat: 5, ease: "sine.inOut", transformOrigin: "100% 50%" }, 14.6));

// ranking panel: best to worst on one scale and one zero line; a closed market goes last without a bar
const NAMES = {}; STOPS.forEach((s) => { NAMES[s.k] = [s.name, s.rank]; });
const rows = Object.keys(NAMES).map((k) => ({ k, name: NAMES[k][0], ctry: NAMES[k][1], m: MK[k] }))
  .sort((a, b) => (a.m.closed ? 1 : 0) - (b.m.closed ? 1 : 0) || (b.m.pct || 0) - (a.m.pct || 0));
const live = rows.filter((r) => !r.m.closed);
const maxPos = Math.max(0, ...live.map((r) => r.m.pct)), maxNeg = Math.max(0, ...live.map((r) => -r.m.pct));
const TRACK = C.track, LAB = 118, EDGE = 10; // track width, room a value label needs beside its bar, margin when a side is empty
const roomL = maxNeg > 0 ? LAB : EDGE, roomR = maxPos > 0 ? LAB : EDGE;
const SC = (TRACK - roomL - roomR) / (maxNeg + maxPos);   // px per percentage point, shared by every bar
const X0 = roomL + maxNeg * SC;                           // zero line
const panel = K.el("div", "ui panel", ui);
panel.style.setProperty("--who", (788 - TRACK) + "px");
const rowEls = rows.map((r, k) => {
  const d = dirOf(r.m);
  const w = r.m.closed ? 0 : Math.max(3, Math.abs(r.m.pct) * SC);
  const pos = d === "dn" ? `right:${TRACK - X0}px` : `left:${X0}px`;
  const val = r.m.closed ? "مغلق" : fmtPct(r.m.pct);
  const row = K.el("div", "row", panel,
    `<div class="who"><b>${r.name}</b><span>${r.ctry}</span></div><div class="track"><div class="zero" style="left:${X0}px"></div>` +
    `<div class="seg ${d}" style="${r.m.closed ? `left:${X0 + 4}px` : pos}">${r.m.closed ? "" : '<div class="bar"></div>'}<div class="val"><bdi>${val}</bdi></div></div></div><div class="hl"></div>`);
  const bar = row.querySelector(".bar"), vl = row.querySelector(".val");
  const t = 14.55 + k * 0.085;
  if (bar) tl.to(bar, { width: w, duration: 0.45, ease: "power3.out" }, t);
  tl.to(vl, { opacity: 1, duration: 0.25 }, t + 0.18);
  return row;
});
gsap.set(panel, { autoAlpha: 0 });
tl.fromTo(panel, { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.4, ease: "power3.out", immediateRender: false }, 14.27);
// while the ranking holds: the top row is outlined, then a light pass reads the rows top to bottom
const hlTop = rowEls[0].querySelector(".hl");
tl.fromTo(hlTop, { opacity: 0 }, { opacity: 1, duration: 0.4, immediateRender: false }, 16.3);
tl.to(hlTop, { opacity: 0, duration: 0.5 }, 17.9);
rowEls.forEach((row, k) => {
  const h = row.querySelector(".hl");
  tl.fromTo(h, { opacity: 0 }, { opacity: 0.9, duration: 0.18, immediateRender: false }, 17.9 + k * 0.1);
  tl.to(h, { opacity: 0, duration: 0.3 }, 18.1 + k * 0.1);
});

// header, chips, bottom block: hidden under the title card, arrive on the cut at 1.37
const mapUi = [hdr, chipB, chipG, pillL, ttl, counter, src];
mapUi.forEach((e) => gsap.set(e, { autoAlpha: 0 }));
tl.fromTo([hdr, pillL, ttl, counter, src], { autoAlpha: 0, y: 14 }, { autoAlpha: 1, y: 0, duration: 0.35, ease: "power2.out", stagger: 0.04, immediateRender: false }, 1.37);
tl.fromTo(chipB, { autoAlpha: 0, y: 14 }, { autoAlpha: 1, y: 0, duration: 0.35, immediateRender: false }, 3.7);
tl.fromTo(chipG, { autoAlpha: 0, y: 14 }, { autoAlpha: 1, y: 0, duration: 0.35, immediateRender: false }, 3.85);

// ---------------------------------------------------------------- title card (0 - 1.37)
const tc = K.el("div", "titlecard", overlay); tc.style.cssText = "position:absolute;inset:0;z-index:16";
const g1 = K.el("div", "glow", tc); gsap.set(g1, { left: 190, top: 560, width: 700, height: 700 });
const logo = K.el("img", "", tc); logo.src = "../../brand/logos/kanz-white.png";
gsap.set(logo, { position: "absolute", left: 280, top: 640, width: 520 });
const tPill = K.el("div", "pill lav", tc, KICK);
gsap.set(tPill, { position: "absolute", left: 540, top: 840, xPercent: -50, yPercent: -50 });
const tTtl = K.el("div", "ttl", tc, TITLE);
gsap.set(tTtl, { position: "absolute", left: 540, top: 960, xPercent: -50, yPercent: -50, fontSize: 104 });
const tDate = K.el("div", "src", tc, `${D.weekday} ${D.date}`);
gsap.set(tDate, { position: "absolute", left: 540, top: 1076, xPercent: -50, yPercent: -50, fontSize: 38, color: "#cbbbd6" });
[tPill, tTtl, tDate].forEach((e, i) => tl.fromTo(e, { autoAlpha: 0, y: 22, scale: 0.96 }, { autoAlpha: 1, y: 0, scale: 1, duration: 0.34, ease: "back.out(1.6)", immediateRender: false }, [0.27, 0.43, 0.6][i]));
[tPill, tTtl, tDate].forEach((e) => gsap.set(e, { autoAlpha: 0 }));
tl.fromTo(g1, { scale: 0.92, opacity: 0.8 }, { scale: 1.08, opacity: 1, duration: 1.3, ease: "sine.inOut" }, 0);
tl.to(tc, { scale: 1.035, duration: 1.37, ease: "none", transformOrigin: "50% 50%" }, 0);
tl.set(tc, { autoAlpha: 0 }, 1.37);

// ---------------------------------------------------------------- end card (19.63 - end)
const ec = K.el("div", "titlecard", overlay); ec.style.cssText = "position:absolute;inset:0;z-index:18;background:#1d1c20 url('../../library/backgrounds/charcoal-grain-1080x1920.png') center/cover";
const g2 = K.el("div", "glow", ec); gsap.set(g2, { left: 190, top: 560, width: 700, height: 700 });
const logo2 = K.el("img", "", ec); logo2.src = "../../brand/logos/kanz-white.png";
gsap.set(logo2, { position: "absolute", left: 340, top: 700, width: 400 });
const cta = K.el("div", "ttl", ec, "تابع الأسواق كل يوم<br>مع مجتمع كنز");
gsap.set(cta, { position: "absolute", left: 540, top: 930, xPercent: -50, yPercent: -50, fontSize: 70, textAlign: "center", lineHeight: 1.3 });
const btn = K.el("div", "pill lav", ec, "<bdi>kanzms.circle.so</bdi>");
gsap.set(btn, { position: "absolute", left: 540, top: 1100, xPercent: -50, yPercent: -50, fontSize: 38, padding: "14px 34px" });
gsap.set(ec, { autoAlpha: 0 });
tl.set(ec, { autoAlpha: 1 }, 19.63);
[logo2, cta, btn].forEach((e, i) => tl.fromTo(e, { autoAlpha: 0, y: 20 }, { autoAlpha: 1, y: 0, duration: 0.4, ease: "power3.out", immediateRender: false }, 19.66 + i * 0.1));
tl.fromTo(g2, { scale: 0.9, opacity: 0.6 }, { scale: 1.1, opacity: 1, duration: 2.0, ease: "sine.out" }, 19.63);

// ease the map chapter out before the end card (leans into the riser in the mix)
tl.to([ui, ...anchors.filter((a) => a.id).map((a) => a.el)], { opacity: 0.55, duration: 1.2, ease: "power1.in" }, 18.4);
