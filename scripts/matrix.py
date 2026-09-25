#!/usr/bin/env python3
"""Expand one approved base ad into its variant matrix: hooks x CTAs x platforms.

    python scripts/matrix.py examples/sunpeel/storyboard.yml -o matrix.csv

Every row is one deliverable with its own ID, so each can be logged, checked
and judged on its own. The review queue is the slowest part of the pipeline,
so the script warns when the matrix grows past what one review can handle.
"""

import argparse
import csv
import sys

from common import load_specs, load_storyboard

REVIEW_LIMIT = 24


def rows(board, lock, specs):
    ad = board["ad"]
    variants = board.get("variants") or {}
    hooks = variants.get("hooks") or [{"id": "H0", "super": ""}]
    ctas = variants.get("ctas") or [{"id": "C0", "text": ""}]
    for pid in ad["platforms"]:
        spec = specs["platforms"][pid]
        aspect = ad["master_aspect"] if ad["master_aspect"] in spec["aspects"] else spec["master_aspect"]
        source = "master" if aspect == ad["master_aspect"] else f"reframe from {ad['master_aspect']}"
        for hook in hooks:
            for cta in ctas:
                yield {
                    "variant_id": f"{ad['id']}_{pid}_{hook['id']}{cta['id']}",
                    "platform": pid,
                    "aspect": aspect,
                    "source": source,
                    "length_s": ad["length_s"],
                    "hook_id": hook["id"],
                    "hook": hook.get("super", ""),
                    "cta_id": cta["id"],
                    "cta": cta.get("text", ""),
                    "lock_version": lock["meta"]["version"],
                    "status": "draft",
                }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("storyboard")
    ap.add_argument("-o", "--out", help="CSV path (default: stdout)")
    args = ap.parse_args()

    board, lock = load_storyboard(args.storyboard)
    data = list(rows(board, lock, load_specs()))
    if len(data) > REVIEW_LIMIT:
        print(f"WARN  {len(data)} variants. Over {REVIEW_LIMIT}, the review queue becomes the jam: "
              "cut hooks or platforms, or test in two rounds.", file=sys.stderr)

    out = open(args.out, "w", newline="", encoding="utf-8") if args.out else sys.stdout
    writer = csv.DictWriter(out, fieldnames=list(data[0].keys()))
    writer.writeheader()
    writer.writerows(data)
    if args.out:
        out.close()
        print(f"wrote {args.out} ({len(data)} variants)", file=sys.stderr)


if __name__ == "__main__":
    main()
