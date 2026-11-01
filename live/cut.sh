#!/usr/bin/env bash
# cut.sh v2 - trim takes into a 1080x1920 Reel with safe-zone captions + audio.
# usage: bash live/cut.sh live/reels/<reel>.json   (repo root, after record.mjs)
set -euo pipefail
CFG="${1:?usage: cut.sh <config.json>}"
REEL=$(jq -r '.reel' "$CFG"); DUR=$(jq -r '.duration' "$CFG")
AUDIO=$(jq -r '.audio // "silent"' "$CFG"); FALLBACK=$(jq -r '.fallback_to_scene // false' "$CFG")
FPS=30; RAW=out/raw; STATUS="$RAW/status.json"; WORK=out/shots; OUT="docs/$REEL.mp4"
FONT="${FONT:-/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf}"
FF=(ffmpeg -hide_banner -loglevel error -y)
SAFE_TOP=250; SAFE_BOTTOM=1420; MARGIN=90; SAFE_W=900
rm -rf "$WORK"; mkdir -p "$WORK" docs
[ -f "$STATUS" ] || echo '{}' > "$STATUS"
[ -f "$FONT" ] || { echo "CUT_FAIL font missing: $FONT"; exit 1; }
calc() { awk "BEGIN{printf \"%.3f\", $1}"; }
frames_of() { awk "BEGIN{printf \"%d\", $1*$FPS + 0.5}"; }
take_ok() { [ "$(jq -r --arg t "$1" '.[$t].ok // false' "$STATUS")" = true ] && [ -s "$RAW/$1.webm" ]; }

# " / " = line break. 0.80 em/char (was 0.74) leaves room for wide caps (W, M).
captions() {
  local text="$1" where="$2" idx="$3" n longest=0 fs lh y i f l
  [[ "$text" == *TODO* ]] && { echo "CUT_FAIL CAPTION_TODO shot $idx ($where): $text"; exit 1; }
  mapfile -t lines < <(printf '%s\n' "$text" | sed 's# */ *#\n#g')
  n=${#lines[@]}
  for l in "${lines[@]}"; do (( ${#l} > longest )) && longest=${#l}; done
  fs=$(awk "BEGIN{f=int($SAFE_W/($longest*0.80)); print (f>80?80:f)}")
  lh=$(( fs * 13 / 10 ))
  for ((i=0; i<n; i++)); do
    if [ "$where" = top ]; then y=$(( SAFE_TOP + 10 + i * lh )); else y=$(( SAFE_BOTTOM - 10 - (n - i) * lh )); fi
    f="$WORK/s${idx}_${where}_${i}.txt"; printf '%s' "${lines[$i]}" > "$f"
    echo "TEXT shot $idx $where line $i fs=$fs y=$y-$((y + fs)) '${lines[$i]}'"
    CAP+=",drawtext=fontfile=$FONT:textfile=$f:expansion=none:fontsize=$fs:fontcolor=white:borderw=6:bordercolor=black:x=max($MARGIN\\,(w-text_w)/2):y=$y"
  done
}

N=$(jq '.shots | length' "$CFG"); SUM=0; LIVE=0; FB=0
: > "$WORK/list.txt"
for ((i=0; i<N; i++)); do
  take=$(jq -r ".shots[$i].take" "$CFG"); start=$(jq -r ".shots[$i].start" "$CFG"); dur=$(jq -r ".shots[$i].dur" "$CFG")
  # A failed take is never used. Fallback only to a scene take that itself recorded ok.
  # The hook shot (0) may not fall back: its text describes the game.
  if take_ok "$take"; then LIVE=$((LIVE + 1))
  elif [ "$FALLBACK" = true ] && take_ok scene; then
    [ "$i" = 0 ] && { echo "CUT_FAIL shot 0 (hook) has no live footage for $take"; exit 1; }
    echo "SHOT $i FALLBACK $take -> scene"; take=scene; FB=$((FB + 1))
  else echo "CUT_FAIL shot $i: no usable footage for $take"; exit 1; fi
  lead=$(jq -r --arg t "$take" '.[$t].lead // 0' "$STATUS")
  ss=$(calc "$start + $lead"); nf=$(frames_of "$dur"); CAP=""
  top=$(jq -r ".shots[$i].text_top // empty" "$CFG"); bot=$(jq -r ".shots[$i].text_bottom // empty" "$CFG")
  [ -n "$top" ] && captions "$top" top "$i"
  [ -n "$bot" ] && captions "$bot" bottom "$i"
  # output-side -ss: Playwright webm has no cues, so input seeking is unreliable
  "${FF[@]}" -i "$RAW/$take.webm" -ss "$ss" \
    -vf "fps=$FPS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,tpad=stop_mode=clone:stop_duration=$dur$CAP" \
    -frames:v "$nf" -an -c:v libx264 -preset veryfast -crf 14 -pix_fmt yuv420p "$WORK/shot$i.mp4"
  echo "SHOT $i TAKE $take SS $ss DUR $dur FRAMES $nf"
  echo "file 'shot$i.mp4'" >> "$WORK/list.txt"
  SUM=$(calc "$SUM + $dur")
done
echo "FOOTAGE live=$LIVE fallback=$FB of $N shots"
awk "BEGIN{exit !($SUM == $DUR)}" || { echo "CUT_FAIL shot durations sum to $SUM, config.duration is $DUR"; exit 1; }

if [ "$AUDIO" = chiptune ]; then
  C="mod(floor(t/2),4)"; S="mod(floor(t*8),4)"
  B="(220*eq($C,0)+174.61*eq($C,1)+261.63*eq($C,2)+196*eq($C,3))"
  R="(eq($S,0)+1.5*eq($S,1)+2*eq($S,2)+1.5*eq($S,3))"
  EXPR="0.16*sgn(sin(2*PI*$B*$R*t))*(0.35+0.65*exp(-18*mod(t,0.125)))+0.10*sgn(sin(PI*$B*t))"
  ASRC=(-f lavfi -i "aevalsrc='$EXPR':s=44100:d=$DUR")
else
  ASRC=(-f lavfi -i "anullsrc=r=44100:cl=stereo")
fi
TOTAL=$(frames_of "$DUR")
"${FF[@]}" -f concat -safe 0 -i "$WORK/list.txt" "${ASRC[@]}" \
  -map 0:v:0 -map 1:a:0 -vf "fps=$FPS" -frames:v "$TOTAL" \
  -c:v libx264 -profile:v high -crf 20 -preset medium -pix_fmt yuv420p \
  -af "afade=t=out:st=$(calc "$DUR - 0.6"):d=0.6" -ac 2 -c:a aac -b:a 128k \
  -t "$DUR" -movflags +faststart "$OUT"
echo "CUT OK $OUT FRAMES $TOTAL BYTES $(stat -c%s "$OUT")"
