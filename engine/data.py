"""Real data for charts (2026-10-13): fetch or read a date,value series, record its source, print a K.area array.

    python engine/data.py fred FEDFUNDS projects/<slug> [--from 2020-01] [--to 2026-09] [--every year|quarter|month]
    python engine/data.py csv path/to/file.csv projects/<slug> --source "CBE · USD/EGP" --url <page> [--from ...] [--every ...]

`fred` downloads https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES> (public, no key). `csv` reads a file you
already have (for example a Central Bank of Egypt export saved by hand): first column a date (YYYY-MM-DD, YYYY-MM or
YYYY), second a number; header rows and blanks are skipped. Either way the series is saved as
projects/<slug>/assets/data-<name>.csv and a line with the URL and capture date is added to assets/SOURCE.md, so every
number on screen stays traceable (Kanz rule: real market figures need a source on screen and in the project notes).

Prints the `data:` array for K.area, the first/last/min/max points with their dates, and a suggested `source:` line.
Only put on screen the numbers the voice says; the chart shape itself may show the whole series.
"""
import argparse
import csv
import datetime as dt
import io
import sys
import urllib.request
from pathlib import Path

FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def parse(text):
    rows = []
    for r in csv.reader(io.StringIO(text)):
        if len(r) < 2:
            continue
        d, v = r[0].strip(), r[1].strip().replace(",", "")
        try:
            val = float(v)
        except ValueError:
            continue  # header, "." (FRED's missing value) or a note line
        if len(d) == 4:
            d += "-01-01"
        elif len(d) == 7:
            d += "-01"
        try:
            dt.date.fromisoformat(d[:10])
        except ValueError:
            continue
        rows.append((d[:10], val))
    return sorted(rows)


def thin(rows, every):
    """Keep the last value of each year / quarter / month."""
    if every == "month":
        key = lambda d: d[:7]  # noqa: E731
    elif every == "quarter":
        key = lambda d: d[:4] + "Q" + str((int(d[5:7]) - 1) // 3 + 1)  # noqa: E731
    else:
        key = lambda d: d[:4]  # noqa: E731
    out = {}
    for d, v in rows:
        out[key(d)] = (d, v)
    return list(out.values())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["fred", "csv"])
    ap.add_argument("what", help="FRED series id, or a CSV path")
    ap.add_argument("project")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--to", dest="end")
    ap.add_argument("--every", choices=["year", "quarter", "month"], default="month")
    ap.add_argument("--source", help="source line text (csv mode)")
    ap.add_argument("--url", help="page the data came from (csv mode)")
    a = ap.parse_args()
    proj = Path(a.project).resolve()
    assets = proj / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()

    if a.kind == "fred":
        url = FRED.format(a.what)
        with urllib.request.urlopen(url, timeout=30) as r:
            text = r.read().decode("utf-8")
        name, label = a.what, f"FRED · {a.what}"
    else:
        src = Path(a.what)
        text = src.read_text(encoding="utf-8-sig")
        url, name, label = a.url or str(src), src.stem, a.source or src.stem
    rows = parse(text)
    if a.start:
        rows = [r for r in rows if r[0] >= a.start]
    if a.end:
        rows = [r for r in rows if r[0][: len(a.end)] <= a.end]
    rows = thin(rows, a.every)
    if len(rows) < 2:
        sys.exit("fewer than two data points after filtering: check the series id, file or --from/--to")

    out = assets / f"data-{name}.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "value"])
        w.writerows(rows)
    with (assets / "SOURCE.md").open("a", encoding="utf-8") as f:
        f.write(f"- `{out.name}`: {label}, {url}, captured {today}, {rows[0][0]} to {rows[-1][0]}, every {a.every}\n")

    vals = [v for _, v in rows]
    lo, hi = min(rows, key=lambda r: r[1]), max(rows, key=lambda r: r[1])
    d = dt.date.fromisoformat(today)
    print(f"saved {out} ({len(rows)} points) and a line in {assets / 'SOURCE.md'}")
    print(f"first {rows[0][0]} = {rows[0][1]:g} | last {rows[-1][0]} = {rows[-1][1]:g} | min {lo[0]} = {lo[1]:g} | max {hi[0]} = {hi[1]:g}")
    print("data: [" + ", ".join(f"{v:g}" for v in vals) + "]")
    print(f'source: "{label} · {f"{d.day}/{d.month}/{d.year}".translate(AR_DIGITS)}"')


if __name__ == "__main__":
    main()
