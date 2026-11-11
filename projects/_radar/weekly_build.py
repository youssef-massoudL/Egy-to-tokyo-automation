"""Write market-radar-weekly/data.js + out/report.json from weekly_raw.json (weekly_fetch.py) plus the overrides below (sources Kanz / ETF proxy)."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
raw = json.load(open(HERE / "weekly_raw.json", encoding="utf-8"))
# Yahoo returns one bar for these; Kanz candle_cache (daily) gives base and last. (key: base, last, note)
ov = {"egx30": (49596.1, 51152.7, "Kanz candle: Thu 29 Oct -> Thu 5 Nov"), "tasi": (9921.5, 10095.42, "Kanz candle: Thu 29 Oct -> Thu 5 Nov"),
      "dfmgi": (5770.73, 6025.55, "Kanz candle: Fri 30 Oct -> Fri 6 Nov (matches Yahoo Fri print)"),
      "fadgi": (9466.34, 9392.60, "Kanz candle Fri 30 Oct; Fri 6 Nov = Yahoo/Kanz live 9,392.60 (candle misses the closing print)"),
      "kospi": (783.23 / (79005 / 90800), 783.23, "KS200 Fri 6 Nov 783.23 (Yahoo); base derived from KODEX 200 ETF (069500.KS) ratio 90,800 -> 79,005")}
gold_base, gold_now = 3875.19, 4065.2   # Kanz TVC:GOLD: Fri 30 Oct close, live Fri 6 Nov 14:35 Cairo
rows, mk = [], {}
for k in ["egx30", "tasi", "dfmgi", "fadgi", "nifty", "hsi", "kospi", "n225"]:
    if k in ov:
        b, l, note = ov[k]
    else:
        b, l, note = raw[k]["base"][1], raw[k]["last"][1], f"Yahoo {raw[k]['base'][0]} -> {raw[k]['last'][0]}"
    pct = round((l / b - 1) * 100, 2)
    mk[k] = {"pct": pct, "lvl": f"{l:,.0f}"}
    rows.append({"key": k, "base": round(b, 2), "last": l, "pct": pct, "note": note})
b = raw["brent"]
brent = {"price": f"{b['last'][1]:.2f}", "pct": round((b["last"][1] / b["base"][1] - 1) * 100, 2)}
gold = {"pct": round((gold_now / gold_base - 1) * 100, 2)}
rows += [{"key": "brent", "base": b["base"][1], "last": b["last"][1], "pct": brent["pct"], "note": "Yahoo BZ=F Fri 30 Oct -> Fri 6 Nov (live, not a close)"},
         {"key": "gold", "base": gold_base, "last": gold_now, "pct": gold["pct"], "note": "Kanz TVC:GOLD Fri 30 Oct close -> live Fri 6 Nov (not a close)"}]
day = {"weekday": "الأسبوع", "date": "1 – 6 نوفمبر 2026", "mk": mk, "brent": brent, "gold": gold}
proj = HERE.parent / "market-radar-weekly"
(proj / "data.js").write_text("/* Market Radar WEEKLY data (1-6 Nov 2026), written by _radar/weekly_build.py. pct = change over the week vs the last close before it */\nwindow.DAY = " + json.dumps(day, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
(proj / "out" / "report.json").write_text(json.dumps({"edition": "weekly", "date": "2026-11-06", "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
for r in rows: print(f"{r['key']:6} {r['pct']:+7.2f}%  {r['base']:.2f} -> {r['last']:.2f}  {r['note']}")
