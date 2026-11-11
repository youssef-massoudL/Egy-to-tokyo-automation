"""Market Radar routine: make one edition of the market-close reel.

    python run_edition.py egx|us fetch [--wait]   wait for the closing prints (optional), read the closes, write the edition's data.js + report.json
    python run_edition.py egx|us render           render data.js, add the audio, save to New reels/Market close reels/<date>/ with a contact sheet
    python run_edition.py egx|us all [--wait]     both
    python run_edition.py egx|us check            should a scheduled run go ahead? exit 0 yes, 4 too early (a later run will do it), 5 already made today

Exit codes: 0 ok (read report.json: "warnings" lists anything to look at), 3 the edition's home market did not trade today (no reel).
Numbers come from Yahoo's chart API. The scheduled task cross-checks them against the Kanz database and a second source before rendering;
this script only applies rules it can decide alone: stale prints, a market still trading, moves too large to trust.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
ENGINE_ROOT = HERE.parent.parent           # kanz-motion
import os
OUT_ROOT = Path(os.environ["RADAR_OUT"]) if os.environ.get("RADAR_OUT") else ENGINE_ROOT.parent / "Market close reels"

# key -> Yahoo symbol, local closing time on its exchange (including the closing auction)
EDITIONS = {
    "egx": {
        "project": "market-radar-daily", "file": "kanz-market-close-cairo-tokyo", "tz": "Africa/Cairo", "home": "egx30",
        "ready": (14, 42), "give_up": (15, 10), "settle": 4,  # the final EGX30 value lands around 14:40 (4 Nov: 50,439 at 14:33, final 50,650 by 14:40)
        "markets": {"egx30": ("^CASE30", (14, 30)), "tasi": ("^TASI.SR", (15, 20)), "dfmgi": ("DFMGI.AE", (15, 0)), "fadgi": ("FADGI.FGI", (15, 0)),
                    "nifty": ("^NSEI", (15, 30)), "hsi": ("^HSI", (16, 10)), "kospi": ("^KS200", (15, 30)), "n225": ("^N225", (15, 30))},
    },
    "us": {
        "project": "market-radar-europe-us", "file": "kanz-market-close-europe-newyork", "tz": "America/New_York", "home": "spx",
        "ready": (16, 1), "give_up": (16, 25), "settle": 3,
        "markets": {"dax": ("^GDAXI", (17, 35)), "cac": ("^FCHI", (17, 35)), "ftse": ("^FTSE", (16, 35)),
                    "dow": ("^DJI", (16, 0)), "spx": ("^GSPC", (16, 0)), "ndq": ("^IXIC", (16, 0))},
    },
}
EXCHANGE_TZ = {"tasi": "Asia/Riyadh", "dfmgi": "Asia/Dubai", "fadgi": "Asia/Dubai", "nifty": "Asia/Kolkata", "hsi": "Asia/Hong_Kong", "kospi": "Asia/Seoul",
               "n225": "Asia/Tokyo", "dax": "Europe/Berlin", "cac": "Europe/Paris", "ftse": "Europe/London"}
WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
MAX_MOVE = 8.0   # a daily index move above this is held for a human look


def quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=5d&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(5):  # a dropped request must not kill a scheduled run
        try:
            res = json.load(urllib.request.urlopen(req, timeout=25))["chart"]["result"][0]
            break
        except OSError as e:
            if attempt == 4:
                raise
            print(f"  {symbol}: {e}, retrying", flush=True)
            time.sleep(15)
    meta = res["meta"]
    tz = ZoneInfo(meta["exchangeTimezoneName"])
    printed = dt.datetime.fromtimestamp(meta["regularMarketTime"], tz)
    bars = [(dt.datetime.fromtimestamp(t, tz).date(), c) for t, c in zip(res.get("timestamp", []), res["indicators"]["quote"][0]["close"]) if c]
    earlier = [c for d, c in bars if d < printed.date()]
    prev = earlier[-1] if earlier else meta.get("chartPreviousClose")   # some indices return one bar: the meta then holds the previous close
    return {"symbol": symbol, "last": meta["regularMarketPrice"], "prev": prev, "printed": printed, "tz": tz}


def wait_for_close(ed):
    """Block until the home market's closing print is in. Exit 3 if it never traded today."""
    tz = ZoneInfo(ed["tz"])
    sym = ed["markets"][ed["home"]][0]
    last, since = None, None
    while True:
        now = dt.datetime.now(tz)
        ready = now.replace(hour=ed["ready"][0], minute=ed["ready"][1], second=0, microsecond=0)
        give_up = now.replace(hour=ed["give_up"][0], minute=ed["give_up"][1], second=0, microsecond=0)
        if now >= ready:
            try:
                q = quote(sym)
            except Exception as e:  # noqa: BLE001 - network hiccups are retried
                print("  quote failed, retrying:", e, flush=True)
                q = None
            if q:
                if q["printed"].date() != now.date():
                    if now >= give_up:
                        print(f"{sym} last printed {q['printed']:%Y-%m-%d}: no session today, no reel.")
                        sys.exit(3)
                else:
                    if q["last"] != last:
                        last, since = q["last"], now
                    if now >= give_up or (now - since).total_seconds() >= ed["settle"] * 60:   # unchanged for minutes: the close has settled
                        print(f"close settled: {sym} {q['last']} printed {q['printed']:%H:%M} (now {now:%H:%M} {ed['tz']})", flush=True)
                        return
        time.sleep(60 if now >= ready else 20)


