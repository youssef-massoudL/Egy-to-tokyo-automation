"""Generate the voice with ElevenLabs and write word timings in the engine's transcript format.

    python engine/tts.py <project_dir> [--voice VOICE_ID] [--model MODEL_ID] [--speed 1.0] [--sample]
    python engine/tts.py --list-models | --list-voices

Reads ELEVENLABS_API_KEY (and optionally ELEVENLABS_VOICE_ID) from kanz-motion/.env.
Text = the caption block of <project>/script.md with *keyword* marks removed; blank lines
become paragraph pauses. Uses the /with-timestamps endpoint, so every character comes back with
start/end times; words are rebuilt from those, so captions.py works exactly as for a voice note.
Outputs <project>/audio/voice.wav (loudness-normalised) and <project>/transcript.json.
--pause SECONDS generates each paragraph separately (previous/next paragraph passed for continuity) and joins
them with that much silence (edge silence trimmed by the word timestamps; responses cached in audio/_tts): real paragraph pauses, and each question ends as a question. Default: one call.
<project>/say.json (optional) {"replace": [["as written", "as spoken"], ...]} changes only what the voice reads;
captions keep the script.md spelling (engine/captions.py re-aligns them to the spoken words).
--sample renders only the first two paragraphs to audio/sample-<speed>.wav for choosing a voice/speed.
--model defaults to the newest model id containing "v4" that the account can use.
"""
import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.elevenlabs.io/v1"


def env():
    vals = {}
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
    return vals


def call(path, key, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                 headers={"xi-api-key": key, "Content-Type": "application/json"},
                                 method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def pick_model(key):
    models = call("/models", key)
    ids = [m["model_id"] for m in models if m.get("can_do_text_to_speech", True)]
    v4 = [i for i in ids if "v4" in i and "turbo" not in i and "flash" not in i] or [i for i in ids if "v4" in i]
    if not v4:
        sys.exit("No v4 model on this account. Models: " + ", ".join(ids))
    return v4[0]


def spoken_text(md):
    body = md.split("<!-- captions:start -->")[1].split("<!-- captions:end -->")[0]
    return re.sub(r"\n{3,}", "\n\n", body.replace("*", "").strip())


sys.stdout.reconfigure(encoding="utf-8")  # Arabic in console output on Windows
LEXICON = Path(__file__).resolve().parent.parent / "library" / "voice" / "lexicon.json"


def apply_say(text, proj):
    """Voice-only spelling: the project's say.json first, then the shared lexicon of known clone failures."""
    f = proj / "say.json"
    if f.exists():
        for shown, spoken in json.loads(f.read_text(encoding="utf-8")).get("replace", []):
            if shown not in text:
                sys.exit(f"say.json: {shown!r} not found in script.md")
            text = text.replace(shown, spoken)
    if LEXICON.exists():
        for r in json.loads(LEXICON.read_text(encoding="utf-8")).get("replace", []):
            if r["from"] in text:
                print(f"lexicon: {r['from']!r} -> {r['to']!r}")
                text = text.replace(r["from"], r["to"])
    return text


def wav_dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True).stdout)


