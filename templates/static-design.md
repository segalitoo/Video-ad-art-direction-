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

## 1b. The format library (for a testing set)

When a campaign needs many statics to test, pick formats from the angle, not the other way round
(`research.md` section 6 maps angle → format). `scripts/static_formats.py` builds each one from the
lock and renders it; the art director still refines the keepers in Figma.

| Group | Format | Use it when | Needs |
|---|---|---|---|
| Headline | hero-headline | cold traffic, one strong claim | a headline |
| Proof | stat | a real number that surprises | `proof.stats` with a source |
| | review | one customer sentence strong enough to be the headline | `proof.quotes` |
| | testimonial | warm audiences, close to buying | `proof.quotes` |
| | rating | a high rating with many reviews | `proof.rating`, `proof.review_count` |
| Compare | us-vs-them | a clear win over the category's usual way (never a named brand) | them, cons, pros |
| | ingredients | a product made of standout parts or features | 4 to 6 callouts |
| | benefits | several clear benefits, cold traffic | a list |
| | price-per-day | the price is the objection, the daily cost is not | `proof.price_per_day` |
| | badges | trust signals cut the friction | `proof.badges` |
| Native | lifestyle | competitors only run studio shots | a plate (a real place) |
| | ugc-frame | high ad blindness; looks captured, not designed | a plate |
| | text-thread | the most native format; social proof inside the chat | messages |
| | premium | known product, retargeting | nothing: space does the work |
| | seasonal | 2 to 3 weeks before a moment | a plate, a season |

Rules the script enforces:
- **Proof is shown, never invented.** Proof formats refuse to build without the lock's `proof`
  block, and any %, star rating, review count or price per day in the copy must be listed there.
- **A text thread or UGC frame never invents a person.** No fake names, handles or faces; the
  lines are the brand's own, in a native shape.
- **The set, not just the ad.** At least 3 formats and 2 background treatments per batch, no two
  headlines starting on the same word, product scale varying by 20% or more.
- **The thumbnail test.** At 25% size the CTA is still 7 px or more and the headline 12 px or more,
  both at 4.5:1 contrast (3:1 for large type).

Example: `examples/driftpay/formats/` (the lock has no proof, so its proof formats refuse to build).

## 2. Type

- The lock's brand font, installed in Figma. Never a system fallback.
- Headline: Bold, 8–9% of the frame's short side (1200 px square → 104–112 px), line height 98%, tracking −2%, two lines at most.
- Big number: Bold, 18–20% of the short side, tracking −5%.
- Supporting line: Medium, 2.4–2.6% of the short side, a muted ink that still passes 4.5:1.
- CTA: Bold in a pill in the accent colour, ink text (check it passes 4.5:1 on the accent), at least 44 px tall.
- Wordmark with its mark, top-left of the copy block, 3–3.5% of the short side.
- One message per static: wordmark, headline, one supporting line, CTA. Nothing else.

## 2b. Type size and white space (from the research, 2026-10-02)

The evidence, in short: attention to text grows in proportion to its surface size, and people read the
large print first, then the small, then the picture (Pieters & Wedel 2004, eye tracking). Ads with less text
on the image perform better (Meta's own testing behind the old 20% rule). White space in margins and between
blocks raises comprehension by almost 20%, and most readers prefer more of it (Lin 2004; Chaparro et al.,
Wichita State). Dense feature clutter hurts attention to the brand, while a deliberate design helps it
(Pieters, Wedel & Batra 2010). So: few words, set big, in a deliberate field of space.

1. **Few words, big.** The headline is the largest thing on the frame after the product, at least 2x any
   other text. Grow it until it meets one of three limits: its longest line fills the column (the measure,
   6–8% margins each side), the block reaches 20% of the frame height (one row of Meta's 5 x 5 text grid), or
   it needs a 5th line. Never stop at the short-side size if a tall frame has room.
2. **Size follows the room, not the format.** 9:16 has 78% more height than 1:1; its headline grows into it
   (the 20% cap is 384 px on 1920, 270 on 1350, 216 on 1080).
3. **Break for size.** A long word may sit on its own line if that lets the whole headline grow
   (MOM / STOLE MY / MOISTURIZER / AGAIN.), as long as the breaks stay clean (no orphan, no "my" or "the"
   at a line end).
4. **One field of space, with a job.** Tight inside a block (headline lines, headline to sub: one line of
   leading), generous around it. The largest empty area sits next to the hero and frames it; no second
   empty band anywhere (the 15% band rule still holds).
5. **Emphasis inside a line, the brand's way.** Mixed size, weight or colour in one headline is allowed when
   the brand does it: Byoma sets one caps weight and changes size or colour for the key phrase
   ("SAVE 25%" over "BUY MORE, SAVE MORE"). One emphasis per headline, never two.
6. **Readable on the phone.** A 1080 frame shows at about 393 pt wide (x 0.36). Body text at least 38 px on
   9:16 (about 14 pt on screen) ❌ (the 14 pt figure is from spec guides, not Meta's own page); never under 32 px.

## 3. Contrast and safe zones

- Contrast comes from the layout: ink on the sheet colour, 4.5:1 or better. No scrims.
- Stories and TikTok: all type between 16% and 60% of the height; no drawn CTA (the platform adds one).
- Feed and LinkedIn: 7–8% margins on every side.
- Measure contrast on the pixels under the type box, not on the lock swatch: photo walls are darker where the light falls off (L016).
- Headline room: ask for the subject in the lower half, or a low pose; image models ignore "empty upper third" (L013).
- Garments: expect fake woven labels with letters; remove them with one edit of the kept frame (L014).
- More wall for 9:16: tile clean wall only, blur, grain, colour-match the seam; stretch the floor downward to lift a low subject into the safe area (L015).
- Extending a wall in code: `scripts/wall_extend.py` continues each edge's own colour and warns when the photo's rectangle would show as a band (L027). Look at the wall with the contrast boosted before delivery.

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

## When Figma is out of reach

Figma stays the design source, but its MCP calls are limited (Starter plan: 20 a month). Build a
set in one `use_figma` call and check it with one screenshot call. For fixes and exports, write the
same layout as a layout file and render it with `scripts/static_render.py`: it uses the brand font
from `assets/fonts/`, Figma's text rules (letter spacing and line height in %), auto-layout stacks,
pills, fades and shadows. Example: `examples/driftpay/statics-v2/layout.yml`.

