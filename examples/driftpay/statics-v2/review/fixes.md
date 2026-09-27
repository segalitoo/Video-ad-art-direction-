# Statics v2 · fix list after the first pass

Figma file "Driftpay · Statics" (faC0rzsIQRn8o9zgCaEEu9), v2 frames below the v1 row. The fix pass
was written and ready, but the Figma Starter plan's MCP limit (20 tool calls a month) stopped it.
Every value below is in frame pixels. Screenshots of the first pass: `A-*.png`, `B-*.png`, and
`before-after.jpg`.

## Direction A · One bold word

| Frame | Layer | Change | Why |
|---|---|---|---|
| A1 1200×1200 | plane (4:7) | W 560 · H 378 · X 590 · Y 175 | Nose was cut by the frame edge |
| A1 1200×1200 | Get paid… + CTA | CTA Y = 1200 − 90 − CTA height; subline Y = CTA Y − 40 − subline height | One group at the bottom; more space above the group than inside it |
| A1 1200×628 | plane (4:16) | W 420 · H 284 · X 720 · Y 18 | Nose cut; "AL" too covered |
| A1 1080×1350 | plane (4:25) | W 520 · H 351 · X 500 · Y 250 | Nose cut |
| A1 1080×1350 | Get paid… + CTA | as the square: CTA 80 from the bottom, subline 40 above it | Same grouping |
| A2 Stories | Wordmark · Claim | Wordmark Y 300 · Claim Y 400 | Top 14% is covered by the account header |
| A2 Stories | coins (4:33) | W 500 · H 596 · X 290 · Y 900 | Was inside the reply-bar zone (bottom 20%) |
| All A | plane and coins shadow | Drop shadow Y 56 (coins 40) · blur 70 (60) · 30% (28%) · Multiply | Too faint: the objects looked pasted on |

## Direction B · The hand lets go

| Frame | Layer | Change | Why |
|---|---|---|---|
| A1 1200×1200 | B-plane photo (4:50) | W 800 · H 1067 · X 400 · Y 190 | Only fingertips showed; the "let go" beat needs the whole hand |
| A1 1200×1200 | Fade top | W 800 · H 200 · X 400 · Y 190 | Follows the photo |
| A1 1200×1200 | new Fade left | W 220 · H 1200 · X 400 · Y 0 · linear #111A27 100% → 0% | Hides the photo's left edge |
| A1 1200×1200 | Proof chip | X 150 · Y 880 | It covered the plane's wing |
| A1 1080×1350 | B-plane photo (4:80) | W 846 · H 1128 · X 234 · Y 222, fades as above (fade left H 1350) | Same as the square |
| A1 1080×1350 | Proof chip | X 110 · Y 1010 | Same |
| A1 1200×628 | Proof chip | X 640 · Y 486 | It sat on the fingers |
| A2 Stories | Wordmark · Headline | Wordmark Y 300 · Headline Y 400 | Header zone |

## Judge (static rubric, first pass, before fixes)

See `../judge-statics.md`.
