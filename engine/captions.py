"""Align the corrected script to the voice's word timings and cut it into caption chunks.

    python engine/captions.py <project_dir>

Inputs:  <project>/script.md (text between <!-- captions:start/end -->, *keyword* marks)
         <project>/transcript.json (word timings of the final edited voice)
Output:  <project>/build/timing.js  ->  window.TOKENS (every script word with start/end)
                                       window.CAPTIONS (chunks of <= 4 words / 24 chars)

Alignment uses difflib on normalised Arabic tokens; script words the recogniser missed get
times interpolated from their neighbours.
"""
import difflib
import json
import re
import sys
from pathlib import Path

PUNCT = "،؟?!.,:؛\"«»()…"


def norm(t):
    t = re.sub(r"[ً-ْـ*]", "", t)  # harakat, tatweel, keyword marks
    t = t.strip(PUNCT + " ")
    t = re.sub("[إأآ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    t = t.replace("%", "").replace("٪", "")
    t = re.sub(r"^(فال|وال|بال|لل|ال)(?=\d)", "", t)
    return t


def script_tokens(md):
    body = md.split("<!-- captions:start -->")[1].split("<!-- captions:end -->")[0]
    toks = []
    for line in [l.strip() for l in body.strip().splitlines() if l.strip()]:
        words = line.split()
        for i, w in enumerate(words):
            key = "*" in w
            toks.append({"w": w.replace("*", ""), "key": key, "eol": i == len(words) - 1})
    return toks


def main(proj):
    proj = Path(proj)
    toks = script_tokens((proj / "script.md").read_text(encoding="utf-8"))
    tr = json.loads((proj / "transcript.json").read_text(encoding="utf-8"))
    aligned = proj / "transcript.aligned.json"  # engine/align.py: the script itself, timed against the voice
    timing = json.loads(aligned.read_text(encoding="utf-8")) if aligned.exists() else tr
    asr = [w for s in timing["segments"] for w in s["words"] if norm(w["w"])]
    a = [norm(t["w"]) for t in toks]
    b = [norm(w["w"]) for w in asr]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    times = [None] * len(toks)
    for blk in sm.get_opcodes():
        tag, i1, i2, j1, j2 = blk
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                times[i1 + k] = (asr[j1 + k]["start"], asr[j1 + k]["end"])
    matched = sum(t is not None for t in times)
    # interpolate gaps
    for i, t in enumerate(times):
        if t is None:
            prev = next((times[j][1] for j in range(i - 1, -1, -1) if times[j]), 0.0)
            nxt_i = next((j for j in range(i + 1, len(times)) if times[j]), None)
            nxt = times[nxt_i][0] if nxt_i is not None else prev + 0.4
            span = (nxt_i - i + 1) if nxt_i is not None else 1
            step = (nxt - prev) / span
            times[i] = (prev, prev + step)
    for t, (s, e) in zip(toks, times):
        t["start"], t["end"] = round(s, 3), round(e, 3)

    chunks, cur = [], []
    for t in toks:
        cur.append(t)
        text = " ".join(x["w"] for x in cur)
        if t["eol"] or t["w"][-1] in "،,؟?:." or len(cur) >= 4 or len(text) >= 24:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    caps = []
    for i, c in enumerate(chunks):
        start = c[0]["start"]
        end = chunks[i + 1][0]["start"] if i + 1 < len(chunks) else c[-1]["end"] + 0.6
        caps.append({"start": round(start, 3), "end": round(min(end, c[-1]["end"] + 0.9), 3),
                     "words": [{"w": x["w"], "key": x["key"]} for x in c]})
    out = proj / "build"
    out.mkdir(exist_ok=True)
    (out / "timing.js").write_text(
        "window.TOKENS=" + json.dumps(toks, ensure_ascii=False) + ";\nwindow.CAPTIONS=" +
        json.dumps(caps, ensure_ascii=False) + ";\nwindow.DURATION=" + str(tr["duration"]) + ";\n", encoding="utf-8")
    print(f"{len(toks)} script words, {matched} matched to the voice, {len(caps)} caption chunks, {tr['duration']:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1])
