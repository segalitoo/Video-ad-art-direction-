# Judge report · Fernly round 1, step 1 frames (lock v1.2)

**Round score: 74 / 100, usable, fix the listed issues.**
Best set: S02-2 + S03-2 + S04-3 + A2-1 (files 74, match 100).

## Best matching sets

| # | Set | Score | Files | Match | Why |
|---|---|---|---|---|---|
| 1 | S02-2 + S03-2 + S04-3 + A2-1 | **74** | 74 | 100 |  |
| 2 | S02-2 + S03-3 + S04-3 + A2-1 | **74** | 74 | 100 |  |
| 3 | S02-2 + S03-2 + S04-3 + A2-2 | **73** | 73 | 100 |  |

## S02 · Puddle on the soil

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| S02-2 | **73** | 79 | 40 | qwen | Biggest, clearest puddle in the centre; a drop will land well. Faint cover text on one book |
| S02-1 | **70** | 75 | 39 | qwen | Puddle reads; pot rim looks like a shallow bowl; room sharp, not out of focus |
| S02-3 | **65** | 70 | 38 | qwen | Glossy puddle, but readable lettering on the book covers |
| S02-4 | **63** | 66 | 42 | qwen | Pot fills two thirds, two puddles split the eye; book lettering |

## S03 · Moved into full sun

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| S03-2 | **73** | 75 | 60 | qwen | Sun streaks on the floor, several bleached leaves: reads 'too much sun'. Eye level, not low |
| S03-3 | **72** | 75 | 53 | qwen | One big bleached leaf, clean; less sun on the floor than S03-2 |
| S03-1 | **68** | 71 | 50 | qwen | Soft window light, one pale leaf: reads 'sunny', not 'scorched' |
| S03-4 | **64** | 66 | 53 | qwen | Plant shape looks thin and odd; light soft |

## S04 · Phone on the shelf

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| S04-3 | **71** | 75 | 46 | qwen | Medium phone on the shelf, a leaf hanging in, floral mug; screen angled, needs a perspective warp for the UI |
| S04-4 | **67** | 71 | 44 | qwen | Phone near the shelf edge, pot cut on the left; screen angled |
| S04-1 | **60** | 64 | 41 | qwen | Phone too small to carry the app screen; lots of empty floor |
| S04-2 | **58** | 60 | 44 | qwen | Phone is giant and lies on the floor: scale error |

## A2 · Static: the can, too close

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| A2-1 | **79** | 84 | 53 | qwen | Room identical to D1; the can right against the pot: the joke reads at once. Top band empty |
| A2-2 | **76** | 80 | 53 | qwen | Same room; the can a little further away, less pointed |

## What to change before the next round

- S02: 'far out of focus' did not happen with the full room in WORLD; a shot-level way to drop WORLD for macros would help.
- Book lettering still slips through on covers (not spines): widen the negative to 'lettering on books'.
- S04: the UI overlay needs a corner-pin in the edit; the phone screen is never square to the camera.

Scores: 85% Claude's eyes on the rubric in `scripts/judge.py`, 15% machine (sharpness, calm caption bands, palette pull, steadiness). A recommendation: the art director picks.
