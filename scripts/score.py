#!/usr/bin/env python3
"""Score scripts, concepts and static briefs before any paid generation. Words are cheap; clips are not.

    python scripts/score.py new score/r1.yml --kind script --ids A1-direct A1-native A2-editorial
    python scripts/score.py new score/r1.yml --from examples/fernly/storyboard.yml     # one item per hook variant
    python scripts/score.py rank score/r1.yml -o score/r1.md

Claude fills each item's five scores (1 to 5) with a one-line reason, the way the judge pass scores
images; the creative lead can overrule any number. Then `rank` totals them (out of 25) and decides:

    20 or more   produce it, with every hook variant
    15 to 19     produce one version
    under 15     do not produce: rewrite the weakest dimension (named in the report), score again

Rubrics:
    script   hook (does second 2 force second 3?) · buyer_language (a person, not a brand) ·
             objection (names and resolves a real one) · product_moment (natural entry) · close
    static   stop (thumbnail stops the scroll) · message (one idea, reads in 2 s) · proof (shown, real) ·
             product (clear, on-brand) · cta (obvious, legible at 25%)
    concept  angle (from research, differentiated) · hook · proof · format_fit · feasibility (lock, budget)
"""

import argparse
from pathlib import Path

import yaml

from common import fail, load_yaml

RUBRICS = {
    "script": ["hook", "buyer_language", "objection", "product_moment", "close"],
    "static": ["stop", "message", "proof", "product", "cta"],
    "concept": ["angle", "hook", "proof", "format_fit", "feasibility"],
}
PRODUCE_ALL, PRODUCE_ONE = 20, 15


def cmd_new(a):
    path = Path(a.file)
    if path.exists():
        fail(f"{path} exists; score into a new round file")
    items = {}
    if a.from_board:
        board = load_yaml(a.from_board)
        for h in (board.get("variants") or {}).get("hooks") or []:
            items[h["id"]] = {"text": h.get("super", ""), "mechanic": h.get("mechanic", "")}
        for st in board.get("statics") or []:
            items[f"static-{st['id']}"] = {"text": st.get("headline", ""), "kind": "static"}
    for i in a.ids or []:
        items[i] = {"text": ""}
    if not items:
        fail("nothing to score: pass --ids or --from a storyboard")
    for k, it in items.items():
        kind = it.get("kind", a.kind)
        it["scores"] = {d: None for d in RUBRICS[kind]}
        it["why"] = ""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Score round. Fill each score 1 to 5 and a one-line why; then: scripts/score.py rank {path}\n")
        yaml.safe_dump({"kind": a.kind, "items": items}, f, sort_keys=False, allow_unicode=True, width=110)
    print(f"wrote {path} ({len(items)} items, rubric: {a.kind})")


def cmd_rank(a):
    data = load_yaml(a.file)
    rows, missing = [], []
    for iid, it in (data.get("items") or {}).items():
        sc = it.get("scores") or {}
        vals = {k: v for k, v in sc.items()}
        if any(v is None for v in vals.values()):
            missing.append(iid)
            continue
        bad = {k: v for k, v in vals.items() if not (isinstance(v, (int, float)) and 1 <= v <= 5)}
        if bad:
            fail(f"{iid}: scores must be 1 to 5, got {bad}")
        total = sum(vals.values())
        weakest = min(vals, key=vals.get)
        if total >= PRODUCE_ALL:
            verdict = "PRODUCE with every hook variant"
        elif total >= PRODUCE_ONE:
            verdict = "PRODUCE one version"
        else:
            verdict = f"REWRITE: {weakest} is weakest ({vals[weakest]})"
        rows.append((total, iid, vals, verdict, it.get("why", ""), it.get("text", "")))
    if missing:
        fail(f"not scored yet: {', '.join(missing)}")
    rows.sort(key=lambda r: -r[0])
    lines = [f"# Score round · {Path(a.file).stem}", "",
             f"Out of 25. {PRODUCE_ALL}+ produce with every hook variant; {PRODUCE_ONE} to {PRODUCE_ALL - 1} one version; "
             f"under {PRODUCE_ONE} rewrite before any paid run."]
    groups = {}
    for r in rows:                                   # one table per rubric (scripts and statics differ)
        groups.setdefault(tuple(r[2]), []).append(r)
    for dims, group in groups.items():
        lines += ["", "| Rank | Item | " + " | ".join(dims) + " | Total | Decision | Why |",
                  "|---|---|" + "---|" * len(dims) + "---|---|---|"]
        for n, (total, iid, vals, verdict, why, text) in enumerate(group, 1):
            label = f"{iid}" + (f": {text[:40]}" if text else "")
            lines.append(f"| {n} | {label} | " + " | ".join(str(vals[d]) for d in dims) + f" | **{total}** | {verdict} | {why} |")
    out = "\n".join(lines) + "\n"
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
        print(f"wrote {a.out}")
    for total, iid, _, verdict, _, _ in rows:
        print(f"{total:>3}/25  {iid:24} {verdict}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("file")
    n.add_argument("--kind", choices=sorted(RUBRICS), default="script")
    n.add_argument("--ids", nargs="*")
    n.add_argument("--from", dest="from_board", help="a storyboard: one item per hook variant and static")
    r = sub.add_parser("rank")
    r.add_argument("file")
    r.add_argument("-o", "--out")
    a = ap.parse_args()
    {"new": cmd_new, "rank": cmd_rank}[a.cmd](a)


if __name__ == "__main__":
    main()
