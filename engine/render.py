"""Render a project to MP4 (or a few stills for review).

    python engine/render.py <project_dir>                 # full video -> <project>/out/<name>.mp4
    python engine/render.py <project_dir> --stills 2,8,30  # PNG stills  -> <project>/out/stills/
    python engine/render.py <project_dir> --from 20 --to 30  # partial render for quick checks

Loads <project>/index.html in headless Chromium (Playwright), calls K.seek(t) for every frame
at K.fps (12 unique frames per second, written as 24 fps), pipes JPEG frames to ffmpeg, mixes the
voice with the SFX cues the scene registered (library/sfx/manifest.json), and muxes the result.
"""
import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Arabic in the final print on Windows consoles


def decode(path):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32).reshape(-1, 2) / 32768


def load_voice(proj, seconds=60.0):
    """The project's voice, or silence when there is none (sound-effect-only clips such as intros)."""
    f = proj / "audio" / "voice.wav"
    if f.exists():
        return decode(f)
    return np.zeros((int(seconds * SR) + SR, 2), np.float32)


def env_db(x, win):
    """Running RMS level in dBFS over `win` samples (mono)."""
    sq = np.convolve(x * x, np.ones(win, np.float32) / win, "same")
    return 10 * np.log10(sq + 1e-10)


def smooth_gain(g_db, attack, release):
    """One-pole smoothing of a gain curve in dB: fast when it drops, slow when it recovers."""
    out = np.empty_like(g_db)
    a, r, cur = np.exp(-1 / attack), np.exp(-1 / release), 0.0
    for i, g in enumerate(g_db):
        k = a if g < cur else r
        cur = k * cur + (1 - k) * g
        out[i] = cur
    return out


SFX_TARGET = -18.0  # loudest-50 ms RMS every SFX file is levelled to before its scene gain (mix 2)


TARGET_LUFS = -16.0  # K.targetLufs lowers it for SFX-only exports whose voice is added later (2026-10-19)
BED_UNDER_VOICE = 21.0  # room tone sits this many dB under the voice's median speech level


def room_tone(n, seed=7):
    """A quiet, non-musical room tone (Kanz pace, 2026-10-13): brown noise with the rumble and hiss filtered off,
    plus a fainter pink layer for air. Generated, so it is fully owned and identical on every render."""
    d = n / SR + 0.1
    graph = (f"anoisesrc=color=brown:seed={seed}:amplitude=0.6:sample_rate={SR}:duration={d:.3f},highpass=f=80,lowpass=f=700[b];"
             f"anoisesrc=color=pink:seed={seed + 1}:amplitude=0.08:sample_rate={SR}:duration={d:.3f},highpass=f=300,lowpass=f=3500[p];"
             "[b][p]amix=inputs=2:normalize=0,aformat=channel_layouts=stereo")
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-filter_complex", graph, "-f", "s16le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32).reshape(-1, 2) / 32768
    a = a[:n] if len(a) >= n else np.pad(a, ((0, n - len(a)), (0, 0)))
    fade = np.ones(n, np.float32)
    k = min(n // 4, int(0.4 * SR))
    fade[:k] = np.linspace(0, 1, k)
    fade[n - k:] = np.linspace(1, 0, k)
    return a * fade[:, None]


def mix_audio_v2(proj, cues, duration, out, t0=0.0, bed=None):
    """Mix 2 (Ahmed 2026-10-11: "sometimes the sound effects are too loud"). Library files differ by up to
    20 dB inside one category, so every file is levelled first; the SFX bus ducks ~5 dB under speech and
    can never rise above the voice; then the whole mix goes to -16 LUFS with a -1 dBFS peak limit."""
    voice = load_voice(proj)
    n = int((duration - t0) * SR) + SR
    vbus = np.zeros((n, 2), np.float32)
    v = voice[int(t0 * SR):][:n]
    vbus[: len(v)] += v
    sbus = np.zeros((n, 2), np.float32)
    lib = json.loads((ROOT / "library" / "sfx" / "manifest.json").read_text(encoding="utf-8"))
    by_cat = {}
    for m in lib:
        by_cat.setdefault(m["category"], []).append(m["file"])
    cache, rng, used = {}, random.Random(7), set()
    w50 = int(0.05 * SR)
    for c in sorted(cues, key=lambda c: c["t"]):
        files = by_cat.get(c["cat"])
        if not files or c["t"] < t0:
            continue
        f = files[(c["pick"] * 7 + rng.randrange(3)) % len(files)]
        used.add(f)
        if f not in cache:
            a = decode(ROOT / "library" / "sfx" / f)
            loud = env_db(a.mean(axis=1), w50).max() if len(a) else SFX_TARGET
            cache[f] = a * np.float32(10 ** (min(SFX_TARGET - loud, 6.0) / 20))  # level it; boost at most +6 dB
        s = cache[f] * float(c["gain"]) * 0.55
        i = int((c["t"] - t0) * SR)
        j = min(n, i + len(s))
        if i < n:
            sbus[i:j] += s[: j - i]
    # duck under speech and keep the SFX bus at least 4 dB under the voice's typical speech level
    hop = int(0.01 * SR)
    vdb = env_db(vbus.mean(axis=1), int(0.03 * SR))[::hop]
    speech = vdb > -42
    vref = np.median(vdb[speech]) if speech.any() else -20.0
    sdb = env_db(sbus.mean(axis=1), w50)[::hop]
    g = np.where(speech, -5.0, 0.0)
    g = np.minimum(g, (vref - 4.0) - sdb)  # ceiling: never louder than the voice
    g = smooth_gain(np.minimum(g, 0.0), attack=2, release=25)  # 10 ms steps: 20 ms attack, 250 ms release
    gain = np.repeat(10 ** (g / 20), hop)[:n].astype(np.float32)
    if len(gain) < n:
        gain = np.pad(gain, (0, n - len(gain)), constant_values=gain[-1] if len(gain) else 1.0)
    bus = vbus + sbus * gain[:, None]
    if bed == "room":  # never digital silence between phrases (pacing study 2026-10-13)
        rt = room_tone(n)
        rdb = 10 * np.log10(np.mean(rt.mean(axis=1) ** 2) + 1e-12)
        bus += rt * np.float32(10 ** (((vref - BED_UNDER_VOICE) - rdb) / 20))
    raw = out.with_name(out.stem + "-raw.wav")
    pcm = (np.clip(bus, -1, 1) * 32767).astype(np.int16).tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", "-", str(raw)],
                   input=pcm, check=True)
    meas = subprocess.run(["ffmpeg", "-i", str(raw), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    lufs = float(meas.rsplit("I:", 1)[1].split("LUFS")[0])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
                    f"volume={TARGET_LUFS - lufs:.2f}dB,alimiter=limit=0.891:level=false:latency=true", str(out)], check=True)
    raw.unlink()
    return sorted(used)


