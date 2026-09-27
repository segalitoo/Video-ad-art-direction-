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
