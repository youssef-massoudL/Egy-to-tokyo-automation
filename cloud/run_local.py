"""Make one edition on this PC and send it to Slack, without GitHub (backup when GitHub Actions is down).

Usage (from the repo root): python cloud/run_local.py egx|us [--test]
Slack: reads .slack_token in the repo root (line 1: xoxb-... bot token, line 2: channel ID). The file is git-ignored.
Output: out/<date>/ in the repo (video, sheet, report, validation note). The website is not updated (that needs GitHub).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ed = sys.argv[1]
test = "--test" in sys.argv
env = dict(os.environ, RADAR_OUT=str(ROOT / "out"), RADAR_PARALLEL="1", RADAR_TEST="1" if test else "0", PYTHONIOENCODING="utf-8")


def load_slack():   # read at send time, so the file can be added while the run waits for the close
    tok = ROOT / ".slack_token"
    if tok.exists():
        lines = [x.strip() for x in tok.read_text(encoding="utf-8").splitlines() if x.strip()]
        if len(lines) >= 2:
            env["SLACK_BOT_TOKEN"], env["SLACK_CHANNEL_ID"] = lines[0], lines[1]
    if "SLACK_BOT_TOKEN" not in env:
        print("note: no .slack_token found, the reel is made but not sent to Slack")


def run(*cmd):
    print(">", " ".join(cmd), flush=True)
    return subprocess.run([sys.executable, *cmd], cwd=ROOT, env=env).returncode


if not test:
    c = run("projects/_radar/run_edition.py", ed, "check")
    if c:
        raise SystemExit({4: "too early", 5: "already made today"}.get(c, f"check exit {c}"))
if run("projects/_radar/run_edition.py", ed, "fetch", *([] if test else ["--wait"])) == 3:
    raise SystemExit("home market did not trade today, no reel")
for step in (["cloud/validate.py", ed], ["projects/_radar/run_edition.py", ed, "render"]):
    if run(*step):
        raise SystemExit(f"failed: {' '.join(step)}")
from editions import EDITIONS  # noqa: E402  (cloud/ is on the path when run as cloud/run_local.py)
proj = ROOT / "projects" / EDITIONS[ed]["project"]
date = json.loads((proj / "out" / "report.json").read_text(encoding="utf-8"))["date"]
folder = ROOT / "out" / date
load_slack()
if run("cloud/finish.py", ed, str(folder)) or run("cloud/slack_notify.py", ed, str(folder)):
    raise SystemExit("failed at finish / Slack")
print("done:", folder)
