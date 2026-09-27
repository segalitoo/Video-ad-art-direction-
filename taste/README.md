# The taste library

Good and bad examples that every new creative is compared with. It is how the system learns
the art director's taste over time instead of starting from zero on each project.

- `library.yml`: one entry per example: kind (`exemplar` or `anti`), medium, tags, **why**, source.
- `refs/`: the stills (clips as a 5-frame strip), made by `scripts/taste.py`.
- `lessons.md`: rules learned from real results, with evidence and where each is enforced.

## Feed it

- **References you admire:** `python scripts/taste.py add <image> --kind exemplar --medium static --tags ... --why "..." --source "credit"`.
- **Other brands' ads** (Meta Ad Library screenshots and similar): add `--external --copy "the ad's text"`.
  This repo is public, so the image stays in `refs/external/` (git ignores it) and only the entry, the
  reason, the credit and the text are committed. A fresh clone has the entries without those images.
- **Mixed examples:** when only one idea in an ad is worth learning, say that idea in `--why` and
  put what not to copy in `--watch` (clip art, clutter, stock people). The review shows both.
  External work is for internal inspiration only: never published, never used in an ad, always credited.
- **At every gate:** after the art director picks, file the verdicts with their reasons:
  `python scripts/taste.py from-judge <round.yml> --keep D1:"why it works" --reject D3:"what went wrong"`.
- **When something teaches a rule:** `python scripts/taste.py lesson "<rule>" --evidence "<what showed it>" --enforced-in "<where>"`.

## Use it

- Before a gate: `python scripts/taste.py nearest <candidate> --medium frame --tags ... --sheet compare.html`,
  then say which exemplar it is closest to and which anti-example it risks (design review §0.6).
- At the lock: pull the nearest exemplars as image references for the style frames.
- `python scripts/taste.py sheet` renders the whole library as one page.
