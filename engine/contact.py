"""Tile review stills into one contact sheet: python engine/contact.py <folder> <out.jpg> [width]

One sheet is cheaper to review than many separate images (for people and for agents)."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def label_font(size=20):
    for f in ["C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def sheet(src, out, w=360):
    src, out = Path(src), Path(out)
    files = sorted(list(src.glob("*.png")) + list(src.glob("*.jpg")))
    h = int(w * 1920 / 1080)
    cols = min(6, len(files))
    rows = (len(files) + cols - 1) // cols
    img = Image.new("RGB", (cols * w, rows * (h + 30)), "white")
    d = ImageDraw.Draw(img)
    font = label_font()
    for i, f in enumerate(files):
        x, y = (i % cols) * w, (i // cols) * (h + 30)
        img.paste(Image.open(f).convert("RGB").resize((w, h)), (x, y))
        d.text((x + 6, y + h + 4), f.stem, fill="black", font=font)
    img.save(out, quality=88)
    return out


if __name__ == "__main__":
    print(sheet(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 360))
