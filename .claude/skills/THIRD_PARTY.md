# Third-party skills in this folder

Added 2026-09-27 at the art director's request, to raise the design bar. Both packs are aimed at
web interfaces; their transferable rules are also adapted into `templates/design-review.md`
for the ad workflow. Vetted before adding: no instructions that reach for credentials or
override other instructions.

| Folder | Source | Version | Licence | Notes |
|---|---|---|---|---|
| `impeccable/` | [pbakaus/impeccable](https://github.com/pbakaus/impeccable), `plugin/skills/impeccable` | 4.4.0, commit 9d715cc (2026-09-24) | Apache-2.0 (`impeccable/LICENSE`, `NOTICE.md`) | Its launcher downloads a version-pinned binary from the author's GitHub releases on first use. The plugin's hooks and agents were **not** installed: nothing runs on every edit. |
| `taste-*/` | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill), `skills/*` | commit ce26fc2 (2026-09-26) | MIT (`LICENSE` in each folder) | 13 skills; folders prefixed `taste-`. `taste-output-skill` pushes for exhaustive output and can pull against a "concise answers" preference; the user's own preferences win. |

To update: re-clone the source at a newer commit, re-run the vetting scan (URLs, shell commands,
override phrases), replace the folders, and update this table.
