# Design review · the checklist every gate runs

Run this before a creative reaches the art director: at the lock (stage 2), on frames and
clips (stages 4–5), on statics and the edit (stage 8). It sits on top of `judge.py`: the
judge scores, this review explains and fixes.

Adapted for ad creatives from two open skill packs installed in `.claude/skills/`:
[Impeccable](https://github.com/pbakaus/impeccable) (Apache-2.0: the squint test, role-based
typography, spatial thesis, craft floor, "the brief wins") and
[Taste Skill](https://github.com/Leonxlnx/taste-skill) (MIT: brandkit's strategy-first method,
one core metaphor, restraint). The refuse list adds what went wrong on our own pilots.

## 0. How to review

1. **The brief wins.** The lock and the brief outrank your own taste and every rule below.
2. **Eyes first, machine second.** Score and write the visual assessment before reading the
   machine numbers (`judge.py measure`, `spec_check.py`), so the numbers cannot anchor it.
   Then put both side by side and note what each caught alone.
3. **Evidence, not "yes".** Every answer names the file, frame, timecode or value it rests on.
4. **Bounded passes.** Inspect everything once, fix everything in one batch, confirm once.
   No open-ended polishing loop.
5. **The floor is not the ceiling.** Passing every check makes a creative shippable, not good.
   With the floor green, spend the effort on the idea.
6. **Compare with the taste library.** Open the nearest exemplars and anti-examples
   (`python scripts/taste.py nearest <file>`) and say which it is closer to, and why.

## 1. The lock (stage 2): strategy before style

Answer before proposing any look:

- What does the brand represent, in one sentence? What is the emotional promise?
- **The core metaphor:** one idea the whole ad can be built from (a paper plane for money that
  travels; a plant reviewing its human). Not a mood, an idea.
- What the look must avoid (category clichés, competitors' looks, generic AI defaults).
- One strong idea per direction. Three directions, each a different metaphor or world, not
  three colourways of one.
- Style frames are a board, not a single image: a 2×2 of the world, the hero, a detail and a
  type-on-image test, so the lock is judged as a system.

## 2. Frames and clips (stages 4–5)

- **Squint test:** blur the frame. The subject, then the secondary element, then the space for
  the super still read in that order.
- **One idea per frame:** the beat reads in a second with the sound off.
- **Space for type:** the caption band is calm (the judge's calm-band score), and the subject
  sits in the platform's safe zone.
- **On model:** the hero, set and light match the kept frames before and after (the board's
  join score for clips).
- **Physics and material:** water behaves like water, paper like paper. Describe what matter
  does, not a dramatic verb ("pools on the soil", not "floods").
- **AI tells:** melted or duplicated objects, stacked props, fake text or lettering, extra
  fingers, textures that crawl, UI screens nobody asked for.
- **Zoom in on paper and forms** (lesson L011): blank ruled lines, receipts and invoices come back
  with fake glyphs. Check at 100% before picking.

## 3. Statics and supers (stage 8)

**Typography** (roles, not sizes):
- Name the roles first: headline, number, supporting line, CTA, wordmark. Use the fewest.
- Each role differs from its neighbour in at least two of size, weight and space. Adjacent
  roles that differ in size only will blur together.
- The brand's own typeface, set in Figma. **The closest installed font is a failure, not a
  fallback**: stop and get the font.
- Headline two lines at most, line height about 98%, tracking −2% (never below −4%).
- **Text amount follows the job** (lesson L009). A hook or brand card carries one line. An
  explainer, an offer or a native format (a Notes page) may carry more, if the squint test still
  finds the headline first.
- **One bold word may be played with** (lesson L010): hidden behind the product, cropped or
  overlapped, if it is a single well-known word. Never a sentence, a price or a claim.

**Layout** (the spatial thesis, stated before building):
- What leads, what supports, what belongs together, where the eye ends (the CTA).
- Proximity before boxes; tight groups, generous separation; more space above a group than
  inside it.
- Stories and TikTok: type between 16% and 60% of the height; no drawn CTA.

**Colour and contrast:**
- Text 4.5:1 or better, large display type 3:1 or better, measured on the actual background.
- Contrast comes from the layout (a sheet, a column, a clear area), never from a scrim.
- Secondary text is a tint of the ink or the background hue, never a flat grey.
- Shadows have an offset and a soft blur, and only where they explain depth (a sheet on a desk).

## 4. Refuse (unless the brief asks for it)

- Text over photo detail; a dark scrim to rescue it.
- A system or fallback font as the display voice.
- Gradient text, glow halos, glass effects as decoration.
- A small label above every headline; emoji or glyphs as icons.
- Generic stock compositions: centred product on a gradient, floating objects with no reason.
- From our pilots: a hand-free object doing a human's job (the floating watering can); fake
  app screens in UGC frames; overflow physics that turn to mud; two plants where the brief has
  one; room props that change between frames; a POV the model cannot hold.

## 5. Report at the gate

- **Score:** the judge's round score and band.
- **Closest to:** the nearest exemplar and anti-example from the taste library.
- **Fix before the gate:** what this review changed, with evidence.
- **Open for the art director:** the one or two calls that need a person.
