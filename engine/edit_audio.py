"""Cut retakes out of a voice note, tighten pauses, normalise loudness, change speed.

    python engine/edit_audio.py <project_dir>

Reads <project>/audio/edl.json:
    {"source": "source.m4a", "keep": [[0, 16.18], [21.94, 35.18], ...],
     "max_pause": 0.45, "pause_to": 0.3, "speed": 1.25, "snap": 0.25}

Every keep boundary is snapped to the quietest 10 ms frame within +-snap seconds, so cuts
land in breaths rather than inside words. Silences longer than max_pause are shortened to
pause_to. Speed uses ffmpeg atempo (pitch preserved). Optional "mute": [[start, end, "why"], ...] silences ranges of the
FINAL voice (seconds as heard in the video), e.g. a sigh or breath, with short fades; timing
does not change. Output: <project>/audio/voice.wav and voice-edit.json (the snapped ranges).
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 48000
HOP = 480  # 10 ms


def decode(path):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768


def rms_frames(x):
    n = len(x) // HOP
    return np.sqrt((x[: n * HOP].reshape(n, HOP) ** 2).mean(axis=1) + 1e-12)


def snap(t, rms, win):
    a, b = max(0, int((t - win) * 100)), min(len(rms) - 1, int((t + win) * 100))
    return (a + int(np.argmin(rms[a:b + 1]))) / 100 if b > a else t


def tighten(x, max_pause, pause_to):
    rms = rms_frames(x)
    quiet = rms < max(0.004, np.percentile(rms, 20) * 1.5)
    out, i, n = [], 0, len(quiet)
    keep_frames = int(pause_to * 100)
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            run = j - i
            if run > max_pause * 100:
                h = keep_frames // 2
                out.append(x[i * HOP:(i + h) * HOP])
                out.append(x[(j - (keep_frames - h)) * HOP:j * HOP])
            else:
                out.append(x[i * HOP:j * HOP])
            i = j
        else:
            j = i
            while j < n and not quiet[j]:
                j += 1
            out.append(x[i * HOP:j * HOP])
            i = j
    out.append(x[n * HOP:])
    return np.concatenate(out)


def apply_mutes(path, mutes):
    """Silence [start, end] ranges of the final voice in place (25 ms fades at each edge)."""
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    y = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
    fade = int(0.025 * SR)
    for m in mutes:
        a, b = int(m[0] * SR), int(m[1] * SR)
        gain = np.ones(len(y), np.float32)
        gain[a:b] = 0
        gain[max(0, a - fade):a] = np.linspace(1, 0, a - max(0, a - fade))
        gain[b:b + fade] = np.linspace(0, 1, len(gain[b:b + fade]))
        y = y * gain
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", str(path)],
                   input=(np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes(), check=True)


def main(proj):
    proj = Path(proj)
    edl = json.loads((proj / "audio" / "edl.json").read_text(encoding="utf-8"))
    x = decode(proj / "audio" / edl["source"])
    rms = rms_frames(x)
    fade = int(0.012 * SR)
    ramp = np.linspace(0, 1, fade, dtype=np.float32)
    parts, snapped = [], []
    for a, b in edl["keep"]:
        a2 = snap(a, rms, edl.get("snap", 0.25)) if a > 0 else 0.0
        b2 = snap(b, rms, edl.get("snap", 0.25)) if b < len(x) / SR else len(x) / SR
        seg = x[int(a2 * SR):int(b2 * SR)].copy()
        seg[:fade] *= ramp
        seg[-fade:] *= ramp[::-1]
        parts.append(seg)
        snapped.append([round(a2, 2), round(b2, 2)])
    y = tighten(np.concatenate(parts), edl.get("max_pause", 0.45), edl.get("pause_to", 0.3))
    tmp = proj / "audio" / "_cut.wav"
    pcm = (np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", str(tmp)],
                   input=pcm, check=True)
    out = proj / "audio" / "voice.wav"
    af = f"atempo={edl.get('speed', 1.0)},highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-af", af, "-ar", str(SR), str(out)], check=True)
    tmp.unlink()
    if edl.get("mute"):
        apply_mutes(out, edl["mute"])
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True).stdout)
    (proj / "audio" / "voice-edit.json").write_text(json.dumps(
        {"source_seconds": round(len(x) / SR, 2), "kept": snapped, "cut_seconds": round(len(y) / SR, 2),
         "speed": edl.get("speed", 1.0), "final_seconds": round(dur, 2)}, indent=1), encoding="utf-8")
    print(f"source {len(x)/SR:.1f}s -> cut {len(y)/SR:.1f}s -> final {dur:.1f}s at {edl.get('speed', 1.0)}x")


if __name__ == "__main__":
    main(sys.argv[1])
