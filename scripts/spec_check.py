#!/usr/bin/env python3
"""Check an exported video against platforms/specs.yml before a person reviews it.

    python scripts/spec_check.py ad.mp4 --platform tiktok
    python scripts/spec_check.py ad.mp4 --platform tiktok meta_vertical --overlay
    python scripts/spec_check.py ad.mp4            # every platform that takes this ratio

Checks: aspect ratio, resolution, duration, frame rate, audio, loudness,
true peak and file size. With --overlay it also saves the hook frame and the
last frame with each platform's unsafe margins darkened and the safe area
outlined, for the art director to judge by eye.

Exit code 1 if any check FAILs, so it can gate an automated pipeline.
Needs ffmpeg and ffprobe on the PATH.
"""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from common import fail, load_specs, parse_aspect

ASPECT_TOLERANCE = 0.01


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    info = json.loads(out)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        fail(f"{path} has no video stream")
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    num, den = video.get("avg_frame_rate", "0/1").split("/")
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": float(num) / float(den) if float(den) else 0.0,
        "duration": float(info["format"]["duration"]),
        "size_mb": int(info["format"]["size"]) / 1_000_000,
        "codec": video["codec_name"],
        "audio": audio is not None,
    }


def loudness(path):
    """Integrated loudness (LUFS) and true peak (dBTP) from ffmpeg's EBU R128 filter."""
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    summary = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary)
    tp = re.search(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    to_float = lambda m: float(m.group(1)) if m and m.group(1) != "-inf" else float("-inf")
    return to_float(i), to_float(tp)


def matches_aspect(width, height, aspect):
    w, h = parse_aspect(aspect)
    return abs(width / height - w / h) <= ASPECT_TOLERANCE * (w / h)


def check_platform(pid, spec, media, loud, rules):
    results = []
    add = lambda level, msg: results.append((level, msg))

    aspect = next((a for a in spec["aspects"] if matches_aspect(media["width"], media["height"], a)), None)
    if aspect:
        add("PASS", f"aspect {aspect}")
    else:
        add("FAIL", f"{media['width']}x{media['height']} is not one of {', '.join(spec['aspects'])}")

    short = min(media["width"], media["height"])
    target = min(spec["resolution"])
    if short < spec["min_short_side"]:
        add("FAIL", f"short side {short}px, minimum {spec['min_short_side']}px")
    elif short < target:
        add("WARN", f"short side {short}px, recommended {target}px")
    else:
        add("PASS", f"resolution {media['width']}x{media['height']}")

    dur = media["duration"]
    lo, hi = spec["duration_s"]["recommended"]
    if dur > spec["duration_s"]["max"]:
        add("FAIL", f"{dur:.1f}s, maximum {spec['duration_s']['max']}s")
    elif not lo <= dur <= hi:
        add("WARN", f"{dur:.1f}s, recommended {lo}-{hi}s")
    else:
        add("PASS", f"duration {dur:.1f}s")

    fmin, fmax = spec["fps"]
    if not fmin - 0.01 <= media["fps"] <= fmax + 0.01:
        add("FAIL", f"{media['fps']:.2f} fps, allowed {fmin}-{fmax}")
    else:
        add("PASS", f"{media['fps']:.2f} fps")

    if media["size_mb"] > spec["max_file_mb"]:
        add("FAIL", f"{media['size_mb']:.0f} MB, maximum {spec['max_file_mb']} MB")

    if not media["audio"]:
        add("WARN" if spec["audio"] == "expected" else "PASS",
            "no audio track" + (" (this platform expects sound)" if spec["audio"] == "expected" else ""))
    elif loud:
        lufs, peak = loud
        target_lufs, tol = rules["integrated_lufs"], rules["tolerance_lu"]
        if lufs == float("-inf"):
            add("WARN", "audio track is silent")
        elif abs(lufs - target_lufs) > tol:
            add("WARN", f"loudness {lufs:.1f} LUFS, target {target_lufs} ±{tol}")
        else:
            add("PASS", f"loudness {lufs:.1f} LUFS")
        if peak > rules["true_peak_dbtp_max"]:
            add("FAIL", f"true peak {peak:.1f} dBTP, ceiling {rules['true_peak_dbtp_max']} dBTP")
        elif peak != float("-inf"):
            add("PASS", f"true peak {peak:.1f} dBTP")
    return results


def overlay(path, pid, spec, media, out_dir):
    """Save the hook frame and the last frame: unsafe margins darkened, safe area outlined."""
    z = spec["safe_zone_pct"]
    boxes = [
        ("0", "0", "iw", f"ih*{z['top'] / 100}"),
        ("0", f"ih*{1 - z['bottom'] / 100}", "iw", f"ih*{z['bottom'] / 100}"),
        ("0", f"ih*{z['top'] / 100}", f"iw*{z['left'] / 100}", f"ih*{1 - (z['top'] + z['bottom']) / 100}"),
        (f"iw*{1 - z['right'] / 100}", f"ih*{z['top'] / 100}", f"iw*{z['right'] / 100}",
         f"ih*{1 - (z['top'] + z['bottom']) / 100}"),
    ]
    draw = ",".join(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=black@0.55:t=fill" for x, y, w, h in boxes)
    # Outline the safe area in cyan, which reads over warm and dark footage alike.
    draw += (f",drawbox=x=iw*{z['left'] / 100}:y=ih*{z['top'] / 100}"
             f":w=iw*{1 - (z['left'] + z['right']) / 100}:h=ih*{1 - (z['top'] + z['bottom']) / 100}"
             ":color=cyan@0.9:t=6")
    saved = []
    for label, t in (("hook", 0.5), ("end", max(media["duration"] - 0.5, 0))):
        target = out_dir / f"{Path(path).stem}_{pid}_{label}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{min(t, media['duration']):.2f}", "-i", str(path),
             "-frames:v", "1", "-vf", draw, str(target)],
            check=True,
        )
        saved.append(target)
    return saved


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--platform", nargs="+", help="platform ids from platforms/specs.yml")
    ap.add_argument("--overlay", action="store_true", help="save safe-zone overlay frames")
    ap.add_argument("--out-dir", default=None, help="where overlays go (default: next to the video)")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            fail(f"{tool} not found. Install ffmpeg first.")
    if not Path(args.video).exists():
        fail(f"file not found: {args.video}")

    specs = load_specs()
    media = probe(args.video)
    if args.platform:
        unknown = [p for p in args.platform if p not in specs["platforms"]]
        if unknown:
            fail(f"unknown platform(s): {', '.join(unknown)}")
        targets = args.platform
    else:
        targets = [pid for pid, s in specs["platforms"].items()
                   if any(matches_aspect(media["width"], media["height"], a) for a in s["aspects"])]
        if not targets:
            fail(f"no platform takes {media['width']}x{media['height']}")

    loud = loudness(args.video) if media["audio"] else None
    out_dir = Path(args.out_dir or Path(args.video).parent)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"{Path(args.video).name} · {media['width']}x{media['height']} · {media['duration']:.1f}s · "
          f"{media['fps']:.2f} fps · {media['codec']} · {media['size_mb']:.1f} MB")
    failed = False
    for pid in targets:
        spec = specs["platforms"][pid]
        print(f"\n{spec['name']} ({pid})")
        for level, msg in check_platform(pid, spec, media, loud, specs["loudness"]):
            print(f"  {level:<4}  {msg}")
            failed |= level == "FAIL"
        if args.overlay:
            for f in overlay(args.video, pid, spec, media, out_dir):
                print(f"  file  {f}")

    print("\nRESULT:", "FAIL" if failed else "PASS (a person still judges the craft)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
