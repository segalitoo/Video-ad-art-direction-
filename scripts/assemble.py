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
import math
import re
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

    e, w = check_statics(board, lock, specs)
    errors += e
    warnings += w
    warnings += lint(board, lock)
    return errors, warnings


def check_statics(board, lock, specs):
    errors, warnings = [], []
    rules = specs.get("static_text", {})
    seen = set()
    for st in board.get("statics") or []:
        sid = st.get("id", "?")
        if sid in seen:
            errors.append(f"duplicate static id {sid}")
        seen.add(sid)
        for key in ("subject", "headline", "plates", "platforms"):
            if not st.get(key):
                errors.append(f"static {sid}: missing {key}")
        if st.get("copy_space") not in ("top", "bottom"):
            errors.append(f"static {sid}: copy_space must be top or bottom")
        for ratio in st.get("plates") or []:
            try:
                parse_aspect(ratio)
            except ValueError:
                errors.append(f"static {sid}: plate ratio '{ratio}' is not like 4:5")
        for pid in st.get("platforms") or []:
            if pid not in specs["platforms"]:
                errors.append(f"static {sid}: unknown platform '{pid}'")
            elif not specs["platforms"][pid].get("static"):
                errors.append(f"static {sid}: {pid} does not run static ads")
        head = str(st.get("headline", ""))
        if len(head.split()) > rules.get("max_headline_words", 99):
            warnings.append(f"static {sid}: headline has {len(head.split())} words; keep to {rules['max_headline_words']}")
        if len(head) > rules.get("max_headline_chars", 999):
            warnings.append(f"static {sid}: headline is {len(head)} characters; keep under {rules['max_headline_chars']}")
        if st.get("hero") and not (lock.get("hero") or {}).get("description"):
            errors.append(f"static {sid}: uses the hero, but the lock has no hero description")
    return errors, warnings


# ---------- prompt lint: what makes generators fail, caught before any spend

# A keyframe is one frozen frame. Movement words in its subject get drawn as blur
# or ignored, and the motion prompt then has nothing clear to start from.
# Only words that are almost always a movement. Words that are just as often a noun
# or an adjective ("in turn", "a springy bounce", "pops open") are left out on purpose.
MOTION_VERBS = [
    "spin", "drop", "fall", "burst", "re-form", "reform", "pop", "fly", "run", "jump", "move",
    "spray", "hop", "sway", "roll", "unzip", "pour", "splash", "land", "dip", "drift", "rise",
    "shake", "twist", "slide", "glide", "fold", "melt", "explode", "swirl", "zoom", "tilt", "drip",
]


def _forms(verb):
    """drop -> drop, drops, dropped, dropping; rise -> rises, rising, rose; fly -> flies."""
    forms = {verb, verb + "s", verb + "es", verb + "ed", verb + "ing"}
    if verb.endswith("e"):
        forms |= {verb[:-1] + "ing", verb + "d"}
    if verb.endswith("y"):
        forms |= {verb[:-1] + "ies", verb[:-1] + "ied"}
    if len(verb) > 2 and verb[-1] not in "aeiouywx" and verb[-2] in "aeiou" and verb[-3] not in "aeiou":
        forms |= {verb + verb[-1] + "ing", verb + verb[-1] + "ed"}
    return forms


MOTION_FORMS = {f: v for v in MOTION_VERBS for f in _forms(v)} | {"rose": "rise", "flew": "fly", "fell": "fall"}


def _motion_words(text):
    return [w for w in re.findall(r"[a-z]+(?:-[a-z]+)?", str(text).lower()) if w in MOTION_FORMS]


MAX_EVENTS_PER_CLIP = 2
MAX_SCENE_COLOURS = 6


def _events(action):
    """How many separate movements one action line asks for, counted by movement verbs."""
    return len(_motion_words(action))


