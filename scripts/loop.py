#!/usr/bin/env python3
"""Turn a winning static into a short motion loop, with the type kept sharp.

A static that moves catches the eye in a static-heavy feed, but models warp text. So the type
never goes through the video model: static_render.py --layers splits the ad into a plate (no type)
and a transparent type layer; only the plate moves; the type is laid back on top, pixel for pixel.

    python scripts/static_render.py layout.yml -o out --layers                  # F1_plate.png + F1_type.png
    python scripts/loop.py prompt --move float                                 # the motion prompt for the plate
    python scripts/loop.py make --still out/F1_plate.png --move push --type out/F1_type.png -o F1_loop.mp4   # free
    python scripts/loop.py make --clip plate_seedance.mp4 --type out/F1_type.png -o F1_loop.mp4              # paid clip

Free (`--still`): a slow camera move made locally from the plate, no model, no cost.
Paid (`--clip`): animate the plate with an image-to-video model (Seedance on the Higgsfield route;
quote and approve first) using `prompt`, then `make` fits the clip to the frame, plays it forward
and back so the loop has no jump, and lays the type layer over it.

Animate selectively: product and lifestyle statics usually gain from motion; stat and chart
statics often read better still. Test both, the way the matrix tests hooks.
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image

from common import fail

MOVES = {
    "push": "a very slow push-in toward the product, about 3% over the clip",
    "float": "the product floats gently up and down by a few pixels, a soft slow bob",
    "parallax": "a slight parallax: the background drifts a little slower than the product",
    "ambient": "only ambient motion in the background (light shifting, a soft breeze); the product stays still",
}
KEEP = ("Keep the composition, the framing and every colour exactly as the start frame. "
        "No new objects, no text, no letters, no logos appear. Smooth, calm, not a screensaver; "
        "the motion must be subtle enough to loop.")


def cmd_prompt(a):
    print(f"{MOVES[a.move][0].upper()}{MOVES[a.move][1:]}. {KEEP}")
    print(f"\nDuration {a.seconds / 2:g}s (played forward then back = a {a.seconds:g}s loop), aspect as the plate, no audio.")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        fail(f"ffmpeg failed: {r.stderr.strip()[-400:]}")


def cmd_make(a):
    if not shutil.which("ffmpeg"):
        fail("ffmpeg is missing")
    if bool(a.still) == bool(a.clip):
        fail("give --still (free, local move) or --clip (an animated plate), not both")
    t = Image.open(a.type)
    if t.mode != "RGBA":
        fail(f"{a.type} is not a transparent type layer; make it with static_render.py --layers")
    W, H = t.size
    fps, half = 30, a.seconds / 2
    frames = round(half * fps)
    with tempfile.TemporaryDirectory() as tmp:
        fwd = Path(tmp) / "fwd.mp4"
        if a.still:
            z = {"push": "1+0.03*on/{n}", "float": "1.015", "parallax": "1+0.02*on/{n}", "ambient": "1.01"}[a.move].format(n=frames)
            yexp = "ih/2-(ih/zoom/2)" + ("+6*sin(2*PI*on/{n})".format(n=frames) if a.move == "float" else "")
            xexp = "iw/2-(iw/zoom/2)" + ("+10*on/{n}".format(n=frames) if a.move == "parallax" else "")
            vf = (f"scale={W * 2}:{H * 2},zoompan=z='{z}':x='{xexp}':y='{yexp}':d={frames}:s={W}x{H}:fps={fps},"
                  "format=yuv420p")
            run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", a.still, "-vf", vf, "-frames:v", str(frames), str(fwd)])
        else:
            vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},format=yuv420p"
            run(["ffmpeg", "-y", "-v", "error", "-i", a.clip, "-t", f"{half}", "-vf", vf, "-an", str(fwd)])
        loop = Path(tmp) / "loop.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-i", str(fwd), "-filter_complex",
             "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0[v]", "-map", "[v]", str(loop)])
        run(["ffmpeg", "-y", "-v", "error", "-i", str(loop), "-i", a.type, "-filter_complex",
             "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]", "-map", "[v]", "-c:v", "libx264",
             "-crf", "18", "-preset", "medium", "-movflags", "+faststart", "-an", a.out])
    print(f"wrote {a.out}  {W}x{H}, {a.seconds:g}s loop (forward and back), type layer on top")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prompt")
    p.add_argument("--move", choices=sorted(MOVES), default="float")
    p.add_argument("--seconds", type=float, default=6)
    m = sub.add_parser("make")
    m.add_argument("--still", help="the plate PNG, for a free local move")
    m.add_argument("--clip", help="the plate animated by an image-to-video model")
    m.add_argument("--move", choices=sorted(MOVES), default="push")
    m.add_argument("--type", required=True, help="the transparent type layer from static_render.py --layers")
    m.add_argument("--seconds", type=float, default=6)
    m.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    {"prompt": cmd_prompt, "make": cmd_make}[a.cmd](a)


if __name__ == "__main__":
    main()
