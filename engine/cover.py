"""Render a Reel cover in the approved style A ("the idea in an object", Ahmed 2026-10-11):
python engine/cover.py projects/<slug>

Reads projects/<slug>/cover.json:
  {"lines": ["هل فعلًا العقار", "*مبيخسرش*؟"],   # one or two headline lines; *word* = lavender keyword
   "object": "kanz-house-v01.png",                # an approved library object (library/objects/)
   "w": 560, "size": 124}                          # optional: object width, headline font size
Writes out/cover.png (1080x1920, the file to upload) and out/cover-review.jpg: the 9:16 cover with the
3:4 / 4:5 / 1:1 centred crop lines, next to the 3:4 crop the Instagram profile grid shows.
Essential content (headline + object) must sit inside x 150-930, y 440-1380 so it survives every crop;
the script measures the rendered bounds and warns when it does not. Text is real HTML, never generated.
"""
import html
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SAFE = (150, 440, 930, 1380)
CROPS = {"3:4": (240, 1680), "4:5": (285, 1635), "1:1": (420, 1500)}

PAGE = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<link rel="stylesheet" href="{rt}/kanz.css"><link rel="stylesheet" href="{rt}/kanz-look.css">
<style>
#stage .hl{{position:absolute;left:150px;right:150px;top:450px;text-align:center;font-family:var(--head);font-weight:700;
  font-size:{size}px;line-height:1.2;color:#fff}}
#stage .hl .kw{{color:var(--lavender)}}
#stage img.hero{{position:absolute;left:{ox}px;top:{oy}px;width:{w}px;z-index:2;
  filter:drop-shadow(0 18px 22px rgba(0,0,0,.5)) drop-shadow(0 2px 3px rgba(0,0,0,.35))}}
</style></head><body>
<div id="stage" class="look2"><div id="keylight"></div>
  <div class="kglow" style="left:{gx}px;top:{gy}px;width:{gd}px;height:{gd}px"></div>
  <div class="kshadow" style="left:{sx}px;top:{sy}px;width:{sw}px;height:{sh}px"></div>
  <img class="hero" src="{obj}">
  <div class="hl">{lines}</div>
  <div id="vignette"></div></div></body></html>"""


def line_html(s):
    s = html.escape(s)
    return re.sub(r"\*(.+?)\*", r'<span class="kw">\1</span>', s)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    proj = Path(sys.argv[1]).resolve()
    c = json.loads((proj / "cover.json").read_text(encoding="utf-8"))
    out = proj / "out"
    out.mkdir(exist_ok=True)
    w, size, oy = c.get("w", 560), c.get("size", 124), c.get("y", 790)
    obj = (ROOT / "library" / "objects" / c["object"]).as_uri()
    page_html = PAGE.format(rt=(ROOT / "runtime").as_uri(), size=size, w=w, ox=540 - w / 2, oy=oy, obj=obj,
                            gd=w * 1.55, gx=540 - w * 0.775, gy=oy + w * 0.45 - w * 0.775,
                            sw=w * 0.82, sh=w * 0.14, sx=540 - w * 0.41, sy=oy + w * 0.84,
                            lines="<br>".join(line_html(s) for s in c["lines"]))
    src = out / "_cover.html"
    src.write_text(page_html, encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto(src.as_uri())
        pg.wait_for_function("document.fonts.status === 'loaded' && document.querySelector('img.hero').complete")
        # visible bounds: headline glyph box and the object's opaque pixels (PNG padding excluded)
        hl = pg.evaluate("(() => { const r = document.querySelector('.hl').getBoundingClientRect(); const g = document.createRange();"
                         " g.selectNodeContents(document.querySelector('.hl')); const q = g.getBoundingClientRect();"
                         " return [q.left, q.top, q.right, q.bottom]; })()")
        pg.screenshot(path=str(out / "cover.png"))
        b.close()
    im = Image.open(out / "cover.png").convert("RGB")
    hero = Image.open(ROOT / "library" / "objects" / c["object"]).convert("RGBA")
    k = w / hero.width
    bx = hero.getchannel("A").point(lambda a: 255 if a > 40 else 0).getbbox()
    ob = [540 - w / 2 + bx[0] * k, oy + bx[1] * k, 540 - w / 2 + bx[2] * k, oy + bx[3] * k]
    warn = []
    for name, (x0, y0, x1, y1) in (("headline", hl), ("object", ob)):
        if x0 < SAFE[0] or y0 < SAFE[1] or x1 > SAFE[2] or y1 > SAFE[3]:
            warn.append(f"{name} {[round(v) for v in (x0, y0, x1, y1)]} leaves the crop-safe box {list(SAFE)}")
    # review sheet: 9:16 with crop lines | 3:4 grid crop
    rv = im.copy()
    d = ImageDraw.Draw(rv)
    for (name, (y0, y1)), col in zip(CROPS.items(), [(255, 109, 98), (255, 190, 90), (120, 200, 255)]):
        for y in (y0, y1):
            for x in range(0, 1080, 36):
                d.line([(x, y), (x + 20, y)], fill=col, width=4)
        d.text((16, y0 + 8), name, fill=col)
    d.rectangle(SAFE, outline=(213, 173, 239), width=3)
    grid = im.crop((0, CROPS["3:4"][0], 1080, CROPS["3:4"][1]))
    sheet = Image.new("RGB", (1080 + 40 + 1080, 1920), (245, 245, 247))
    sheet.paste(rv, (0, 0))
    sheet.paste(grid, (1120, (1920 - 1440) // 2))
    sheet.resize((1100, 960)).save(out / "cover-review.jpg", quality=86)
    print("cover ->", out / "cover.png")
    print("review ->", out / "cover-review.jpg")
    print("crop-safe:", "ok" if not warn else "\n  ".join(["CHECK"] + warn))


if __name__ == "__main__":
    main()
