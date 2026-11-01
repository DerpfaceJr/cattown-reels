#!/usr/bin/env python3
"""motion.py v2 — prove the Reel really moves (stdlib + ffmpeg only).

usage: python3 live/motion.py live/reels/<reel>.json [video.mp4]
Decodes at 30 fps, grayscale 270x480, and measures the mean absolute frame-to-frame
difference (0-255). diff[i] compares frame i with frame i-1 (frame 0 has none).
Hard-cut frames between shots are excluded from the gate.
Prints MOTION_OK or MOTION_FAIL <reasons>; exits 1 on fail.
"""
import json
import subprocess
import sys
from operator import sub

W, H, FPS = 270, 480, 30
FRAME = W * H
FROZEN_DIFF, FROZEN_LEN = 0.5, 14  # 14 still diffs in a row = 15 identical frames
MIN_MOTION = 1.0


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


def frame_diffs(path):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={FPS},scale={W}:{H},format=gray",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    diffs, prev = [None], None
    while True:
        buf = p.stdout.read(FRAME)
        if len(buf) < FRAME:
            break
        if prev is not None:
            diffs.append(sum(map(abs, map(sub, buf, prev))) / FRAME)
        prev = buf
    if p.wait() != 0:
        sys.exit(f"MOTION_FAIL ffmpeg decode error on {path}")
    return diffs if prev is not None else []


def freezedetect(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-map", "0:v:0",
                        "-vf", "freezedetect=n=0.003:d=0.5", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [ln.strip() for ln in r.stderr.splitlines() if "lavfi.freezedetect" in ln]


def main():
    cfg = json.load(open(sys.argv[1]))
    path = sys.argv[2] if len(sys.argv) > 2 else f"docs/{cfg['reel']}.mp4"
    d = frame_diffs(path)
    n = len(d)
    print(f"MOTION_FILE {path}")
    print(f"MOTION_FRAMES {n}")
    if n < FPS + 1:
        print("MOTION_FAIL too few frames")
        sys.exit(1)

    cuts, t = set(), 0.0
    for s in cfg.get("shots", [])[:-1]:
        t += s["dur"]
        cuts.add(round(t * FPS))
    dm = [None if i in cuts else x for i, x in enumerate(d)]  # cut frames excluded
    print(f"MOTION_CUTS_EXCLUDED {sorted(cuts)}")
    vals = [x for x in dm[1:] if x is not None]
    srt = sorted(vals)
    motion_mean = mean(vals)
    p10 = srt[int(0.10 * (len(srt) - 1))]
    windows = [mean(dm[max(1, i):i + FPS]) for i in range(0, n - FPS + 1)]
    min_1s = min(windows)
    min_1s_at = windows.index(min_1s) / FPS
    first = mean(dm[1:FPS])

    runs, start = [], None
    for i in range(1, n + 1):
        still = i < n and dm[i] is not None and dm[i] < FROZEN_DIFF
        if still and start is None:
            start = i
        elif not still and start is not None:
            if i - start >= FROZEN_LEN:
                runs.append((start, i - 1))
            start = None

    print(f"MOTION_MEAN {motion_mean:.3f}")
    print(f"MOTION_P10 {p10:.3f}")
    print(f"MOTION_MIN_1S {min_1s:.3f} (window starting {min_1s_at:.2f}s)")
    print(f"FIRST_SECOND_MOTION {first:.3f}")
    print(f"FROZEN_RUNS {len(runs)}")
    for a, b in runs:  # picture is static from frame a-1 through frame b
        print(f"  FROZEN {(a - 1) / FPS:.2f}s-{(b + 1) / FPS:.2f}s ({b - a + 2} frames)")

    t = 0.0
    for i, s in enumerate(cfg.get("shots", [])):
        a, b = round(t * FPS), min(n, round((t + s["dur"]) * FPS))
        # skip the cut frame itself so the hard cut doesn't inflate the shot's score
        print(f"PER_SHOT_MOTION {i} {s['take']} {t:.2f}-{t + s['dur']:.2f}s {mean(d[a + 1:b]):.3f}")
        t += s["dur"]

    fd = freezedetect(path)
    print(f"FREEZEDETECT {sum('freeze_start' in ln for ln in fd)} freezes ({len(fd)} lines)")
    for ln in fd:
        print(f"  {ln}")

    print("PER_SECOND_MOTION")
    for sec in range((n + FPS - 1) // FPS):
        m = mean(d[sec * FPS:(sec + 1) * FPS])
        print(f"  {sec:2d}s {m:7.3f} {'#' * min(60, int(m * 4))}")

    reasons = []
    if runs:
        reasons.append(f"{len(runs)} frozen run(s)")
    if min_1s < MIN_MOTION:
        reasons.append(f"MOTION_MIN_1S {min_1s:.3f} < {MIN_MOTION}")
    if first < MIN_MOTION:
        reasons.append(f"FIRST_SECOND_MOTION {first:.3f} < {MIN_MOTION}")
    if reasons:
        print("MOTION_FAIL " + "; ".join(reasons))
        sys.exit(1)
    print("MOTION_NOTE pixel motion only; it does not prove game footage. See SHOT/FOOTAGE lines.")
    print("MOTION_OK")


if __name__ == "__main__":
    main()
