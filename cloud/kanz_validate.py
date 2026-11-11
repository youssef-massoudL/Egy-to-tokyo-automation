"""Cloud version of the Kanz cross-check for the EGX edition. Never changes a number except gold (spot, from Kanz).

Usage: python cloud/kanz_validate.py   (env KANZ_DB_URL = read-only Postgres URL)
Rule: EGX30 is final only when Kanz updated_at_tz >= 14:40 Cairo today AND Kanz price == report.json.
Retries (re-running fetch) until 15:10 Cairo. Exit 0 = OK, 6 = NEEDS REVIEW (reasons in validation.json).
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
RADAR = ROOT / "projects" / "_radar" / "run_edition.py"
REPORT = ROOT / "projects" / "market-radar-daily" / "out" / "report.json"
CAIRO = ZoneInfo("Africa/Cairo")
TOL = 0.15
KANZ = {"egx30": ("EGX", "EGX30"), "tasi": ("TADAWUL", "TASI"), "dfmgi": ("DFM", "DFMGI"), "fadgi": ("FTSE", "FADGI"), "gold": ("TVC", "GOLD")}


def kanz_rows():
    with psycopg2.connect(os.environ["KANZ_DB_URL"]) as c, c.cursor() as cur:
        cur.execute("select exchange,ticker_symbol,price,change_pct,updated_at_tz from live_quotes where (exchange,ticker_symbol) in "
                    "(('EGX','EGX30'),('TADAWUL','TASI'),('DFM','DFMGI'),('FTSE','FADGI'),('TVC','GOLD'))")
        return {(r[0], r[1]): r for r in cur.fetchall()}


def run_fetch(gold=None):
    cmd = [sys.executable, str(RADAR), "egx", "fetch"] + (["--gold-pct", str(gold)] if gold is not None else [])
    subprocess.run(cmd, check=True)


def main():
    notes, status = [], "OK"
    deadline = dt.datetime.now(CAIRO).replace(hour=15, minute=10, second=0, microsecond=0)
    while True:
        k = kanz_rows()
        rep = json.loads(REPORT.read_text(encoding="utf-8"))
        rows = {r["key"]: r for r in rep["rows"]}
        e = k[KANZ["egx30"]]
        upd = e[4].astimezone(CAIRO)
        now = dt.datetime.now(CAIRO)
        final = upd.date() == now.date() and upd.time() >= dt.time(14, 40) and abs(float(e[2]) - rows["egx30"]["last"]) < 0.01
        if final:
            break
        if now >= deadline:
            status = "NEEDS REVIEW"
            notes.append(f"EGX30 close not confirmed by 15:10 Cairo: Kanz {e[2]} updated {upd:%H:%M}, report {rows['egx30']['last']}")
            break
        print("EGX30 not final yet, waiting 3 min", flush=True)
        time.sleep(180)
        run_fetch()
    gold = float(k[KANZ["gold"]][3])
    run_fetch(gold)  # rewrite data with spot gold
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    rows = {r["key"]: r for r in rep["rows"]}
    table = []
    for key in ("egx30", "tasi", "dfmgi", "fadgi", "gold"):
        kr = k[KANZ[key]]
        shown = rows[key]["pct"]
        verdict = "agree" if abs(shown - float(kr[3])) <= TOL else "disagree"
        if verdict == "disagree":
            status = "NEEDS REVIEW"
            notes.append(f"{key}: shown {shown:+.2f}% vs Kanz {float(kr[3]):+.2f}%")
        table.append({"market": key, "shown": shown, "kanz": float(kr[3]), "source2": "Kanz live_quotes", "verdict": verdict})
    for key in ("nifty", "hsi", "kospi", "n225", "brent"):
        table.append({"market": key, "shown": rows[key]["pct"], "kanz": None, "source2": "Yahoo only (no automated second source)", "verdict": "pending"})
    for w in rep.get("warnings", []):
        status = "NEEDS REVIEW"
        notes.append("warning: " + w)
    out = {"date": rep["date"], "status": status, "notes": notes, "table": table, "egx30": rows["egx30"]["last"], "egx30_pct": rows["egx30"]["pct"]}
    (REPORT.parent / "validation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(6 if status != "OK" else 0)


main()
