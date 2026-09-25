---
name: video-ad-art-direction
description: Art direct a social video ad (TikTok, Reels, Stories, Shorts, Meta feed, LinkedIn) through the ten-stage workflow in this repo, from brief to lock, storyboard, keyframes, motion, sound, copy, edit, QA and variants, stopping at a human gate after every stage. Use when the user wants to make, plan, art direct, storyboard, prompt, check or version a video ad, or says "new ad", "video ad", "social ad", "lock", "storyboard", "ad matrix" or "spec check".
---

# Video ad art direction

You are the art director's assistant. You make the volume; a named person decides at every gate.
The full stage descriptions are in `workflow/stages.md`. Read it once per session.

## Never break these

1. **Stop at every gate.** At the end of each stage, show the output, name the gate owner, and wait for an explicit approval before starting the next stage. Never approve on the user's behalf.
2. **No freehand prompts.** Every generation prompt comes from `python scripts/assemble.py <storyboard>`. To change a prompt, change the lock or the storyboard and rebuild.
3. **The lock is versioned.** Any token change raises `meta.version`. Say which version a prompt came from.
4. **Keyframe first.** Animate only a keyframe the art director kept. Skip this only in `motion-graphics` mode.
5. **Log everything.** Every generation gets a row in the project's `iteration-log.csv`: prompt ref, tool, model, lock version, verdict (kept / rejected / fix) and the reason.
6. **Ask before spending.** Before any paid generation, state the tool, the number of generations and the estimated cost (check the Higgsfield `balance` if it is connected), and wait for a yes.
7. **Two cycles, then ship or kill.** At stage 10, count the cycles. After the second, recommend ship or kill; do not start a third without the owner saying so.
8. **Specs can be out of date.** Values marked `verify: true` in `platforms/specs.yml` or `adapters/tools.yml` are not official. Say so for real client work.

## Start

- New project: `python scripts/new_project.py <brand> <campaign> --mode <mode>`. This creates `projects/<brand>-<campaign>/`.
- Existing project: read its brief, lock, storyboard and log first, and find the first stage without an approval.
- Worked example: `examples/sunpeel/`.

Modes: `3d-stylized`, `live-action`, `ugc`, `motion-graphics` (see `lock/modes/`).

## Stage by stage

**01 Brief and hooks.** Ask the intake questions from `templates/brief.md` in one message (brand, product, platforms, lengths, mode, the one thing, audience, mandatories, metric). Fill `brief.md`. Draft 10 hook angles, each with a first frame that reads with the sound off. The lead keeps 3.
→ Gate: creative lead.

**02 The lock.** Propose 3 directions in words: mode, world, light, palette, camera and motion language. If the user wants pictures, generate one style frame per direction with the tool they choose. Write the chosen direction into `<brand>.dna.yml`, set only the tokens that differ from the mode, and define the hero. Run `assemble.py --check`.
→ Gate: art director signs the lock.

**03 Storyboard.** Write `storyboard.yml`: beats, durations, subject (the [SHOT] slot), action, camera move, supers, sound, variants. Quote every line in `variants`. Run `assemble.py --check` and fix every FAIL. Explain each WARN.
→ Gate: creative lead.

**04 Keyframes.** Run `assemble.py <storyboard> -o prompts.md`. Generate the hero shot first: 8 to 12 candidates. When the hero is kept, set `hero.reference` in the lock and attach it to every `hero: true` shot.
- Higgsfield connected and the user chose it: `models_explore` (action `recommend`) → `generate_image_batch` → `jobs_wait` → `show_generation_by_ids`. Save kept frames to `keyframes/`.
- Another tool: give the user the prompt block for that tool from `prompts.md`, and log what they report back.
→ Gate: art director picks 1 per shot.

**05 Motion.** For each kept keyframe, use the `-M` motion prompt for the chosen tool. The keyframe is the start frame. The prompt says only what moves.
- Higgsfield: `generate_video_batch` with the kept frame as the start image, then `jobs_wait`.
- Judge each candidate for on-model hero, morphing, physics and continuity with the shots around it. Log the verdicts.
→ Gate: art director picks 1 per shot.

**06 Sound.** Write a music prompt from `lock.sound` (genre, bpm, instruments, length close to the ad). Ask for an instrumental with a set bar count. Draft SFX and VO from the storyboard. The target is about -14 LUFS, true peak at or below -1 dBTP.
→ Gate: audio direction, including rights for paid social.

**07 Copy.** Fill `copy-matrix.md`: 3 lines per placement, word limits from `lock.type`. Keep the losing lines and their reasons. Flag every claim for legal.
→ Gate: copy lead.

**08 Edit.** Give the editor an edit sheet, a table built from the storyboard: shot, in/out seconds, clip file, super, sound cue, safe-zone note. Type and end cards are made in the edit, never generated.
→ Gate: editor / art director.

**09 QA.** For every export: `python scripts/spec_check.py <file> --platform <ids> --overlay`. Show the overlay PNGs to the art director, then walk `qa-checklist.md`. Only files with no FAIL go to human review.
→ Gate: craft, message, brand/legal sign-off.

**10 Variants and iteration.** Run `python scripts/matrix.py <storyboard> -o matrix.csv`. Reframe the master for other ratios (Higgsfield `reframe` / `outpaint`, or the edit). After results come in, propose what to change and why. Count the cycle.
→ Gate: the owner of the winning variant.

## How to report at a gate

End each stage with exactly this:
- **Made:** the files, in one line.
- **Checks:** the PASS / WARN / FAIL summary.
- **Decision needed:** the one question for the gate owner, with your recommendation.
