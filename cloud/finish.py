"""After render: ffprobe checks, validation note, site.json, one-line result.
Usage: python cloud/finish.py egx|us <out_folder>. Writes finish.json (status, line, video)."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from editions import EDITIONS  # noqa: E402

NAME, folder = sys.argv[1], Path(sys.argv[2])
ED = EDITIONS[NAME]
ROOT = Path(__file__).resolve().parent.parent
proj = ROOT / "projects" / ED["project"]
val = json.loads((proj / "out" / "validation.json").read_text(encoding="utf-8"))
video = folder / f"{ED['file']}_{val['date']}.mp4"
probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,r_frame_rate,width,height", "-of", "json", str(video)],
                       capture_output=True, text=True, check=True)
streams = json.loads(probe.stdout)["streams"]
v = next(s for s in streams if s["codec_type"] == "video")
problems = []
if v["r_frame_rate"] != "60/1" or (v["width"], v["height"]) != (1080, 1920):
    problems.append(f"video is {v['width']}x{v['height']} {v['r_frame_rate']}, expected 1080x1920 60/1")
if not any(s["codec_type"] == "audio" for s in streams):
    problems.append("no audio stream")
status = "NEEDS REVIEW" if problems else val["status"]   # OK, SINGLE SOURCE, TEST or NEEDS REVIEW
lines = [f"# Validation: {NAME.upper()} edition, {val['date']}", f"Status: {status}", ""] + [f"- {n}" for n in val["notes"] + problems] + \
        ["", "| Market | Shown % | Second source | Result |", "|---|---|---|---|"] + \
        [f"| {r['market']} | {'closed' if r['shown'] is None else format(r['shown'], '+.2f')} | {r['source2']}{'' if r['kanz'] is None else ' ' + format(r['kanz'], '+.2f')} | {r['verdict']} |" for r in val["table"]]
(folder / f"{video.stem}_validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
if status == "NEEDS REVIEW":
    (folder / "NEEDS REVIEW.txt").write_text("\n".join(val["notes"] + problems) or "see validation note", encoding="utf-8")

# what the website shows for this edition
rep = json.loads((proj / "out" / "report.json").read_text(encoding="utf-8"))
data = (proj / "data.js").read_text(encoding="utf-8")
day = json.loads(data[data.index("window.DAY = ") + len("window.DAY = "):].rstrip().rstrip(";"))
site = {"edition": NAME, "date": rep["date"], "weekday": day["weekday"], "date_ar": day["date"], "status": status, "file": video.name,
        "rows": [{"key": r["key"], "closed": bool(r.get("closed")), "pct": r.get("pct")} for r in rep["rows"]]}
(folder / f"{video.stem}_site.json").write_text(json.dumps(site, ensure_ascii=False, indent=1), encoding="utf-8")

label = {"egx": "EGX close reel (Cairo to Tokyo)", "us": "Europe + US close reel"}[NAME]
line = f"{label} {val['date']}: {val['home'].upper()} {val['home_last']:,.2f} ({val['home_pct']:+.2f}%) - {status}" + \
       (": " + "; ".join(val["notes"] + problems) if status != "OK" else "")
Path("finish.json").write_text(json.dumps({"status": status, "line": line, "video": video.name}), encoding="utf-8")
print(line)
