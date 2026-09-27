#!/usr/bin/env python3
"""Render static ads from a layout file, with the brand font, the way Figma lays them out.

The Figma builder (scripts/figma/*.js) is the design source; this renders the same layouts
locally when Figma is out of reach (plan limits, no connector) and for export. Text follows
Figma's rules: letter spacing in % of the size, line height in %, the font's ascent and descent
centred in the line box, kerning kept (raqm).

    python scripts/static_render.py examples/driftpay/statics-v2/layout.yml -o examples/driftpay/statics-v2/final
    python scripts/static_render.py layout.yml --only "B · A1 1200x1200" --sheet review.jpg

Layout file: `fonts` (style -> ttf), `colors` (name -> hex), `defaults`, `frames`. Each frame has
name, w, h, bg and `items`, drawn in order:

  image     src, x, y, w, h (cover-fit), shadow {y, blur, opacity}
  fade      x, y, w, h, color, edge top|bottom|left (opaque at that edge, clear at the other)
  text      text, style, size, color, x, y, ls, lh, width (wraps), fit (fill w − 2·fit), center
  stack     x, y, gap, lines [{text, style, size, color, ls, lh}], accent {color, mode fill|underline};
            the part of a line between |bars| is the accent
  wordmark  x, y, size, ink, mark (colour), name
  cta       label, size, x, y | below <id> + gap | bottom <px>, fill, ink
  chip      x, y, words [[text, style, color], ...], dot (colour)

Any item can carry `id` (for `below`) and `bottom: N` (placed N px above the frame's bottom edge).
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import yaml

from common import ROOT, fail

_fonts = {}


def font(path, size):
    key = (str(path), round(size, 2))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(str(path), max(1, round(size)))
    return _fonts[key]


def rgb(v, colors):
    v = colors.get(v, v)
    v = v.lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


class Ctx:
    def __init__(self, layout, base):
        self.colors = layout.get("colors") or {}
        self.fonts = {k: (base / v if not Path(v).is_absolute() else Path(v)) for k, v in layout["fonts"].items()}
        self.base = base
        self.boxes = {}

    def f(self, style, size):
        if style not in self.fonts:
            fail(f"no font for style {style}")
        return font(self.fonts[style], size)

    def c(self, v):
        return rgb(v, self.colors)


def line_width(fnt, text, size, ls):
    return fnt.getlength(text) + max(0, len(text) - 1) * ls / 100 * size


def draw_line(img, ctx, x, top, text, style, size, colors_at, ls=-2, lh=100):
    """One line of text; colors_at(i) gives the colour of character i. Returns (width, box height)."""
    fnt = ctx.f(style, size)
    asc, desc = fnt.getmetrics()
    box = size * lh / 100
    base = top + (box - (asc + desc)) / 2 + asc
    d = ImageDraw.Draw(img)
    track = ls / 100 * size
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        cx = x + fnt.getlength(text[:i]) + i * track
        d.text((cx, base), ch, font=fnt, fill=colors_at(i), anchor="ls")
    return line_width(fnt, text, size, ls), box


def wrap(ctx, text, style, size, ls, width):
    fnt = ctx.f(style, size)
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if cur and line_width(fnt, trial, size, ls) > width:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    return lines + ([cur] if cur else [])


def shadow_layer(size, alpha, dx, dy, blur, opacity, color=(30, 22, 14)):
    sh = Image.new("RGBA", size, color + (0,))
    a = Image.new("L", size, 0)
    a.paste(alpha.point(lambda v: round(v * opacity)), (dx, dy))
    if blur:
        a = a.filter(ImageFilter.GaussianBlur(blur / 2))
    sh.putalpha(a)
    return sh


def paste_with_shadow(canvas, im, x, y, shadow):
    if shadow:
        full = Image.new("L", canvas.size, 0)
        full.paste(im.getchannel("A"), (round(x), round(y)))
        canvas.alpha_composite(shadow_layer(canvas.size, full, 0, round(shadow.get("y", 0)),
                                            shadow.get("blur", 0), shadow.get("opacity", 0.25)))
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(im, (round(x), round(y)), im)
    canvas.alpha_composite(layer)


def cover(src, w, h):
    im = Image.open(src).convert("RGBA")
    s = max(w / im.width, h / im.height)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    left, top = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((left, top, left + round(w), top + round(h)))


def place_y(it, h, fh, ctx):
    if "below" in it:
        b = ctx.boxes[it["below"]]
        return b[1] + b[3] + it.get("gap", 0)
    if "bottom" in it:
        return fh - it["bottom"] - h
    return it.get("y", 0)


def render_frame(fr, ctx):
    W, H = fr["w"], fr["h"]
    canvas = Image.new("RGBA", (W, H), ctx.c(fr.get("bg", "#FFFFFF")) + (255,))
    ctx.boxes = {}
    for it in fr["items"]:
        kind = it["type"]
        box = None
        if kind == "image":
            im = cover(ctx.base / it["src"], it["w"], it["h"])
            paste_with_shadow(canvas, im, it["x"], it["y"], it.get("shadow"))
            box = (it["x"], it["y"], it["w"], it["h"])
        elif kind == "fade":
            w, h = round(it["w"]), round(it["h"])
            col = ctx.c(it["color"])
            g = Image.new("L", (w, h))
            n = h if it["edge"] in ("top", "bottom") else w
            ramp = [round(255 * (1 - i / max(1, n - 1))) for i in range(n)]
            if it["edge"] == "bottom":
                ramp.reverse()
            if it["edge"] in ("top", "bottom"):
                g.putdata([ramp[y] for y in range(h) for _ in range(w)])
            else:
                g.putdata([ramp[x] for _ in range(h) for x in range(w)])
            layer = Image.new("RGBA", canvas.size, col + (0,))
            solid = Image.new("RGBA", (w, h), col + (255,))
            solid.putalpha(g)
            layer.paste(solid, (round(it["x"]), round(it["y"])))
            canvas.alpha_composite(layer)
            box = (it["x"], it["y"], w, h)
        elif kind == "text":
            style, size, ls, lh = it["style"], it["size"], it.get("ls", -2), it.get("lh", 100)
            if "fit" in it:                                  # fill the width edge to edge
                target = W - 2 * it["fit"]
                size = size * target / line_width(ctx.f(style, size), it["text"], size, ls)
                size = int(size)
            lines = wrap(ctx, it["text"], style, size, ls, it["width"]) if it.get("width") else [it["text"]]
            col = ctx.c(it["color"])
            fnt = ctx.f(style, size)
            widths = [line_width(fnt, t, size, ls) for t in lines]
            tw, th = max(widths), size * lh / 100 * len(lines)
            x = (W - tw) / 2 if it.get("center") else it["x"]
            y = place_y(it, th, H, ctx)
            for i, t in enumerate(lines):
                draw_line(canvas, ctx, x, y + i * size * lh / 100, t, style, size, lambda _: col, ls, lh)
            box = (x, y, it.get("width") or tw, th)
        elif kind == "stack":
            x, y0 = it["x"], it["y"]
            y, gap, acc = y0, it.get("gap", 0), it.get("accent") or {}
            wmax = 0
            for ln in it["lines"]:
                raw = ln["text"]
                plain = raw.replace("|", "")
                a, b = raw.find("|"), raw.rfind("|") - 1
                base_col, acc_col = ctx.c(ln["color"]), ctx.c(acc.get("color", ln["color"]))
                fill_mode = acc.get("mode", "fill") == "fill"
                colors_at = (lambda i, a=a, b=b: acc_col if fill_mode and a >= 0 and a <= i < b else base_col)
                size, ls, lh = ln["size"], ln.get("ls", -2), ln.get("lh", 100)
                w, bh = draw_line(canvas, ctx, x, y, plain, ln["style"], size, colors_at, ls, lh)
                if not fill_mode and a >= 0:
                    fnt = ctx.f(ln["style"], size)
                    ax = x + fnt.getlength(plain[:a]) + a * ls / 100 * size
                    aw = line_width(fnt, plain[a:b], size, ls)
                    bar_h = max(6, size * 0.09)
                    ImageDraw.Draw(canvas).rectangle([ax + aw * 0.02, y + bh * 0.93, ax + aw * 0.98, y + bh * 0.93 + bar_h], fill=acc_col)
                wmax = max(wmax, w)
                y += bh + gap
            box = (x, y0, wmax, y - gap - y0)
        elif kind == "wordmark":
            s, ink = it["size"], ctx.c(it["ink"])
            m = s * 0.75
            text_h = s
            row_h = max(m, text_h)
            x, y = it["x"], place_y(it, row_h, H, ctx)
            k = m / 24
            my = y + (row_h - m) / 2
            ImageDraw.Draw(canvas).polygon([(x + px * k, my + py * k) for px, py in ((0, 11), (24, 0), (13, 24), (10, 14))],
                                           fill=ctx.c(it.get("mark", "coral")))
            tx = x + m + round(s * 0.3)
            w, _ = draw_line(canvas, ctx, tx, y + (row_h - text_h) / 2, it.get("name", "Driftpay"), "Bold", s,
                             lambda _: ink, -3, 100)
            box = (x, y, tx + w - x, row_h)
        elif kind == "cta":
            s = it["size"]
            fnt = ctx.f("Bold", s)
            tw = line_width(fnt, it["label"], s, -1)
            w, h = tw + 2.2 * s, s + 1.24 * s
            x, y = it.get("x", 0), place_y(it, h, H, ctx)
            ImageDraw.Draw(canvas).rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=ctx.c(it.get("fill", "coral")))
            ink = ctx.c(it.get("ink", "navy"))
            draw_line(canvas, ctx, x + 1.1 * s, y + 0.62 * s, it["label"], "Bold", s, lambda _: ink, -1, 100)
            box = (x, y, w, h)
        elif kind == "chip":
            size, padl, padr, padv, gap, dot = 26, 22, 26, 16, 14, 16
            words = it["words"]
            ws = [line_width(ctx.f(st, size), t, size, -1) for t, st, _ in words]
            w = padl + dot + gap + sum(ws) + gap * (len(ws) - 1) + padr
            h = size + 2 * padv
            x, y = it["x"], place_y(it, h, H, ctx)
            card = Image.new("RGBA", (round(w), round(h)), (0, 0, 0, 0))
            ImageDraw.Draw(card).rounded_rectangle([0, 0, w - 1, h - 1], radius=16, fill=(255, 255, 255, 255))
            paste_with_shadow(canvas, card, x, y, {"y": 10, "blur": 28, "opacity": 0.25})
            d = ImageDraw.Draw(canvas)
            d.ellipse([x + padl, y + (h - dot) / 2, x + padl + dot, y + (h + dot) / 2], fill=ctx.c(it.get("dot", "coral")))
            cx = x + padl + dot + gap
            for (t, st, col), tw in zip(words, ws):
                c = ctx.c(col)
                draw_line(canvas, ctx, cx, y + padv, t, st, size, lambda _, c=c: c, -1, 100)
                cx += tw + gap
            box = (x, y, w, h)
        else:
            fail(f"unknown item type {kind}")
        if it.get("id") and box:
            ctx.boxes[it["id"]] = box
    return canvas.convert("RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("layout")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--only", help="render only frames whose name contains this")
    ap.add_argument("--sheet", help="also write a contact sheet of every rendered frame")
    ap.add_argument("--quality", type=int, default=92)
    a = ap.parse_args()
    lp = Path(a.layout)
    layout = yaml.safe_load(lp.read_text(encoding="utf-8"))
    ctx = Ctx(layout, lp.parent)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    done = []
    for fr in layout["frames"]:
        if a.only and a.only not in fr["name"]:
            continue
        img = render_frame(fr, ctx)
        path = out / f"{fr['file']}.jpg"
        img.save(path, quality=a.quality, subsampling=0)
        done.append((fr, img))
        print(f"{path}  {img.width}x{img.height}")
    if a.sheet and done:
        H = 520
        thumbs = [im.resize((round(im.width * H / im.height), H)) for _, im in done]
        rows, row, width = [], [], 0
        for t in thumbs:
            if row and width + t.width > 2600:
                rows.append(row)
                row, width = [], 0
            row.append(t)
            width += t.width + 16
        rows.append(row)
        W = max(sum(t.width + 16 for t in r) for r in rows) + 16
        sheet = Image.new("RGB", (W, len(rows) * (H + 16) + 16), (226, 226, 222))
        y = 16
        for r in rows:
            x = 16
            for t in r:
                sheet.paste(t, (x, y))
                x += t.width + 16
            y += H + 16
        sheet.save(a.sheet, quality=90)
        print(f"wrote {a.sheet}")


if __name__ == "__main__":
    main()
