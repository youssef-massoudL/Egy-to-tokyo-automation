"""Post one message to a Slack incoming webhook. Env: SLACK_WEBHOOK_URL, RELEASE_URL. Reads finish.json."""
import json
import os
import urllib.request

if not os.environ.get("SLACK_WEBHOOK_URL", "").strip():
    print("no SLACK_WEBHOOK_URL secret, skipping Slack")
    raise SystemExit(0)
f = json.load(open("finish.json", encoding="utf-8"))
public = f["status"] in ("OK", "SINGLE SOURCE")
icon = ":white_check_mark:" if f["status"] == "OK" else ":large_yellow_circle:" if public else ":warning:"
where = "Download" if public else "Draft (collaborators only), review then publish"
text = f"{icon} {f['line']}\n{where}: {os.environ['RELEASE_URL']}"
if os.environ.get("WEBSITE_URL"):
    text += f"\nWebsite: {os.environ['WEBSITE_URL']}"
req = urllib.request.Request(os.environ["SLACK_WEBHOOK_URL"], data=json.dumps({"text": text}).encode(), headers={"Content-Type": "application/json"})
print(urllib.request.urlopen(req, timeout=20).read().decode())
