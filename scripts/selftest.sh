#!/usr/bin/env bash
# Runs every script against the Sunpeel example and a synthetic video.
# Usage: bash scripts/selftest.sh
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=.selftest; rm -rf "$tmp"; mkdir -p "$tmp"
ok() { echo "ok   $1"; }

python3 scripts/assemble.py examples/sunpeel/storyboard.yml --check 2>/dev/null && ok "sunpeel passes pre-checks"
python3 scripts/assemble.py examples/fernly/storyboard.yml --check 2>/dev/null && ok "fernly passes pre-checks"
python3 scripts/assemble.py examples/fernly/storyboard.yml > "$tmp/fernly.md" 2>/dev/null
diff -q "$tmp/fernly.md" examples/fernly/prompts.md >/dev/null && ok "committed fernly prompts.md is up to date" || { echo "FAIL fernly prompts.md is stale"; exit 1; }
python3 scripts/assemble.py examples/sunpeel/storyboard.yml > "$tmp/prompts.md" 2>/dev/null
diff -q "$tmp/prompts.md" examples/sunpeel/prompts.md >/dev/null && ok "committed prompts.md is up to date" || { echo "FAIL prompts.md is stale"; exit 1; }
for ex in driftpay fernly; do
  python3 scripts/assemble.py examples/$ex/storyboard.yml 2>/dev/null | diff -q - examples/$ex/prompts.md >/dev/null \
    && python3 scripts/matrix.py examples/$ex/storyboard.yml 2>/dev/null | diff -q - examples/$ex/matrix.csv >/dev/null \
    || { echo "FAIL $ex prompts.md or matrix.csv is stale: rebuild them"; exit 1; }
done
ok "committed driftpay and fernly prompts and matrices are up to date"
python3 scripts/matrix.py examples/sunpeel/storyboard.yml > "$tmp/matrix.csv" 2>/dev/null
diff -q "$tmp/matrix.csv" examples/sunpeel/matrix.csv >/dev/null && ok "committed matrix.csv is up to date" || { echo "FAIL matrix.csv is stale"; exit 1; }

# A broken storyboard must fail.
sed 's/beat: hook/beat: build/' examples/sunpeel/storyboard.yml > "$tmp/bad.yml"
cp examples/sunpeel/sunpeel.dna.yml "$tmp/"
if python3 scripts/assemble.py "$tmp/bad.yml" --check 2>/dev/null; then echo "FAIL missing hook not caught"; exit 1; fi
ok "missing hook is caught"

# The prompt lint must flag movement in a keyframe and an overloaded action.
sed 's/floating in mid-air/spinning in mid-air/; s/the can drops onto the ledge and settles with one springy bounce/the can drops, lands and rolls/' \
  examples/sunpeel/storyboard.yml > "$tmp/lint.yml"
lint_out=$(python3 scripts/assemble.py "$tmp/lint.yml" --check 2>&1 || true)
echo "$lint_out" | grep -q "subject has movement (spinning)" && echo "$lint_out" | grep -q "S02: action has 3" \
  && ok "prompt lint flags movement in a keyframe and an overloaded action" || { echo "FAIL prompt lint"; exit 1; }

