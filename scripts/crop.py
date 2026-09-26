#!/usr/bin/env python3
"""Cut a feed version (4:5 or 1:1) from the 9:16 master with a centre crop.

    python scripts/crop.py master.mp4 4:5
    python scripts/crop.py master.mp4 1:1 -o feed_1x1.mp4

Free, where a generated reframe costs credits (about 138 for 15s at 1080p on
Higgsfield). It only works when the master's safe area survives the crop, so
the script checks that first against the strictest 9:16 safe zone in
platforms/specs.yml and stops if the crop would cut into it.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from common import fail, load_specs, parse_aspect, safe_union


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("aspect", help="target ratio, e.g. 4:5 or 1:1")
    ap.add_argument("-o", "--out", help="output path (default: <name>_<ratio>.mp4)")
    ap.add_argument("--force", action="store_true", help="crop even if it cuts into the safe area")
    args = ap.parse_args()

    info = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "json", args.video], capture_output=True, text=True, check=True).stdout)
    width, height = info["streams"][0]["width"], info["streams"][0]["height"]
    tw, th = parse_aspect(args.aspect)
    new_h = round(width * th / tw / 2) * 2
    if new_h > height:
        fail(f"{args.aspect} is wider than the source; this script only crops height")
    cut_pct = (height - new_h) / 2 / height * 100

    specs = load_specs()
    nine = [p for p, s in specs["platforms"].items() if "9:16" in s["aspects"]]
    zone = safe_union(specs, nine)
    fits = cut_pct <= zone["top"] and cut_pct <= zone["bottom"]
    print(f"crop removes {cut_pct:.1f}% top and bottom; 9:16 safe zone is top {zone['top']}% / bottom {zone['bottom']}%")
    if not fits and not args.force:
        print("FAIL  the crop cuts into the safe area. Use a generated reframe, or --force and check by eye.",
              file=sys.stderr)
        sys.exit(1)

    out = args.out or str(Path(args.video).with_name(f"{Path(args.video).stem}_{tw}x{th}.mp4"))
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", args.video,
         "-vf", f"crop={width}:{new_h}:0:{(height - new_h) // 2}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "copy", out],
        check=True,
    )
    print(("PASS  " if fits else "WARN  ") + f"wrote {out} ({width}x{new_h})")


if __name__ == "__main__":
    main()
