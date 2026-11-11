"""Tighten a finished voice without re-voicing it: shorten long pauses, then speed it up slightly.

    python engine/retime.py projects/<slug> [--tempo 1.08] [--max-pause 0.3] [--floor -40]

Pauses (below --floor dB for longer than --max-pause) are cut down to --max-pause by removing their
middle, then ffmpeg atempo (pitch kept) speeds the whole voice by --tempo. Word timings in
build/timing.js (TOKENS, CAPTIONS, DURATION) are mapped through the same cuts, so the scene's
K.T()/K.N() anchors follow the new voice. transcript.json and transcript.aligned.json are remapped too, so
`make.py review/render` (which rebuild timing.js from them) stay in sync without a new alignment call. The
originals are kept with a -pre-retime suffix; running it again starts from those, so settings do not compound.
Normally run through `python engine/make.py retime <slug> [tempo] [max-pause]`.

Pacing study 2026-10-13: the script-route voice (ElevenLabs at 1.15) runs ~2.3 words/s against
~3.3 in the voice-note Reels, and ElevenLabs caps speed at 1.2. Retiming keeps the approved take
(including spliced re-voiced lines) instead of generating a new one.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


def silences(wav, floor, min_len):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", f"silencedetect=noise={floor}dB:d={min_len}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    return list(zip(starts, ends))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--tempo", type=float, default=1.08)
    ap.add_argument("--max-pause", type=float, default=0.3)
    ap.add_argument("--floor", type=float, default=-40)
    a = ap.parse_args()
    proj = Path(a.project)
    voice, timing = proj / "audio" / "voice.wav", proj / "build" / "timing.js"
    v0, t0 = proj / "audio" / "voice-pre-retime.wav", proj / "build" / "timing-pre-retime.js"
    trs = [(proj / n, proj / n.replace(".json", "-pre-retime.json")) for n in ("transcript.json", "transcript.aligned.json")]
    # A transcript without a "retime" stamp means make.py tts/audio wrote a new voice since the last retime: refresh the
    # originals from it, or the old take would be retimed again (gamblers-fallacy 2026-10-14: a pronunciation fix was lost).
    tr_now = proj / "transcript.json"
    fresh = tr_now.exists() and "retime" not in json.loads(tr_now.read_text(encoding="utf-8"))
    if not v0.exists() or fresh:
        shutil.copy(voice, v0)
        if timing.exists():
            shutil.copy(timing, t0)
        for cur, pre in trs:
            if cur.exists():
                shutil.copy(cur, pre)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v0)],
                               capture_output=True, text=True).stdout)

    # keep-segments: everything except the middle of each long pause (keep max_pause/2 at both edges)
    cuts = []
    for s, e in silences(v0, a.floor, a.max_pause):
        if e >= dur - 0.05:  # trailing silence: leave it, the scene decides the ending
            continue
        h = a.max_pause / 2
        cuts.append((s + h, e - h))
    keep, cur = [], 0.0
    for s, e in cuts:
        keep.append((cur, s))
        cur = e
    keep.append((cur, dur))

    def remap(t):
        """Original time -> new time (inside a removed span, snap to its start)."""
        out = 0.0
        for s, e in keep:
            if t <= s:
                break
            out += min(t, e) - s
            if t <= e:
                break
        return round(out / a.tempo, 3)

    parts = "".join(f"[0:a]atrim={s:.4f}:{e:.4f},asetpts=PTS-STARTPTS[a{i}];" for i, (s, e) in enumerate(keep))
    graph = parts + "".join(f"[a{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=0:a=1[c];[c]atempo={a.tempo}[o]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(v0), "-filter_complex", graph, "-map", "[o]", str(voice)], check=True)

    # transcripts (segments -> words with start/end), remapped the same way
    for cur, pre in trs:
        if not pre.exists():
            continue
        tr = json.loads(pre.read_text(encoding="utf-8"))
        for seg in tr.get("segments", []):
            for k in ("start", "end"):
                if k in seg:
                    seg[k] = remap(seg[k])
            for w in seg.get("words", []):
                for k in ("start", "end"):
                    if k in w:
                        w[k] = remap(w[k])
        if "duration" in tr:
            tr["duration"] = remap(tr["duration"])
        tr["retime"] = {"tempo": a.tempo, "max_pause": a.max_pause, "pauses_cut": len(cuts)}
        if "sha256" in tr:  # engine/align.py cache key: keep it valid for the retimed voice (same text)
            text = tr["segments"][0]["text"] if tr.get("segments") else ""
            tr["sha256"] = hashlib.sha256(voice.read_bytes() + text.encode()).hexdigest()
        cur.write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")

    if not t0.exists():
        print(f"voice retimed; no build/timing.js yet (run make.py captions)")
        return
    src = t0.read_text(encoding="utf-8")
    tokens = json.loads(re.search(r"window\.TOKENS=(\[.*?\]);", src, re.S).group(1))
    caps = json.loads(re.search(r"window\.CAPTIONS=(\[.*?\]);", src, re.S).group(1))
    old_d = float(re.search(r"window\.DURATION=([\d.]+)", src).group(1))
    for tk in tokens:
        tk["start"], tk["end"] = remap(tk["start"]), remap(tk["end"])
    for c in caps:
        c["start"], c["end"] = remap(c["start"]), remap(c["end"])
        for w in c.get("words", []):
            for k in ("start", "end"):
                if k in w:
                    w[k] = remap(w[k])
    new_d = remap(old_d)
    timing.write_text(f"window.TOKENS={json.dumps(tokens, ensure_ascii=False)};\nwindow.CAPTIONS={json.dumps(caps, ensure_ascii=False)};\n"
                      f"window.DURATION={new_d};\n", encoding="utf-8")
    removed = sum(e - s for s, e in cuts)
    print(f"{len(cuts)} pauses shortened ({removed:.2f} s removed), tempo {a.tempo}: {old_d:.2f} s -> {new_d:.2f} s")


if __name__ == "__main__":
    main()