# The people filter drops body-part negatives by whole word only ("interface" is not a face).
(cd scripts && python3 -c "
from common import load_storyboard; import assemble as A
b, l = load_storyboard('../examples/fernly/storyboard.yml')
assert any('interface' in n for n in A.negatives_for(l, 'image'))") && ok "people filter keeps 'interface'" || { echo "FAIL people filter"; exit 1; }

# edit_of must name another shot's frame; people: hands keeps faces out and guards fingers.
sed 's/edit_of: S05-K-end/edit_of: S09-K/' examples/fernly/storyboard.yml > "$tmp/editof.yml"; cp examples/fernly/fernly.dna.yml "$tmp/"
if python3 scripts/assemble.py "$tmp/editof.yml" --check >/dev/null 2>&1; then echo "FAIL bad edit_of not caught"; exit 1; fi
ok "edit_of pointing at a missing frame is caught"
(cd scripts && python3 -c "
from common import load_storyboard; import assemble as A
b, l = load_storyboard('../examples/fernly/storyboard.yml'); n = A.negatives_for(l, 'image')
assert 'faces or full people' in n and not any('people or body parts' == x for x in n)") && ok "people: hands bans faces, not the hand" || { echo "FAIL people: hands"; exit 1; }

# Routes: every route resolves, a bad one is refused, and the own-keys client builds requests without sending.
for r in higgsfield-web own-keys weave higgsfield-api; do
  python3 scripts/assemble.py examples/driftpay/storyboard.yml --route $r 2>/dev/null | grep -q "Route: \`$r\`" || { echo "FAIL route $r"; exit 1; }
done
if python3 scripts/assemble.py examples/driftpay/storyboard.yml --route nope --check >/dev/null 2>&1; then echo "FAIL bad route not caught"; exit 1; fi
ok "all four routes build; a bad route is refused"
python3 scripts/img_api.py --provider gemini --prompt x --ref examples/driftpay/test/out/S01_2.qwen.jpg --dry-run | grep -q "generateContent" \
  && python3 scripts/img_api.py --provider openai --prompt x --dry-run | grep -q "images/generations" && ok "own-keys client builds Gemini and OpenAI requests" \
  || { echo "FAIL img_api dry run"; exit 1; }
if python3 scripts/img_api.py --provider openai --prompt x >/dev/null 2>&1; then echo "FAIL unapproved spend not refused"; exit 1; fi
ok "own-keys client refuses to spend without approval"

# Chain: every shot starts on the previous end frame; a missing end frame breaks it loudly.
python3 - "$tmp" <<'PY'
import sys, yaml
b = yaml.safe_load(open("examples/driftpay/storyboard.yml"))
b["ad"]["chain"] = True
for s in b["shots"]:
    for k in ("from_frame", "edit_of", "edit_verb"):
        s.pop(k, None)
    s.setdefault("end_subject", "the same scene a moment later")
b["statics"] = []
yaml.safe_dump(b, open(f"{sys.argv[1]}/chain.yml", "w"), sort_keys=False)
del b["shots"][1]["end_subject"]
yaml.safe_dump(b, open(f"{sys.argv[1]}/chain-broken.yml", "w"), sort_keys=False)
PY
cp examples/driftpay/driftpay.dna.yml "$tmp/"
python3 scripts/assemble.py "$tmp/chain.yml" 2>/dev/null | grep -q "S03-K · start frame:\*\* the kept S02-K-end frame (the chain" \
  && ok "chained shots start on the previous shot's end frame" || { echo "FAIL chain"; exit 1; }
if python3 scripts/assemble.py "$tmp/chain-broken.yml" --check >/dev/null 2>&1; then echo "FAIL broken chain not caught"; exit 1; fi
ok "a chain with a missing end frame is refused"

# Taste library: file examples, find the nearest, record a lesson (in a scratch library).
export TASTE_DIR="$tmp/taste"
python3 scripts/taste.py add examples/driftpay/test/out/S04_2.qwen.jpg --kind exemplar --medium frame --tags paper --why "clean map" --source test >/dev/null
python3 scripts/taste.py add examples/driftpay/test/out/S01_2.qwen.jpg --kind anti --medium frame --tags desk --why "test anti" --source test >/dev/null
python3 scripts/taste.py nearest examples/driftpay/test/out/S04_1.qwen.jpg --medium frame --tags paper -k 1 | grep -q "T0001" \
  && ok "taste library ranks the matching exemplar first" || { echo "FAIL taste nearest"; exit 1; }
if python3 scripts/taste.py add examples/driftpay/test/out/S04_2.qwen.jpg --kind exemplar --medium frame --why "" --source x >/dev/null 2>&1; then
  echo "FAIL taste entry without a reason not refused"; exit 1; fi
ok "taste library refuses an example without a reason"
python3 - "$tmp" <<'PY'
import sys
from PIL import Image, ImageDraw
t = sys.argv[1]
im = Image.new("RGB", (400, 400))
for y in range(400):                                   # a mint backdrop with a strong gradient
    ImageDraw.Draw(im).line([(0, y), (399, y)], fill=(200 - y // 4, 225 - y // 5, 205 - y // 5))
d = ImageDraw.Draw(im)
d.polygon([(80, 200), (330, 90), (230, 320)], fill=(235, 235, 238))     # a white "plane"
d.line([(200, 170), (260, 200)], fill=(150, 150, 152), width=6)         # a grey shaded seam inside it
im.save(f"{t}/cut_src.png")
PY
python3 scripts/cutout.py "$tmp/cut_src.png" -o "$tmp/cut.png" --chroma --near 5 --far 10 >/dev/null
python3 - "$tmp" <<'PY' && ok "cut-out keeps the object whole and drops a gradient backdrop" || { echo "FAIL cutout"; exit 1; }
import sys
from PIL import Image
c = Image.open(f"{sys.argv[1]}/cut.png")
w, h = c.size
assert 200 < w < 270 and 200 < h < 250, c.size                        # cropped to the object
a = c.getchannel("A")
assert a.getpixel((w // 2, h // 2)) == 255                             # the seam inside stays solid
assert a.getpixel((2, h - 3)) == 0                                     # backdrop corner is gone
PY
cat > "$tmp/layout.yml" <<YML
fonts: {Bold: $PWD/assets/fonts/space-grotesk/SpaceGrotesk-Bold.ttf, Medium: $PWD/assets/fonts/space-grotesk/SpaceGrotesk-Medium.ttf}
colors: {paper: "#F4F1EA", navy: "#1E2A44", coral: "#FF6B4A"}
frames:
  - name: t
    file: t
    w: 600
    h: 750
    bg: paper
    items:
      - {type: wordmark, x: 40, y: 40, size: 24, ink: navy}
      - {type: text, text: "LOCAL.", style: Bold, size: 200, fit: 30, center: true, y: 150, ls: -5, lh: 90, color: navy}
      - {type: stack, id: s, x: 40, y: 400, accent: {color: coral, mode: underline}, lines: [{text: "|1 day.|", style: Bold, size: 60, color: navy}]}
      - {type: cta, label: Open a free account, size: 20, x: 40, below: s, gap: 20}
YML
python3 scripts/static_render.py "$tmp/layout.yml" -o "$tmp/render" >/dev/null
python3 - "$tmp" <<'PY' && ok "static renderer fits the big word and draws the accent and CTA" || { echo "FAIL static_render"; exit 1; }
import sys
from PIL import Image
im = Image.open(f"{sys.argv[1]}/render/t.jpg").convert("RGB")
assert im.size == (600, 750)
word = im.crop((0, 140, 600, 390)).convert("L").point(lambda v: 255 if v < 70 else 0).getbbox()
assert word and word[0] < 45 and word[2] > 555, word                        # the word fills the width
assert any(p[0] > 230 and p[1] < 140 for p in (im.getpixel((x, y)) for x in range(40, 250) for y in range(455, 480)))   # coral underline
PY
python3 scripts/taste.py add examples/driftpay/test/out/S04_2.qwen.jpg --kind exemplar --medium static --why "ext" \
  --source "someone else" --external --copy "Headline" --watch "clip art" >/dev/null
test -f "$TASTE_DIR/refs/external/T0003.jpg" && grep -q 'external: true' "$TASTE_DIR/library.yml" && grep -q 'watch: clip art' "$TASTE_DIR/library.yml" \
  && git check-ignore -q taste/refs/external/T0003.jpg \
  && ok "external references stay out of git" || { echo "FAIL taste external"; exit 1; }
rm "$TASTE_DIR/refs/external/T0003.jpg"
python3 scripts/taste.py sheet -o "$tmp/lib.html" >/dev/null && grep -q "image not on this machine" "$tmp/lib.html" \
  && ok "the library sheet survives a missing external image" || { echo "FAIL taste sheet missing"; exit 1; }
unset TASTE_DIR

# Judge pass: a matching pair must beat a mismatched one, a hard fail drops out, an unscored file stops the rank.
mkdir -p "$tmp/judge/out"
python3 - "$tmp/judge" <<'PY'
import sys
from PIL import Image, ImageDraw
t = sys.argv[1]
def plant(name, pot, droop):
    im = Image.new("RGB", (540, 960), (244, 239, 230)); d = ImageDraw.Draw(im)
    d.rectangle((0, 700, 540, 960), fill=(150, 110, 70)); d.rectangle((195, 550, 345, 725), fill=pot)
    for i in range(7):
        x = 270 + (i - 3) * 45; d.ellipse((x - 40, 325 + droop, x + 40, 425 + droop), fill=(47, 125, 79))
    im.save(f"{t}/out/{name}")
plant("droopy.a.png", (200, 100, 59), 100); plant("droopy.b.png", (120, 120, 120), 100)
plant("lush.a.png", (200, 100, 59), 0); plant("lush.b.png", (120, 120, 120), 0)
PY
cp examples/fernly/fernly.dna.yml "$tmp/"
python3 scripts/judge.py new "$tmp/judge/r.yml" --lock ../fernly.dna.yml D="out/droopy.*" L="out/lush.*" --pair D:L:first_last >/dev/null
python3 scripts/judge.py measure "$tmp/judge/r.yml" >/dev/null
python3 - "$tmp/judge/r.yml" <<'PY'
import sys, yaml
p = sys.argv[1]; d = yaml.safe_load(open(p))
s = dict(lock=4, hero=4, craft=4, composition=4, story=4, animatable=4)
d["scores"] = {"D1": s, "D2": s, "L1": s, "L2": {**s, "fail": "text in the image"}}
assert d["pair_machine"]["D1+L1"] > d["pair_machine"]["D2+L1"], "matching pots must measure closer"
yaml.safe_dump(d, open(p, "w"), sort_keys=False)
del d["scores"]["D2"]["craft"]; yaml.safe_dump(d, open(p.replace("r.yml", "bad.yml"), "w"), sort_keys=False)
PY
python3 scripts/judge.py rank "$tmp/judge/r.yml" | grep -q "Best set: D1 + L1" && ok "judge ranks the matching pair first and drops a hard fail" \
  || { echo "FAIL judge ranking"; exit 1; }
if python3 scripts/judge.py rank "$tmp/judge/bad.yml" >/dev/null 2>&1; then echo "FAIL unscored file not caught"; exit 1; fi
ok "judge refuses to rank an unfinished visual pass"

# Copy rules: guardrails, unproven proof numbers, hook sets (research-first, proof-never-invented).
python3 - "$tmp" <<'PY'
import sys, yaml
t = sys.argv[1]
lock = yaml.safe_load(open("examples/fernly/fernly.dna.yml"))
lock["guardrails"] = {"never_say": ["guaranteed"]}
lock["proof"] = {"rating": "4.8", "stats": [{"value": "93%", "claim": "x", "source": "y"}]}
yaml.safe_dump(lock, open(f"{t}/copy.dna.yml", "w"))
yaml.safe_dump({"hooks": [
    {"id": "H1", "line": "I was drowning my fern every week", "mechanic": "confession"},
    {"id": "H2", "line": "I stopped watering, guaranteed results", "mechanic": "result"},
    {"id": "H3", "line": "87% of plants die this way", "mechanic": "stat"},
    {"id": "H4", "line": "93% of owners water too much", "mechanic": "stat"}]}, open(f"{t}/hooks.yml", "w"))
PY
copy_out=$(python3 scripts/copy_check.py "$tmp/hooks.yml" --lock "$tmp/copy.dna.yml" || true)
echo "$copy_out" | grep -q '"guaranteed" is in the lock' && echo "$copy_out" | grep -q '"87%" reads as proof' \
  && ! echo "$copy_out" | grep -q '"93%"' && echo "$copy_out" | grep -q 'H1, H2 all start with "i"' \
  && ok "copy check flags banned words, unproven numbers and hooks that start alike" || { echo "FAIL copy_check: $copy_out"; exit 1; }
python3 scripts/copy_check.py examples/fernly/storyboard.yml >/dev/null && ok "fernly copy passes the copy check" || { echo "FAIL fernly copy"; exit 1; }

# Static formats: proof formats refuse without proof; with proof, all 15 build and render cleanly.
mkdir -p "$tmp/fmt"; cp examples/driftpay/statics-v2/cut/hero-plane.png "$tmp/fmt/p.png"
python3 - "$tmp" <<'PY'
import sys, yaml
t = sys.argv[1]
lock = yaml.safe_load(open("examples/driftpay/driftpay.dna.yml"))
lock["proof"] = {"rating": "4.8", "review_count": "1,200+", "stats": [{"value": "93%", "claim": "paid next day", "source": "test"}],
                 "quotes": [{"text": "I stopped chasing payments.", "name": "Test"}], "badges": ["A", "B"], "price_per_day": "$0.33/day"}
yaml.safe_dump(lock, open(f"{t}/fmt/proof.dna.yml", "w"))
plate = "../../examples/driftpay/final/statics/plates/A1_4x5.jpg"
ads = [{"id": "F01", "format": "hero-headline", "headline": "Get paid like it's local.", "bg": "light"},
       {"id": "F02", "format": "stat", "bg": "dark"}, {"id": "F03", "format": "review"}, {"id": "F04", "format": "testimonial"},
       {"id": "F05", "format": "rating", "headline": "Freelancers stay."},
       {"id": "F06", "format": "us-vs-them", "headline": "Bank or us?", "them": "Bank", "cons": ["Slow"], "pros": ["Fast"], "product_scale": 0.8},
       {"id": "F07", "format": "ingredients", "headline": "Inside", "callouts": [{"name": "A", "benefit": "b"}, {"name": "C", "benefit": "d"}]},
       {"id": "F08", "format": "benefits", "headline": "Invoices on time.", "benefits": ["One", "Two"], "bg": "accent"},
       {"id": "F09", "format": "price-per-day", "headline": "Less than coffee.", "bg": "dark"},
       {"id": "F10", "format": "badges", "headline": "Built right"},
       {"id": "F11", "format": "lifestyle", "plate": plate, "headline": "Your money isn't abroad."},
       {"id": "F12", "format": "ugc-frame", "plate": plate, "headline": "ok this changed invoicing"},
       {"id": "F13", "format": "text-thread", "messages": [{"from": "them", "text": "fees?"}, {"from": "me", "text": "none"}]},
       {"id": "F14", "format": "premium", "headline": "Paid. Locally.", "product_scale": 1.3},
       {"id": "F15", "format": "seasonal", "plate": plate, "season": "Tax season", "headline": "Close the year paid."}]
yaml.safe_dump({"lock": "proof.dna.yml", "product": "p.png", "ads": ads}, open(f"{t}/fmt/all.yml", "w"))
yaml.safe_dump({"lock": "../../examples/driftpay/driftpay.dna.yml", "product": "p.png",
                "ads": [{"id": "X", "format": "stat"}]}, open(f"{t}/fmt/noproof.yml", "w"))
yaml.safe_dump({"lock": "proof.dna.yml", "product": "p.png", "ads": [
    {"id": "S1", "format": "benefits", "headline": "Paid fast", "benefits": ["a"]},
    {"id": "S2", "format": "benefits", "headline": "Paid again", "benefits": ["a"]},
    {"id": "S3", "format": "benefits", "headline": "Paid now", "benefits": ["a"]}]}, open(f"{t}/fmt/same.yml", "w"))
PY
if python3 scripts/static_formats.py "$tmp/fmt/noproof.yml" >/dev/null 2>&1; then echo "FAIL proof format built without proof"; exit 1; fi
ok "proof formats refuse to build without proof in the lock"
fmt_out=$(python3 scripts/static_formats.py "$tmp/fmt/all.yml" --render "$tmp/fmt/out")
# the fixture's product is a wide, flat plane, so the space check rightly reports empty bands; nothing else may fire
echo "$fmt_out" | grep -q "15 ads, 15 formats, 15 frames" && ! echo "$fmt_out" | grep "^FLAG" | grep -qv "empty band\|is empty\|nothing below" \
  && [ "$(ls "$tmp/fmt/out" | wc -l)" -eq 15 ] && ok "all 15 static formats build, pass the thumbnail and layout tests and render" || { echo "FAIL static formats: $fmt_out"; exit 1; }
python3 - <<'PY' && ok "headlines break like a designer's: on punctuation, no orphans, no 'the' at a line end" || { echo "FAIL line breaks"; exit 1; }
import sys
sys.path.insert(0, "scripts")
from static_render import balance, clean_breaks, font, line_width
f = font("assets/fonts/space-grotesk/SpaceGrotesk-Bold.ttf", 90)
m = lambda t: line_width(f, t, 90, -2)
assert balance("Your barrier called. It wants a break.", m, 1000) == ["Your barrier called.", "It wants a break."]
assert balance("One shelf. Two generations. Same jar.", m, 1000) == ["One shelf.", "Two generations.", "Same jar."]
assert balance("Line one\nline two", m, 2000) == ["Line one", "line two"]
assert not clean_breaks(["Before the next active, the", "barrier."]) and not clean_breaks(["Your barrier", "called. It wants", "a break."])
PY
python3 - "$tmp" <<'PY' && ok "flow layouts for a tall product fill 4:5, 1:1 and 9:16 with no flags; a collision is caught" || { echo "FAIL flow layouts"; exit 1; }
import subprocess, sys, yaml
from PIL import Image, ImageDraw
sys.path.insert(0, "scripts")
t = sys.argv[1]
im = Image.new("RGBA", (600, 620), (0, 0, 0, 0))
ImageDraw.Draw(im).rounded_rectangle([60, 0, 300, 620], 40, fill=(230, 30, 140, 255))
ImageDraw.Draw(im).rounded_rectangle([330, 300, 560, 620], 40, fill=(250, 250, 250, 255))
im.save(f"{t}/fmt/tall.png")
ads = [{"id": "T1", "format": "hero-headline", "headline": "Before the next active, the barrier.", "subhead": "Ceramides in every one."},
       {"id": "T2", "format": "benefits", "headline": "Science you can read on the jar.", "benefits": ["One", "Two", "Three"]},
       {"id": "T3", "format": "premium", "headline": "Finally, a routine we can share.", "bg": "dark"},
       {"id": "T4", "format": "text-thread", "messages": [{"from": "me", "text": "where is it"}, {"from": "them", "text": "mine now"}]},
       {"id": "T5", "format": "us-vs-them", "headline": "Your barrier called. It wants a break.", "them": "Ten steps", "cons": ["Acids"], "pros": ["Three steps"]},
       {"id": "T6", "format": "ingredients", "headline": "3-1-1: the ratio your barrier uses.", "callouts": [{"name": "A", "benefit": "b"}, {"name": "C", "benefit": "d"}]}]
yaml.safe_dump({"lock": "proof.dna.yml", "product": "tall.png", "sizes": ["1080x1350", "1080x1080", "1080x1920"], "ads": ads},
               open(f"{t}/fmt/flow.yml", "w"))
out = subprocess.run([sys.executable, "scripts/static_formats.py", f"{t}/fmt/flow.yml"], capture_output=True, text=True).stdout
assert "PASS  6 ads, 6 formats, 18 frames, 0 flag" in out, out
from static_render import Ctx, render_frame
from static_formats import layout_checks
fr = {"w": 1080, "h": 1080, "bg": "#FFFFFF", "items": [
    {"type": "text", "text": "Headline here", "style": "Bold", "size": 90, "x": 80, "y": 100, "color": "#111111"},
    {"type": "text", "text": "Sub line", "style": "Medium", "size": 40, "x": 80, "y": 150, "color": "#111111"},
    {"type": "text", "text": "Low", "style": "Medium", "size": 40, "x": 80, "y": 900, "color": "#CCCCCC"}]}
ctx = Ctx({"fonts": {"Bold": "assets/fonts/space-grotesk/SpaceGrotesk-Bold.ttf",
                     "Medium": "assets/fonts/space-grotesk/SpaceGrotesk-Medium.ttf"}, "colors": {}, "frames": [fr]}, __import__("pathlib").Path("."))
render_frame(fr, ctx)
flags = " | ".join(layout_checks("X", ctx, 1080, 1080))
assert "overlaps" in flags and "empty band" in flags and "pixels behind it" in flags, flags
PY
python3 - "$tmp" <<'PY'
import sys, yaml
t = sys.argv[1]
d = yaml.safe_load(open(f"{t}/fmt/all.yml")); d["sizes"] = ["1080x1920"]
yaml.safe_dump(d, open(f"{t}/fmt/tall.yml", "w"))
PY
python3 scripts/static_formats.py "$tmp/fmt/tall.yml" -o "$tmp/fmt/tall_layout.yml" >/dev/null 2>&1 || true
python3 - <<'PY' && ok "type system: tracking follows size, word spaces keep their width, real punctuation, a 32 px floor" || { echo "FAIL type system"; exit 1; }
import sys
sys.path.insert(0, "scripts")
from static_formats import smart, track_for, MIN_TEXT
from static_render import font, line_width, words_of
t = [track_for(p) for p in (24, 32, 48, 96, 160)]
assert t == sorted(t, reverse=True) and t[0] > 0 > t[-1], t
f = font("assets/fonts/space-grotesk/SpaceGrotesk-Bold.ttf", 100)
assert line_width(f, "a b", 100, -5) - line_width(f, "ab", 100, -5) == line_width(f, "a b", 100, 0) - line_width(f, "ab", 100, 0)
assert smart("mom where's it") == "mom where\u2019s it" and smart('"hi"') == "\u201chi\u201d" and smart("a - b...") == "a \u2013 b\u2026"
assert words_of(smart("3 parts here")) == ["3\u00a0parts", "here"]
assert MIN_TEXT >= 32
PY
python3 - "$tmp/fmt/tall_layout.yml" <<'PY' && ok "9:16 statics: no drawn CTA, all type starts at or below 16% of the height" || { echo "FAIL 9:16 safe band"; exit 1; }
import sys, yaml
lay = yaml.safe_load(open(sys.argv[1]))
text = ("text", "stack", "marks", "bubble", "cta", "wordmark", "chip")
for f in lay["frames"]:
    assert not any(i.get("type") == "cta" for i in f["items"]), f["name"] + ": a drawn CTA on a 9:16 frame"
    tops = [i["y"] for i in f["items"] if i.get("type") in text and "y" in i]
    assert not tops or min(tops) >= f["h"] * 0.16 - 1, f["name"] + ": type above 16%"
PY
same=$(python3 scripts/static_formats.py "$tmp/fmt/same.yml" || true)
echo "$same" | grep -q "use 1 format" && echo "$same" | grep -q "same background" && echo "$same" | grep -q 'all start with "paid"' \
  && ok "a batch of look-alike statics is flagged" || { echo "FAIL batch checks: $same"; exit 1; }
chk=examples/driftpay/formats/.layout-check.yml                 # same folder, so relative paths match
python3 scripts/static_formats.py examples/driftpay/formats/formats.yml -o "$chk" >/dev/null
diff -q "$chk" examples/driftpay/formats/layout.yml >/dev/null && { rm -f "$chk"; ok "committed driftpay formats layout is up to date"; } \
  || { rm -f "$chk"; echo "FAIL driftpay formats layout is stale"; exit 1; }

# Layers for motion loops: plate + type layer put back together equal the full static, and the
# plate carries no type (F6 has a fade, which once leaked the headline into the plate).
for f in F1 F6; do python3 scripts/static_render.py examples/driftpay/formats/layout.yml -o "$tmp/layers" --only $f --layers >/dev/null; done
python3 - "$tmp/layers" <<'PY' && ok "plate and type layers recompose the static; the plate has no type, fades included" || { echo "FAIL layers"; exit 1; }
import sys, glob
from PIL import Image, ImageChops, ImageStat
d = sys.argv[1]
for f in ("F1", "F6"):
    full = Image.open(glob.glob(f"{d}/{f}_*[0-9].jpg")[0]).convert("RGB")
    plate = Image.open(glob.glob(f"{d}/{f}_*_plate.png")[0]).convert("RGBA")
    typ = Image.open(glob.glob(f"{d}/{f}_*_type.png")[0])
    mask = typ.split()[-1].point(lambda a: 255 if a > 200 else 0)
    bare = ImageStat.Stat(ImageChops.difference(plate.convert("RGB"), full), mask).mean
    assert max(bare) > 20, f + ": the plate still shows the type"
    plate.alpha_composite(typ)
    assert max(ImageStat.Stat(ImageChops.difference(plate.convert("RGB"), full)).mean) < 2.0, f   # JPEG noise on a photo
PY

# Finish items: a glow with no box edge, a contact shadow under a cut-out, and zero-mean grain kept off the type layer.
python3 - "$tmp" <<'PY' && ok "glow has no hard edge, contact shadow sits under the cut-out, grain keeps the colour and skips the type layer" || { echo "FAIL finish items"; exit 1; }
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageStat
sys.path.insert(0, "scripts")
from static_render import Ctx, render_frame
t = Path(sys.argv[1])
cut = Image.new("RGBA", (200, 300), (0, 0, 0, 0)); ImageDraw.Draw(cut).rectangle([60, 40, 140, 299], fill=(230, 20, 140, 255))
cut.save(t / "cut.png")
ctx = Ctx({"fonts": {}, "colors": {}}, t)
base = {"w": 600, "h": 600, "bg": "#FFEF8F"}
glow = render_frame(dict(base, items=[{"type": "glow", "x": 100, "y": 100, "w": 400, "h": 400, "color": "#FFFFFF", "opacity": 0.6}]), ctx)
px = lambda im, x, y: sum(im.getpixel((x, y)))
assert px(glow, 300, 300) > px(glow, 50, 50) + 40, "glow does not lighten its centre"
assert all(px(glow, x, y) == px(glow, 50, 50) for x, y in ((101, 300), (300, 101), (101, 101))), "glow reaches its box edge"
item = {"type": "image", "src": "cut.png", "fit": "contain", "x": 200, "y": 100, "w": 200, "h": 300}
plain = render_frame(dict(base, items=[item]), ctx)
shad = render_frame(dict(base, items=[dict(item, contact={"opacity": 0.6, "height": 0.08})]), ctx)
assert px(shad, 300, 401) < px(plain, 300, 401) - 30, "no contact shadow under the base"
assert px(shad, 300, 200) == px(plain, 300, 200) and px(shad, 300, 560) == px(plain, 300, 560), "shadow spills"
flat = render_frame(dict(base, items=[]), ctx); grain = render_frame(dict(base, items=[], grain=0.05), ctx)
m0, m1 = ImageStat.Stat(flat).mean, ImageStat.Stat(grain).mean
assert max(abs(a - b) for a, b in zip(m0, m1)) < 1.0, ("grain shifts the colour", m0, m1)
assert max(ImageStat.Stat(grain).stddev) > 1.0, "grain not visible in the numbers"
typ = render_frame(dict(base, items=[], grain=0.05), ctx, layer="type")
assert typ.getextrema()[3] == (0, 0), "grain on the type layer"
PY

# Optical margin: big type hangs its first ink on the margin, not its side bearing (it once measured nothing).
python3 - "$tmp" <<'PY' && ok "optical margin puts the first ink of big type on the margin" || { echo "FAIL optical margin"; exit 1; }
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
from static_render import Ctx, render_frame
ctx = Ctx({"fonts": {"Bold": str(Path("assets/fonts/space-grotesk/SpaceGrotesk-Bold.ttf").resolve())}, "colors": {}}, Path(sys.argv[1]))
def ink_x(optical):
    it = {"type": "text", "text": "Oh", "style": "Bold", "size": 240, "x": 100, "y": 40, "color": "#000000", "lh": 100, "ls": 0, "optical": optical}
    im = render_frame({"w": 800, "h": 400, "bg": "#FFFFFF", "items": [it]}, ctx, layer="type")
    return im.split()[-1].point(lambda v: 255 if v > 96 else 0).getbbox()[0]
assert ink_x(False) >= 106, ink_x(False)          # the round O carries a real side bearing at this size
assert abs(ink_x(True) - 100) <= 1, ink_x(True)
PY

# Score gate: totals, thresholds, the weakest dimension named.
python3 scripts/score.py new "$tmp/score.yml" --kind script --ids A B C >/dev/null
python3 - "$tmp/score.yml" <<'PY'
import sys, yaml
p = sys.argv[1]; d = yaml.safe_load(open(p))
for (k, it), v in zip(d["items"].items(), ([5, 4, 4, 4, 4], [3, 4, 3, 4, 3], [3, 2, 2, 3, 3])):
    it["scores"] = dict(zip(it["scores"], v))
yaml.safe_dump(d, open(p, "w"))
PY
score_out=$(python3 scripts/score.py rank "$tmp/score.yml")
echo "$score_out" | grep -q "21/25  A .*every hook variant" && echo "$score_out" | grep -q "17/25  B .*one version" \
  && echo "$score_out" | grep -q "13/25  C .*REWRITE: buyer_language" && ok "score gate ranks and decides before any paid run" \
  || { echo "FAIL score: $score_out"; exit 1; }

# Performance loop: kill / hold / scale / wait from the account's rules, fatigue, winners into the library.
cat > "$tmp/export.csv" <<'CSV'
Ad name,Amount spent (USD),Impressions,Link clicks,Results,Frequency,Days
fernly-reviews-15s_tiktok_H1C1,120.50,10000,260,5,1.8,3
fernly-reviews-15s_tiktok_H2C1,95.00,9000,70,1,2.1,3
fernly-reviews-15s_tiktok_H3C1,15.00,1200,30,0,1.1,3
fernly-reviews-15s_meta_feed_H2C2,60.00,6000,95,1,1.5,7
CSV
perf_out=$(python3 scripts/perf.py read "$tmp/export.csv" --rules templates/perf.yml --matrix examples/fernly/matrix.csv -o "$tmp/perf.md")
echo "$perf_out" | grep -q "SCALE  fernly-reviews-15s_tiktok_H1C1" && echo "$perf_out" | grep -q "KILL   fernly-reviews-15s_tiktok_H2C1" \
  && echo "$perf_out" | grep -q "WAIT   fernly-reviews-15s_tiktok_H3C1" && echo "$perf_out" | grep -q "HOLD   fernly-reviews-15s_meta_feed_H2C2" \
  && grep -q "## By hook" "$tmp/perf.md" && grep -q "Multiply the winners" "$tmp/perf.md" \
  && ok "perf read decides kill, hold, scale and wait, and plans the winner's variations" || { echo "FAIL perf: $perf_out"; exit 1; }
printf 'fernly-reviews-15s_tiktok_H1: ../examples/driftpay/test/out/S04_2.qwen.jpg\n' > "$tmp/creatives.yml"
cp "$tmp/creatives.yml" "$tmp/c.yml"; sed -i 's#\.\./examples#../examples#' "$tmp/c.yml"
TASTE_DIR="$tmp/taste-perf" python3 scripts/perf.py taste "$tmp/export.csv" --rules templates/perf.yml --files "$tmp/c.yml" >/dev/null
grep -q "Performance: SCALE" "$tmp/taste-perf/library.yml" && grep -q "performer" "$tmp/taste-perf/library.yml" \
  && ok "the winner is filed in the taste library with its numbers" || { echo "FAIL perf taste"; exit 1; }

if command -v ffmpeg >/dev/null; then
  ffmpeg -y -v error -f lavfi -i "testsrc2=size=1080x1920:rate=30:duration=15" \
    -f lavfi -i "sine=frequency=440:duration=15" -af "loudnorm=I=-14:TP=-1.5" \
    -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$tmp/good.mp4"
  python3 scripts/spec_check.py "$tmp/good.mp4" --platform meta_vertical --overlay >/dev/null && ok "clean 9:16 export passes"
  ffmpeg -y -v error -f lavfi -i "color=c=orange:size=1080x1920:rate=30:duration=70" \
    -f lavfi -i "sine=frequency=100:duration=70" -af "volume=30dB" \
    -c:v libx264 -pix_fmt yuv420p -c:a pcm_s16le "$tmp/bad.mov"
  if python3 scripts/spec_check.py "$tmp/bad.mov" --platform youtube_shorts >/dev/null; then
    echo "FAIL long, clipping export not caught"; exit 1; fi
  ok "too long + clipping export fails"
  python3 scripts/crop.py "$tmp/good.mp4" 4:5 -o "$tmp/feed.mp4" >/dev/null
  python3 scripts/spec_check.py "$tmp/feed.mp4" --platform meta_feed >/dev/null && ok "free 4:5 crop passes the feed spec"
  if python3 scripts/crop.py "$tmp/good.mp4" 1:1 -o "$tmp/sq.mp4" >/dev/null 2>&1; then
    echo "FAIL 1:1 crop into the safe area not caught"; exit 1; fi
  ok "1:1 crop that cuts the safe area is refused"

  # The cut: five stand-in clips become a master and a 4:5 feed cut that pass their specs.
  for n in 1 2 3 4 5; do
    ffmpeg -y -v error -f lavfi -i "testsrc2=size=720x1280:rate=24:duration=4" -f lavfi -i "sine=frequency=$((300+n*50)):duration=4" \
      -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$tmp/c$n.mp4"
  done
  cl=""; for n in 1 2 3 4 5; do cl="$cl --clip S0$n=$tmp/c$n.mp4@0.2"; done
  python3 scripts/cut.py examples/driftpay/storyboard.yml --kept "$tmp/none.yml" $cl -o "$tmp/cut.mp4" >/dev/null
  python3 scripts/spec_check.py "$tmp/cut.mp4" --platform meta_vertical linkedin_feed >/dev/null && ok "cut master passes its specs"
  python3 scripts/cut.py examples/driftpay/storyboard.yml --kept "$tmp/none.yml" $cl --aspect 4:5 -o "$tmp/cut45.mp4" >/dev/null
  python3 scripts/spec_check.py "$tmp/cut45.mp4" --platform meta_feed >/dev/null && ok "4:5 feed cut passes its specs"
  if python3 scripts/cut.py examples/driftpay/storyboard.yml --kept "$tmp/none.yml" --clip S01=$tmp/c1.mp4 -o "$tmp/x.mp4" >/dev/null 2>&1; then
    echo "FAIL cut with missing clips not caught"; exit 1; fi
  ok "cut refuses a storyboard with missing clips"

  # The visual storyboard: stage 3 (nothing generated: sketch boxes) and after the cut (frames, strips, joins).
  python3 scripts/board.py examples/driftpay/storyboard.yml --kept "$tmp/none.yml" -o "$tmp/board0.html" >/dev/null
  grep -q 'class="frame missing"' "$tmp/board0.html" && ok "board draws sketch boxes before anything is generated" || { echo "FAIL board sketch"; exit 1; }
  printf 'clips:\n' > "$tmp/kept.yml"; for n in 1 2 3 4 5; do printf '  S0%s: c%s.mp4@0.2\n' $n $n >> "$tmp/kept.yml"; done
  python3 scripts/board.py examples/driftpay/storyboard.yml --kept "$tmp/kept.yml" -o "$tmp/board1.html" >/dev/null
  grep -q "join [0-9]*%" "$tmp/board1.html" && ok "board scores every join from the kept clips" || { echo "FAIL board joins"; exit 1; }

  # Static ads: compose from stand-in plates, then QA each export.
  python3 - "$tmp" <<'PY'
import sys
from PIL import Image
for name, size in (("p45.png", (1080, 1350)), ("p916.png", (1080, 1920))):
    Image.new("RGB", size, (240, 170, 140)).save(f"{sys.argv[1]}/{name}")
PY
  python3 scripts/static_compose.py examples/sunpeel/storyboard.yml A1 \
    --plate 4:5="$tmp/p45.png" --plate 9:16="$tmp/p916.png" --out-dir "$tmp/static" >/dev/null
  n=$(ls "$tmp/static" | wc -l)
  [ "$n" -eq 4 ] && ok "static A1 composed for 4 placement sizes" || { echo "FAIL static compose made $n files"; exit 1; }
  for f in "$tmp"/static/*.jpg; do python3 scripts/spec_check.py "$f" >/dev/null || { echo "FAIL static QA $f"; exit 1; }; done
  ok "every static export passes its platform spec"
  if python3 scripts/spec_check.py "$tmp/static/A1_tiktok_1080x1920.jpg" --platform youtube_shorts >/dev/null; then
    echo "FAIL static on a platform without statics not caught"; exit 1; fi
  ok "static on a platform that has no static ads is refused"
  python3 scripts/loop.py make --still "$tmp"/layers/F1_*_plate.png --move float --type "$tmp"/layers/F1_*_type.png -o "$tmp/loop.mp4" >/dev/null
  [ "$(ffprobe -v error -show_entries stream=nb_frames -of csv=p=0 "$tmp/loop.mp4")" -eq 180 ] \
    && ok "a static becomes a 6 s loop with its type layer on top" || { echo "FAIL loop"; exit 1; }
  # a clip made from the full source image goes through the ad's own layout (crop, fade, type), not a centre crop
  plate_src=$(python3 -c "import yaml; f=[f for f in yaml.safe_load(open('examples/driftpay/formats/layout.yml'))['frames'] if f['name'].startswith('F6')][0]; print([i['src'] for i in f['items'] if i['type']=='image'][0])")
  ffmpeg -y -v error -loop 1 -i "examples/driftpay/formats/$plate_src" -t 1 -r 30 -vf "scale=600:-2,format=yuv420p" "$tmp/src_clip.mp4"
  python3 scripts/loop.py make --clip "$tmp/src_clip.mp4" --layout examples/driftpay/formats/layout.yml --frame F6 -o "$tmp/loop_layout.mp4" >/dev/null
  python3 - "$tmp" <<'PY' && ok "a source-image clip loops through the ad's layout: same crop, fade and type as the static" || { echo "FAIL loop through layout"; exit 1; }
import subprocess, sys
from PIL import Image, ImageChops, ImageStat
t = sys.argv[1]
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{t}/loop_layout.mp4", "-frames:v", "1", f"{t}/ll0.png"], check=True)
subprocess.run([sys.executable, "scripts/static_render.py", "examples/driftpay/formats/layout.yml", "-o", f"{t}/ll", "--only", "F6"],
               check=True, capture_output=True)
import glob
a = Image.open(f"{t}/ll0.png").convert("RGB"); b = Image.open(glob.glob(f"{t}/ll/F6_*.jpg")[0]).convert("RGB")
assert a.size == b.size and max(ImageStat.Stat(ImageChops.difference(a, b)).mean) < 12
PY
else
  echo "skip spec_check tests (ffmpeg not installed)"
fi
rm -rf "$tmp"
echo "all good"
