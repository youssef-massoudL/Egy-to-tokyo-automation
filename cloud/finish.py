"""After render: ffprobe checks, validation note, one-line result. Usage: python cloud/finish.py <out_folder>. Writes finish.json."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
folder = Path(sys.argv[1])
val = json.loads((ROOT / "projects" / "market-radar-daily" / "out" / "validation.json").read_text(encoding="utf-8"))
video = next(p for p in folder.glob("kanz-market-close-cairo-tokyo_*.mp4"))
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
lines = [f"# Validation: EGX edition, {val['date']}", f"Status: {status}", ""] + [f"- {n}" for n in val["notes"] + problems] + \
        ["", "| Market | Shown % | Second source | Result |", "|---|---|---|---|"] + \
        [f"| {r['market']} | {'closed' if r['shown'] is None else format(r['shown'], '+.2f')} | {r['source2']}{'' if r['kanz'] is None else ' ' + format(r['kanz'], '+.2f')} | {r['verdict']} |" for r in val["table"]]
(folder / f"{video.stem}_validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
if status == "NEEDS REVIEW":
    (folder / "NEEDS REVIEW.txt").write_text("\n".join(val["notes"] + problems) or "see validation note", encoding="utf-8")
line = f"EGX close reel {val['date']}: EGX30 {val['egx30']:,.1f} ({val['egx30_pct']:+.2f}%) - {status}" + (": " + "; ".join(val["notes"] + problems) if status != "OK" else "")
Path("finish.json").write_text(json.dumps({"status": status, "line": line, "video": video.name}), encoding="utf-8")
print(line)
