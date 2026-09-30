# The ten stages

The same stages every time, with one named person at every gate.

AI makes the volume. A person decides every frame a viewer actually sees.
This is the Bingo Bay workflow adapted for video, where every rejected clip costs more than a rejected still.

```
DEFINE                       PRODUCE (in parallel)                     SHIP
01 Brief & hooks  ─┐         04 Keyframes ─J► 05 Motion J┐             08 Edit
02 The lock        ├──────►  06 Sound & voice            ├──────►      09 QA & platform check
03 Storyboard     ─┘         07 Copy & on-screen text   ─┘             10 Variants & iteration
                                                                            │
                         ◄──── loops back to 04–07, two cycles at most ─────┘
```
J = judge pass: Claude scores every batch and names the best matching set before a person picks.

**Rules that never move**
- One human gate per stage, with a named owner. The person there edits; they do not operate the tools.
- The lock is frozen before the first generation. Changing a token raises the version.
- Prompts are assembled from the lock (`scripts/assemble.py`), never written freehand.
- Keyframe first, motion second. Only a kept frame gets animated.
- One chain of frames: each shot starts where the last one ends (`chain: true`); a hard cut is a decision, not an accident.
- Every gate from stage 3 on shows the visual storyboard (`board.py`).
- Every generation is logged with a verdict and a reason (`iteration-log.csv`).
- Claude judges every batch before a person does (`judge.py`): a score and a reason per file, and the best matching set. People pick.
- Research before the brief: angles come from the market and the buyer's own words, not a blank prompt.
- Proof is shown, never invented: numbers and quotes only from the lock's `proof` block.
- Score before spending (`score.py`): no paid generation for a script or concept under 15/25.
- Results feed back (`perf.py`): the platform's numbers decide kill, hold or scale, and winners join the taste library.
- Two iteration cycles, then ship it or kill it.

---

## 01 · Define · Research, brief and hook angles
Research first, then the brief. Claude maps the category, then turns a 2-minute intake into a one-page brief and drafts ten hooks. The lead keeps three.

| | |
|---|---|
| **Output** | `research.md`: competitor map, saturated zones and gaps (angle and format), trust barriers, proof on hand, the customer voice bank, 7 angles ranked by gap × pain × proof with a format each. `brief.md`: the one thing, the single buyer, insight, 3 angles, what the ads do not do, mandatories, the metric and the test thresholds (`perf.yml`) |
| **Human gate** | The creative lead approves the research and the brief. One message; if it needs "and", it is two ads. |
| **Tools** | Claude, Perplexity or web search, the Meta Ad Library and TikTok Creative Center, reviews and forums for the buyer's words |
| **Automated** | Competitor scans, the voice bank, angle ranking, brief draft, hook volume |
| **Stays manual** | Framing the problem, picking the angle, setting the test thresholds with the media buyer |
| **Bottleneck** | Generic research. Every finding names its source; a line that fits any brand in the category is cut. |

## 02 · Define · The lock
Style exploration at volume, narrowed to three directions, then frozen as tokens.

| | |
|---|---|
| **Output** | `<brand>.dna.yml`: mode, tokens, palette, type, sound, end card, hero, negatives, and how the brand talks and proves: `verbal`, `proof`, `buyer`, `guardrails` |
| **Human gate** | The art director signs the lock. The highest-leverage call in the pipeline. |
| **Tools** | Claude, Higgsfield / Nano Banana / Midjourney for style frames, Figma for the direction board |
| **Automated** | Style frames, mode defaults, pre-checks (`assemble.py --check`) |
| **Stays manual** | The lock itself: mode, palette, light, camera language, the hero |
| **Bottleneck** | Decision fatigue. The shortlist is capped at three directions. |

**Modes:** `3d-stylized` · `live-action` · `ugc` · `motion-graphics`.
Switching the whole ad to another look is one line: `meta.mode`.

## 03 · Define · Script and storyboard
The shot list, beat by beat: hook, build, product, proof, payoff, end card.

