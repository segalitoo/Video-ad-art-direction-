# Judge report · Driftpay test frames (lock v1.0)

**Round score: 87 / 100, go to the gate.**
Best set: D2 + E1 + M2 (files 87, match 100).

## Best matching sets

| # | Set | Score | Files | Match | Why |
|---|---|---|---|---|---|
| 1 | D2 + E1 + M2 | **87** | 87 | 100 | first_last 100 (eyes: Only the invoice changed into the plane; everything else identical) |
| 2 | D2 + E1 + M1 | **81** | 81 | 100 | first_last 100 (eyes: Only the invoice changed into the plane; everything else identical) |
| 3 | D2 + E2 + M2 | **79** | 79 | 100 | first_last 100 (eyes: Identical desk; plane shape weaker) |

## D · S01 desk, invoice (S02 start)

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| D2 | **81** | 84 | 66 | qwen | One coral stripe, curled corner, laptop and cup behind, calm lower third. Reads 'handmade' at once |
| D1 | **72** | 71 | 73 | qwen | Real paper under real light; two coral stripes where the lock says one; invoice fills the lower third |

## E · S02 end: folded plane, edited from D2

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| E1 | **89** | 94 | 61 | qwen-edit | Classic paper dart, stripe along the wing; desk, laptop, cup and window identical to D2 |
| E2 | **67** | 68 | 62 | qwen-edit | Odd plane shape, the stripe shrank to a patch |

## M · S04 plane over the map

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| M2 | **90** | 94 | 67 | qwen | Clean ruled lines only, clocks with hands and no numerals, coral thread route; reads as the world at once |
| M1 | **74** | 75 | 69 | qwen | Big, dramatic plane on the route; faint pseudo-characters on the wing; map fills the lower third |

## By model

| Model | Files | Mean | Best | Fails |
|---|---|---|---|---|
| qwen | 4 | 79 | 90 | 0 |
| qwen-edit | 2 | 78 | 89 | 0 |

## What to change before the next round

- Say 'one thin coral stripe' in the S01 subject so every candidate matches the hero.
- The edit dropped the invoice's ruled lines from the plane; fine at this size, note for close-ups.

Scores: 85% Claude's eyes on the rubric in `scripts/judge.py`, 15% machine (sharpness, calm caption bands, palette pull, steadiness). A recommendation: the art director picks.
