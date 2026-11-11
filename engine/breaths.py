"""List audible breaths and sighs in the final voice, as candidates for edl.json "mute".

    python engine/breaths.py <project_dir> [--min 0.35]

A breath/sigh is a stretch of noisy, pitchless sound (high spectral flatness, low periodicity)
that is loud enough to hear. Speech is voiced, silence is quiet, so both are skipped. Listen to
each candidate (or check its neighbouring words) before muting: unvoiced consonants such as
"س" or "ش" are short and stay under the minimum length.
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

SR, WIN = 16000, 0.05


def frames(path):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
    n = int(WIN * SR)
    out = []
    for i in range(len(x) // n):
        seg = x[i * n:(i + 1) * n]
        db = 20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9)
        w = seg * np.hanning(n)
        spec = np.abs(np.fft.rfft(w)) + 1e-9
        flat = np.exp(np.log(spec).mean()) / spec.mean()
        ac = np.correlate(w, w, "full")[n - 1:]
        per = ac[SR // 400:SR // 70].max() / (ac[0] + 1e-9)
        out.append((db, flat, per))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--min", type=float, default=0.35, help="shortest candidate, seconds")
    a = ap.parse_args()
    proj = Path(a.project)
    f = frames(proj / "audio" / "voice.wav")
    breathy = [(-48 < db < -18) and flat > 0.25 and per < 0.4 for db, flat, per in f]
    muted = json.loads((proj / "audio" / "edl.json").read_text(encoding="utf-8")).get("mute", []) \
        if (proj / "audio" / "edl.json").exists() else []
    found, i = [], 0
    while i < len(breathy):
        if breathy[i]:
            j = i
            while j + 1 < len(breathy) and (breathy[j + 1] or (j + 2 < len(breathy) and breathy[j + 2])):
                j += 1
            s, e = round(i * WIN, 2), round((j + 1) * WIN, 2)
            if e - s >= a.min and not any(m[0] - 0.1 <= s and e <= m[1] + 0.1 for m in muted):
                found.append([s, e])
            i = j + 1
        else:
            i += 1
    words = []
    tr = proj / "transcript.json"
    if tr.exists():
        words = [w for seg in json.loads(tr.read_text(encoding="utf-8"))["segments"] for w in seg["words"]]
    for s, e in found:
        nxt = next((w["w"] for w in words if w["start"] >= e - 0.15), "")
        print(f"{s:7.2f} - {e:7.2f}  ({e - s:.2f}s)  before: {nxt}")
    print(f"{len(found)} candidate(s). To silence one, add [start, end, \"why\"] to audio/edl.json \"mute\", "
          "then run engine/edit_audio.py (voice-note route) and re-render.")


if __name__ == "__main__":
    main()
