#!/usr/bin/env python3
"""Build every shot prompt from the lock, for every tool.

    python scripts/assemble.py examples/sunpeel/storyboard.yml --check
    python scripts/assemble.py examples/sunpeel/storyboard.yml -o prompts.md
    python scripts/assemble.py <storyboard> --tools higgsfield kling

Keyframe prompt  = STYLE + [SHOT] + WORLD + FORM + LIGHT + GRADE + PALETTE + TECH + FRAME
Motion prompt    = [ACTION] + CAMERA MOVE + MOTION + "hold the start frame's look"

The keyframe carries the look. The motion prompt only says what moves,
so an image-to-video model does not fight the frame it was given.
"""

import argparse
from pathlib import Path
import sys

from common import (
    HEX_RE, TOKEN_ORDER, load_specs, load_storyboard, load_tools,
    parse_aspect, safe_union,
)

HOOK_MAX_S = 2.0


# ---------- pre-checks (stage 3 gate: the machine checks before a person does)

def check(board, lock, specs, tools):
    errors, warnings = [], []
    ad, shots = board["ad"], board["shots"]
    platforms = specs["platforms"]

    for key in TOKEN_ORDER:
        if not lock["tokens"].get(key):
            errors.append(f"lock token {key} is empty and the mode has no default")

    palette = lock.get("palette") or []
    for colour in palette:
        if not HEX_RE.match(str(colour.get("hex", ""))):
            errors.append(f"palette colour '{colour.get('name')}' has an invalid hex: {colour.get('hex')}")
    if not 4 <= len(palette) <= 8:
        warnings.append(f"palette has {len(palette)} colours; 4 to 8 keeps a lock tight")

    for pid in ad.get("platforms", []):
        if pid not in platforms:
            errors.append(f"unknown platform '{pid}'. Options: {', '.join(platforms)}")
            continue
        spec = platforms[pid]
        if ad["length_s"] > spec["duration_s"]["max"]:
            errors.append(f"{pid}: {ad['length_s']}s is over the {spec['duration_s']['max']}s maximum")
        if ad["master_aspect"] not in spec["aspects"]:
            warnings.append(f"{pid}: needs {spec['master_aspect']}; reframe from the {ad['master_aspect']} master")

    for name in ad.get("tools", []):
        if name not in tools:
            errors.append(f"unknown tool '{name}'. Add it to adapters/tools.yml")

    total = sum(float(s.get("duration_s", 0)) for s in shots)
    if abs(total - float(ad["length_s"])) > 0.5:
        warnings.append(f"shots add up to {total:g}s, the ad is {ad['length_s']}s")

    if shots[0].get("beat") != "hook":
        errors.append("the first shot must be the hook")
    elif float(shots[0].get("duration_s", 0)) > HOOK_MAX_S + 1:
        warnings.append(f"hook shot is {shots[0]['duration_s']}s; the hook has to land inside {HOOK_MAX_S:g}s")
    if not any(s.get("beat") == "end-card" for s in shots):
        warnings.append("no end-card shot")

    max_words = (lock.get("type") or {}).get("max_words_per_super", 6)
    seen = set()
    for s in shots:
        if s["id"] in seen:
            errors.append(f"duplicate shot id {s['id']}")
        seen.add(s["id"])
        words = len(str(s.get("super", "")).split())
        if words > max_words:
            warnings.append(f"{s['id']}: super has {words} words, the lock allows {max_words}")
        if s.get("generate", True) and not s.get("subject"):
            errors.append(f"{s['id']}: a generated shot needs a subject")
        if s.get("hero") and not (lock.get("hero") or {}).get("description"):
            errors.append(f"{s['id']}: uses the hero, but the lock has no hero description")

    variants = board.get("variants") or {}
    for kind, allowed in (("hooks", {"id", "super"}), ("ctas", {"id", "text"})):
        for variant in variants.get(kind, []):
            extra = set(variant) - allowed
            if extra:
                errors.append(f"{kind} {variant.get('id')}: unexpected key(s) {sorted(extra)}. "
                              "A line with a comma must be in quotes")
    for variant in variants.get("hooks", []):
        words = len(str(variant.get("super", "")).split())
        if words > max_words:
            warnings.append(f"hook {variant['id']}: {words} words, the lock allows {max_words}")

    return errors, warnings


# ---------- prompt assembly

def frame_line(ad, specs):
    """Composition words for the model, derived from the strictest safe zone."""
    w, h = parse_aspect(ad["master_aspect"])
    shape = "vertical" if h > w else "square" if h == w else "horizontal"
    same_ratio = [p for p in ad["platforms"] if ad["master_aspect"] in specs["platforms"][p]["aspects"]]
    zone = safe_union(specs, same_ratio or ad["platforms"])
    words = f"{shape} {w}:{h} frame, main subject centred"
    if zone["bottom"] >= 20:
        words += ", calm uncluttered lower third"
    if zone["top"] >= 10:
        words += ", open space at the top"
    return words, zone