| | |
|---|---|
| **Output** | `storyboard.yml` (and a Figma board if a client needs pictures) |
| **Human gate** | The creative lead checks the beats against the brief. The hook must land in 2 seconds with the sound off. |
| **Tools** | Claude, Figma, `assemble.py --check` |
| **Automated** | Beat drafts, timing sum, word counts on supers, hook position, platform length limits, and a prompt lint: movement in a keyframe, too many events for a short clip, brand names that clash with the text ban, too many scene colours, music cues leaking into SFX |
| **Stays manual** | Pacing, what the viewer feels at each beat |
| **Score gate** | `score.py`: script and hooks scored on hook, buyer language, objection, product moment, close (out of 25). 20+ produce with every hook variant; 15 to 19 one version; under 15 rewrite first. Words are cheap; clips are not. |
| **Bottleneck** | Storyboards that look finished too early. Words first, pictures at stage 4. |

## 04 · Produce · Keyframes
One still per shot, generated from the assembled prompt. Pick 1 of 8 to 12.

| | |
|---|---|
| **Output** | The hero reference (`H0`) first, then one kept keyframe per shot in `keyframes/` |
| **Human gate** | The art director curates the batch. Never the first output. |
| **Tools** | Figma Weave (Nano Banana 2 drafts, Nano Banana Pro finals), Higgsfield, Midjourney, Photoshop for paint-over |
| **Automated** | Budget for the round (`assemble.py`), batch generation, background removal, the judge pass, the log entry |
| **Stays manual** | Selection, paint-over, retouching to the lock |
| **Bottleneck** | Consistency across shots. The hero reference is approved first and attached to every hero shot. |

## 05 · Produce · Motion
Image-to-video from each kept keyframe. The prompt describes only what moves.

| | |
|---|---|
| **Output** | One kept clip per shot in `clips/` |
| **Human gate** | The art director picks per shot and checks against the lock and the previous cut. |
| **Tools** | Seedance 2.5 on Higgsfield or Figma Weave (candidates at 720p, kept clip upscaled to 1080p); Kling or Veo 3.1 as fallbacks |
| **Automated** | Clip batches, the judge pass, upscale, the log entry |
| **Stays manual** | Selection, judging physics and on-model motion |
| **Bottleneck** | Cost and morphing. Keyframes gate motion, so only approved frames get animated. |

## J · Produce · Judge pass (before every pick)
After each generation round (keyframes, clips, static plates), Claude scores every file before the art director sees the batch. It recommends; it never picks.

| | |
|---|---|
| **Output** | `judge/<round>.yml` (every score with a reason), `report.md` (round score, top 3 matching sets, ranking per shot, by model, what to fix), a scored contact sheet |
| **How** | `judge.py new` groups the files by shot and says which must match (`first_last` for a start/end frame pair, `same_set` for shots in one room). `judge.py measure` runs the machine pass. Claude opens every file and scores the rubric 1 to 5 with a note, plus the shortlisted pairs. `judge.py rank` combines them. |
| **Rubric, images** | Lock 20 · hero on model 20 · craft (AI tells) 20 · composition and caption space 15 · story beat 15 · animatable 10 |
| **Rubric, clips** | On model 20 · no morphing 20 · physics 15 · the asked movement only 20 · continuity 15 · craft 10 |
| **Score** | Per file: 85% eyes, 15% machine (sharpness, calm caption bands, palette pull, steadiness). A hard fail (text in the image, people in a people-free lock, a broken hero) scores 0. Per set: the mean of its files × how well they match. The round score is the best set's: 80+ go to the gate, 65–79 usable with the listed fixes, under 65 regenerate. |
| **Human gate** | None of its own: it feeds the stage 4 and 5 gates. The art director can overrule any score; the log keeps both. |
| **Stays manual** | Taste. The scores rank; they do not decide. |
| **Bottleneck** | Small props. Pixels barely move when a mug changes, so the machine only orders the pairs; matching props is judged by eye on the shortlist. |

## 06 · Produce · Sound and voice
Music bed, SFX and voiceover from the lock's sound tokens.

| | |
|---|---|
| **Output** | Music bed cut to length, SFX, VO, mixed to about -14 LUFS and -1 dBTP |
| **Human gate** | Audio direction clears the rights. Everything is judged on a phone speaker. |
| **Tools** | Suno for music (outside Claude); SFX from Seedance native audio (same price); voiceover with Higgsfield text-to-speech (ElevenLabs engine) |
| **Automated** | Track candidates, VO in several languages, loudness measurement |
| **Stays manual** | The mix, the cut points, rights for paid social |
| **Bottleneck** | Licensing. A pre-cleared kit per brand. |

**Static plates** are generated here too, from the same lock: one plate per ratio in `statics` (4:5, 9:16), 4 candidates each, with the headline band left empty. Same gate: the art director picks.

