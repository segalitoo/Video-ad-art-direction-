#!/usr/bin/env python3
"""Place a photo in a frame larger than it, extending its seamless studio wall where the frame reaches past it.

The fill continues each edge's own colour (push-pull), is blurred to read as out-of-focus wall, carries the
photo's own grain, and the photo is feathered into it. `seam_check` measures the wall's luminance across every
extended edge and warns when the photo's rectangle would show as a band (lesson L027). Only for flat seamless
grounds; never extend through a subject (L015). Limit: the fill holds each edge's colour, so a steep light
falloff stops at the edge; seam_check flags that too, and the fix is a different scale or anchor.

    from wall_extend import place
    frame = place(Image.open("plate.png").convert("RGB"), scale, anchor_src, anchor_dst, 1080, 1920)
"""
from PIL import Image, ImageFilter


def _fill(img, known):
    """Push-pull fill: every unknown pixel takes a smooth average of the nearest known pixels, so the extension
    continues each edge's own colour (a wall darker at the top stays darker at the top) instead of one flat tone."""
    import numpy as np
    levels = [(img * known[..., None], known)]
    while min(levels[-1][1].shape) > 2:
        a, m = levels[-1]
        h, w = m.shape[0] // 2 * 2, m.shape[1] // 2 * 2
        a2 = a[:h, :w].reshape(h // 2, 2, w // 2, 2, 3).sum((1, 3))
        m2 = m[:h, :w].reshape(h // 2, 2, w // 2, 2).sum((1, 3))
        col = np.where(m2[..., None] > 0, a2 / np.maximum(m2, 1e-6)[..., None], 0)
        levels.append((col * np.minimum(m2, 1)[..., None], np.minimum(m2, 1)))
    a, m = levels[-1]
    cur = a / np.maximum(m, 1e-6)[..., None]
    for a, m in reversed(levels[:-1]):
        ups = np.stack([np.asarray(Image.fromarray(cur[..., c].astype(np.float32)).resize((m.shape[1], m.shape[0]),
                                                                                           Image.BILINEAR)) for c in range(3)], -1)
        own = a / np.maximum(m, 1e-6)[..., None]
        cur = m[..., None] * own + (1 - m[..., None]) * ups
    return cur


def extend(im, left=0, top=0, right=0, bottom=0, feather=48):
    """Extend a seamless studio wall past the photo. The fill continues each edge's own colour (push-pull), is
    blurred so it reads as out-of-focus wall, gets the photo's own grain, and the photo is feathered into it.
    (Before 2026-10-02 the fill was the border's mean colour: on a wall with a light falloff, the photo's
    rectangle showed as soft bands. L027.)"""
    import numpy as np
    W, H = im.size
    big = np.zeros((H + top + bottom, W + left + right, 3), np.float64)
    known = np.zeros(big.shape[:2])
    big[top:top + H, left:left + W] = np.asarray(im, np.float64)
    known[top:top + H, left:left + W] = 1
    fill = _fill(big, known)
    fimg = Image.fromarray(np.clip(fill, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(18))
    fill = np.asarray(fimg, np.float64)
    # grain: the photo's own noise level, measured on its border strip
    g = np.asarray(im.convert("L"), np.float64)
    hp = g - np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(2)), np.float64)
    edge = np.concatenate([hp[:24].ravel(), hp[-24:].ravel(), hp[:, :24].ravel(), hp[:, -24:].ravel()])
    sd = float(np.clip(edge.std(), 0, 6))
    rng = np.random.default_rng(7)
    n = Image.fromarray(np.clip(128 + rng.normal(0, sd * 1.6, known.shape), 0, 255).astype(np.uint8))
    n = np.asarray(n.filter(ImageFilter.GaussianBlur(0.8)), np.float64) - 128
    fill = fill + n[..., None]
    out = Image.fromarray(np.clip(fill, 0, 255).astype(np.uint8))
    # the photo on top, feathered only on the sides that were extended
    m = np.ones((H, W))
    ys, xs = np.mgrid[0:H, 0:W]
    d = np.full((H, W), float(feather))
    if left:   d = np.minimum(d, xs)
    if top:    d = np.minimum(d, ys)
    if right:  d = np.minimum(d, W - 1 - xs)
    if bottom: d = np.minimum(d, H - 1 - ys)
    t = np.clip(d / feather, 0, 1)
    m = (t * t * (3 - 2 * t) * 255).astype(np.uint8)
    out.paste(im, (left, top), Image.fromarray(m))
    seam_check(out, (left, top, left + W, top + H), (left, top, right, bottom))
    return out


def seam_check(out, box, pads, limit=1.5):
    """L027: the photo's rectangle must not show. Across each extended edge, take the wall's luminance profile
    (blurred, averaged along the edge, from 150 px outside to 200 px inside) and measure its bend over a 60 px span
    near the edge. A natural light falloff bends slowly; a band at the seam is a narrow ridge or trough."""
    import numpy as np
    g = np.asarray(out.convert("L").filter(ImageFilter.GaussianBlur(6)), np.float64)
    x0, y0, x1, y1 = box
    ds = np.arange(-150, 201, 10)
    Hh, Ww = g.shape
    cx = lambda v: min(max(v, 0), Ww - 1)                    # clamp: a narrow pad is sampled up to the frame edge
    cy = lambda v: min(max(v, 0), Hh - 1)
    take = {"left": lambda d: g[y0:y1, cx(x0 + d)], "top": lambda d: g[cy(y0 + d), x0:x1],      # same order as pads
            "right": lambda d: g[y0:y1, cx(x1 - 1 - d)], "bottom": lambda d: g[cy(y1 - 1 - d), x0:x1]}
    bad = []
    for (name, f), pad in zip(take.items(), pads):
        if pad < 40:
            continue
        prof = np.array([f(int(d)).mean() for d in ds])
        # narrow bends only: (p[d-60] + p[d+60]) / 2 - p[d], for d from 60 px outside to 100 px inside
        bend = float(max(abs((prof[i - 6] + prof[i + 6]) / 2 - prof[i]) for i in range(9, 26)))
        if bend > limit:
            bad.append(f"{name} {bend:.1f}")
    if bad:
        print("SEAM: extension edge shows (" + ", ".join(bad) + ")")
    return bad


def place(plate, scale, anchor_src, anchor_dst, W, H):
    """Scale the plate so that anchor_src (plate px) lands on anchor_dst (frame px); extend as needed."""
    ax, ay = anchor_src
    fx, fy = anchor_dst
    x0 = ax - fx / scale; y0 = ay - fy / scale               # frame's top-left in plate px
    x1 = x0 + W / scale; y1 = y0 + H / scale
    pw, ph = plate.size
    pad = [max(0, round(-x0)), max(0, round(-y0)), max(0, round(x1 - pw)), max(0, round(y1 - ph))]
    if any(pad):
        plate = extend(plate, *pad)
        x0 += pad[0]; y0 += pad[1]; x1 += pad[0]; y1 += pad[1]
    crop = plate.crop((round(x0), round(y0), round(x1), round(y1)))
    return crop.resize((W, H), Image.LANCZOS)
