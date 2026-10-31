#!/usr/bin/env python3
"""@whatifrpg Post 3 POV floor 1 slime loop (spec 5930ff8b). DRAFT, never run. Every frame drawn by code; numpy chiptune or silent."""
import math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 1080, 1920, 30, 6.0
N = int(FPS * DUR)
LW, LH = 270, 480
OUT, COVER = "docs/whatif3.mp4", "docs/whatif3_cover.png"
WAV = "build/whatif3_audio.wav"
SAFE = (90, 250, 900, 1500)
CX, SEED = 495, 20261102

WALL, BRICK, FLOOR1 = (40, 36, 58), (30, 26, 44), (62, 52, 78)
STICK, FL0, FL1 = (101, 67, 33), (255, 186, 8), (255, 120, 0)
SLIME, SHINE, SWEAT = (114, 221, 102), (202, 255, 191), (76, 201, 240)
HERO, FACE = (76, 201, 240), (244, 241, 234)
WHITE, BLACK, GOLD = (255, 255, 255), (0, 0, 0), (255, 209, 102)

FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_fc = {}


def font(size):
    if size not in _fc:
        path = next((p for p in FONTS if os.path.exists(p)), None)
        _fc[size] = ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)
    return _fc[size]


def shade(c, k):
    return tuple(int(v * k) for v in c)


ROOM = Image.new("RGB", (LW, LH), WALL)
_d = ImageDraw.Draw(ROOM)
for _r, _y in enumerate(range(0, 340, 12)):
    _d.line((0, _y, LW, _y), fill=BRICK)
    for _x in range(12 * (_r % 2), LW, 24):
        _d.line((_x, _y, _x, min(_y + 11, 339)), fill=BRICK)
_d.rectangle((0, 340, LW - 1, LH - 1), fill=FLOOR1)
for _x in range(0, LW, 30):
    _d.line((_x, 340, _x, LH - 1), fill=shade(FLOOR1, 0.8))
for _y in range(370, LH, 30):
    _d.line((0, _y, LW - 1, _y), fill=shade(FLOOR1, 0.8))


def torch(d, x, fl):
    d.rectangle((x - 2, 250, x + 1, 259), fill=STICK)
    a, b = (FL0, FL1) if fl else (FL1, FL0)
    d.rectangle((x - 3, 242, x + 2, 249), fill=a)
    d.rectangle((x - 1, 245 - fl, x, 249), fill=b)


def hero(d, x, yb, step):
    d.rectangle((x, yb - 24, x + 15, yb - 8), fill=HERO)
    d.rectangle((x + 2, yb - 22, x + 13, yb - 14), fill=FACE)
    d.rectangle((x + 4, yb - 20, x + 5, yb - 19), fill=BLACK)
    d.rectangle((x + 10, yb - 20, x + 11, yb - 19), fill=BLACK)
    a, b = (1, 4) if step else (4, 1)
    d.rectangle((x + 2, yb - 8, x + 5, yb - a), fill=HERO)
    d.rectangle((x + 10, yb - 8, x + 13, yb - b), fill=HERO)


def hero_xy(t):
    ph = (t / DUR + 0.12) % 1.0
    hx = round(-16 + 302 * ph)
    if 0.38 <= ph < 0.57:
        return hx, 340 - round(40 * math.sin(math.pi * (ph - 0.38) / 0.19)), False
    return hx, 340, True


