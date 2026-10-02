# Lessons

Rules learned from real results. Each one names its evidence and where it is enforced now.

### L001 · Describe what matter does, never a dramatic verb
- **Evidence:** Fernly S01, "floods over the pot rim" glazed the pot and floor in mud (judge 54); "pools on the soil, the pot stays clean" judged 80.
- **Enforced in:** design review §2 (physics and material)
- **Added:** 2026-09-27

### L002 · A human's job needs a hand, not a floating object
- **Evidence:** Fernly S01, the watering can floating in from the top read as fake to the art director; the hand version read as real.
- **Enforced in:** design review §4; locks can set `people: hands`
- **Added:** 2026-09-27

### L003 · End frames are edits of the start frame, never a second generation
- **Evidence:** Fernly S05, two separate generations changed shelf, pots and mug (pair match 4/5); the edited pair matched 5/5 and animated cleanly.
- **Enforced in:** assemble.py (end frames as edit prompts), `chain: true`
- **Added:** 2026-09-27

### L004 · Every shot starts where the last one ended
- **Evidence:** Driftpay cut, joins of 43% (S03→S04) and 54% (S04→S05) read as jumps to the art director.
- **Enforced in:** `chain: true`, board.py join scores (under 70% flagged)
- **Added:** 2026-09-27

### L005 · Type sits on a clean field, in the brand font, never over photo detail
- **Evidence:** Driftpay statics v1 (text over the map and laptop, a fallback serif) were unreadable and generic to the art director.
- **Enforced in:** templates/static-design.md, design review §3
- **Added:** 2026-09-27

### L006 · Ask for the angle a model can hold; test impossible views cheaply first
- **Evidence:** the plant's-eye view failed 0 of 22 frames across two tests on two models.
- **Enforced in:** go/no-go test rules; design review §4
- **Added:** 2026-09-27

### L007 · Soul 2 ignores inline negatives for app interfaces in UGC prompts
- **Evidence:** 11 of 12 Soul 2 frames drew an Instagram or TikTok screen despite the negative.
- **Enforced in:** route choice (keyframes on Nano Banana Pro or Qwen)
- **Added:** 2026-09-27

### L008 · Look at the clip before you trust the frame
- **Evidence:** S05 bent the plane into a V before the coins; picking the in-point frame by frame saved the shot.
- **Enforced in:** cut.py in-points from kept.yml; board.py motion strips
- **Added:** 2026-09-27

### L009 · The amount of text follows the job: a hook or brand card carries one line; an explainer, offer or native format (a Notes page) may carry more, as long as the hierarchy still reads at a glance
- **Evidence:** Art director on the first reference batch: 'some have too much text but its ok and depend on the need'; T0008 (Notes format) works with long copy
- **Enforced in:** templates/design-review.md §3
- **Added:** 2026-09-27

### L010 · One bold word can be played with (hidden behind the product, cropped, overlapped) as long as it stays a single, well-known word; sentences cannot be played with that way
- **Evidence:** Art director on T0013 (sneaker poster): 'the text is not fully readable but it features 1 bold word that can be played a bit so its ok'; T0012 (MIX naan) uses the same device
- **Enforced in:** templates/design-review.md §3
- **Added:** 2026-09-27

### L011 · Zoom into every paper prop before picking: image models fill blank forms with fake glyphs. Prefer 'plain ruled lines' over 'lines where the numbers would be' (suspected trigger, not yet proven)
- **Evidence:** Driftpay statics v2: 2 of 3 plane images from the same prompt (Qwen Image 3, 'grey ruled lines where the numbers would be') had letter-like marks in the cells; the third was clean. Test the plain wording on the next run
- **Enforced in:** templates/design-review.md §2 (AI tells) and the hero description in the lock
- **Added:** 2026-09-27

### L012 · Budget Figma MCP calls: the Starter plan allows 20 a month; build in one call, check with one screenshot call, and render locally (scripts/static_render.py, same layout) for fixes and export
- **Evidence:** Driftpay statics v2: the fix pass hit the limit after build, upload and two screenshot calls
- **Enforced in:** templates/static-design.md
- **Added:** 2026-09-27

