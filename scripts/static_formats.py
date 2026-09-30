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
from static_render import Ctx, font, line_width, render_frame

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

    def cta(self, label, fill, ink, bottom=None, x=None, center=False, plain=False):
        size = 32 * self.u
        it = self.add(type="cta", label=label, size=round(size), fill=fill, ink=ink, plain=plain,
                      bottom=round(bottom if bottom is not None else 80 * self.u))
        if center:
            it["center"] = True
        else:
            it["x"] = round(x if x is not None else 80 * self.u)
        self.checks.append(("CTA", label, size, ink, fill if not plain else None))

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
    accent = next((c for c in (pal["accent"], pal["hero"]) if contrast(c, bg) >= 3), pal["on"](bg))   # text colour
    cta_fill = pal["hero"] if contrast(pal["hero"], bg) >= 1.6 else pal["on"](bg)
    cta_ink = pal["on"](cta_fill)
    frame = {"w": W, "h": H, "bg": bg}

    if fmt == "hero-headline":
        b.headline(head, 128 * u, m, 150 * u, ink, bg, width=W - 2 * m)
        if ad.get("subhead"):
            b.text(ad["subhead"], 40 * u, m, H * 0.40, ink, "Medium", width=round(W * 0.5), ls=-1, lh=125)
        b.product_img(W * 0.45, H * 0.40, W * 0.5, H * 0.48, scale)
        b.cta(cta, cta_fill, cta_ink)
    elif fmt == "stat":
        st = proof["stats"][int(ad.get("stat", 0))]
        b.headline(f"{st['value']}*", 300 * u, m, 110 * u, accent, bg, ls=-5, lh=90)
        b.text(case(st["claim"], lock), 52 * u, m, 110 * u + 300 * u, ink, "Bold", width=round(W * 0.52), lh=105)
        b.product_img(W * 0.52, H * 0.42, W * 0.42, H * 0.44, scale * PRODUCT_SCALE["stat"])
        b.text(f"*{st.get('source', '')}", 22 * u, m, 0, pal["on"](bg), "Medium", bottom=round(170 * u), width=round(W * 0.5), ls=0, lh=125)
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
        b.text(f"BASED ON {proof['review_count']} REVIEWS", 30 * u, 0, 530 * u, ink, "Medium", center=True, ls=4)
        b.product_img(W * 0.3, H * 0.47, W * 0.4, H * 0.34, scale * PRODUCT_SCALE["rating"])
        b.cta(cta, cta_fill, cta_ink, center=True)
    elif fmt == "us-vs-them":
        b.headline(head, 72 * u, m, 90 * u, ink, bg, width=W - 2 * m)
        colw, top = (W - 3 * m) / 2, H * 0.25
        n = max(len(ad["cons"][:5]), len(ad["pros"][:5]))
        ch = 120 * u + n * 34 * u * 2.4 + 40 * u
        b.add(type="rect", x=round(m), y=round(top), w=round(colw), h=round(ch), fill=pal["soft"], radius=round(28 * u))
        b.add(type="rect", x=round(2 * m + colw), y=round(top), w=round(colw), h=round(ch), fill=pal["hero"], radius=round(28 * u))
        on_hero = pal["on"](pal["hero"])
        b.text(ad["them"], 36 * u, m + 36 * u, top + 36 * u, "#555A63", "Bold", width=round(colw - 72 * u), ls=-1)
        b.text(ad.get("us", (lock.get("meta") or {}).get("brand", "")), 36 * u, 2 * m + colw + 36 * u, top + 36 * u, on_hero, "Bold", ls=-1)
        b.add(type="marks", x=round(m + 36 * u), y=round(top + 120 * u), size=round(34 * u), mark="cross", color="#9AA0A8",
              ink="#555A63", width=round(colw - 72 * u), lines=ad["cons"][:5])
        b.add(type="marks", x=round(2 * m + colw + 36 * u), y=round(top + 120 * u), size=round(34 * u), mark="check",
              color=pal["on"](pal["hero"]), ink=on_hero, width=round(colw - 72 * u), lines=ad["pros"][:5])
        b.product_img(W * 0.5, top + ch + 20 * u, W * 0.45, H * 0.85 - top - ch - 20 * u, scale * PRODUCT_SCALE["us-vs-them"] / 0.55)
        b.cta(cta, cta_fill, cta_ink)
    elif fmt == "ingredients":
        b.headline(head, 64 * u, m, 90 * u, ink, bg, width=W - 2 * m, center=True)
        px, py, pw, ph = W * 0.3, H * 0.28, W * 0.4, H * 0.46
        b.product_img(px, py, pw, ph, scale, anchor="center")
        cols = ad["callouts"][:6]
        for i, c in enumerate(cols):
            left = i % 2 == 0
            row = i // 2
            cy = H * 0.3 + row * H * 0.15
            tx = m if left else W * 0.72
            b.text(c["name"], 36 * u, tx, cy, accent, "Bold", width=round(W * 0.24), ls=-1)
            b.text(c.get("benefit", ""), 27 * u, tx, cy + 46 * u, ink, "Medium", width=round(W * 0.24), ls=0, lh=125)
            ex = tx + W * 0.24 + 16 * u if left else tx - 16 * u          # past the text column, never through it
            b.add(type="line", x1=round(W * 0.42 if left else W * 0.58), y1=round(py + ph * (0.38 + 0.12 * row)),
                  x2=round(ex), y2=round(cy + 20 * u), color=accent, width=max(2, round(3 * u)), dot=round(7 * u))
        b.cta(cta, cta_fill, cta_ink, center=True)
    elif fmt == "benefits":
        b.headline(head, 80 * u, m, 110 * u, ink, bg, width=W * 0.8)
        b.add(type="marks", x=round(m), y=round(H * 0.36), size=round(38 * u), mark="check", color=accent,
              ink=ink, width=round(W * 0.5), lines=ad["benefits"][:6])
        b.product_img(W * 0.55, H * 0.38, W * 0.4, H * 0.46, scale)
        b.cta(cta, cta_fill, cta_ink)
    elif fmt == "price-per-day":
        if head:
            b.headline(head, 56 * u, m, 130 * u, ink, bg, width=W - 2 * m, center=True)
        b.text(proof["price_per_day"], 220 * u, 0, 240 * u, accent, center=True, ls=-5)
        if ad.get("compare"):
            b.text(ad["compare"], 40 * u, 0, 490 * u, ink, "Medium", center=True, ls=-1)
        b.product_img(W * 0.3, H * 0.47, W * 0.4, H * 0.34, scale * PRODUCT_SCALE["price-per-day"])
        b.cta(cta, cta_fill, cta_ink, center=True)
    elif fmt == "badges":
        b.headline(head, 64 * u, m, 110 * u, ink, bg, width=W - 2 * m, center=True)
        b.product_img(W * 0.3, H * 0.24, W * 0.4, H * 0.4, scale)
        chips = proof["badges"][:6]
        size, pad, gap = 28 * u, 26 * u, 18 * u
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
        b.add(type="image", src=str((base / ad["plate"]).resolve()), x=0, y=0, w=W, h=H)
        if fmt == "ugc-frame":
            size = 50 * u
            lines_w = min(W - 2 * m, b.tw(head, "Bold", size) + 80 * u)
            b.add(type="rect", x=round((W - lines_w) / 2), y=round(H * 0.18), w=round(lines_w),
                  h=round(size * 1.2 * max(1, round(b.tw(head, "Bold", size) / (lines_w - 80 * u) + 0.49)) + 60 * u),
                  fill="#FFFFFF", radius=round(18 * u))
            b.headline(head, size, (W - lines_w) / 2 + 40 * u, H * 0.18 + 30 * u, "#111111", "#FFFFFF", width=lines_w - 80 * u, lh=120)
            b.cta(cta, "#FFFFFF", "#111111", center=True)
        else:
            band = pal["dark"]
            b.add(type="fade", x=0, y=round(H * 0.45), w=W, h=round(H * 0.55), color=band, edge="bottom")
            if fmt == "seasonal":
                size, pad = 32 * u, 24 * u
                w = b.tw(ad["season"], "Bold", size) + 2 * pad
                b.add(type="rect", x=round(m), y=round(m), w=round(w), h=round(size + pad * 1.4), fill=pal["hero"], radius=round((size + pad * 1.4) / 2))
                b.text(ad["season"], size, m + pad, m + pad * 0.7, pal["on"](pal["hero"]), "Bold", ls=0)
            b.headline(head, 84 * u, m, 0, pal["on"](band), band, width=W - 2 * m, bottom=round(200 * u))
            b.cta(cta, cta_fill if contrast(cta_fill, band) >= 1.6 else pal["light"], pal["on"](cta_fill if contrast(cta_fill, band) >= 1.6 else pal["light"]))
    elif fmt == "text-thread":
        frame["bg"] = pal["light"]
        y = H * 0.1
        bw = W - 2 * m
        for msg in ad["messages"][:6]:
            me = msg.get("from", "them") == "me"
            fill = pal["hero"] if me else "#E6E7EB"
            it = b.add(type="bubble", x=round(m), y=round(y), text=msg["text"], size=round(48 * u), width=round(bw * 0.8),
                       side="right" if me else "left", fill=fill, ink=pal["on"](fill))
            if not me:
                it["x"] = round(m)
            else:
                it["x"] = round(m + bw * 0.2)
            lines = max(1, -(-b.tw(msg["text"], "Medium", 48 * u) // (bw * 0.8 - 68 * u)))
            y += lines * 48 * u * 1.25 + 68 * u + 24 * u
        b.checks.append(("headline", ad["messages"][0]["text"], 48 * u, "#111111", "#E6E7EB"))
        b.product_img(W * 0.55, y, W * 0.35, min(H * 0.28, H - y - 200 * u), scale * PRODUCT_SCALE["text-thread"], shadow=False)
        b.cta(cta, pal["hero"], pal["on"](pal["hero"]), center=True)
    elif fmt == "premium":
        if head:
            b.headline(head, 72 * u, 0, 140 * u, ink, bg, center=True, ls=-2)
        b.product_img(W * 0.2, H * 0.2, W * 0.6, H * 0.55, min(1.0, scale))
        brand = (lock.get("meta") or {}).get("brand", "")
        b.text(brand, 28 * u, 0, H - 250 * u, ink, "Bold", center=True, ls=12)
        b.cta(cta, None, ink, center=True, plain=True)
    else:
        fail(f"unknown format {fmt}")
    frame["items"] = b.items
    return frame, b.checks


# ---------- checks

def thumbnail_checks(ad_id, checks):
    """At 25% size: CTA cap height >= 7 px, headline >= 12 px, contrast 4.5 (3 for large text)."""
    out = []
    for kind, text, size, ink, bg in checks:
        px = size * 0.25
        minimum = 7 if kind == "CTA" else 12
        if px < minimum:
            out.append(f"{ad_id}: {kind} is {px:.0f}px at 25% size; it needs {minimum}px to read in the feed")
        if bg:
            c = contrast(ink, bg)
            need_c = 3.0 if size >= 48 else 4.5
            if c < need_c:
                out.append(f"{ad_id}: {kind} contrast {c:.1f}:1 on its background; needs {need_c}:1")
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
        ctx = Ctx(layout, base)
        done = []
        for fr in frames:
            img = render_frame(fr, ctx)
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
