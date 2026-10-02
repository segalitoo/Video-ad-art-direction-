#!/usr/bin/env python3
"""Fifteen static ad formats, filled from the lock and rendered by static_render.py.

    python scripts/static_formats.py --list
    python scripts/static_formats.py examples/fernly/statics/formats.yml -o layout.yml --render out/ --sheet sheet.jpg

A formats file names the lock, the product cut-out and one entry per ad:

    lock: ../fernly.dna.yml
    product: cut/product.png          # transparent PNG, made with scripts/cutout.py
    sizes: ["1080x1350"]              # portrait or square: 1080x1350, 1080x1080, 1080x1920
    fonts: {Bold: ..., Medium: ...}   # optional; Space Grotesk by default
    ads:
      - {id: F1, format: hero-headline, headline: "...", subhead: "...", bg: light}
      - {id: F2, format: stat, stat: 0, bg: accent}

Every colour comes from the lock's palette, the CTA from `verbal.cta`, the case from
`verbal.headline_case`. Proof formats (stat, review, testimonial, rating, price-per-day, badges)
read the lock's `proof` block and refuse to build without it: proof is shown, never invented.
Plate formats (lifestyle, ugc-frame, seasonal) need a `plate:` image made at the image stage.

Before the layout is written, the batch is checked as a set: at least 3 formats, 2 background
treatments, no two headlines starting on the same word, product scale varying by 20% or more,
and every line against the copy rules. The thumbnail test checks each ad at 25% size: the CTA
and headline still big enough to read, and their colours in contrast.
"""

import argparse
from pathlib import Path
import sys

import yaml

from common import ROOT, fail, load_lock, load_yaml
from copy_rules import guardrail_hits, headline_issues, unproven_claims, words
from static_render import Ctx, balance, break_cost, clean_breaks, font, line_width, render_frame

DEFAULT_FONTS = {"Bold": ROOT / "assets/fonts/space-grotesk/SpaceGrotesk-Bold.ttf",
                 "Medium": ROOT / "assets/fonts/space-grotesk/SpaceGrotesk-Medium.ttf"}

FORMATS = {
    # name: (group, what it needs, one line)
    "hero-headline": ("headline", [], "one big headline, product supporting, lots of space"),
    "stat": ("proof", ["proof.stats"], "one number as the focal point, source underneath"),
    "review": ("proof", ["proof.quotes"], "a customer sentence as the headline, stars, name"),
    "testimonial": ("proof", ["proof.quotes"], "a review card: quote, name, stars, product beside it"),
    "rating": ("proof", ["proof.rating", "proof.review_count"], "the star rating as the anchor"),
    "us-vs-them": ("compare", ["them", "cons", "pros"], "two columns: the category's way, crossed; ours, ticked"),
    "ingredients": ("compare", ["callouts"], "product in the middle, 4 to 6 labelled callouts"),
    "benefits": ("compare", ["benefits"], "a ticked list you can scan in two seconds"),
    "price-per-day": ("compare", ["proof.price_per_day"], "the daily price, next to something they already buy"),
    "badges": ("compare", ["proof.badges"], "certifications and claims as badges around the product"),
    "lifestyle": ("native", ["plate"], "the product in a real place, headline on a band"),
    "ugc-frame": ("native", ["plate"], "looks captured, not designed: a story-style caption sticker"),
    "text-thread": ("native", ["messages"], "a chat about the product; the most native format"),
    "premium": ("native", [], "the product alone, most of the frame empty, text-only CTA"),
    "seasonal": ("native", ["plate", "season"], "the product in a moment (season, holiday), tagged"),
}
PROOF_FORMATS = {k for k, v in FORMATS.items() if any(n.startswith("proof.") for n in v[1])}
PRODUCT_SCALE = {"hero-headline": 1.0, "stat": 0.8, "review": 0.7, "testimonial": 0.75, "rating": 0.8,
                 "us-vs-them": 0.55, "ingredients": 1.0, "benefits": 1.0, "price-per-day": 0.8, "badges": 1.0,
                 "text-thread": 0.5, "premium": 1.4}


# ---------- the type system
# Sizes are px on a 1080-wide frame. A role names what a line does; the lock can override any field
# under type.roles, and type.tracking shifts every role for a face that runs loose or tight.

ROLES = {
    "display": {"style": "Display", "steps": [64, 72, 80, 88, 96, 108, 120, 136, 152], "lh": 98},
    "subhead": {"style": "Medium", "size": 44, "lh": 132},
    "body": {"style": "Medium", "size": 40, "lh": 130},
    "label": {"style": "Bold", "size": 40, "lh": 112},
    "caption": {"style": "Medium", "size": 34, "lh": 128},
    "cta": {"style": "Semi", "size": 38, "lh": 100},
}
# Tracking in % of the size: open at small sizes for legibility, tight at display sizes where the
# face's own spacing reads loose. Interpolated on a log scale between these points.
TRACK = [(24, 1.2), (32, 0.6), (40, 0.2), (48, 0.0), (64, -0.5), (88, -0.8), (120, -1.0), (160, -1.4)]
MIN_TEXT = 32          # nothing smaller than this on a 1080 frame: 8 px at the 25% thumbnail
FALLBACK = {"Display": "Bold", "Semi": "Bold", "Regular": "Medium"}


def track_for(px):
    import math
    if px <= TRACK[0][0]:
        return TRACK[0][1]
    for (a, ta), (b, tb) in zip(TRACK, TRACK[1:]):
        if px <= b:
            t = (math.log(px) - math.log(a)) / (math.log(b) - math.log(a))
            return ta + (tb - ta) * t
    return TRACK[-1][1]


def smart(text):
    """Typographer's punctuation: curly quotes and apostrophes, an en dash for a spaced hyphen, an
    ellipsis, and a no-break space after a number so "3 parts" never splits."""
    import re
    if not isinstance(text, str):
        return text
    t = text.replace("...", "\u2026").replace(" - ", " \u2013 ")
    t = re.sub(r'(^|[\s(\[])"', "\\1\u201c", t)
    t = t.replace('"', "\u201d")
    t = re.sub(r"(^|[\s(\[])'", "\\1\u2018", t)
    t = t.replace("'", "\u2019")
    t = re.sub(r"(\d) (?=[A-Za-z])", "\\1\u00a0", t)
    return t


def smart_ad(ad):
    keys = ("headline", "subhead", "them", "us", "compare", "season")
    for k in keys:
        if k in ad:
            ad[k] = smart(ad[k])
    for k in ("cons", "pros", "benefits"):
        if k in ad:
            ad[k] = [smart(x) for x in ad[k]]
    for c in ad.get("callouts") or []:
        for k in ("name", "benefit"):
            if k in c:
                c[k] = smart(c[k])
    for msg in ad.get("messages") or []:
        msg["text"] = smart(msg["text"])
    return ad


