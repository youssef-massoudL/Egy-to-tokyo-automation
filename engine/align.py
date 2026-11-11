"""Time the corrected script word by word against the final voice (ElevenLabs forced alignment).

    python engine/align.py <project_dir> [--force]

Sends audio/voice.wav and the spoken text of script.md (between the caption markers, *marks*
removed) to /v1/forced-alignment and writes <project>/transcript.aligned.json in the transcript
format, with every script word in order. captions.py prefers it over transcript.json, so captions
follow the exact script instead of ASR guesses. Skipped (no API call) when the script and voice
are unchanged since the last alignment, or when the voice came from ElevenLabs TTS (already exact).
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import eleven


def spoken_text(md):
    body = md.split("<!-- captions:start -->")[1].split("<!-- captions:end -->")[0]
    return re.sub(r"\n{3,}", "\n\n", body.replace("*", "").strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    proj = Path(a.project).resolve()
    voice, out = proj / "audio" / "voice.wav", proj / "transcript.aligned.json"
    tr = proj / "transcript.json"
    if tr.exists() and json.loads(tr.read_text(encoding="utf-8")).get("source") == "elevenlabs":
        print("voice is ElevenLabs TTS: its timings are already exact, no alignment needed")
        return
    if not voice.exists() or not (proj / "script.md").exists():
        sys.exit(f"align needs {voice} and script.md")
    text = spoken_text((proj / "script.md").read_text(encoding="utf-8"))
    digest = hashlib.sha256(voice.read_bytes() + text.encode()).hexdigest()
    if out.exists() and not a.force and json.loads(out.read_text(encoding="utf-8")).get("sha256") == digest:
        print("alignment up to date")
        return
    r = eleven.upload("/forced-alignment", {"text": text}, {"file": voice})
    words = [{"w": w["text"].strip(), "start": round(w["start"], 3), "end": round(w["end"], 3),
              "p": round(max(0.0, 1 - w.get("loss", 0)), 3)}
             for w in r["words"] if w["text"].strip()]
    dur = json.loads(tr.read_text(encoding="utf-8"))["duration"] if tr.exists() else words[-1]["end"]
    out.write_text(json.dumps({"source": voice.name, "sha256": digest, "engine": "elevenlabs-forced-alignment",
                               "loss": round(r.get("loss", 0), 4), "duration": dur,
                               "segments": [{"start": words[0]["start"], "end": words[-1]["end"], "text": text,
                                             "words": words}]}, ensure_ascii=False, indent=1), encoding="utf-8")
    # words fitting far worse than the rest (mean + 2 sd of loss): usually digits written differently from
    # how they are spoken, or script words the voice does not say. Check their captions.
    loss = [1 - w["p"] for w in words]
    m = sum(loss) / len(loss)
    sd = (sum((x - m) ** 2 for x in loss) / len(loss)) ** 0.5
    shaky = [w for w, x in zip(words, loss) if x > m + 2 * sd]
    print(f"aligned {len(words)} script words (loss {r.get('loss', 0):.3f}); check these captions: "
          + (", ".join(f"{w['w']}@{w['start']:.1f}s" for w in shaky[:15]) or "none"))


if __name__ == "__main__":
    main()