def keyframe_prompt(shot, lock, frame_words):
    t = lock["tokens"]
    palette = ", ".join(c["name"] for c in lock.get("palette") or [])
    parts = [t["STYLE"], f"[SHOT: {shot['subject']}]"]
    if shot.get("hero"):
        parts.append(f"featuring {lock['hero']['description']}")
    if t.get("WORLD"):
        parts.append(t["WORLD"])
    parts += [t["FORM"], t["LIGHT"], t["GRADE"]]
    if palette:
        parts.append(f"colour palette of {palette}")
    parts += [t["TECH"], frame_words]
    return ". ".join(p.strip().rstrip(".") for p in parts) + "."


def hero_prompt(lock):
    """The hero reference: the product alone on a clean ground, approved before any shot.

    Every hero shot attaches this image, which is what keeps the product
    on-model from shot to shot and from tool to tool.
    """
    t = lock["tokens"]
    parts = [
        t["STYLE"],
        f"[HERO: {lock['hero']['description']}]",
        t["FORM"], t["LIGHT"], t["GRADE"], t["TECH"],
        "product reference shot, centred, whole product in frame, three-quarter view, "
        "clean neutral soft-gradient background for easy cutout",
    ]
    return ". ".join(p.strip().rstrip(".") for p in parts) + "."


def motion_prompt(shot, lock):
    t = lock["tokens"]
    action = shot.get("action") or "subtle ambient motion"
    move = shot.get("camera_move") or "static camera"
    keep = "the hero" if shot.get("hero") else "the subject"
    parts = [
        action,
        f"Camera: {move}",
        t["MOTION"],
        f"Keep the look, colours and {keep} exactly as in the start frame",
    ]
    return ". ".join(p.strip().rstrip(".") for p in parts) + "."


def for_tool(prompt, tool, negatives, aspect, motion=False):
    """Rewrite one master prompt into a tool's own form. Returns (prompt, extra_lines).

    Motion prompts skip the aspect ratio: image-to-video takes it from the start frame.
    """
    extra = []
    kind = "video" if motion else "image"
    neg_mode = tool.get(f"negative_{kind}", tool.get("negative", "inline"))
    if negatives and neg_mode == "inline":
        prompt += " Keep it clean: no " + ", no ".join(negatives) + "."
    elif negatives and neg_mode == "field":
        extra.append("Negative field: " + ", ".join(negatives))
    elif negatives and neg_mode == "param":
        prompt += " " + tool["negative_param"].format(items=", ".join(negatives))

    if motion:
        extra.append(f"Start frame: the kept keyframe ({aspect}); the clip inherits its aspect ratio")
    elif tool.get("aspect") == "param":
        w, h = parse_aspect(aspect)
        prompt += " " + tool["aspect_param"].format(w=w, h=h)
    elif tool.get("aspect") == "ui":
        extra.append(f"Set aspect ratio in the tool: {aspect}")
    if tool.get("extra_params") and not motion:
        prompt += " " + tool["extra_params"]
    return prompt, extra


def render_group(label, results):
    """One block per distinct prompt, so tools that share a prompt share a block."""
    groups = {}
    for name, text, extra in results:
        groups.setdefault((text, tuple(extra)), []).append(name)
    out = []
    for (text, extra), names in groups.items():
        out += [f"**{label} · {' · '.join(names)}**", "", "```", text, "```"]
        out += [f"- {e}" for e in extra] + [""]
    return out


DEFAULT_CANDIDATES = {"keyframe": 8, "motion": 3}


def budget(board, lock, tools, tool_names):
    """Credits for one full round of stage 4 and 5, per tool that lists its models.

    Shown before the stage 4 gate, so the spend is approved before it happens.
    """
    cands = {**DEFAULT_CANDIDATES, **(board["ad"].get("candidates") or {})}
    shots = [s for s in board["shots"] if s.get("generate", True)]
    hero = 1 if any(s.get("hero") for s in shots) else 0
    rows = []
    for name in tool_names:
        models = tools[name].get("models") or {}
        img, vid = models.get("image"), models.get("video")
        if not (img or vid):
            continue
        key_n = (len(shots) + hero) * cands["keyframe"]
        mot_n = len(shots) * cands["motion"] if lock["_mode"].get("keyframe_first") else 0
        key_c = key_n * img["credits"] if img else None
        mot_c = mot_n * vid["credits"] if vid else None
        total = (key_c or 0) + (mot_c or 0)
        rows.append(
            f"| {name} | {key_n} × {img['name']} ≈ {key_c:g} | " if img else f"| {name} | n/a | "
        )
        rows[-1] += (f"{mot_n} × {vid['name']} ≈ {mot_c:g} | " if vid else "n/a | ")
        rows[-1] += f"**{total:g}** {tools[name].get('cost_unit', 'credits')} |"
    if not rows:
        return []
    return [
        "## Budget · one round of stages 4 and 5",
        "",
        f"{len(shots)} generated shots{' + the hero reference' if hero else ''}, "
        f"{cands['keyframe']} keyframe candidates each, {cands['motion']} motion candidates per kept frame. "
        "Prices are the quotes at `last_checked` in `adapters/tools.yml`; the tool quotes the real cost "
        "before each run, and nothing runs without approval.",
        "",
        "| Tool | Keyframes | Motion | Total |",
        "|---|---|---|---|",
        *rows,
        "",
    ]


