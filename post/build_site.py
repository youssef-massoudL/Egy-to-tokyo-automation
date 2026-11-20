"""Build the whole GitHub Pages site from the post workflow: python post/build_site.py <site_dir> <live_site_url> [post_result_<mk>.json ...]
The posts named on the command line go in; every reel edition and every other post is carried over from the live site."""
import json
import shutil
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "cloud"))
from editions import EDITIONS  # noqa: E402
from site_posts import carry_posts, put_post  # noqa: E402

site, live, results = Path(sys.argv[1]), (sys.argv[2] if len(sys.argv) > 2 else "").rstrip("/"), sys.argv[3:]
site.mkdir(parents=True, exist_ok=True)
(site / "fonts").mkdir(exist_ok=True)
shutil.copy(ROOT / "site" / "index.html", site / "index.html")
for f in ("IBM-Regular.ttf", "IBM-Medium.ttf", "ThmanyahDisplay-Bold.woff2"):
    shutil.copy(ROOT / "brand" / "fonts" / f, site / "fonts" / f)
shutil.copy(ROOT / "brand" / "logos" / "kanz-white.png", site / "kanz-white.png")

made = {put_post(site, r) for r in results}
carry_posts(site, live, skip=made)

for ed in EDITIONS:   # the reels, unchanged
    if not live:
        break
    try:
        got = {}
        for f in ("latest.json", "latest.mp4", "latest.jpg"):
            with urllib.request.urlopen(f"{live}/{ed}/{f}", timeout=120) as r:
                got[f] = r.read()
        (site / ed).mkdir(exist_ok=True)
        for f, body in got.items():
            (site / ed / f).write_bytes(body)
        print(f"{ed}: carried over reel {json.loads(got['latest.json']).get('date')}")
    except Exception as e:  # noqa: BLE001
        print(f"{ed}: no reel on the live site ({e})")
