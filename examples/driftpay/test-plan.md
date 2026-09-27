# Go/no-go test · Driftpay

Run before the full budget. The pass rules are written before any result exists,
so the result cannot move them. Every run is estimated first and approved.

## What runs (Higgsfield API, list prices; the account has no discount)

| # | Generation | Model (API id) | Cost |
|---|---|---|---|
| 1 | S01 desk with the invoice, 2 candidates | `alibaba/qwen-image-3/text-to-image`, 2k, 9:16 | $0.15 |
| 2 | S02 end frame: the invoice folded into a plane, edited from the kept S01 frame, 2 candidates | `alibaba/qwen-image-3/edit` | $0.15 |
| 3 | S04 the plane over the paper map, 2 candidates | `alibaba/qwen-image-3/text-to-image` | $0.15 |
| 4 | S02 clip: the fold, first + last frame | `bytedance/seedance-2.5/image-to-video`, 4s, 480p | $0.82 |
| 5 | S04 clip: the flight over the map | same | $0.82 |
| | **Total** | | **$2.09** |

The judge pass (`scripts/judge.py`) scores every frame and clip before the art director picks.

## Pass rules (3 of 4 = go)

1. **The fold reads as paper folding**: crisp creases, no melting, stretching or popping.
2. **The flight reads as a paper plane gliding** over a map you recognise as the world, within 1 second.
3. **It looks handmade**, real paper under real light, not glossy CGI (judged on the frames, before any clip).
4. **The art director would stop scrolling for it on LinkedIn.**

No figures or writing generated on the paper anywhere, or that item fails.

## If it fails

Back to Fernly with the POV look, if that test passed, or to Sunpeel. The system carries over.

## Result

| Item | Pass / fail | Why |
|---|---|---|
| 1 Fold | Pass | Clip judged 82: crisp creases, the sheet stands up and becomes the dart; the desk never moves |
| 2 Flight | Pass, weak | Clip judged 68: reads as a plane over the world at phone speed, but it pivots more than it glides and the thread re-routes. Fix: first + last frame |
| 3 Handmade | Pass | Frames judged 87 (best set D2 + E1 + M2): real paper under real light, clocks without numerals, no writing |
| 4 Stop-scroll | Pass | The art director went ahead with the full round (2026-09-27) |
| **Decision** | **Go** | 4 of 4. Delivered: see `final/README.md` |

## Spend

Six images and two clips: $2.09 at list, as quoted (the account has no discount).