## 07 · Produce · Copy and on-screen text
Hooks, supers, CTAs, captions and platform primary text. Three lines per placement, one ships.

| | |
|---|---|
| **Output** | `copy-matrix.md` with every losing line and its reason; hooks tagged by mechanic and voice |
| **Human gate** | The copy lead picks and trims. Claims never ship unreviewed. |
| **Tools** | Claude with the lock's `verbal`, `buyer` and `proof` blocks and the voice bank; `copy_check.py` |
| **Automated** | Bulk drafts, hooks across 3+ mechanics and 3 voices, word-count limits, banned words, unproven numbers, hooks that start alike, locale fan-out |
| **Stays manual** | Final voice, anything legal will read |
| **Bottleneck** | Native review, done by market priority |

## 08 · Ship · Edit
Clips, sound and type come together. Type is set by hand, never generated.

| | |
|---|---|
| **Output** | The master edit in the master aspect ratio |
| **Human gate** | The editor or art director owns the cut. |
| **Tools** | CapCut, Premiere, DaVinci Resolve, After Effects for type and motion graphics |
| **Automated** | Captions draft, the edit sheet from the storyboard |
| **Stays manual** | Rhythm, cut points, type, the end card |
| **Bottleneck** | Fixing a bad clip in the edit. Send it back to stage 5 instead. |

**Statics** are set in this stage by `scripts/static_compose.py`: headline, wordmark and CTA on the kept plate, every placement size, inside each platform's safe zone, with contrast checked (WCAG AA 4.5:1, a soft scrim only when needed). Stories and TikTok get no drawn CTA, because the platform adds its own button.

## 09 · Ship · QA and platform check
Machines check first, people judge what passed.

| | |
|---|---|
| **Output** | A signed-off export for each platform |
| **Human gate** | Mandatory sign-off: art director for craft, creative lead for message, brand owner for legal |
| **Tools** | `scripts/spec_check.py` (specs, loudness, safe-zone overlays), `qa-checklist.md` |
| **Automated** | Aspect, resolution, duration, fps, loudness, true peak, file size, overlay frames |
| **Stays manual** | Creative judgement on whatever passed |
| **Bottleneck** | The review queue, the biggest jam of all. Only files with no FAIL reach a person. |

## 10 · Ship · Variants and iteration
One approved base becomes the ad matrix, then performance data picks what to fix.

| | |
|---|---|
| **Output** | `matrix.csv`, reframed exports, `perf.md` (kill / hold / scale per ad, patterns by hook, CTA and platform, a 10-variation plan per winner), and the next test batch |
| **Human gate** | Data proposes, a person decides. Someone owns the winning variant. |
| **Tools** | `scripts/matrix.py`, `scripts/crop.py` for a free 4:5 cut, Higgsfield reframe only when the crop fails, `scripts/perf.py` on the platform export, `scripts/loop.py` to test a static as a motion loop |
| **Automated** | Variant expansion, reframes, the kill / hold / scale read against the account's thresholds, fatigue, winners filed in the taste library with their numbers |
| **Stays manual** | Deciding what to fix and why |
| **Bottleneck** | Endless loops. Two cycles at most, then ship it or kill it. |

---

## Where it jams, and where it compounds

**The top four jams**
1. **The review queue.** Automated pre-checks at stage 3 and stage 9, so people only see what passed. The matrix warns past 24 variants.
2. **Consistency in motion.** The lock, one hero reference, keyframe-first, and motion-only prompts.
3. **Rights and disclosure.** Pre-cleared sound kits, likeness rules in the brief, AI labels in the QA checklist.
4. **Endless iteration.** Two cycles at most.

**Where it gets faster each time**
- **×N:** one approved base becomes hooks × CTAs × platforms.
- **LOCK:** the next campaign starts from this lock, not a blank prompt.
- **ADAPTERS:** a new tool is one block in `adapters/tools.yml`, and every prompt works in it.
- **LOG:** every verdict and reason sharpens the next lock version.
- **RESULTS:** winners go into the taste library with their numbers, so taste is checked against what performed.
- **MULTIPLY:** a winner gets ten variations (hooks, treatments, formats, proof, CTA, awareness) before any new concept.

**Credit.** The research sheet, the static format library, the score gate and the kill / hold / scale
loop adapt ideas from public guides by Dusan Radovanovic (hookandscale.io, 2026), rewritten for this
system: text set in the edit, not generated; proof only from the lock; thresholds set per account.
