"""Build the one-shot SFX library from downloaded CC0 sources.

    python engine/sfx_library.py

Sources live in library/sfx/raw/ (downloaded, gitignored). Each long recording is split at
silences into separate hits; each hit is trimmed to max_len, faded, peak-normalised and saved as
library/sfx/<category>/<name>-NN.wav. library/sfx/manifest.json records every file's source
page and licence. Only CC0 sources are listed here, so the output can be committed and shared.
"""
import json
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "library" / "sfx" / "raw"
OUT = ROOT / "library" / "sfx"
SR = 48000

BSB = "https://bigsoundbank.com/{}.html"
CC0 = "CC0 1.0 (public domain)"

# category, name, source file (relative to RAW), source page, max hits, max length (s)
SOURCES = [
    ("paper", "page-turn", "bigsoundbank/great-page-that-turns-1-s0362.mp3", BSB.format("great-page-that-turns-1-s0362"), 2, 1.2),
    ("paper", "pages", "bigsoundbank/pages-that-turn-2-s1413.mp3", BSB.format("pages-that-turn-2-s1413"), 6, 1.0),
    ("paper", "handle", "bigsoundbank/news-paper-manipulations-s1251.mp3", BSB.format("news-paper-manipulations-s1251"), 6, 0.9),
    ("paper", "tear", "bigsoundbank/newspaper-is-torn-s0671.mp3", BSB.format("newspaper-is-torn-s0671"), 4, 1.0),
    ("whoosh", "soft", "bigsoundbank/whoosh-3-s1795.mp3", BSB.format("whoosh-3-s1795"), 1, 1.0),
    ("whoosh", "soft", "bigsoundbank/whoosh-4-s1796.mp3", BSB.format("whoosh-4-s1796"), 1, 1.1),
    ("whoosh", "short", "bigsoundbank/whoosh-5-s1797.mp3", BSB.format("whoosh-5-s1797"), 1, 0.6),
    ("whoosh", "short", "bigsoundbank/whoosh-10-s1798.mp3", BSB.format("whoosh-10-s1798"), 1, 0.5),
    ("whoosh", "set", "bigsoundbank/whoosh-1-s0572.mp3", BSB.format("whoosh-1-s0572"), 6, 1.0),
    ("whoosh", "set", "bigsoundbank/whoosh-2-s0573.mp3", BSB.format("whoosh-2-s0573"), 6, 1.0),
    ("marker", "whiteboard", "bigsoundbank/whiteboard-marker-s0807.mp3", BSB.format("whiteboard-marker-s0807"), 8, 1.0),
    ("marker", "felt", "bigsoundbank/felt-coloring-s1426.mp3", BSB.format("felt-coloring-s1426"), 6, 1.0),
    ("click", "pen", "bigsoundbank/pen-click-s0613.mp3", BSB.format("pen-click-s0613"), 6, 0.4),
    ("coin", "coins", "bigsoundbank/coins-1-s0193.mp3", BSB.format("coins-1-s0193"), 6, 1.0),
    ("coin", "coins", "bigsoundbank/coins-2-s0194.mp3", BSB.format("coins-2-s0194"), 6, 1.0),
    ("coin", "cup", "bigsoundbank/coin-in-cup-1-s0339.mp3", BSB.format("coin-in-cup-1-s0339"), 1, 0.9),
    ("tape", "stick", "bigsoundbank/adhesive-tape-1-s0297.mp3", BSB.format("adhesive-tape-1-s0297"), 4, 0.9),
    ("tape", "stick", "bigsoundbank/adhesive-tape-2-s0298.mp3", BSB.format("adhesive-tape-2-s0298"), 3, 0.9),
    ("typewriter", "keys", "bigsoundbank/typewriter-2-s2835.mp3", BSB.format("typewriter-2-s2835"), 8, 0.35),
    ("typewriter", "bell", "bigsoundbank/typewriter-bell-s2844.mp3", BSB.format("typewriter-bell-s2844"), 1, 1.6),
    ("fire", "crackle", "bigsoundbank/big-branching-fire-1-s0987.mp3", BSB.format("big-branching-fire-1-s0987"), 2, 7.0),
]
KENNEY = [
    ("click", "ui", "kenney_interface-sounds/Audio", ["click_00{}.ogg".format(i) for i in range(1, 6)]),
    ("click", "switch", "kenney_interface-sounds/Audio", ["switch_00{}.ogg".format(i) for i in range(1, 8)]),
    ("click", "select", "kenney_interface-sounds/Audio", ["select_00{}.ogg".format(i) for i in range(1, 9)]),
    ("pop", "drop", "kenney_interface-sounds/Audio", ["drop_00{}.ogg".format(i) for i in range(1, 5)]),
    ("pop", "pluck", "kenney_interface-sounds/Audio", ["pluck_00{}.ogg".format(i) for i in range(1, 3)]),
    ("hit", "soft-medium", "kenney_impact-sounds/Audio", ["impactSoft_medium_00{}.ogg".format(i) for i in range(5)]),
    ("hit", "soft-heavy", "kenney_impact-sounds/Audio", ["impactSoft_heavy_00{}.ogg".format(i) for i in range(5)]),
    ("hit", "wood-light", "kenney_impact-sounds/Audio", ["impactWood_light_00{}.ogg".format(i) for i in range(5)]),
]
KENNEY_PAGE = {"kenney_interface-sounds": "https://kenney.nl/assets/interface-sounds",
               "kenney_impact-sounds": "https://kenney.nl/assets/impact-sounds"}


