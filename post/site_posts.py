"""Close posts on the GitHub Pages site (folder posts/<market>/ next to the reel editions).

put_post(site, result_json)   copy one finished post into the site: latest.json, wide.png, tall.png and small JPG previews
carry_posts(site, live)       copy every market not put this run from the live site (a deploy replaces the whole site)
Both the reel's cloud/build_site.py and post/build_site.py call carry_posts, so neither deploy wipes the other's content.

put_team(site, dist)          the "فريق كنز" tab: the built kanz-team app (branch kanz-team) in team/, a list of its
                              files in team/files.json, and the app's page as the site's 404.html so a link such as
                              team/docs/what-kanz-is still opens (GitHub Pages only reads the 404.html at the root)
carry_team(site, live)        copy team/ and 404.html from the live site, by that list
"""
import json
import os
import shutil
import urllib.request
from pathlib import Path

POST_MARKETS = ("tasi", "egx", "us")
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


TEAM = "team"
# The root 404.html is the team app's page, so team/ links open it. Any other unknown address goes to the home page.
NOT_TEAM = ('<script>if (!location.pathname.includes("/team/")) '
            'location.replace(location.pathname.split("/").slice(0, 2).join("/") + "/");</script>')


def put_team(site, dist):
    site, dist = Path(site), Path(dist)
    d = site / TEAM
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(dist, d)
    files = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file())
    (d / "files.json").write_text(json.dumps(files, indent=0), encoding="utf-8")
    page = (d / "index.html").read_text(encoding="utf-8")
    (site / "404.html").write_text(page.replace("<head>", "<head>" + NOT_TEAM, 1), encoding="utf-8")
    print(f"team: {len(files)} files from {dist}")


def carry_team(site, live):
    live = (live or "").rstrip("/")
    if not live:
        return
    site = Path(site)
    try:
        with urllib.request.urlopen(f"{live}/{TEAM}/files.json", timeout=60) as r:
            files = json.loads(r.read())
        got = {}
        for f in files + ["files.json"]:
            with urllib.request.urlopen(f"{live}/{TEAM}/{f}", timeout=120) as r:
                got[f] = r.read()
        with urllib.request.urlopen(f"{live}/404.html", timeout=60) as r:
            page404 = r.read()
        for f, body in got.items():
            out = site / TEAM / f
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(body)
        (site / "404.html").write_bytes(page404)
        print(f"team: carried over {len(files)} files from the live site")
    except Exception as e:  # noqa: BLE001 - not published yet
        print(f"team: not on the live site ({e})")


def team(site, live):
    """The team tab for a site build: the fresh app when TEAM_DIST names one (Deploy website), else the live copy."""
    dist = os.environ.get("TEAM_DIST")
    if dist and Path(dist, "index.html").is_file():
        put_team(site, dist)
    else:
        carry_team(site, live)