def mix_audio(proj, cues, duration, out, t0=0.0, mix=1, bed=None):
    if mix == 2:
        return mix_audio_v2(proj, cues, duration, out, t0, bed)
    voice = load_voice(proj)
    n = int((duration - t0) * SR) + SR
    bus = np.zeros((n, 2), np.float32)
    v = voice[int(t0 * SR):][:n]
    bus[: len(v)] += v
    lib = json.loads((ROOT / "library" / "sfx" / "manifest.json").read_text(encoding="utf-8"))
    by_cat = {}
    for m in lib:
        by_cat.setdefault(m["category"], []).append(m["file"])
    cache = {}
    rng = random.Random(7)
    used = set()
    for c in sorted(cues, key=lambda c: c["t"]):
        files = by_cat.get(c["cat"])
        if not files or c["t"] < t0:
            continue
        f = files[(c["pick"] * 7 + rng.randrange(3)) % len(files)]
        used.add(f)
        if f not in cache:
            cache[f] = decode(ROOT / "library" / "sfx" / f)
        s = cache[f] * float(c["gain"]) * 0.55  # SFX sit well under the voice
        i = int((c["t"] - t0) * SR)
        j = min(n, i + len(s))
        if i < n:
            bus[i:j] += s[: j - i]
    peak = np.abs(bus).max()
    if peak > 0.98:
        bus *= 0.98 / peak
    pcm = (bus * 32767).astype(np.int16).tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", "-", str(out)],
                   input=pcm, check=True)
    return sorted(used)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--stills")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--name", default=None)
    ap.add_argument("--cam24", action="store_true", help="smooth camera even if the scene does not set K.camSmooth")
    a = ap.parse_args()
    proj = Path(a.project).resolve()
    out_dir = proj / "out"
    out_dir.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--allow-file-access-from-files"])
        page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto((proj / "index.html").as_uri())
        page.wait_for_function("document.fonts && document.fonts.status === 'loaded' && window.K")
        page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
        fonts = page.evaluate("Array.from(document.fonts).filter(f => f.status === 'loaded').map(f => f.family)")
        if errors:
            print("PAGE ERRORS:", *errors, sep="\n  ")
        duration = page.evaluate("K.duration")
        fps = page.evaluate("K.fps")
        # smooth camera (Ahmed 2026-10-11, new videos): scenes set K.camSmooth = true; capture every 24 fps frame
        # so the camera glides while graphics stay on twos. Older scenes leave it off and render as before.
        if a.cam24:
            page.evaluate("K.camSmooth = true")
        if page.evaluate("!!K.camSmooth"):
            fps = 24
        # The stage fills the 1080x1920 viewport: capture that region directly. A locator screenshot
        # waits for the element to be "stable", which intermittently times out on long renders.
        clip = {"x": 0, "y": 0, "width": 1080, "height": 1920}
        if a.stills:
            sd = out_dir / ("stills-" + (a.name or "review"))
            sd.mkdir(exist_ok=True)
            for t in [float(x) for x in a.stills.split(",")]:
                for attempt in range(4):  # same intermittent capture failure as the video loop below
                    try:
                        page.evaluate(f"K.seek({t})")
                        page.screenshot(path=str(sd / f"t{t:06.2f}.png"), clip=clip)
                        break
                    except Exception as e:  # noqa: BLE001
                        if attempt == 3:
                            raise
                        print(f"  still {t}: {str(e).splitlines()[0]} -> reopening the page", flush=True)
                        page.close()
                        page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
                        page.goto((proj / "index.html").as_uri())
                        page.wait_for_function("document.fonts && document.fonts.status === 'loaded' && window.K")
                        page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
            print("fonts:", sorted(set(fonts)), "| stills ->", sd)
            browser.close()
            return
        t1 = a.t1 if a.t1 is not None else duration
        name = a.name or proj.name
        silent = out_dir / f"_{name}-video.mp4"
        ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(fps), "-i", "-",
                               # 24 fps output as always; a scene that sets K.fps above 24 (e.g. 60 for map flights) keeps its rate
                               "-r", str(max(24, fps)), "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-maxrate", "9M", "-bufsize", "18M",
                               "-pix_fmt", "yuv420p",
                               str(silent)], stdin=subprocess.PIPE)
        frames = int((t1 - a.t0) * fps)
        def open_page():
            pg = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
            pg.goto((proj / "index.html").as_uri())
            pg.wait_for_function("document.fonts && document.fonts.status === 'loaded' && window.K")
            pg.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
            if cam_smooth:
                pg.evaluate("K.camSmooth = true")
            return pg

        cam_smooth = bool(a.cam24)
        for i in range(frames):
            # Chromium sometimes fails a screenshot after a few hundred frames when memory is low ("Unable to capture
            # screenshot", 2026-10-13 at ~7.7 s on a 1.5 GB-free machine). Reopen the page and redo that frame.
            for attempt in range(4):
                try:
                    page.evaluate(f"K.seek({a.t0 + i / fps})")
                    shot = page.screenshot(type="jpeg", quality=93, clip=clip)
                    break
                except Exception as e:  # noqa: BLE001 - playwright raises its own Error type
                    if attempt == 3:
                        raise
                    print(f"  frame {i}: {str(e).splitlines()[0]} -> reopening the page", flush=True)
                    try:
                        page.close()
                    except Exception:  # noqa: BLE001
                        pass
                    page = open_page()
            ff.stdin.write(shot)
            if i % (fps * 10) == 0:
                print(f"  frame {i}/{frames}", flush=True)
        ff.stdin.close()
        ff.wait()
        cues = page.evaluate("K.cues")
        mix = page.evaluate("K.mix || 1")
        bed = page.evaluate("K.bed || null")
        under = page.evaluate("K.bedUnder || null")  # per-video room-tone level, dB under the voice (Ahmed 2026-10-13: too loud)
        if under:
            globals()["BED_UNDER_VOICE"] = float(under)
        tgt = page.evaluate("K.targetLufs || null")
        if tgt:
            globals()["TARGET_LUFS"] = float(tgt)
        browser.close()
    audio = out_dir / f"_{name}-audio.wav"
    used = mix_audio(proj, cues, t1, audio, a.t0, mix, bed)
    final = out_dir / f"{name}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(audio), "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(final)], check=True)
    silent.unlink()
    audio.unlink()
    (out_dir / f"{name}.sfx-used.json").write_text(json.dumps({"cues": len(cues), "files": used}, indent=1), encoding="utf-8")
    print(f"done -> {final}  ({t1 - a.t0:.1f}s, {len(cues)} sfx cues, fonts: {sorted(set(fonts))})")


if __name__ == "__main__":
    main()
