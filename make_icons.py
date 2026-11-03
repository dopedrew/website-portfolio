#!/usr/bin/env python3
"""
Draw the site icons from the "AH." nav wordmark.

The favicon is drawn, not cropped from a screenshot: the source was a 70x37
grab of the header, which is far too small to scale up to a 512px icon
without going soft. Colours and proportions come from style.css so the icon
and the site stay in step.

The dot is deliberately kept: it is the only colour in the mark and it is
what makes a two-letter favicon read as a logo rather than as initials. It
does get small at 16px, which is fine, the AH still carries it.

Rerun after changing the brand colours:
    python3 make_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
FONT = Path("/home/dopedrew/ops/tools/fonts/Archivo-VF.ttf")  # Inter stand-in, same grotesque

BG = (10, 15, 26)        # --bg      #0a0f1a
TEXT = (226, 232, 240)   # --text    #e2e8f0
ACCENT = (59, 130, 246)  # --accent  #3b82f6

MASTER = 1024


def draw_master() -> Image.Image:
    img = Image.new("RGB", (MASTER, MASTER), BG)
    d = ImageDraw.Draw(img)

    # Size for the WHOLE mark including the dot, with margin, or the dot
    # runs off the right edge.
    size = int(MASTER * 0.44)
    font = ImageFont.truetype(str(FONT), size)
    try:
        font.set_variation_by_axes([800])  # bold, matching the nav wordmark
    except Exception:
        pass

    # Centre on the rendered ink box of the full "AH." rather than on advance
    # widths: the trailing dot's advance includes side bearing, which pushed
    # the mark left and clipped the dot.
    ink = d.textbbox((0, 0), "AH.", font=font)
    ink_w, ink_h = ink[2] - ink[0], ink[3] - ink[1]
    x = (MASTER - ink_w) / 2 - ink[0]
    y = (MASTER - ink_h) / 2 - ink[1]

    ah_w = d.textlength("AH", font=font)
    d.text((x, y), "AH", font=font, fill=TEXT)
    d.text((x + ah_w, y), ".", font=font, fill=ACCENT)
    return img


def main() -> None:
    master = draw_master()

    # favicon.ico carries the small sizes browsers actually pick from.
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
    master.resize((256, 256), Image.LANCZOS).save(
        ROOT / "favicon.ico", format="ICO", sizes=ico_sizes)

    for name, px in [("icon-192.png", 192), ("icon-512.png", 512),
                     ("apple-touch-icon.png", 180)]:
        master.resize((px, px), Image.LANCZOS).save(ROOT / name, format="PNG")

    print("wrote favicon.ico, icon-192.png, icon-512.png, apple-touch-icon.png")


if __name__ == "__main__":
    main()
