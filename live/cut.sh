#!/usr/bin/env bash
# cut.sh v5 - trim takes into a 1080x1920 Reel with backed safe-zone captions + audio.
# usage: bash live/cut.sh live/reels/<reel>.json   (repo root, after record.mjs)
# v3: a take may be out/raw/<take>.mp4 (frame-by-frame capture) or out/raw/<take>.webm (real-time).
# v4: every caption line sits on a semi-opaque backing box; TEXTBOX x0,y0,x1,y1 is logged per line and
#     the cut fails if a box leaves the 9:16 safe zone (x<=960, 220<=y<=1500). AUDIO= line logged.
# v5: caption width/height are MEASURED from the font file (live/textw.py: hmtx advances, hhea
#     ascent-descent) and each line is drawn at the logged x, so the TEXTBOX is the real box.
#     Per-shot `counter` text (e.g. DEATH 3) on its own backed plate under the hook.
#     GATE3D for whatif* reels: every take URL is daily-tower-web/3d.html, '3D ROGUELIKE' is in the
#     on-screen text and in caption line 1, else no MP4.
set -euo pipefail
CFG="${1:?usage: cut.sh <config.json>}"
REEL=$(jq -r '.reel' "$CFG"); DUR=$(jq -r '.duration' "$CFG")
AUDIO=$(jq -r '.audio // "silent"' "$CFG"); FALLBACK=$(jq -r '.fallback_to_scene // false' "$CFG")
FPS=30; RAW=out/raw; STATUS="$RAW/status.json"; WORK=out/shots; OUT="docs/$REEL.mp4"
FONT="${FONT:-/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf}"
FF=(ffmpeg -hide_banner -loglevel error -y)
SAFE_TOP=250; SAFE_BOTTOM=1420; MARGIN=90; SAFE_W=760; BOXB=18; RIGHT_MAX=940; COUNTER_FS=56; COUNTER_Y=490
rm -rf "$WORK"; mkdir -p "$WORK" docs
[ -f "$STATUS" ] || echo '{}' > "$STATUS"
[ -f "$FONT" ] || { echo "CUT_FAIL font missing: $FONT"; exit 1; }
calc() { awk "BEGIN{printf \"%.3f\", $1}"; }
frames_of() { awk "BEGIN{printf \"%d\", $1*$FPS + 0.5}"; }
src_of() { if [ -s "$RAW/$1.mp4" ]; then echo "$RAW/$1.mp4"; else echo "$RAW/$1.webm"; fi; }
take_ok() { [ "$(jq -r --arg t "$1" '.[$t].ok // false' "$STATUS")" = true ] && [ -s "$(src_of "$1")" ]; }

# GATE3D: @whatifrpg reels must present Daily Tower as a 3D roguelike, captured from 3d.html only.
if [[ "$REEL" == whatif* ]]; then
  NT=$(jq '.takes | length' "$CFG")
  BAD=$(jq -r '.takes[].url // "none"' "$CFG" | grep -cvE '^https://derpfacejr\.github\.io/daily-tower-web/3d\.html([?#].*)?$' || true)
  ONSCREEN=$(jq -r '[.shots[] | .text_top, .text_bottom, .counter] | map(select(. != null)) | join(" / ")' "$CFG")
  CAP1=$(jq -r '(.caption // "") | split("\n")[0]' "$CFG")
  G_URL=OK; G_TXT=OK; G_CAP=OK
  if [ "$BAD" != 0 ]; then G_URL=FAIL; fi
  grep -qi '3D ROGUELIKE' <<<"$ONSCREEN" || G_TXT=FAIL
  grep -qi '3D ROGUELIKE' <<<"$CAP1" || G_CAP=FAIL
  echo "CAPTION_LINE1 $CAP1"
  echo "GATE3D takes=$NT non_3d_urls=$BAD url=$G_URL onscreen_text=$G_TXT caption_line1=$G_CAP"
  if [ "$G_URL$G_TXT$G_CAP" != OKOKOK ]; then echo "CUT_FAIL GATE3D"; exit 1; fi
  echo "GATE3D OK"
fi

