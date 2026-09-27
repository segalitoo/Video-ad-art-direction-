# Driftpay statics v2 · delivery note

Ten statics in two directions, run as one campaign (art director, 2026-09-27). Built from the
taste library (`plan.md` names the example behind each choice).

| | Direction | Frames | Judge (static rubric) |
|---|---|---|---|
| A | One bold word: "LOCAL." with the plane through it; "Paid in / 1 day. / Not 5." | 5 | 85–88, avg 86 |
| B | The hand lets go: "Send the invoice. Get paid tomorrow."; the hand placing the last coin | 5 | 84–91, avg 88 |
| v1 | Delivered 2026-09-27 | – | 47–48 |

**Files:** `final/*.jpg` (export-ready, every one passes `spec_check.py` for its platform;
safe-zone overlays in `review/qa/`). Sheet: `review/v2-final-sheet.jpg`. Before/after:
`review/before-after.jpg`.

**Source of truth:** `layout.yml`, rendered with `scripts/static_render.py` in Space Grotesk
(`assets/fonts/`, SIL OFL). The Figma file "Driftpay · Statics" holds the same frames at the
first pass (v2 rows under v1); the Figma plan's MCP limit stopped the fix pass, so the fixes in
`review/fixes.md` and the three later tweaks (plane lifted off the A, chip beside the plane,
Stories products above the reply bar) live in `layout.yml` only. Apply them in Figma when the
limit resets, or by hand.

**Images:** Qwen Image 3 at 2K via the Higgsfield API, 9 of 10 approved runs made ($0.675; one
failed as "model unavailable" and was not rerun). Judge: `judge-images.md`. Picks: the plane
cut from B-plane 2 (used in both directions, mirrored for A), coins AC1, hands BC2 and BS2.
Rejected: both A-plane images (fake glyphs in the ruled cells), BC1 and BS1 (melted coin edges).

**Before real use:** "1 day", "tomorrow" and "free account" are claims and go to legal (brief).
Lock v1.1 allows hands.
