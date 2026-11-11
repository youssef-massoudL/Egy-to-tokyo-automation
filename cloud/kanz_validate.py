"""Cross-check for the EGX edition. Writes out/validation.json. Never changes a number except gold (spot, from Kanz).

With KANZ_DB_URL (read-only Postgres URL):
  EGX30 is final only when Kanz updated_at_tz >= 14:40 Cairo today AND Kanz price == report.json; retries until 15:10 Cairo.
  TASI / DFM / FADGI / gold must be within 0.15 points of Kanz.
Without it (single-source mode, Yahoo only):
  EGX30 must be unchanged for 10 minutes and it must be at least 14:50 Cairo; status is "SINGLE SOURCE" (release stays a draft).
RADAR_TEST=1 skips all waiting (manual test runs at any hour; status "TEST").
Exit 0 always on a finished check; status is in validation.json.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
RADAR = ROOT / "projects" / "_radar" / "run_edition.py"
REPORT = ROOT / "projects" / "market-radar-daily" / "out" / "report.json"
CAIRO = ZoneInfo("Africa/Cairo")
TOL = 0.15
KANZ = {"egx30": ("EGX", "EGX30"), "tasi": ("TADAWUL", "TASI"), "dfmgi": ("DFM", "DFMGI"), "fadgi": ("FTSE", "FADGI"), "gold": ("TVC", "GOLD")}
TEST = os.environ.get("RADAR_TEST") == "1"
DB = os.environ.get("KANZ_DB_URL", "").strip()


def report():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    return rep, {r["key"]: r for r in rep["rows"]}


def run_fetch(gold=None):
    cmd = [sys.executable, str(RADAR), "egx", "fetch"] + (["--gold-pct", str(gold)] if gold is not None else [])
    subprocess.run(cmd, check=True)


def kanz_rows():
    import psycopg2
    with psycopg2.connect(DB) as c, c.cursor() as cur:
        cur.execute("select exchange,ticker_symbol,price,change_pct,updated_at_tz from live_quotes where (exchange,ticker_symbol) in "
                    "(('EGX','EGX30'),('TADAWUL','TASI'),('DFM','DFMGI'),('FTSE','FADGI'),('TVC','GOLD'))")
        return {(r[0], r[1]): r for r in cur.fetchall()}


def with_kanz(notes):
    status = "TEST" if TEST else "OK"
    deadline = dt.datetime.now(CAIRO).replace(hour=15, minute=10, second=0, microsecond=0)
    while True:
        k = kanz_rows()
        _, rows = report()
        e = k[KANZ["egx30"]]
        upd = e[4].astimezone(CAIRO)
        now = dt.datetime.now(CAIRO)
        if TEST or (upd.date() == now.date() and upd.time() >= dt.time(14, 40) and abs(float(e[2]) - rows["egx30"]["last"]) < 0.01):
            break
        if now >= deadline:
            status = "NEEDS REVIEW"
            notes.append(f"EGX30 close not confirmed by 15:10 Cairo: Kanz {e[2]} updated {upd:%H:%M}, report {rows['egx30']['last']}")
            break
        print("EGX30 not final yet, waiting 3 min", flush=True)
        time.sleep(180)
        run_fetch()
    run_fetch(float(k[KANZ["gold"]][3]))  # rewrite data with spot gold
    _, rows = report()
    table = []
    for key in ("egx30", "tasi", "dfmgi", "fadgi", "gold"):
        kpct = float(k[KANZ[key]][3])
        if rows[key].get("closed"):
            table.append({"market": key, "shown": None, "kanz": kpct, "source2": "no session today (shown as closed)", "verdict": "closed"})
            continue
        shown = rows[key]["pct"]
        verdict = "agree" if abs(shown - kpct) <= TOL else "disagree"
        if verdict == "disagree":
            status = "NEEDS REVIEW"
            notes.append(f"{key}: shown {shown:+.2f}% vs Kanz {kpct:+.2f}%")
        table.append({"market": key, "shown": shown, "kanz": kpct, "source2": "Kanz live_quotes", "verdict": verdict})
    return status, table, ("nifty", "hsi", "kospi", "n225", "brent")


def single_source(notes):
    """No Kanz: wait until 14:50 Cairo and EGX30 unchanged for 10 minutes (re-reading Yahoo every 2 minutes)."""
    if not TEST:
        deadline = dt.datetime.now(CAIRO).replace(hour=15, minute=10, second=0, microsecond=0)
        last, since = None, None
        while True:
            _, rows = report()
            now = dt.datetime.now(CAIRO)
            if rows["egx30"]["last"] != last:
                last, since = rows["egx30"]["last"], now
            if now.time() >= dt.time(14, 50) and (now - since).total_seconds() >= 600:
                break
            if now >= deadline:
                notes.append(f"EGX30 still changing at 15:10 Cairo (last {last})")
                break
            time.sleep(120)
            run_fetch()
    notes.append("single source: no Kanz check; EGX30 not confirmed against Kanz; gold is Yahoo futures, not spot")
    _, rows = report()
    table = [{"market": "egx30", "shown": rows["egx30"]["pct"], "kanz": None, "source2": "Yahoo only, settled 10 min", "verdict": "pending"}]
    return ("TEST" if TEST else "SINGLE SOURCE"), table, ("tasi", "dfmgi", "fadgi", "nifty", "hsi", "kospi", "n225", "brent", "gold")


def main():
    notes = []
    status, table, rest = (with_kanz if DB else single_source)(notes)
    rep, rows = report()
    for key in rest:
        if rows[key].get("closed"):
            table.append({"market": key, "shown": None, "kanz": None, "source2": "no session today (shown as closed)", "verdict": "closed"})
        else:
            table.append({"market": key, "shown": rows[key]["pct"], "kanz": None, "source2": "Yahoo only", "verdict": "pending"})
    for w in rep.get("warnings", []):
        if status in ("OK", "SINGLE SOURCE") and not (TEST and "no session today" in w):
            status = "NEEDS REVIEW"
        notes.append("warning: " + w)
    if TEST:
        notes.insert(0, "TEST RUN: no waiting for the close; numbers are whatever Yahoo had at run time")
    out = {"date": rep["date"], "status": status, "notes": notes, "table": table, "egx30": rows["egx30"]["last"], "egx30_pct": rows["egx30"]["pct"]}
    (REPORT.parent / "validation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


main()