### L013 · Soul 2.0 ignores "empty upper third": ask for the subject in the lower half with the top of the head just below the middle, or choose a pose that is low by nature (lying on a sofa gives the headline room for free)
- **Evidence:** A fashion spec (local project, 2026-09-30): round 1 put the head in the top third in 10 of 10 frames; "lower half" wording improved the standing frames, and all 8 sofa frames left half the frame as wall
- **Enforced in:** templates/static-design.md §3
- **Added:** 2026-09-30

### L014 · Image models sew fake woven labels with made-up letters onto garments; remove them with one Nano Banana Pro edit of the kept frame ("remove the label, keep everything else exactly the same"), which also upscales to 2K and keeps the face
- **Evidence:** Same project: 14 of 16 round 2 frames had a bib label with fake letters even with "no labels" in the prompt; the 2-credit edits removed it with the face, pose and light unchanged
- **Enforced in:** templates/static-design.md §3; the lock's negative_image
- **Added:** 2026-09-30

### L015 · To reach 9:16 or give type more room, extend a plain wall for free, but never mirror a strip that contains the subject: tile only clean wall, blur the symmetry away, add grain, and colour-match the seam; extend the floor downward to lift a low subject into the Reels safe area. Floors can't be mirrored sideways (the planks make a V)
- **Evidence:** Same project: the first mirror copied her head upside down into the top; the second showed a seam line; the third (clean-wall tile, colour match) was invisible. The sofa frame sat in the bottom 35% of Stories until the floor was stretched
- **Enforced in:** templates/static-design.md §3
- **Added:** 2026-09-30

### L016 · Check the ink on the real wall, not on the lock colour: a photo wall is darker than its sampled swatch where the headline sits. Measure the pixels under the type box; the brand plum fell to 3.4:1 on the darker plaster, a deeper shade of it reached 4.8:1
- **Evidence:** Same project: the lock's "5.2:1 on the wall" came from a light sample; the headline area measured #A99174
- **Enforced in:** templates/static-design.md §3
- **Added:** 2026-09-30

### L017 · Never write "headline", "copy space" or "for text" in an image prompt: the model draws fake text and boxes to fill it. Ask for the space in plain picture terms ("the upper third is plain tiled wall")
- **Evidence:** Byoma spec set, 2026-10-01: 8 of 8 Soul drafts with "space for a headline" had fake lettering or white boxes; one NBP edit cleaned the chosen frame
- **Enforced in:** the lock's negative_image ("headline boxes")
- **Added:** 2026-10-01

### L018 · A layout made of fixed positions breaks when the size changes. Measure the type first, then give the product the space that is left; break lines like a designer (on punctuation, no orphan, no "the" at a line end); and check the rendered file, not the plan: collisions, empty bands, contrast on the real pixels
- **Evidence:** Byoma spec set, 2026-10-01: the first 30 files passed every pre-render check, yet the 1:1 headline ran into the product, 9:16 frames had empty halves, callout names were 3.7:1, and "Your barrier called. It wants / a break." broke mid-sentence. The art director caught it at the set gate
- **Enforced in:** scripts/static_formats.py (flow layouts, fit and balance, layout_checks after render); scripts/selftest.sh
- **Added:** 2026-10-01

### L019 · In the Higgsfield web app, turn "Enhance prompt" off for loop clips, and never ask for moving light: the rewrite turns "soft light drifts" into blinds, flares and a colour shift. Ask for one small move (a push, a breath) and say the light and colours stay as the start frame. Check every clip frame against frame 0 before building the loop
- **Evidence:** Byoma B06, 2026-10-01: Wan 2.2 with enhance on drew window-blind shadows from 0.6 s and ended on a dark crimson wall; white type fell to 1.7:1. B05 (one small human move) drifted little and kept 4.6:1. The free local push was the safe B06 loop
- **Enforced in:** scripts/loop.py (make --layout renders each clip frame through the static's own layout)
- **Added:** 2026-10-01
