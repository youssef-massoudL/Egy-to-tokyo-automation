"""Check a scene frame by frame before rendering: python engine/lint.py <project_dir> [--every 0.25]

Reads the live page (no video render) and reports:
  safe   text outside the platform safe zones (K.SAFE, docs/LOOK-V2.md); objects whose centre is outside
  dead   stretches longer than --dead seconds where nothing new appears and the camera holds
  fill   stretches longer than 1.5 s where visible content covers less than --fill of the safe area (MUST FIX
         since 2026-10-11: fill the frame when the voice names a thing, or justify it)
  hook   the first visual arriving later than --hook (0.3 s since 2026-10-11) and a first frame below --fill
  bars   boards where two or more bars use hand-entered heights or different scales (K.scale, docs/LOOK-V2.md)
  covered  a label or headline word hidden under an object (e.g. a carried hero crossing it) or under the caption
  under    a focal object more than 15% behind a caption box
  edge     an object (K.bgObj figures included) with its centre inside but over a quarter of it past the side margin
           (covered / under / edge added 2026-10-13 from the us-dollar-decisions-pace v3 review)
Writes out/lint.json and, when there are findings, out/lint.jpg: one frame per finding with the
unsafe zones shaded red. Exit code is 0 either way: these are review flags, not hard failures.
"""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
from contact import sheet  # noqa: E402

SAFE = {"top": 270, "bottom": 1440, "left": 120, "right": 960, "upperLeft": 65, "upperRight": 1015, "upperBottom": 1000}
TEXT = "#world .t, #world .tag, #world .card, #world .kcount, #world .ksrc, #headline .w, #overlay .t"
COVER = "#world .t, #world .tag, #headline .w"  # labels that must stay readable (2026-10-13)
OBJS = "#world img.obj,#world .kdoc, #world .kphoto, #world img.kmap, #world svg.mk path, #world svg.mk polyline, #world svg.mk rect, #world .kpin, #world .kmark, #world .kframe, #world .abs"

PROBE = """(t) => {
  K.seek(t);
  const st = document.getElementById('stage').getBoundingClientRect();
  const out = [];
  let next = window.__lid || 1;
  const eff = (el) => { let o = 1; for (let e = el; e && e.id !== 'stage'; e = e.parentElement) {
      const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none') return 0; o *= parseFloat(cs.opacity); }
    return o; };
  const take = (sel, kind) => document.querySelectorAll(sel).forEach((el) => {
    if (el.closest('#safeguide')) return;
    if (el.matches('.kshadow, .kglow, .kfg')) return;
    const r = el.getBoundingClientRect();
    if (r.width < 3 || r.height < 3) return;
    const x0 = Math.max(r.left, st.left), x1 = Math.min(r.right, st.right), y0 = Math.max(r.top, st.top), y1 = Math.min(r.bottom, st.bottom);
    if (x1 <= x0 || y1 <= y0) return;
    const o = eff(el); if (o < 0.15) return;
    if (!el.dataset.lid) el.dataset.lid = String(next++);
    out.push({ id: +el.dataset.lid, kind, x0: r.left - st.left, y0: r.top - st.top, x1: r.right - st.left, y1: r.bottom - st.top,
      txt: kind === 'text' ? (el.textContent || '').trim().slice(0, 40) : (el.getAttribute('src') || el.getAttribute('class') || el.tagName).toString().split('/').pop().slice(0, 40) });
  });
  TAKE
  window.__lid = next;
  // text hidden under an object or the caption: test three points along the label's middle line
  const covered = [];
  document.querySelectorAll(COVERSEL).forEach((el) => {
    if (eff(el) < 0.5) return;
    const r = el.getBoundingClientRect();
    if (r.width < 3 || r.height < 3) return;
    const ys = r.top + r.height / 2, hits = {};
    for (const xs of [r.left + r.width * 0.25, r.left + r.width / 2, r.left + r.width * 0.75]) {
      for (const e of document.elementsFromPoint(xs, ys)) {
        if (e === el || el.contains(e)) break;
        if (e.closest('#captions')) break; // caption overlap is measured by area in Python
        if (e.matches('img.obj') && !e.matches('.kfg') && eff(e) >= 0.3) {
          const k = (e.getAttribute('src') || '').split('/').pop(); hits[k] = (hits[k] || 0) + 1; break; }
      }
    }
    const by = Object.keys(hits).find((k) => hits[k] >= 2);
    if (by) covered.push({ id: +(el.dataset.lid || 0), txt: (el.textContent || '').trim().slice(0, 40), by });
  });
  const w = document.getElementById('world');
  return { items: out, covered, cam: [gsap.getProperty(w, 'x'), gsap.getProperty(w, 'y'), gsap.getProperty(w, 'scaleX')] };
}"""