def slime(d, t):
    cx, by = 135, 340
    duck = 2.10 <= t < 2.60
    if duck:
        w, h = 48, 8
    else:
        if 2.60 <= t < 3.25:
            s = 3 * math.sin(2 * math.pi * (t - 2.6) / 0.3) * (1 - (t - 2.6) / 0.65)
        else:
            s = math.sin(2 * math.pi * t / 0.5)
        w, h = 36 + round(2 * s), 24 - round(2 * s)
    x0, y0 = cx - w // 2, by - h
    d.rounded_rectangle((x0, y0, x0 + w - 1, by - 1), radius=min(8, h // 2), fill=SLIME)
    if duck:
        for ex in (126, 141):
            d.rectangle((ex, by - 5, ex + 2, by - 5), fill=BLACK)
    else:
        dx = -2 if 0.90 <= t < 1.56 else 0
        d.rectangle((x0 + 5, y0 + 3, x0 + 10, y0 + 6), fill=SHINE)
        for ex in (126 + dx, 141 + dx):
            d.rectangle((ex, y0 + 10, ex + 2, y0 + 12), fill=BLACK)
    if 0.90 <= t < 1.56:
        d.rectangle((x0 + w - 4, y0 - 2, x0 + w - 1, y0 + 3), fill=SWEAT)
    if 1.00 <= t < 1.60:
        bx, top = cx - 1, y0 - 20
        d.rectangle((bx - 1, top - 1, bx + 2, top + 12), fill=BLACK)
        d.rectangle((bx, top, bx + 1, top + 7), fill=GOLD)
        d.rectangle((bx, top + 10, bx + 1, top + 11), fill=GOLD)


def low_frame(t, i):
    im = ROOM.copy()
    d = ImageDraw.Draw(im)
    fl = (i * 8 // 30) % 2
    torch(d, 30, fl)
    torch(d, 240, fl)
    slime(d, t)
    hx, hy, walk = hero_xy(t)
    hero(d, hx, hy, (i // 5) % 2 if walk else 0)
    return im


def overlay(img, t, i):
    d = ImageDraw.Draw(img)
    boxes = []

    def txt(s, size, cy, kind="main", fill=WHITE):
        kw = dict(font=font(size), anchor="mm", stroke_width=6)
        boxes.append((kind, d.textbbox((CX, cy), s, **kw)))
        d.text((CX, cy), s, fill=fill, stroke_fill=BLACK, **kw)

    txt("POV: YOU'RE THE", 48, 300)
    txt("FLOOR 1 SLIME", 60, 380)
    txt("IN DEVELOPMENT", 32, 460, kind="small", fill=FACE)
    return boxes


def check(i, t, img, boxes):
    e = []
    if img.size != (W, H) or img.mode != "RGB":
        e.append(f"f{i}: frame {img.size} {img.mode}")
    main = sum(1 for k, _ in boxes if k == "main")
    if main > 2 or len(boxes) - main > 1:
        e.append(f"f{i}: {main} main / {len(boxes) - main} small lines")
    for k, (x0, y0, x1, y1) in boxes:
        if x0 < SAFE[0] or y0 < SAFE[1] or x1 > SAFE[2] or y1 > SAFE[3]:
            e.append(f"f{i}: {k} text box {(x0, y0, x1, y1)} outside safe zone")
    return e


def frame(i, t):
    img = low_frame(t, i).resize((W, H), Image.NEAREST)
    return img, overlay(img, t, i)


def make_audio(path):
    import numpy as np
    import wave
    sr, end = 44100, DUR - 0.05
    n = int(sr * DUR)
    out = np.zeros(n)
    rng = np.random.default_rng(SEED)

    def note(m, t0, dur, amp, m1=None):
        dur = min(dur, end - t0)
        a, b = int(t0 * sr), min(n, int((t0 + dur) * sr))
        if a >= b:
            return
        tt = np.arange(b - a) / sr
        f = 440 * 2 ** ((m + ((m1 or m) - m) * tt / dur - 69) / 12)
        sq = np.sign(np.sin(2 * np.pi * np.cumsum(f) / sr))
        env = np.minimum(1, tt / 0.005) * np.exp(-tt * 4) * np.clip((dur - tt) / 0.005, 0, 1)
        out[a:b] += amp * sq * env

    E8 = 60 / 160 / 2
    LEAD = [72, 67] * 4 + [74, 69, 76, 69, 77, 71, 79, 71, 76, 72, 77, 72, 79, 74, 81, 74,
                           79, 76, 74, 71, 67, 71, 72, 0]
    BASS = ((48, 55), (53, 60), (55, 62), (48, 55))
    hl = int(0.03 * sr)
    henv = np.exp(-np.arange(hl) / (0.006 * sr))
    for k, m in enumerate(LEAD):
        if m:
            note(m, k * E8, E8 * (2 if k == 30 else 0.9), 0.5)
        if k % 2 == 0:
            note(BASS[k // 8][(k // 2) % 2], k * E8, E8 * 1.8, 0.35)
        else:
            a = int(k * E8 * sr)
            out[a:a + hl] += 0.15 * np.diff(rng.standard_normal(hl + 1)) * henv
    note(81, 2.10, 0.12, 0.4, m1=69)
    peak = float(np.max(np.abs(out)))
    if peak <= 0:
        raise ValueError("silent mix")
    out *= 10 ** (-6 / 20) / peak
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(np.round(out * 32767).astype("<i2").tobytes())


def cmd(audio):
    a = ["-i", WAV] if audio else ["-f", "lavfi", "-t", str(DUR), "-i", "anullsrc=r=48000:cl=stereo"]
    return ["ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            *a, "-map", "0:v", "-map", "1:a", "-shortest", "-t", str(DUR),
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", OUT]


def render(audio):
    p = subprocess.Popen(cmd(audio), stdin=subprocess.PIPE)
    errs = []
    try:
        for i in range(N):
            t = (i % N) / FPS
            img, boxes = frame(i, t)
            errs += check(i, t, img, boxes)
            if i == 0:
                img.save(COVER)
            try:
                p.stdin.write(img.tobytes())
            except BrokenPipeError:
                break
    finally:
        try:
            p.stdin.close()
        except BrokenPipeError:
            pass
        rc = p.wait()
    return errs, rc


def probe():
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:format=duration",
                        "-of", "default=noprint_wrappers=1", OUT], capture_output=True, text=True)
    kv = [ln.partition("=")[::2] for ln in r.stdout.splitlines()]
    dur = next((float(v) for k, v in kv if k == "duration" and v.strip() != "N/A"), 0.0)
    return r.returncode, ("codec_type", "audio") in kv, dur


if __name__ == "__main__":
    os.makedirs("docs", exist_ok=True)
    os.makedirs("build", exist_ok=True)
    f0, _ = frame(0, 0.0)
    fn, _ = frame(N, N / FPS)
    loop_ok = f0.tobytes() == fn.tobytes()
    print("LOOP=OK" if loop_ok else "LOOP=FAIL")
    audio, errs, rc = False, [], 1
    try:
        make_audio(WAV)
        errs, rc = render(True)
        audio = rc == 0
    except Exception as ex:
        print(f"chiptune failed: {ex!r}", file=sys.stderr)
    if not audio:
        errs, rc = render(False)
    print("AUDIO=chiptune" if audio else "AUDIO=silent")
    if rc != 0:
        print(f"FAIL: ffmpeg exit {rc}")
        sys.exit(1)
    if errs:
        print(f"FAIL: {len(errs)} check errors")
        for e in errs[:20]:
            print("  " + e)
        sys.exit(1)
    prc, has_audio, dur = probe()
    ok = prc == 0 and has_audio and 5.9 <= dur <= 6.1
    print(f"PROBE: audio_stream={has_audio} duration={dur:.3f}s -> {'OK' if ok else 'FAIL'}")
    if not ok or not loop_ok:
        sys.exit(1)
    print(f"OK: wrote {OUT} and {COVER}")
