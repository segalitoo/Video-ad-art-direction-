#!/usr/bin/env python3
"""The judge pass: score generated images and clips, and find the set that matches best.

It runs after every generation round (keyframes, clips, static plates) and before the
human gate. It recommends; the art director still picks.

    python scripts/judge.py new round.yml --lock ../fernly.dna.yml \\
        D="out/plant-droopy.*" L="out/plant-lush.*" P="out/S01-pour.*" \\
        --pair D:L:first_last --pair D:P:same_set
    python scripts/judge.py measure round.yml      # machine pass, and review strips for clips
    #   Claude looks at every file and fills `scores` (and `pair_scores` for the shortlist)
    python scripts/judge.py rank round.yml -o report.md --sheet sheet.html

Two passes, because pixels and eyes see different things:
- The machine pass measures what pixels can tell: sharpness, whether the bands kept free
  for captions and platform UI are calm, how close the colours sit to the lock palette,
  and how alike two frames are. Clips get a 5-frame review strip and a steadiness score.
- The visual pass is Claude looking at every file and scoring the rubric below from 1 to 5,
  each with a reason. A hard fail (text in the image, people in a people-free lock, a
  melted hero) takes the file out, whatever its other scores.

The overall score per file is 85% visual, 15% machine. A set (one file per group) scores
the mean of its files times how well they match: identical framing for a first/last frame
pair, the same pot, props and light for two shots in one room. The round score is the best
set's score: 80+ go to the gate, 65-79 usable with the listed fixes, below 65 regenerate.
"""

import argparse
import colorsys
from glob import glob
import itertools
import html
import math
import os
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageFilter, ImageStat
import yaml

from common import fail, load_lock, load_yaml

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
CLIP_EXT = {".mp4", ".mov", ".webm"}

# Criterion: (weight, what Claude judges). Scores are 1-5.
RUBRIC = {
    "image": {
        "lock": (20, "Reads as the lock: style, light, grade and palette"),
        "hero": (20, "Hero on model (shape, pot, colour); in other shots the subject reads right"),
        "craft": (20, "No AI tells: warped or melted objects, extra parts, fake textures, garbled detail"),
        "composition": (15, "Subject placement, clean space for captions and platform UI"),
        "story": (15, "Does its beat and reads in a second with the sound off"),
        "animatable": (10, "Will move cleanly: a clear subject, nothing tangled that will morph"),
    },
    "clip": {
        "on_model": (20, "The hero and set stay the same from first frame to last"),
        "morph": (20, "No morphing, melting, popping or objects appearing from nowhere"),
        "physics": (15, "Weight, speed and contact feel real"),
        "motion": (20, "Does the one movement the prompt asked for, nothing else"),
        "continuity": (15, "Cuts cleanly with the shots around it"),
        "craft": (10, "Sharp, stable, no flicker or compression mush"),
    },
}
PAIR_RULES = {
    "first_last": "Same framing, pot, props and light; only the subject's state changes",
    "same_set": "Same room: pot, surface, props, window and light match",
}
VISUAL_SHARE = 0.85
BANDS = [(80, "go to the gate"), (65, "usable, fix the listed issues"), (0, "regenerate")]
CALM_TOP, CALM_BOTTOM = 0.15, 1 / 3   # bands assemble.py's FRAME line asks to keep open


# ---------- pixels ----------

def srgb_to_lab(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(float(c)) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def sharpness(gray):
    """Spread of a Laplacian: higher is crisper. Compared inside a round, never absolutely."""
    lap = gray.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], 1, 128))
    return ImageStat.Stat(lap).stddev[0]


def band_calm(gray):
    """How quiet the caption bands are against the whole frame (100 = calm, 0 = busy)."""
    edges = gray.filter(ImageFilter.FIND_EDGES)
    w, h = edges.size
    whole = ImageStat.Stat(edges).mean[0] or 1
    top = ImageStat.Stat(edges.crop((0, 0, w, int(h * CALM_TOP)))).mean[0]
    bottom = ImageStat.Stat(edges.crop((0, int(h * (1 - CALM_BOTTOM)), w, h))).mean[0]
    ratio = max(top, bottom) / whole
    return max(0.0, min(100.0, (1.4 - ratio) / 0.8 * 100))


