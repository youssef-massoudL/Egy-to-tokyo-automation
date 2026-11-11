"""Transcribe a voice note to word-timed JSON (Arabic by default).

    python engine/transcribe.py <audio> <out.json> [--lang ar]                       # ElevenLabs Scribe v2
    uv run --with faster-whisper python engine/transcribe.py <audio> <out.json> --engine whisper

ElevenLabs Scribe v2 (default when ELEVENLABS_API_KEY is in .env) handles Egyptian Arabic well, runs
in the cloud (local Whisper ran out of memory on Windows) and tags audio events such as coughs,
sighs and laughter; those are listed under "events" so they can be cut or muted. faster-whisper
"turbo" with VAD stays as the offline fallback. Output keeps every word with start/end seconds
so beats, captions and cuts can be timed to the voice.
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path


def whisper(audio_path, lang, model_name):
    import numpy as np
    from faster_whisper import WhisperModel

    # decode with ffmpeg (16 kHz mono float) rather than PyAV, whose API drifts between versions
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", audio_path, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio, language=lang, vad_filter=True,
                                      word_timestamps=True, beam_size=5)
    segs = []
    for s in segments:
        segs.append({
            "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
            "words": [{"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3),
                       "p": round(w.probability, 3)} for w in (s.words or [])],
        })
    return segs, [], round(info.duration, 3), {"engine": "faster-whisper", "model": model_name}


def scribe(audio_path, lang):
    import eleven
    r = eleven.upload("/speech-to-text", {"model_id": "scribe_v2", "language_code": lang,
                                          "timestamps_granularity": "word", "tag_audio_events": "true"},
                      {"file": audio_path})
    words, events = [], []
    for w in r["words"]:
        if w.get("type") == "word":
            words.append({"w": w["text"].strip(), "start": round(w["start"], 3), "end": round(w["end"], 3),
                          "p": round(math.exp(w.get("logprob", 0)), 3)})
        elif w.get("type") == "audio_event":
            events.append({"event": w["text"].strip("()[] "), "start": round(w["start"], 3), "end": round(w["end"], 3)})
    # segments: break at sentence punctuation or pauses over 0.7 s, like Whisper's
    segs, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        gap = words[i + 1]["start"] - w["end"] if i + 1 < len(words) else 9
        if gap > 0.7 or w["w"][-1:] in ".؟?!":
            segs.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                         "text": " ".join(x["w"] for x in cur), "words": cur})
            cur = []
    dur = r.get("audio_duration_secs") or (words[-1]["end"] if words else 0)
    return segs, events, round(dur, 3), {"engine": "elevenlabs-scribe", "model": "scribe_v2",
                                         "transcription_id": r.get("transcription_id")}


def main():
    import eleven
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out")
    ap.add_argument("--lang", default="ar")
    ap.add_argument("--engine", choices=["elevenlabs", "whisper"],
                    default="elevenlabs" if eleven.has_key() else "whisper")
    ap.add_argument("--model", default="turbo", help="Whisper model (whisper engine only)")
    a = ap.parse_args()

    if a.engine == "elevenlabs":
        segs, events, dur, meta = scribe(a.audio, a.lang)
    else:
        segs, events, dur, meta = whisper(a.audio, a.lang, a.model)
    for s in segs:
        print(f"[{s['start']:7.2f} → {s['end']:7.2f}] {s['text']}")
    for e in events:
        print(f"  event {e['event']} at {e['start']:.2f}-{e['end']:.2f}")
    out = {
        "source": Path(a.audio).name,
        "sha256": hashlib.sha256(Path(a.audio).read_bytes()).hexdigest(),
        **meta, "language": a.lang, "duration": dur, "segments": segs, "events": events,
    }
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