def lint(board, lock):
    out = []
    brand = str(lock.get("meta", {}).get("brand", "")).strip()
    hero = lock.get("hero") or {}
    bans_text = any("text" in n.lower() for n in lock["negative"] + lock["negative_image"])

    if brand and brand.lower() in str(hero.get("description", "")).lower() and bans_text and not hero.get("wordmark"):
        out.append(f'hero: "{brand}" in the description while text is banned. The model may print it anyway '
                   f'or leave the can blank. Describe the label graphically and set hero.wordmark if the name '
                   f'must appear')

    if lock.get("meta", {}).get("people") is False:
        for key, value in lock["tokens"].items():
            found = [b for b in ("skin", "face", "hand", "finger", "person", "people") if b in str(value).lower()]
            if found:
                out.append(f"tokens: {key} mentions {', '.join(found)} but the lock has people: false; "
                           f"override {key} in the lock")

    for n in lock["negative"] + lock["negative_image"] + lock["negative_video"]:
        if re.search(r"\b(in|on|during|when|except|only) the\b.*\b(shots?|scenes?|frames?)\b", n.lower()):
            out.append(f'negative "{n}" is conditional; models cannot follow conditions. Put it in the '
                       f"shot's own description instead")

    colours = [c for c in lock.get("palette") or [] if not str(c.get("role", "")).startswith("type")]
    if len(colours) > MAX_SCENE_COLOURS:
        out.append(f"palette: {len(colours)} scene colours in every prompt; image models follow 3 to 6. "
                   f"Mark extra colours as role: type or background-only")

    seen = {}
    for key, value in lock["tokens"].items():
        for phrase in str(value or "").split(","):
            ph = phrase.strip().lower()
            if len(ph.split()) >= 2:
                if ph in seen and seen[ph] != key:
                    out.append(f'tokens: "{ph}" is in both {seen[ph]} and {key}; say it once')
                seen.setdefault(ph, key)

    for st in board.get("statics") or []:
        moving = sorted(set(_motion_words(st.get("subject", ""))))
        if moving:
            out.append(f"static {st.get('id')}: subject has movement ({', '.join(moving)}); a static is one frozen frame")

    for shot in board["shots"]:
        if not shot.get("generate", True):
            continue
        sid = shot["id"]
        moving = sorted(set(_motion_words(f"{shot.get('subject', '')} {shot.get('end_subject', '')}")))
        if moving:
            out.append(f"{sid}: subject has movement ({', '.join(moving)}). A keyframe is one frozen frame: "
                       f"describe the first frame, put the movement in `action`")
        n = _events(str(shot.get("action", "")))
        if n > MAX_EVENTS_PER_CLIP:
            out.append(f"{sid}: action has {n} separate events for a {shot.get('duration_s')}s shot; "
                       f"clips this short land 1 or 2 cleanly")
        if "music" in str(shot.get("sound", "")).lower() and not shot.get("sfx"):
            out.append(f"{sid}: sound is a music cue and there is no sfx line; the clip will be generated "
                       f"without sound effects. Add `sfx:` for what the viewer should hear")
        ref = hero.get("reference")
        if shot.get("hero") and not (ref and (lock["_path"].parent / ref).exists()):
            out.append(f"{sid}: hero shot, but the hero reference ({ref or 'not set'}) does not exist yet. "
                       f"Generate and approve H0 first")
    return out


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


def scene_palette(lock):
    """Colours the scene is painted with. Colours reserved for type are set in the edit, not generated."""
    return ", ".join(c["name"] for c in lock.get("palette") or []
                     if not str(c.get("role", "")).startswith("type"))


def hero_words(lock):
    hero = lock["hero"]
    words = hero["description"]
    if hero.get("wordmark"):
        words += f', with the wordmark "{hero["wordmark"]}" printed cleanly on it'
    return words


def negatives_for(lock, kind):
    """Negatives for a still ("image") or a clip ("video").

    Stills get the full list. Clips get a short one: the lock's own negatives, the
    motion-only ones and the text rule. Video models tend to draw what a long list
    names, and the start frame already carries everything a still negative protects.
    A mode negative is dropped when the lock already bans the same thing ("deformed
    hands" under "human hands"), and the wordmark is carved out of the text ban.
    """
    own = lock["_own_negative"]
    if kind == "video":
        text_rules = [n for n in lock["negative"] if "text" in n.lower() or "letters" in n.lower()]
        items = text_rules[:1] + own + lock["negative_video"]
    else:
        items = lock["negative"] + lock["negative_image"]
    if lock.get("meta", {}).get("people") is False:
        # Product-only ads: naming body parts in a negative can invite them. One rule replaces them all.
        body = ("skin", "face", "finger", "hand", "teeth", "eye", "people", "person")
        items = [n for n in items if not any(b in n.lower() for b in body)] + ["people or body parts"]
    own_heads = {n.split()[-1].lower() for n in own}
    items = [n for n in items if n in own or n.split()[-1].lower() not in own_heads]
    mark = (lock.get("hero") or {}).get("wordmark")
    if mark:
        items = [f"text other than the {mark} wordmark" if "text" in n.lower() else n for n in items]
    seen, out = set(), []
    for n in items:
        if n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


