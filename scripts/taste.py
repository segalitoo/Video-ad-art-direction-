#!/usr/bin/env python3
"""The taste library: good and bad examples that every new creative is compared with.

It grows with every project. References the art director admires go in by hand; creatives
approved at a gate go in as exemplars with the art director's reason; rejected ones go in as
anti-examples with what went wrong. The judge pass and the design review then compare each
new candidate with its nearest neighbours, and `lessons.md` collects the rules learned.

    python scripts/taste.py add ref.jpg --kind exemplar --medium static --tags big-number,paper --why "..." --source "..."
    python scripts/taste.py from-judge judge/r1.yml --keep D1:"reads as dying at once" --reject D3:"two pots stacked"
    python scripts/taste.py nearest candidate.jpg --medium frame --tags paper-craft -k 3 --sheet compare.html
    python scripts/taste.py lesson "Describe what water does inside the pot, never 'flood'" --evidence "fernly S01 clip, judge 54"
    python scripts/taste.py sheet -o taste/library.html

Files live in taste/: library.yml (one entry per example), refs/ (JPEG copies, clips as a
5-frame strip), lessons.md. External references are for internal inspiration only: never
published or used in an ad, always credited in `source`.
"""

import argparse
from datetime import date
import html
import os
from pathlib import Path
import subprocess
import tempfile

from PIL import Image
import yaml

from common import ROOT, fail, load_yaml
from judge import colour_match, embedded, hue_hist, region_labs, structure_match, thumb_gray

TASTE = Path(os.environ.get("TASTE_DIR", ROOT / "taste"))   # override for tests
LIB = TASTE / "library.yml"
REFS = TASTE / "refs"
LESSONS = TASTE / "lessons.md"
MEDIA = ["frame", "clip", "static", "board", "lock", "edit"]
CLIP_EXT = {".mp4", ".mov", ".webm"}


def load_lib():
    return (load_yaml(LIB) or {}).get("entries") or [] if LIB.exists() else []


def save_lib(entries):
    TASTE.mkdir(exist_ok=True)
    with open(LIB, "w", encoding="utf-8") as f:
        f.write("# The taste library. Add with scripts/taste.py; edit `why` and `tags` by hand freely.\n")
        yaml.safe_dump({"entries": entries}, f, sort_keys=False, allow_unicode=True, width=110)


def still_of(path):
    """A still for any file: the image itself, or a 5-frame strip for a clip."""
    path = Path(path)
    if path.suffix.lower() not in CLIP_EXT:
        return Image.open(path).convert("RGB")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(path)], capture_output=True, text=True, check=True).stdout.strip() or 0)
    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(5):
            out = Path(tmp) / f"{i}.png"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{dur * (i + 0.5) / 5:.3f}", "-i", str(path),
                            "-frames:v", "1", str(out)], check=True)
            frames.append(Image.open(out).convert("RGB"))
    w, h = frames[0].size
    tw = 360
    th = round(h * tw / w)
    strip = Image.new("RGB", (tw * 5 + 32, th), "white")
    for i, f in enumerate(frames):
        strip.paste(f.resize((tw, th)), (i * (tw + 8), 0))
    return strip


def features(img):
    return {"gray": thumb_gray(img), "_hist": hue_hist(img), "_cells": region_labs(img)}


def likeness(a, b):
    return 0.5 * structure_match(a["gray"], b["gray"]) + 0.5 * colour_match(a, b)


