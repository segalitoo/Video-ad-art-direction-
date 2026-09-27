# Driftpay statics v2 · two directions from the taste library

The v1 statics failed on type (fallback font, text over photo detail, a dark scrim) and on
idea (a generic photo with a headline on top). v2 builds each static from named library
examples and lessons, in Figma with Space Grotesk. Sketches: `sketches.png`.

Placements (unchanged from the brief): A1 LinkedIn 1200×1200 and 1200×628, Meta feed 1080×1350 ·
A2 Stories 1080×1920 and Meta feed 1080×1350.

## A · One bold word

| Choice | From |
|---|---|
| One huge word fills the width ("LOCAL."), the paper plane flies through it and hides part of a letter | T0013 sneaker poster, T0012 MIX naan, lesson L010 |
| Setup small, payoff huge: "Paid in / **1 day.** / Not 5." | T0016 Goli |
| Paper-white field, ink navy type, coral only on the CTA and the plane's stripe | T0021 Carty, T0024 Dropcard (one accent colour) |
| The claim "1 day" is never covered by the plane | L010: a claim may not be played with |

Images: the hero plane and the coin stack, each shot alone on a plain backdrop in a colour
that is not in the object, then cut out here (colour key) and placed on the paper-white field in Figma.

## B · The hand lets go

| Choice | From |
|---|---|
| A real hand has just let go of the paper-plane invoice; the plane glides off | T0022 Carty CTA panel, T0025 dot., lesson L002 (a hand does the human's job) |
| Dark ink-navy A1, paper-white A2: the fields alternate across the set | T0017 Levanta system, T0023 Carty page rhythm |
| One coral phrase per headline ("tomorrow.", "1 day.") and the coral CTA | T0017 Levanta, T0024 Dropcard, T0015 Rosie |
| A small white "Invoice · Paid" chip floats beside the plane as proof, set in Figma | T0024 Dropcard floating proof |

Lock change needed: `people: false` → `people: hands` (lock v1.1), as Fernly did.

## Images · Qwen Image 3, 2K, higgsfield-api route, $0.075 each

| ID | For | Aspect | Count | Cost |
|---|---|---|---|---|
| A-plane | A1 all sizes (cut-out) | 1:1 | 2 | $0.15 |
| A-coins | A2 all sizes (cut-out) | 3:4 | 2 | $0.15 |
| B-plane | A1 all sizes (4:5, 1:1, 1.91:1 split) | 3:4 | 2 | $0.15 |
| B-coins | A2 Stories / feed | 9:16 and 3:4 | 2 + 2 | $0.30 |
| **Total** | | | **10** | **$0.75** |

Shared tokens (from the lock): handmade paper-craft miniature, crisp folded paper with visible
fibres, clean scored creases, true paper thickness, soft daylight from the left, macro
photograph of real paper models, 50mm lens.

Negative (all): numbers or writing on the paper, text, logo, glossy plastic or CGI sheen.
Hands (B): extra, missing or fused fingers; a face or full person; jewellery, watch, sleeve print.

### A-plane
A paper plane folded from a crisp white invoice sheet with a thin coral stripe along one edge
and grey ruled lines where the numbers would be, gliding up and to the right in a three-quarter
view, alone in the centre with wide empty space around it, on a plain seamless mint-green
paper backdrop. Every fold in sharp focus. [shared tokens]

### A-coins
A small stack of five round paper coins cut from thick card, alternating coral and mint, blank
faces with no symbols, standing alone in the centre on a plain seamless deep ink-navy paper
backdrop, seen slightly from above. [shared tokens]

### B-plane
A person's hand at the lower right, fingers just opened, has let go of a paper plane folded from
a crisp white invoice sheet with a thin coral stripe along one edge; the plane glides up and to
the left above the open fingers. Plain seamless deep ink-navy backdrop; the top 45% of the frame
is empty dark navy for type. Natural skin, slightly desaturated. [shared tokens]

### B-coins
A person's hand at the right edge sets one coral paper coin on top of a small stack of round
paper coins cut from thick card, alternating coral and mint, blank faces, on a plain seamless
paper-white backdrop; the top half of the frame is empty paper white for type. [shared tokens]

## After the images
1. Judge pass (`judge.py`, image rubric) and keep the best of each pair.
2. Cut-outs for A (colour key), then build both directions in Figma (`statics_layout.js`, new layouts).
3. Static rubric on every export, `taste.py nearest` against the library, design review §3.
4. Before/after sheet: v1 next to A and B.

Claims: "1 day" and "tomorrow" go to legal before real use (brief, mandatories).
