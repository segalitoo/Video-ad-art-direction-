#!/usr/bin/env python3
"""Give a clean generated clip the feel of phone footage: handheld drift, grain, light flicker.

    python scripts/phone_look.py clip.mp4
    python scripts/phone_look.py clip.mp4 --shake 2 --grain 8 -o clip_phone.mp4

Why in the edit and not in the prompt: video models asked for "handheld" tend to add
shake that swims or warps the whole frame. Generating a steady clip and adding the
movement here keeps it believable, the same across shots, and adjustable for free.

--shake 0-3   how much the camera drifts (0 = locked off, 1 = breathing, 3 = walking)
--grain 0-15  sensor noise
The frame is scaled up 6% so the drift never shows an edge; size and sound are kept.
"""

import argparse
import json
from pathlib import Path
import subprocess

from common import fail

SHAKE_PX = {0: 0, 1: 6, 2: 12, 3: 22}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip")
    ap.add_argument("--shake", type=int, default=1, choices=range(0, 4))
    ap.add_argument("--grain", type=int, default=6)
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    if not Path(args.clip).exists():
        fail(f"file not found: {args.clip}")

    info = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "json", args.clip], capture_output=True, text=True, check=True).stdout)
    w, h = info["streams"][0]["width"], info["streams"][0]["height"]
    a = SHAKE_PX[args.shake]
    # Two slow sine waves per axis at unrelated rates read as a hand, not a machine.
    x = f"(in_w-{w})/2+{a}*sin(2*PI*t*0.37)+{a / 2}*sin(2*PI*t*1.13)"
    y = f"(in_h-{h})/2+{a}*sin(2*PI*t*0.29+1)+{a / 2}*sin(2*PI*t*0.91)"
    chain = [
        f"scale=iw*1.06:ih*1.06",
        f"crop={w}:{h}:'{x}':'{y}'",
        "eq=brightness='0.012*sin(2*PI*t*0.5)':eval=frame",
    ]
    if args.grain:
        chain.append(f"noise=alls={args.grain}:allf=t")
    out = args.out or str(Path(args.clip).with_name(f"{Path(args.clip).stem}_phone.mp4"))
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", args.clip, "-vf", ",".join(chain),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "copy", out],
        check=True,
    )
    print(f"wrote {out} ({w}x{h}, shake {args.shake}, grain {args.grain})")


if __name__ == "__main__":
    main()
