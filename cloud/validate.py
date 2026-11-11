"""Cross-check one edition. Usage: python cloud/validate.py egx|us. Writes projects/<project>/out/validation.json.
Never changes a number except EGX gold (spot, from Kanz).

EGX with KANZ_DB_URL (read-only Postgres URL):
  EGX30 is final only when Kanz updated_at_tz >= 14:40 Cairo today AND Kanz price == report.json; retries until 15:10 Cairo.
  TASI / DFM / FADGI / gold must be within 0.15 points of Kanz.
Otherwise (US always, EGX without the secret) single source, Yahoo only:
  the home index must be unchanged for N minutes after a set time (EGX 10 min after 14:50 Cairo, US 5 min after 16:05 New York).
  Status "SINGLE SOURCE": published with a note on the website.
A market with no session today is shown closed and noted, not held (weekends and holidays are normal).
Any other fetch warning (still trading, huge move, stale print) -> NEEDS REVIEW (draft, not on the website).
RADAR_TEST=1 skips all waiting (manual test runs at any hour; status "TEST").
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from editions import EDITIONS  # noqa: E402

NAME = sys.argv[1]
ED = EDITIONS[NAME]
ROOT = Path(__file__).resolve().parent.parent
RADAR = ROOT / "projects" / "_radar" / "run_edition.py"
REPORT = ROOT / "projects" / ED["project"] / "out" / "report.json"
TZ = ZoneInfo(ED["tz"])
HOME = ED["home"]
TOL = 0.15
KANZ = {"egx30": ("EGX", "EGX30"), "tasi": ("TADAWUL", "TASI"), "dfmgi": ("DFM", "DFMGI"), "fadgi": ("FTSE", "FADGI"), "gold": ("TVC", "GOLD")}
TEST = os.environ.get("RADAR_TEST") == "1"
DB = os.environ.get("KANZ_DB_URL", "").strip() if ED["kanz"] else ""


def report():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    return rep, {r["key"]: r for r in rep["rows"]}


def run_fetch(gold=None):
    cmd = [sys.executable, str(RADAR), NAME, "fetch"] + (["--gold-pct", str(gold)] if gold is not None else [])
    subprocess.run(cmd, check=True)


def at(hm):
    return dt.datetime.now(TZ).replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)


def kanz_rows():
    import psycopg2
    with psycopg2.connect(DB) as c, c.cursor() as cur:
        cur.execute("select exchange,ticker_symbol,price,change_pct,updated_at_tz from live_quotes where (exchange,ticker_symbol) in "
                    "(('EGX','EGX30'),('TADAWUL','TASI'),('DFM','DFMGI'),('FTSE','FADGI'),('TVC','GOLD'))")
        return {(r[0], r[1]): r for r in cur.fetchall()}


def with_kanz(notes):
    status = "TEST" if TEST else "OK"
    while True:
        k = kanz_rows()
        _, rows = report()
        e = k[KANZ["egx30"]]
        upd = e[4].astimezone(TZ)
        now = dt.datetime.now(TZ)
        if TEST or (upd.date() == now.date() and upd.time() >= dt.time(14, 40) and abs(float(e[2]) - rows["egx30"]["last"]) < 0.01):
            break
        if now >= at(ED["give_up"]):
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
    return status, table


def single_source(notes):
    if not TEST:
        last, since = None, None
        mins = ED["stable_secs"] // 60
        while True:
            _, rows = report()
            now = dt.datetime.now(TZ)
            if rows[HOME]["last"] != last:
                last, since = rows[HOME]["last"], now
            if now >= at(ED["stable_after"]) and (now - since).total_seconds() >= ED["stable_secs"]:
                break
            if now >= at(ED["give_up"]):
                notes.append(f"{HOME} still changing at {ED['give_up'][0]}:{ED['give_up'][1]:02d} local (last {last})")
                break
            time.sleep(60)
            run_fetch()
        notes.append(f"single source: Yahoo only; {HOME} unchanged {mins} min before use" + ("; not confirmed against Kanz; gold is futures, not spot" if NAME == "egx" else ""))
    return ("TEST" if TEST else "SINGLE SOURCE"), []


def main():
    notes = []
    status, table = (with_kanz if DB else single_source)(notes)
    rep, rows = report()
    done = {r["market"] for r in table}
    for r in rep["rows"]:
        if r["key"] in done:
            continue
        if r.get("closed"):
            table.append({"market": r["key"], "shown": None, "kanz": None, "source2": "no session today (shown as closed)", "verdict": "closed"})
        else:
            table.append({"market": r["key"], "shown": r["pct"], "kanz": None, "source2": "Yahoo only", "verdict": "pending"})
    for w in rep.get("warnings", []):
        if "no session today" not in w and status in ("OK", "SINGLE SOURCE"):
            status = "NEEDS REVIEW"
        notes.append("warning: " + w)
    if TEST:
        notes.insert(0, "TEST RUN: no waiting for the close; numbers are whatever Yahoo had at run time")
    out = {"edition": NAME, "date": rep["date"], "status": status, "notes": notes, "table": table,
           "home": HOME, "home_last": rows[HOME]["last"], "home_pct": rows[HOME]["pct"]}
    (REPORT.parent / "validation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


main()
