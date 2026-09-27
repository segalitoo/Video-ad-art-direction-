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
diff -q "$tmp/fernly.md" examples/fernly/prompts.md >/dev/null && ok "committed fernly prompts.md is up to date"
python3 scripts/assemble.py examples/sunpeel/storyboard.yml > "$tmp/prompts.md" 2>/dev/null
diff -q "$tmp/prompts.md" examples/sunpeel/prompts.md >/dev/null && ok "committed prompts.md is up to date"
python3 scripts/matrix.py examples/sunpeel/storyboard.yml > "$tmp/matrix.csv" 2>/dev/null
diff -q "$tmp/matrix.csv" examples/sunpeel/matrix.csv >/dev/null && ok "committed matrix.csv is up to date"

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
  python3 scripts/cut.py examples/driftpay/storyboard.yml $cl -o "$tmp/cut.mp4" >/dev/null
  python3 scripts/spec_check.py "$tmp/cut.mp4" --platform meta_vertical linkedin_feed >/dev/null && ok "cut master passes its specs"
  python3 scripts/cut.py examples/driftpay/storyboard.yml $cl --aspect 4:5 -o "$tmp/cut45.mp4" >/dev/null
  python3 scripts/spec_check.py "$tmp/cut45.mp4" --platform meta_feed >/dev/null && ok "4:5 feed cut passes its specs"
  if python3 scripts/cut.py examples/driftpay/storyboard.yml --clip S01=$tmp/c1.mp4 -o "$tmp/x.mp4" >/dev/null 2>&1; then
    echo "FAIL cut with missing clips not caught"; exit 1; fi
  ok "cut refuses a storyboard with missing clips"

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
else
  echo "skip spec_check tests (ffmpeg not installed)"
fi
rm -rf "$tmp"
echo "all good"