# measure SIZE TEXT -> MW MH (pixels, from the font file)
measure() {
  local r
  r=$(python3 live/textw.py "$FONT" "$1" "$2") || { echo "CUT_FAIL TEXTW fs=$1 '$2'"; exit 1; }
  MW=${r%% *}; MH=${r##* }
}

TOPEND=0
# " / " = line break. Largest fs <= 80 (counter: <= 56) whose measured width fits SAFE_W.
captions() {
  local text="$1" where="$2" idx="$3" n fs lh y base i f l fit x0 bx0 bx1 by0 by1 safe
  if [[ "$text" == *TODO* ]]; then echo "CUT_FAIL CAPTION_TODO shot $idx ($where): $text"; exit 1; fi
  mapfile -t lines < <(printf '%s\n' "$text" | sed 's# */ *#\n#g')
  n=${#lines[@]}
  if [ "$where" = counter ]; then fs=$COUNTER_FS; else fs=80; fi
  while true; do
    fit=1
    for l in "${lines[@]}"; do measure "$fs" "$l"; if (( MW > SAFE_W )); then fit=0; fi; done
    if (( fit == 1 )); then break; fi
    fs=$(( fs - 2 ))
    if (( fs < 24 )); then echo "CUT_FAIL text too wide even at fs 24: $text"; exit 1; fi
  done
  measure "$fs" "${lines[0]}"; lh=$(( MH + 2 * BOXB ))
  case "$where" in
    top) base=$(( SAFE_TOP + 10 )) ;;
    counter) base=$COUNTER_Y; if (( TOPEND > 0 && base - BOXB < TOPEND + 12 )); then base=$(( TOPEND + 12 + BOXB )); fi ;;
    *) base=$(( SAFE_BOTTOM - 10 - n * lh )) ;;
  esac
  for ((i=0; i<n; i++)); do
    y=$(( base + i * lh ))
    f="$WORK/s${idx}_${where}_${i}.txt"; printf '%s' "${lines[$i]}" > "$f"
    measure "$fs" "${lines[$i]}"
    x0=$(( (1080 - MW) / 2 ))
    if (( x0 < MARGIN )); then x0=$MARGIN; fi
    if (( x0 + MW + BOXB > RIGHT_MAX )); then x0=$(( RIGHT_MAX - BOXB - MW )); fi
    bx0=$(( x0 - BOXB )); bx1=$(( x0 + MW + BOXB )); by0=$(( y - BOXB )); by1=$(( y + MH + BOXB ))
    safe=OK
    if (( bx0 < 0 || bx1 > 960 || by0 < 220 || by1 > 1500 )); then safe=FAIL; fi
    if [ "$where" = top ]; then TOPEND=$by1; fi
    echo "TEXT shot $idx $where line $i fs=$fs w=$MW h=$MH x=$x0 y=$y '${lines[$i]}'"
    echo "TEXTBOX $REEL shot $idx $where line $i $bx0,$by0,$bx1,$by1 safe=$safe (measured: textw.py hmtx advances + hhea ascent-descent of $(basename "$FONT"); zone x<=960, 220<=y<=1500)"
    if [ "$safe" != OK ]; then echo "CUT_FAIL TEXTBOX outside safe zone: shot $idx $where line $i"; exit 1; fi
    CAP+=",drawtext=fontfile=$FONT:textfile=$f:expansion=none:fontsize=$fs:fontcolor=white:borderw=6:bordercolor=black:box=1:boxcolor=black@0.62:boxborderw=$BOXB:x=$x0:y=$y"
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
  ss=$(calc "$start + $lead"); nf=$(frames_of "$dur"); CAP=""; SRC=$(src_of "$take"); TOPEND=0
  top=$(jq -r ".shots[$i].text_top // empty" "$CFG"); bot=$(jq -r ".shots[$i].text_bottom // empty" "$CFG")
  cnt=$(jq -r ".shots[$i].counter // empty" "$CFG")
  [ -n "$top" ] && captions "$top" top "$i"
  [ -n "$cnt" ] && captions "$cnt" counter "$i"
  [ -n "$bot" ] && captions "$bot" bottom "$i"
  # output-side -ss: Playwright webm has no cues, so input seeking is unreliable
  "${FF[@]}" -i "$SRC" -ss "$ss" \
    -vf "fps=$FPS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,tpad=stop_mode=clone:stop_duration=$dur$CAP" \
    -frames:v "$nf" -an -c:v libx264 -preset veryfast -crf 14 -pix_fmt yuv420p "$WORK/shot$i.mp4"
  echo "SHOT $i TAKE $take SRC $SRC SS $ss DUR $dur FRAMES $nf COUNTER ${cnt:--}"
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
  AUDIO_DESC="chiptune (square-wave loop synthesized by ffmpeg aevalsrc in cut.sh; no third-party music, no game audio)"
else
  ASRC=(-f lavfi -i "anullsrc=r=44100:cl=stereo")
  AUDIO_DESC="silent (anullsrc; add music in the Instagram app)"
fi
TOTAL=$(frames_of "$DUR")
"${FF[@]}" -f concat -safe 0 -i "$WORK/list.txt" "${ASRC[@]}" \
  -map 0:v:0 -map 1:a:0 -vf "fps=$FPS" -frames:v "$TOTAL" \
  -c:v libx264 -profile:v high -crf 20 -preset medium -pix_fmt yuv420p \
  -af "afade=t=out:st=$(calc "$DUR - 0.6"):d=0.6" -ac 2 -c:a aac -b:a 128k \
  -t "$DUR" -movflags +faststart "$OUT"
echo "AUDIO=$AUDIO_DESC"
echo "CUT OK $OUT FRAMES $TOTAL BYTES $(stat -c%s "$OUT")"