def palette_pull(img, palette):
    """Share-weighted closeness of the 8 dominant colours to the nearest lock colour."""
    if not palette:
        return None
    labs = [srgb_to_lab(hex_rgb(c)) for c in palette]
    small = img.convert("RGB").resize((96, 96)).quantize(8)
    pal = small.getpalette()
    total = 96 * 96
    score = 0.0
    for count, idx in small.getcolors():
        lab = srgb_to_lab(pal[idx * 3: idx * 3 + 3])
        de = min(math.dist(lab, p) for p in labs)
        score += count / total * max(0.0, 1 - de / 50)
    return score * 100


def pixels(img):
    return list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())


def thumb_gray(img):
    return pixels(img.convert("L").resize((48, 85)))


def region_labs(img, cols=9, rows=16):
    """Mean colour of each cell in a 9 x 16 grid, so a changed pot or mug shows up locally."""
    small = img.convert("RGB").resize((cols, rows), Image.BOX)
    return [srgb_to_lab(px) for px in pixels(small)]


def hue_hist(img):
    """Hue x saturation x value histogram, 12 x 3 x 3 bins, normalised."""
    bins = [0.0] * 108
    px = pixels(img.convert("RGB").resize((64, 114)))
    for r, g, b in px:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        bins[min(int(h * 12), 11) * 9 + min(int(s * 3), 2) * 3 + min(int(v * 3), 2)] += 1
    return [b / len(px) for b in bins]


def structure_match(a, b):
    """Pearson correlation of two small grayscale thumbnails, 0-100."""
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = math.sqrt(sum((x - ma) ** 2 for x in a)) or 1
    vb = math.sqrt(sum((y - mb) ** 2 for y in b)) or 1
    return max(0.0, cov / (va * vb)) * 100


def colour_match(fa, fb):
    """Half overall colour mix, half the share of grid cells whose colour stayed put (dE < 12)."""
    hist = sum(min(x, y) for x, y in zip(fa["_hist"], fb["_hist"]))
    kept = sum(1 for a, b in zip(fa["_cells"], fb["_cells"]) if math.dist(a, b) < 12)
    return (0.5 * hist + 0.5 * kept / len(fa["_cells"])) * 100


def pair_machine(fa, fb, relation):
    s, c = structure_match(fa["_gray"], fb["_gray"]), colour_match(fa, fb)
    weight = 0.6 if relation == "first_last" else 0.2
    return round(weight * s + (1 - weight) * c, 1)


# ---------- clips ----------

def clip_frames(path, out_dir, n=5):
    """n evenly spaced frames as PIL images, and a strip PNG of them for the visual pass."""
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip() or 0)
    frames = []
    for i in range(n):
        t = min(dur * i / (n - 1), max(dur - 0.05, 0))
        tmp = out_dir / f".{path.stem}_{i}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path),
                        "-frames:v", "1", str(tmp)], check=True)
        frames.append(Image.open(tmp).convert("RGB"))
        tmp.unlink()
    w, h = frames[0].size
    tw = 270
    th = round(h * tw / w)
    strip = Image.new("RGB", (tw * n + 8 * (n - 1), th), "white")
    for i, fr in enumerate(frames):
        strip.paste(fr.resize((tw, th)), (i * (tw + 8), 0))
    strip_path = out_dir / f"{path.stem}.strip.png"
    strip.save(strip_path)
    return frames, strip_path


