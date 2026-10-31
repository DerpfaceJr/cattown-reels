#!/usr/bin/env python3
"""@whatifrpg Post 4 'L or R?' doors loop (spec dfa972c2). DRAFT, never run. Drawn by code; numpy chiptune or silent."""
import math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 1080, 1920, 30, 6.0
N = int(FPS * DUR)
LW, LH = 270, 480
OUT, COVER, COVER_I = "docs/whatif4.mp4", "docs/whatif4_cover.png", 8
WAV = "build/whatif4_audio.wav"
SAFE = (90, 250, 900, 1500)
CX, SEED = 495, 20261103

WALL, BRICK, FLOOR1 = (40, 36, 58), (30, 26, 44), (62, 52, 78)
STICK, FL0, FL1 = (101, 67, 33), (255, 186, 8), (255, 120, 0)
SLIME, SHINE, HOLE = (114, 221, 102), (202, 255, 191), (12, 10, 20)
WOOD, TONGUE = (139, 90, 43), (220, 60, 60)
HERO, FACE = (76, 201, 240), (244, 241, 234)
WHITE, BLACK, GOLD = (255, 255, 255), (0, 0, 0), (255, 209, 102)
GLYPH = {"L": ("100", "100", "100", "100", "111"), "R": ("110", "101", "110", "101", "101")}

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


def plaque(d, ch, cx, cy):
    cells = [(cx - 3 + 2 * c, cy - 5 + 2 * r) for r, row in enumerate(GLYPH[ch])
             for c, v in enumerate(row) if v == "1"]
    for x, y in cells:
        d.rectangle((x - 1, y - 1, x + 2, y + 2), fill=BLACK)
    for x, y in cells:
        d.rectangle((x, y, x + 1, y + 1), fill=GOLD)


def arch(d, x0, x1):
    for k, c in ((0, shade(WALL, 1.3)), (4, HOLE)):
        d.ellipse((x0 + k, 250 + k, x1 - k, 310 - k), fill=c)
        d.rectangle((x0 + k, 280, x1 - k, 339), fill=c)


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
arch(_d, 40, 100)
arch(_d, 170, 230)
_d.rectangle((46, 328, 94, 339), fill=SLIME)
plaque(_d, "L", 70, 234)
plaque(_d, "R", 200, 234)


def torch(d, x, fl):
    d.rectangle((x - 2, 250, x + 1, 259), fill=STICK)
    a, b = (FL0, FL1) if fl else (FL1, FL0)
    d.rectangle((x - 3, 242, x + 2, 249), fill=a)
    d.rectangle((x - 1, 245 - fl, x, 249), fill=b)


def hero(d, x, yb, step, flip=False):
    def r(a, y0, b, y1, c):
        if flip:
            a, b = 15 - b, 15 - a
        d.rectangle((x + a, yb - y0, x + b, yb - y1), fill=c)
    r(0, 24, 15, 8, HERO)
    r(2, 22, 13, 14, FACE)
    r(4, 20, 5, 19, BLACK)
    r(10, 20, 11, 19, BLACK)
    a, b = (1, 4) if step else (4, 1)
    r(2, 8, 5, a, HERO)
    r(10, 8, 13, b, HERO)


def chest(d, t):
    lift = round(6 * max(0.0, math.sin(2 * math.pi * t)))
    d.rectangle((186, 330, 213, 339), fill=WOOD)
    d.rectangle((186, 333, 213, 334), fill=FL0)
    d.rectangle((186, 320 - lift, 213, 329 - lift), fill=WOOD)
    d.rectangle((186, 324 - lift, 213, 325 - lift), fill=FL0)
    if lift >= 2:
        for tx in range(188, 212, 4):
            d.rectangle((tx, 330 - lift, tx + 1, 331 - lift), fill=WHITE)
            d.rectangle((tx + 2, 328, tx + 3, 329), fill=WHITE)
        d.rectangle((198, 328, 201, 329), fill=TONGUE)


def arrows(d, dr):
    for x, s, on in ((112, -1, dr < 0), (157, 1, dr > 0)):
        c = GOLD if on else shade(GOLD, 0.4)
        d.polygon([(x, 315), (x - 5 * s, 312), (x - 5 * s, 318)], fill=c)


def low_frame(t, i):
    im = ROOM.copy()
    d = ImageDraw.Draw(im)
    fl = (i * 8 // 30) % 2
    torch(d, 30, fl)
    torch(d, 240, fl)
    for bx, off in ((55, 0.0), (68, 0.33), (82, 0.66)):
        p = (t / 1.5 + off) % 1.0
        if p <= 0.85:
            y = 336 - round(18 * p)
            d.rectangle((bx, y, bx + 2, y + 2), fill=SHINE)
    chest(d, t)
    dr = -1 if int(t // 1.5) % 2 == 0 else 1
    dx = dr * round(5 * math.sin(math.pi * (t % 1.5) / 1.5))
    arrows(d, dr)
    hero(d, 127 + dx, 340 + round(math.sin(2 * math.pi * t / 0.5)), 0, flip=dr < 0)
    return im


def overlay(img, t, i):
    d = ImageDraw.Draw(img)
    boxes = []

    def txt(s, size, cy, kind="main", fill=WHITE):
        kw = dict(font=font(size), anchor="mm", stroke_width=6)
        boxes.append((kind, d.textbbox((CX, cy), s, **kw)))
        d.text((CX, cy), s, fill=fill, stroke_fill=BLACK, **kw)

    txt("L = SLIME PIT", 52, 300)
    txt("R = MIMIC CHEST", 52, 380)
    txt("COMMENT L OR R", 36, 460, kind="small")
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

    def note(m, t0, dur, amp):
        dur = min(dur, end - t0)
        a, b = int(t0 * sr), min(n, int((t0 + dur) * sr))
        if a >= b:
            return
        tt = np.arange(b - a) / sr
        f = 440 * 2 ** ((m - 69) / 12)
        sq = np.sign(np.sin(2 * np.pi * f * tt))
        env = np.minimum(1, tt / 0.005) * np.exp(-tt * 4) * np.clip((dur - tt) / 0.005, 0, 1)
        out[a:b] += amp * sq * env

    E8 = 60 / 160 / 2
    A = [72, 0, 76, 79, 77, 76, 74, 0]
    LEAD = A + [76, 77, 79, 77, 76, 74, 79, 0] + A + [76, 77, 79, 77, 76, 74, 71, 0]
    BASS = ((48, 55), (53, 60), (48, 55), (55, 62))
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
    for t0, m in ((0.0, 64), (1.5, 76), (3.0, 64), (4.5, 76)):
        note(m, t0, 0.06, 0.3)
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
            if i == COVER_I:
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
