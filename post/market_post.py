"""Kanz market-close post (EGX and Tadawul): fetch, wait for the final close, write the Arabic text, render two PNGs, validate.

Usage (from the repo root):
  python post/market_post.py egx|tasi [--test] [--history FILE.json] [--out DIR]

  --test      render now with whatever TradingView shows (no waiting, status TEST)
  --history   daily closes as JSON [["2026-11-19", 51458.0], ...] instead of the Kanz database (local tests without KANZ_DB_URL)
  --out       output root (default out/posts); files land in <out>/<date>/

Sources:
  TradingView scanner (public, 15-minute delay): the five indices, and every stock in the home index for breadth and share volume.
  Kanz database (KANZ_DB_URL, read-only): daily closes of the home index for week / streak / "lowest since",
  and live_quotes to confirm the close is final.
Rules copied from the approved 19 Nov 2026 posts:
  - a company counts as up only if its price rose; unchanged companies count with the decliners.
  - trading share = number of shares traded (not value), split between rising and non-rising companies.
  - weeks run Sunday to Thursday; the week change is measured from the previous week's last close.
Exit codes: 0 made (any status), 3 the market did not trade today, 4 too early (before the close), 5 already made today.
Writes <out>/<date>/kanz-close-post-<market>_<date>_{wide,tall}.png, _data.json, _validation.md, and post_result.json in the cwd.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

MARKETS = {
    "egx": {
        "tz": "Africa/Cairo", "city": "القاهرة", "currency": "بالجنيه", "home": "EGX:EGX30", "kanz": ("EGX", "EGX30"),
        "scan": "egypt", "head": "المؤشر", "name": "EGX30", "sub_name": "EGX30 ", "card_name": "المؤشر",
        "breadth_note": " في EGX30", "subs_note": "تغيّرات المؤشرات الفرعية وفوتسي مصر من تريدنج فيو عند الإغلاق",
        "open": (10, 0), "close": (14, 30), "final_after": (14, 45), "give_up": (15, 45),
        "logo": {"xchg": "egx-logo.png", "kanz": [84, 38, 56], "box": [358.2, 30.9, 77.7]},
        "indices": [  # (TradingView symbol, bar label, short name for text)
            ("EGX:EGX30", "أكبر 30 شركة EGX30", "أكبر 30 شركة"),
            ("EGX:EGX30CAPPED", "أكبر 30 شركة بسقف للأوزان", "مؤشر الأوزان المحددة"),
            ("FTSE:WIEGY", "مؤشر فوتسي مصر", "فوتسي مصر"),
            ("EGX:EGX100EWI", "أكبر 100 شركة EGX100", "أكبر 100 شركة"),
            ("EGX:EGX70EWI", "الشركات المتوسطة والصغيرة EGX70", "الشركات المتوسطة والصغيرة"),
        ],
        "masc": ("مؤشر الأوزان المحددة", "فوتسي مصر"),   # take a masculine verb (هبط / صعد)
    },
    "tasi": {
        "tz": "Asia/Riyadh", "city": "الرياض", "currency": "بالريال", "home": "TADAWUL:TASI", "kanz": ("TADAWUL", "TASI"),
        "scan": "ksa", "head": "تاسي", "name": "تاسي", "sub_name": "", "card_name": "تاسي",
        "breadth_note": "", "subs_note": "تغيّرات المؤشرات الفرعية من تريدنج فيو عند الإغلاق",
        "open": (10, 0), "close": (15, 0), "final_after": (15, 25), "give_up": (16, 15),
        "logo": {"xchg": "saudi-exchange-logo.png", "kanz": [82.4, 36.7, 46.9], "box": [302.7, 37.1, 66.4]},
        "indices": [
            ("TADAWUL:TASI", "المؤشر العام تاسي", "تاسي"),
            ("TADAWUL:MT30", "أكبر 30 شركة MT30", "أكبر 30 شركة"),
            ("TADAWUL:TDFI", "الخدمات المالية", "الخدمات المالية"),
            ("TADAWUL:TBNI", "البنوك", "البنوك"),
            ("TADAWUL:NOMUC", "السوق الموازية نمو NOMUC", "السوق الموازية"),
        ],
        "masc": (),
    },
}
FILE = "kanz-close-post-{m}_{d}"
STABLE_SECS = 480          # the home index must hold the same value this long before it counts as the close
POLL_SECS = 60
TRADING_DAYS = (6, 0, 1, 2, 3)   # Sun..Thu (Python weekday numbers)

DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
ORD = {2: "ثاني", 3: "ثالث", 4: "رابع", 5: "خامس", 6: "سادس", 7: "سابع", 8: "ثامن", 9: "تاسع", 10: "عاشر"}
FEM = {3: "ثلاث", 4: "أربع", 5: "خمس", 6: "ست", 7: "سبع", 8: "ثماني", 9: "تسع", 10: "عشر"}
MASC = {3: "ثلاثة", 4: "أربعة", 5: "خمسة", 6: "ستة", 7: "سبعة", 8: "ثمانية", 9: "تسعة", 10: "عشرة"}
MINUS = "−"


# ---------------------------------------------------------------- Arabic helpers
def f2(x):
    return f"{x:,.2f}"


def dm(d):
    return f"{d.day} {MONTHS[d.month - 1]}"


def wdm(d):
    return f"{DAYS[d.weekday()]} {dm(d)}"


def signed_pct(x):
    return f'<span class="ltr">{"+" if x > 0 else MINUS if x < 0 else ""}{abs(x):.2f}%</span>'


def color(x):
    return "green" if x > 0 else "red" if x < 0 else "neutral"


def companies(n):
    return "شركات" if 3 <= n % 100 <= 10 else "شركة"


def shares_of_100(n):           # "74 سهمًا", "5 أسهم"
    if n == 1:
        return "سهم واحد"
    if n == 2:
        return "سهمان"
    if 3 <= n <= 10:
        return f"{n} أسهم"
    if 11 <= n <= 99:
        return f"{n} سهمًا"
    return f"{n} سهم"


def sessions(n):                # "ثلاث جلسات"
    if n == 2:
        return "جلستين"
    if n in FEM:
        return f"{FEM[n]} جلسات"
    return f"{n} جلسة"


def weeks(n, win):              # "أسبوعين رابحين", "ثلاثة أسابيع رابحة"
    adj1, adj2, adjp = ("رابح", "رابحين", "رابحة") if win else ("خاسر", "خاسرين", "خاسرة")
    if n == 1:
        return f"أسبوع {adj1}"
    if n == 2:
        return f"أسبوعين {adj2}"
    if n in MASC:
        return f"{MASC[n]} أسابيع {adjp}"
    return f"{n} أسبوعًا {adj1}ًا"


def ordinal(n):
    return ORD.get(n, f"الـ{n}")


def today_month(now):
    return now.month - 1


# ---------------------------------------------------------------- sources
def tv_scan(market, body):
    req = urllib.request.Request(f"https://scanner.tradingview.com/{market}/scan", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    for attempt in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:  # noqa: BLE001  (network hiccup: retry a few times)
            if attempt == 3:
                raise
            print("TradingView retry:", e, flush=True)
            time.sleep(10)


def tv_indices(cfg):
    cols = ["close", "change", "change_abs", "close[1]", "time", "high", "low"]
    d = tv_scan("global", {"symbols": {"tickers": [s for s, _, _ in cfg["indices"]]}, "columns": cols})
    got = {r["s"]: dict(zip(cols, r["d"])) for r in d["data"]}
    return got


def tv_breadth(cfg):
    d = tv_scan(cfg["scan"], {"filter": [{"left": "type", "operation": "equal", "right": "stock"}],
                              "columns": ["name", "change", "volume", "indexes"], "range": [0, 2000]})
    rows = [r["d"] for r in d["data"] if any(i.get("proname") == cfg["home"] for i in (r["d"][3] or []))]
    up = [r for r in rows if (r[1] or 0) > 0]
    rest = [r for r in rows if not (r[1] or 0) > 0]          # unchanged counts with the decliners (approved posts)
    vu = sum(r[2] or 0 for r in up)
    vd = sum(r[2] or 0 for r in rest)
    vol_down = round(100 * vd / (vu + vd)) if vu + vd else 0
    return {"total": len(rows), "up": len(up), "down": len(rest), "flat": sum(1 for r in rows if not r[1]),
            "vol_down_pct": vol_down, "vol_up_pct": 100 - vol_down}


def kanz_conn():
    url = os.environ.get("KANZ_DB_URL", "").strip()
    if not url:
        return None
    import psycopg2
    return psycopg2.connect(url)


def kanz_history(cfg, tz):
    """Daily closes of the home index, oldest first, as [(date, close)], from Kanz candle_cache (split-adjusted, newest bar may be forming)."""
    with kanz_conn() as c, c.cursor() as cur:
        cur.execute("select time_unix, close from candle_cache where resolution='D' and exchange=%s and ticker_symbol=%s "
                    "and time_unix > extract(epoch from now() - interval '500 days') order by time_unix", cfg["kanz"])
        return [(dt.datetime.fromtimestamp(t, tz).date(), float(cl)) for t, cl in cur.fetchall()]


def kanz_live(cfg):
    with kanz_conn() as c, c.cursor() as cur:
        cur.execute("select price, change_pct, updated_at_tz from live_quotes where exchange=%s and ticker_symbol=%s", cfg["kanz"])
        return cur.fetchone()


# ---------------------------------------------------------------- history facts
def facts(hist, today, close):
    """hist: [(date, close)] before today (oldest first). Returns streak / since / level / floor / week facts."""
    h = [(d, c) for d, c in hist if d < today] + [(today, close)]
    closes = [c for _, c in h]
    n = len(h)
    chg = close - closes[-2]
    sign = (chg > 0) - (chg < 0)
    f = {"prev_date": h[-2][0], "prev_close": closes[-2], "change": chg, "sign": sign}

    # streak of sessions moving the same way, and the points over it
    k = 0
    for i in range(n - 1, 0, -1):
        s = (closes[i] > closes[i - 1]) - (closes[i] < closes[i - 1])
        if s != sign or s == 0:
            break
        k += 1
    f["streak"] = k
    f["streak_pts"] = close - closes[n - 1 - k] if k else 0

    # lowest (highest) close since D: D = the most recent earlier close beyond today
    f["since"] = None
    if sign:
        for i in range(n - 2, -1, -1):
            if (closes[i] < close) if sign < 0 else (closes[i] > close):
                gap = n - 2 - i                       # sessions between D and today
                if gap >= 2:
                    between = h[i + 1:n - 1]
                    ref = min(between, key=lambda x: x[1]) if sign < 0 else max(between, key=lambda x: x[1])
                    f["since"] = {"date": h[i][0], "close": closes[i], "diff": abs(close - closes[i]), "gap": gap,
                                  "level_date": ref[0], "level_close": ref[1], "level_diff": abs(ref[1] - close)}
                    # floor (ceiling): the most recent swing low (high) before D that is still beyond today
                    for j in range(i - 1, 0, -1):
                        a, b, c2 = closes[j - 1], closes[j], closes[j + 1]
                        swing = (b < a and b < c2 and b < close) if sign < 0 else (b > a and b > c2 and b > close)
                        if swing:
                            f["floor"] = {"date": h[j][0], "close": b, "diff": abs(close - b)}
                            break
                break

    # weeks run Sunday..Thursday; the week's base is the last close before this week's Sunday
    def week_start(d):
        return d - dt.timedelta(days=(d.weekday() + 1) % 7)
    ws = week_start(today)
    before = [(d, c) for d, c in h if d < ws]
    f["week_base_date"], f["week_base"] = before[-1] if before else h[0]
    f["week_pts"] = close - f["week_base"]
    f["week_pct"] = 100 * f["week_pts"] / f["week_base"]
    f["week_end"] = today.weekday() == 3          # Thursday: the week's last session
    # previous complete weeks, newest first: +1 / -1 per week
    lasts = {}
    for d, c in h:
        lasts[week_start(d)] = (d, c)
    keys = sorted(lasts)
    wk = [(lasts[keys[i]][1] - lasts[keys[i - 1]][1]) for i in range(1, len(keys)) if keys[i] < ws]
    wkp = [100 * (lasts[keys[i]][1] - lasts[keys[i - 1]][1]) / lasts[keys[i - 1]][1] for i in range(1, len(keys)) if keys[i] < ws]
    prev = [(w > 0) - (w < 0) for w in reversed(wk)]
    f["prev_week_pct"] = wkp[-1] if wkp else None
    # month to date: from the last close of the previous month
    pm = [(d, c) for d, c in h if d < today.replace(day=1)]
    f["month_base_date"], f["month_base"] = pm[-1] if pm else (None, None)
    wsign = (f["week_pts"] > 0) - (f["week_pts"] < 0)
    run_same = 0
    for s in prev:
        if s != wsign:
            break
        run_same += 1
    run_opp = 0
    if not run_same:
        for s in prev:
            if s != -wsign:
                break
            run_opp += 1
    f["weeks_same"], f["weeks_opp"] = run_same, run_opp
    return f


# ---------------------------------------------------------------- text
def compose(m, cfg, now, idx, br, f):
    tz_today = now.date()
    home = idx[cfg["home"]]
    close, pct, pts = home["close"], home["change"], home["change_abs"]
    down = pct < 0
    verb = "يهبط" if pct < 0 else "يصعد" if pct > 0 else "يستقر"
    move = "بانخفاض" if pct < 0 else "بارتفاع"
    day = DAYS[tz_today.weekday()]
    wpct, wpts = f["week_pct"], f["week_pts"]
    wwin = wpts > 0
    name = cfg["card_name"]
    streak, since = f["streak"], f["since"]
    lowhigh = "أدنى" if down else "أعلى"
    fall_rise = "هبوط" if down else "صعود"

    # headline
    p = f"{abs(pct):.2f}%"
    if f["week_end"]:
        head_wide = f"{cfg['head']} {verb} {p}، ويُنهي الأسبوع {'رابحًا' if wwin else 'خاسرًا'} {abs(wpct):.2f}%."
        head_tall = [f"{cfg['head']} {verb} {p}", f"والأسبوع {'رابح' if wwin else 'خاسر'} {abs(wpct):.2f}%."]
    elif streak >= 3 and pct:
        head_wide = f"{cfg['head']} {verb} {p} في {ordinal(streak)} {fall_rise} على التوالي."
        head_tall = [f"{cfg['head']} {verb} {p}", f"{ordinal(streak)} {fall_rise} على التوالي."]
    elif since and since["gap"] >= 5:
        head_wide = f"{cfg['head']} {verb} {p} إلى {lowhigh} إغلاق منذ {dm(since['date'])}."
        head_tall = [f"{cfg['head']} {verb} {p}", f"إلى {lowhigh} إغلاق منذ {dm(since['date'])}."]
    else:
        head_wide = f"{cfg['head']} {verb} {p}."
        head_tall = [f"{cfg['head']} {verb} {p}."]

    # line under the headline
    extra = []
    if streak >= 2 and pct:
        extra.append(f"{ordinal(streak)} {fall_rise} على التوالي")
    if since:
        extra.append(f"{lowhigh} إغلاق منذ {dm(since['date'])}")
    line1 = f"أغلق {cfg['sub_name']}عند {f2(close)}" + (f" {move} {f2(abs(pts))} نقطة" if pct else " دون تغيير")
    line1 += (" — " + "، و".join(extra) + ".") if extra else "."
    up, dn, tot = br["up"], br["down"], br["total"]
    vol_side_down = br["vol_down_pct"] >= br["vol_up_pct"]
    vol_share = br["vol_down_pct"] if vol_side_down else br["vol_up_pct"]
    count_side_down = dn > up
    mixed = up != dn and count_side_down != vol_side_down
    line2 = (f"صعدت {up} {companies(up)} وهبطت {dn}، {'لكن ' if mixed else 'و'}{vol_share}% من الأسهم التي تم تداولها "
             f"كانت في شركات {'هبطت' if vol_side_down else 'صعدت'}.")
    sub_wide = [line1, line2]
    sub_tall = [f"أغلق {cfg['name']} عند {f2(close)} {move if pct else 'دون تغيير'}{' ' + p if pct else ''}.",
                f"صعدت {up} {companies(up)}، وهبطت {dn}."]

    # stats
    stats = [
        {"k": f"إغلاق {day}", "v": f2(close), "color": "amber"},
        {"k": "تغيّر الجلسة", "v": f'<span class="ltr">{MINUS if pts < 0 else "+" if pts > 0 else ""}{f2(abs(pts))}</span> نقطة', "color": color(pct)},
        {"k": "شركات صعدت مقابل هبطت", "v": f'<span class="ltr">{up} / {dn}</span>', "color": color(up - dn)},
        {"k": "تغيّر الأسبوع", "v": signed_pct(wpct), "color": color(wpct)},
    ]

    # cards
    lost_won = "ربح" if wwin else "خسر"
    base_day = DAYS[f["week_base_date"].weekday()]
    if f["weeks_opp"] >= 3:
        after = f"، وهو أول أسبوع {'رابح' if wwin else 'خاسر'} بعد {weeks(f['weeks_opp'], not wwin)}"
    elif f["weeks_opp"]:
        after = f"، بعد {weeks(f['weeks_opp'], not wwin)}"
    elif f["weeks_same"] >= 1:
        after = f"، وهو {ordinal(f['weeks_same'] + 1)} أسبوع {'رابح' if wwin else 'خاسر'} على التوالي"
    else:
        after = ""
    after_short = f"، بعد {weeks(f['weeks_opp'], not wwin)}" if f["weeks_opp"] else after
    if f["week_end"]:
        c_week = {"title": f"أسبوع {'رابح' if wwin else 'خاسر'} {abs(wpct):.2f}%", "color": color(wpts),
                  "text": f"{lost_won} {name} {f2(abs(wpts))} نقطة هذا الأسبوع منذ إغلاق {base_day} الماضي {f2(f['week_base'])}{after}.",
                  "tall": f"{lost_won} {name} {f2(abs(wpts))} نقطة هذا الأسبوع{after_short}."}
    else:   # mid-week: the week is not done, so the context is last week's result
        pw = f["prev_week_pct"]
        last = f"، بعد أسبوع {'رابح' if pw > 0 else 'خاسر'} {abs(pw):.2f}%" if pw else ""
        c_week = {"title": f"الأسبوع حتى الآن {signed_pct(wpct)}", "color": color(wpts),
                  "text": f"{lost_won} {name} {f2(abs(wpts))} نقطة منذ إغلاق {base_day} الماضي {f2(f['week_base'])}{last}.",
                  "tall": f"{lost_won} {name} {f2(abs(wpts))} نقطة منذ إغلاق {base_day} الماضي{last}."}

    share = round(100 * max(up, dn) / tot) if tot else 0
    if share >= 65:
        bt = f"{'هبطت' if count_side_down else 'صعدت'} {max(up, dn)} {companies(max(up, dn))} من {tot}"
    else:
        bt = f"صعدت {up} {companies(up)} وهبطت {dn}"
    side = "هبطت" if vol_side_down else "صعدت"
    if mixed:
        more = "الصاعدة فاق الهابطة" if up > dn else "الهابطة فاق الصاعدة"
        b_text = f"عدد الشركات {more}، لكن من كل 100 سهم تم تداولها، كان هناك {shares_of_100(vol_share)} في شركات {side}."
        b_tall = f"لكن {vol_share}% من التداول كان على الشركات {'الهابطة' if vol_side_down else 'الصاعدة'}."
    else:
        b_text = (f"صعدت {up} {companies(up)} وهبطت {dn}، أي {share}% منها. ومن كل 100 سهم تم تداولها، كان هناك "
                  f"{shares_of_100(vol_share)} في شركات {side}.")
        few = f"صعدت {up} {companies(up)} فقط" if count_side_down else f"هبطت {dn} {companies(dn)} فقط"
        b_tall = f"{few}، و{vol_share}% من التداول كان على الشركات {'الهابطة' if vol_side_down else 'الصاعدة'}."
    c_breadth = {"title": bt, "text": b_text, "tall": b_tall, "color": "amber" if mixed else ("red" if count_side_down else "green")}

    cards_more = []
    c_streak = c_level = c_floor = c_div = None
    if streak >= 3 and pct:
        t = f"{'خسر' if down else 'ربح'} {name} {f2(abs(f['streak_pts']))} نقطة في {sessions(streak)}"
        if since:
            t += (f"، وسجّل {lowhigh} إغلاق منذ يوم {dm(since['date'])}، وهو {'فوق' if down else 'تحت'} إغلاق ذلك اليوم "
                  f"بـ{f2(since['diff'])} نقطة")
        c_streak = {"title": f"{ordinal(streak)} {fall_rise} على التوالي", "text": t + ".", "color": color(pct)}
    if since:
        under_over = "تحت" if down else "فوق"
        t = (f"أغلق {name} {under_over} إغلاق {wdm(since['level_date'])} بـ{f2(since['level_diff'])} نقطة، "
             f"في {lowhigh} إغلاق منذ {dm(since['date'])}")
        if f.get("floor"):
            t += f"، و{'فوق' if down else 'تحت'} إغلاق {dm(f['floor']['date'])} بـ{f2(f['floor']['diff'])} نقطة"
        c_level = {"title": f"{under_over} إغلاق {dm(since['level_date'])}", "text": t + ".", "color": "amber"}
    if f.get("floor"):
        fl = f["floor"]
        c_floor = {"title": f"منذ إغلاق {dm(fl['date'])}", "color": "neutral",
                   "text": f"لا يزال {name} {'فوق' if down else 'تحت'} إغلاق {wdm(fl['date'])} البالغ {f2(fl['close'])} بفارق {f2(fl['diff'])} نقطة."}
    subs = [(sym, short, idx[sym]["change"]) for sym, _, short in cfg["indices"][1:] if idx.get(sym) and idx[sym]["change"] is not None]
    hsign = (pct > 0) - (pct < 0)
    opp = [s for s in subs if ((s[2] > 0) - (s[2] < 0)) == -hsign and abs(s[2]) >= 0.05] if hsign else []
    same = sorted([s for s in subs if ((s[2] > 0) - (s[2] < 0)) == hsign], key=lambda s: -abs(s[2]))

    def verb_list(items, rising):    # "هبطت أكبر 30 شركة 0.66% والبنوك 0.60%"; the verb repeats only when its gender changes
        out, last_v = [], None
        for _, short, ch in items:
            masc = short in cfg.get("masc", ())
            v = ("صعد" if rising else "هبط") + ("" if masc else "ت")
            out.append((f"{v} " if v != last_v else "") + f"{short} {abs(ch):.2f}%")
            last_v = v
        return " و".join(out)
    if opp and same:
        a = same[:2]
        t = verb_list(a, not down) + "، بينما " + verb_list(opp, down) + "."
        c_div = {"title": " و".join(s[1] for s in a), "text": t, "color": "neutral"}
    c_month = None
    if f.get("month_base"):
        mp_ = close - f["month_base"]
        c_month = {"title": f"منذ بداية {MONTHS[today_month(now)]} {signed_pct(100 * mp_ / f['month_base'])}", "color": color(mp_),
                   "text": f"{'ربح' if mp_ > 0 else 'خسر'} {name} {f2(abs(mp_))} نقطة منذ إغلاق {wdm(f['month_base_date'])} "
                           f"البالغ {f2(f['month_base'])}، آخر جلسة في الشهر الماضي."}
    hi, lo = home.get("high"), home.get("low")
    c_range = None
    if hi and lo:
        c_range = {"title": "مدى الجلسة", "color": "neutral",
                   "text": f"تحرك {name} بين {f2(lo)} و{f2(hi)} خلال الجلسة، وأغلق على بُعد {f2(close - lo)} نقطة من أدنى مستوى و{f2(hi - close)} من أعلاه."}

    if c_div:
        c3 = c_level or c_streak or c_floor or c_month or c_range
        c4 = c_div
    else:
        c3 = c_streak or c_level or c_month or c_range
        c4 = next((c for c in (c_floor, c_level, c_month, c_range) if c and c is not c3), None)
    cards_wide = [c_week, c_breadth] + [c for c in (c3, c4) if c]
    cards_tall = [{"title": c_week["title"], "text": c_week["tall"], "color": c_week["color"]},
                  {"title": c_breadth["title"], "text": c_breadth["tall"], "color": c_breadth["color"]}]

    # footer
    prev_ok = f.get("prev_ok")
    prev_txt = f"الإغلاق السابق {f2(f['prev_close'])}" + (f" يطابق إغلاق {wdm(f['prev_date'])}" if prev_ok else "")
    stamp = f"{now:%H:%M} بتوقيت {cfg['city']}، {dm(now)} {now.year}"
    foot_wide = [f"لقطة تريدنج فيو «عند الإغلاق» {stamp} · {prev_txt} · الصاعدة والهابطة من {tot} شركة{cfg['breadth_note']}",
                 f"· حصة التداول محسوبة بعدد الأسهم المتداولة لا بقيمتها {cfg['currency']} · {cfg['subs_note']} · "
                 f"الأسابيع محسوبة من إغلاقات الخميس · محتوى تعليمي وليس نصيحة استثمارية."]
    foot_tall = [f"لقطة تريدنج فيو عند الإغلاق {stamp}",
                 "· حصة التداول بعدد الأسهم لا بقيمتها · محتوى تعليمي وليس نصيحة استثمارية."]

    return {
        "market": m, "logo": cfg["logo"], "head_wide": head_wide, "head_tall": head_tall, "sub_wide": sub_wide, "sub_tall": sub_tall,
        "breadth": br, "idx_section": f"جلسة {day}، خمسة مؤشرات",
        "indices": [{"label": lbl, "pct": round(idx[s]["change"], 2)} for s, lbl, _ in cfg["indices"]],
        "stats": stats, "cards_wide": cards_wide, "cards_tall": cards_tall, "foot_wide": foot_wide, "foot_tall": foot_tall,
    }


# ---------------------------------------------------------------- render
def render(data, out_png_wide, out_png_tall):
    from playwright.sync_api import sync_playwright
    tpl = (HERE / "template.html").as_uri()
    with sync_playwright() as p:
        b = p.chromium.launch()
        for layout, path, (w, h, s) in (("wide", out_png_wide, (2000, 1125, 2.56)), ("tall", out_png_tall, (1125, 2000, 1.92))):
            pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=s)
            pg.add_init_script("window.POST = " + json.dumps(dict(data, layout=layout), ensure_ascii=False) + ";")
            pg.goto(tpl)
            pg.wait_for_function("window.READY !== undefined")
            pg.evaluate("window.READY")
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": w, "height": h})
            pg.close()
        b.close()


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("market", choices=MARKETS)
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--history")
    ap.add_argument("--out", default=str(ROOT / "out" / "posts"))
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--date", help="test only: pretend it is this session date (YYYY-MM-DD HH:MM), e.g. to re-make the last close on a weekend")
    a = ap.parse_args()
    m, cfg = a.market, MARKETS[a.market]
    tz = ZoneInfo(cfg["tz"])

    def at(hm):
        return dt.datetime.now(tz).replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)

    def clock():
        return dt.datetime.fromisoformat(a.date).replace(tzinfo=tz) if a.date else dt.datetime.now(tz)

    if a.date and not a.test:
        raise SystemExit("--date is for --test runs only")
    now = clock()
    today = now.date()
    folder = Path(a.out) / today.isoformat()
    stem = FILE.format(m=m, d=today.isoformat())
    if not a.test:
        if today.weekday() not in TRADING_DAYS:
            print(f"{m}: no session on {DAYS[today.weekday()]}")
            return 3
        if now < at(cfg["close"]):
            print(f"{m}: too early ({now:%H:%M}, closes {cfg['close'][0]}:{cfg['close'][1]:02d})")
            return 4
        if (folder / f"{stem}_wide.png").exists() and not a.redo:
            print(f"{m}: already made today")
            return 5

    notes, status = [], "TEST" if a.test else "OK"
    db = bool(os.environ.get("KANZ_DB_URL", "").strip())

    # wait until the home index holds still after the close (TradingView is 15 minutes behind)
    idx = tv_indices(cfg)
    home_time = dt.datetime.fromtimestamp(idx[cfg["home"]]["time"], tz).date()
    if home_time != today and not a.test:
        print(f"{m}: {cfg['home']} has no session today (last bar {home_time}): holiday")
        return 3
    if not a.test:
        last_val, since_t = idx[cfg["home"]]["close"], time.time()
        if now >= at(cfg["final_after"]) + dt.timedelta(minutes=20):   # late start (backup slot): the delayed feed has long settled
            since_t -= STABLE_SECS
        while True:
            now = dt.datetime.now(tz)
            kanz_ok = True
            if db:
                price, _, upd = kanz_live(cfg)
                kanz_ok = abs(price - idx[cfg["home"]]["close"]) < 0.011 and upd.astimezone(tz) >= at(cfg["close"])
            stable = time.time() - since_t >= STABLE_SECS
            if now >= at(cfg["final_after"]) and stable and kanz_ok:
                break
            if now >= at(cfg["give_up"]):
                status = "NEEDS REVIEW"
                notes.append(f"close not confirmed by {cfg['give_up'][0]}:{cfg['give_up'][1]:02d} "
                             f"(stable {stable}, Kanz agrees {kanz_ok}); made with the last TradingView value")
                break
            time.sleep(POLL_SECS)
            idx = tv_indices(cfg)
            v = idx[cfg["home"]]["close"]
            if v != last_val:
                print(f"{now:%H:%M:%S} {cfg['home']} {last_val} -> {v}", flush=True)
                last_val, since_t = v, time.time()
    now = clock()
    br = tv_breadth(cfg)
    home = idx[cfg["home"]]

    # history
    if a.history:
        hist = [(dt.date.fromisoformat(d), float(c)) for d, c in json.loads(Path(a.history).read_text(encoding="utf-8"))]
        src = f"history file {a.history}"
    elif db:
        hist = kanz_history(cfg, tz)
        src = "Kanz candle_cache"
    else:
        raise SystemExit("KANZ_DB_URL is not set and no --history file: the week, streak and 'lowest since' lines need the Kanz daily closes")
    f = facts(hist, today, home["close"])

    # checks
    prev_tv = home["close"] - home["change_abs"]
    f["prev_ok"] = abs(prev_tv - f["prev_close"]) < 0.011
    table = [("previous close", f2(prev_tv), f"{src} {f['prev_date']} {f2(f['prev_close'])}", "agree" if f["prev_ok"] else "DISAGREE")]
    if not f["prev_ok"]:
        status = "NEEDS REVIEW" if status == "OK" else status
        notes.append(f"TradingView previous close {f2(prev_tv)} differs from {src} {f2(f['prev_close'])} on {f['prev_date']}")
    if db:
        price, kpct, upd = kanz_live(cfg)
        ok = abs(price - home["close"]) < 0.011
        table.append(("home close", f2(home["close"]), f"Kanz live_quotes {f2(price)} ({kpct:+.2f}%, updated {upd.astimezone(tz):%H:%M})", "agree" if ok else "DISAGREE"))
        if not ok and status == "OK":
            status = "NEEDS REVIEW"
            notes.append(f"Kanz live price {f2(price)} differs from TradingView {f2(home['close'])}")
    else:
        notes.append("no KANZ_DB_URL: the close was not checked against Kanz live_quotes")
    for sym, lbl, _ in cfg["indices"]:
        r = idx.get(sym)
        if not r or r["change"] is None:
            status = "NEEDS REVIEW" if status == "OK" else status
            notes.append(f"{sym} missing from TradingView")
        elif abs(r["change"]) > 8:
            status = "NEEDS REVIEW" if status == "OK" else status
            notes.append(f"{sym} moved {r['change']:+.2f}%: check it")
        elif dt.datetime.fromtimestamp(r["time"], tz).date() != today and not sym.startswith("FTSE:"):
            notes.append(f"{sym} last bar is {dt.datetime.fromtimestamp(r['time'], tz).date()}, not today")
    if m == "egx" and br["total"] != 31 or m == "tasi" and not 240 <= br["total"] <= 320:
        status = "NEEDS REVIEW" if status == "OK" else status
        notes.append(f"breadth counted {br['total']} companies in {cfg['home']}: check the index membership")

    data = compose(m, cfg, now, idx, br, f)
    folder.mkdir(parents=True, exist_ok=True)
    wide, tall = folder / f"{stem}_wide.png", folder / f"{stem}_tall.png"
    render(data, wide, tall)
    (folder / f"{stem}_data.json").write_text(json.dumps({"data": data, "facts": {k: str(v) for k, v in f.items()}, "indices": idx},
                                                         ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    md = [f"# Validation: {m.upper()} close post, {today}", f"Status: {status}", ""] + [f"- {n}" for n in notes] + \
         ["", "| Check | Shown | Second source | Result |", "|---|---|---|---|"] + [f"| {a_} | {b_} | {c_} | {d_} |" for a_, b_, c_, d_ in table] + \
         ["", f"Breadth: {br['up']} up / {br['down']} not up ({br['flat']} unchanged) of {br['total']}; "
              f"share volume {br['vol_down_pct']}% in non-rising companies."]
    (folder / f"{stem}_validation.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if status == "NEEDS REVIEW":
        (folder / f"NEEDS REVIEW {m}.txt").write_text("\n".join(notes), encoding="utf-8")
    line = f"{cfg['name']} {f2(home['close'])} ({home['change']:+.2f}%), week {f['week_pct']:+.2f}%, {br['up']}/{br['down']} - {status}"
    result = json.dumps({"market": m, "date": today.isoformat(), "status": status, "line": line,
                         "files": [str(wide), str(tall)], "date_ar": f"{DAYS[today.weekday()]} {dm(today)}"}, ensure_ascii=False)
    Path("post_result.json").write_text(result, encoding="utf-8")
    Path(f"post_result_{m}.json").write_text(result, encoding="utf-8")   # kept per market for the website step
    print(line)
    for n in notes:
        print(" -", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
