"""Weekly Market Radar data: python weekly_fetch.py <start YYYY-MM-DD> <end YYYY-MM-DD>
Weekly % = last close on or before <end> vs last close before <start>. Prints every bar used so the dates can be checked."""
import json, sys, urllib.parse, urllib.request, datetime as dt
from zoneinfo import ZoneInfo
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
start, end = (dt.date.fromisoformat(a) for a in sys.argv[1:3])
M = {"egx30": "^CASE30", "tasi": "^TASI.SR", "dfmgi": "DFMGI.AE", "fadgi": "FADGI.FGI", "nifty": "^NSEI", "hsi": "^HSI", "kospi": "^KS200", "n225": "^N225", "brent": "BZ=F", "gold": "GC=F"}
out = {}
for k, s in M.items():
    req = urllib.request.Request(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?range=1mo&interval=1d", headers={"User-Agent": "Mozilla/5.0"})
    r = json.load(urllib.request.urlopen(req, timeout=25))["chart"]["result"][0]
    tz = ZoneInfo(r["meta"]["exchangeTimezoneName"])
    bars = [(dt.datetime.fromtimestamp(t, tz).date(), c) for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c]
    # the last bar may be live: replace its close with the regular market price only if it is the meta's day
    pre = [b for b in bars if b[0] < start]
    if not pre: print(k, "NO BASE", bars[:3]); continue
    base = pre[-1]
    week = [b for b in bars if start <= b[0] <= end]
    last = week[-1]
    out[k] = {"symbol": s, "base": [str(base[0]), base[1]], "last": [str(last[0]), last[1]], "pct": round((last[1] / base[1] - 1) * 100, 2), "days": [(str(d), round(c, 2)) for d, c in week], "meta_time": dt.datetime.fromtimestamp(r["meta"]["regularMarketTime"], tz).isoformat()}
    print(f"{k:6} {out[k]['pct']:+7.2f}%  {base[0]} {base[1]:.2f} -> {last[0]} {last[1]:.2f}  (meta {out[k]['meta_time']})")
json.dump(out, open("weekly_raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
