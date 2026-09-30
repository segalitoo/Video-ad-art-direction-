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
