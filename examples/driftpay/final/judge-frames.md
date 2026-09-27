# Judge report · Driftpay final frames

**Round score: 81 / 100, go to the gate.**
Best set: T1 + N2 + C1 (files 81, match 100).

## Best matching sets

| # | Set | Score | Files | Match | Why |
|---|---|---|---|---|---|
| 1 | T1 + N2 + C1 | **81** | 81 | 100 |  |
| 2 | T1 + N2 + C2 | **80** | 80 | 100 |  |
| 3 | T2 + N2 + C1 | **79** | 79 | 100 |  |

## T · S03 start: plane lifting off (edit of E1)

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| T1 | **82** | 85 | 66 | qwen-edit | Plane shape unchanged from E1; shadow separated from the desk reads 'just lifted'. Not near the desk edge |
| T2 | **77** | 79 | 65 | qwen-edit | Clearly airborne, but the plane widened: off model |

## N · S04 end: plane along the route (edit of M2)

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| N2 | **79** | 80 | 70 | qwen-edit | Plane moved along the thread toward the right; thread and map unchanged. Not the far end, a short glide |
| N1 | **70** | 70 | 69 | qwen-edit | Plane turned upward and left the route: gives the clip the wrong path |

## C · S05 end: coins (edit of E1)

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| C1 | **81** | 84 | 68 | qwen-edit | Tall coral and mint coin stack, the desk identical: 'paid' reads at once |
| C2 | **78** | 80 | 66 | qwen-edit | Smaller stack, a little slanted; clean |

## What to change before the next round

- Edits move objects only a little: ask for the far end by landmark (e.g. 'next to the clock on the right edge') next time.

Scores: 85% Claude's eyes on the rubric in `scripts/judge.py`, 15% machine (sharpness, calm caption bands, palette pull, steadiness). A recommendation: the art director picks.
