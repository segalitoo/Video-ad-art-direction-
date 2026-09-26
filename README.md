# Video ad art direction

A system for art directing social video ads with Claude.
AI makes the volume at every stage. A named person signs off each one.

It extends the [Bingo Bay AI production workflow](https://segalitoo.github.io/ran-portfolio/work/ai-workflow.html) from stills to video: the same lock, the same human gates, the same iteration log, plus what video needs (time, motion, sound, platform rules).

**Platforms:** TikTok · Instagram/Facebook Reels and Stories · YouTube Shorts · Meta feed · LinkedIn
**Looks:** 3D stylized · live action · UGC · motion graphics
**Tools:** any. One master prompt, adapted for Figma Weave and Higgsfield (both inside Claude), Nano Banana, Midjourney, Veo in Google Flow, Kling, Runway, Suno, ElevenLabs. You can add more.

**Inside Claude, two engines split by strength.** The video model is **Seedance 2.5**, on either engine. Figma Weave runs keyframes and motion behind one connector and keeps the lock as a saved workflow the art director can open. Higgsfield is the cheaper route for Seedance, holds the hero as an extra reference in motion, and also reframes, runs Marketing Studio, predicts virality and publishes to TikTok. Every paid run is quoted and approved first; `assemble.py` prints the budget for a full round before stage 4.

## How it works

```
DEFINE                      PRODUCE (in parallel)                SHIP
01 Brief & hooks            04 Keyframes → 05 Motion             08 Edit
02 The lock                 06 Sound & voice                     09 QA & platform check
03 Storyboard               07 Copy & on-screen text             10 Variants & iteration
```

Ten stages, one human gate each, two iteration cycles at most. Full detail: [`workflow/stages.md`](workflow/stages.md).

Five ideas carry the whole system:
1. **The lock.** The look is written as tokens before the first generation (`<brand>.dna.yml`). A moodboard gets interpreted; a token gets pasted.
2. **Assembled prompts.** `STYLE + [SHOT] + WORLD + FORM + LIGHT + GRADE + PALETTE + TECH + FRAME`. Only the bracketed slot changes between shots, so every shot reads as one film.
3. **Keyframe first.** Each shot starts as a still (pick 1 of 8 to 12). Only a kept frame gets animated, and its motion prompt says only what moves. This keeps paid video generations low.
4. **Machines check first.** Pre-checks on the storyboard, and spec checks on every export, so people only review what passed.
5. **Everything logged.** Each generation records its verdict, reason and lock version.

## Using it with Claude

This repo includes a Claude skill: [`.claude/skills/video-ad-art-direction`](.claude/skills/video-ad-art-direction/SKILL.md).
In Claude Code, open this repo and say *"new video ad for …"*. Claude runs the stages and stops at every gate for your approval.
To use it in the Claude app, zip the skill folder and upload it as a custom skill in the app settings.

## Using the scripts

```bash
pip install -r requirements.txt            # PyYAML; spec_check also needs ffmpeg

python scripts/new_project.py acme spring-launch --mode ugc      # scaffold projects/acme-spring-launch/
python scripts/assemble.py <storyboard.yml> --check              # stage 3 pre-checks
python scripts/assemble.py <storyboard.yml> -o prompts.md        # every prompt, for every tool
python scripts/matrix.py   <storyboard.yml> -o matrix.csv        # hooks × CTAs × platforms
python scripts/crop.py master.mp4 4:5                           # free 4:5 feed cut, checks the safe area
python scripts/spec_check.py export.mp4 --platform tiktok --overlay   # stage 9 QA
bash scripts/selftest.sh                                         # test everything
```

## What is in the repo

| Path | What it is |
|---|---|
| `workflow/stages.md` | The ten stages: output, gate owner, tools, automated / manual, bottleneck |
| `lock/_template.dna.yml` | The lock template |
| `lock/modes/` | Defaults for the four looks. A lock picks one and overrides what it needs |
| `platforms/specs.yml` | Ratios, lengths, safe zones and loudness per platform, with sources |
| `adapters/tools.yml` | How each tool wants its prompt (negatives, aspect, clip length) |
| `templates/` | Brief, storyboard, copy matrix, QA checklist, iteration log |
| `scripts/` | Scaffold, assemble, matrix, spec check, self-test |
| `examples/sunpeel/` | The pilot: a fictional zero-sugar citrus soda |
| `docs/brief-generator.html` | Intake form that writes the brief, lock and storyboard ([live](https://claude.ai/artifact/DvdWpJVGGaiz4g3wWVT6h6)) |
| `docs/plan.html` | The plan as a page, in the portfolio design system ([live](https://claude.ai/artifact/HQm6PR8irg3vVe4BnLf99o)) |

## Honest limits

- **Specs change.** Values marked `verify: true` come from third-party guides, not official numbers (checked 2026-09-25). Check them against the platform's own template before a client delivery.
- **Tool facts change faster.** Clip lengths and parameters in `adapters/tools.yml` are marked the same way.
- **A mode swaps the look, not the story.** One line switches Sunpeel from 3D to live action, but a UGC ad needs its own storyboard: a creator talking to camera, not bubbles forming a can.
- **The sound check measures; it does not listen.** Loudness and peak are checked. Whether the loop grates on the fortieth play is still a person's call.
