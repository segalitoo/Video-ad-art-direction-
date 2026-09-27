# Static ads · the design system

Statics are designed, not captioned. The layout is chosen first; the plate is made for it;
the type is set in Figma with the brand font. `static_compose.py` stays as a quick draft
tool only.

## 1. Pick the layout before the plate

| Layout | Use it for | Type lives on | Image lives in |
|---|---|---|---|
| **Paper band** | 1:1, 4:5, 9:16 with one headline | a solid sheet across the top (38–42% of the height) | the rest, under a soft sheet shadow |
| **Split** | 1.91:1 (LinkedIn landscape) | a solid column on the left (45–48% of the width) | the right side |
| **Big number** | a claim with a number ("1 day", "0% fees") | the sheet, with the number set 3–4× the words around it | below the sheet |

The plate prompt then says where the subject sits (below the sheet, or right of the column)
and keeps that area simple. Type never sits on photo detail.

## 2. Type

- The lock's brand font, installed in Figma. Never a system fallback.
- Headline: Bold, 8–9% of the frame's short side (1200 px square → 104–112 px), line height 98%, tracking −2%, two lines at most.
- Big number: Bold, 18–20% of the short side, tracking −5%.
- Supporting line: Medium, 2.4–2.6% of the short side, a muted ink that still passes 4.5:1.
- CTA: Bold in a pill in the accent colour, ink text (check it passes 4.5:1 on the accent), at least 44 px tall.
- Wordmark with its mark, top-left of the copy block, 3–3.5% of the short side.
- One message per static: wordmark, headline, one supporting line, CTA. Nothing else.

## 3. Contrast and safe zones

- Contrast comes from the layout: ink on the sheet colour, 4.5:1 or better. No scrims.
- Stories and TikTok: all type between 16% and 60% of the height; no drawn CTA (the platform adds one).
- Feed and LinkedIn: 7–8% margins on every side.

## 4. The judge rubric for statics

| Criterion | Weight | What passes |
|---|---|---|
| Readable at thumbnail | 25 | the headline reads at 25% size, on a phone |
| Hierarchy | 20 | one thing first, then the next; nothing competes |
| Composition | 20 | a deliberate layout, the subject framed, space used on purpose |
| Brand | 15 | lock font, palette and wordmark, used correctly |
| Craft | 20 | clean plate, no AI tells, crisp edges, aligned to the grid |

## 5. In Figma

`scripts/figma/statics_layout.js` builds the frames (placements, sheet, type, wordmark, CTA,
empty photo slots) through the Figma connector's `use_figma`; `upload_assets` then fills the
photo slots with the kept plates (the environment must allow `mcp.figma.com`). The art
director refines in Figma; exports go back to `spec_check.py`.
