"""The links of the day's social posts, kept for the Slack message (cloud/slack_notify.py).

Every posting script calls add() right after its platform confirms the post, so Slack, which runs last, shows exactly
what went out: a platform that is off, failed or held is simply not there. Kept in social_links.json next to finish.json
(not in the reel's folder, so it never lands in the release).
"""
import json
from pathlib import Path

FILE = Path("social_links.json")
LABEL = {"instagram": "Instagram", "facebook": "Facebook", "twitter": "X"}   # also the order in Slack


def reel(name, folder):
    return f"{name}/{Path(folder).name}"   # edition/date: links of another reel are never shown


def load(name, folder):
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        links = data["links"] if data.get("reel") == reel(name, folder) else {}
        return links if isinstance(links, dict) else {}
    except (OSError, ValueError, KeyError, AttributeError):
        return {}


def add(name, folder, platform, url):
    """Never raises: the post is already public, a link that cannot be saved must not fail the step."""
    if not url:
        return
    try:
        links = load(name, folder)
        links[platform] = url
        FILE.write_text(json.dumps({"reel": reel(name, folder), "links": links}, indent=1), encoding="utf-8")
    except OSError as e:
        print(f"could not save the {platform} link for Slack: {e}")


def slack_line(name, folder):
    """One line of Slack links, e.g. <https://...|Instagram> · <https://...|X>; empty when nothing was posted."""
    links = load(name, folder)
    order = [p for p in LABEL if p in links] + [p for p in links if p not in LABEL]
    safe = {p: str(links[p]).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") for p in order}
    return " · ".join(f"<{safe[p]}|{LABEL.get(p, p)}>" for p in order)
