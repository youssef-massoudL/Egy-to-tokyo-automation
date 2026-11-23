"""Post the day's reel through Zernio (zernio.com) to the platforms listed in ZERNIO_PLATFORMS (default facebook,twitter).

Off unless ZERNIO_POST_ENABLED=true (a repo variable), so nothing is posted until someone switches it on.
Needs one repo secret, ZERNIO_API_KEY (zernio.com/dashboard/api-keys, starts with sk_). The accounts are the ones
connected in Zernio; each platform must have exactly one, or the script stops and names them.
Optional repo variable ZERNIO_PLATFORMS: comma list, e.g. "facebook,twitter" or "facebook,twitter,instagram".

One Zernio post per platform, each with the video that platform wants:
  facebook / instagram  the Meta encode from cloud/ig_post.py (1080x1920), Facebook as a Reel (3-60 s)
  twitter               the X encode from cloud/x_post.py (720x1280, 30 fps)
Flow: POST /v1/media/presign, PUT the file, POST /v1/posts with publishNow. Each post carries an Idempotency-Key made
from edition + date + platform, so re-running the step the same day replays the first post instead of posting twice.
X refuses a caption it has seen recently: if it says duplicate, the X post is sent once more with the date added,
the same rule as cloud/x_post.py. One platform failing does not stop the others; the step fails at the end if any did.
Do not switch on X_POST_ENABLED at the same time as twitter here, or X gets the reel twice.

Private test (ZERNIO_TEST=1, the "private social test" box on a test run): Facebook only, sent as an unpublished
draft in the Page's Publishing Tools (only Page admins see it, it expires after about 30 days). X has no private
posts, so X is skipped and only printed. Works whether or not ZERNIO_POST_ENABLED is on, and whatever the check status.
Usage: python cloud/zernio_post.py egx|us <out_folder> [--dry-run]   (reads finish.json and <video>_site.json)
--dry-run encodes and prints what it would post, and calls nothing.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import caption  # noqa: E402
import social_links  # noqa: E402
from ig_post import COVER_MS, for_ig  # noqa: E402
from x_post import for_x  # noqa: E402

API = "https://zernio.com/api/v1"
ENCODE = {"facebook": for_ig, "instagram": for_ig, "twitter": for_x}
EXTRA = {"facebook": {"contentType": "reel"}, "instagram": {"thumbOffset": COVER_MS}}   # platformSpecificData per platform
DONE = ("published", "failed", "cancelled", "draft")


def call(key, method, path, body=None, headers=None):
    req = urllib.request.Request(f"{API}/{path}", method=method,
                                 data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:   # Zernio explains a refusal in the body: keep it
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"error": raw[:500]}


def upload(key, clip):
    code, pre = call(key, "POST", "media/presign",
                     {"filename": clip.name, "contentType": "video/mp4", "size": clip.stat().st_size})
    if code != 200:
        raise RuntimeError(f"presign failed: {code} {json.dumps(pre, ensure_ascii=False)[:400]}")
    put = urllib.request.Request(pre["uploadUrl"], data=clip.read_bytes(), method="PUT",
                                 headers={"Content-Type": "video/mp4"})
    urllib.request.urlopen(put, timeout=600).read()
    return pre["publicUrl"]


def clean_key(raw):
    """The secret as pasted, minus what a copy often brings along: spaces, quotes, a 'Bearer ' in front."""
    key = raw.strip().strip("'\"").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key


def key_shape(key):
    """What the key looks like, never the key: a Zernio key is sk_ + 64 hex, 67 characters."""
    hexpart = key[3:]
    return (f"{len(key)} characters, starts with sk_: {'yes' if key.startswith('sk_') else 'no'}, "
            f"rest is 64 hex: {'yes' if len(hexpart) == 64 and all(c in '0123456789abcdef' for c in hexpart.lower()) else 'no'}")


def accounts(key):
    code, data = call(key, "GET", "accounts")
    if code == 401:
        raise SystemExit(f"Zernio refused the API key ({data.get('error', '')}). The secret holds {key_shape(key)}. "
                         "A real key is 67 characters, sk_ + 64 hex. Make a new key at zernio.com/dashboard/api-keys "
                         "and paste it, whole, as the secret's value.")
    if code != 200:
        raise SystemExit(f"Zernio GET /accounts failed: {code} {json.dumps(data, ensure_ascii=False)[:400]}")
    found = {}
    for a in data.get("accounts", []):
        found.setdefault(a.get("platform"), []).append(a)
    return found


def post(key, platform, account_id, text, media_url, idem, draft=False):
    entry = {"platform": platform, "accountId": account_id}
    if platform in EXTRA:
        entry["platformSpecificData"] = dict(EXTRA[platform])
    if draft:   # Facebook only: an unpublished draft in Publishing Tools, not a post
        entry.setdefault("platformSpecificData", {})["facebookSettings"] = {"draft": True}
    code, data = call(key, "POST", "posts", {"content": text, "mediaItems": [{"type": "video", "url": media_url}],
                                             "platforms": [entry], "publishNow": True},
                      headers={"Idempotency-Key": idem})
    if code == 409 and data.get("details", {}).get("existingPostId"):   # same content already sent within 24 h
        code, data = call(key, "GET", f"posts/{data['details']['existingPostId']}")
    if code not in (200, 201, 207):
        return {"status": "failed", "errorMessage": f"{code} {json.dumps(data, ensure_ascii=False)[:400]}"}
    p = data.get("post", data)
    entry = (p.get("platforms") or [{}])[0]
    deadline = time.time() + 600   # a video can still be processing when the call returns
    while entry.get("status") not in DONE and p.get("_id") and time.time() < deadline:
        time.sleep(15)
        code, data = call(key, "GET", f"posts/{p['_id']}")
        if code == 200:
            p = data.get("post", data)
            entry = (p.get("platforms") or [{}])[0]
    for _ in range(4):   # published, but the public link (needed for the Slack message) can come a moment later
        if entry.get("status") != "published" or entry.get("platformPostUrl") or not p.get("_id"):
            break
        time.sleep(15)
        try:
            code, data = call(key, "GET", f"posts/{p['_id']}")
        except Exception:   # the post is already out: a link that cannot be read must not turn it into a failure
            break
        fresh = (data.get("post", data).get("platforms") or [{}])[0] if code == 200 else {}
        if fresh.get("platformPostUrl"):
            entry = fresh
    return {**entry, "postId": p.get("_id")}


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    test = os.environ.get("ZERNIO_TEST", "").strip() == "1"
    name, folder = args[0], Path(args[1])
    if os.environ.get("ZERNIO_POST_ENABLED", "").strip().lower() != "true" and not dry and not test:
        print("Zernio posting is off (repo variable ZERNIO_POST_ENABLED is not true), skipping")
        return
    key = clean_key(os.environ.get("ZERNIO_API_KEY", ""))
    if not dry and not key:
        raise SystemExit("the secret ZERNIO_API_KEY is empty")
    platforms = [p.strip().lower() for p in (os.environ.get("ZERNIO_PLATFORMS") or "facebook,twitter").split(",") if p.strip()]
    unknown = [p for p in platforms if p not in ENCODE]
    if unknown:
        raise SystemExit(f"ZERNIO_PLATFORMS has platforms this script does not post video to: {', '.join(unknown)}")
    if test:   # only Facebook can hold a private draft; everything else is printed, never sent
        for p in platforms:
            if p != "facebook":
                print(f"private test: {p} skipped (no private posts there)")
        platforms = ["facebook"]

    fin = json.load(open("finish.json", encoding="utf-8"))
    if fin["status"] not in ("OK", "SINGLE SOURCE") and not test:   # same rule as the public release: a held reel waits for a person
        print(f"status {fin['status']}, not posted through Zernio")
        return
    video = folder / fin["video"]
    site = json.loads((folder / f"{video.stem}_site.json").read_text(encoding="utf-8"))
    text = caption.build(name, site)["x"]   # the fixed line per edition: cloud/caption.py

    encoded = {}   # one encode per kind: Facebook and Instagram share the Meta one
    for p in platforms:
        if ENCODE[p] not in encoded:
            encoded[ENCODE[p]] = ENCODE[p](video)
    clips = {p: encoded[ENCODE[p]] for p in platforms}
    if dry:
        for p in platforms:
            print(f"dry run: would post {clips[p].name} ({clips[p].stat().st_size / 1e6:.1f} MB) to {p}"
                  f"{' as a Reel' if p == 'facebook' else ''} with:")
        print(text)
        return

    found = accounts(key)
    urls, failed = {}, []
    for p in platforms:
        acc = found.get(p, [])
        if len(acc) != 1:
            print(f"{p}: {len(acc)} connected accounts in Zernio "
                  f"({', '.join(a.get('username', '?') for a in acc) or 'none'}), need exactly one, not posted")
            failed.append(p)
            continue
        try:
            clip = clips[p]
            if clip not in urls:   # one upload per encode
                urls[clip] = upload(key, clip)
            run = f"/test-{os.environ.get('GITHUB_RUN_ID', int(time.time()))}" if test else ""   # every test is its own draft
            idem = str(uuid.uuid5(uuid.NAMESPACE_URL, f"kanz-radar/{name}/{folder.name}/{p}{run}"))
            res = post(key, p, acc[0]["_id"], text, urls[clip], idem, draft=test)
            if test:
                print("private test, Zernio answered:", json.dumps(res, ensure_ascii=False)[:800])
                if res.get("status") != "failed":
                    print(f"private test OK: draft Reel on {p} (@{acc[0].get('username')}), "
                          "see Meta Business Suite > Content > Drafts, or the Page's Publishing Tools")
                    continue
            if p == "twitter" and res.get("status") == "failed" and "duplicate" in str(res.get("errorMessage", "")).lower():
                print("X called the caption a duplicate, posting it with the date")
                res = post(key, p, acc[0]["_id"], f"{text}\n{site['weekday']} {site['date_ar']}", urls[clip], idem + "-dated")
        except Exception as e:   # one platform failing never holds the others back
            res = {"status": "failed", "errorMessage": str(e)[:400]}
        if res.get("status") == "published":
            link = res.get("platformPostUrl")
            if not link and p == "twitter" and res.get("platformPostId"):
                link = f"https://x.com/i/status/{res['platformPostId']}"
            social_links.add(name, folder, p, link)
            print(f"posted to {p} (@{acc[0].get('username')}): {res.get('platformPostUrl')}")
        else:
            print(f"{p} NOT posted: status {res.get('status')}, {res.get('errorCategory', '')} {res.get('errorMessage', '')}".strip())
            failed.append(p)
    if failed:
        raise SystemExit(f"Zernio: not posted to {', '.join(failed)}")


if __name__ == "__main__":
    main()