# ---------- colour

def lum(hexv):
    r, g, b = (int(hexv.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def palette(lock):
    cols = [c for c in lock.get("palette") or [] if c.get("hex")]
    if len(cols) < 2:
        fail("the lock needs a palette of 2 or more colours")
    by = lambda role: next((c["hex"] for c in cols if c.get("role") == role), None)
    ordered = sorted((c["hex"] for c in cols), key=lum)
    dark, light = ordered[0], ordered[-1]
    if lum(dark) > 0.05:
        dark = "#111111"
    if lum(light) < 0.8:
        light = "#FFFFFF"
    hero = by("hero") or ordered[len(ordered) // 2]
    accent = by("accent") or hero
    on = lambda bg: light if contrast(light, bg) >= contrast(dark, bg) else dark
    return {"dark": dark, "light": light, "hero": hero, "accent": accent, "on": on,
            "muted": "#8A8F98", "soft": "#ECEDEF"}


def treatment(bg, pal):
    """Background name -> (background hex, ink hex)."""
    base = {"light": pal["light"], "dark": pal["dark"], "accent": pal["hero"]}.get(bg or "light", bg)
    if not str(base).startswith("#"):
        fail(f"background '{bg}' is not light, dark, accent or a hex")
    return base, pal["on"](base)


# ---------- helpers

class Build:
    def __init__(self, W, H, fonts, pal, lock, product):
        self.W, self.H, self.u = W, H, W / 1080
        self.fonts, self.pal, self.lock, self.product = fonts, pal, lock, product
        self.items, self.checks = [], []
        ty = lock.get("type") or {}
        self.roles = {k: dict(v, **((ty.get("roles") or {}).get(k) or {})) for k, v in ROLES.items()}
        self.track_shift = float(ty.get("tracking", 0) or 0)

    def st(self, style):
        """A style the fonts block may not have falls back: Display and Semi to Bold, Regular to Medium."""
        return style if style in self.fonts else FALLBACK.get(style, "Bold")

    def role(self, name, size=None):
        """style, size (px on this frame), leading %, tracking % for a role."""
        r = self.roles[name]
        px = size or r.get("size") or r["steps"][-1]
        return {"style": self.st(r["style"]), "size": px * self.u, "lh": r["lh"],
                "ls": round(track_for(px) + self.track_shift + r.get("ls_shift", 0), 2)}

    def set_text(self, text, role, x, y, color, width, bg=None, size=None, center=False, **kw):
        """A block of text in a role, with designed line breaks. Returns its height."""
        r = self.role(role, size)
        ls_ = self.lines(text, r["style"], r["size"], width, r["ls"])
        it = self.text("\n".join(ls_), r["size"], x, y, color, r["style"], width=round(width), ls=r["ls"], lh=r["lh"],
                       optical=True, **kw)
        if center:
            it["center"] = True
        if bg is not None:
            self.checks.append(("text", text, r["size"], color, bg))
        return r["size"] * r["lh"] / 100 * len(ls_)

    def display(self, text, x, y, color, bg, width, max_lines=3, max_h=None, center=False):
        """The headline, sized to a step of the scale: the biggest step with clean line breaks, or a
        step within 15% of it whose every break lands on punctuation."""
        r0 = self.roles["display"]
        found = []
        for px in sorted(r0["steps"], reverse=True):
            r = self.role("display", px)
            ls_ = self.lines(text, r["style"], r["size"], width, r["ls"])
            h = r["size"] * r["lh"] / 100 * len(ls_)
            if len(ls_) <= max_lines and (not max_h or h <= max_h) and clean_breaks(ls_):
                found.append((px, ls_, h))
                if px < found[0][0] * 0.85:
                    break
        if not found:
            px = r0["steps"][0]
            r = self.role("display", px)
            ls_ = self.lines(text, r["style"], r["size"], width, r["ls"])
            found = [(px, ls_, r["size"] * r["lh"] / 100 * len(ls_))]
        punct = [f for f in found if f[0] >= found[0][0] * 0.85 and len(f[1]) > 1
                 and all(t.split(" ")[-1][-1] in ".?!:," for t in f[1][:-1])]
        px, ls_, h = (punct or found)[0]
        r = self.role("display", px)
        it = self.text("\n".join(ls_), r["size"], x, y, color, r["style"], width=round(width), ls=r["ls"], lh=r["lh"],
                       optical=True)
        if center:
            it["center"] = True
        self.checks.append(("headline", text, r["size"], color, bg))
        return h, r["size"]

    def snap(self, y):
        """On the 8 px baseline grid."""
        g = 8 * self.u
        return round(y / g) * g

    def tw(self, text, style, size, ls=-1):
        return line_width(font(self.fonts[style], size), text, size, ls)

    def add(self, **it):
        self.items.append(it)
        return it

    def text(self, text, size, x, y, color, style="Bold", **kw):
        return self.add(type="text", text=text, style=style, size=round(size), x=round(x), y=round(y),
                        color=color, ls=kw.pop("ls", -2), lh=kw.pop("lh", 100), **kw)

    def product_img(self, x, y, w, h, scale=1.0, shadow=True, anchor="floor"):
        if not self.product:
            return
        cx, cy = x + w / 2, (y + h / 2 if anchor == "center" else y + h)
        w, h = w * scale, h * scale
        self.add(type="image", src=str(self.product), fit="contain", anchor=anchor, x=round(cx - w / 2),
                 y=round(cy - (h / 2 if anchor == "center" else h)),
                 w=round(w), h=round(h), **({"shadow": {"y": round(30 * self.u), "blur": round(50 * self.u),
                                                         "opacity": 0.22}} if shadow else {}))

    def product_in(self, x, y, w, h, align="center", valign="bottom", scale=1.0, shadow=True):
        """The product as big as the box allows (times scale), placed by align/valign. Returns the
        box it fills, or None without a product."""
        if not self.product:
            return None
        from PIL import Image
        with Image.open(self.product) as im:
            bb = im.split()[-1].getbbox() if im.mode == "RGBA" else None
            pw, ph = (bb[2] - bb[0], bb[3] - bb[1]) if bb else im.size
        a = pw / ph
        vw = min(w, h * a) * scale
        vh = vw / a
        vx = x + {"left": 0, "center": (w - vw) / 2, "right": w - vw}[align]
        vy = y + {"top": 0, "center": (h - vh) / 2, "bottom": h - vh}[valign]
        self.add(type="image", src=str(self.product), fit="contain", anchor="floor", x=round(vx), y=round(vy),
                 w=round(vw), h=round(vh), **({"shadow": {"y": round(30 * self.u), "blur": round(50 * self.u),
                                                          "opacity": 0.22}} if shadow else {}))
        return vx, vy, vw, vh

    def beside_cta(self, label):
        """Left edge for a product that sits beside a bottom-left CTA without touching it."""
        r = self.role("cta")
        return max(self.W * 0.3, 80 * self.u + self.tw(label, r["style"], r["size"], r["ls"]) + 2.2 * r["size"] + 32 * self.u)

    def feed_product(self, y, label, scale=1.0):
        """Feed frames: the product either beside the CTA (down to its baseline) or above it (full width),
        whichever shows it bigger. A tall pack goes beside, a wide one above."""
        if not self.product:
            return None
        from PIL import Image
        with Image.open(self.product) as im:
            bb = im.split()[-1].getbbox() if im.mode == "RGBA" else None
            pw, ph = (bb[2] - bb[0], bb[3] - bb[1]) if bb else im.size
        u, m = self.u, 80 * self.u
        x = self.beside_cta(label)
        side = (x, y, self.W - m * 0.6 - x, self.H - m - y)
        above = (m, y, self.W - 2 * m, self.H - m - 76 * u - 40 * u - y)
        area = lambda r: min(r[2], r[3] * pw / ph) ** 2
        r = side if area(side) >= area(above) else above
        return self.product_in(*r, "right" if r is side else "center", "center", scale=scale)

    def cta(self, label, fill, ink, bottom=None, x=None, center=False, plain=False, y=None):
        if self.H / self.W >= 1.7:      # Stories and Reels: the platform draws its own CTA button
            return
        r = self.role("cta")
        size = r["size"]
        it = self.add(type="cta", label=label, size=round(size), fill=fill, ink=ink, plain=plain, style=r["style"], ls=r["ls"],
                      **({"y": round(y)} if y is not None else {"bottom": round(bottom if bottom is not None else 80 * self.u)}))
        if center:
            it["center"] = True
        else:
            it["x"] = round(x if x is not None else 80 * self.u)
        self.checks.append(("CTA", label, size, ink, fill if not plain else None))

    # ---- flow layout: measure the type, then give the product the space that is left

    @property
    def tall(self):
        return self.H / self.W >= 1.7

    @property
    def top(self):
        """Where the type starts: 16% down on Stories and Reels (under the profile row), else the margin."""
        return self.H * 0.16 if self.tall else 88 * self.u

    @property
    def floor(self):
        """Where the content ends: above the CTA in the feed; above the reply bar on Stories and Reels."""
        return self.H * 0.82 if self.tall else self.H - 80 * self.u - 76 * self.u - 44 * self.u

    def marks_h(self, items, size, width, style="Medium", ls=-1, lh=115, gap=None):
        """Height of a ticked list as the renderer draws it."""
        m = size * 0.9
        n = [len(self.lines(t, style, size, width - m - size * 0.5, ls)) for t in items]
        return sum(n) * size * lh / 100 + (size * 0.7 if gap is None else gap) * (len(items) - 1)

    def lines(self, text, style, size, width, ls=-2):
        fnt = font(self.fonts[style], size)
        return balance(text, lambda t: line_width(fnt, t, size, ls), width)

    def fit(self, text, style, max_size, width, max_lines=3, max_h=None, lh=95, ls=-2, min_size=None):
        """The biggest size whose balanced line breaks are clean (no orphan, no weak word at a line
        end, no sentence split across a break) and fit max_lines and max_h. When several sizes
        within 15% of that work, the one whose breaks all land on punctuation wins."""
        min_size = min_size or max_size * 0.45
        found, size = [], max_size
        while size >= min_size:
            ls_ = self.lines(text, style, size, width, ls)
            h = size * lh / 100 * len(ls_)
            if len(ls_) <= max_lines and (not max_h or h <= max_h) and clean_breaks(ls_):
                found.append((size, ls_))
                if size < found[0][0] * 0.85:
                    break
            size -= max_size * 0.03
        if not found:
            ls_ = self.lines(text, style, min_size, width, ls)
            return min_size, ls_
        punct = [f for f in found if f[0] >= found[0][0] * 0.85 and len(f[1]) > 1
                 and all(t.split()[-1][-1] in ".?!:," for t in f[1][:-1])]
        return (punct or found)[0]

    def block(self, text, max_size, x, y, color, bg, width, style="Bold", max_lines=3, max_h=None, lh=95,
              ls=-2, center=False, check=True, min_size=None, **kw):
        """A headline or subhead with fitted size and designed line breaks. Returns (height, size)."""
        size, ls_ = self.fit(text, style, max_size, width, max_lines, max_h, lh, ls, min_size)
        it = self.text("\n".join(ls_), size, x, y, color, style, width=round(width), ls=ls, lh=lh, **kw)
        if center:
            it["center"] = True
        if check:
            self.checks.append(("headline", text, size, color, bg))
        return size * lh / 100 * len(ls_), size

    def headline(self, text, size, x, y, color, bg, width=None, **kw):
        it = self.text(text, size, x, y, color, width=round(width) if width else None, lh=kw.pop("lh", 95), **kw)
        if not width:
            it.pop("width")
        self.checks.append(("headline", text, size, color, bg))
        return it


def case(text, lock):
    c = (lock.get("verbal") or {}).get("headline_case", "sentence")
    return text.upper() if c == "upper" else text.lower() if c == "lower" else text.title() if c == "title" else text


def need(ad, lock, fmt):
    miss = []
    for n in FORMATS[fmt][1]:
        if n.startswith("proof."):
            if not (lock.get("proof") or {}).get(n[6:]):
                miss.append(f"lock {n}")
        elif not ad.get(n):
            miss.append(n)
    return miss


# ---------- the formats (portrait and square; positions are shares of the frame)

def build_ad(ad, W, H, fonts, lock, base):
    fmt = ad["format"]
    pal = palette(lock)
    bg, ink = treatment(ad.get("bg"), pal)
    b = Build(W, H, fonts, pal, lock, (base / ad["product"]).resolve() if ad.get("product") else None)
    u, m = b.u, 80 * b.u
    scale = float(ad.get("product_scale", 1.0))
    ctas = (lock.get("verbal") or {}).get("cta") or ["Shop now"]
    cta = ad.get("cta") or ctas[0]
    head = case(ad.get("headline", ""), lock)
    proof = lock.get("proof") or {}
    accent = next((c for t in (4.5, 3) for c in (pal["accent"], pal["hero"]) if contrast(c, bg) >= t), pal["on"](bg))   # text colour
    cta_fill = pal["hero"] if contrast(pal["hero"], bg) >= 1.6 else pal["on"](bg)
    cta_ink = pal["on"](cta_fill)
    frame = {"w": W, "h": H, "bg": bg}

    if fmt == "hero-headline":
        y = b.top
        hh, dsz = b.display(head, m, y, ink, bg, W - 2 * m, max_lines=3, max_h=H * (0.24 if b.tall else 0.30))
        y = b.snap(y + hh + max(32 * u, dsz * 0.32))
        if ad.get("subhead"):
            y = b.snap(y + b.set_text(ad["subhead"], "subhead", m, y, ink, W * 0.66, bg=bg))
        y += 48 * u
        if b.tall:
            b.product_in(m, y, W - 2 * m, b.floor - y, "center", scale=scale)
        else:                                            # beside the CTA, down to its baseline
            b.feed_product(y, cta, scale)
        b.cta(cta, cta_fill, cta_ink)
    elif fmt == "stat":
        st = proof["stats"][int(ad.get("stat", 0))]
        b.headline(f"{st['value']}*", 300 * u, m, 110 * u, accent, bg, ls=-5, lh=90)
        b.text(case(st["claim"], lock), 52 * u, m, 110 * u + 300 * u, ink, "Bold", width=round(W * 0.52), lh=105)
        b.product_img(W * 0.52, H * 0.42, W * 0.42, H * 0.44, scale * PRODUCT_SCALE["stat"])
        b.text(f"*{st.get('source', '')}", MIN_TEXT * u, m, 0, pal["on"](bg), "Medium", bottom=round(170 * u), width=round(W * 0.5), ls=0, lh=125)
        b.cta(cta, cta_fill, cta_ink)
    elif fmt in ("review", "testimonial"):
        q = proof["quotes"][int(ad.get("quote", 0))]
        rating = proof.get("rating")
        qsize = 64 * u
        x_in = m + (60 * u if fmt == "testimonial" else 0)
        qlines = max(1, -(-b.tw(f"“{q['text']}”", "Bold", qsize, -2) // (W - 2 * x_in)))
        body_h = (90 * u if rating else 0) + qlines * qsize * 1.12 + 40 * u + 40 * u
        if fmt == "testimonial":
            frame["bg"] = pal["hero"]
            card_bg = pal["light"]
            ink = pal["on"](card_bg)
            b.add(type="rect", x=round(m), y=round(H * 0.12), w=round(W - 2 * m), h=round(body_h + 120 * u), fill=card_bg,
                  radius=round(36 * u), shadow={"y": round(20 * u), "blur": round(50 * u), "opacity": 0.2})
            top, bgq = H * 0.12 + 60 * u, card_bg
            cta_fill, cta_ink = pal["light"], pal["on"](pal["light"])
            if contrast(cta_fill, frame["bg"]) < 1.6:
                cta_fill, cta_ink = pal["dark"], pal["on"](pal["dark"])
        else:
            top, bgq = H * 0.12, bg
        x0 = m + (60 * u if fmt == "testimonial" else 0)
        if rating:
            b.add(type="stars", x=round(x0), y=round(top), size=round(52 * u), filled=round(float(rating)))
        qy = top + (90 * u if rating else 0)
        b.headline(f"“{q['text']}”", qsize, x0, qy, ink, bgq, width=W - 2 * x0, lh=112, id="quote")
        b.add(type="text", text=f"— {q.get('name', '')}", style="Medium", size=round(34 * u), x=round(x0), below="quote",
              gap=round(30 * u), color=ink, ls=0, lh=100)
        if fmt == "testimonial":
            b.product_img(W * 0.55, H * 0.52, W * 0.4, H * 0.36, scale * PRODUCT_SCALE["testimonial"])
            b.cta(cta, cta_fill, cta_ink)
        else:
            b.product_img(W * 0.3, H * 0.6, W * 0.4, H * 0.26, scale * PRODUCT_SCALE["review"])
            b.cta(cta, cta_fill, cta_ink, center=True)
    elif fmt == "rating":
        if head:
            b.headline(head, 56 * u, m, 120 * u, ink, bg, width=W - 2 * m, center=True)
        b.text(f"{proof['rating']} OUT OF 5", 120 * u, 0, 260 * u, accent, center=True, ls=-3)
        b.add(type="stars", x=0, y=round(420 * u), size=round(80 * u), filled=round(float(proof["rating"])), center=True)
        b.text(f"BASED ON {proof['review_count']} REVIEWS", 34 * u, 0, 530 * u, ink, "Medium", center=True, ls=4)
        b.product_img(W * 0.3, H * 0.47, W * 0.4, H * 0.34, scale * PRODUCT_SCALE["rating"])
        b.cta(cta, cta_fill, cta_ink, center=True)
    elif fmt == "us-vs-them":
        y = b.top
        hh, dsz = b.display(head, m, y, ink, bg, W - 2 * m, max_lines=2, max_h=H * 0.2)
        top = b.snap(y + hh + max(40 * u, dsz * 0.4))
        gut = 24 * u
        colw = (W - 2 * m - gut) / 2
        pad = 36 * u
        lab = b.role("label", 38)
        bod = b.role("body", 36 if not b.tall else 40)
        us = ad.get("us", (lock.get("meta") or {}).get("brand", ""))
        cols = [(ad["them"], ad["cons"][:5]), (us, ad["pros"][:5])]
        inner = colw - 2 * pad
        title_h = max(len(b.lines(t, lab["style"], lab["size"], inner, lab["ls"])) for t, _ in cols) * lab["size"] * lab["lh"] / 100
        lgap = bod["size"] * 0.55
        list_h = max(b.marks_h(ls_, bod["size"], inner, bod["style"], bod["ls"], bod["lh"], lgap) for _, ls_ in cols)
        ch = b.snap(pad + title_h + bod["size"] * 0.7 + list_h + pad)
        on_hero = pal["on"](pal["hero"])
        for i, ((title, ls_), fill, tink, mark, mcol) in enumerate(zip(
                cols, (pal["soft"], pal["hero"]), ("#4A4F57", on_hero), ("cross", "check"), ("#9AA0A8", on_hero))):
            x = m + i * (colw + gut)
            b.add(type="rect", x=round(x), y=round(top), w=round(colw), h=round(ch), fill=fill, radius=round(28 * u))
            b.text(title, lab["size"], x + pad, top + pad, tink, lab["style"], width=round(inner), ls=lab["ls"], lh=lab["lh"])
            b.add(type="marks", x=round(x + pad), y=round(top + pad + title_h + bod["size"] * 0.7), size=round(bod["size"]),
                  mark=mark, color=mcol, ink=tink, width=round(inner), lines=ls_, style=bod["style"], ls=bod["ls"],
                  lh=bod["lh"], gap=round(lgap))
            b.checks.append(("text", title, lab["size"], tink, fill))
        y = top + ch + 48 * u
        if b.tall:
            b.product_in(m, y, W - 2 * m, b.floor - y, "center", scale=scale)
        else:
            b.feed_product(y, cta, scale)
        b.cta(cta, cta_fill, cta_ink)
    elif fmt == "ingredients":
        y = b.top
        hh, dsz = b.display(head, m, y, ink, bg, W - 2 * m, max_lines=2, max_h=H * 0.2)
        y0 = b.snap(y + hh + max(48 * u, dsz * 0.5))
        y1 = b.floor if b.tall else H - 80 * u - 85 * u - 48 * u
        cols = ad["callouts"][:6]
        lab, cap = b.role("label"), b.role("caption")
        def callout(c, tx, ty, w):
            b.text(c["name"], lab["size"], tx, ty, accent, lab["style"], width=round(w), ls=lab["ls"], lh=lab["lh"])
            ny = ty + lab["size"] * lab["lh"] / 100 + 4 * u
            bl = b.lines(c.get("benefit", ""), cap["style"], cap["size"], w, cap["ls"])
            if c.get("benefit"):
                b.text("\n".join(bl), cap["size"], tx, ny, ink, cap["style"], width=round(w), ls=cap["ls"], lh=cap["lh"])
            b.checks.append(("text", c["name"], lab["size"], accent, bg))
            return ny - ty + len(bl) * cap["size"] * cap["lh"] / 100, bl
        if b.tall:                                        # Stories: all type above 60%, so the callouts sit in a grid
            colw = (W - 2 * m - 40 * u) / 2               # under the headline, the product below them
            b.add(type="line", x1=round(m), y1=round(y0 - 28 * u), x2=round(W - m), y2=round(y0 - 28 * u),
                  color=accent, width=max(2, round(3 * u)))         # a rule over the grid: reads as an ingredient panel
            ty = y0
            for r0 in range(0, len(cols), 2):
                rh = max(callout(c, m + jj * (colw + 40 * u), ty, colw)[0] for jj, c in enumerate(cols[r0:r0 + 2]))
                ty = b.snap(ty + rh + 40 * u)
            b.product_in(m, ty + 16 * u, W - 2 * m, y1 - ty - 16 * u, "center", "center", scale)
            cols = []
        colw = W * 0.32                                   # the callouts stack on the left, the product fills the right
        px = m + colw + 32 * u
        if cols:
            vx, vy, vw, vh = b.product_in(px, y0, W - m - px, y1 - y0, "center", "center", scale) or (px, y0, W - m - px, y1 - y0)
            hs = [lab["size"] * lab["lh"] / 100 + 4 * u + len(b.lines(c.get("benefit", ""), cap["style"], cap["size"], colw, cap["ls"])) * cap["size"] * cap["lh"] / 100 for c in cols]
            span = max(vh, sum(hs) + 40 * u * (len(cols) - 1))
            gap = (span - sum(hs)) / max(1, len(cols) - 1)
            ty = vy + (vh - span) / 2
            for i, c in enumerate(cols):
                h_, bl = callout(c, m, ty, colw)
                tw_ = max(b.tw(c["name"], lab["style"], lab["size"], lab["ls"]), *(b.tw(t, cap["style"], cap["size"], cap["ls"]) for t in bl or [""]))
                tx = vx + vw * (0.2 + 0.12 * (i % 2))          # a point on the product
                tyy = vy + vh * (0.25 + 0.55 * i / max(1, len(cols) - 1))
                b.add(type="line", x1=round(tx), y1=round(tyy), x2=round(m + tw_ + 20 * u), y2=round(ty + lab["size"] * 0.55),
                      color=accent, width=max(2, round(3 * u)), dot=round(7 * u))
                ty += h_ + gap
        b.cta(cta, cta_fill, cta_ink, center=True)
    elif fmt == "benefits":
        y = b.top
        hh, _ = b.block(head, (124 if b.tall else 112) * u, m, y, ink, bg, W - 2 * m, max_lines=3, max_h=H * 0.26)
        y0 = y + hh + 60 * u
        items = ad["benefits"][:6]
        fs = (52 if b.tall else 44) * u
        if b.tall or H - 80 * u - y0 > (W - 2 * m) * 0.7:      # a deep frame: list, then the product under it
            lh_ = b.marks_h(items, fs, W - 2 * m)
            b.add(type="marks", x=round(m), y=round(y0), size=round(fs), mark="check", color=accent, ink=ink,
                  width=round(W - 2 * m), lines=items)
            y2 = y0 + lh_ + 64 * u
            if b.tall:
                b.product_in(m, y2, W - 2 * m, b.floor - y2, "center", scale=scale)
            else:
                b.feed_product(y2, cta, scale)
        else:
            colw = W * 0.44
            lh_ = b.marks_h(items, fs, colw)
            b.product_in(m + colw + 24 * u, y0, W - m * 0.6 - (m + colw + 24 * u), H - 80 * u - y0, "right", "top",
                         scale=scale)                       # a wide frame: list and product side by side, from the top
            b.add(type="marks", x=round(m), y=round(y0), size=round(fs), mark="check", color=accent, ink=ink,
                  width=round(colw), lines=items)
        b.cta(cta, cta_fill, cta_ink)
    elif fmt == "price-per-day":
        if head:
            b.headline(head, 56 * u, m, 130 * u, ink, bg, width=W - 2 * m, center=True)
        ps = min(220 * u, 220 * u * (W - 2 * m) / max(1, b.tw(proof["price_per_day"], "Bold", 220 * u, -5)))
        b.text(proof["price_per_day"], ps, 0, 240 * u + (220 * u - ps) / 2, accent, center=True, ls=-5)
        if ad.get("compare"):
            b.text(ad["compare"], 40 * u, 0, 490 * u, ink, "Medium", center=True, ls=-1)
        b.product_img(W * 0.3, H * 0.47, W * 0.4, H * 0.34, scale * PRODUCT_SCALE["price-per-day"])
        b.cta(cta, cta_fill, cta_ink, center=True)
    elif fmt == "badges":
        b.headline(head, 64 * u, m, 110 * u, ink, bg, width=W - 2 * m, center=True)
        b.product_img(W * 0.3, H * 0.24, W * 0.4, H * 0.4, scale)
        chips = proof["badges"][:6]
        size, pad, gap = 32 * u, 26 * u, 18 * u
        rows, row, rw = [], [], 0
        for c in chips:
            w = b.tw(c, "Bold", size) + 2 * pad
            if row and rw + w > W - 2 * m:
                rows.append((row, rw - gap))
                row, rw = [], 0
            row.append((c, w))
            rw += w + gap
        rows.append((row, rw - gap))
        y = H * 0.68
        for row, rw in rows:
            x = (W - rw) / 2
            for c, w in row:
                b.add(type="rect", x=round(x), y=round(y), w=round(w), h=round(size + 2 * pad * 0.7), fill=pal["hero"], radius=round((size + 2 * pad * 0.7) / 2))
                b.text(c, size, x + pad, y + pad * 0.7, pal["on"](pal["hero"]), "Bold", ls=-1)
                x += w + gap
            y += size + 2 * pad * 0.7 + gap
        b.cta(cta, cta_fill, cta_ink, center=True)
    elif fmt in ("lifestyle", "seasonal", "ugc-frame"):
        b.add(type="image", src=str((base / ad["plate"]).resolve()), x=0, y=0, w=W, h=H,
              **{k: ad[k] for k in ("focus", "zoom") if ad.get(k)})
        if fmt == "ugc-frame":
            size, padx, pady = (56 if b.tall else 52) * u, 40 * u, 30 * u
            hl = b.lines(head, "Bold", size, W - 2 * m - 2 * padx)
            lw = max(b.tw(t, "Bold", size, -2) for t in hl)
            bw_, bh_ = lw + 2 * padx, size * 1.2 * len(hl) + 2 * pady
            by = b.top if b.tall else H * 0.12
            b.add(type="rect", x=round((W - bw_) / 2), y=round(by), w=round(bw_), h=round(bh_), fill="#FFFFFF", radius=round(18 * u))
            b.headline("\n".join(hl), size, (W - bw_) / 2 + padx, by + pady, "#111111", "#FFFFFF", width=lw + 4, lh=120)
            b.cta(cta, "#FFFFFF", "#111111", center=True, y=by + bh_ + 20 * u)    # under the sticker, off the face
        else:
            band = pal["dark"]
            at = ad.get("text_at") or ("top" if b.tall else "bottom")
            fade = ad.get("fade", True)
            tink = {"light": pal["light"], "dark": pal["dark"]}.get(ad.get("ink")) or pal["on"](band)
            smax = (124 if b.tall else 108) * u
            hs, hl = b.fit(head, "Bold", smax, W - 2 * m, 3, H * 0.28)
            hh = hs * 0.95 * len(hl)
            top = b.top
            if fmt == "seasonal":
                size, pad = 32 * u, 24 * u
                w = b.tw(ad["season"], "Bold", size) + 2 * pad
                top = max(top, m + size + pad * 1.4 + 32 * u)
            if at == "top":
                hy = top
            else:
                hy = (H * 0.58 if b.tall else H - 80 * u - 76 * u - 44 * u) - hh
            if fade:
                if at == "top":
                    b.add(type="fade", x=0, y=0, w=W, h=round(hy + hh + H * 0.2), color=band, edge="top")
                else:
                    b.add(type="fade", x=0, y=round(hy - H * 0.22), w=W, h=round(H - hy + H * 0.22), color=band, edge="bottom")
            if fmt == "seasonal":
                b.add(type="rect", x=round(m), y=round(m), w=round(w), h=round(size + pad * 1.4), fill=pal["hero"], radius=round((size + pad * 1.4) / 2))
                b.text(ad["season"], size, m + pad, m + pad * 0.7, pal["on"](pal["hero"]), "Bold", ls=0)
            b.headline("\n".join(hl), hs, m, hy, tink, band if fade else None, width=W - 2 * m)
            cf = cta_fill if not fade or contrast(cta_fill, band) >= 1.6 else pal["light"]
            b.cta(cta, cf, pal["on"](cf))
    elif fmt == "text-thread":
        frame["bg"] = pal["light"]
        y = b.top
        fs = ((56 if b.tall else 50) if H / W >= 1.2 else 48) * u
        bw = W - 2 * m
        side = "left"
        for msg in ad["messages"][:6]:
            me = msg.get("from", "them") == "me"
            fill = pal["hero"] if me else "#E6E7EB"
            pad = fs * 0.7
            b.add(type="bubble", x=round(m + (bw * 0.2 if me else 0)), y=round(y), text=msg["text"], size=round(fs),
                  width=round(bw * 0.8), side="right" if me else "left", fill=fill, ink=pal["on"](fill))
            y += len(b.lines(msg["text"], "Medium", fs, bw * 0.8 - 2 * pad, -1)) * fs * 1.25 + 2 * pad * 0.8 + 22 * u
            side = "right" if me else "left"
        b.checks.append(("headline", ad["messages"][0]["text"], fs, "#111111", "#E6E7EB"))
        y += 8 * u
        bottom = b.floor if b.tall else H - 80 * u
        cs = 34 * u
        cw = b.tw(cta, "Bold", cs, -1) + 2.2 * cs
        sq = min(W * (0.72 if b.tall else 0.6), bottom - y, W - 2 * m - (0 if b.tall else cw + 40 * u))   # the product sent as a photo, on the side of the last message
        if sq > 120 * u and b.product:
            cx = m if side == "left" else W - m - sq
            b.add(type="rect", x=round(cx), y=round(y), w=round(sq), h=round(sq), fill="#F1F1F3", radius=round(fs * 0.9))
            b.product_in(cx + sq * 0.1, y + sq * 0.1, sq * 0.8, sq * 0.8, "center", "center", scale, shadow=False)
        b.cta(cta, pal["hero"], pal["on"](pal["hero"]), x=(W - m - cw) if side == "left" else m)
    elif fmt == "premium":
        y = b.top + (0 if b.tall else 24 * u)
        hh, _ = b.block(head, (100 if b.tall else 88) * u, m, y, ink, bg, W - 2 * m, max_lines=2, max_h=H * 0.18,
                        center=True)
        brand = (lock.get("meta") or {}).get("brand", "")
        bsz = 34 * u
        y0 = y + hh + 56 * u
        if b.tall:                                        # Stories: the brand line stays above 60%, under the headline
            b.text(brand, bsz, 0, y + hh + 32 * u, ink, "Bold", center=True, ls=12)
            y0 += bsz + 32 * u
            b.product_in(W * 0.1, y0, W * 0.8, b.floor - y0, "center", scale=min(1.0, scale))
        else:
            bottom = H - 80 * u - 76 * u - 24 * u - bsz - 40 * u
            box = b.product_in(W * 0.1, y0, W * 0.8, bottom - y0, "center", "center", scale=min(1.0, scale))
            b.text(brand, bsz, 0, (box[1] + box[3] if box else bottom) + 40 * u, ink, "Bold", center=True, ls=12)
        b.cta(cta, None, ink, center=True, plain=True)
    else:
        fail(f"unknown format {fmt}")
    if H / W >= 1.7:
        safe_band(b, W, H)
    frame["items"] = b.items
    return frame, b.checks


TEXT_ITEMS = ("text", "stack", "marks", "bubble", "cta", "wordmark", "chip")


def safe_band(b, W, H):
    """Stories and Reels: the platform covers the top 14% and the bottom ~35%. Shift the layout down so
    every type item starts at or below 16% of the height (full-frame plates and fades stay put), then
    flag any type that still starts below 60%."""
    tops = [it["y"] for it in b.items if it.get("type") in TEXT_ITEMS and "y" in it]
    shift = max(0, round(H * 0.16 - min(tops))) if tops else 0
    for it in b.items:
        full = it.get("type") in ("image", "fade") and it.get("w") == W and it.get("x", 0) == 0 and it.get("y", 0) == 0
        if shift and not full:
            for k in ("y", "y1", "y2"):
                if k in it:
                    it[k] = it[k] + shift
    for it in b.items:
        if it.get("type") in TEXT_ITEMS and "y" in it and it["y"] > H * 0.60:
            b.checks.append(("SAFE", it.get("text") or it.get("label") or it.get("type"), 0, None, None))


# ---------- checks

def thumbnail_checks(ad_id, checks):
    """At 25% size: CTA cap height >= 7 px, headline >= 12 px, contrast 4.5 (3 for large text)."""
    out = []
    for kind, text, size, ink, bg in checks:
        if kind == "SAFE":
            out.append(f"{ad_id}: \"{text}\" starts below 60% of the height, under the Stories and Reels UI")
            continue
        px = size * 0.25
        minimum = {"CTA": 7, "text": 8}.get(kind, 12)
        if px < minimum:
            out.append(f"{ad_id}: {kind} is {px:.0f}px at 25% size; it needs {minimum}px to read in the feed")
        if bg:
            c = contrast(ink, bg)
            need_c = 3.0 if size >= 48 else 4.5
            if c < need_c:
                out.append(f"{ad_id}: {kind} contrast {c:.1f}:1 on its background; needs {need_c}:1")
    return out


TYPE_KINDS = {"text", "stack", "marks", "bubble", "cta"}


def layout_checks(name, ctx, W, H):
    """After rendering: type that collides with type or the product, type outside the margins, type
    under the contrast floor on the real pixels behind it, and empty bands on flat frames."""
    out, u, tall = [], W / 1080, H / W >= 1.7
    d = ctx.drawn
    label = lambda it: str(it.get("text") or it.get("label") or (it.get("lines") or [it.get("type")])[0]).replace("\n", " ")[:38]
    hit = lambda a, b, t: (min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]) > t and
                           min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]) > t)
    plate = any(k == "image" and it.get("fit") != "contain" and it.get("w") == W and it.get("h") == H for k, _, it, _ in d)
    types = [(bx, it) for k, bx, it, _ in d if k in TYPE_KINDS]
    prods = [bx for k, bx, it, _ in d if k == "image" and it.get("fit") == "contain"]
    for i, (a, it) in enumerate(types):
        for b2, it2 in types[i + 1:]:
            if hit(a, b2, 4 * u):
                out.append(f'{name}: "{label(it)}" overlaps "{label(it2)}"')
        if any(hit(a, p, 4 * u) for p in prods):
            out.append(f'{name}: "{label(it)}" runs into the product')
        if a[0] < W * 0.04 or a[0] + a[2] > W * 0.96 + 1 or a[1] < 0 or a[1] + a[3] > H:
            out.append(f'{name}: "{label(it)}" is outside the margins')
    for k, bx, it, _ in d:
        if k != "line":
            continue
        for t in range(1, 95):                             # a leader may touch its own label at the end, never cross type
            px = it["x1"] + (it["x2"] - it["x1"]) * t / 100
            py = it["y1"] + (it["y2"] - it["y1"]) * t / 100
            hit_t = next((it2 for a, it2 in types if a[0] + 2 < px < a[0] + a[2] - 2 and a[1] + 2 < py < a[1] + a[3] - 2), None)
            if hit_t is not None:
                out.append(f'{name}: a callout line crosses "{label(hit_t)}"')
                break
    sizes = set()
    for k, bx, it, _ in d:
        if k in ("text", "marks", "bubble", "cta"):
            sizes.add(round(it["size"] / u))
            if it["size"] < MIN_TEXT * u - 0.5:
                out.append(f'{name}: "{label(it)}" is {it["size"] / u:.0f}px; nothing goes under {MIN_TEXT}px on a 1080 frame')
    if len(sizes) > 5:
        out.append(f"{name}: {len(sizes)} type sizes in one ad ({', '.join(str(x) for x in sorted(sizes))}); keep to 5 or fewer")
    for k, bx, it, c in d:
        if k == "text" and c is not None:
            need_c = 3.0 if it["size"] >= 48 * u else 4.5
            if c < need_c:
                out.append(f'{name}: "{label(it)}" is {c:.1f}:1 on the pixels behind it; needs {need_c}:1')
    if not plate:
        spans = sorted((bx[1], bx[1] + bx[3]) for k, bx, it, _ in d
                       if k in TYPE_KINDS or k == "rect"
                       or (k == "image" and (it.get("fit") == "contain" or it.get("w") == W)))   # a cut-out or a photo band
        if spans:
            merged = [list(spans[0])]
            for a0, a1 in spans[1:]:
                if a0 <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], a1)
                else:
                    merged.append([a0, a1])
            for (_, e), (s2, _) in zip(merged, merged[1:]):
                if s2 - e > H * 0.15:
                    out.append(f"{name}: an empty band {100 * (s2 - e) / H:.0f}% of the height deep at {100 * e / H:.0f}%")
            if merged[0][0] > H * (0.22 if tall else 0.14):
                out.append(f"{name}: the top {100 * merged[0][0] / H:.0f}% is empty")
            if merged[-1][1] < H * (0.70 if tall else 0.84):
                out.append(f"{name}: nothing below {100 * merged[-1][1] / H:.0f}% of the height")
    return out