def add_entry(src, kind, medium, tags, why, source, by):
    if kind not in ("exemplar", "anti"):
        fail("kind is exemplar or anti")
    if medium not in MEDIA:
        fail(f"medium is one of {', '.join(MEDIA)}")
    if not why:
        fail("say why: the reason is what the library learns from")
    entries = load_lib()
    n = 1 + max([int(e["id"][1:]) for e in entries] or [0])
    eid = f"T{n:04d}"
    REFS.mkdir(parents=True, exist_ok=True)
    img = still_of(src)
    if max(img.size) > 1400:
        s = 1400 / max(img.size)
        img = img.resize((round(img.width * s), round(img.height * s)))
    ref = REFS / f"{eid}.jpg"
    img.save(ref, quality=88)
    entry = {"id": eid, "kind": kind, "medium": medium, "file": str(ref.relative_to(TASTE)),
             "original": str(src), "tags": tags, "why": why, "source": source,
             "added": date.today().isoformat(), "by": by}
    entries.append(entry)
    save_lib(entries)
    print(f"added {eid} ({kind}, {medium}): {why}")
    return entry


def cmd_add(args):
    add_entry(args.file, args.kind, args.medium, split_tags(args.tags), args.why, args.source, args.by)


def split_tags(text):
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def cmd_from_judge(args):
    """The art director's gate verdicts, filed with their reasons."""
    data = load_yaml(args.round)
    base = Path(args.round).parent
    for flag, kind in ((args.keep or [], "exemplar"), (args.reject or [], "anti")):
        for spec in flag:
            iid, _, reason = spec.partition(":")
            item = (data.get("items") or {}).get(iid)
            if not item:
                fail(f"{iid} is not in {args.round}")
            score = (data.get("scores") or {}).get(iid) or {}
            why = reason.strip() or score.get("fail") or score.get("note") or ""
            medium = args.medium or {"clip": "clip", "static": "static"}.get(item.get("kind"), "frame")
            add_entry(base / item["file"], kind, medium, split_tags(args.tags), why,
                      f"{data.get('round', Path(args.round).stem)}, {iid}", "art director (gate)")


def cmd_nearest(args):
    entries = [e for e in load_lib() if not args.medium or e["medium"] == args.medium]
    if not entries:
        fail("the library has no entries for this medium yet; add references first")
    cand = still_of(args.file)
    fc = features(cand)
    tags = set(split_tags(args.tags))
    ranked = []
    for e in entries:
        f = features(Image.open(TASTE / e["file"]).convert("RGB"))
        overlap = len(tags & set(e.get("tags") or [])) / len(tags) if tags else 0
        score = 0.6 * overlap * 100 + 0.4 * likeness(fc, f) if tags else likeness(fc, f)
        ranked.append((score, e))
    ranked.sort(key=lambda r: -r[0])
    picks = {k: [r for r in ranked if r[1]["kind"] == k][:args.k] for k in ("exemplar", "anti")}
    for kind, rows in picks.items():
        print(f"{'Closest exemplars' if kind == 'exemplar' else 'Closest anti-examples'}:")
        for s, e in rows:
            print(f"  {e['id']} {s:5.1f}  {TASTE / e['file']}  · {e['why']}")
    if args.sheet:
        cards = [f'<figure class="cand"><img src="{embedded_img(cand)}"><figcaption>candidate · {html.escape(str(args.file))}</figcaption></figure>']
        for kind, rows in picks.items():
            for s, e in rows:
                cards.append(f'<figure class="{kind}"><img src="{embedded(TASTE / e["file"], 420)}"><figcaption>'
                             f'<b>{e["id"]}</b> {kind} · {s:.0f}<br>{html.escape(e["why"])}</figcaption></figure>')
        Path(args.sheet).write_text(page("Taste comparison", "".join(cards)), encoding="utf-8")
        print(f"wrote {args.sheet}")


def embedded_img(img):
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as t:
        img.save(t.name, quality=85)
        return embedded(t.name, 420)


