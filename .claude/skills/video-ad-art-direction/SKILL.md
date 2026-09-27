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
6. **Ask before spending.** Before any paid generation, state the tool, the model, the number of generations and the quoted cost, and wait for an explicit yes. Every run, including reruns. Weave quotes the exact cost when called without `acknowledgedCost`; Higgsfield takes `get_cost: true`.
7. **Two cycles, then ship or kill.** At stage 10, count the cycles. After the second, recommend ship or kill; do not start a third without the owner saying so.
8. **Judge before every pick.** After each keyframe, clip or static plate round, run the judge pass below and lead the gate with its report. You recommend; the art director picks, and can overrule any score.
9. **Specs can be out of date.** Values marked `verify: true` in `platforms/specs.yml` or `adapters/tools.yml` are not official. Say so for real client work.

## Routes: who does each job

`adapters/tools.yml` has four routes: `higgsfield-web` (the default: Nano Banana Pro, GPT Image, Seedance 2.5 through the Higgsfield connector), `own-keys` (Nano Banana Pro on the Gemini API and GPT Image on the OpenAI API via `scripts/img_api.py`, Seedance on the Higgsfield API), `weave` and `higgsfield-api`. The storyboard's `ad.route` picks one; when the user says "use the <name> route", set it there and rebuild. The prompts file opens with the route table, and the budget shows the same round on the other routes.

## The chain and the visual storyboard

- Set `chain: true` in the storyboard: every shot then starts on the previous shot's end frame, and each end frame is an edit of the frame before it (Nano Banana Pro with the previous frame as the reference). Clips always run first + last frame. Use `cut: hard` only where the story wants a jump, and say so at the storyboard gate.
- Keep `kept.yml` next to the storyboard: every kept frame id and every kept clip with its in-point. `board.py` and `cut.py` both read it.
- Show `python scripts/board.py <storyboard> -o board.html` at every gate from stage 3 on (sketch boxes before generation, frames and motion strips after), and publish it so the art director can scan it on a phone. Every join under 70% is a visible jump: fix it before the edit.

## Tools: Figma Weave and Higgsfield

