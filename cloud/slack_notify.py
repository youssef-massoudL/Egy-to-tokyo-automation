"""Post one message to a Slack incoming webhook. Env: SLACK_WEBHOOK_URL, RELEASE_URL. Reads finish.json."""
import json
import os
import urllib.request

f = json.load(open("finish.json", encoding="utf-8"))
icon = ":white_check_mark:" if f["status"] == "OK" else ":warning:"
text = f"{icon} {f['line']}\nDownload (team only, GitHub login): {os.environ['RELEASE_URL']}"
req = urllib.request.Request(os.environ["SLACK_WEBHOOK_URL"], data=json.dumps({"text": text}).encode(), headers={"Content-Type": "application/json"})
print(urllib.request.urlopen(req, timeout=20).read().decode())
