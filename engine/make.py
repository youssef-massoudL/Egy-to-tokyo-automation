"""One command per step, from voice note or written script to video, with human checkpoints between.

Voice-note route
    python engine/make.py new <name> <voice-note>   # create projects/<name>/, copy audio, raw transcript
    python engine/make.py clean <name>              # optional: ElevenLabs voice isolator on a noisy note
    python engine/make.py audio <name>              # apply audio/edl.json (cuts, pauses, speed), final transcript
Script route (ElevenLabs voice, needs .env)
    python engine/make.py script <name>             # create projects/<name>/ with a script.md to fill in
    python engine/make.py sample <name> [speed]     # first two paragraphs only, to choose voice/speed
    python engine/make.py tts <name> [speed] [pause] # script check, voice per paragraph joined by [pause] s (0.25),
                                                    # captions, then the voice check (Scribe vs script)
    python engine/make.py voicecheck <name>         # re-run the voice check alone
Both routes
    python engine/make.py breaths <name>            # list audible breaths/sighs to mute (audio/edl.json "mute")
    python engine/make.py captions <name>           # time script.md against the final voice (forced alignment)
    python engine/make.py retime <name> [tempo] [max-pause]  # pace (docs/PACE.md): pauses -> 0.3 s, tempo 1.08
                                                    # (script route default; voice notes: tempo 1.0), then captions
    python engine/sfx_gen.py <category> <name> "<prompt>"   # generate a missing sound effect into library/sfx
    python engine/make.py review <name> 2,10,30     # stills -> one contact sheet out/review.jpg
    python engine/make.py render <name> [version]   # full MP4 in projects/<name>/out/
    python engine/make.py check <name> [version]    # 12 frames pulled from the MP4 -> out/check-<version>.jpg + loudness

Between steps: write audio/edl.json (voice route), correct script.md (caption text + *keywords*),
write scene.js (the visuals). See README.md and docs/EFFICIENCY.md.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
WHISPER = ["uv", "run", "--with", "faster-whisper", "python"]
sys.path.insert(0, str(ROOT / "engine"))
import eleven  # noqa: E402

# ElevenLabs Scribe when a key is set (cloud, tags coughs/sighs); local faster-whisper otherwise
TRANSCRIBE = [PY, "engine/transcribe.py"] if eleven.has_key() else WHISPER + ["engine/transcribe.py", "--engine", "whisper"]
SCRIPT_STUB = """# Title (Arabic title)

Source: who wrote it, date. Voice: ElevenLabs (`engine/make.py tts`). The text between the markers is
spoken exactly as written and is also the caption source; `*word*` marks the caption keyword (stripped
before TTS). Blank lines are paragraph pauses.

<!-- captions:start -->
<!-- captions:end -->
"""


def run(cmd):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


def scaffold(proj):
    proj.mkdir(parents=True, exist_ok=False)
    (proj / "audio").mkdir()
    for f in ["index.html", "scene.js"]:
        shutil.copy2(ROOT / "projects" / "_template" / f, proj / f)


def captions(proj):
    # forced alignment first (cached by hash, so unchanged script + voice costs no API call)
    if eleven.has_key() and (proj / "script.md").exists() and (proj / "audio" / "voice.wav").exists():
        run([PY, "engine/align.py", proj])
    run([PY, "engine/captions.py", proj])


def sheet(src, out):
    sys.path.insert(0, str(ROOT / "engine"))
    from contact import sheet as make_sheet
    return make_sheet(src, out)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    step, name = sys.argv[1], sys.argv[2]
    arg = sys.argv[3] if len(sys.argv) > 3 else None
    proj = ROOT / "projects" / name
    out = proj / "out"
    if step in ("captions", "retime", "stills", "review", "render") and not (proj / "transcript.json").exists():
        sys.exit(f"{name} has no voice yet: run `make.py tts {name}` (script route) or `make.py audio {name}` first.")
    if step == "new":
        src = Path(arg)
        scaffold(proj)
        shutil.copy2(src, proj / "audio" / ("source" + src.suffix))
        run(TRANSCRIBE + [proj / "audio" / ("source" + src.suffix), proj / "transcript.raw.json"])
        print(f"\nNext: write {proj / 'audio' / 'edl.json'} (keep ranges, speed) from transcript.raw.json"
              ' (its "events" list coughs, sighs and laughs to cut)')
    elif step == "clean":
        src = next((proj / "audio").glob("source.*"))
        clean = proj / "audio" / "source-clean.mp3"
        clean.write_bytes(eleven.upload("/audio-isolation", {}, {"audio": src}, raw=True))
        run(TRANSCRIBE + [clean, proj / "transcript.raw.json"])
        print(f"\nIsolated voice -> {clean}. Compare it with {src.name}; if it sounds better, set"
              f' "source": "{clean.name}" in audio/edl.json (timings are unchanged).')
    elif step == "audio":
        run([PY, "engine/edit_audio.py", proj])
        run(TRANSCRIBE + [proj / "audio" / "voice.wav", proj / "transcript.json"])
        print(f"\nNext: write {proj / 'script.md'} from transcript.json (fix recognition slips, mark *keywords*)")
    elif step == "script":
        scaffold(proj)
        (proj / "script.md").write_text(SCRIPT_STUB, encoding="utf-8")
        print(f"Next: paste the copy into {proj / 'script.md'} between the markers, mark *keywords*, then sample/tts")
    elif step == "sample":
        run([PY, "engine/tts.py", proj, "--sample", "--speed", arg or "1.0"])
    elif step == "tts":
        run([PY, "engine/voicecheck.py", proj, "--pre"])
        pause = sys.argv[4] if len(sys.argv) > 4 else "0.25"
        run([PY, "engine/tts.py", proj, "--speed", arg or "1.0", "--pause", pause])
        captions(proj)
        run([PY, "engine/voicecheck.py", proj])
    elif step == "voicecheck":
        run([PY, "engine/voicecheck.py", proj])
    elif step == "breaths":
        run([PY, "engine/breaths.py", proj])
    elif step == "captions":
        captions(proj)
    elif step == "retime":
        mp = sys.argv[4] if len(sys.argv) > 4 else "0.3"
        run([PY, "engine/retime.py", proj, "--tempo", arg or "1.08", "--max-pause", mp])
        captions(proj)
    elif step in ("stills", "review"):
        captions(proj)
        run([PY, "engine/render.py", proj, "--stills", arg, "--name", "review"])
        print("review sheet ->", sheet(out / "stills-review", out / "review.jpg"))
    elif step == "render":
        captions(proj)
        run([PY, "engine/render.py", proj, "--name", f"{name}-{arg or 'v1'}"])
    elif step == "check":
        version = arg or "v1"
        mp4 = out / f"{name}-{version}.mp4"
        if not mp4.exists():  # renders named by hand, e.g. kanz-pilot-01-v2.mp4
            mp4 = max(out.glob(f"*-{version}.mp4"), key=lambda f: f.stat().st_mtime)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)],
                                   capture_output=True, text=True, check=True).stdout)
        cd = out / f"check-{version}"
        cd.mkdir(exist_ok=True)
        for f in cd.glob("*.*"):
            f.unlink()
        for i in range(12):
            t = round(dur * (i + 0.5) / 12, 1)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(mp4), "-frames:v", "1",
                            str(cd / f"f{i:02d}-{t:05.1f}s.jpg")], check=True)
        log = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(mp4), "-af", "ebur128", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
        print(f"{mp4.name}: {dur:.1f}s, integrated loudness {lufs[-1] if lufs else '?'} LUFS (target -16)")
        print("check sheet ->", sheet(cd, out / f"check-{version}.jpg"))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
