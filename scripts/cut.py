#!/usr/bin/env python3
"""Stage 8: cut the master from the kept clips, with supers and the end card set from the lock.

    python scripts/cut.py examples/driftpay/storyboard.yml -o master.mp4      # clips from kept.yml
    python scripts/cut.py <storyboard> --clip S01=clips/S01.mp4 --clip S02=clips/S02.mp4@0.4 ... -o master.mp4

- Shots run in storyboard order, each trimmed to its `duration_s` (from an optional
  in-point: `@0.4` starts 0.4 s into the clip) and scaled to the master size.
- Every `super` is set in the top safe band as a tag: the lock's background colour behind
  its "type on light" colour, checked for contrast. Type is never generated.
- A shot with `generate: false` (the end card) is drawn from the lock: brand wordmark,
  the rest of its super as the line under it, on the background colour.
- Sound: each clip's own sound, soft edges between shots, then two-pass loudness
  normalisation to the target in platforms/specs.yml.
Needs ffmpeg. The result still goes through spec_check.py and the art director.
"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from common import fail, load_specs, load_storyboard, load_yaml, parse_aspect, safe_union
import static_compose as sc

FPS = 24
SHORT_SIDE = 1080


def run(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode:
        fail(f"{' '.join(cmd[:4])} ... failed:\n{res.stderr[-800:]}")
    return res


def has_audio(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    return bool(out.strip())


def colours(lock):
    bg = sc.palette_role(lock, "background", default=(244, 241, 234))
    ink = sc.palette_role(lock, "type", "light", default=(30, 42, 68))
    if sc.contrast(bg, ink) < sc.MIN_CONTRAST:
        fail(f"type on light vs background is {sc.contrast(bg, ink):.1f}:1, under {sc.MIN_CONTRAST}:1")
    accent = sc.palette_role(lock, "hero", default=ink)
    return bg, ink, accent


def super_png(text, size, zone, lock, font_path, out):
    """The super as a paper tag in the top safe band, on a transparent layer."""
    w, h = size
    bg, ink, _ = colours(lock)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    side = w * (zone["left"] + 4) / 100
    pad = round(h * 0.012)
    start = round(h * max(float((lock.get("type") or {}).get("min_size_pct_of_height", 3.5)), 3.5) / 100 * 1.15)
    font, lines = sc.fit_headline(draw, text, font_path, w - 2 * side - 2 * pad, start)
    asc, desc = font.getmetrics()
    line_h = round((asc + desc) * 1.12)
    box_w = max(draw.textlength(l, font=font) for l in lines) + 2 * pad
    box_h = line_h * len(lines) + 2 * pad - round(line_h * 0.12)
    x0 = (w - box_w) / 2
    y0 = h * zone["top"] / 100 + h * 0.015
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((x0, y0 + 6, x0 + box_w, y0 + box_h + 6), radius=pad, fill=(0, 0, 0, 70))
    layer = Image.alpha_composite(layer, shadow.filter(ImageFilter.GaussianBlur(8)))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((x0, y0, x0 + box_w, y0 + box_h), radius=pad, fill=bg + (242,))
    for i, line in enumerate(lines):
        lw = draw.textlength(line, font=font)
        draw.text(((w - lw) / 2, y0 + pad + i * line_h), line, font=font, fill=ink)
    layer.save(out)


def end_card_png(shot, lock, size, zone, font_path, out):
    """Brand wordmark with a small paper plane above it, the line under it, all inside the safe zone."""
    w, h = size
    bg, ink, accent = colours(lock)
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    brand = lock["meta"]["brand"]
    line = re.sub(rf"^\s*{re.escape(brand)}\s*[.:,-]?\s*", "", shot.get("super", "")).strip()
    top, bottom = h * zone["top"] / 100, h * (1 - zone["bottom"] / 100)
    centre = (top + bottom) / 2
    mark = ImageFont.truetype(font_path, round(w * 0.15))
    mw = draw.textlength(brand, font=mark)
    asc, desc = mark.getmetrics()
    # A paper plane from three facets: the lit wing, the shaded wing, the keel.
    px, py, s = w / 2, centre - asc * 1.35, w * 0.085
    draw.polygon([(px - s, py + s * 0.35), (px + s, py - s * 0.45), (px - s * 0.1, py + s * 0.15)], fill=accent)
    draw.polygon([(px - s * 0.1, py + s * 0.15), (px + s, py - s * 0.45), (px + s * 0.05, py + s * 0.6)],
                 fill=tuple(round(c * 0.8) for c in accent))
    draw.polygon([(px - s * 0.1, py + s * 0.15), (px + s * 0.05, py + s * 0.6), (px - s * 0.2, py + s * 0.35)],
                 fill=tuple(round(c * 0.65) for c in accent))
    draw.text(((w - mw) / 2, centre - asc / 2), brand, font=mark, fill=ink)
    if line:
        body = ImageFont.truetype(font_path, round(w * 0.05))
        lw = draw.textlength(line, font=body)
        if lw > w * 0.84:
            body = ImageFont.truetype(font_path, round(w * 0.05 * w * 0.84 / lw))
            lw = draw.textlength(line, font=body)
        draw.text(((w - lw) / 2, centre + asc / 2 + desc + h * 0.02), line, font=body, fill=ink)
    img.save(out)


def segment(src, start, dur, size, overlay, out, fade_in=0.0, bg=None):
    w, h = size
    # Cover, then centre-crop: a no-op for the master ratio, a clean centre cut for 4:5 or 1:1.
    fx = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},setsar=1,fps={FPS}"
    if fade_in:
        fx += f",fade=in:st=0:d={fade_in}:color=0x{bytes(bg).hex()}"
    af = f"aresample=48000,aformat=channel_layouts=stereo,afade=in:d=0.04,afade=out:st={dur - 0.06:.3f}:d=0.06"
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if src.suffix.lower() == ".png":
        cmd += ["-loop", "1", "-t", f"{dur}", "-i", str(src)]
    else:
        cmd += ["-ss", f"{start}", "-t", f"{dur}", "-i", str(src)]
    if overlay:
        cmd += ["-loop", "1", "-t", f"{dur}", "-i", str(overlay)]
    audio_in = 2 if overlay else 1          # input index of the silent track, when the clip has no sound
    if src.suffix.lower() != ".png" and has_audio(src):
        amap = "0:a"
    else:
        cmd += ["-f", "lavfi", "-t", f"{dur}", "-i", "anullsrc=r=48000:cl=stereo"]
        amap = f"{audio_in}:a"
    vf = f"[0:v]{fx}[v0]" + (";[v0][1:v]overlay=0:0:format=auto[v]" if overlay else ";[v0]null[v]")
    cmd += ["-filter_complex", vf + f";[{amap}]{af}[a]", "-map", "[v]", "-map", "[a]", "-t", f"{dur}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17", "-preset", "slow", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", str(out)]
    run(cmd)


def loudnorm(src, out, target, total):
    i, tp = target["integrated_lufs"], min(target["true_peak_dbtp_max"] - 0.5, -1.5)
    first = run(["ffmpeg", "-hide_banner", "-i", str(src), "-af", f"loudnorm=I={i}:TP={tp}:LRA=11:print_format=json",
                 "-f", "null", "-"]).stderr
    m = json.loads(first[first.rfind("{"):first.rfind("}") + 1])
    af = (f"loudnorm=I={i}:TP={tp}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    # Linear gain keeps the dynamics but cannot hold the true peak; a 4x-oversampled limiter does.
    af += ",aresample=192000,alimiter=limit=0.70:attack=1:release=50:level=false,aresample=48000"
    # The AAC encoder delay adds ~0.02 s to the container, so drop the end card's last frame:
    # the file then reports just under the storyboard length instead of a hair over it.
    frames = round(total * FPS) - 1
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-frames:v", str(frames), "-t", f"{frames / FPS:.3f}", "-c:v", "copy", "-af", af, "-ar", "48000",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("storyboard")
    ap.add_argument("--clip", action="append", default=[], help="SHOT=path.mp4[@in_seconds]; overrides kept.yml")
    ap.add_argument("--kept", help="kept.yml with the kept clips (default: kept.yml next to the storyboard)")
    ap.add_argument("--font", help="brand font file; falls back to the lock's family, then a system bold sans")
    ap.add_argument("--aspect", help="cut another ratio (e.g. 4:5) from the same clips; supers move into its safe zone")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    board, lock = load_storyboard(args.storyboard)
    specs = load_specs()
    ad = board["ad"]
    aspect = args.aspect or ad["master_aspect"]
    aw, ah = parse_aspect(aspect)
    size = (SHORT_SIDE, round(SHORT_SIDE * ah / aw)) if ah >= aw else (round(SHORT_SIDE * aw / ah), SHORT_SIDE)
    same = [p for p in ad["platforms"] if aspect in specs["platforms"][p]["aspects"]]
    if not same:
        fail(f"no target platform takes {aspect}")
    zone = safe_union(specs, same or ad["platforms"])
    font_path, fallback = sc.find_font(args.font, (lock.get("type") or {}).get("family", "").split("(")[0].strip(),
                                       sc.FALLBACK_BODY)
    if fallback:
        print(f"note: brand font not installed; set in {Path(font_path).name}. Pass --font to use the brand font.")

    clips = {}
    kept_path = Path(args.kept) if args.kept else Path(args.storyboard).parent / "kept.yml"
    if kept_path.exists():
        for sid, spec in ((load_yaml(kept_path) or {}).get("clips") or {}).items():
            path, _, start = str(spec).partition("@")
            clips[sid] = (kept_path.parent / path, float(start or 0))
    for spec in args.clip:
        sid, _, rest = spec.partition("=")
        path, _, start = rest.partition("@")
        if not Path(path).exists():
            fail(f"{sid}: clip not found: {path}")
        clips[sid] = (Path(path), float(start or 0))

    bg = colours(lock)[0]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts, total = [], 0.0
        for n, shot in enumerate(board["shots"]):
            dur = float(shot["duration_s"])
            seg = tmp / f"{n:02d}.mp4"
            if not shot.get("generate", True):
                card = tmp / f"{shot['id']}.png"
                end_card_png(shot, lock, size, zone, font_path, card)
                segment(card, 0, dur, size, None, seg, fade_in=0.25, bg=bg)
            else:
                if shot["id"] not in clips:
                    fail(f"no clip for {shot['id']}: add --clip {shot['id']}=path.mp4")
                src, start = clips[shot["id"]]
                overlay = None
                if shot.get("super"):
                    overlay = tmp / f"{shot['id']}-super.png"
                    super_png(shot["super"], size, zone, lock, font_path, overlay)
                segment(src, start, dur, size, overlay, seg)
            parts.append(seg)
            total += dur
            print(f"{shot['id']:4} {dur:>4}s  {clips.get(shot['id'], ('end card', 0))[0]}")
        listing = tmp / "list.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        joined = tmp / "joined.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)])
        loudnorm(joined, Path(args.out), specs["loudness"], total)
    print(f"wrote {args.out}: {size[0]}x{size[1]}, {total:g}s, {FPS} fps, loudness target {specs['loudness']['integrated_lufs']} LUFS")


if __name__ == "__main__":
    main()
