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

  image     src, x, y, w, h (cover-fit, focus [fx, fy], zoom; fit: contain keeps a cut-out whole,
            anchor floor|center), shadow {y, blur, opacity}, contact {opacity, spread, height, blur,
            color}: a soft ellipse where a cut-out stands, so it sits on the floor instead of floating
  glow      x, y, w, h, color, opacity: soft light that fades to nothing at the box edge (no seam)
  fade      x, y, w, h, color, edge top|bottom|left (opaque at that edge, clear at the other)
  text      text, style, size, color, x, y, ls, lh, width (wraps with balanced, designed line breaks;
            \n forces a break), fit (fill w − 2·fit), center, align right
  stack     x, y, gap, lines [{text, style, size, color, ls, lh}], accent {color, mode fill|underline};
            the part of a line between |bars| is the accent
  wordmark  x, y, size, ink, mark (colour), name
  cta       label, size, x, y | below <id> + gap | bottom <px>, fill, ink, style (Bold), plain (text only)
  chip      x, y, words [[text, style, color], ...], dot (colour)
  rect      x, y, w, h, fill, radius, shadow, stroke {color, width}: a card, a sticker, a column
  stars     x, y, size, count (5), filled (count), fill, empty
  marks     x, y, size, gap, color, mark check|cross, lines [text], style, ink, width: a list with a
            drawn tick or cross before each line
  bubble    x, y, text, size, width (max), side left|right, fill, ink, style: a chat message
  line      x1, y1, x2, y2, color, width, dot (radius at x1,y1): a callout leader