def build(board, lock, specs, tools, tool_names):
    ad, meta = board["ad"], lock["meta"]
    frame_words, zone = frame_line(ad, specs)
    negatives = lock["negative"]
    aspect = ad["master_aspect"]
    image_tools = [n for n in tool_names if "image" in tools[n]["role"] or tools[n]["role"] == "any"]
    video_tools = [n for n in tool_names if "video" in tools[n]["role"] or tools[n]["role"] == "any"]

    out = [
        f"# Prompts · {ad['id']}",
        "",
        f"Built from `{lock['_path'].name}` **v{meta['version']}** · mode `{meta['mode']}` · "
        f"master {aspect} · {ad['length_s']}s · platforms: {', '.join(ad['platforms'])}",
        "",
        "Generated by `scripts/assemble.py`. Do not edit prompts here: change the lock or the "
        "storyboard and rebuild, so every prompt stays traceable to a lock version.",
        "",
        f"**Safe zone for the {aspect} master** (strictest across platforms): "
        f"top {zone['top']:g}% · bottom {zone['bottom']:g}% · left {zone['left']:g}% · right {zone['right']:g}%. "
        "Keep text, logo, product and faces inside it.",
        "",
        "**Palette:** " + " · ".join(f"{c['name']} `{c['hex']}`" for c in lock.get("palette") or []),
        "",
    ]
    if lock["_mode"].get("keyframe_first"):
        out += ["**Order:** keyframe first. Pick 1 of 8 to 12, log every verdict, then animate "
                "only the kept frame.", ""]
    else:
        out += ["**Order:** this mode builds layouts by hand. Generated prompts below are for "
                "textures and backgrounds only.", ""]

    out += budget(board, lock, tools, tool_names)

    if any(s.get("hero") and s.get("generate", True) for s in board["shots"]):
        hero = hero_prompt(lock)
        out += ["## H0 · hero reference · first", "",
                "Generate and approve this before any shot. The kept image becomes `hero.reference` "
                "in the lock and is attached to every hero shot.", ""]
        out += render_group("H0-K · hero", [(n, *for_tool(hero, tools[n], negatives, aspect)) for n in image_tools])

    for shot in board["shots"]:
        out += [f"## {shot['id']} · {shot.get('beat', '')} · {shot.get('duration_s', '?')}s", ""]
        rows = [("Super", shot.get("super")), ("Sound", shot.get("sound")),
                ("VO", shot.get("vo")), ("Hero ref", lock["hero"].get("reference") if shot.get("hero") else None)]
        out += [f"- **{k}:** {v}" for k, v in rows if v]
        out.append("")
        if not shot.get("generate", True):
            out += ["_Built by hand in the edit. Nothing to generate._", ""]
            continue

        key = keyframe_prompt(shot, lock, frame_words)
        mov = motion_prompt(shot, lock)
        keyframes = [(name, *for_tool(key, tools[name], negatives, aspect)) for name in image_tools]
        motions = []
        for name in video_tools:
            base = mov if tools[name].get("motion_prompt") else key + " " + mov
            text, extra = for_tool(base, tools[name], negatives, aspect, motion=True)
            clip = tools[name].get("clip_s")
            if clip:
                options = " or ".join(str(c) for c in clip) if isinstance(clip, list) else clip
                extra.append(f"Generate {options}s, trim to {shot.get('duration_s')}s in the edit")
            motions.append((name, text, extra))
        out += render_group(f"{shot['id']}-K · keyframe", keyframes)
        out += render_group(f"{shot['id']}-M · motion", motions)

    return "\n".join(out).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("storyboard")
    ap.add_argument("--check", action="store_true", help="run the pre-checks only")
    ap.add_argument("--tools", nargs="+", help="override the storyboard's tool list")
    ap.add_argument("-o", "--out", help="write prompts to this file (default: stdout)")
    args = ap.parse_args()

    board, lock = load_storyboard(args.storyboard)
    specs, tools = load_specs(), load_tools()
    if args.tools:
        board["ad"]["tools"] = args.tools

    errors, warnings = check(board, lock, specs, tools)
    for w in warnings:
        print(f"WARN  {w}", file=sys.stderr)
    for e in errors:
        print(f"FAIL  {e}", file=sys.stderr)
    if errors:
        sys.exit(1)
    if args.check:
        print(f"PASS  {board['ad']['id']}: lock v{lock['meta']['version']}, "
              f"{len(board['shots'])} shots, {len(warnings)} warnings", file=sys.stderr)
        return

    tool_names = board["ad"].get("tools") or ["generic"]
    text = build(board, lock, specs, tools, tool_names)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
