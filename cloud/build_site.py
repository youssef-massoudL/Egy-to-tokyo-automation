"""Build the whole GitHub Pages site: python cloud/build_site.py egx|us <out_folder> <site_dir> [<live_site_url>]
This run's edition comes from <out_folder>; the other edition is carried over from the live site (a deploy replaces the
whole site, so without this one edition would wipe the other)."""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from editions import EDITIONS  # noqa: E402
from site_reels import carry_reel, poster  # noqa: E402

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
poster(video, d / "latest.jpg")
print(f"{NAME}: {fin['status']} {video.name}")

# the other edition(s): from the live site, or from the release when the live site is behind
for other in EDITIONS:
    if other != NAME:
        carry_reel(site, other, live)

# the close posts (made by the post workflow): carried over too, so a reel deploy never wipes them
sys.path.insert(0, str(ROOT / "post"))
from site_posts import carry_posts, team  # noqa: E402
carry_posts(site, live)
team(site, live)   # the فريق كنز tab
