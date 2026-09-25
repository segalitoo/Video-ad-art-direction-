#!/usr/bin/env python3
"""Start a new ad project from the templates.

    python scripts/new_project.py sunpeel peel-back-summer
    python scripts/new_project.py acme spring-launch --mode ugc

Creates projects/<brand>-<campaign>/ with the brief, lock, storyboard, copy
matrix, QA checklist and an empty iteration log, plus folders for keyframes,
clips and exports.
"""

import argparse
from pathlib import Path
import re
import shutil
import sys

from common import MODES_DIR, ROOT

TEMPLATES = ROOT / "templates"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brand")
    ap.add_argument("campaign")
    ap.add_argument("--mode", default="3d-stylized",
                    choices=sorted(p.stem for p in MODES_DIR.glob("*.yml")))
    args = ap.parse_args()

    brand, campaign = slug(args.brand), slug(args.campaign)
    target = ROOT / "projects" / f"{brand}-{campaign}"
    if target.exists():
        print(f"error: {target} already exists", file=sys.stderr)
        sys.exit(2)

    for sub in ("keyframes", "clips", "exports"):
        (target / sub).mkdir(parents=True)
    for name in ("brief.md", "copy-matrix.md", "qa-checklist.md"):
        shutil.copy(TEMPLATES / name, target / name)

    lock_name = f"{brand}.dna.yml"
    lock = (ROOT / "lock" / "_template.dna.yml").read_text(encoding="utf-8")
    lock = lock.replace("mode: 3d-stylized ", f"mode: {args.mode} ", 1)
    (target / lock_name).write_text(lock, encoding="utf-8")

    board = (TEMPLATES / "storyboard.yml").read_text(encoding="utf-8")
    board = board.replace("lock: <brand>.dna.yml", f"lock: {lock_name}")
    board = board.replace("id: <brand>-<concept>-15s", f"id: {brand}-{campaign}-15s")
    (target / "storyboard.yml").write_text(board, encoding="utf-8")

    header = (TEMPLATES / "iteration-log.csv").read_text(encoding="utf-8").splitlines()[0]
    (target / "iteration-log.csv").write_text(header + "\n", encoding="utf-8")

    print(f"created {target.relative_to(ROOT)}  (mode: {args.mode})")
    print("next: fill brief.md, get it approved, then write the lock")


if __name__ == "__main__":
    main()
