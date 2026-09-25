# The ten stages

The same stages every time, with one named person at every gate.

AI makes the volume. A person decides every frame a viewer actually sees.
This is the Bingo Bay workflow adapted for video, where every rejected clip costs more than a rejected still.

```
DEFINE                       PRODUCE (in parallel)                     SHIP
01 Brief & hooks  ─┐         04 Keyframes ──► 05 Motion ─┐             08 Edit
02 The lock        ├──────►  06 Sound & voice            ├──────►      09 QA & platform check
03 Storyboard     ─┘         07 Copy & on-screen text   ─┘             10 Variants & iteration
                                                                            │
                         ◄──── loops back to 04–07, two cycles at most ─────┘
```

**Rules that never move**
- One human gate per stage, with a named owner. The person there edits; they do not operate the tools.
- The lock is frozen before the first generation. Changing a token raises the version.
- Prompts are assembled from the lock (`scripts/assemble.py`), never written freehand.
- Keyframe first, motion second. Only a kept frame gets animated.
- Every generation is logged with a verdict and a reason (`iteration-log.csv`).
- Two iteration cycles, then ship it or kill it.

---

## 01 · Define · Brief and hook angles
Claude turns a 2-minute intake into a one-page brief and drafts ten hook angles. The lead keeps three.

| | |
|---|---|
| **Output** | `brief.md`: the one thing, audience, insight, 3 hook angles, mandatories, success metric |
| **Human gate** | The creative lead approves the brief. One message; if it needs "and", it is two ads. |
| **Tools** | Claude, Perplexity or web search for trend and competitor scans, the Meta Ad Library and TikTok Creative Center for references |
| **Automated** | Brief draft, hook volume, reference scans |
| **Stays manual** | Framing the problem, picking the angle |
| **Bottleneck** | Vague briefs. Claude asks the intake questions until every field is filled. |

## 02 · Define · The lock
Style exploration at volume, narrowed to three directions, then frozen as tokens.

| | |
|---|---|
| **Output** | `<brand>.dna.yml`: mode, tokens, palette, type, sound, end card, hero, negatives |
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
| **Automated** | Beat drafts, timing sum, word counts on supers, hook position, platform length limits |
| **Stays manual** | Pacing, what the viewer feels at each beat |
| **Bottleneck** | Storyboards that look finished too early. Words first, pictures at stage 4. |

## 04 · Produce · Keyframes
One still per shot, generated from the assembled prompt. Pick 1 of 8 to 12.

| | |
|---|---|
| **Output** | The hero reference (`H0`) first, then one kept keyframe per shot in `keyframes/` |
| **Human gate** | The art director curates the batch. Never the first output. |
| **Tools** | Figma Weave (Nano Banana 2 drafts, Nano Banana Pro finals), Higgsfield, Midjourney, Photoshop for paint-over |
| **Automated** | Budget for the round (`assemble.py`), batch generation, background removal, the log entry |
| **Stays manual** | Selection, paint-over, retouching to the lock |
| **Bottleneck** | Consistency across shots. The hero reference is approved first and attached to every hero shot. |

## 05 · Produce · Motion
Image-to-video from each kept keyframe. The prompt describes only what moves.

| | |
|---|---|
| **Output** | One kept clip per shot in `clips/` |
| **Human gate** | The art director picks per shot and checks against the lock and the previous cut. |
| **Tools** | Figma Weave (Kling, Veo 3.1), Higgsfield, Runway, Midjourney video |
| **Automated** | Clip batches, upscale, the log entry |
| **Stays manual** | Selection, judging physics and on-model motion |
| **Bottleneck** | Cost and morphing. Keyframes gate motion, so only approved frames get animated. |

## 06 · Produce · Sound and voice
Music bed, SFX and voiceover from the lock's sound tokens.

| | |
|---|---|
| **Output** | Music bed cut to length, SFX, VO, mixed to about -14 LUFS and -1 dBTP |
| **Human gate** | Audio direction clears the rights. Everything is judged on a phone speaker. |
| **Tools** | Suno, ElevenLabs, Higgsfield audio, Veo native sound for SFX |
| **Automated** | Track candidates, VO in several languages, loudness measurement |
| **Stays manual** | The mix, the cut points, rights for paid social |
| **Bottleneck** | Licensing. A pre-cleared kit per brand. |

## 07 · Produce · Copy and on-screen text
Hooks, supers, CTAs, captions and platform primary text. Three lines per placement, one ships.

| | |
|---|---|
| **Output** | `copy-matrix.md` with every losing line and its reason |
| **Human gate** | The copy lead picks and trims. Claims never ship unreviewed. |
| **Tools** | Claude with the brand voice guide as its system prompt |
| **Automated** | Bulk drafts, word-count limits from the lock, locale fan-out |
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
| **Output** | `matrix.csv`, reframed exports, and the next test batch |
| **Human gate** | Data proposes, a person decides. Someone owns the winning variant. |
| **Tools** | `scripts/matrix.py`, Higgsfield reframe / outpaint, platform A/B tests |
| **Automated** | Variant expansion, reframes, data pulls, logging |
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
