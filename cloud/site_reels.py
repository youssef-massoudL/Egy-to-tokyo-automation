"""Put one reel edition into a website build: carry_reel(site, edition, live_site_url).
Normally copies it from the live site. When the live site is behind (that day's website deploy failed), takes the newer
reel from its GitHub release instead, so any later deploy, of either edition, repairs the site by itself.
Only public releases tagged exactly <edition>-YYYY-MM-DD with status OK or SINGLE SOURCE count: never drafts or tests."""
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "youssef-massoudL/Egy-to-tokyo-automation")
GOOD = ("OK", "SINGLE SOURCE")


def get(url, timeout=120, api=False):
    req = urllib.request.Request(url)
    if api:
        req.add_header("Accept", "application/vnd.github+json")
        if os.environ.get("GH_TOKEN"):
            req.add_header("Authorization", f"Bearer {os.environ['GH_TOKEN']}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def poster(video, jpg):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-5", "-i", str(video), "-frames:v", "1",
                    "-vf", "scale=540:-1", "-q:v", "3", str(jpg)], check=True)


def newest_release(ed):
    """(date, {asset name: download url}) of the newest public reel release of the edition, or None."""
    best = None
    for r in json.loads(get(f"https://api.github.com/repos/{REPO}/releases?per_page=50", api=True)):
        m = re.fullmatch(rf"{ed}-(\d{{4}}-\d\d-\d\d)", r["tag_name"])
        if m and not r["draft"] and not r["prerelease"] and (best is None or m[1] > best[0]):
            best = (m[1], {a["name"]: a["browser_download_url"] for a in r["assets"]})
    return best


def rank(meta):
    """A later day wins; on the same day a real reel wins over a test."""
    return (meta.get("date") or "", meta.get("status") in GOOD)


def from_release(d, ed, live_meta):
    """Fill folder d from the newest release if it is ahead of the live site. False = the live copy is fine."""
    rel = newest_release(ed)
    if not rel or rel[0] < rank(live_meta)[0]:
        return False
    info = next((u for n, u in rel[1].items() if n.endswith("_site.json")), None)
    if not info:
        return False
    meta = json.loads(get(info))
    video = rel[1].get(meta.get("file"))
    if meta.get("edition") != ed or meta.get("status") not in GOOD or not video or rank(meta) <= rank(live_meta):
        return False
    with tempfile.TemporaryDirectory() as t:   # everything ready first, so a failure half way leaves nothing mixed
        t = Path(t)
        (t / "latest.mp4").write_bytes(get(video))
        poster(t / "latest.mp4", t / "latest.jpg")
        d.mkdir(parents=True, exist_ok=True)
        for f in ("latest.mp4", "latest.jpg"):
            (d / f).write_bytes((t / f).read_bytes())
    (d / "latest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{ed}: {meta['date']} taken from its release (live site had {live_meta.get('date', 'none')})")
    return True


def carry_reel(site, ed, live):
    live = (live or "").rstrip("/")
    if not live:
        return
    d = Path(site) / ed
    try:
        live_meta = json.loads(get(f"{live}/{ed}/latest.json"))
    except Exception as e:  # noqa: BLE001 - nothing published yet for that edition
        print(f"{ed}: not on the live site ({e})")
        live_meta = {}
    try:
        if from_release(d, ed, live_meta):
            return
    except Exception as e:  # noqa: BLE001 - the live copy still goes in
        print(f"{ed}: could not take the release ({e})")
    if not live_meta:
        return
    try:
        got = {f: get(f"{live}/{ed}/{f}") for f in ("latest.mp4", "latest.jpg")}
    except Exception as e:  # noqa: BLE001
        print(f"{ed}: could not copy the live reel ({e})")
        return
    d.mkdir(parents=True, exist_ok=True)
    for f, body in got.items():
        (d / f).write_bytes(body)
    (d / "latest.json").write_text(json.dumps(live_meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{ed}: carried over {live_meta.get('date')} from the live site")
