"""Render a project in N time slices at once, then join them without re-encoding.
Usage (from the repo root): python cloud/render_parallel.py projects/<project> --name <name> [--jobs N]
Output: projects/<project>/out/<name>.mp4 (video only; run_edition.py adds the music).

The engine renders by seeking the timeline (K.seek) frame by frame, so slices are independent: slice k gets frames
[f_k, f_k+1) through engine/render.py --from/--to. Boundaries are whole frames, so the joined video has exactly the frames
a single render would have."""
import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("project")
ap.add_argument("--name", required=True)
ap.add_argument("--jobs", type=int, default=int(os.environ.get("RADAR_JOBS", "0")) or os.cpu_count() or 2)
a = ap.parse_args()
proj = Path(a.project).resolve()
out = proj / "out"
out.mkdir(exist_ok=True)

with sync_playwright() as p:   # read the timeline length and frame rate the same way render.py does
    b = p.chromium.launch(args=["--allow-file-access-from-files"])
    pg = b.new_page(viewport={"width": 1080, "height": 1920})
    pg.goto((proj / "index.html").as_uri())
    pg.wait_for_function("window.K && document.fonts && document.fonts.status === 'loaded'")
    duration, fps, cam = pg.evaluate("[K.duration, K.fps, !!K.camSmooth]")
    b.close()
if cam:
    fps = 24
total = int(duration * fps)
jobs = max(1, min(a.jobs, total // 60))
cuts = [round(k * total / jobs) for k in range(jobs + 1)]
print(f"{total} frames at {fps} fps in {jobs} slices: {cuts}", flush=True)


def part(k):
    f0, f1 = cuts[k], cuts[k + 1]
    cmd = [sys.executable, "engine/render.py", str(proj), "--name", f"_slice{k}", "--from", repr(f0 / fps)]
    if k < jobs - 1:
        cmd += ["--to", repr(f1 / fps + 1e-7)]   # render.py takes int((to - from) * fps) frames: the epsilon keeps the last one
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    return out / f"_slice{k}.mp4"


with ThreadPoolExecutor(jobs) as ex:
    parts = list(ex.map(part, range(jobs)))
lst = out / "_slices.txt"
lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
final = out / f"{a.name}.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-map", "0:v", "-c", "copy",
                "-movflags", "+faststart", str(final)], check=True)
n = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
                    "-of", "csv=p=0", str(final)], capture_output=True, text=True, check=True).stdout.strip().strip(",")
for p in parts + [lst]:
    p.unlink(missing_ok=True)
    (out / f"{p.stem}.sfx-used.json").unlink(missing_ok=True)
if int(n) != total:
    raise SystemExit(f"joined video has {n} frames, expected {total}")
print(f"done -> {final} ({n} frames, {jobs} slices)")
