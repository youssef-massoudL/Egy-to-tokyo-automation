"""Satellite map base for a Market Radar edition: reprojects NASA Blue Marble (equirectangular) to the edition's Mercator map and grades it.

    python make_photo.py <project_dir>

Writes <project_dir>/assets/photo/: base.jpg (the whole map, dark Kanz grade, edges fading to the background) and, per country that can light up,
<id>-up.jpg (lavender), <id>-dn.jpg (red), <id>-cl.jpg (grey), plus manifest.js with each crop's box. Crops keep memory low while rendering.
Source: NASA Earth Observatory, Blue Marble Next Generation with Topography and Bathymetry, December 2004 (public domain), source/ folder.
"""
import json
import os
import re
import sys
from pathlib import Path

os.environ["OPENCV_IO_MAX_IMAGE_PIXELS"] = str(2 ** 40)
import cv2  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
SRC = HERE / "source" / "world.topo.bathy.200412.3x21600x10800.jpg"
BG = np.array([26, 22, 23], np.float32)  # BGR of the charcoal the map fades into
FADE = 900  # world px over which the base fades out at the map's edges (~125 px on screen in the pulled-back overview)


def rgb(h):  # hex -> BGR 0-255
    return np.array([int(h[5:7], 16), int(h[3:5], 16), int(h[1:3], 16)], np.float32)


# shadow -> mid -> highlight of each country grade: the land's real light and dark, in one brand colour
DUO = {"up": ("#2d1647", "#9a6cc6", "#ecd9fb"), "dn": ("#2c0a0b", "#c2423b", "#ffb8b1"), "cl": ("#1b191e", "#6d6875", "#c0bbc8")}


def duotone(img, key):
    """The land's real light and dark in one brand colour. Exposure is set per country (a desert and a jungle end up equally readable),
    with local contrast so bright deserts keep their terrain instead of going flat white."""
    lum = (img[..., 0] * 0.114 + img[..., 1] * 0.587 + img[..., 2] * 0.299) / 255
    detail = lum + 1.6 * (lum - cv2.GaussianBlur(lum, (0, 0), 22))
    land = detail[lum > 0.1]
    lo, hi = (np.percentile(land, 3), np.percentile(land, 99)) if land.size > 100 else (0.05, 0.8)
    t = 0.14 + 0.72 * np.clip((detail - lo) / max(hi - lo, 0.05), 0, 1) ** 0.95
    t = t[..., None]
    a, b, c = (rgb(x) for x in DUO[key])
    out = np.where(t < 0.5, a + (b - a) * (t / 0.5), b + (c - b) * ((t - 0.5) / 0.5))
    return np.clip(out * 0.92 + img * 0.08, 0, 255)


def base_grade(img):
    """Dark and low in colour, leaning purple: still clearly a photo of the Earth, never competing with the lit countries."""
    lum = (img[..., 0] * 0.114 + img[..., 1] * 0.587 + img[..., 2] * 0.299)[..., None]
    mixed = img * 0.26 + lum * 0.74
    tint = np.array([0.98, 0.74, 0.88], np.float32)  # BGR: pull green down, lean purple
    out = mixed * tint * 0.52
    return np.clip(out + np.array([20, 10, 15], np.float32), 0, 255)


def save(path, img, params):
    ok, buf = cv2.imencode(".jpg", img, params)  # cv2.imwrite cannot write to non-ASCII Windows paths
    assert ok, path
    buf.tofile(path)


def main():
    d = Path(sys.argv[1]).resolve()
    txt = (d / "assets" / "map-data.js").read_text(encoding="utf-8")
    M = json.loads(txt[txt.index("window.MAP=") + len("window.MAP="):].rstrip().rstrip(";"))
    W, H, S0 = M["W"], M["H"], M["S0"]
    lon0, lat0 = M.get("LON0", 15), M.get("LAT0", 52)
    world = cv2.imdecode(np.fromfile(SRC, np.uint8), cv2.IMREAD_COLOR)  # cv2.imread cannot open non-ASCII Windows paths
    assert world is not None, SRC
    sh, sw = world.shape[:2]
    mer0 = np.log(np.tan(np.pi / 4 + np.radians(lat0) / 2))
    lons = lon0 + np.degrees(np.arange(W, dtype=np.float64) / S0)
    lats = np.degrees(2 * np.arctan(np.exp(mer0 - np.arange(H, dtype=np.float64) / S0)) - np.pi / 2)
    mx = (((lons + 180) % 360) * sw / 360).astype(np.float32)
    my = ((90 - lats) * sh / 180).astype(np.float32)
    # remap in tiles: cv2.remap's coordinate maps are limited to 32767 px and a full map at once is heavy
    photo = np.zeros((H, W, 3), np.uint8)
    for y0 in range(0, H, 1024):
        ys = my[y0:y0 + 1024]
        x1, y1 = np.meshgrid(mx, ys)
        photo[y0:y0 + 1024] = cv2.remap(world, x1, y1, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    del world
    out = d / "assets" / "photo"
    out.mkdir(parents=True, exist_ok=True)
    jpg = [cv2.IMWRITE_JPEG_QUALITY, 84]

    base = base_grade(photo.astype(np.float32))
    fx = np.clip(np.minimum(np.arange(W), W - 1 - np.arange(W)) / FADE, 0, 1)
    fy = np.clip(np.minimum(np.arange(H), H - 1 - np.arange(H)) / FADE, 0, 1)
    f = (fx[None, :] * fy[:, None])[..., None].astype(np.float32)
    f = f * f * (3 - 2 * f)  # smoothstep
    base = base * f + BG * (1 - f)
    save(out / "base.jpg", base.astype(np.uint8), jpg)
    del base

    boxes = {}
    for c in M["countries"]:
        if not c.get("id"):
            continue
        nums = np.array(re.findall(r"-?\d+\.?\d*", c["d"]), np.float64)
        xs, ys = nums[0::2], nums[1::2]
        x0, x1 = int(max(0, xs.min() - 4)), int(min(W, xs.max() + 4))
        y0, y1 = int(max(0, ys.min() - 4)), int(min(H, ys.max() + 4))
        crop = photo[y0:y1, x0:x1].astype(np.float32)
        for key in DUO:
            save(out / f"{c['id']}-{key}.jpg", duotone(crop, key).astype(np.uint8), jpg)
        boxes[c["id"]] = {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
    (out / "manifest.js").write_text("window.PHOTO=" + json.dumps(boxes) + ";\n", encoding="utf-8")
    print(d.name, "base", W, "x", H, "countries", sorted(boxes))


main()
