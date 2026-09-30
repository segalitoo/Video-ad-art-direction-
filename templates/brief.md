# Video ad brief · <brand> · <campaign>

> Stage 1 output. One page. The creative lead approves it before the lock is written.
> Claude drafts it from a 2-minute intake and `research.md`. The lead edits and approves it;
> nobody writes it from a blank page.

| Field | Value |
|---|---|
| Brand / product | |
| Campaign | |
| Requester | |
| Deadline | |
| Budget (generation credits) | |
| Platforms | TikTok · Reels/Stories · Shorts · Meta feed · LinkedIn |
| Lengths | 6s · 15s · 30s |
| Style mode | 3d-stylized · live-action · ugc · motion-graphics |
| Awareness level | cold · problem-aware · solution-aware · most-aware |

## 1. The one thing
One sentence the viewer should remember. If it needs "and", it is two ads.

## 2. The single buyer
One person, not a segment. "A 34-year-old freelancer who lost a week of pay to a bank transfer",
not "SMBs 25 to 45". Their pain, their dream outcome and their top objection, in their own words
(from the voice bank in `research.md`). These go into the lock's `buyer` block.

## 3. Insight
The true tension the ad plays on. One line.

## 4. Angles (from research.md, top three by rank)
| # | Angle | Rank (gap × pain × proof) | Format | First frame, sound off | Why it stops the scroll |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

## 5. What these ads do not do
Guardrails: claims we cannot prove, words the brand never says, tones and colours that are off-brand.
These go into the lock's `guardrails` block, and the pre-checks enforce them.

## 6. Mandatories
Logo rules, legal lines, claims that need proof, music rights, talent or likeness rules, AI disclosure.

## 7. Success metric and test rules
One metric judges the test: hook rate (3s views / impressions), hold rate, CTR, or cost per result.
The kill, hold and scale thresholds for this account go into `perf.yml` (see `templates/perf.yml`);
`scripts/perf.py` applies them to the platform export. Set them here with the media buyer, not from defaults.

| | Value |
|---|---|
| Target cost per result | |
| Minimum spend before any call | |
| Kill at 24 h if | |
| Scale if | |

## 8. References
Links to 3 to 5 reference ads. For each one, write what to take from it (pace, framing, type), not "like this".

## Approval
- [ ] Creative lead approved · name · date
