#!/usr/bin/env bash
# probe.sh — gate the final Reel: 1080x1920, h264, yuv420p, duration within ±0.1 s of config.
# usage: bash live/probe.sh live/reels/<reel>.json   -> prints WF_PROBE OK|FAIL, exits 1 on FAIL
set -uo pipefail

CFG="${1:?usage: probe.sh <config.json>}"
REEL=$(jq -r '.reel' "$CFG")
WANT=$(jq -r '.duration' "$CFG")
F="docs/$REEL.mp4"

fail() { echo "WF_PROBE FAIL $*"; exit 1; }
[ -s "$F" ] || fail "missing $F"

# One entry per call: ffprobe's csv field order is not the order you ask for.
q() { ffprobe -v error -select_streams v:0 -show_entries "$1" -of default=nw=1:nk=1 "$F" | head -n1; }
W=$(q stream=width); H=$(q stream=height); CODEC=$(q stream=codec_name); PIX=$(q stream=pix_fmt)
DUR=$(q format=duration); BYTES=$(stat -c%s "$F")
ACODEC=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$F" | head -n1)
echo "PROBE_DETAIL ${W}x${H} codec=$CODEC pix=$PIX dur=$DUR audio=${ACODEC:-none} bytes=$BYTES"

[ "$W" = 1080 ] && [ "$H" = 1920 ] || fail "size ${W}x${H} (want 1080x1920)"
[ "$CODEC" = h264 ] || fail "codec $CODEC (want h264)"
[ "$PIX" = yuv420p ] || fail "pix_fmt $PIX (want yuv420p)"
awk "BEGIN{d=$DUR-$WANT; exit !(d<=0.1 && d>=-0.1)}" || fail "duration $DUR (want $WANT ±0.1)"
echo "WF_PROBE OK $W,$H $DUR $BYTES"
