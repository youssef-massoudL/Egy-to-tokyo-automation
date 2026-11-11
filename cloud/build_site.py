"""Build the static website for GitHub Pages: python cloud/build_site.py <out_folder> <site_dir>
Copies site/index.html + fonts + logo, the day's video as latest.mp4, a poster frame, and latest.json (numbers + status)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
folder, site = Path(sys.argv[1]), Path(sys.argv[2])
site.mkdir(parents=True, exist_ok=True)
(site / "fonts").mkdir(exist_ok=True)
shutil.copy(ROOT / "site" / "index.html", site / "index.html")
for f in ("IBM-Regular.ttf", "IBM-Medium.ttf", "ThmanyahDisplay-Bold.woff2"):
    shutil.copy(ROOT / "brand" / "fonts" / f, site / "fonts" / f)
shutil.copy(ROOT / "brand" / "logos" / "kanz-white.png", site / "kanz-white.png")

fin = json.loads(Path("finish.json").read_text(encoding="utf-8"))
video = folder / fin["video"]
shutil.copy(video, site / "latest.mp4")
# poster: the ranking frame near the end
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "17", "-i", str(video), "-frames:v", "1", "-vf", "scale=540:-1", "-q:v", "3", str(site / "latest.jpg")], check=True)

rep = json.loads(next(folder.glob("*_report.json")).read_text(encoding="utf-8"))
data = (ROOT / "projects" / "market-radar-daily" / "data.js").read_text(encoding="utf-8")
day = json.loads(data[data.index("window.DAY = ") + len("window.DAY = "):].rstrip().rstrip(";"))
rows = [{"key": r["key"], "closed": bool(r.get("closed")), "pct": r.get("pct")} for r in rep["rows"]]
out = {"date": rep["date"], "weekday": day["weekday"], "date_ar": day["date"], "status": fin["status"], "file": video.name, "rows": rows}
(site / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("site built:", out["date"], out["status"])
