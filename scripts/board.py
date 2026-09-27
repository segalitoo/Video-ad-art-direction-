#!/usr/bin/env python3
"""The visual storyboard: one card per shot, start frame to end frame, to scan the flow at a glance.

    python scripts/board.py examples/driftpay/storyboard.yml -o board.html
    python scripts/board.py examples/driftpay/storyboard.yml --kept kept.yml -o board.html

Each card shows the shot's timecode, its start and end frame with the super drawn where the
viewer will see it, a 5-frame strip of the kept clip, and the action, camera and sound.
Between cards a badge says how the cut connects: chained (starts on the previous end frame),
reused, or a hard cut. A frame that does not exist yet is drawn as a sketch box with its
subject, so the same board works at stage 3, before anything is generated.

kept.yml (next to the storyboard; paths relative to it) names the kept files:

    frames: {S01-K: test/out/S01_2.jpg, S01-K-end: ...}
    clips:  {S01: final/out/S01.mp4@0.4}      # @ = the in-point used in the cut

The page is self-contained (images embedded) and can be published as it is.
"""

import argparse
import base64
import html
import io
from pathlib import Path
import subprocess
import tempfile

from PIL import Image

from common import load_route, load_specs, load_storyboard, load_yaml, parse_aspect, safe_union
from judge import colour_match, hue_hist, region_labs, structure_match, thumb_gray
from static_compose import hex_rgb, palette_role

JUMP = 70   # a join under this reads as a jump between clips (judge.py similarity, 0-100)


def data_uri(img, width):
    img = img.convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def clip_strip(path, start, dur, n=5):
    """n frames across the part of the clip the cut uses."""
    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(n):
            t = start + dur * (i + 0.5) / n
            out = Path(tmp) / f"{i}.png"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                            str(out)], check=True)
            frames.append(data_uri(Image.open(out), 160))
    return frames


def tc(seconds):
    return f"{int(seconds // 60):02d}:{seconds % 60:04.1f}"


def frame_box(src, label, text, super_text, zone, aspect_css):
    sup = (f'<span class="super" style="top:calc({zone["top"]:g}% + 1.5%)">{html.escape(super_text)}</span>'
           if super_text else "")
    band = (f'<i class="unsafe top" style="height:{zone["top"]:g}%"></i>'
            f'<i class="unsafe bottom" style="height:{zone["bottom"]:g}%"></i>')
    inner = (f'<img src="{src}" alt="{html.escape(label)}">' if src
             else f'<span class="sketch">{html.escape(text or "not written yet")}</span>')
    cls = "frame" if src else "frame missing"
    return (f'<figure class="{cls}" style="aspect-ratio:{aspect_css}">{inner}{band}{sup}'
            f'<figcaption>{html.escape(label)}</figcaption></figure>')