Any item can carry `id` (for `below`) and `bottom: N` (placed N px above the frame's bottom edge).
A frame can carry `grain` (0.03 to 0.06): fine noise that joins photo and flat colour into one
surface. It keeps the mean colour and stays off the type layer.
"""

import argparse
from itertools import combinations
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


def tracked(text):
    """Characters that take tracking: everything but word spaces, so a tight headline keeps its
    word gaps (negative tracking on a space is what made words run together)."""
    return sum(1 for c in text if c != " ")


def line_width(fnt, text, size, ls):
    return fnt.getlength(text) + max(0, tracked(text) - 1) * ls / 100 * size


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
        cx = x + fnt.getlength(text[:i]) + tracked(text[:i]) * track
        d.text((cx, base), ch, font=fnt, fill=colors_at(i), anchor="ls")
    return line_width(fnt, text, size, ls), box


WEAK_ENDS = {"a", "an", "the", "to", "of", "my", "your", "our", "his", "her", "its", "their", "and", "or",
             "but", "on", "in", "for", "with", "at", "by", "from", "is", "are", "be", "no", "not"}


def words_of(text):
    """Words split on ordinary spaces only: a no-break space binds what it joins."""
    return [w for w in str(text).split(" ") if w]


def greedy(words, measure, width):
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if cur and measure(trial) > width:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    return lines + ([cur] if cur else [])


def split_sentences(lines):
    """Lines that end one sentence and start the next after a break inside the first."""
    n = 0
    for i, t in enumerate(lines):
        starts = i == 0 or words_of(lines[i - 1])[-1][-1] in ".?!:"
        if not starts and any(w[-1] in ".?!" for w in words_of(t)[:-1]):
            n += 1
    return n


def break_cost(lines, measure, width):
    """How a designer would rate these line breaks; lower is better. Balanced lines, breaks after
    punctuation, no line ending on 'the' or 'my', no single word left alone on the last line."""
    ws = [measure(t) for t in lines]
    if max(ws) > width:
        return None
    top = max(ws)
    cost = sum(((top - w) / width) ** 2 for w in ws[:-1])     # ragged right inside the block
    if len(lines) > 1:
        cost += 0.5 * max(0, 0.6 - ws[-1] / top)              # a short tail line
        if len(words_of(lines[-1])) == 1:
            cost += 2.0                                       # an orphan
    if sum(len(words_of(t)) for t in lines) > 3:
        cost += 1.0 * sum(len(words_of(t)) == 1 for t in lines[:-1])   # a lone word mid-block
    cost += 0.8 * split_sentences(lines)
    for t in lines[:-1]:
        last = words_of(t)[-1]
        if last[-1] in ".?!:":
            cost -= 0.6
        elif last[-1] in ",;":
            cost -= 0.3
        elif last.lower() in WEAK_ENDS:
            cost += 0.8
    return cost


def clean_breaks(lines):
    """True when no line ends on a weak word and no word stands alone on a line."""
    if sum(len(words_of(t)) for t in lines) > 3 and any(len(words_of(t)) == 1 for t in lines):
        return False
    if split_sentences(lines):
        return False
    return not any(words_of(t)[-1].lower() in WEAK_ENDS for t in lines[:-1])


def balance(text, measure, width):
    """Line breaks for a headline or a short block: the fewest lines that fit, or one more when that
    lets every line end on a sentence or a clause. A \\n in the text is a forced break."""
    out = []
    for para in str(text).split("\n"):
        words = words_of(para)
        if not words:
            continue
        g = greedy(words, measure, width)
        if len(words) > 24 or len(g) == 1 and len(words) < 4:
            out += g
            continue
        best, best_cost = g, None
        for n in {len(g), len(g) + 1} if len(g) > 1 else {1, 2}:
            if n > len(words):
                continue
            for cut in combinations(range(1, len(words)), n - 1):
                idx = (0,) + cut + (len(words),)
                lines = [" ".join(words[idx[i]:idx[i + 1]]) for i in range(n)]
                c = break_cost(lines, measure, width)
                if c is None:
                    continue
                c += 0.35 * (n - len(g))
                if n == 2 and len(g) == 1:
                    c += 0.4                                  # a fitting one-liner stays one line unless the break is clean
                if best_cost is None or c < best_cost:
                    best, best_cost = lines, c
        out += best
    return out


def wrap(ctx, text, style, size, ls, width):
    fnt = ctx.f(style, size)
    return balance(text, lambda t: line_width(fnt, t, size, ls), width)


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


def contact_shadow(canvas, im, x, y, spec):
    """A soft, dark ellipse where the object stands: width of its base, a sliver tall, blurred.
    spec: {opacity, spread (x the base width), height (x the base width), blur (px)}."""
    a = im.getchannel("A")
    bb = a.getbbox()
    if not bb:
        return
    base = a.crop((bb[0], bb[3] - max(2, (bb[3] - bb[1]) // 12), bb[2], bb[3])).getbbox()
    l, r = (bb[0] + base[0], bb[0] + base[2]) if base else (bb[0], bb[2])
    w = (r - l) * spec.get("spread", 1.08)
    h = w * spec.get("height", 0.07)
    cx, cy = x + (l + r) / 2, y + bb[3] - h * 0.25
    lay = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(lay).ellipse([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], fill=round(255 * spec.get("opacity", 0.45)))
    lay = lay.filter(ImageFilter.GaussianBlur(spec.get("blur", max(4, h * 0.6))))
    tint = Image.new("RGBA", canvas.size, tuple(spec.get("color", (40, 20, 10))) + (0,))
    tint.putalpha(lay)
    canvas.alpha_composite(tint)


def cover(src, w, h, focus=None, zoom=1.0):
    """Fill w×h. focus [fx, fy] (0–1) is the point of the source kept in view; zoom > 1 crops tighter."""
    im = Image.open(src).convert("RGBA")
    s = max(w / im.width, h / im.height) * max(1.0, zoom)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    fx, fy = focus or (0.5, 0.5)
    left = min(max(0, round(fx * im.width - w / 2)), im.width - round(w))
    top = min(max(0, round(fy * im.height - h / 2)), im.height - round(h))
    return im.crop((left, top, left + round(w), top + round(h)))


def contain(src, w, h, anchor="floor"):
    im = Image.open(src).convert("RGBA")
    s = min(w / im.width, h / im.height)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    out = Image.new("RGBA", (round(w), round(h)), (0, 0, 0, 0))
    top = (round(h) - im.height) // 2 if anchor == "center" else round(h) - im.height   # default: stands on the box floor
    out.paste(im, ((round(w) - im.width) // 2, top))
    return out


def star(cx, cy, r):
    import math
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy - rr * math.sin(a)))
    return pts


def behind(canvas, box, ink):
    """The worst contrast (10th percentile) between the ink and the pixels already under a text box."""
    x, y, w, h = (round(v) for v in box)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas.width, x + w), min(canvas.height, y + h)
    if x1 <= x0 or y1 <= y0:
        return None
    region = canvas.crop((x0, y0, x1, y1)).convert("RGB")
    region.thumbnail((120, 120))
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    lum = lambda p: 0.2126 * lin(p[0] / 255) + 0.7152 * lin(p[1] / 255) + 0.0722 * lin(p[2] / 255)
    li = lum(ink)
    px = region.tobytes()
    ratios = sorted((max(li, lb) + 0.05) / (min(li, lb) + 0.05)
                    for lb in (lum(px[i:i + 3]) for i in range(0, len(px), 3)))
    return ratios[len(ratios) // 10]


def place_y(it, h, fh, ctx):
    if "below" in it:
        b = ctx.boxes[it["below"]]
        return b[1] + b[3] + it.get("gap", 0)
    if "bottom" in it:
        return fh - it["bottom"] - h
    return it.get("y", 0)


PLATE_ITEMS = {"image", "fade", "glow"}      # what a motion loop animates; everything else is the type layer


def render_frame(fr, ctx, layer=None):
    """layer None: the whole ad. 'plate': background, images and fades only (for animating).
    'type': everything else on a transparent canvas (laid over the animated plate)."""
    W, H = fr["w"], fr["h"]
    bg = ctx.c(fr.get("bg", "#FFFFFF")) + (255,)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0) if layer == "type" else bg)
    ctx.boxes = {}
    ctx.drawn = []          # (kind, (x, y, w, h) of what is visible, item, extra) for the layout checks
    for it in fr["items"]:
        kind = it["type"]
        if layer and (kind in PLATE_ITEMS) != (layer == "plate"):
            if it.get("id"):                     # keep positions for items placed `below` this one
                ctx.boxes[it["id"]] = (it.get("x", 0), it.get("y", 0), it.get("w", 0), it.get("h", 0))
            continue
        box = None
        if kind == "image":
            if it.get("fit") == "contain":
                im = contain(ctx.base / it["src"], it["w"], it["h"], it.get("anchor", "floor"))
            else:
                im = cover(ctx.base / it["src"], it["w"], it["h"], it.get("focus"), it.get("zoom", 1.0))
            if it.get("contact") and im.mode == "RGBA":
                contact_shadow(canvas, im, it["x"], it["y"], it["contact"])
            paste_with_shadow(canvas, im, it["x"], it["y"], it.get("shadow"))
            box = (it["x"], it["y"], it["w"], it["h"])
            vis = im.split()[-1].getbbox() if im.mode == "RGBA" else None
            ctx.drawn.append(("image", (it["x"] + vis[0], it["y"] + vis[1], vis[2] - vis[0], vis[3] - vis[1]) if vis else box, it, None))
        elif kind == "glow":
            gw, gh = round(it["w"]), round(it["h"])
            op = it.get("opacity", 0.35)
            # radial falloff that reaches 0 at the ellipse touching the box, with zero slope there (smoothstep):
            # no seam at the box edge, which a blurred ellipse always leaves on a flat ground
            lut = [round(255 * op * (lambda a: a * a * (3 - 2 * a))(max(0.0, 1 - v / 128))) for v in range(256)]
            g = Image.radial_gradient("L").resize((gw, gh), Image.BILINEAR).point(lut)
            col = ctx.c(it.get("color", "#FFFFFF"))
            over = Image.new("RGBA", canvas.size, col + (0,))
            over.paste(Image.new("RGBA", (gw, gh), col + (255,)), (round(it["x"]), round(it["y"])), g)
            canvas.alpha_composite(over)
            box = (it["x"], it["y"], gw, gh)
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
            over = Image.new("RGBA", canvas.size, col + (0,))     # not `layer`: that names the pass being drawn
            solid = Image.new("RGBA", (w, h), col + (255,))
            solid.putalpha(g)
            over.paste(solid, (round(it["x"]), round(it["y"])))
            canvas.alpha_composite(over)
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
            ctx.drawn.append(("text", (x, y, tw, th), it, behind(canvas, (x, y, tw, th), col)))
            for i, t in enumerate(lines):
                lx = x + (tw - widths[i]) if it.get("align") == "right" else x
                if it.get("optical") and t and not it.get("center") and it.get("align") != "right":
                    if t[0] in "\u201c\u2018\"'":
                        lx -= fnt.getlength(t[0])                        # hanging punctuation
                    else:
                        lx -= max(0, fnt.getbbox(t[0], anchor="ls")[0])  # the stem, not the side bearing, on the margin
                draw_line(canvas, ctx, lx, y + i * size * lh / 100, t, style, size, lambda _: col, ls, lh)
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
            ctx.drawn.append(("stack", box, it, None))
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
            s, st, cls = it["size"], it.get("style", "Bold"), it.get("ls", -1)
            fnt = ctx.f(st, s)
            tw = line_width(fnt, it["label"], s, cls)
            w, h = tw + 2.2 * s, s + 1.24 * s
            asc, desc = fnt.getmetrics()
            xb, cb = fnt.getbbox("x", anchor="ls"), fnt.getbbox("H", anchor="ls")
            mid = (-xb[1] - cb[1]) / 4                                   # halfway between x-height and cap height
            box_base = (s - (asc + desc)) / 2 + asc                      # where draw_line puts the baseline in its box
            if it.get("center"):
                it = dict(it, x=(W - w) / 2)
            x, y = it.get("x", 0), place_y(it, h, H, ctx)
            ink = ctx.c(it.get("ink", "navy"))
            if it.get("plain"):
                draw_line(canvas, ctx, x + 1.1 * s, y + 0.62 * s, it["label"], st, s, lambda _: ink, 4, 100)
                ImageDraw.Draw(canvas).rectangle([x + 1.1 * s, y + 1.72 * s, x + 1.1 * s + tw, y + 1.72 * s + max(2, s * 0.06)], fill=ink)
            else:
                ImageDraw.Draw(canvas).rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=ctx.c(it.get("fill", "coral")))
                top = y + h / 2 + mid - box_base                         # optical centre of the label on the pill
                draw_line(canvas, ctx, x + 1.1 * s, top, it["label"], st, s, lambda _: ink, cls, 100)
            box = (x, y, w, h)
            ctx.drawn.append(("cta", box, it, None))
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
        elif kind == "rect":
            w, h = round(it["w"]), round(it["h"])
            card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            st = it.get("stroke") or {}
            ImageDraw.Draw(card).rounded_rectangle([0, 0, w - 1, h - 1], radius=it.get("radius", 0),
                                                   fill=ctx.c(it["fill"]) + (255,) if it.get("fill") else None,
                                                   outline=ctx.c(st["color"]) if st else None, width=st.get("width", 0))
            y = place_y(it, h, H, ctx)
            paste_with_shadow(canvas, card, it["x"], y, it.get("shadow"))
            box = (it["x"], y, w, h)
            ctx.drawn.append(("rect", box, it, None))
        elif kind == "stars":
            n, filled, sz = it.get("count", 5), it.get("filled", it.get("count", 5)), it["size"]
            y = place_y(it, sz, H, ctx)
            d = ImageDraw.Draw(canvas)
            gap = sz * 0.18
            x0 = (W - (n * sz + (n - 1) * gap)) / 2 if it.get("center") else it["x"]
            for i in range(n):
                cx = x0 + i * (sz + gap) + sz / 2
                d.polygon(star(cx, y + sz / 2, sz / 2), fill=ctx.c(it.get("fill", "#F5B400") if i < filled else it.get("empty", "#D9D9D9")))
            box = (x0, y, n * sz + (n - 1) * gap, sz)
        elif kind == "marks":
            sz, gap, style = it["size"], it.get("gap", it["size"] * 0.7), it.get("style", "Medium")
            x, y0 = it["x"], it["y"]
            y = y0
            d = ImageDraw.Draw(canvas)
            col, ink = ctx.c(it.get("color", "#1FA463")), ctx.c(it.get("ink", "#111111"))
            m = sz * 0.9
            wmax = 0
            mls, mlh = it.get("ls", -1), it.get("lh", 115)
            for text in it["lines"]:
                mf = ctx.f(style, sz)
                masc, mdesc = mf.getmetrics()
                cy = y + (sz * mlh / 100 - (masc + mdesc)) / 2 + masc + mf.getbbox("x", anchor="ls")[1] / 2   # centred on the x-height
                d.ellipse([x, cy - m / 2, x + m, cy + m / 2], fill=col)
                k, lw = m / 10, max(2, round(sz * 0.11))
                if it.get("mark", "check") == "check":
                    d.line([(x + 2.6 * k, cy + 0.1 * k), (x + 4.3 * k, cy + 1.9 * k), (x + 7.5 * k, cy - 2.0 * k)], fill=(255, 255, 255), width=lw, joint="curve")
                else:
                    d.line([(x + 3 * k, cy - 2 * k), (x + 7 * k, cy + 2 * k)], fill=(255, 255, 255), width=lw)
                    d.line([(x + 7 * k, cy - 2 * k), (x + 3 * k, cy + 2 * k)], fill=(255, 255, 255), width=lw)
                lines = wrap(ctx, text, style, sz, mls, it["width"] - m - sz * 0.5) if it.get("width") else [text]
                for j, t in enumerate(lines):
                    lw_ = draw_line(canvas, ctx, x + m + sz * 0.5, y + j * sz * mlh / 100, t, style, sz, lambda _: ink, mls, mlh)[0]
                    wmax = max(wmax, m + sz * 0.5 + lw_)
                y += len(lines) * sz * mlh / 100 + gap
            box = (x, y0, wmax, y - gap - y0)
            ctx.drawn.append(("marks", box, it, None))
        elif kind == "bubble":
            sz, style = it["size"], it.get("style", "Medium")
            pad = sz * 0.7
            lines = wrap(ctx, it["text"], style, sz, -1, it["width"] - 2 * pad)
            fnt = ctx.f(style, sz)
            tw = max(line_width(fnt, t, sz, -1) for t in lines)
            w, h = tw + 2 * pad, len(lines) * sz * 1.25 + 2 * pad * 0.8
            y = place_y(it, h, H, ctx)
            x = it["x"] if it.get("side", "left") == "left" else it["x"] + it["width"] - w
            card = Image.new("RGBA", (round(w), round(h)), (0, 0, 0, 0))
            ImageDraw.Draw(card).rounded_rectangle([0, 0, w - 1, h - 1], radius=min(h / 2, sz * 1.2), fill=ctx.c(it["fill"]) + (255,))
            paste_with_shadow(canvas, card, x, y, None)
            ink = ctx.c(it["ink"])
            for j, t in enumerate(lines):
                draw_line(canvas, ctx, x + pad, y + pad * 0.8 + j * sz * 1.25, t, style, sz, lambda _: ink, -1, 125)
            box = (x, y, w, h)
            ctx.drawn.append(("bubble", box, it, None))
        elif kind == "line":
            d = ImageDraw.Draw(canvas)
            col = ctx.c(it.get("color", "#111111"))
            d.line([(it["x1"], it["y1"]), (it["x2"], it["y2"])], fill=col, width=it.get("width", 3))
            if it.get("dot"):
                r = it["dot"]
                d.ellipse([it["x1"] - r, it["y1"] - r, it["x1"] + r, it["y1"] + r], fill=col)
            box = (min(it["x1"], it["x2"]), min(it["y1"], it["y2"]), abs(it["x2"] - it["x1"]), abs(it["y2"] - it["y1"]))
            ctx.drawn.append(("line", box, it, None))
        else:
            fail(f"unknown item type {kind}")
        if it.get("id") and box:
            ctx.boxes[it["id"]] = box
    if fr.get("grain") and layer != "type":
        from PIL import ImageChops
        k = float(fr["grain"])                            # 0.03 to 0.06: felt, not seen
        n = Image.effect_noise(canvas.size, 40)
        up = n.point(lambda v: round(max(0, v - 128) * k * 4))
        down = n.point(lambda v: round(max(0, 128 - v) * k * 4))
        room = lambda v: round(255 * min(1.0, min(v, 255 - v) / 24))   # less grain near 0 and 255, so clipping can't shift the colour

        def grainy(ch):
            h = ch.point(room)
            return ImageChops.subtract(ImageChops.add(ch, ImageChops.multiply(up, h)), ImageChops.multiply(down, h))
        r, g, b_, a = canvas.split()
        canvas = Image.merge("RGBA", tuple(grainy(ch) for ch in (r, g, b_)) + (a,))
    return canvas if layer == "type" else canvas.convert("RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("layout")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--only", help="render only frames whose name contains this")
    ap.add_argument("--sheet", help="also write a contact sheet of every rendered frame")
    ap.add_argument("--quality", type=int, default=92)
    ap.add_argument("--layers", action="store_true",
                    help="also write <file>_plate.png (no type, to animate) and <file>_type.png (transparent) for scripts/loop.py")
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
        if a.layers:
            render_frame(fr, ctx, "plate").save(out / f"{fr['file']}_plate.png")
            render_frame(fr, ctx, "type").save(out / f"{fr['file']}_type.png")
            print(f"  + {fr['file']}_plate.png, {fr['file']}_type.png")
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
