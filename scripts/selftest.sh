#!/usr/bin/env bash
# Runs every script against the Sunpeel example and a synthetic video.
# Usage: bash scripts/selftest.sh
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=.selftest; rm -rf "$tmp"; mkdir -p "$tmp"
ok() { echo "ok   $1"; }

python3 scripts/assemble.py examples/sunpeel/storyboard.yml --check 2>/dev/null && ok "sunpeel passes pre-checks"
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
else
  echo "skip spec_check tests (ffmpeg not installed)"
fi
rm -rf "$tmp"
echo "all good"
