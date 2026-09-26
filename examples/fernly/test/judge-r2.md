# Judge report · Fernly test, round 2 (lock v1.1)

**Round score: 66 / 100, usable, fix the listed issues.**
Best set: D1 + L1 + P2 (files 71, match 88).

## Best matching sets

| # | Set | Score | Files | Match | Why |
|---|---|---|---|---|---|
| 1 | D1 + L1 + P2 | **66** | 71 | 88 | first_last 100 (eyes: Everything identical except the plant; the pot shifts a few pixels); same_set 75 (eyes: Same room, shelf, mug and curtain; P2's camera is higher and closer, pot smaller) |
| 2 | D1 + L1 + P1 | **63** | 70 | 78 | first_last 100 (eyes: Everything identical except the plant; the pot shifts a few pixels); same_set 56 (machine) |
| 3 | D4 + L1 + P2 | **60** | 68 | 74 | first_last 74 (machine); same_set 75 (eyes: Same room, shelf, mug and curtain; P2's camera is higher and closer) |

## D · S05 start: wilting monstera

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| D1 | **72** | 74 | 65 | qwen | Clearly dying: stems hang over the rim, lower leaves yellow. Clean. Room reads a bit bare for phone footage |
| D2 | **66** | 66 | 68 | qwen | Strong wilt, but a stem trails to the floor into a dried clump that will likely morph |
| D4 | **66** | 66 | 64 | qwen | Centred and clean, but the upper leaves look healthy: reads 'a bit sad', not 'dying' |
| D3 | 0 | – | 70 | qwen | FAIL: Broken hero: two terracotta pots stacked |

## L · S05 end: lush, edited from D1

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| L1 | **77** | 79 | 68 | qwen-edit | Same plant grown lush and upright; room identical to D1. Dry stems show at the soil |
| L2 | **65** | 65 | 67 | qwen-edit | Dense and healthy; one leaf crosses the curtain, brown roots at the base |

## P · S01: pour

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| P2 | **62** | 61 | 68 | qwen | Same as P1, can closer to the corner, stream into the leaves; pot looks smaller than in D1 |
| P1 | **62** | 61 | 64 | qwen | The monstera now, same room. Eye level, not from the soil; thin stream reads 'watering', not 'drowning' |

## By model

| Model | Files | Mean | Best | Fails |
|---|---|---|---|---|
| qwen | 6 | 66 | 72 | 1 |
| qwen-edit | 2 | 71 | 77 | 0 |

## What to change before the next round

- The set now holds, but it is bare: add one or two named lived-in details to WORLD (a folded grey throw on the shelf, a charger cable on the floor) and keep phone_look.py grain in the edit.
- No frame in either round gave the view from the soil (0 of 7). Accept the eye-level pour: it reads, and a floating can fits people: false. Update S01's subject to match.
- Make S01 an edit too: take the kept lush frame (L1) and add the tipped yellow can and a heavy gush. Same room and pot by construction.
- The stream is thin in every frame; let the motion prompt carry the 'heavy gush' in S01.
- Keep Qwen Image 3 plus its edit model for keyframes. The judge caught the stacked pots (D3), the classic failure to watch for.

Scores: 85% Claude's eyes on the rubric in `scripts/judge.py`, 15% machine (sharpness, calm caption bands, palette pull, steadiness). A recommendation: the art director picks.
