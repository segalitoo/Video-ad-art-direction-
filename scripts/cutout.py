#!/usr/bin/env python3
"""Cut an object out of a plain, one-colour backdrop (a colour key), for layouts where type
sits behind the object.

Shoot the object on a seamless backdrop in a colour the object does not contain (the plane on
mint, the coins on navy). The backdrop colour is sampled from the image border; pixels close to
it go transparent, with a soft ramp so paper edges stay clean.

    python scripts/cutout.py out/A-plane_1.png -o cut/A-plane_1.png
    python scripts/cutout.py out/A-coins_1.png --near 18 --far 42 --check cut/check.png

--near: colour distance (Lab) under which a pixel is backdrop. --far: distance over which it is
object. Between the two, alpha ramps. --choke pulls the edge in by a few pixels. The backdrop's
own shadow is dropped on purpose: the layout adds a clean shadow for its own light. --check writes the cut-out over a checkerboard and a
dark and a light field, to look for fringes before it goes to Figma.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from judge import srgb_to_lab as lab


def border_colour(img, band=12):
    w, h = img.size
    px = []
    for box in ((0, 0, w, band), (0, h - band, w, h), (0, 0, band, h), (w - band, 0, w, h)):
        px += list(img.crop(box).resize((64, 8)).get_flattened_data())
    px.sort(key=sum)
    mid = px[len(px) // 4: 3 * len(px) // 4]          # drop the darkest and lightest quarters
    return tuple(sum(c[i] for c in mid) // len(mid) for i in range(3))


def cut(img, near, far, choke=1, chroma=False, despill=False):
    img = img.convert("RGB")
    key = lab(border_colour(img))
    small = img if max(img.size) <= 1600 else img.resize((img.width // 2, img.height // 2))
    ramp = []
    for p in small.get_flattened_data():
        l = lab(p)
        dl = 0.0 if chroma else max(0.0, l[0] - key[0])   # darker than the backdrop = its shadow
        d = (dl ** 2 + (l[1] - key[1]) ** 2 + (l[2] - key[2]) ** 2) ** 0.5
        ramp.append(0 if d <= near else 255 if d >= far else round(255 * (d - near) / (far - near)))
    alpha = Image.new("L", small.size)
    alpha.putdata(ramp)
    alpha = alpha.filter(ImageFilter.MedianFilter(3))
    # The silhouette: close small gaps (shaded sides, dark seams between layers), then fill every
    # hole the backdrop cannot reach from the border. Inside it alpha is full; outside it nothing
    # survives, which also drops uneven backdrop light far from the object.
    solid = alpha.point(lambda a: 255 if a > 127 else 0)
    k = max(3, (min(solid.size) // 60) | 1)
    closed = solid.filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.MinFilter(k))
    w, h = closed.size
    for xy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if closed.getpixel(xy) == 0:
            ImageDraw.floodfill(closed, xy, 128)
    core = closed.point(lambda v: 0 if v == 128 else 255)
    near_core = core.filter(ImageFilter.MaxFilter(5))
    alpha = ImageChops.multiply(ImageChops.lighter(alpha, core.filter(ImageFilter.MinFilter(5))), near_core)
    alpha = alpha.resize(img.size, Image.LANCZOS)
    if choke:                                          # pull the edge in: drops the backdrop fringe
        alpha = alpha.filter(ImageFilter.MinFilter(2 * choke + 1)).filter(ImageFilter.GaussianBlur(choke * 0.6))
    out = img.convert("RGBA")
    if despill:                                        # backdrop colour seen through gaps: make it neutral
        kr, kg, kb = border_colour(img)
        dom = max(range(3), key=lambda i: (kr, kg, kb)[i] - sum((kr, kg, kb)) / 3)
        def fix(px):
            r, g, b, a_ = px
            c = (r, g, b)
            excess = c[dom] - max(c[i] for i in range(3) if i != dom)
            if excess <= 4:
                return px
            y = round(0.299 * r + 0.587 * g + 0.114 * b)
            return (y, y, y, a_)
        out.putdata([fix(px) for px in out.get_flattened_data()])
    out.putalpha(alpha)
    bbox = alpha.point(lambda a: 255 if a > 24 else 0).getbbox()
    return out.crop(bbox) if bbox else out, border_colour(img)


def check_sheet(cut_img, path):
    w, h = cut_img.size
    sheet = Image.new("RGB", (w * 3 + 40, h + 20), "white")
    tiles = []
    checker = Image.new("RGB", (w, h), "#ddd")
    for y in range(0, h, 24):
        for x in range(0, w, 24):
            if (x // 24 + y // 24) % 2:
                checker.paste("#fff", (x, y, min(x + 24, w), min(y + 24, h)))
    tiles = [checker, Image.new("RGB", (w, h), "#1E2A44"), Image.new("RGB", (w, h), "#F4F1EA")]
    for i, t in enumerate(tiles):
        t.paste(cut_img, (0, 0), cut_img)
        sheet.paste(t, (10 + i * (w + 10), 10))
    sheet.thumbnail((2400, 2400))
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--near", type=float, default=16)
    ap.add_argument("--far", type=float, default=38)
    ap.add_argument("--choke", type=int, default=1, help="pixels to pull the edge in (removes fringe)")
    ap.add_argument("--chroma", action="store_true",
                    help="key on colour only, ignore brightness: for a neutral object on a coloured backdrop with a gradient")
    ap.add_argument("--despill", action="store_true", help="turn pixels tinted by the backdrop colour neutral grey (white or grey objects only)")
    ap.add_argument("--check")
    a = ap.parse_args()
    img, key = cut(Image.open(a.image), a.near, a.far, a.choke, a.chroma, a.despill)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    img.save(a.out)
    print(f"{a.out}: {img.size[0]}x{img.size[1]}, backdrop #{key[0]:02X}{key[1]:02X}{key[2]:02X}")
    if a.check:
        check_sheet(img, a.check)
        print(f"wrote {a.check}")


if __name__ == "__main__":
    main()
