# Driftpay · Paper planes · delivery

A 15-second paper-craft ad for a fictional cross-border payments app, made end to end with
this system on the Higgsfield API: Qwen Image 3 frames and edits, Seedance 2.5 clips,
cut, typeset and checked by the scripts in this repo.

## Files

| File | Where it runs | Checks |
|---|---|---|
| `deliver/driftpay-paper-planes_9x16.mp4` | Reels, Stories, LinkedIn (vertical) | spec_check PASS: 1080x1920, 24 fps, 14.98 s, -14.8 LUFS, -2.8 dBTP |
| `deliver/driftpay-paper-planes_4x5.mp4` | Meta feed, LinkedIn feed | spec_check PASS: 1080x1350, same sound |
| `statics/A1_*` | LinkedIn 1200x1200 and 1200x628, Meta feed 1:1 and 4:5 | spec_check PASS |
| `statics/A2_*` | Stories 9:16, Meta feed 4:5 and 1:1 | spec_check PASS |
| `qa/` | Safe-zone overlays for the hook and end frames, one frame per shot | for the art director |

## The cut

| Shot | Seconds | Clip, in-point | Super | Judge |
|---|---|---|---|---|
| S01 hook | 2 | S01 720p @ 0 | Your invoice is leaving. | 94 |
| S02 fold | 3 | S02 720p @ 0.9 | Sent to a client 6,000 km away. | 82 |
| S03 take-off | 2.5 | S03 720p @ 1.0 | No three-day wait. | 91 |
| S04 the map | 3.5 | S04 720p @ 0.3 | Across time zones, same day. | 84 |
| S05 payoff | 2.5 | S05 720p @ 1.54 | Paid in 1 day. | 70 |
| S99 end card | 1.5 | drawn from the lock | Driftpay. Get paid like it's local. | |

Built with:
```bash
python scripts/cut.py examples/driftpay/storyboard.yml \
  --clip S01=out/S01.seedance720.mp4@0 --clip S02=out/S02.seedance720.mp4@0.9 \
  --clip S03=out/S03.seedance720.mp4@1.0 --clip S04=out/S04.seedance720.mp4@0.3 \
  --clip S05=out/S05.seedance720.mp4@1.54 --font DejaVuSans-Bold.ttf -o deliver/..._9x16.mp4   # add --aspect 4:5 for the feed cut
```

## What it cost (Higgsfield API, list prices; the account has no discount)

| Step | Spend |
|---|---|
| Go/no-go test: 6 frames, 2 clips at 480p | $2.09 |
| Final: 7 edits, 5 clips at 720p | $9.85 |
| **Driftpay total** | **$11.94** |

One edit ($0.075) was wasted: a storyboard change failed its check, the command chain did not stop,
and the edit ran with the old prompt. Commands that spend now run with `set -e`.

## Before real use

- **Font:** Space Grotesk could not be downloaded here; type is set in DejaVu Sans Bold. Re-run `cut.py` and `static_compose.py` with `--font SpaceGrotesk-Medium.ttf`.
- **Music:** the sound is Seedance's own paper foley; the lock's pizzicato bed (Suno) is not in yet.
- **Claims:** "Paid in 1 day", "same day" and "free account" go to legal first.
- **S05** dissolves the plane into falling coins instead of unfolding it: a magic beat, judged 70.
- **AI label** where the platform requires it.