def keyframe_prompt(shot, lock, frame_words):
    t = lock["tokens"]
    palette = scene_palette(lock)
    parts = [t["STYLE"], f"[SHOT: {shot['subject']}]"]
    if shot.get("hero"):
        parts.append(f"featuring {hero_words(lock)}")
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
        f"[HERO: {hero_words(lock)}]",
        t["FORM"], t["LIGHT"], t["GRADE"], t["TECH"],
        "product reference shot, centred, whole product in frame, three-quarter view, "
        "clean neutral soft-gradient background for easy cutout",
    ]
    return ". ".join(p.strip().rstrip(".") for p in parts) + "."


def static_prompt(item, lock, ratio):
    """A plate for a static ad: the image with an empty band where the headline will be set."""
    t = lock["tokens"]
    w, h = parse_aspect(ratio)
    shape = "vertical" if h > w else "square" if h == w else "horizontal"
    copy = item.get("copy_space", "top")
    parts = [t["STYLE"], f"[STATIC: {item['subject']}]"]
    if item.get("hero"):
        parts.append(f"featuring {hero_words(lock)}")
    if t.get("WORLD"):
        parts.append(t["WORLD"])
    parts += [t["FORM"], t["LIGHT"], t["GRADE"]]
    palette = scene_palette(lock)
    if palette:
        parts.append(f"colour palette of {palette}")
    if h / w > 1.5 or copy == "top":
        # 9:16 always takes the headline on top: the platform's own UI covers the bottom third.
        layout = ("the subject in the middle of the frame, not too large, the top third left as clean, "
                  "simple, empty background, and a simple uncluttered strip along the bottom edge")
    else:
        layout = ("the subject in the upper middle of the frame, not too large, the bottom third left as "
                  "clean, simple, empty background")
    parts += [t["TECH"], f"{shape} {w}:{h} frame, {layout}"]
    return ". ".join(p.strip().rstrip(".") for p in parts) + "."


def motion_prompt(shot, lock):
    t = lock["tokens"]
    action = shot.get("action") or "subtle ambient motion"
    move = shot.get("camera_move") or "static camera"
    keep = "the hero" if shot.get("hero") else "the subject"
    if shot.get("end_subject"):
        # The subject is meant to change here; only the setting must hold.
        hold = "Move smoothly from the start frame to the end frame; keep the setting, framing and light the same"
    else:
        hold = f"Keep the look, colours and {keep} exactly as in the start frame"
    parts = [action, f"Camera: {move}", t["MOTION"], hold]
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


DEFAULT_CANDIDATES = {"keyframe": 8, "motion": 3, "static": 4}


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
        ends = sum(1 for s in shots if s.get("end_subject"))
        key_n = (len(shots) + hero + ends) * cands["keyframe"]
        mot_n = len(shots) * cands["motion"] if lock["_mode"].get("keyframe_first") else 0
        key_c = key_n * img["credits"] if img else None
        mot_c = None
        if vid and "credits_per_s" in vid:
            # Priced by the second: each shot is generated at its own length, never under the minimum.
            secs = sum(max(vid.get("min_s", 0), math.ceil(float(s.get("duration_s", 0)))) for s in shots)
            mot_c = secs * vid["credits_per_s"] * (cands["motion"] if mot_n else 0)
        elif vid:
            mot_c = mot_n * vid["credits"]
        st_n = sum(len(st.get("plates") or []) for st in board.get("statics") or []) * cands["static"]
        st_c = st_n * img["credits"] if img else None
        total = (key_c or 0) + (mot_c or 0) + (st_c or 0)
        rows.append(
            f"| {name} | {key_n} × {img['name']} ≈ {key_c:g} | " if img else f"| {name} | n/a | "
        )
        rows[-1] += (f"{mot_n} × {vid['name']} ≈ {mot_c:g} | " if vid else "n/a | ")
        rows[-1] += (f"{st_n} × {img['name']} ≈ {st_c:g} | " if img and st_n else "0 | ")
        rows[-1] += f"**{total:g}** {tools[name].get('cost_unit', 'credits')} |"
        usd = tools[name].get("usd_per_credit")
        rows[-1] += f" ≈ ${total * usd:,.0f} |" if usd else " n/a |"
    if not rows:
        return []
    return [
        "## Budget · one round of stages 4 and 5, plus static plates",
        "",
        f"{len(shots)} generated shots{' + the hero reference' if hero else ''}, "
        f"{cands['keyframe']} keyframe candidates each, {cands['motion']} motion candidates per kept frame. "
        "Prices are the quotes at `last_checked` in `adapters/tools.yml`; the tool quotes the real cost "
        "before each run, and nothing runs without approval. USD uses `usd_per_credit` (the plan "
        "noted beside it); a Weave credit and a Higgsfield credit are not the same money.",
        "",
        "| Tool | Keyframes | Motion | Static plates | Total | USD |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
    ]