GUIDE = """(S) => {
  const st = document.getElementById('stage'), g = document.createElement('div');
  g.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:40';
  const box = (l, t, w, h) => { const d = document.createElement('div');
    d.style.cssText = `position:absolute;left:${l}px;top:${t}px;width:${w}px;height:${h}px;background:rgba(229,83,75,.24)`; g.appendChild(d); };
  box(0, 0, 1080, S.top); box(0, S.bottom, 1080, 1920 - S.bottom);
  box(0, S.top, S.upperLeft, S.upperBottom - S.top); box(S.upperRight, S.top, 1080 - S.upperRight, S.upperBottom - S.top);
  box(0, S.upperBottom, S.left, S.bottom - S.upperBottom); box(S.right, S.upperBottom, 1080 - S.right, S.bottom - S.upperBottom);
  st.appendChild(g);
}"""


def outside(it):
    """How a rectangle breaks the safe zone, or ''."""
    why = []
    if it["y0"] < SAFE["top"] - 1:
        why.append("top")
    if it["y1"] > SAFE["bottom"] + 1:
        why.append("bottom")
    lower = it["y1"] > SAFE["upperBottom"]
    left, right = (SAFE["left"], SAFE["right"]) if lower else (SAFE["upperLeft"], SAFE["upperRight"])
    if it["x0"] < left - 1:
        why.append("left")
    if it["x1"] > right + 1:
        why.append("right")
    return "+".join(why)