Both run inside Claude. Split by strength, set in `adapters/tools.yml`:
- **Video model: Seedance 2.5** on either engine (the user's choice). Kling is the cheaper fallback; Veo 3.1 when a shot needs native sound.
- **Figma Weave:** keyframes and motion, many models behind one connector, and saved Weave workflows the art director can open and adjust visually. Needs a paid Weave plan.
- **Higgsfield:** the cheaper route for Seedance (about 28 credits per 4s 720p clip against about 168 on Weave), and the only one that takes the hero as an extra reference in motion. Also reframe and outpaint, Marketing Studio, the virality predictor, TikTok publishing.
- If one has no credits, use the other and say so.

## Higgsfield API route (scripts/hf_api.py)

When the environment has the Higgsfield API credential connected (or HF_KEY is set):
- Always `python scripts/hf_api.py estimate <model> -i body.json` first and show the dollar amount; submit with `run ... --yes` only after the user approves that amount. `--max-usd` may cover a batch the user approved as a whole.
- Every submission is logged to `runs.jsonl` before polling. Set `HF_RUNS_LOG=<project>/runs.jsonl` so each project keeps its own log; copy each verdict into the project's `iteration-log.csv`.
- Keyframes: `higgsfield-ai/soul/v2/standard` or `alibaba/qwen-image-3/text-to-image` (Nano Banana Pro is not on the API). Motion: `bytedance/seedance-2.5/image-to-video` with the kept keyframe's output URL as `image_url` (and `end_image_url` for first/last-frame shots), 480p for candidates, 720p for finals (the API has no 1080p).
- Never resubmit a generation after an ambiguous timeout; check the dashboard first.

## Getting the files

Generations live on Higgsfield and appear in the chat widget. This cloud environment's network policy blocks the media hosts (checked 2026-09-26), so files cannot be downloaded into the repo here. Either the user downloads the kept files and runs the scripts locally, or the user adds Higgsfield's media host, `d1xarpci4ikg0w.cloudfront.net` (seen in its result URLs, 2026-09-26), to the environment's allowed domains. API results come from a different host, `d3u0tzju9qaucj.cloudfront.net` (seen 2026-09-26); allow it too. Until then, build a contact sheet page from the output URLs in `runs.jsonl`: the user's browser can load them even when this container cannot. Output URLs expire after about 7 days, so download kept files before then. The log still records job IDs, which is all that later generations need (keyframe job IDs feed motion, clip job IDs feed upscale).

## Judge pass (scripts/judge.py)

Runs between generation and the gate in stages 4 and 5 and for static plates. It needs the files on disk (see Getting the files).
1. `judge.py new judge/<round>.yml --lock <lock> G="glob" ... --label G="what it is" --pair A:B:first_last|same_set`. One group per shot. `first_last` for a start/end frame pair (framing must match); `same_set` for shots in one room (pot, props, light must match).
2. `judge.py measure judge/<round>.yml`: the machine pass, plus a 5-frame strip per clip.
3. Open every file (clips: open the strip) with the Read tool and fill `scores` with 1 to 5 per rubric criterion and a one-line note that names what you saw. Then fill `pair_scores` for the pairs it lists: name any prop, pot, surface or light change. Add `fail: "<reason>"` for a hard fail: text or letters in the image, people or body parts when `people: false`, a broken hero, the wrong ratio.
   - Never score a file you have not opened. Score what you see, not the machine numbers, and not the model you expect to win.
   - Use the whole scale: 3 is usable, 5 is ready for a client.
4. Add `fixes`: the prompt or lock changes that would lift the weakest criterion (they feed the next lock version).
5. `judge.py rank judge/<round>.yml -o judge/<round>.md --sheet judge/<round>.html`. Lead the gate with the round score and band, the top 3 sets with why, and the fixes; send the sheet. Log the scores next to the verdicts in `iteration-log.csv`.

## Start

- New project: `python scripts/new_project.py <brand> <campaign> --mode <mode>`. This creates `projects/<brand>-<campaign>/`.
- Existing project: read its brief, lock, storyboard and log first, and find the first stage without an approval.
- Worked example: `examples/sunpeel/`.

Modes: `3d-stylized`, `live-action`, `ugc`, `motion-graphics` (see `lock/modes/`).

## Stage by stage

**01 Brief and hooks.** Ask the intake questions from `templates/brief.md` in one message (brand, product, platforms, lengths, mode, the one thing, audience, mandatories, metric). Fill `brief.md`. Draft 10 hook angles, each with a first frame that reads with the sound off. The lead keeps 3.
→ Gate: creative lead.

**02 The lock.** Propose 3 directions in words: mode, world, light, palette, camera and motion language. If the user wants pictures, generate style frames per direction on GPT Image 2.5 medium (`draft_params`, 0.5 credits each). Write the chosen direction into `<brand>.dna.yml`, set only the tokens that differ from the mode, and define the hero. Run `assemble.py --check`.
→ Gate: art director signs the lock.

**03 Storyboard.** Write `storyboard.yml` (with `chain: true` and an `end_subject` on every shot): beats, durations, subject (the [SHOT] slot), action, camera move, supers, sound, variants. Quote every line in `variants`. Run `assemble.py --check` and fix every FAIL. Fix every prompt-lint WARN (movement in a keyframe subject, more than 2 movements per short clip, brand name vs the text ban, too many scene colours, a music cue with no `sfx`), or explain why it stays. Then read the assembled prompts once, whole, as the model will: the lint catches patterns, not contradictions.
→ Gate: creative lead.

**04 Keyframes.** Run `assemble.py <storyboard> -o prompts.md` and show its **Budget** table first; that is the spend being approved. Generate the `H0` hero reference first: 8 to 12 candidates. When the hero is kept, set `hero.reference` in the lock and attach it to every `hero: true` shot.
- Figma Weave (the default engine): `weave_find_model` for the model named in `adapters/tools.yml` → `weave_run_model` without `acknowledgedCost` to get the quote → ask Approve/Cancel with a structured question → run with the quoted cost → `weave_get_model_run_output` → download with the curl command it returns into `keyframes/`. Drafts on Nano Banana 2, finals on Nano Banana Pro.
- Higgsfield: check `balance` first. Keyframes on Nano Banana Pro with `image_params` from `adapters/tools.yml`; on hero shots attach the hero reference as `image_references`. `generate_image_batch` → `jobs_wait` → `show_generation_by_ids`.
- First hero round is an A/B: 4 Nano Banana Pro + 4 GPT Image 2.5 (high, 2K, Sunburst), shown side by side and numbered. The winner is logged with its reason and becomes the keyframe model for the project.
- Another tool: give the user the prompt block for that tool from `prompts.md`, and log what they report back.
- Run the judge pass. Show every candidate side by side, with its number and score, and the best matching set, before asking for a pick.
→ Gate: art director picks 1 per shot.

**05 Motion.** For each kept keyframe, use the `-M` motion prompt for the chosen tool. The keyframe is the start frame. The prompt says only what moves.
- Seedance 2.5 settings: 4 seconds minimum (trim in the edit), 720p for candidates, sound off (`generate_audio: false`, sound is stage 6), 9:16.
- Higgsfield: `generate_video_batch` with the `video_params` in `adapters/tools.yml`: `mode: omni_reference`, the kept keyframe as `start_image`, and on hero shots the hero reference as `image_references`. Then `jobs_wait` and `show_generation_by_ids`.
- Figma Weave: Seedance 2.5 image-to-video, the kept keyframe as First Frame. Same quote → approve → run loop as stage 4.
- Submit batches of at most 6 videos and 8 images (the Plus plan's parallel limit).
- After the pick, upscale only the kept clip to 1080p (Higgsfield `upscale_video`, provider `topaz`, resolution `1080p`). Never re-render it at 1080p: without a seed the motion changes. Upscale has no price preview: say so, and ask before running it.
- Run the judge pass on the clips (the clip rubric: on model, morphing, physics, the asked movement, continuity, craft). Log the verdicts.
→ Gate: art director picks 1 per shot.

**06 Sound.** Higgsfield has no music or general SFX model inside Claude (its audio tool is speech only).
- Music: write a Suno prompt from `lock.sound` (genre, bpm, instruments, length close to the ad, instrumental, set bar count). The user runs it in Suno and shares the file.
- SFX: already in the Seedance clips (`generate_audio` is on, same price); the motion prompts carry each shot's sound cue. Keep or mute per shot in the edit.
- Voiceover: Higgsfield `generate_audio` (`text2speech_v2`, variant `elevenlabs`) from the approved VO lines.
- Mix target: about -14 LUFS, true peak at or below -1 dBTP.
→ Gate: audio direction, including rights for paid social.

**Static plates (with stage 4).** For each item in `statics`, generate the `A#-<ratio>` plate prompts from `prompts.md` on the keyframe model, 4 candidates per ratio, with the hero reference on hero statics. Plates carry no text: the headline band stays empty. Judge pass, then the same gate as keyframes.

**07 Copy.** Fill `copy-matrix.md`: 3 lines per placement, word limits from `lock.type`. Static headlines: at most 7 words and 40 characters (checked by `--check`). Keep the losing lines and their reasons. Flag every claim for legal.
→ Gate: copy lead.

**08 Edit.** Statics: `python scripts/static_compose.py <storyboard> A1 --plate 4:5=<kept> --plate 9:16=<kept> [--font <brand font>]` writes every placement size with headline, wordmark and CTA inside the safe zones. On Stories and TikTok it leaves the CTA out (the platform adds its own) and keeps the headline in the top band. Show the results side by side; the art director can refine them in Figma. Video: `python scripts/cut.py <storyboard> --clip S01=<kept clip>@<in> ... -o master.mp4` cuts the master: each shot trimmed to its length, supers set in the top safe band from the lock, the end card drawn from the lock, loudness to target. Add `--aspect 4:5` for the feed cut (supers move into its safe zone; never crop a finished master with supers). Choose in-points by looking at the clip frame by frame. Type and end cards are made in the edit, never generated.
→ Gate: editor / art director.

**09 QA.** For every export, video or static: `python scripts/spec_check.py <file> --platform <ids> --overlay`. Show the overlay PNGs to the art director, then walk `qa-checklist.md`. Only files with no FAIL go to human review.
→ Gate: craft, message, brand/legal sign-off.

**10 Variants and iteration.** Run `python scripts/matrix.py <storyboard> -o matrix.csv`. For 4:5, crop the 9:16 master for free: `python scripts/crop.py master.mp4 4:5` (it checks the safe area survives). Use Higgsfield `reframe` (about 138 credits for 15s at 1080p, quote first) only when the crop fails, as it does for 1:1. After results come in, propose what to change and why. Count the cycle.
→ Gate: the owner of the winning variant.

## How to report at a gate

End each stage with exactly this:
- **Made:** the files, in one line.
- **Checks:** the PASS / WARN / FAIL summary, and the judge round score when the stage generated files.
- **Decision needed:** the one question for the gate owner, with your recommendation.
