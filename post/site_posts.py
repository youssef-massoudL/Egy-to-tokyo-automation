"""Close posts on the GitHub Pages site (folder posts/<market>/ next to the reel editions).

put_post(site, result_json)   copy one finished post into the site: latest.json, wide.png, tall.png and small JPG previews
carry_posts(site, live)       copy every market not put this run from the live site (a deploy replaces the whole site)
Both the reel's cloud/build_site.py and post/build_site.py call carry_posts, so neither deploy wipes the other's content.
"""
import json
import shutil
import urllib.request
from pathlib import Path

POST_MARKETS = ("tasi", "egx", "spx", "dji", "ndx")
FILES = ("latest.json", "wide.png", "tall.png", "wide.jpg", "tall.jpg")


def put_post(site, result_path):
    from PIL import Image
    res = json.loads(Path(result_path).read_text(encoding="utf-8"))
    d = Path(site) / "posts" / res["market"]
    d.mkdir(parents=True, exist_ok=True)
    wide, tall = map(Path, res["files"])
    shutil.copy(wide, d / "wide.png")
    shutil.copy(tall, d / "tall.png")
    for src, name, w in ((wide, "wide.jpg", 1600), (tall, "tall.jpg", 720)):
        im = Image.open(src).convert("RGB")
        im.resize((w, round(im.height * w / im.width)), Image.LANCZOS).save(d / name, quality=86)
    meta = {k: res[k] for k in ("market", "date", "date_ar", "status", "line")}
    meta["files"] = {"wide": wide.name, "tall": tall.name}
    (d / "latest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"posts/{res['market']}: {res['status']} {res['date']}")
    return res["market"]


def carry_posts(site, live, skip=()):
    live = (live or "").rstrip("/")
    if not live:
        return
    for mk in POST_MARKETS:
        if mk in skip:
            continue
        d = Path(site) / "posts" / mk
        try:
            got = {}
            for f in FILES:
                with urllib.request.urlopen(f"{live}/posts/{mk}/{f}", timeout=60) as r:
                    got[f] = r.read()
            d.mkdir(parents=True, exist_ok=True)
            for f, body in got.items():
                (d / f).write_bytes(body)
            print(f"posts/{mk}: carried over {json.loads(got['latest.json']).get('date')} from the live site")
        except Exception as e:  # noqa: BLE001 - nothing published yet for that market
            print(f"posts/{mk}: not on the live site ({e})")
