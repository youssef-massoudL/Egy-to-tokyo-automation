"""Post the day's reel to Instagram as a Reel: the MP4 with the caption from cloud/caption.py.

Off unless IG_POST_ENABLED=true (a repo variable), so nothing reaches Instagram until someone switches it on.
Needs two repo secrets:
  IG_USER_ID       the Instagram professional account's id (a number, from Graph API Explorer: me/accounts?fields=instagram_business_account)
  IG_ACCESS_TOKEN  a Meta system-user token (Business Settings > System users) with instagram_basic,
                   instagram_content_publish and pages_show_list. A system-user token set to "Never" does not expire,
                   so the workflow never has to refresh or store a token. (A 60-day user token also works, until it expires.)
Optional repo variable IG_GRAPH_HOST: graph.facebook.com (default, for system-user / Facebook-login tokens) or
graph.instagram.com (for tokens made with Instagram Login).

Instagram Reels take MP4, H.264, yuv420p, AAC at most 48 kHz, 23-60 fps, moov atom first, up to 300 MB, so the reel
is re-encoded to exactly that at its own 1080x1920 size. Upload is the resumable flow: create a REELS container with
upload_type=resumable, send the bytes to rupload.facebook.com, wait until the container is FINISHED, then media_publish.
Usage: python cloud/ig_post.py egx|us <out_folder> [--dry-run]   (reads finish.json and <video>_site.json)
--dry-run re-encodes and prints what it would post, and calls nothing.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import caption  # noqa: E402

VERSION = "v23.0"
SECRETS = ("IG_USER_ID", "IG_ACCESS_TOKEN")


def call(host, token, method, path, params=None):
    url = f"https://{host}/{VERSION}/{path}"
    params = {**(params or {}), "access_token": token}
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=120).read())
    except urllib.error.HTTPError as e:   # Meta explains a refusal in the body: show it instead of a bare status
        raise SystemExit(f"Instagram {method} /{path} failed: {e.code} {e.read().decode(errors='replace')[:500]}")


def for_ig(video):
    out = video.with_name(video.stem + "_ig.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video),
                    "-vf", "scale=1080:1920:flags=lanczos:out_range=tv,format=yuv420p", "-color_range", "tv",
                    "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-preset", "slow",
                    "-b:v", "12M", "-maxrate", "20M", "-bufsize", "30M", "-g", "120", "-flags", "+cgop",
                    "-c:a", "aac", "-profile:a", "aac_low", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart", str(out)], check=True)
    return out


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    name, folder = args[0], Path(args[1])
    if os.environ.get("IG_POST_ENABLED", "").strip().lower() != "true" and not dry:
        print("Instagram posting is off (repo variable IG_POST_ENABLED is not true), skipping Instagram")
        return
    user, token = (os.environ.get(k, "").strip() for k in SECRETS)
    if not dry and not (user and token):   # switched on but half set up: say what is missing instead of skipping quietly
        raise SystemExit("IG_POST_ENABLED is true but these secrets are empty: " + ", ".join(k for k in SECRETS if not os.environ.get(k, "").strip()))
    host = os.environ.get("IG_GRAPH_HOST", "").strip() or "graph.facebook.com"

    fin = json.load(open("finish.json", encoding="utf-8"))
    if fin["status"] not in ("OK", "SINGLE SOURCE"):   # same rule as the public release: a held reel waits for a person
        print(f"status {fin['status']}, not posted to Instagram")
        return
    video = folder / fin["video"]
    site = json.loads((folder / f"{video.stem}_site.json").read_text(encoding="utf-8"))
    text = caption.build(name, site)["instagram"]   # the fixed line per edition: cloud/caption.py

    clip = for_ig(video)
    blob = clip.read_bytes()
    if dry:
        print(f"dry run: would post {clip.name} ({len(blob) / 1e6:.1f} MB) as a Reel with:")
        print(text)
        return

    box = call(host, token, "POST", f"{user}/media",
               {"media_type": "REELS", "upload_type": "resumable", "caption": text, "share_to_feed": "true"})
    cid = box["id"]
    req = urllib.request.Request(box.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{VERSION}/{cid}", data=blob,
                                 method="POST", headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(blob))})
    try:
        up = json.loads(urllib.request.urlopen(req, timeout=600).read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Instagram upload failed: {e.code} {e.read().decode(errors='replace')[:500]}")
    if not up.get("success"):
        raise SystemExit(f"Instagram upload failed: {json.dumps(up)[:500]}")

    deadline = time.time() + 900
    while True:   # Instagram processes the video before it can be published
        st = call(host, token, "GET", cid, {"fields": "status_code,status"})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED") or time.time() > deadline:
            raise SystemExit(f"Instagram could not process the video: {json.dumps(st)[:500]}")
        time.sleep(10)

    post = call(host, token, "POST", f"{user}/media_publish", {"creation_id": cid})
    link = call(host, token, "GET", post["id"], {"fields": "permalink"}).get("permalink", "")
    print("posted to Instagram:", post["id"], link, f"({len(blob) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
