"""Post one market's close post (the 16:9 image) to social media through Zernio. Saudi and EGX only.

Usage (from the repo root): python post/social_post.py [--dry-run]     (reads post_result.json)
Same Zernio setup as the reel (cloud/zernio_post.py): off unless ZERNIO_POST_ENABLED=true, the platforms in
ZERNIO_PLATFORMS (default facebook,twitter), the key in ZERNIO_API_KEY. Only a post with status OK goes out; a
NEEDS REVIEW post waits for a person. post/run_one.py calls this on real runs only, never on a redo, and before Slack
so the Slack message carries the links. One platform failing does not stop the others; the script fails at the end.
ZERNIO_TEST=1 (the "private social test" box on a test run): Facebook only, as an unpublished draft.
--dry-run makes the images and prints what it would post, and calls nothing.
"""
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cloud"))
import social_links  # noqa: E402
from zernio_post import accounts, clean_key, post, upload  # noqa: E402

MARKETS = ("tasi", "egx")   # the US post is not sent to social media
TITLE = {"egx": "إغلاق البورصة المصرية", "tasi": "إغلاق السوق السعودية"}
SHAPE = {"facebook": "wide", "twitter": "wide", "instagram": "wide"}   # "wide" 16:9 or "tall" 9:16, per platform
WIDTH = {"facebook": 2048, "twitter": 2048, "instagram": 1440}         # Instagram takes 1440 at most


def caption(res):   # the market and the day only: no numbers, no hashtags (the date also keeps X from calling it a repeat)
    return f"{TITLE[res['market']]} · {res['date_ar']} | الرادار"


def jpeg(source, width):
    """The 5120 px PNG as a JPEG small enough for every platform (X takes 5 MB at most)."""
    from PIL import Image
    out = source.with_name(f"{source.stem}_social{width}.jpg")
    im = Image.open(source).convert("RGB")
    im.resize((width, round(im.height * width / im.width)), Image.LANCZOS).save(out, quality=92)
    return out


def main():
    dry = "--dry-run" in sys.argv
    test = os.environ.get("ZERNIO_TEST", "").strip() == "1"
    res = json.loads(Path("post_result.json").read_text(encoding="utf-8"))
    mk = res["market"]
    if mk not in MARKETS:
        print(f"{mk}: this post is not sent to social media")
        return
    if os.environ.get("ZERNIO_POST_ENABLED", "").strip().lower() != "true" and not dry and not test:
        print("social posting is off (ZERNIO_POST_ENABLED is not true), skipping")
        return
    if res["status"] != "OK" and not dry and not test:
        print(f"status {res['status']}, not posted to social media")
        return
    platforms = [p.strip().lower() for p in (os.environ.get("ZERNIO_PLATFORMS") or "facebook,twitter").split(",") if p.strip()]
    unknown = [p for p in platforms if p not in SHAPE]
    if unknown:
        raise SystemExit(f"ZERNIO_PLATFORMS has platforms this script does not post images to: {', '.join(unknown)}")
    if test:
        for p in platforms:
            if p != "facebook":
                print(f"private test: {p} skipped (no private posts there)")
        platforms = ["facebook"]

    wide, tall = map(Path, res["files"])
    made, clips = {}, {}
    for p in platforms:
        kind = (wide if SHAPE[p] == "wide" else tall, WIDTH[p])
        if kind not in made:
            made[kind] = jpeg(*kind)
        clips[p] = made[kind]
    text, folder = caption(res), wide.parent
    if dry:
        for p in platforms:
            print(f"dry run: would post {clips[p].name} ({clips[p].stat().st_size / 1e6:.2f} MB) to {p} with:")
        print(text)
        return

    key = clean_key(os.environ.get("ZERNIO_API_KEY", ""))
    if not key:
        raise SystemExit("the secret ZERNIO_API_KEY is empty")
    found = accounts(key)
    urls, failed = {}, []
    for p in platforms:
        acc = found.get(p, [])
        if len(acc) != 1:
            print(f"{p}: {len(acc)} connected accounts in Zernio, need exactly one, not posted")
            failed.append(p)
            continue
        try:
            clip = clips[p]
            if clip not in urls:   # one upload per image
                urls[clip] = upload(key, clip, "image/jpeg")
            run = f"/test-{os.environ.get('GITHUB_RUN_ID', '0')}" if test else ""
            idem = str(uuid.uuid5(uuid.NAMESPACE_URL, f"kanz-radar/post-{mk}/{res['date']}/{p}{run}"))
            out = post(key, p, acc[0]["_id"], text, urls[clip], idem, draft=test, kind="image", extra={})
        except Exception as e:   # noqa: BLE001 - one platform failing never holds the others back
            out = {"status": "failed", "errorMessage": str(e)[:400]}
        if test:
            print("private test, Zernio answered:", json.dumps(out, ensure_ascii=False)[:800])
            if out.get("status") == "failed":
                failed.append(p)
            continue
        if out.get("status") == "published":
            link = out.get("platformPostUrl")
            if not link and p == "twitter" and out.get("platformPostId"):
                link = f"https://x.com/i/status/{out['platformPostId']}"
            social_links.add(f"post-{mk}", folder, p, link)
            print(f"posted to {p} (@{acc[0].get('username')}): {out.get('platformPostUrl')}")
        else:
            print(f"{p} NOT posted: status {out.get('status')}, {out.get('errorCategory', '')} {out.get('errorMessage', '')}".strip())
            failed.append(p)
    if failed:
        raise SystemExit(f"social posting: not posted to {', '.join(failed)}")


if __name__ == "__main__":
    main()