def words_from_alignment(al):
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    words, cur = [], None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur:
                words.append(cur)
            cur = None
            continue
        if cur is None:
            cur = {"w": "", "start": s, "end": e, "p": 1.0}
        cur["w"] += c
        cur["end"] = e
    if cur:
        words.append(cur)
    return [{**w, "start": round(w["start"], 3), "end": round(w["end"], 3)} for w in words]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?")
    ap.add_argument("--voice")
    ap.add_argument("--model")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--stability", type=float, default=0.5)
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--pause", type=float, help="per-paragraph generation joined by this many seconds of silence")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--list-voices", action="store_true")
    a = ap.parse_args()
    e = env()
    key = e.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("Add ELEVENLABS_API_KEY=... to kanz-motion/.env (see .env.example)")
    if a.list_models:
        for m in call("/models", key):
            print(m["model_id"], "|", m.get("name"), "| languages:", len(m.get("languages", [])))
        return
    if a.list_voices:
        for v in call("/voices", key)["voices"]:
            print(v["voice_id"], "|", v["name"], "|", v.get("category"), "|", json.dumps(v.get("labels", {}), ensure_ascii=False))
        return
    proj = Path(a.project).resolve()
    voice = a.voice or e.get("ELEVENLABS_VOICE_ID")
    if not voice:
        sys.exit("Pass --voice VOICE_ID or set ELEVENLABS_VOICE_ID in .env (python engine/tts.py --list-voices)")
    model = a.model or pick_model(key)
    text = apply_say(spoken_text((proj / "script.md").read_text(encoding="utf-8")), proj)
    if a.sample:
        text = "\n\n".join(text.split("\n\n")[:2])
    settings = {"stability": a.stability, "similarity_boost": 0.75, "speed": a.speed}
    (proj / "audio").mkdir(exist_ok=True)
    out = proj / "audio" / (f"sample-{a.speed}.wav" if a.sample else "voice.wav")

    def tts(t, prev=None, nxt=None):
        body = {"text": t, "model_id": model, "language_code": "ar", "voice_settings": settings,
                "output_format": "mp3_44100_192"}
        if prev:
            body["previous_text"] = prev
        if nxt:
            body["next_text"] = nxt
        try:
            return call(f"/text-to-speech/{voice}/with-timestamps", key, body)
        except urllib.error.HTTPError as err:
            if err.code == 400 and (prev or nxt):  # model without context support: plain call
                return tts(t)
            raise

    paras = [p for p in text.split("\n\n") if p.strip()] if a.pause is not None else [text]
    tmp = proj / "audio" / "_tts"
    tmp.mkdir(exist_ok=True)
    gap = tmp / "gap.wav"
    if a.pause:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                        "-t", str(a.pause), str(gap)], check=True)
    parts, words, t0 = [], [], 0.0
    for i, para in enumerate(paras):
        # A question gets no next_text: with the answer as context the model reads it flat, as a lead-in.
        ctx = (paras[i - 1] if i else None,
               paras[i + 1] if i + 1 < len(paras) and not para.rstrip().endswith(("؟", "?")) else None)
        # keyed on the paragraph only, so fixing one paragraph does not re-roll its neighbours
        sig = hashlib.sha1(json.dumps([para, voice, model, settings], ensure_ascii=False).encode()).hexdigest()
        cache = tmp / f"p{i:02d}.json"  # one cached response per paragraph: re-joins cost no credits
        res = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else None
        if not res or res.get("_sig") != sig:
            res = {**tts(para, *ctx), "_sig": sig}
            cache.write_text(json.dumps(res), encoding="utf-8")
        mp3, wav = tmp / f"p{i:02d}.mp3", tmp / f"p{i:02d}.wav"
        mp3.write_bytes(base64.b64decode(res["audio_base64"]))
        pw = words_from_alignment(res.get("alignment") or res["normalized_alignment"])
        a0, a1 = 0.0, None
        if a.pause is not None:  # trim the model's own edge silence so every pause is exactly --pause plus ~0.25 s
            a0, a1 = max(0.0, pw[0]["start"] - 0.05), pw[-1]["end"] + 0.2
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ss", str(a0)] + (["-to", str(a1)] if a1 else [])
        subprocess.run(cmd + ["-ar", "48000", "-ac", "1", str(wav)], check=True)
        for w in pw:
            words.append({**w, "start": round(w["start"] - a0 + t0, 3), "end": round(w["end"] - a0 + t0, 3)})
        t0 += wav_dur(wav)
        parts.append(wav)
        if a.pause and i + 1 < len(paras):
            parts.append(gap)
            t0 += a.pause
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    joined = tmp / "joined.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)],
                   check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(joined), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar", "48000", str(out)], check=True)
    if a.sample:
        print(f"sample -> {out}  (model {model}, speed {a.speed})")
        return
    dur = wav_dur(out)
    tr = {"source": "elevenlabs", "engine": "elevenlabs-with-timestamps", "model": model, "voice_id": voice,
          "speed": a.speed, "pause": a.pause, "language": "ar", "duration": round(dur, 3),
          "segments": [{"start": words[0]["start"], "end": words[-1]["end"], "text": text, "words": words}]}
    (proj / "transcript.json").write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"voice -> {out}  ({dur:.1f}s, {len(words)} words, {len(paras)} part(s), model {model}, speed {a.speed})")


if __name__ == "__main__":
    main()