def coverage(items):
    """Share of the safe area covered by visible content, on a 20 px grid."""
    cell, x0, x1, y0, y1 = 20, SAFE["upperLeft"], SAFE["upperRight"], SAFE["top"], SAFE["bottom"]
    cols, rows = (x1 - x0) // cell, (y1 - y0) // cell
    hit = set()
    for it in items:
        if it["kind"] == "caption":
            continue
        for cy in range(max(0, int((it["y0"] - y0) // cell)), min(rows, int((it["y1"] - y0) // cell) + 1)):
            for cx in range(max(0, int((it["x0"] - x0) // cell)), min(cols, int((it["x1"] - x0) // cell) + 1)):
                hit.add((cx, cy))
    return len(hit) / (cols * rows)


def bar_findings(bars):
    """Boards whose bars are not drawn from values on one shared scale. Illustrative bars are skipped."""
    by_board = {}
    for b in bars:
        if not b.get("illustrative"):
            by_board.setdefault(b["board"], []).append(b)
    out = []
    for board, bs in by_board.items():
        if len(bs) < 2:
            continue
        hand = [b for b in bs if b["value"] is None]
        scales = {b["scale"] for b in bs if b["value"] is not None}
        if hand:
            out.append({"board": board, "why": "hand-entered heights", "at": hand[0]["at"],
                        "detail": "h = " + ", ".join(str(round(b["h"])) for b in hand) + "; pass value + scale"})
        elif len(scales) > 1:
            out.append({"board": board, "why": "different scales", "at": bs[0]["at"],
                        "detail": f"{len(scales)} scales on one board; use one K.scale per comparison"})
    return out


def runs(times, flags, min_len):
    out, start = [], None
    for t, f in zip(times + [None], flags + [False]):
        if f and start is None:
            start = t
        if not f and start is not None:
            end = t if t is not None else times[-1]
            if end - start >= min_len:
                out.append((round(start, 2), round(end, 2)))
            start = None
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--every", type=float, default=0.25)
    ap.add_argument("--dead", type=float, default=2.5)
    ap.add_argument("--fill", type=float, default=0.30)
    ap.add_argument("--hook", type=float, default=0.3)
    ap.add_argument("--no-sheet", action="store_true")
    a = ap.parse_args()
    proj = Path(a.project).resolve()
    out_dir = proj / "out"
    out_dir.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--allow-file-access-from-files"])
        page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto((proj / "index.html").as_uri())
        page.wait_for_function("document.fonts && document.fonts.status === 'loaded' && window.K")
        page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
        if errors:
            print("PAGE ERRORS:", *errors, sep="\n  ")
        voice_end = page.evaluate("window.DURATION || K.duration")
        look2 = page.evaluate("!!K.LOOK")
        probe = PROBE.replace("TAKE", f"take({json.dumps(TEXT)}, 'text'); take({json.dumps(OBJS)}, 'obj');"
                                      " take('#captions .box', 'caption');").replace("COVERSEL", json.dumps(COVER))
        # start one sample in: GSAP does not render zero-duration sets on a seek to exactly 0
        frames, t = [], a.every
        while t <= voice_end + 0.01:
            f = page.evaluate(probe, t)
            frames.append((round(t, 2), f))
            t += a.every

        times = [t for t, _ in frames]
        # 1. safe zones
        safe_hits = {}
        for t, f in frames:
            for it in f["items"]:
                why = outside(it)
                if not why:
                    continue
                if it["kind"] == "obj":
                    cx, cy = (it["x0"] + it["x1"]) / 2, (it["y0"] + it["y1"]) / 2
                    if SAFE["upperLeft"] <= cx <= SAFE["upperRight"] and SAFE["top"] <= cy <= SAFE["bottom"]:
                        continue
                    # an object mostly outside (peeking under the UI) is harmless; one cut in half is not
                    ix = max(0, min(it["x1"], SAFE["upperRight"]) - max(it["x0"], SAFE["upperLeft"]))
                    iy = max(0, min(it["y1"], SAFE["bottom"]) - max(it["y0"], SAFE["top"]))
                    if ix * iy < 0.25 * (it["x1"] - it["x0"]) * (it["y1"] - it["y0"]):
                        continue
                    why = "centre-" + why
                key = ("caption", 0, why) if it["kind"] == "caption" else (it["kind"], it["id"], why)
                h = safe_hits.setdefault(key, {"kind": it["kind"], "what": it["txt"], "why": why, "from": t, "to": t, "frames": 0})
                h["to"] = t
                h["frames"] += 1
        # one-sample hits are elements sliding past an edge during a camera move: ignore them
        safe = sorted((h for h in safe_hits.values() if h["frames"] >= 2), key=lambda h: h["from"])

        # 2. dead stretches: no new element and no camera move
        events, seen_prev, cam_prev = [], set(), None
        for t, f in frames:
            ids = {it["id"] for it in f["items"] if it["kind"] != "caption"}
            new = ids - seen_prev
            cam = f["cam"]
            moved = cam_prev is not None and (abs(cam[0] - cam_prev[0]) > 25 or abs(cam[1] - cam_prev[1]) > 25
                                              or abs(cam[2] - cam_prev[2]) > 0.015)
            if new or moved:
                events.append(t)
            seen_prev, cam_prev = ids, cam
        dead = []
        for e0, e1 in zip(events, events[1:] + [voice_end]):
            if e1 - e0 > a.dead:
                dead.append((round(e0, 2), round(e1, 2)))

        # 3. frame fill (captions excluded)
        cov = []
        for t, f in frames:
            cov.append(round(coverage(f["items"]), 3))
        thin = runs(times, [c < a.fill for c in cov], 1.5)

        # 4. hook
        first = next((t for t, f in frames if any(it["kind"] != "caption" for it in f["items"])), None)
        hook = None if first is not None and first <= a.hook else first
        first_fill = cov[0] if cov else 0

        # 5. bars drawn to scale
        bars = bar_findings(page.evaluate("(K.bars || []).map(b => ({...b}))"))

        # 6. covered text (2026-10-13): a label under an object at a 0.25 s sample (a one-frame crossing during a fast
        #    camera whip is not caught, by design) or under the caption for two samples (a move sliding past is ignored)
        cover_hits = {}
        for t, f in frames:
            for c in f.get("covered", []):
                h = cover_hits.setdefault((c["id"], c["by"]), {"what": c["txt"], "by": c["by"], "from": t, "to": t, "frames": 0})
                h["to"], h["frames"] = t, h["frames"] + 1
        # a label more than a quarter under a caption box (area, not a centre test: half-hidden labels count)
        for t, f in frames:
            caps = [it for it in f["items"] if it["kind"] == "caption"]
            for it in f["items"]:
                if it["kind"] != "text" or it["y0"] < SAFE["top"]:
                    continue
                area = (it["x1"] - it["x0"]) * (it["y1"] - it["y0"])
                ov = sum(max(0, min(it["x1"], c["x1"]) - max(it["x0"], c["x0"])) * max(0, min(it["y1"], c["y1"]) - max(it["y0"], c["y0"]))
                         for c in caps)
                if area and ov > 0.25 * area:
                    h = cover_hits.setdefault((it["id"], "caption"), {"what": it["txt"], "by": "caption", "from": t, "to": t, "frames": 0})
                    h["to"], h["frames"] = t, h["frames"] + 1
        covered = sorted((h for h in cover_hits.values() if h["by"] != "caption" or h["frames"] >= 2), key=lambda h: h["from"])

        # 7. objects behind the caption band: more than 15% of a focal object under a caption box, 2+ samples
        under_hits = {}
        for t, f in frames:
            caps = [it for it in f["items"] if it["kind"] == "caption"]
            for it in f["items"]:
                if it["kind"] != "obj" or not it["txt"].endswith(".png"):
                    continue
                area = (it["x1"] - it["x0"]) * (it["y1"] - it["y0"])
                ov = sum(max(0, min(it["x1"], c["x1"]) - max(it["x0"], c["x0"])) * max(0, min(it["y1"], c["y1"]) - max(it["y0"], c["y0"]))
                         for c in caps)
                if area and ov > 0.15 * area:
                    h = under_hits.setdefault(it["id"], {"what": it["txt"], "from": t, "to": t, "frames": 0})
                    h["to"], h["frames"] = t, h["frames"] + 1
        under = sorted((h for h in under_hits.values() if h["frames"] >= 2), key=lambda h: h["from"])

        # 8. objects pushed past the side margin: centre inside, but more than a quarter of the width beyond it
        #    (the safe check above only catches objects whose centre is outside). Includes faint K.bgObj figures.
        edge_hits = {}
        for t, f in frames:
            for it in f["items"]:
                if it["kind"] != "obj" or not it["txt"].endswith(".png"):
                    continue
                w = it["x1"] - it["x0"]
                lower = (it["y0"] + it["y1"]) / 2 > SAFE["upperBottom"]
                left, right = (SAFE["left"], SAFE["right"]) if lower else (SAFE["upperLeft"], SAFE["upperRight"])
                beyond = max(0, left - it["x0"]) + max(0, it["x1"] - right)
                cx = (it["x0"] + it["x1"]) / 2
                if w and left <= cx <= right and beyond > 0.25 * w:
                    h = edge_hits.setdefault(it["id"], {"what": it["txt"], "from": t, "to": t, "frames": 0})
                    h["to"], h["frames"] = t, h["frames"] + 1
        edge = sorted((h for h in edge_hits.values() if h["frames"] >= 3), key=lambda h: h["from"])

        report = {"project": proj.name, "look2": look2, "every": a.every, "voice_end": voice_end,
                  "safe": safe, "dead": dead, "thin": thin, "hook_late": hook, "first_fill": first_fill, "bars": bars,
                  "covered": covered, "under_captions": under, "edge": edge,
                  "fill_median": sorted(cov)[len(cov) // 2] if cov else 0}
        (out_dir / "lint.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

        print(f"lint {proj.name}: look2={'on' if look2 else 'off'}, {len(frames)} frames to {voice_end:.1f}s, median fill {report['fill_median']:.0%}")
        print(f"  safe zones: {len(safe)} finding(s)")
        for h in safe[:25]:
            what = f"captions in {h['frames']} sampled frames" if h["kind"] == "caption" else h["what"]
            print(f"    {h['from']:6.2f}-{h['to']:6.2f}s  {h['kind']:7} {h['why']:20} {what}")
        print(f"  dead stretches > {a.dead}s: {dead or 'none'}")
        print(f"  thin frames (< {a.fill:.0%} of safe area for 1.5 s+): {('MUST FIX ' + str(thin)) if thin else 'none'}")
        hook_msg = 'first visual at %.2fs (later than %.1f s)' % (hook, a.hook) if hook is not None else 'ok'
        if first_fill < a.fill:
            hook_msg += f'; first frame only {first_fill:.0%} filled (want a complete composition: question + hero object)'
        print(f"  hook: {hook_msg}")
        print(f"  bars to scale: {len(bars) or 'ok'}{' finding(s)' if bars else ''}")
        for b in bars:
            at = f"{b['at']:6.2f}s" if isinstance(b["at"], (int, float)) else "     -"
            print(f"    {at}  {b['why']:22} {b['detail']}")
        print(f"  covered text: {len(covered) or 'none'}")
        for h in covered:
            print(f"    {h['from']:6.2f}-{h['to']:6.2f}s  '{h['what']}' under {h['by']}")
        print(f"  objects behind captions: {len(under) or 'none'}")
        for h in under:
            print(f"    {h['from']:6.2f}-{h['to']:6.2f}s  {h['what']}")
        print(f"  objects past the side margin: {len(edge) or 'none'}")
        for h in edge:
            print(f"    {h['from']:6.2f}-{h['to']:6.2f}s  {h['what']}")

        shots = sorted({round(h["from"], 2) for h in safe if h["kind"] == "text"}
                       | {round(h["from"], 2) for h in covered + under + edge}
                       | {round((s + e) / 2, 2) for s, e in dead} | {round((s + e) / 2, 2) for s, e in thin})
        if shots and not a.no_sheet:
            sd = out_dir / "lint"
            sd.mkdir(exist_ok=True)
            for old in sd.glob("*.png"):
                old.unlink()
            page.evaluate(GUIDE, SAFE)
            for t in shots[:18]:
                page.evaluate("(t) => K.seek(t)", t)
                page.screenshot(path=str(sd / f"t{t:06.2f}s.png"), clip={"x": 0, "y": 0, "width": 1080, "height": 1920})
            print("  lint sheet ->", sheet(sd, out_dir / "lint.jpg"))
        browser.close()


if __name__ == "__main__":
    main()
