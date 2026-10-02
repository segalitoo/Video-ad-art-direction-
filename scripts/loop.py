#!/usr/bin/env python3
"""Turn a winning static into a short motion loop, with the type kept sharp.

A static that moves catches the eye in a static-heavy feed, but models warp text. So the type
never goes through the video model: static_render.py --layers splits the ad into a plate (no type)
and a transparent type layer; only the plate moves; the type is laid back on top, pixel for pixel.

    python scripts/static_render.py layout.yml -o out --layers                  # F1_plate.png + F1_type.png
    python scripts/loop.py prompt --move float                                 # the motion prompt for the plate
    python scripts/loop.py make --still out/F1_plate.png --move push --type out/F1_type.png -o F1_loop.mp4   # free
    python scripts/loop.py make --clip plate_seedance.mp4 --type out/F1_type.png -o F1_loop.mp4              # paid clip
    python scripts/loop.py make --clip wan.mp4 --layout layout.yml --frame "F6 lifestyle 1080x1920" -o F6_loop.mp4

With --layout and --frame, every clip frame is put through the ad's own layout instead of a centre
crop: the plate's focus and zoom, any fade and the type are applied as in the approved static. Use it
when the clip was made from the full source image (e.g. a 3:4 keyframe) rather than the cropped plate.

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
    if a.layout:
        if not (a.clip and a.frame):
            fail("--layout needs --clip and --frame")
        return make_through_layout(a)
    if not a.type:
        fail("give --type (the type layer), or --layout and --frame")
    t = Image.open(a.type)
    if t.mode != "RGBA":
        fail(f"{a.type} is not a transparent type layer; make it with static_render.py --layers")
    W, H = t.size
    if a.clip:
        clip_s = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.clip],
                                      capture_output=True, text=True, check=True).stdout.strip())
        if a.seconds is None:                       # use the whole clip: its forward half is the full clip
            a.seconds = round(2 * clip_s, 2)
        elif a.seconds / 2 < clip_s - 0.1:
            print(f"note: the clip is {clip_s:g}s; only its first {a.seconds / 2:g}s are used (leave out --seconds to use all of it)")
    elif a.seconds is None:
        a.seconds = 6
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


def make_through_layout(a):
    """Each clip frame replaces the plate image of one layout frame and is rendered with the rest of the
    ad (crop, fades, type), so the loop matches the approved static exactly."""
    import yaml
    from static_render import Ctx, render_frame
    lay_path = Path(a.layout).resolve()
    layout = yaml.safe_load(lay_path.read_text(encoding="utf-8"))
    fr = next((f for f in layout["frames"] if a.frame in f.get("name", "")), None)
    if not fr:
        fail(f"no frame named like '{a.frame}' in {a.layout}")
    W, H = fr["w"], fr["h"]
    plate = next((it for it in fr["items"] if it.get("type") == "image" and it.get("fit") != "contain"
                  and it.get("w") == W and it.get("h") == H), None)
    if not plate:
        fail(f"'{fr['name']}' has no full-frame plate image to animate")
    ctx = Ctx(layout, lay_path.parent)
    src = Image.open(ctx.base / plate["src"])
    clip_wh = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                              "-of", "csv=p=0", a.clip], capture_output=True, text=True, check=True).stdout.strip()
    cw, ch = (int(v) for v in clip_wh.split(",")[:2])
    if abs(cw / ch - src.width / src.height) > 0.03:
        print(f"note: the clip is {cw}x{ch} but the plate source is {src.width}x{src.height}; the crop will not match the static")
    up = max(W / cw, H / ch) * max(1.0, plate.get("zoom", 1.0))
    if up > 1.5:
        print(f"note: the clip is {cw}x{ch}; the frame enlarges it {up:.1f}x, so it will look softer than the type (upscale the clip first)")
    clip_s = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.clip],
                                  capture_output=True, text=True, check=True).stdout.strip())
    half = clip_s if a.seconds is None else min(clip_s, a.seconds / 2)
    fps = 30
    with tempfile.TemporaryDirectory() as tmp:
        raw, seq = Path(tmp) / "raw", Path(tmp) / "seq"
        raw.mkdir()
        seq.mkdir()
        run(["ffmpeg", "-y", "-v", "error", "-i", a.clip, "-t", f"{half}", "-vf", f"fps={fps}", str(raw / "%05d.png")])
        frames = sorted(raw.glob("*.png"))
        for i, f in enumerate(frames):
            plate["src"] = str(f)
            render_frame(fr, ctx).save(seq / f"{i:05d}.png")
        fwd, loop = Path(tmp) / "fwd.mp4", Path(tmp) / "loop.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-framerate", str(fps), "-i", str(seq / "%05d.png"), "-pix_fmt", "yuv420p",
             "-c:v", "libx264", "-crf", "12", str(fwd)])
        run(["ffmpeg", "-y", "-v", "error", "-i", str(fwd), "-filter_complex",
             "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,format=yuv420p[v]", "-map", "[v]", "-c:v", "libx264",
             "-crf", "18", "-preset", "medium", "-movflags", "+faststart", "-an", a.out])
    print(f"wrote {a.out}  {W}x{H}, {2 * len(frames) / fps:g}s loop (forward and back), rendered through '{fr['name']}'")


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
    m.add_argument("--type", help="the transparent type layer from static_render.py --layers")
    m.add_argument("--layout", help="with --clip: render each clip frame through this layout file's --frame")
    m.add_argument("--frame", help="with --layout: the frame name (or part of it), e.g. 'B06 lifestyle 1080x1920'")
    m.add_argument("--seconds", type=float, default=None,
                   help="loop length; default 6 for --still, twice the clip length for --clip")
    m.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    {"prompt": cmd_prompt, "make": cmd_make}[a.cmd](a)


if __name__ == "__main__":
    main()