def read_market(key, symbol, close_at, warnings, ed_tz):
    q = quote(symbol)
    now = dt.datetime.now(q["tz"])
    if q["printed"].date() != now.date():
        warnings.append(f"{key}: no session today (last print {q['printed']:%a %d %b}), shown as closed")
        return {"closed": True}, {"key": key, "symbol": symbol, "closed": True, "last_print": q["printed"].isoformat()}
    # the exchange's own clock (Yahoo files some indices under another city's time zone, e.g. FADGI under London)
    local = dt.datetime.now(ZoneInfo(EXCHANGE_TZ.get(key, ed_tz)))
    if local.time() < dt.time(*close_at):
        warnings.append(f"{key}: still trading at {local:%H:%M} local (closes {close_at[0]:02d}:{close_at[1]:02d}), the number is not a close")
    pct = (q["last"] / q["prev"] - 1) * 100
    if abs(pct) > MAX_MOVE:
        warnings.append(f"{key}: {pct:+.2f}% is unusually large, check it")
    if q["last"] == q["prev"]:
        warnings.append(f"{key}: last equals previous close, possibly stale")
    return {"pct": round(pct, 2), "lvl": f"{q['last']:,.0f}"}, {"key": key, "symbol": symbol, "last": q["last"], "prev": q["prev"], "pct": round(pct, 2), "printed": q["printed"].isoformat()}


