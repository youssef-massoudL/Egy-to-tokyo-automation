"""Send the day's reel to Slack.

With SLACK_BOT_TOKEN + SLACK_CHANNEL_ID: uploads the MP4 itself, with the day and the markets as its message.
  (Slack app with bot scopes files:write and chat:write, invited to the channel.)
Else with SLACK_WEBHOOK_URL: posts the same text with a download link (webhooks cannot carry files).
Usage: python cloud/slack_notify.py egx|us <out_folder>   (reads finish.json and <video>_site.json)
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

NAMES = {
    "egx30": "EGX30 · مصر", "tasi": "تاسي · السعودية", "dfmgi": "سوق دبي", "fadgi": "فوتسي أبوظبي", "nifty": "نيفتي 50 · الهند",
    "hsi": "هانج سنج · هونج كونج", "kospi": "كوسبي 200 · كوريا", "n225": "نيكاي 225 · اليابان",
    "dax": "داكس · ألمانيا", "cac": "كاك 40 · فرنسا", "ftse": "فوتسي 100 · بريطانيا", "dow": "داو جونز", "spx": "إس آند بي 500", "ndq": "ناسداك",
    "brent": "برنت", "gold": "الذهب",
}
TITLE = {"egx": "من القاهرة لطوكيو", "us": "من أوروبا لنيويورك"}

name, folder = sys.argv[1], Path(sys.argv[2])
token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
channel = os.environ.get("SLACK_CHANNEL_ID", "").strip()
hook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
if not ((token and channel) or hook):
    print("no Slack secrets, skipping Slack")
    raise SystemExit(0)

fin = json.load(open("finish.json", encoding="utf-8"))
video = folder / fin["video"]
site = json.loads((folder / f"{video.stem}_site.json").read_text(encoding="utf-8"))

lines = []
if fin["status"] == "TEST":
    lines.append("🧪 تجربة (test run, not a real close)")
elif fin["status"] == "NEEDS REVIEW":
    lines.append("⚠️ للمراجعة قبل النشر (needs review)")
lines.append(f"*{TITLE[name]}* · {site['weekday']} {site['date_ar']}")
for r in site["rows"]:
    v = "مغلق" if r["closed"] else f"{'🟣' if r['pct'] >= 0 else '🔴'} {r['pct']:+.2f}%"
    lines.append(f"{NAMES.get(r['key'], r['key'])}: {v}")
text = "\n".join(lines)


def call(method, data=None, raw=None, url=None, ctype=None):
    req = urllib.request.Request(url or f"https://slack.com/api/{method}",
                                 data=raw if raw is not None else urllib.parse.urlencode(data).encode(),
                                 headers={"Authorization": f"Bearer {token}", **({"Content-Type": ctype} if ctype else {})})
    body = urllib.request.urlopen(req, timeout=300).read()
    if url:
        return body
    out = json.loads(body)
    if not out.get("ok"):
        raise SystemExit(f"Slack {method} failed: {out.get('error')}")
    return out


if token and channel:
    blob = video.read_bytes()
    up = call("files.getUploadURLExternal", {"filename": video.name, "length": len(blob)})
    call(None, raw=blob, url=up["upload_url"], ctype="application/octet-stream")
    call("files.completeUploadExternal", {"files": json.dumps([{"id": up["file_id"], "title": video.name}]),
                                          "channel_id": channel, "initial_comment": text})
    print("uploaded", video.name, f"{len(blob) / 1e6:.1f} MB to Slack")
else:
    link = os.environ.get("RELEASE_URL", "")
    req = urllib.request.Request(hook, data=json.dumps({"text": text + (f"\n{link}" if link else "")}).encode(),
                                 headers={"Content-Type": "application/json"})
    print(urllib.request.urlopen(req, timeout=20).read().decode())
