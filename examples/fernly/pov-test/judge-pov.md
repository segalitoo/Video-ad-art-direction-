# Judge report · Fernly POV rescue test

**Round score: 61 / 100, regenerate.**
Best set: W3 + F1 + R1 (files 61, match 100).

## Best matching sets

| # | Set | Score | Files | Match | Why |
|---|---|---|---|---|---|
| 1 | W3 + F1 + R1 | **61** | 61 | 100 |  |
| 2 | W1 + F1 + R1 | **57** | 57 | 100 |  |

## W · Worm's-eye view

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| W3 | **67** | 68 | 65 | soul | Grittier phone look, floor-level angle looking up a little; still a side view of the plant, not from it |
| W1 | **54** | 52 | 65 | qwen | Closest to a POV: leaves overhang the lens, soil at the bottom edge. But a second monstera stands mid-frame, so it reads 'watching another plant' |
| W2 | 0 | – | 54 | soul | FAIL: Instagram or TikTok interface with usernames drawn into the image |
| W4 | 0 | – | 53 | soul | FAIL: Instagram or TikTok interface with usernames drawn into the image |
| W5 | 0 | – | 68 | soul | FAIL: Instagram or TikTok interface with usernames drawn into the image |

## F · Phone lying on the soil, 0.5x

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| F1 | **62** | 62 | 62 | qwen | Side view, the can huge in the foreground; no POV |
| F2 | 0 | – | 60 | soul | FAIL: Instagram or TikTok interface with usernames drawn into the image |
| F3 | 0 | – | 59 | soul | FAIL: Instagram or TikTok interface with usernames drawn into the image |
| F4 | 0 | – | 54 | soul | FAIL: Instagram or TikTok interface with usernames drawn into the image |
| F5 | 0 | – | 57 | soul | FAIL: Instagram or TikTok interface with usernames drawn into the image |

## R · Pot rim in the foreground

| File | Overall | Eyes | Machine | Model | Note |
|---|---|---|---|---|---|
| R1 | **53** | 52 | 57 | qwen | Pot rim and soil in the foreground, but it is a second pot: the hand waters a different plant behind |
| R2 | 0 | – | 59 | soul | FAIL: Instagram or TikTok interface with usernames drawn into the image |
| R3 | 0 | – | 70 | soul | FAIL: Instagram or TikTok interface with usernames drawn into the image |
| R4 | 0 | – | 54 | soul | FAIL: Instagram or TikTok interface with usernames drawn into the image |
| R5 | 0 | – | 58 | soul | FAIL: Instagram or TikTok interface with usernames drawn into the image |

## By model

| Model | Files | Mean | Best | Fails |
|---|---|---|---|---|
| qwen | 3 | 57 | 62 | 0 |
| soul | 12 | 67 | 67 | 11 |

## What to change before the next round

- The plant's-eye view is out of reach for these image models: 0 of 22 frames across both tests. Qwen reads 'from inside the pot' as a second pot.
- Soul 2 ignores inline negatives for app interfaces: 11 of 12 images drew a Stories screen. Do not use Soul 2 for UGC-styled prompts.
- Recommendation: stop the Fernly POV route; test Driftpay.

Scores: 85% Claude's eyes on the rubric in `scripts/judge.py`, 15% machine (sharpness, calm caption bands, palette pull, steadiness). A recommendation: the art director picks.
