"""Post the day's reel to X: the MP4 with the caption from cloud/caption.py.

Off unless X_POST_ENABLED=true (a repo variable), so nothing reaches X until someone switches it on.
Needs the Kanz X account's OAuth 1.0a keys as repo secrets: X_API_KEY, X_API_SECRET (the app's consumer key and
secret) and X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET (the account's token, made with Read and Write permission).
These do not expire, so the workflow never has to refresh or store a token.

X documents video up to 1280x1024 and recommends 720x1280 portrait, 30 or 60 fps, H.264 High, yuv420p, AAC-LC,
so the 1080x1920 reel is re-encoded to 720x1280 first. Upload is X's v2 chunked flow (initialize, append in
4 MB segments, finalize, wait for processing), then POST /2/tweets with the media id.
Usage: python cloud/x_post.py egx|us <out_folder> [--dry-run]   (reads finish.json and <video>_site.json)
--dry-run re-encodes and prints what it would post, and calls nothing.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import caption  # noqa: E402

API = "https://api.x.com/2"
CHUNK = 4 * 1024 * 1024   # X: keep each segment at or below 5 MB
SECRETS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")


def quote(s):
    return urllib.parse.quote(str(s), safe="~")


def oauth_header(method, url, query, keys, nonce=None, stamp=None):
    """OAuth 1.0a HMAC-SHA1. Only the query string is signed: JSON and multipart bodies are not part of the base."""
    consumer_key, consumer_secret, token, token_secret = keys
    oauth = {"oauth_consumer_key": consumer_key, "oauth_nonce": nonce or secrets.token_hex(16),
             "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": str(stamp or int(time.time())),
             "oauth_token": token, "oauth_version": "1.0"}
    params = sorted((quote(k), quote(v)) for k, v in [*oauth.items(), *query.items()])
    base = "&".join([method.upper(), quote(url), quote("&".join(f"{k}={v}" for k, v in params))])
    key = f"{quote(consumer_secret)}&{quote(token_secret)}".encode()
    oauth["oauth_signature"] = base64.b64encode(hmac.new(key, base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{quote(k)}="{quote(v)}"' for k, v in sorted(oauth.items()))


def call(keys, method, path, query=None, body=None, ctype=None):
    url = f"{API}/{path}"
    query = query or {}
    headers = {"Authorization": oauth_header(method, url, query, keys)}
    if ctype:
        headers["Content-Type"] = ctype
    full = url + ("?" + urllib.parse.urlencode(query) if query else "")
    try:
        raw = urllib.request.urlopen(urllib.request.Request(full, data=body, method=method, headers=headers), timeout=300).read()
    except urllib.error.HTTPError as e:   # X explains a refusal in the body: show it instead of a bare status
        raise SystemExit(f"X {method} /{path} failed: {e.code} {e.read().decode(errors='replace')[:500]}")
    return json.loads(raw) if raw.strip() else {}


def multipart(fields, file_field, blob):
    boundary = "kanz" + secrets.token_hex(12)
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="chunk"\r\n'
                 f"Content-Type: application/octet-stream\r\n\r\n".encode() + blob + b"\r\n")
    return b"".join(parts) + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def for_x(video):
    out = video.with_name(video.stem + "_x.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video),
                    "-vf", "scale=720:1280:flags=lanczos:out_range=tv,fps=30,format=yuv420p", "-color_range", "tv",
                    "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
                    "-b:v", "6M", "-maxrate", "8M", "-bufsize", "12M", "-g", "60", "-flags", "+cgop",
                    "-c:a", "aac", "-profile:a", "aac_low", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                    "-movflags", "+faststart", str(out)], check=True)
    return out


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    name, folder = args[0], Path(args[1])
    if os.environ.get("X_POST_ENABLED", "").strip().lower() != "true" and not dry:
        print("X posting is off (repo variable X_POST_ENABLED is not true), skipping X")
        return
    keys = [os.environ.get(k, "").strip() for k in SECRETS]
    if not dry and not all(keys):   # switched on but half set up: say what is missing instead of skipping quietly
        raise SystemExit("X_POST_ENABLED is true but these secrets are empty: " + ", ".join(k for k, v in zip(SECRETS, keys) if not v))

    fin = json.load(open("finish.json", encoding="utf-8"))
    if fin["status"] not in ("OK", "SINGLE SOURCE"):   # same rule as the public release: a held reel waits for a person
        print(f"status {fin['status']}, not posted to X")
        return
    video = folder / fin["video"]
    site = json.loads((folder / f"{video.stem}_site.json").read_text(encoding="utf-8"))
    text = caption.build(name, site)["x"]   # the fixed line per edition: cloud/caption.py

    clip = for_x(video)
    blob = clip.read_bytes()
    if dry:
        print(f"dry run: would post {clip.name} ({len(blob) / 1e6:.1f} MB, {-(-len(blob) // CHUNK)} segments) with:")
        print(text)
        return

    media = call(keys, "POST", "media/upload/initialize", ctype="application/json",
                 body=json.dumps({"media_type": "video/mp4", "total_bytes": len(blob), "media_category": "tweet_video"}).encode())
    media_id = media["data"]["id"]
    for i in range(0, len(blob), CHUNK):
        body, ctype = multipart({"segment_index": i // CHUNK}, "media", blob[i:i + CHUNK])
        call(keys, "POST", f"media/upload/{media_id}/append", body=body, ctype=ctype)
    info = call(keys, "POST", f"media/upload/{media_id}/finalize").get("data", {}).get("processing_info")
    deadline = time.time() + 600
    while info and info.get("state") != "succeeded":
        if info.get("state") == "failed" or time.time() > deadline:
            raise SystemExit(f"X could not process the video: {json.dumps(info)[:500]}")
        time.sleep(max(1, int(info.get("check_after_secs", 5))))
        info = call(keys, "GET", "media/upload", {"command": "STATUS", "media_id": media_id}).get("data", {}).get("processing_info")

    def tweet(words):
        return call(keys, "POST", "tweets", ctype="application/json",
                    body=json.dumps({"text": words, "media": {"media_ids": [media_id]}}, ensure_ascii=False).encode())

    try:
        post = tweet(text)
    except SystemExit as e:   # the caption is the same every day: if X calls it a duplicate, add the date and post once more
        if "duplicate" not in str(e).lower():
            raise
        print("X called the caption a duplicate, posting it with the date")
        post = tweet(f"{text}\n{site['weekday']} {site['date_ar']}")
    print("posted to X:", post["data"]["id"], f"({len(blob) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