def flicker(path):
    """Spread of frame-to-frame brightness jumps over the clip; lower is steadier. 0-100 score."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf",
         "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-f", "null", "-"],
        capture_output=True, text=True).stdout
    ys = [float(v) for v in re.findall(r"YAVG=([0-9.]+)", out)]
    if len(ys) < 3:
        return None
    jumps = [abs(b - a) for a, b in zip(ys, ys[1:])]
    mean = sum(jumps) / len(jumps)
    spread = math.sqrt(sum((j - mean) ** 2 for j in jumps) / len(jumps))
    return round(max(0.0, 100 - spread * 25), 1)


# ---------- round file ----------

def kind_of(path):
    ext = Path(path).suffix.lower()
    return "clip" if ext in CLIP_EXT else "image" if ext in IMAGE_EXT else None


def model_of(path):
    """hf_api downloads are named <subject>.<model>[_n].<ext>."""
    stem = Path(path).stem
    parts = stem.split(".")
    return re.sub(r"_\d+$", "", parts[1]) if len(parts) > 1 else ""


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Judge round. Claude fills `scores` and `pair_scores`; run `judge.py rank` after.\n")
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, width=110)


def cmd_new(args):
    out = Path(args.round)
    base = out.parent
    groups, items = {}, {}
    for spec in args.groups:
        if "=" not in spec:
            fail(f"group '{spec}' should look like D=\"out/plant-droopy.*\"")
        gid, pattern = spec.split("=", 1)
        files = sorted(glob(str(base / pattern)) if not Path(pattern).is_absolute() else glob(pattern))
        files = [f for f in files if kind_of(f) and ".strip." not in f]
        if not files:
            fail(f"group {gid}: no images or clips match {pattern} (relative to {base})")
        groups[gid] = {"label": dict(l.split("=", 1) for l in args.label or []).get(gid, gid), "files": len(files)}
        for n, f in enumerate(files, 1):
            items[f"{gid}-{n}" if gid[-1].isdigit() else f"{gid}{n}"] = {"file": str(Path(f).resolve().relative_to(base.resolve()))
                                  if Path(f).resolve().is_relative_to(base.resolve()) else f,
                                  "group": gid, "kind": kind_of(f), "model": model_of(f)}
    pairs = []
    for p in args.pair or []:
        a, b, rel = (p.split(":") + ["same_set"])[:3]
        if a not in groups or b not in groups or rel not in PAIR_RULES:
            fail(f"--pair {p}: use GROUP:GROUP:{'|'.join(PAIR_RULES)} with groups from this round")
        pairs.append({"a": a, "b": b, "relation": rel})
    data = {"round": args.name or out.stem, "lock": args.lock, "groups": groups, "pairs": pairs,
            "items": items, "scores": {}, "pair_scores": {}, "fixes": []}
    save(out, data)
    print(f"wrote {out}: {len(items)} files in {len(groups)} groups, {len(pairs)} pair rules")


def load_round(path):
    data = load_yaml(path)
    base = Path(path).parent
    for iid, it in data["items"].items():
        it["_path"] = base / it["file"]
        if not it["_path"].exists():
            fail(f"{iid}: file not found: {it['_path']}")
    lock = load_lock(base / data["lock"]) if data.get("lock") else None
    return data, base, lock


def scene_hexes(lock):
    if not lock:
        return []
    return [c["hex"] for c in lock.get("palette") or [] if not str(c.get("role", "")).startswith("type")]


def features(data, lock):
    palette = scene_hexes(lock)
    for iid, it in data["items"].items():
        if it["kind"] == "clip":
            frames, strip = clip_frames(it["_path"], it["_path"].parent)
            it["_strip"] = strip
            img = frames[len(frames) // 2]
        else:
            img = Image.open(it["_path"]).convert("RGB")
        gray = img.convert("L")
        gray = gray.resize((540, round(540 * gray.height / gray.width)))
        it["_gray"], it["_hist"], it["_cells"] = thumb_gray(img), hue_hist(img), region_labs(img)
        it["_sharp"] = sharpness(gray)
        it["_calm"] = band_calm(gray)
        it["_palette"] = palette_pull(img, palette)
        it["_size"] = img.size
    top = max(it["_sharp"] for it in data["items"].values()) or 1
    for it in data["items"].values():
        it["_sharp_score"] = it["_sharp"] / top * 100


def cmd_measure(args):
    data, base, lock = load_round(args.round)
    features(data, lock)
    machine = {}
    for iid, it in data["items"].items():
        m = {"size": f"{it['_size'][0]}x{it['_size'][1]}", "sharp": round(it["_sharp_score"], 1),
             "calm_bands": round(it["_calm"], 1)}
        if it["_palette"] is not None:
            m["palette"] = round(it["_palette"], 1)
        if it["kind"] == "clip":
            m["steady"] = flicker(it["_path"])
            m["strip"] = os.path.relpath(it["_strip"], base)
        machine[iid] = m
    pm = {}
    for rule in data.get("pairs") or []:
        a_ids = [i for i, it in data["items"].items() if it["group"] == rule["a"]]
        b_ids = [i for i, it in data["items"].items() if it["group"] == rule["b"]]
        for a, b in itertools.product(a_ids, b_ids):
            pm[f"{a}+{b}"] = pair_machine(data["items"][a], data["items"][b], rule["relation"])
    data["machine"], data["pair_machine"] = machine, pm
    for it in data["items"].values():
        for k in [k for k in it if k.startswith("_")]:
            del it[k]
    save(args.round, data)

    kinds = {it["kind"] for it in data["items"].values()}
    print(f"measured {len(machine)} files, {len(pm)} pairs → {args.round}")
    print("\nNext: look at every file and fill `scores` with 1-5 per criterion and a note:")
    for k in sorted(kinds):
        for c, (w, text) in RUBRIC[k].items():
            print(f"  {k:5} {c:12} ×{w:<3} {text}")
    print("  add fail: \"reason\" for a hard fail (text in image, people when the lock says none, a broken hero)")
    short = shortlist(data, n=args.pairs)
    if short:
        print(f"\nThen score these {len(short)} pairs in `pair_scores` (match: 1-5, note), the machine's top candidates:")
        for key, rel in short:
            print(f"  {key:10} {rel:11} machine {pm[key]:5.1f}  {PAIR_RULES[rel]}")


def shortlist(data, n):
    """The machine's top pairs per rule; Claude's eyes go there, not to all of them."""
    out = []
    for rule in data.get("pairs") or []:
        keys = [k for k in data.get("pair_machine", {})
                if data["items"][k.split("+")[0]]["group"] == rule["a"]
                and data["items"][k.split("+")[1]]["group"] == rule["b"]]
        keys.sort(key=lambda k: -data["pair_machine"][k])
        out += [(k, rule["relation"]) for k in keys[:n]]
    return out


# ---------- rank ----------

def visual_score(scores, kind):
    rubric = RUBRIC[kind]
    missing = [c for c in rubric if not isinstance(scores.get(c), (int, float))]
    if missing:
        return None, missing
    total = sum(w for w, _ in rubric.values())
    return sum(w * (min(max(scores[c], 1), 5) - 1) / 4 for c, (w, _) in rubric.items()) / total * 100, []


def machine_score(m):
    vals = [m[k] for k in ("sharp", "calm_bands", "palette", "steady") if m.get(k) is not None]
    return sum(vals) / len(vals) if vals else 0.0


def band(score):
    return next(text for floor, text in BANDS if score >= floor)


def compute(data):
    if "machine" not in data:
        fail("run `judge.py measure` first")
    rows, problems = {}, []
    for iid, it in data["items"].items():
        s = (data.get("scores") or {}).get(iid) or {}
        vis, missing = visual_score(s, it["kind"])
        if missing and not s.get("fail"):
            problems.append(f"{iid}: no score for {', '.join(missing)}")
            continue
        mach = machine_score(data["machine"][iid])
        overall = 0.0 if s.get("fail") else VISUAL_SHARE * vis + (1 - VISUAL_SHARE) * mach
        rows[iid] = {"group": it["group"], "model": it.get("model", ""), "file": it["file"],
                     "visual": vis, "machine": mach, "overall": overall,
                     "fail": s.get("fail", ""), "note": s.get("note", "")}
    if problems:
        fail("the visual pass is not finished:\n  " + "\n  ".join(problems))

    def pair_value(a, b):
        key = f"{a}+{b}"
        ps = (data.get("pair_scores") or {}).get(key)
        if ps and isinstance(ps.get("match"), (int, float)):
            return (ps["match"] - 1) / 4, "eyes", ps.get("note", "")
        return data["pair_machine"][key] / 100, "machine", ""

    groups = list(data["groups"])
    live = {g: [i for i, r in rows.items() if r["group"] == g and not r["fail"]] for g in groups}
    combos = []
    if all(live.values()):
        for combo in itertools.product(*(live[g] for g in groups)):
            pick = dict(zip(groups, combo))
            mean = sum(rows[i]["overall"] for i in combo) / len(combo)
            matches = [pair_value(pick[r["a"]], pick[r["b"]]) + (r["relation"],) for r in data.get("pairs") or []]
            fit = sum(m[0] for m in matches) / len(matches) if matches else 1.0
            combos.append({"files": combo, "score": mean * (0.5 + 0.5 * fit), "mean": mean,
                           "fit": fit * 100, "matches": matches})
        combos.sort(key=lambda c: -c["score"])
    return rows, combos


def cmd_rank(args):
    data = load_yaml(args.round)
    rows, combos = compute(data)
    groups = data["groups"]
    lines = [f"# Judge report · {data['round']}", ""]
    if combos:
        best = combos[0]
        lines += [f"**Round score: {best['score']:.0f} / 100, {band(best['score'])}.**",
                  f"Best set: {' + '.join(best['files'])} (files {best['mean']:.0f}, match {best['fit']:.0f}).", ""]
    else:
        lines += ["**No complete set: every file in at least one group failed. Regenerate that group.**", ""]

    lines += ["## Best matching sets", "", "| # | Set | Score | Files | Match | Why |", "|---|---|---|---|---|---|"]
    for n, c in enumerate(combos[:args.top], 1):
        why = "; ".join(f"{rel} {v * 100:.0f} ({src}{': ' + note if note else ''})" for v, src, note, rel in c["matches"])
        lines.append(f"| {n} | {' + '.join(c['files'])} | **{c['score']:.0f}** | {c['mean']:.0f} | {c['fit']:.0f} | {why} |")

    for g in groups:
        ids = sorted((i for i, r in rows.items() if r["group"] == g), key=lambda i: -rows[i]["overall"])
        lines += ["", f"## {g} · {groups[g].get('label', g)}", "",
                  "| File | Overall | Eyes | Machine | Model | Note |", "|---|---|---|---|---|---|"]
        for i in ids:
            r = rows[i]
            shown = f"FAIL: {r['fail']}" if r["fail"] else r["note"]
            lines.append(f"| {i} | **{r['overall']:.0f}** | {r['visual']:.0f} | {r['machine']:.0f} | {r['model']} | {shown} |"
                         if not r["fail"] else f"| {i} | 0 | – | {r['machine']:.0f} | {r['model']} | {shown} |")

    models = sorted({r["model"] for r in rows.values() if r["model"]})
    if len(models) > 1:
        lines += ["", "## By model", "", "| Model | Files | Mean | Best | Fails |", "|---|---|---|---|---|"]
        for m in models:
            rs = [r for r in rows.values() if r["model"] == m]
            ok = [r["overall"] for r in rs if not r["fail"]]
            lines.append(f"| {m} | {len(rs)} | {sum(ok) / len(ok) if ok else 0:.0f} | {max(ok) if ok else 0:.0f} | "
                         f"{sum(1 for r in rs if r['fail'])} |")
    if data.get("fixes"):
        lines += ["", "## What to change before the next round", ""] + [f"- {f}" for f in data["fixes"]]
    lines += ["", "Scores: 85% Claude's eyes on the rubric in `scripts/judge.py`, 15% machine "
              "(sharpness, calm caption bands, palette pull, steadiness). A recommendation: the art director picks."]
    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(report)
    if args.sheet:
        write_sheet(args.sheet, data, rows, combos, Path(args.round).parent)
        print(f"wrote {args.sheet}")


def embedded(path, width=540):
    """A JPEG thumbnail as a data URI, so the sheet works when downloaded or sent on its own."""
    import base64, io
    img = Image.open(path).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def write_sheet(path, data, rows, combos, base):
    """A self-contained contact sheet with scores, best set first. Images are embedded;
    each one still links to its full-size file next to the round."""
    best = set(combos[0]["files"]) if combos else set()
    rel = Path(path).resolve().parent

    sections = []
    for g, meta in data["groups"].items():
        ids = sorted((i for i, r in rows.items() if r["group"] == g), key=lambda i: -rows[i]["overall"])
        cells = []
        for i in ids:
            r, it = rows[i], data["items"][i]
            show = data["machine"][i].get("strip") or it["file"]
            p = (base / show).resolve()
            href = str(p.relative_to(rel)) if p.is_relative_to(rel) else str(p)
            tag = " ".join(t for t in ("best" if i in best else "", "fail" if r["fail"] else "",
                                       "clip" if it["kind"] == "clip" else "") if t)
            label = "FAIL" if r["fail"] else f"{r['overall']:.0f}"
            width = 1400 if it["kind"] == "clip" else 540
            cells.append(f'<figure class="{tag}"><a href="{html.escape(href)}"><img src="{embedded(p, width)}" '
                         f'loading="lazy" alt="{i}"></a><figcaption><b>{i}</b> <span>{label}</span> '
                         f'{html.escape(r["model"])}<br><small>{html.escape(r["fail"] or r["note"])}</small>'
                         f'</figcaption></figure>')
        sections.append(f"<section><h2>{html.escape(g)} · {html.escape(str(meta.get('label', g)))}</h2>"
                        f"<div class=row>{''.join(cells)}</div></section>")
    head = (f"Round score {combos[0]['score']:.0f}, {band(combos[0]['score'])}. Best set: "
            f"{' + '.join(combos[0]['files'])}." if combos else "No complete set.")
    page = f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Judge sheet</title>
<style>
:root{{--bg:#f6f4ef;--fg:#1d1f1a;--muted:#6b6e64;--card:#fff;--best:#2f7d4f;--fail:#b3261e}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151613;--fg:#ecebe6;--muted:#9a9d92;--card:#22241f;--best:#6fcf97;--fail:#f2b8b5}}}}
body{{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif}}
h1{{font-size:20px;margin:0 0 4px}} p{{color:var(--muted);margin:0 0 16px}} h2{{font-size:16px;margin:24px 0 8px}}
.row{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}}
figure{{margin:0;background:var(--card);border-radius:8px;overflow:hidden;border:3px solid transparent}}
figure.clip{{grid-column:1/-1}} figure.best{{border-color:var(--best)}} figure.fail{{opacity:.55}} figure.fail span{{color:var(--fail)}}
img{{display:block;width:100%;background:#8883}} figcaption{{padding:6px 8px;font-size:13px}}
figcaption span{{float:right;font-weight:700}} small{{color:var(--muted)}}
</style>
<h1>{html.escape(data['round'])}</h1><p>{html.escape(head)} Green border: the best set. Scores are advice; the art director picks.</p>
{''.join(sections)}
</html>"""
    Path(path).write_text(page, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new", help="start a round file from groups of files")
    p.add_argument("round")
    p.add_argument("groups", nargs="+", help='GROUP="glob", relative to the round file')
    p.add_argument("--lock", help="the lock, relative to the round file (for the palette check)")
    p.add_argument("--pair", action="append", help="GROUP:GROUP:first_last|same_set")
    p.add_argument("--label", action="append", help='GROUP="what it is", e.g. D="S05 start, droopy plant"')
    p.add_argument("--name")
    p = sub.add_parser("measure", help="machine pass")
    p.add_argument("round")
    p.add_argument("--pairs", type=int, default=5, help="pairs per rule for Claude to judge by eye")
    p = sub.add_parser("rank", help="combine and rank")
    p.add_argument("round")
    p.add_argument("-o", "--out")
    p.add_argument("--sheet")
    p.add_argument("--top", type=int, default=3)
    args = ap.parse_args()
    {"new": cmd_new, "measure": cmd_measure, "rank": cmd_rank}[args.cmd](args)


if __name__ == "__main__":
    main()