def decode(path):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768


def write(path, y):
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", str(path)],
                   input=pcm, check=True)


def finish(y, max_len):
    y = y[: int(max_len * SR)].copy()
    f_in, f_out = int(0.004 * SR), min(int(0.08 * SR), len(y) // 3)
    y[:f_in] *= np.linspace(0, 1, f_in)
    y[-f_out:] *= np.linspace(1, 0, f_out)
    peak = np.abs(y).max() or 1
    return y * (0.89 / peak)  # about -1 dBFS; the mixer sets each cue's level


def split_hits(x, n, max_len):
    hop = 480
    m = len(x) // hop
    rms = np.sqrt((x[: m * hop].reshape(m, hop) ** 2).mean(axis=1) + 1e-12)
    thr = max(np.percentile(rms, 30) * 3, rms.max() * 0.06)
    loud = rms > thr
    hits, i = [], 0
    while i < m and len(hits) < n:
        if loud[i]:
            j = i
            while j < m and (loud[j] or (j + 15 < m and loud[j:j + 15].any())):
                j += 1
            if (j - i) * hop / SR > 0.05:
                start = max(0, i - 2) * hop
                hits.append(x[start:start + int(max_len * SR)])
            i = j
        i += 1
    return hits


def main():
    manifest = []
    counters = {}
    for cat, name, rel, page, n, max_len in SOURCES:
        src = RAW / rel
        if not src.exists():
            print("missing", rel)
            continue
        for h in split_hits(decode(src), n, max_len):
            k = counters[(cat, name)] = counters.get((cat, name), 0) + 1
            out = OUT / cat / f"{name}-{k:02d}.wav"
            write(out, finish(h, max_len))
            manifest.append({"file": str(out.relative_to(OUT)).replace("\\", "/"), "category": cat,
                             "source_file": Path(rel).name, "source_page": page, "license": CC0, "author": "BigSoundBank"})
    for cat, name, folder, files in KENNEY:
        for f in files:
            src = RAW / folder / f
            if not src.exists():
                continue
            k = counters[(cat, name)] = counters.get((cat, name), 0) + 1
            out = OUT / cat / f"{name}-{k:02d}.wav"
            write(out, finish(decode(src), 1.2))
            manifest.append({"file": str(out.relative_to(OUT)).replace("\\", "/"), "category": cat, "source_file": f,
                             "source_page": KENNEY_PAGE[folder.split("/")[0]], "license": CC0, "author": "Kenney (kenney.nl)"})
    gen = OUT / "generated.json"  # ElevenLabs effects from engine/sfx_gen.py; their files are not rebuilt here
    if gen.exists():
        manifest += [g for g in json.loads(gen.read_text(encoding="utf-8")) if (OUT / g["file"]).exists()]
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    by = {}
    for m in manifest:
        by[m["category"]] = by.get(m["category"], 0) + 1
    print(len(manifest), "one-shots:", by)


if __name__ == "__main__":
    main()
