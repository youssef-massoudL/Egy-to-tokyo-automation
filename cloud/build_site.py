"""Build the whole GitHub Pages site: python cloud/build_site.py egx|us <out_folder> <site_dir> [<live_site_url>]
This run's edition comes from <out_folder>; the other edition is carried over from the live site (a deploy replaces the
whole site, so without this one edition would wipe the other)."""
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from editions import EDITIONS  # noqa: E402

NAME, folder, site = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
live = (sys.argv[4] if len(sys.argv) > 4 else "").rstrip("/")
ROOT = Path(__file__).resolve().parent.parent
site.mkdir(parents=True, exist_ok=True)
(site / "fonts").mkdir(exist_ok=True)
shutil.copy(ROOT / "site" / "index.html", site / "index.html")
for f in ("IBM-Regular.ttf", "IBM-Medium.ttf", "ThmanyahDisplay-Bold.woff2"):
    shutil.copy(ROOT / "brand" / "fonts" / f, site / "fonts" / f)
shutil.copy(ROOT / "brand" / "logos" / "kanz-white.png", site / "kanz-white.png")

# this edition
d = site / NAME
d.mkdir(exist_ok=True)
fin = json.loads(Path("finish.json").read_text(encoding="utf-8"))
video = folder / fin["video"]
shutil.copy(video, d / "latest.mp4")
shutil.copy(folder / f"{video.stem}_site.json", d / "latest.json")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-5", "-i", str(video), "-frames:v", "1", "-vf", "scale=540:-1", "-q:v", "3", str(d / "latest.jpg")], check=True)
print(f"{NAME}: {fin['status']} {video.name}")


def get(url, dest=None):
    with urllib.request.urlopen(url, timeout=60) as r:
        body = r.read()
    if dest:
        dest.write_bytes(body)
    return body


# the other edition(s): copy from the live site if it has them
for other in EDITIONS:
    if other == NAME or not live:
        continue
    o = site / other
    for base in (f"{live}/{other}", live if other == "egx" else None):   # the first site had EGX at the root
        if not base:
            continue
        try:
            meta = json.loads(get(f"{base}/latest.json"))
            if meta.get("edition", "egx") != other:
                continue
            o.mkdir(exist_ok=True)
            meta["edition"] = other
            (o / "latest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            get(f"{base}/latest.mp4", o / "latest.mp4")
            get(f"{base}/latest.jpg", o / "latest.jpg")
            print(f"{other}: carried over {meta.get('date')} from {base}")
            break
        except Exception as e:  # noqa: BLE001 - nothing published yet for that edition
            print(f"{other}: not on the live site at {base} ({e})")
