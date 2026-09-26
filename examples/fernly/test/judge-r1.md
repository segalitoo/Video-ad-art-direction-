# Judge report · Fernly test, round 1

**Round score: 55 / 100, regenerate.**
Best set: D5 + L5 + P5 (files 68, match 62).

## Best matching sets

| # | Set | Score | Files | Match | Why |
|---|---|---|---|---|---|
| 1 | D5 + L5 + P5 | **55** | 68 | 62 | first_last 75 (eyes: Same pot, window, curtain, floor and floral mug; left shelf changes shape, white pots vanish, bed edge appears, mug moves up); same_set 50 (eyes: Same warm room, window right, books and yellow mug; the plant is a fern) |
| 2 | D5 + L5 + P3 | **51** | 66 | 56 | first_last 75 (eyes: Same pot, window, curtain, floor and floral mug; left shelf changes shape, white pots vanish, bed edge appears, mug moves up); same_set 36 (machine) |
| 3 | D5 + L5 + P2 | **49** | 65 | 50 | first_last 75 (eyes: Same pot, window, curtain, floor and floral mug; left shelf changes shape, white pots vanish, bed edge appears, mug moves up); same_set 25 (eyes: Different light, room and plant) |

## D · S05 start: droopy monstera

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| D5 | **69** | 71 | 56 | qwen | Cleanest frame. Lower leaves wilted, top still perky, so it reads 'unwell', not 'dying'. A little too polished for phone footage |
| D3 | **62** | 64 | 52 | soul | A few hanging leaves read slightly tired. Tangled stems at the base may morph |
| D1 | **51** | 52 | 45 | soul | Healthy plant, not droopy: misses the beat. Plant sits left, books cut off at the bottom right |
| D2 | **45** | 44 | 52 | soul | Healthy, not droopy. Odd black hook at the top left, garbled book titles, busy lower third |
| D4 | 0 | – | 58 | soul | FAIL: Instagram Stories interface and a username drawn into the image |

## L · S05 end: lush monstera

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| L5 | **72** | 75 | 58 | qwen | Upright and healthy, centred, calm top. Lusher than D5 but not dramatically so |
| L3 | **67** | 69 | 59 | soul | Most lush and glossy. Gibberish book titles, books and mugs crowd the lower third |
| L1 | **66** | 69 | 48 | soul | Lush, but it fills to the top edge and hides the pot; no room for captions |
| L4 | **55** | 55 | 57 | soul | Leaves spread in a messy fan; mugs and books crowd the lower third |
| L2 | 0 | – | 64 | soul | FAIL: Instagram Stories interface and a username drawn into the image |

## P · S01: pour, from the soil

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| P5 | **62** | 61 | 66 | qwen | A fern, not the monstera. Best light and matches D5's room; stream too gentle to sell 'drown' |
| P3 | **56** | 56 | 54 | soul | Not the monstera. Same yellow-curtain room as D3/L4; floor-level angle, not from the soil |
| P2 | **53** | 52 | 54 | soul | A pothos, not the monstera. Clean, but a thin stream: 'watering', not 'drowning' |
| P1 | **43** | 40 | 60 | soul | A fern, not the monstera. Odd heap of soil in the foreground, cool light |
| P4 | **42** | 40 | 55 | soul | Not the monstera. Blue fabric at the left edge may be a person on the sofa; pot looks like plastic |

## By model

| Model | Files | Mean | Best | Fails |
|---|---|---|---|---|
| qwen | 3 | 68 | 72 | 0 |
| soul | 12 | 54 | 67 | 2 |

## What to change before the next round

- S01 shows a fern or pothos in all 5 frames: the plant is the narrator, so S01 must be the monstera. Set hero: true on S01 (storyboard bug).
- Replace 'a few books and mugs around' with a fixed set list in the lock: one pale oak shelf left with three paperbacks and one cream floral mug, a tall window right with linen curtains, honey oak floor. Nothing else.
- Make every end frame (L) as an edit of its kept start frame (D) with Qwen Image 3 Edit: 'same photo, only the plant changes'. Same pot, props and light by construction.
- Soul drew an Instagram Stories screen twice (D4, L2): 'phone video, vertical' reads as a screenshot. Add image negatives: social media interface, app buttons, usernames.
- Droopy is not droopy enough: 'most leaves hang limp, some yellowing edges, stems bending over the pot rim'.
- No model gave the view from the soil, and every stream is gentle. Ask for 'a heavy gush of water' and accept a floor-level angle, or build S01 as an edit of the set frame.
- Qwen won every group on cleanliness and room match; Soul looks more like real phone footage but failed 2 of 12. Keep Qwen, plus its edit model.

Scores: 85% Claude's eyes on the rubric in `scripts/judge.py`, 15% machine (sharpness, calm caption bands, palette pull, steadiness). A recommendation: the art director picks.
