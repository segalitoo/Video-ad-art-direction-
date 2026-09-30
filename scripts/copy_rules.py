"""Rules for every line a viewer reads or hears. Shared by assemble.py --check and copy_check.py.

- guardrails: the lock's `guardrails.never_say` words, anywhere on screen or in the voiceover.
- proof: a percentage, a star rating, a review count or a price per day that the lock's `proof`
  block does not list. Proof is shown, never invented.
- headlines: word count from `verbal.headline_max_words`; no opening on a filler word.
- hooks: under 12 words, one mechanic each, no two starting on the same word, and a set that
  covers at least three mechanics.
"""

import re

MECHANICS = ["confession", "contrarian", "curiosity", "result", "challenge", "stat", "question", "visual"]
VOICES = ["direct", "editorial", "native"]         # direct response, editorial, UGC-native
FILLER_OPENERS = {"the", "our", "we", "a", "an"}
HOOK_MAX_WORDS = 12

# Claims that need proof: 93%, 4.8/5, 4.8 stars, 10,000+ reviews, $1.13/day
PROOF_PATTERNS = [
    r"\d+(?:[.,]\d+)?\s?%",
    r"\b\d(?:[.,]\d)?\s?(?:/\s?5|out of 5|stars?|★)",
    r"\b\d[\d,.]*\+?\s?(?:reviews?|ratings?|customers?|users?)\b",
    r"[$€£₪]\s?\d+(?:[.,]\d+)?\s?(?:/|a |per )\s?day",
]


def words(text):
    return re.findall(r"[\w'’-]+", str(text or ""), re.UNICODE)


def viewer_lines(board):
    """(where, kind, text) for every line a viewer reads or hears in a storyboard."""
    out = []
    for s in board.get("shots") or []:
        for key in ("super", "vo"):
            if s.get(key):
                out.append((f"{s['id']} {key}", key, str(s[key])))
    for st in board.get("statics") or []:
        for key in ("headline", "cta"):
            if st.get(key):
                out.append((f"static {st.get('id')} {key}", key, str(st[key])))
    v = board.get("variants") or {}
    for h in v.get("hooks") or []:
        out.append((f"hook {h.get('id')}", "hook", str(h.get("super", ""))))
    for c in v.get("ctas") or []:
        out.append((f"cta {c.get('id')}", "cta", str(c.get("text", ""))))
    return out


def guardrail_hits(text, lock):
    banned = ((lock.get("guardrails") or {}).get("never_say")) or []
    low = str(text).lower()
    return [b for b in banned if b and re.search(rf"(?<!\w){re.escape(str(b).lower())}(?!\w)", low)]


def proof_text(lock):
    """Every proof value in the lock, as one lowercase string, digits normalised."""
    p = lock.get("proof") or {}
    parts = [p.get("rating"), p.get("review_count"), p.get("price_per_day")]
    for s in p.get("stats") or []:
        parts += [s.get("value"), s.get("claim")] if isinstance(s, dict) else [s]
    return norm(" ".join(str(x) for x in parts if x))


def norm(text):
    return re.sub(r"\s+", "", str(text).lower().replace(",", ""))


def unproven_claims(text, lock):
    """Numbers that read as proof but are not in the lock's proof block."""
    have = proof_text(lock)
    out = []
    for pat in PROOF_PATTERNS:
        for m in re.finditer(pat, str(text), re.I):
            num = re.search(r"\d[\d,.]*", m.group(0)).group(0)
            if norm(num) not in have:
                out.append(m.group(0).strip())
    return out


def headline_issues(text, lock):
    out = []
    verbal = lock.get("verbal") or {}
    limit = verbal.get("headline_max_words") or 8
    w = words(text)
    if len(w) > limit:
        out.append(f"{len(w)} words; the lock allows {limit}")
    if w and w[0].lower() in FILLER_OPENERS:
        out.append(f'opens on "{w[0]}"; lead with the idea, not a filler word')
    return out


def hook_set_issues(hooks):
    """hooks: [{id, line, mechanic?, voice?}]. Checks each line and the set as a whole."""
    out = []
    firsts = {}
    for h in hooks:
        hid, line = h.get("id", "?"), str(h.get("line", ""))
        w = words(line)
        if len(w) > HOOK_MAX_WORDS:
            out.append(f"hook {hid}: {len(w)} words; a hook lands under {HOOK_MAX_WORDS}")
        if w:
            firsts.setdefault(w[0].lower(), []).append(hid)
        m = h.get("mechanic")
        if m and m not in MECHANICS:
            out.append(f"hook {hid}: unknown mechanic '{m}'. Options: {', '.join(MECHANICS)}")
        v = h.get("voice")
        if v and v not in VOICES:
            out.append(f"hook {hid}: unknown voice '{v}'. Options: {', '.join(VOICES)}")
    for first, ids in firsts.items():
        if len(ids) > 1:
            out.append(f'hooks {", ".join(ids)} all start with "{first}"; two hooks that start alike read as one')
    mech = {h.get("mechanic") for h in hooks if h.get("mechanic")}
    if not mech:                                    # untagged sets (older boards) are not judged on coverage
        return out
    untagged = [str(h.get("id")) for h in hooks if not h.get("mechanic")]
    if untagged:
        out.append(f"hooks {', '.join(untagged)}: no mechanic; tag every hook so the set can be checked")
    if len(hooks) >= 3 and len(mech) < 3:
        out.append(f"{len(hooks)} hooks use {len(mech)} mechanic(s); cover at least 3 "
                   f"({', '.join(MECHANICS[:5])}, ...)")
    return out


def check_board_copy(board, lock):
    """Warnings for assemble.py --check: guardrails, unproven claims, headline rules, hook set."""
    out = []
    for where, kind, text in viewer_lines(board):
        for b in guardrail_hits(text, lock):
            out.append(f'{where}: "{b}" is in the lock\'s never_say list')
        for c in unproven_claims(text, lock):
            out.append(f'{where}: "{c}" reads as proof but is not in the lock\'s proof block. Add the source or cut it')
        if kind == "headline":
            out += [f"{where}: {i}" for i in headline_issues(text, lock)]
    hooks = [{"id": h.get("id"), "line": h.get("super"), "mechanic": h.get("mechanic"), "voice": h.get("voice")}
             for h in (board.get("variants") or {}).get("hooks") or []]
    out += hook_set_issues(hooks)
    return out
