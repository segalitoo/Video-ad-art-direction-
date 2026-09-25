# QA checklist · stage 9

> Machines check first, people judge what passed.
> Run `python scripts/spec_check.py <file> --platform <p> --overlay` for every export.
> Only files with no FAIL reach the human review.

## Automated (scripts/spec_check.py)
- [ ] Aspect ratio matches the platform
- [ ] Resolution at or above the platform minimum
- [ ] Duration under the platform maximum (warns outside the recommended range)
- [ ] Frame rate in range
- [ ] Loudness about -14 LUFS, true peak at or below -1 dBTP
- [ ] Audio present where the platform expects it
- [ ] File size under the limit
- [ ] Safe-zone overlay exported for the hook frame and the end card

## Craft · art director
- [ ] Every generated shot matches the lock version in the log
- [ ] Hero (product / character) is on-model in every shot
- [ ] No AI artefacts: hands, faces, label warping, morphing between frames
- [ ] Palette holds across cuts; the grade is continuous
- [ ] Text, logo and product sit inside the safe zone (check the overlay PNG)

## Message · creative lead
- [ ] Hook reads in the first 2 seconds with sound off
- [ ] The one thing from the brief is said, once, clearly
- [ ] Captions on every spoken line
- [ ] CTA is visible for at least 2 seconds

## Brand and legal
- [ ] Every claim is approved and can be proven
- [ ] Music and voice rights cleared for paid social, in every market
- [ ] AI disclosure / "made with AI" label applied where required
- [ ] No real person's likeness without consent

## Sign-off
| Gate | Owner | Date |
|---|---|---|
| Craft | Art director | |
| Message | Creative lead | |
| Brand / legal | Brand owner | |
