#!/usr/bin/env python3
"""Check every line a viewer reads or hears against the lock, before the copy lead sees it.

    python scripts/copy_check.py examples/fernly/storyboard.yml
    python scripts/copy_check.py hooks.yml --lock ../fernly.dna.yml

A storyboard: every super, voiceover line, static headline and CTA, and the hook variants.
A hooks file: `hooks: [{id, line, mechanic, voice}]`, for drafting before the storyboard exists.

Checks: the lock's `guardrails.never_say`; numbers that read as proof (%, stars, review counts,
price per day) but are not in the lock's `proof` block; headline length and filler openers
(`verbal.headline_max_words`); hooks under 12 words, no two starting alike, and a set covering
at least three mechanics (see templates/copy-matrix.md). Exit 1 when anything is flagged.
"""

import argparse
from pathlib import Path
import sys

from common import fail, load_lock, load_storyboard, load_yaml
from copy_rules import MECHANICS, check_board_copy, guardrail_hits, hook_set_issues, unproven_claims


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="a storyboard.yml or a hooks file")
    ap.add_argument("--lock", help="the lock, for a hooks file")
    a = ap.parse_args()
    data = load_yaml(a.file)
    if "shots" in data:
        board, lock = load_storyboard(a.file)
        issues = check_board_copy(board, lock)
        n = sum(1 for _ in board.get("shots") or []) + len(board.get("statics") or [])
        label = f"{board['ad']['id']}: {n} shots and statics"
    elif "hooks" in data:
        if not a.lock:
            fail("a hooks file needs --lock")
        lock = load_lock(Path(a.lock))
        hooks = data["hooks"]
        issues = hook_set_issues(hooks)
        for h in hooks:
            for b in guardrail_hits(h.get("line", ""), lock):
                issues.append(f'hook {h.get("id")}: "{b}" is in the lock\'s never_say list')
            for c in unproven_claims(h.get("line", ""), lock):
                issues.append(f'hook {h.get("id")}: "{c}" reads as proof but is not in the lock\'s proof block')
        used = sorted({h.get("mechanic") for h in hooks if h.get("mechanic")})
        label = f"{len(hooks)} hooks, mechanics: {', '.join(used) or 'none'} (of {', '.join(MECHANICS)})"
    else:
        fail(f"{a.file} is neither a storyboard (shots) nor a hooks file (hooks)")
    for i in issues:
        print(f"FLAG  {i}")
    print(f"{'PASS' if not issues else 'CHECK'}  {label}, {len(issues)} flag(s)")
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
