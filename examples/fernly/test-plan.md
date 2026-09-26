# Go/no-go test · Fernly

Run before the full budget. The pass rules are written before any result exists,
so the result cannot move them.

## What runs (Higgsfield API, about $1.50 before cashback; every step is estimated first)

Nano Banana Pro is not on the API, so the test also picks the keyframe model:
each still is made on both Soul 2 and Qwen Image 3, and the better model wins.

| # | Generation | Model (API id) | Est. |
|---|---|---|---|
| 1 | Plant, droopy (S05 start frame, also the hero reference) | `higgsfield-ai/soul/v2/standard` + `alibaba/qwen-image-3/text-to-image`, 9:16 | ❌ estimate |
| 2 | Plant, lush (S05 end frame) | same two models | ❌ estimate |
| 3 | S01 keyframe (POV from the soil, spout in frame) | same two models | ❌ estimate |
| 4 | S01 motion from the better keyframe: the pour | `bytedance/seedance-2.5/image-to-video`, 4s, 480p | ≈ $0.58 |
| 5 | S05 motion, droopy to lush (`image_url` + `end_image_url`) | same, 4s, 480p | ≈ $0.58 |
| 6 | Voice: the S01 line in Arthur's voice | Higgsfield web (chat connector), ≈ 0.3 credits, or a voice model on the API if listed | ≈ $0.02 |
| | **Total** | | **≈ $1.50** |

Clips run at 480p on purpose: the test judges motion and believability, not resolution.

Clips run at 480p on purpose: the test judges motion and believability, not resolution.

## Pass rules (3 of 4 = go)

1. **The pour reads as real water**: a believable stream and splash, no melting spout.
2. **The POV reads as "from the pot" within 1 second**, with the sound off.
3. **The growth reads as growth**: leaves lift and open; the plant does not melt, swap or morph into another plant.
4. **Arthur's line makes the creative lead smile.**

No faces or hands anywhere, in any of the above, or it is an automatic fail for that item.

## If it fails

Switch to Driftpay (lowest risk) or back to Sunpeel. The lock, storyboard and scripts
carry over; about $1.50 is spent, half of it returned as cashback.

## Result

| Item | Pass / fail | Why |
|---|---|---|
| 1 Pour | Pass | Round 2 clip passed but the floating can read as fake. Re-run with a hand (lock v1.2): steady pour, water pools, clean pot, natural hand (judge 80) |
| 2 POV | Fail | 0 of 7 frames across two rounds gave the view from the soil; the camera watches the plant |
| 3 Growth | Pass | D1 to L1 on first/last frame: leaves lift, yellow turns green, room and pot hold, no morph |
| 4 Voice | Pass | The art director heard Arthur read the S01 line on higgsfield.ai: "sounds good" (2026-09-26) |
| **Decision** | **Go** | 3 of 4 pass (pour, growth, voice). The POV rule failed: the camera watches the plant, and the captions and Arthur make it the narrator |

## Results, round 1 (2026-09-26)

Six requests, 15 images, $0.29 at list. Judge report: [`test/judge-r1.md`](test/judge-r1.md) (sheet: `test/judge-r1.html`).

- **Round score 55 / 100: regenerate.** Best set D5 + L5 + P5, the same set the art director picked.
- **Model:** Qwen Image 3 won every group (mean 68 vs 53 for Soul 2). Soul looks more like phone footage but drew an Instagram Stories screen twice.
- **Why it is not ready:** S01 shows a fern or pothos, not the monstera (S01 was not a hero shot: a storyboard bug). Props drift between D5 and L5 (shelf, white pots, bed edge, mug), which would morph in the S05 clip. The droopy plant is only half droopy.
- **Clips on hold** until round 2 fixes the frames: animating a mismatched pair spends $0.82 to show a morph we can already see.

## Results, round 2 (lock v1.1, 2026-09-26)

Eight requests, $0.60 at list: 4 wilting frames and 2 pour frames on Qwen Image 3, then 2 lush frames made as edits of the best wilting frame (D1) with Qwen Image 3 Edit. Report: [`test/judge-r2.md`](test/judge-r2.md).

- **Round score 66 / 100 (from 55): usable.** Best set D1 + L1 + P2.
- **The S05 pair now matches 5/5:** the edit kept the room, shelf, books, mug, curtain and light; only the plant changed. This was the main fix.
- **S01 now shows the monstera,** in the same room. The view from the soil never appeared (0 of 7 across both rounds).
- **Open:** the room is consistent but bare; the stream is thin. Fixes are in the report.

## Results, round 2 clips

Two Seedance 2.5 clips, 4s 480p with sound, $1.64 at list. Report: [`test/judge-r2-clips.md`](test/judge-r2-clips.md).
Test total: $2.53 at list across both rounds.

- **S05, 77:** the edited first/last pair works. This is the method for every change-of-state shot.
- **S01, 72:** stable and believable, but the stream is thin and the can never tilts. The motion follows the start frame, so the gush has to be in the keyframe.
- **Concept note:** with rule 2 failed, the camera observes the plant instead of seeing from it. The captions and Arthur still make the plant the narrator.

## Results, S01 with a hand (lock v1.2)

The art director rejected the floating can as not real. Lock v1.2 allows one hand (`people: hands`); S01 became an edit of L1.
Two hand frames ($0.15, judge 75), then two clips ($1.64):

- **First clip, 54:** the hand held, but "floods over the pot rim" made Seedance glaze the pot and floor with mud.
- **Retry on H2, 80:** steady pour, water pools on the soil, clean pot, no finger morph. The motion line now says what the water does inside the pot.

Test total: $4.32 at list.
