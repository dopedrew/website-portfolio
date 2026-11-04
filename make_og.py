#!/usr/bin/env python3
"""
Draw the 1200x630 Open Graph card.

The site previously pointed og:image at icon-512.png, a square app icon, so
every LinkedIn/Slack/X share rendered a tiny logo instead of a card. Link
unfurlers want 1200x630; anything else gets letterboxed or cropped.

Drawn from the same tokens as style.css so the card and the site match.
    python3 make_og.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
FONTS = Path("/home/dopedrew/ops/tools/fonts")
# Source Serif 4 (the site webfont) is not installed locally; Noto Serif
# Display is the closest available transitional serif and keeps the card
# reading like the site's headlines rather than like the body sans.
SERIF = Path("/usr/share/fonts/truetype/noto/NotoSerifDisplay-Regular.ttf")
SANS = FONTS / "Archivo-VF.ttf"

BG = (246, 243, 238)      # --bg          #f6f3ee
TEXT = (29, 26, 21)       # --text        #1d1a15
MUTED = (110, 100, 89)    # --muted       #6e6459
ACCENT = (138, 101, 48)   # --accent      #8a6530

W, H = 1200, 630


def _font(path: Path, size: int, weight: int | None = None):
    f = ImageFont.truetype(str(path), size)
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    serif = _font(SERIF if SERIF.exists() else SANS, 76)
    mono_ish = _font(SANS, 24, 500)
    body = _font(SANS, 30, 400)

    x = 86
    d.text((x, 150), "Andrew Hogan", font=serif, fill=TEXT)
    d.text((x, 262), "SECURITY ENGINEER  ·  U.S. ARMY VETERAN",
           font=mono_ish, fill=ACCENT)
    d.text((x, 330), "Threat intelligence, detection engineering,",
           font=body, fill=MUTED)
    d.text((x, 372), "and the tools I build to do both.", font=body, fill=MUTED)

    # Rule + wordmark, echoing the site's hero-meta divider.
    d.line([(x, 462), (W - x, 462)], fill=(29, 26, 21, 40), width=2)
    d.text((x, 492), "andrew-hogan.com", font=mono_ish, fill=MUTED)

    ah = _font(SANS, 44, 800)
    bbox = d.textbbox((0, 0), "AH.", font=ah)
    d.text((W - x - (bbox[2] - bbox[0]), 482), "AH", font=ah, fill=TEXT)
    ah_w = d.textlength("AH", font=ah)
    d.text((W - x - (bbox[2] - bbox[0]) + ah_w, 482), ".", font=ah, fill=ACCENT)

    img.save(ROOT / "og-image.png", "PNG", optimize=True)
    print(f"wrote og-image.png ({W}x{H})")


if __name__ == "__main__":
    main()