def fetch(name, gold_pct=None):
    ed = EDITIONS[name]
    today = dt.datetime.now(ZoneInfo(ed["tz"]))
    warnings, rows, mk = [], [], {}
    for key, (symbol, close_at) in ed["markets"].items():
        mk[key], row = read_market(key, symbol, close_at, warnings, ed["tz"])
        rows.append(row)
    if mk[ed["home"]].get("closed"):
        print(f"{ed['home']} did not trade today, no reel.")
        sys.exit(3)
    b, g = quote("BZ=F"), quote("GC=F")
    brent = {"price": f"{b['last']:.2f}", "pct": round((b["last"] / b["prev"] - 1) * 100, 2)}
    gold = {"pct": round((g["last"] / g["prev"] - 1) * 100, 2) if gold_pct is None else gold_pct}
    rows += [{"key": "brent", "symbol": "BZ=F", "last": b["last"], "prev": b["prev"], "pct": brent["pct"]},
             {"key": "gold", "symbol": "GC=F futures" if gold_pct is None else "spot, passed with --gold-pct (Kanz TVC:GOLD)", "last": g["last"], "prev": g["prev"], "pct": gold["pct"]}]
    day = {"weekday": WEEKDAYS[today.weekday()], "date": f"{today.day} {MONTHS[today.month - 1]} {today.year}", "mk": mk, "brent": brent, "gold": gold}
    proj = ENGINE_ROOT / "projects" / ed["project"]
    header = (f"/* Market Radar data, written by _radar/run_edition.py {today:%Y-%m-%d %H:%M} {ed['tz']}. The only file that changes from day to day.\n"
              " * pct = daily change vs the previous close; lvl = index level on the card; closed = no session that day. Sources and checks: out/report.json */\n")
    (proj / "data.js").write_text(header + "window.DAY = " + json.dumps(day, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    (proj / "out").mkdir(exist_ok=True)
    report = {"edition": name, "date": f"{today:%Y-%m-%d}", "read_at": today.isoformat(), "warnings": warnings, "rows": rows}
    (proj / "out" / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        print(f"  {r['key']:7} {'closed' if r.get('closed') else format(r['pct'], '+.2f') + '%':>9}  {r.get('last', '')}")
    for w in warnings:
        print("  WARNING:", w)
    return report


def render(name):
    ed = EDITIONS[name]
    proj = ENGINE_ROOT / "projects" / ed["project"]
    report = json.loads((proj / "out" / "report.json").read_text(encoding="utf-8"))
    date = report["date"]
    folder = OUT_ROOT / date
    folder.mkdir(parents=True, exist_ok=True)
    # two runs of one edition (a scheduled one and a manual one) must not render over each other
    lock = folder / f".{ed['file']}.rendering"
    if lock.exists() and time.time() - lock.stat().st_mtime < 20 * 60:
        print("another run is rendering this edition, stopping")
        sys.exit(5)
    lock.touch()
    try:
        return render_locked(ed, proj, report, date, folder)
    finally:
        lock.unlink(missing_ok=True)


def render_locked(ed, proj, report, date, folder):
    subprocess.run([sys.executable, "engine/render.py", f"projects/{ed['project']}", "--name", date], cwd=ENGINE_ROOT, check=True)
    final = folder / f"{ed['file']}_{date}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(proj / "out" / f"{date}.mp4"), "-i", str(HERE / "audio.m4a"), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest", str(final)], check=True)
    sheet = folder / f"{ed['file']}_{date}_sheet.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(final), "-vf", "fps=1,scale=270:-1,tile=8x3", "-frames:v", "1", "-q:v", "3", str(sheet)], check=True)
    (folder / f"{ed['file']}_{date}_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("video:", final)
    print("sheet:", sheet)
    return final


def check(name):
    ed = EDITIONS[name]
    tz = ZoneInfo(ed["tz"])
    now = dt.datetime.now(tz)
    if (OUT_ROOT / f"{now:%Y-%m-%d}" / f"{ed['file']}_{now:%Y-%m-%d}.mp4").exists():
        print("already made today")
        sys.exit(5)
    ready = now.replace(hour=ed["ready"][0], minute=ed["ready"][1], second=0, microsecond=0)
    if (ready - now).total_seconds() > 30 * 60:
        print(f"too early: {now:%H:%M} {ed['tz']}, the close is at {ready:%H:%M}")
        sys.exit(4)
    print("go")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edition", choices=EDITIONS)
    ap.add_argument("step", choices=["check", "fetch", "render", "all"])
    ap.add_argument("--wait", action="store_true", help="wait for the home market's closing print first")
    ap.add_argument("--gold-pct", type=float, help="gold spot change from Kanz (TVC:GOLD); without it gold is Yahoo's futures contract")
    a = ap.parse_args()
    if a.step == "check":
        check(a.edition)
        return
    if a.step in ("fetch", "all"):
        if a.wait:
            wait_for_close(EDITIONS[a.edition])
        fetch(a.edition, a.gold_pct)
    if a.step in ("render", "all"):
        render(a.edition)


main()
