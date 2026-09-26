#!/usr/bin/env python3
"""Set the type on a kept static plate and export every platform size.

    python scripts/static_compose.py storyboard.yml A1 --plate 4:5=keyframes/A1_4x5.png --plate 9:16=keyframes/A1_9x16.png
    python scripts/static_compose.py storyboard.yml A1 --plate 4:5=a.png --plate 9:16=b.png --font Recoleta-SemiBold.ttf

For each platform the static runs on, and each size that platform takes, it:
  1. cuts the size from the plate whose shape is closest (cover-fit, centred),
  2. sets the headline in the plate's empty band (copy_space), sized to fit in two lines,
  3. sets the wordmark and a CTA button on one row at the bottom of the safe area; on
     placements that draw their own CTA (Stories, TikTok) it skips the button and puts
     the headline in the top band with the wordmark under it,
  4. picks light or dark type from the image behind it, and adds a soft scrim only
     when the contrast would fall under WCAG AA (4.5:1),
  5. writes a JPG and reports what it did.

Text stays inside each platform's safe zone from platforms/specs.yml. Type is set
here, from the lock, and never generated: the plates carry no text on purpose.
Needs Pillow (pip install pillow).
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

from common import fail, load_specs, load_storyboard, parse_aspect

FALLBACK_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "C:/Windows/Fonts/georgiab.ttf",
]
FALLBACK_BODY = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
MIN_CONTRAST = 4.5


# ---------- colour

def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(rgb):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def palette_role(lock, *words, default):
    for c in lock.get("palette") or []:
        role = str(c.get("role", "")).lower()
        if all(w in role for w in words):
            return hex_rgb(c["hex"])
    return default


# ---------- fonts

def find_font(explicit, family, fallbacks):
    if explicit:
        if not Path(explicit).exists():
            fail(f"font not found: {explicit}")
        return explicit, False
    if family and shutil.which("fc-match"):
        out = subprocess.run(["fc-match", "-f", "%{file}", family], capture_output=True, text=True).stdout
        if out and Path(out).exists() and family.split()[0].lower() in Path(out).name.lower():
            return out, False
    for f in fallbacks:
        if Path(f).exists():
            return f, True
    fail("no usable font found; pass --font path/to/font.ttf")


def wrap(draw, text, font, width):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if draw.textlength(test, font=font) <= width or not line:
            line = test
        else:
            lines.append(line)
            line = w
    lines.append(line)
    return lines


def balance(draw, text, font):
    """Best two-line break: lines as even as possible, a break after punctuation strongly preferred."""
    words = text.split()
    best, best_score = None, None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        wa, wb = draw.textlength(a, font=font), draw.textlength(b, font=font)
        score = abs(wa - wb) - (10_000 if a[-1] in ".,!?;:" else 0)
        if best_score is None or score < best_score:
            best, best_score = [a, b], score
    return best


def fit_headline(draw, text, font_path, width, start, max_lines=2):
    size = start
    while size > 12:
        font = ImageFont.truetype(font_path, size)
        if draw.textlength(text, font=font) <= width:
            return font, [text]
        if max_lines >= 2 and len(text.split()) > 1:
            lines = balance(draw, text, font)
            if all(draw.textlength(l, font=font) <= width for l in lines):
                return font, lines
        size -= 2
    font = ImageFont.truetype(font_path, 12)
    return font, wrap(draw, text, font, width)


# ---------- layout

def cover(img, w, h):
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def nearest(ratio, plates):
    w, h = parse_aspect(ratio)
    return min(plates, key=lambda p: abs(parse_aspect(p)[0] / parse_aspect(p)[1] - w / h))


def compose(plate, size, zone, item, lock, head_font, body_font, native_cta=False):
    """native_cta: the platform draws its own button (Stories, TikTok). Then no CTA is drawn,
    the headline goes in the top band (the bottom third is under the platform's UI) and the
    wordmark sits under the headline."""
    W, H = size
    img = cover(plate.convert("RGB"), W, H)
    draw = ImageDraw.Draw(img, "RGBA")
    notes = []

    side = max(zone["left"], zone["right"]) / 100 * W + 0.05 * W
    top = zone["top"] / 100 * H + 0.03 * H
    bottom = H - zone["bottom"] / 100 * H - 0.03 * H
    text_w = W - 2 * side
    unit = min(W, H)

    # Bottom row: wordmark left, CTA button right.
    cta_font = ImageFont.truetype(body_font, round(unit * 0.036))
    cta = "" if native_cta else str(item.get("cta", "")).strip()
    pad_x, pad_y = unit * 0.035, unit * 0.022
    cta_w = draw.textlength(cta, font=cta_font) + 2 * pad_x if cta else 0
    cta_h = cta_font.size + 2 * pad_y
    row_y = bottom - cta_h

    # Headline in the empty band.
    headline = str(item.get("headline", "")).strip()
    hfont, lines = fit_headline(draw, headline, head_font, text_w, round(unit * 0.085))
    line_h = round(hfont.size * 1.12)
    block_h = line_h * len(lines)
    if item.get("copy_space") == "bottom" and not native_cta:
        head_y = row_y - unit * 0.05 - block_h
    else:
        head_y = top

    band = (int(side), int(max(head_y, 0)), int(W - side), int(min(head_y + block_h, H)))
    region = img.crop(band).resize((1, 1), Image.BOX).getpixel((0, 0))
    light = palette_role(lock, "type", "dark", default=(255, 255, 255))
    dark = palette_role(lock, "type", "light", default=(20, 20, 20))
    ink = dark if contrast(dark, region) >= contrast(light, region) else light
    ratio = contrast(ink, region)
    if ratio < MIN_CONTRAST:
        # A soft scrim behind the headline band only, in the opposite tone of the ink.
        tone = (0, 0, 0) if ink == light else (255, 255, 255)
        y0, y1 = band[1] - unit * 0.06, band[3] + unit * 0.06
        for i in range(int(y1 - y0)):
            t = i / max(y1 - y0 - 1, 1)
            a = int(150 * (1 - abs(t - 0.5) * 2) ** 0.6)
            draw.line([(0, y0 + i), (W, y0 + i)], fill=tone + (a,))
        region2 = img.crop(band).resize((1, 1), Image.BOX).getpixel((0, 0))
        notes.append(f"scrim added (contrast {ratio:.1f} -> {contrast(ink, region2):.1f})")
        ratio = contrast(ink, region2)

    for i, line in enumerate(lines):
        lw = draw.textlength(line, font=hfont)
        draw.text(((W - lw) / 2, head_y + i * line_h), line, font=hfont, fill=ink)

    mark = (lock.get("hero") or {}).get("wordmark") or lock.get("meta", {}).get("brand", "")
    if mark and native_cta:
        mfont = ImageFont.truetype(head_font, round(unit * 0.045))
        my = head_y + block_h + unit * 0.035
        mw = draw.textlength(mark, font=mfont)
        mregion = img.crop((int((W - mw) / 2), int(my), int((W + mw) / 2), int(my + mfont.size))).resize((1, 1), Image.BOX).getpixel((0, 0))
        mink = dark if contrast(dark, mregion) >= contrast(light, mregion) else light
        draw.text(((W - mw) / 2, my), mark, font=mfont, fill=mink)
    elif mark:
        mfont = ImageFont.truetype(head_font, round(unit * 0.042))
        mregion = img.crop((int(side), int(row_y), int(W / 2), int(row_y + cta_h))).resize((1, 1), Image.BOX).getpixel((0, 0))
        mink = dark if contrast(dark, mregion) >= contrast(light, mregion) else light
        draw.text((side, row_y + (cta_h - mfont.size) / 2 - unit * 0.004), mark, font=mfont, fill=mink)
    if cta:
        hero_rgb = palette_role(lock, "hero", default=(0, 0, 0))
        on_hero = light if contrast(light, hero_rgb) >= contrast(dark, hero_rgb) else dark
        x1 = W - side
        draw.rounded_rectangle((x1 - cta_w, row_y, x1, row_y + cta_h), radius=cta_h / 2, fill=hero_rgb)
        draw.text((x1 - cta_w + pad_x, row_y + pad_y - unit * 0.004), cta, font=cta_font, fill=on_hero)
        if contrast(on_hero, hero_rgb) < 3:
            notes.append(f"CTA contrast {contrast(on_hero, hero_rgb):.1f} is under 3:1")

    notes.insert(0, f"headline {hfont.size}px in {len(lines)} line(s), contrast {ratio:.1f}")
    return img, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("storyboard")
    ap.add_argument("static", help="static id, e.g. A1")
    ap.add_argument("--plate", action="append", default=[], metavar="RATIO=PATH",
                    help="a kept plate for one ratio; repeat for each plate ratio")
    ap.add_argument("--font", help="headline font file (default: the lock's type family, else a fallback)")
    ap.add_argument("--body-font", help="CTA font file")
    ap.add_argument("--out-dir", default=None, help="default: exports/ next to the storyboard")
    args = ap.parse_args()

    board, lock = load_storyboard(args.storyboard)
    specs = load_specs()
    item = next((s for s in board.get("statics") or [] if s.get("id") == args.static), None)
    if not item:
        fail(f"no static '{args.static}' in {args.storyboard}")

    plates = {}
    for entry in args.plate:
        ratio, _, path = entry.partition("=")
        if not Path(path).exists():
            fail(f"plate not found: {path}")
        plates[ratio] = Image.open(path)
    if not plates:
        fail("pass at least one --plate RATIO=PATH")

    family = (lock.get("type") or {}).get("family", "").split("(")[0].strip()
    head_font, head_fallback = find_font(args.font, family, FALLBACK_FONTS)
    body_font, _ = find_font(args.body_font, None, FALLBACK_BODY) if not args.body_font else (args.body_font, False)
    if head_fallback:
        print(f"WARN  font '{family}' not installed; using {Path(head_font).name}. Pass --font for the real one.")

    out_dir = Path(args.out_dir or Path(args.storyboard).parent / "exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    for pid in item.get("platforms") or []:
        spec = specs["platforms"][pid]
        for ratio, (w, h) in spec["static"]["sizes"].items():
            source = nearest(ratio, list(plates))
            img, notes = compose(plates[source], (w, h), spec["safe_zone_pct"], item, lock, head_font, body_font,
                                 native_cta=spec["static"].get("native_cta", False))
            name = f"{item['id']}_{pid}_{w}x{h}.jpg"
            img.save(out_dir / name, "JPEG", quality=92, optimize=True)
            print(f"wrote {out_dir / name}  (from {source} plate; {'; '.join(notes)})")


if __name__ == "__main__":
    main()