def build(board, lock, specs, tools, tool_names):
    ad, meta = board["ad"], lock["meta"]
    frame_words, zone = frame_line(ad, specs)
    neg_image, neg_video = negatives_for(lock, "image"), negatives_for(lock, "video")
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
        out += render_group("H0-K · hero", [(n, *for_tool(hero, tools[n], neg_image, aspect)) for n in image_tools])

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
        keyframes = [(name, *for_tool(key, tools[name], neg_image, aspect)) for name in image_tools]
        motions = []
        for name in video_tools:
            base = mov if tools[name].get("motion_prompt") else key + " " + mov
            sfx = shot.get("sfx") or ("" if "music" in str(shot.get("sound", "")).lower() else shot.get("sound"))
            if tools[name].get("audio_native") and sfx:
                # Native-audio models make SFX from the prompt; music always comes from stage 6.
                base += f" Sound effects only: {sfx}. No music, no voice."
            text, extra = for_tool(base, tools[name], neg_video, aspect, motion=True)
            clip, span = tools[name].get("clip_s"), tools[name].get("clip_range")
            if span:
                gen = max(span[0], math.ceil(float(shot.get("duration_s", span[0]))))
                extra.append(f"Generate {gen}s (allowed {span[0]}-{span[1]}s), trim to {shot.get('duration_s')}s in the edit")
            elif clip:
                options = " or ".join(str(c) for c in clip) if isinstance(clip, list) else clip
                extra.append(f"Generate {options}s, trim to {shot.get('duration_s')}s in the edit")
            if shot.get("hero") and tools[name].get("hero_reference"):
                extra.append("Attach the hero reference as an extra reference image, next to the start frame")
            if shot.get("end_subject"):
                extra.append(f"Last frame: the kept {shot['id']}-K-end keyframe (role end_image); the model fills the change between")
            motions.append((name, text, extra))
        out += render_group(f"{shot['id']}-K · keyframe", keyframes)
        if shot.get("end_subject"):
            # First + last frame: the model interpolates between two approved stills, which keeps a
            # change of state (droopy -> lush, closed -> open) from melting into something else.
            end = keyframe_prompt({**shot, "subject": shot["end_subject"]}, lock, frame_words)
            out += render_group(f"{shot['id']}-K-end · last frame",
                                [(n, *for_tool(end, tools[n], neg_image, aspect)) for n in image_tools])
        out += render_group(f"{shot['id']}-M · motion", motions)

    statics = board.get("statics") or []
    if statics:
        out += ["## Static ads", "",
                "Plates only: the headline band is left empty on purpose. Type, CTA and wordmark are set by "
                "`scripts/static_compose.py` from the kept plate, never generated.", ""]
        for st in statics:
            out += [f"### {st['id']} · {st.get('concept', '')}", "",
                    f"- **Headline ({st.get('copy_space')}):** {st.get('headline')}",
                    f"- **CTA:** {st.get('cta', '')}",
                    f"- **Platforms:** {', '.join(st.get('platforms') or [])}", ""]
            for ratio in st.get("plates") or []:
                prompt = static_prompt(st, lock, ratio)
                out += render_group(f"{st['id']}-{ratio} · static plate",
                                    [(n, *for_tool(prompt, tools[n], neg_image, ratio)) for n in image_tools])

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
