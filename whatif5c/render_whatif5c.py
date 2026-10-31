#!/usr/bin/env python3
"""@whatifrpg Post 5C 'HE WON'T MOVE' 12 s loop (spec e506c07f). DRAFT, never run. Drawn by code; numpy chiptune or silent."""
import math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 1080, 1920, 30, 12.0
N = int(FPS * DUR)
LW, LH = 270, 480
OUT, COVER, COVER_I = "docs/whatif5c.mp4", "docs/whatif5c_cover.png", 8
WAV = "build/whatif5c_audio.wav"
SAFE = (90, 250, 900, 1500)
CX, SEED, HX = 495, 20261106, 127

WALL, BRICK, FLOOR1 = (40, 36, 58), (30, 26, 44), (62, 52, 78)
STICK, FL0, FL1 = (101, 67, 33), (255, 186, 8), (255, 120, 0)
SLIME, SHINE, HOLE = (114, 221, 102), (202, 255, 191), (12, 10, 20)
WOOD, TONGUE, DUST = (139, 90, 43), (220, 60, 60), (99, 83, 124)
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


def facing(i):
    if i < 90 or i >= 270:
        return -1
    if i < 180:
        return 1
    return 1 if (i - 180) // 15 % 2 == 0 else -1


def low_frame(t, i):
    i %= N
    t = i / FPS
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
    dr = facing(i)
    if i < 270:
        yb = 340 + round(math.sin(2 * math.pi * t))
        arrows(d, dr)
    else:
        yb = 340 - round(10 * math.sin(math.pi * ((i - 270) % 30) / 30))
        arrows(d, 1 if (i - 270) // 15 % 2 == 0 else -1)
    hero(d, HX, yb, 0, flip=dr < 0)
    cx = HX + 8
    if i < 270:
        for o in (-4, 0, 4)[:(i % 45) // 15 + 1]:
            d.rectangle((cx + o - 1, 306, cx + o, 307), fill=WHITE)
    else:
        d.rectangle((cx - 1, yb - 36, cx, yb - 31), fill=WHITE)
        d.rectangle((cx - 1, yb - 29, cx, yb - 28), fill=WHITE)
    for k in (i, i - 300, i - 330):
        if 0 <= k < 9:
            for x in (128, 142):
                d.rectangle((x, 338 - k // 3, x + 1, 339 - k // 3), fill=DUST)
    return im


def overlay(img, t, i):
    d = ImageDraw.Draw(img)
    boxes = []

    def txt(s, size, cy, kind="main", fill=WHITE):
        kw = dict(font=font(size), anchor="mm", stroke_width=6)
        boxes.append((kind, d.textbbox((CX, cy), s, **kw)))
        d.text((CX, cy), s, fill=fill, stroke_fill=BLACK, **kw)

    a, b = ("HE WON'T MOVE", "UNTIL YOU PICK") if i % N < 270 else ("YOUR CALL.", "LEFT OR RIGHT?")
    txt(a, 52, 300)
    txt(b, 52, 380)
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

    def hit(t0, ln, dk, amp, hz=0):
        a = int(t0 * sr)
        tt = np.arange(max(0, min(int(ln * sr), n - a))) / sr
        w = rng.standard_normal(len(tt)) + 2 * np.sin(2 * np.pi * hz * tt)
        out[a:a + len(tt)] += amp * w * np.exp(-tt / dk)

    B = 60 / 160
    P = [72, 0, 76, 74, 0, 72, 71, 0]
    BASS = ((48, 55), (53, 60), (48, 55), (55, 62))
    for j, m in enumerate(P):
        if m:
            note(m, j * 2 * B, 1.8 * B, 0.45)
            note(m, 6 + j * B, 0.9 * B, 0.5)
    for j, m in enumerate([77, 81, 84, 81, 79, 82, 81, 76] * 2):
        note(m, 9 + j * B / 2, 0.45 * B, 0.5)
    for b in range(32):
        note(BASS[b // 4 % 4][b % 2], b * B, 0.9 * B, 0.35)
        hit(b * B + B / 2, 0.03, 0.006, 0.08)
        if b >= 24 and b % 2:
            hit(b * B, 0.08, 0.02, 0.15)
    for t0 in (0.0, 10.0, 11.0):
        hit(t0, 0.06, 0.02, 0.2, 80)
    note(76, 3.0, 0.06, 0.3)
    for k, t0 in enumerate((6.5, 7.0, 7.5, 8.0, 8.5)):
        note(76 if k % 2 else 64, t0, 0.03, 0.3)
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
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                        "-of", "default=noprint_wrappers=1", OUT], capture_output=True, text=True)
    kv = [ln.partition("=")[::2] for ln in r.stdout.splitlines()]
    dur = next((float(v) for k, v in kv if k == "duration" and v.strip() != "N/A"), 0.0)
    g = lambda key: next((v for k, v in kv if k == key), "?")
    return r.returncode, ("codec_type", "audio") in kv, dur, f"{g('width')}x{g('height')}"


if __name__ == "__main__":
    os.makedirs("docs", exist_ok=True)
    os.makedirs("build", exist_ok=True)
    f0, _ = frame(0, 0.0)
    fn, _ = frame(N, N / FPS)
    loop_ok = f0.tobytes() == fn.tobytes()
    print("LOOP=OK" if loop_ok else "LOOP=FAIL")
    try:
        import numpy as np
        a = np.asarray(frame(N - 1, (N - 1) / FPS)[0], dtype=float)[520:]
        print(f"SEAM_DIFF={np.abs(a - np.asarray(f0, dtype=float)[520:]).mean():.2f}")
    except Exception as ex:
        print(f"SEAM_DIFF=NA {ex!r}")
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
    prc, has_audio, dur, size = probe()
    ok = prc == 0 and has_audio and 11.9 <= dur <= 12.1 and size == f"{W}x{H}"
    print(f"PROBE: size={size} audio_stream={has_audio} duration={dur:.3f}s -> {'OK' if ok else 'FAIL'}")
    if not ok or not loop_ok:
        sys.exit(1)
    print(f"OK: wrote {OUT} and {COVER}")