def cmd_lesson(args):
    TASTE.mkdir(exist_ok=True)
    if not LESSONS.exists():
        LESSONS.write_text("# Lessons\n\nRules learned from real results. Each one names its evidence and where "
                           "it is enforced now.\n", encoding="utf-8")
    n = sum(1 for line in LESSONS.read_text(encoding="utf-8").splitlines() if line.startswith("### L")) + 1
    with open(LESSONS, "a", encoding="utf-8") as f:
        f.write(f"\n### L{n:03d} · {args.text}\n- **Evidence:** {args.evidence}\n"
                f"- **Enforced in:** {args.enforced_in or 'the design review'}\n- **Added:** {date.today().isoformat()}\n")
    print(f"added lesson L{n:03d}")


def page(title, body):
    return f"""<title>{html.escape(title)}</title>
<style>
:root{{--bg:#F1F2EF;--card:#FFFFFF;--ink:#1C211B;--muted:#5E665C;--good:#2F7D55;--bad:#B3261E}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--bg:#151814;--card:#1F231E;--ink:#E7EAE4;--muted:#9AA296;--good:#6CC795;--bad:#F2B8B5}}}}
:root[data-theme="dark"]{{color-scheme:dark;--bg:#151814;--card:#1F231E;--ink:#E7EAE4;--muted:#9AA296;--good:#6CC795;--bad:#F2B8B5}}
body{{background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}}
.wrap{{max-width:1200px;margin:0 auto;padding-inline:16px;padding-block:24px 40px}}
h1{{font-size:22px;margin:0 0 16px}}h2{{font-size:15px;margin:24px 0 10px;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,220px),1fr));gap:14px}}
figure{{margin:0;background:var(--card);border-radius:8px;overflow:hidden;border:3px solid transparent}}
figure img{{display:block;width:100%}}figcaption{{padding:8px 10px;font-size:13px}}
.exemplar{{border-color:var(--good)}}.anti{{border-color:var(--bad)}}.cand{{border-color:var(--ink)}}
</style><div class="wrap"><h1>{html.escape(title)}</h1><div class="grid">{body}</div></div>"""


def cmd_sheet(args):
    entries = load_lib()
    body = "".join(f'<figure class="{e["kind"]}"><img src="{embedded(TASTE / e["file"], 420)}"><figcaption><b>{e["id"]}</b> '
                   f'{e["kind"]} · {e["medium"]}<br>{html.escape(e["why"])}<br><small>{html.escape(", ".join(e.get("tags") or []))}'
                   f' · {html.escape(e.get("source", ""))}</small></figcaption></figure>' for e in entries)
    Path(args.out).write_text(page(f"Taste library · {len(entries)} examples", body), encoding="utf-8")
    print(f"wrote {args.out}: {len(entries)} examples")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("file")
    p.add_argument("--kind", required=True, choices=["exemplar", "anti"])
    p.add_argument("--medium", required=True, choices=MEDIA)
    p.add_argument("--tags", default="")
    p.add_argument("--why", required=True)
    p.add_argument("--source", required=True, help="where it came from; credit external work")
    p.add_argument("--by", default="art director")
    p = sub.add_parser("from-judge")
    p.add_argument("round")
    p.add_argument("--keep", action="append", help='ID:"why it works"')
    p.add_argument("--reject", action="append", help='ID:"what went wrong"')
    p.add_argument("--medium", choices=MEDIA)
    p.add_argument("--tags", default="")
    p = sub.add_parser("nearest")
    p.add_argument("file")
    p.add_argument("--medium", choices=MEDIA)
    p.add_argument("--tags", default="")
    p.add_argument("-k", type=int, default=3)
    p.add_argument("--sheet")
    p = sub.add_parser("lesson")
    p.add_argument("text")
    p.add_argument("--evidence", required=True)
    p.add_argument("--enforced-in")
    p = sub.add_parser("sheet")
    p.add_argument("-o", "--out", default=str(TASTE / "library.html"))
    args = ap.parse_args()
    {"add": cmd_add, "from-judge": cmd_from_judge, "nearest": cmd_nearest, "lesson": cmd_lesson,
     "sheet": cmd_sheet}[args.cmd](args)


if __name__ == "__main__":
    main()