def batch_checks(ads, lock):
    out = []
    fmts = {a["format"] for a in ads}
    if len(ads) >= 3 and len(fmts) < 3:
        out.append(f"{len(ads)} ads use {len(fmts)} format(s); a set needs at least 3 so the ads do not read as one")
    bgs = {str(a.get("bg", "light")) for a in ads if a["format"] not in ("lifestyle", "seasonal", "ugc-frame")}
    if len(ads) >= 3 and len(bgs) < 2:
        out.append("every ad has the same background; use at least 2 treatments (light, dark, accent, a photo)")
    firsts = {}
    for a in ads:
        w = words(a.get("headline", ""))
        if w:
            firsts.setdefault(w[0].lower(), []).append(a["id"])
        for key in ("headline", "subhead", "compare"):
            for bw in guardrail_hits(a.get(key, ""), lock):
                out.append(f'{a["id"]} {key}: "{bw}" is in the lock\'s never_say list')
            for c in unproven_claims(a.get(key, ""), lock):
                out.append(f'{a["id"]} {key}: "{c}" reads as proof but is not in the lock\'s proof block')
        for key in ("pros", "cons", "benefits"):
            for line in a.get(key) or []:
                for c in unproven_claims(line, lock):
                    out.append(f'{a["id"]} {key}: "{c}" reads as proof but is not in the lock\'s proof block')
        if a.get("headline"):
            out += [f"{a['id']} headline: {i}" for i in headline_issues(a["headline"], lock)]
    for first, ids in firsts.items():
        if len(ids) > 1:
            out.append(f'headlines of {", ".join(ids)} all start with "{first}"')
    scales = [float(a.get("product_scale", 1.0)) * PRODUCT_SCALE[a["format"]] for a in ads if a["format"] in PRODUCT_SCALE]
    if len(scales) >= 3 and max(scales) / min(scales) < 1.2:
        out.append("the product is the same size in every ad; vary it by 20% or more (product_scale)")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?")
    ap.add_argument("-o", "--out", help="write the layout file static_render.py renders")
    ap.add_argument("--render", help="also render the frames into this folder")
    ap.add_argument("--sheet", help="with --render: a contact sheet")
    ap.add_argument("--list", action="store_true", help="list the formats and what each needs")
    a = ap.parse_args()
    if a.list or not a.file:
        for name, (group, needs, line) in FORMATS.items():
            print(f"{name:14} {group:9} {line}" + (f"   needs: {', '.join(needs)}" if needs else ""))
        return
    spec_path = Path(a.file)
    spec = load_yaml(spec_path)
    base = spec_path.parent
    lock = load_lock((base / spec["lock"]).resolve())
    if spec.get("type"):                                # a formats file may tune the type for a test
        t = dict(lock.get("type") or {})
        t.update({k: v for k, v in spec["type"].items() if k != "roles"})
        t["roles"] = {**(t.get("roles") or {}), **(spec["type"].get("roles") or {})}
        lock["type"] = t
    fonts = {k: (base / v).resolve() for k, v in (spec.get("fonts") or {}).items()} or DEFAULT_FONTS
    for k in ("Bold", "Medium"):
        if k not in fonts:
            fail(f"fonts needs a {k} style")
    sizes = []
    for s in spec.get("sizes") or ["1080x1350"]:
        W, H = (int(x) for x in str(s).lower().split("x"))
        if H < W:
            fail(f"{s}: the formats are laid out for portrait and square; landscape sizes need their own layout")
        sizes.append((W, H))
    ads = spec.get("ads") or []
    if not ads:
        fail("no ads in the formats file")
    errors = []
    for ad in ads:
        smart_ad(ad)
        ad.setdefault("product", spec.get("product"))
        if spec.get("cta"):
            ad.setdefault("cta", spec["cta"])
        if ad.get("format") not in FORMATS:
            errors.append(f"{ad.get('id')}: unknown format '{ad.get('format')}'. Run --list")
            continue
        miss = need(ad, lock, ad["format"])
        if miss:
            why = " (proof is shown, never invented)" if ad["format"] in PROOF_FORMATS else ""
            errors.append(f"{ad['id']} {ad['format']}: missing {', '.join(miss)}{why}")
    if errors:
        for e in errors:
            print(f"ERROR {e}")
        sys.exit(2)
    frames, flags = [], batch_checks(ads, lock)
    for ad in ads:
        for W, H in sizes:
            fr, checks = build_ad(ad, W, H, {k: str(v) for k, v in fonts.items()}, lock, base)
            fr.update(name=f"{ad['id']} {ad['format']} {W}x{H}", file=f"{ad['id']}_{ad['format']}_{W}x{H}")
            frames.append(fr)
            flags += thumbnail_checks(f"{ad['id']} {W}x{H}", checks)
    layout = {"fonts": {k: str(v) for k, v in fonts.items()}, "colors": {}, "frames": frames}
    ctx = Ctx(layout, base)
    rendered = []
    for fr in frames:                                   # render once to check what is really on the frame
        rendered.append(render_frame(fr, ctx))
        flags += layout_checks(fr["name"].replace(f" {fr['w']}x", f" {fr['w']}x").split(" ")[0] + f" {fr['w']}x{fr['h']}", ctx, fr["w"], fr["h"])
    for f in flags:
        print(f"FLAG  {f}")
    print(f"{'PASS' if not flags else 'CHECK'}  {len(ads)} ads, {len({x['format'] for x in ads})} formats, "
          f"{len(frames)} frames, {len(flags)} flag(s)")
    if a.out:
        import copy
        import os
        rel = copy.deepcopy(layout)                     # paths relative to the layout file, so it can be committed
        here = Path(a.out).resolve().parent
        rel["fonts"] = {k: os.path.relpath(v, here) for k, v in rel["fonts"].items()}
        for fr in rel["frames"]:
            for it in fr["items"]:
                if it.get("type") == "image":
                    it["src"] = os.path.relpath(it["src"], here)
        Path(a.out).write_text(yaml.safe_dump(rel, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
        print(f"wrote {a.out}")
    if a.render:
        out = Path(a.render)
        out.mkdir(parents=True, exist_ok=True)
        done = []
        for fr, img in zip(frames, rendered):
            path = out / f"{fr['file']}.jpg"
            img.save(path, quality=92, subsampling=0)
            done.append(img)
            print(path)
        if a.sheet and done:
            h = 520
            thumbs = [im.resize((round(im.width * h / im.height), h)) for im in done]
            from PIL import Image
            per = 5
            rows = [thumbs[i:i + per] for i in range(0, len(thumbs), per)]
            Wd = max(sum(t.width + 16 for t in r) for r in rows) + 16
            sheet = Image.new("RGB", (Wd, len(rows) * (h + 16) + 16), (226, 226, 222))
            for ri, r in enumerate(rows):
                x = 16
                for t in r:
                    sheet.paste(t, (x, 16 + ri * (h + 16)))
                    x += t.width + 16
            sheet.save(a.sheet, quality=90)
            print(f"wrote {a.sheet}")


if __name__ == "__main__":
    main()
