"""One market's close post in GitHub Actions: make it, publish the release, send it to Slack. Usage: python post/run_one.py egx|tasi
Env: TEST=1 (test run), TEST_DATE ("YYYY-MM-DD HH:MM", tests only), SLACK_TEST=true (send a test to Slack), SITE_TEST=true
(put a test on the website), REDO=true (real run: make today's again), plus the Kanz / Slack secrets.
Writes to $GITHUB_OUTPUT: site=true when this post should go on the website. Exit 1 when the post failed."""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

mk = sys.argv[1]
test = os.environ.get("TEST") == "1"
date_in = os.environ.get("TEST_DATE", "").strip() if test else ""
tz = ZoneInfo({"egx": "Africa/Cairo", "tasi": "Asia/Riyadh", "us": "America/New_York"}[mk])
D = date_in[:10] if date_in else dt.datetime.now(tz).date().isoformat()
run_no = os.environ.get("GITHUB_RUN_NUMBER", "0")
tag = f"post-{mk}-{D}-test-{run_no}" if test else f"post-{mk}-{D}"


def out(**kv):
    p = os.environ.get("GITHUB_OUTPUT")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.writelines(f"{k}={v}\n" for k, v in kv.items())


def gh(*a, check=True):
    return subprocess.run(["gh", *a], capture_output=True, text=True, check=check)


out(site="false")
if not test and os.environ.get("REDO") != "true" and gh("release", "view", tag, check=False).returncode == 0:
    print(f"{mk}: already made today ({tag})")
    raise SystemExit(0)

# the stored closes (week / streak / "lowest since" without the Kanz database) live in the release "post-history"
HIST = "post-history"
Path("out/history").mkdir(parents=True, exist_ok=True)
got = gh("release", "download", HIST, "--pattern", "*.json", "--dir", "out/history", "--clobber", check=False)
print("stored closes:", "downloaded" if got.returncode == 0 else "none yet, starting from the seed in post/history")

args = [sys.executable, "post/market_post.py", mk, "--out", "out/posts", "--store", "out/history"] + (["--test"] if test else []) + (["--date", date_in] if date_in else [])
code = subprocess.run(args).returncode
if code in (3, 4):
    print(f"{mk}: {'no session today (holiday)' if code == 3 else 'too early'}, no post")
    raise SystemExit(0)
if code:
    raise SystemExit(f"{mk}: post failed (exit {code})")

res = json.loads(Path("post_result.json").read_text(encoding="utf-8"))
stores = [Path("out/history") / f"{k}.json" for k in res.get("store", [mk])]   # the US report keeps three: spx, dji, ndx
if not test and res["status"] == "OK" and all(p.exists() for p in stores):   # market_post.py added today's closes
    if gh("release", "view", HIST, check=False).returncode:
        gh("release", "create", HIST, "--prerelease", "--title", "Close post: stored daily closes",
           "--notes", "Daily closes of EGX30 and TASI used by the close posts. Updated by the workflow after every OK post; do not delete.")
    gh("release", "upload", HIST, *map(str, stores), "--clobber")
    print("stored closes updated")
files = [str(p) for p in sorted(Path(f"out/posts/{res['date']}").glob(f"*{mk}*"))]
title = f"{'EGX' if mk == 'egx' else 'Tadawul'} close post {res['date']}" + (" (test)" if test else "")
if gh("release", "view", tag, check=False).returncode == 0:
    gh("release", "upload", tag, *files, "--clobber")                      # a redo replaces the day's files
else:
    gh("release", "create", tag, *files, "--title", title, "--notes", res["line"], *([] if res["status"] == "OK" else ["--draft"]))
os.environ["RELEASE_URL"] = gh("release", "view", tag, "--json", "url", "-q", ".url").stdout.strip()
print(res["line"], os.environ["RELEASE_URL"])
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary, "a", encoding="utf-8") as f:
        f.write(f"- {res['line']} ({os.environ['RELEASE_URL']})\n")

slack_ok = True
if not test or os.environ.get("SLACK_TEST") == "true":
    slack_ok = subprocess.run([sys.executable, "post/send_slack.py"]).returncode == 0
on_site = res["status"] == "OK" or (test and os.environ.get("SITE_TEST") == "true")
out(site="true" if on_site else "false")
if not slack_ok:
    raise SystemExit(f"{mk}: Slack failed")