def end_card_html(shot, lock, aspect_css):
    brand = lock["meta"]["brand"]
    line = shot.get("super", "")
    if line.lower().startswith(brand.lower()):
        line = line[len(brand):].lstrip(" .:,-")
    bg = "#%02x%02x%02x" % palette_role(lock, "background", default=(244, 241, 234))
    ink = "#%02x%02x%02x" % palette_role(lock, "type", "light", default=(30, 42, 68))
    return (f'<figure class="frame endcard" style="aspect-ratio:{aspect_css};background:{bg};color:{ink}">'
            f'<b>{html.escape(brand)}</b><span>{html.escape(line)}</span><figcaption>end card, drawn in the edit</figcaption></figure>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("storyboard")
    ap.add_argument("--kept", help="kept.yml (default: kept.yml next to the storyboard, if it exists)")
    ap.add_argument("--standalone", action="store_true", help="wrap in a full HTML document for local viewing")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    board, lock = load_storyboard(args.storyboard)
    base = Path(args.storyboard).parent
    kept_path = Path(args.kept) if args.kept else base / "kept.yml"
    kept = load_yaml(kept_path) if kept_path.exists() else {}
    kbase = kept_path.parent
    frames, clips = kept.get("frames") or {}, kept.get("clips") or {}
    ad, specs = board["ad"], load_specs()
    w, h = parse_aspect(ad["master_aspect"])
    aspect_css = f"{w}/{h}"
    same = [p for p in ad["platforms"] if ad["master_aspect"] in specs["platforms"][p]["aspects"]]
    zone = safe_union(specs, same or ad["platforms"])

    def kept_img(fid):
        f = frames.get(fid)
        return Image.open(kbase / f).convert("RGB") if f and (kbase / f).exists() else None

    def clip_img(sid, at_end, dur):
        """The first or last frame the cut actually uses from this shot's kept clip."""
        if sid not in clips:
            return None
        path, _, start = str(clips[sid]).partition("@")
        if not (kbase / path).exists():
            return None
        t = float(start or 0) + (max(dur - 0.05, 0) if at_end else 0)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f.png"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(kbase / path),
                            "-frames:v", "1", str(out)], check=True)
            return Image.open(out).convert("RGB")

    def join(a, b):
        """How alike the last frame of one shot and the first of the next are, 0-100."""
        fa = {"_hist": hue_hist(a), "_cells": region_labs(a)}
        fb = {"_hist": hue_hist(b), "_cells": region_labs(b)}
        return round(0.5 * structure_match(thumb_gray(a), thumb_gray(b)) + 0.5 * colour_match(fa, fb))

    shots, cards, t = board["shots"], [], 0.0
    segs, joins = [], []
    total = sum(float(s.get("duration_s", 0)) for s in shots)
    prev, prev_out = None, None
    for shot in shots:
        dur = float(shot.get("duration_s", 0))
        sid = shot["id"]
        segs.append(f'<span class="seg beat-{html.escape(shot.get("beat", ""))}" style="flex:{dur}" '
                    f'title="{sid} {tc(t)}–{tc(t + dur)}">{sid}</span>')
        start_img = end_img = None
        if shot.get("generate", True):
            start_id = shot.get("from_frame") or f"{sid}-K"
            start_img = kept_img(start_id) or clip_img(sid, False, dur)
            end_img = kept_img(f"{sid}-K-end") if shot.get("end_subject") else None
            out_img = clip_img(sid, True, dur)
            end_label = f"{sid}-K-end" if end_img else f"{sid} clip, out at {dur:g}s"
            end_img = end_img or out_img
        score = join(prev_out, start_img) if prev_out is not None and start_img is not None else None
        joins.append(score)
        score_txt = f" · join {score}%" if score is not None else ""
        chip = '<span class="in c-open">opening frame</span>'
        if prev is not None:
            if not shot.get("generate", True):
                chip = '<span class="in c-hard">cut to the end card</span>'
            elif shot.get("_chained"):
                chip = f'<span class="in c-chained">continues from {prev}{score_txt}</span>'
            elif shot.get("from_frame"):
                chip = f'<span class="in c-reused">starts on the kept {shot["from_frame"]}{score_txt}</span>'
            elif shot.get("edit_of"):
                chip = f'<span class="in c-reused">edit of {shot["edit_of"]}{score_txt}</span>'
            else:
                chip = f'<span class="in c-hard">hard cut: a new frame{score_txt}</span>'
            if score is not None and score < JUMP and shot.get("cut") != "hard":
                chip = chip.replace('class="in ', 'class="in c-jump ').replace("</span>", ": a visible jump</span>", 1)
        if not shot.get("generate", True):
            body = end_card_html(shot, lock, aspect_css)
        else:
            body = frame_box(data_uri(start_img, 360) if start_img else None, start_id, shot.get("subject", ""),
                             shot.get("super"), zone, aspect_css)
            body += '<span class="arrow" aria-hidden="true">→</span>'
            body += frame_box(data_uri(end_img, 360) if end_img else None, end_label if end_img else f"{sid} end",
                              shot.get("end_subject") or "the clip's last frame", None, zone, aspect_css)
        strip = ""
        if sid in clips:
            path, _, start = str(clips[sid]).partition("@")
            if (kbase / path).exists():
                strip = '<div class="strip">' + "".join(f'<img src="{u}" alt="">' for u in
                                                      clip_strip(kbase / path, float(start or 0), dur)) + "</div>"
        rows = [("Action", shot.get("action")), ("Camera", shot.get("camera_move")),
                ("Sound", shot.get("sfx") or shot.get("sound")), ("Voice", shot.get("vo"))]
        meta = "".join(f"<dt>{k}</dt><dd>{html.escape(str(v))}</dd>" for k, v in rows if v)
        cards.append(f'<article class="shot">{chip}<header><b>{sid}</b><span class="beat">{html.escape(shot.get("beat", ""))}</span>'
                     f'<span class="tc">{tc(t)} – {tc(t + dur)} · {dur:g}s</span></header>'
                     f'<div class="frames">{body}</div>{strip}<dl>{meta}</dl></article>')
        t += dur
        prev, prev_out = sid, (end_img if shot.get("generate", True) else None)

    chained = sum(1 for s in shots if s.get("_chained"))
    hard = sum(1 for i, s in enumerate(shots) if i and s.get("generate", True) and not s.get("from_frame"))
    route = load_route(None, board)[0]
    scored = [j for j in joins if j is not None]
    worst = min(scored) if scored else None
    swatches = "".join(f'<span class="sw" style="background:{c["hex"]}" title="{html.escape(c["name"])}"></span>'
                       for c in lock.get("palette") or [])
    page = f"""<title>{html.escape(lock['meta']['brand'])} Storyboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@500&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>
:root{{--bg:#EDF0F3;--surface:#FFFFFF;--ink:#1A2130;--muted:#5D6778;--line:#D5DAE1;--accent:#2F5BD8;--chain:#2F7D55;--hard:#A86A12;--unsafe:rgba(26,33,48,.10);
--f-display:"Barlow Condensed","Arial Narrow",Arial,sans-serif;--f-body:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;--f-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--bg:#12161C;--surface:#1B212A;--ink:#E6EAF0;--muted:#98A2B2;--line:#2C3440;--accent:#8AA6FF;--chain:#6CC795;--hard:#E0A64A;--unsafe:rgba(0,0,0,.28)}}}}
:root[data-theme="dark"]{{color-scheme:dark;--bg:#12161C;--surface:#1B212A;--ink:#E6EAF0;--muted:#98A2B2;--line:#2C3440;--accent:#8AA6FF;--chain:#6CC795;--hard:#E0A64A;--unsafe:rgba(0,0,0,.28)}}
body{{background:var(--bg);color:var(--ink);font:15px/1.5 var(--f-body)}}
.wrap{{max-width:1320px;margin:0 auto;padding-inline:16px;padding-block:28px 48px}}
h1{{font:700 clamp(28px,4vw,40px)/1.05 var(--f-display);letter-spacing:.01em;margin:0;text-wrap:balance}}
.sub{{color:var(--muted);margin:6px 0 18px;font-size:14px}}
.sub code{{font:500 12.5px var(--f-mono);color:var(--accent)}}
.facts{{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:center;font-size:13px;color:var(--muted);margin-bottom:12px}}
.facts b{{color:var(--ink);font-weight:600}}
.sw{{display:inline-block;width:14px;height:14px;border-radius:3px;margin-right:3px;vertical-align:-2px;box-shadow:inset 0 0 0 1px rgba(0,0,0,.12)}}
.timeline{{display:flex;gap:2px;height:30px;margin:0 0 26px;border-radius:6px;overflow:hidden}}
.seg{{display:flex;align-items:center;justify-content:center;font:700 13px var(--f-display);letter-spacing:.06em;color:#fff;background:var(--accent);min-width:0}}
.beat-hook{{background:#1F3F9E}}.beat-payoff{{background:var(--chain)}}.beat-end-card{{background:#5D6778}}
.board{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));gap:18px}}
.shot{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px;display:flex;flex-direction:column;gap:10px}}
.shot header{{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}}
.shot header b{{font:700 26px/1 var(--f-display)}}
.beat{{font:600 11px var(--f-body);text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}}
.tc{{margin-left:auto;font:500 12px var(--f-mono);color:var(--accent);font-variant-numeric:tabular-nums}}
.frames{{display:flex;align-items:center;gap:6px}}
.arrow{{color:var(--muted);font-size:18px;flex:none}}
.frame{{position:relative;flex:1;margin:0;border-radius:6px;overflow:hidden;background:var(--bg);container-type:inline-size;max-width:100%}}
.frame img{{width:100%;height:100%;object-fit:cover;display:block}}
.frame figcaption{{position:absolute;left:6px;bottom:6px;font:500 10.5px var(--f-mono);background:rgba(10,14,20,.72);color:#fff;padding:2px 5px;border-radius:3px}}
.unsafe{{position:absolute;left:0;right:0;background:var(--unsafe);pointer-events:none}}.unsafe.top{{top:0}}.unsafe.bottom{{bottom:0}}
.super{{position:absolute;left:8%;right:8%;text-align:center;font:700 6.6cqw/1.2 var(--f-body);color:#1A2130;background:rgba(244,241,234,.94);border-radius:1.5cqw;padding:1.4cqw 2cqw;box-shadow:0 1px 4px rgba(0,0,0,.2)}}
.missing{{outline:1.5px dashed var(--line);outline-offset:-1.5px;display:flex;align-items:center;justify-content:center}}
.sketch{{padding:10%;font:italic 13px/1.4 var(--f-body);color:var(--muted);text-align:center}}
.endcard{{flex:0 0 calc(50% - 15px);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2cqw;text-align:center}}
.endcard b{{font:700 15cqw/1 var(--f-body)}}.endcard span{{font:600 5.4cqw/1.3 var(--f-body);padding-inline:8%}}
.strip{{display:grid;grid-template-columns:repeat(5,1fr);gap:3px}}.strip img{{width:100%;border-radius:3px;display:block}}
dl{{display:grid;grid-template-columns:auto 1fr;gap:4px 10px;margin:0;font-size:13.5px}}
dt{{font:600 11px var(--f-body);text-transform:uppercase;letter-spacing:.07em;color:var(--muted);padding-top:2px}}dd{{margin:0}}
.legend{{display:flex;flex-wrap:wrap;gap:14px;font-size:12.5px;color:var(--muted);margin:-10px 0 22px}}
.chip{{display:inline-block;font:600 11px var(--f-body);padding:2px 8px;border-radius:99px;margin-right:6px}}
.c-chained{{background:color-mix(in srgb,var(--chain) 16%,transparent);color:var(--chain)}}
.c-reused{{background:color-mix(in srgb,var(--accent) 14%,transparent);color:var(--accent)}}
.c-hard{{background:color-mix(in srgb,var(--hard) 16%,transparent);color:var(--hard)}}
.c-open{{background:color-mix(in srgb,var(--muted) 14%,transparent);color:var(--muted)}}
.c-jump{{background:color-mix(in srgb,#C2352B 16%,transparent);color:#C2352B}}
.shot .in{{font:600 11px var(--f-body);padding:2px 8px;border-radius:99px;align-self:flex-start}}
</style>
<div class="wrap">
<h1>{html.escape(lock['meta']['brand'])} · {html.escape(lock['meta'].get('campaign', ''))}</h1>
<p class="sub"><code>{html.escape(ad['id'])}</code> · lock v{html.escape(str(lock['meta']['version']))} · {html.escape(ad['master_aspect'])} master · {total:g}s · {html.escape(', '.join(ad['platforms']))}</p>
<div class="facts"><span><b>{len(shots)}</b> shots</span><span><b>{chained}</b> chained cuts</span><span><b>{hard}</b> hard cuts</span><span>route <b>{html.escape(route)}</b></span><span>weakest join <b>{'n/a' if worst is None else f'{worst}%'}</b></span><span>{swatches}</span></div>
<div class="timeline" role="img" aria-label="Shot timeline">{''.join(segs)}</div>
<div class="legend"><span><span class="chip c-chained">chained</span>starts on the previous shot's end frame</span><span><span class="chip c-reused">reused</span>starts on a kept frame from earlier</span><span><span class="chip c-hard">hard cut</span>a new frame, on purpose</span><span><span class="chip c-jump">jump</span>join under 70%: the next clip does not start where this one ends</span><span>Shaded bands: platform UI covers them.</span></div>
<div class="board">{''.join(cards)}</div>
</div>"""
    out = Path(args.out)
    if args.standalone:
        page = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
                'content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>' + page + "</body></html>")
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out}: {len(shots)} shots, {len(frames)} kept frames, {sum(1 for s in clips if s in {x['id'] for x in shots})} clips")


if __name__ == "__main__":
    main()
