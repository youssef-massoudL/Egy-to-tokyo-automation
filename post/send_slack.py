"""Send one market's close post to Slack: the two PNGs (wide 16:9 and tall 9:16) in one message with the market and the date.

Usage: python post/send_slack.py            (reads post_result.json written by post/market_post.py)
Same Slack setup as the reel (cloud/slack_notify.py): SLACK_BOT_TOKEN + SLACK_CHANNEL_ID, or SLACK_WEBHOOK_URL (text + RELEASE_URL link only).
A post with status NEEDS REVIEW is never sent: it waits as a draft release for a person.
"""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

TITLE = {"egx": "إغلاق البورصة المصرية", "tasi": "إغلاق السوق السعودية", "us": "إغلاق السوق الأمريكية"}

res = json.loads(Path("post_result.json").read_text(encoding="utf-8"))
token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
channel = os.environ.get("SLACK_CHANNEL_ID", "").strip()
hook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
if token and not channel and not hook:
    raise SystemExit("SLACK_BOT_TOKEN is set but SLACK_CHANNEL_ID is empty: add the channel ID (C...) as a repo secret or variable")
if not ((token and channel) or hook):
    print("no Slack secrets, skipping Slack")
    raise SystemExit(0)
if res["status"] == "NEEDS REVIEW":
    print("needs review, not sent to Slack")
    raise SystemExit(0)
text = f"*{TITLE[res['market']]}* · {res['date_ar']}"


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
    files = []
    for p in map(Path, res["files"]):
        blob = p.read_bytes()
        up = call("files.getUploadURLExternal", {"filename": p.name, "length": len(blob)})
        call(None, raw=blob, url=up["upload_url"], ctype="application/octet-stream")
        files.append({"id": up["file_id"], "title": p.name})
    call("files.completeUploadExternal", {"files": json.dumps(files), "channel_id": channel, "initial_comment": text})
    print("sent", len(files), "images to Slack")
else:
    link = os.environ.get("RELEASE_URL", "")
    req = urllib.request.Request(hook, data=json.dumps({"text": text + (f"\n{link}" if link else "")}).encode(),
                                 headers={"Content-Type": "application/json"})
    print(urllib.request.urlopen(req, timeout=20).read().decode())
