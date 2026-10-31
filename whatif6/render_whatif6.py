#!/usr/bin/env python3
# @whatifrpg Reel 6 '4 WAYS TO DIE', 15 s loop (plan 3e9e9e3e).
import math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR, N, SEG = 1080, 1920, 30, 15.0, 450, 90
LW, LH, FL, CX = 270, 480, 340, 495
WINR = os.environ.get("WIN") == "R"
ORDER = (1, 0, 2, 3) if WINR else (0, 1, 2, 3)
OUT, COVER, WAV = "docs/whatif6.mp4", "docs/whatif6_cover.png", "build/whatif6.wav"
COVER_I = 48 if WINR else 6
SAFE = (90, 250, 900, 1500)
TYPES = ("SLIME PIT", "MIMIC CHEST", "SPIKE FLOOR", "FALLING TORCH")
DEATH_K = (15, 54, 30, 45)
FLOOR1, FL0, FL1, SLIME, SHINE = (62, 52, 78), (255, 186, 8), (255, 120, 0), (114, 221, 102), (202, 255, 191)
HOLE, WOOD, RED, DUST, GREY = (12, 10, 20), (139, 90, 43), (220, 60, 60), (99, 83, 124), (200, 200, 214)
HERO, FACE, WHITE, BLACK = (76, 201, 240), (244, 241, 234), (255, 255, 255), (0, 0, 0)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
_fc = {}


def font(s):
    if s not in _fc:
        _fc[s] = ImageFont.truetype(FONT, s) if os.path.exists(FONT) else ImageFont.load_default(size=s)
    return _fc[s]


def shade(c, k):
    return tuple(int(v * k) for v in c)


def lerp(a, b, k):
    return round(a + (b - a) * min(1.0, max(0.0, k)))


ROOM = Image.new("RGB", (LW, LH), (40, 36, 58))
_d = ImageDraw.Draw(ROOM)
for _r, _y in enumerate(range(0, FL, 12)):
    _d.line((0, _y, LW, _y), fill=(30, 26, 44))
    for _x in range(12 * (_r % 2), LW, 24):
        _d.line((_x, _y, _x, min(_y + 11, FL - 1)), fill=(30, 26, 44))
_d.rectangle((0, FL, LW - 1, LH - 1), fill=FLOOR1)
for _x in range(0, LW, 30):
    _d.line((_x, FL, _x, LH - 1), fill=shade(FLOOR1, 0.8))


def torch(d, x, y, fl):
    d.rectangle((x - 2, y, x + 1, y + 9), fill=(101, 67, 33))
    a, b = (FL0, FL1) if fl else (FL1, FL0)
    d.rectangle((x - 3, y - 8, x + 2, y - 1), fill=a)
    d.rectangle((x - 1, y - 5 - fl, x, y - 1), fill=b)


def hero(d, x, yb, step=0, col=HERO):
    def r(a, y0, b, y1, c):
        top, bot = yb - y0, min(yb - y1, FL - 1)
        if top <= bot:
            d.rectangle((x + a, top, x + b, bot), fill=c)
    r(0, 24, 15, 8, col)
    r(2, 22, 13, 14, FACE)
    r(4, 20, 5, 19, BLACK)
    r(10, 20, 11, 19, BLACK)
    a, b = (1, 4) if step else (4, 1)
    r(2, 8, 5, a, col)
    r(10, 8, 13, b, col)


def chest(d, lift):
    R = d.rectangle
    R((150, 316, 185, 339), fill=WOOD)
    R((150, 326, 185, 328), fill=FL0)
    if lift > 0:
        R((151, 316 - lift, 184, 316), fill=HOLE)
    R((150, 304 - lift, 185, 315 - lift), fill=WOOD)
    R((150, 309 - lift, 185, 310 - lift), fill=FL0)
    if lift > 3:
        for tx in range(152, 182, 5):
            R((tx, 316 - lift, tx + 2, 318 - lift), fill=WHITE)
            R((tx + 2, 314, tx + 4, 316), fill=WHITE)


def spikes(d, x0, x1, h):
    for sx in range(x0, x1, 8):
        if h > 0:
            d.polygon([(sx, FL - 1), (sx + 3, FL - 1 - h), (sx + 7, FL - 1)], fill=GREY)


def low_frame(i):
    s, k = divmod(i % N, SEG)
    ty = ORDER[s] if s < 4 else 4
    im = ROOM.copy()
    d = ImageDraw.Draw(im)
    R = d.rectangle
    fl = i * 8 // 30 % 2
    torch(d, 30, 250, fl)
    torch(d, 240, 250, fl)
    st = i // 6 % 2
    if ty == 0:
        R((100, FL, 160, 371), fill=shade(SLIME, 0.7))
        R((100, FL, 160, FL + 3), fill=SLIME)
        hero(d, 122, 300 + round(52 * (k / 15) ** 2) if k < 15 else min(376, 352 + round(24 * (k - 15) / 30)))
        if 15 <= k < 27:
            y = FL - 3 - round(13 * math.sin(math.pi * (k - 15) / 12))
            for x in (118 - (k - 15), 138 + (k - 15)):
                R((x, y, x + 2, y + 2), fill=SHINE)
        if k >= 45:
            for x, off in ((124, 0.0), (134, 0.5)):
                y = FL - 3 - round(16 * (((k - 45) / 22 + off) % 1))
                R((x, y, x + 2, y + 2), fill=SHINE)
    elif ty == 1:
        x = lerp(70, 118, k / 30) if k < 42 else lerp(118, 160, (k - 42) / 12)
        yb = FL - round(14 * math.sin(math.pi * (k - 42) / 12)) if 42 <= k < 54 else FL
        hero(d, x, yb, st if k < 30 else 0)
        chest(d, lerp(0, 12, (k - 30) / 6) if k < 54 else (lerp(12, 0, (k - 54) / 4) if k < 60 else 3 * (k // 5 % 2)))
        if 34 <= k < 48:
            R((150 - (34 if k < 42 else lerp(34, 0, (k - 42) / 6)), 314, 150, 317), fill=RED)
    elif ty == 2:
        if k < 45:
            yb = FL if k < 30 else FL - round(30 * math.sin(math.pi * (k - 30) / 15))
            hero(d, lerp(60, 128, k / 30), yb, st if k < 30 else 0, RED if k >= 30 and k % 6 < 3 else HERO)
        else:
            R((124, 316, 147, 323), fill=HERO)
            R((141, 317, 146, 322), fill=FACE)
        spikes(d, 116, 164, lerp(0, 16, (k - 30) / 3))
        if k >= 60:
            y = 310 - (k - 60)
            R((132, y, 139, y + 7), fill=WHITE)
            for ex in (133, 137):
                R((ex, y + 2, ex + 1, y + 3), fill=BLACK)
    elif ty == 3:
        hero(d, lerp(50, 128, k / 30), FL, st if k < 30 else 0, (52, 48, 56) if k >= 45 else HERO)
        if k < 45:
            torch(d, 136 + (k % 2 if 30 <= k < 36 else 0), 250 + round(56 * ((k - 36) / 9) ** 2) if k >= 36 else 250, fl)
        elif k < 66:
            R((133, 308 - fl, 138, 315), fill=FL0 if fl else FL1)
    else:
        spikes(d, 100, 132, 16)
        if k >= 42:
            R((152, FL, 184, 371), fill=HOLE)
            for j, x in enumerate((156, 170)):
                y = FL + 2 + 3 * (k - 42) + 6 * j
                if y < 366:
                    R((x, y, x + 7, y + 4), fill=FLOOR1)
        elif k >= 32:
            d.line((156, FL + 2, 168, FL + 10, 180, FL + 3), fill=HOLE)
        if k < 24:
            x, yb = lerp(70, 140, k / 24), FL - round(36 * math.sin(math.pi * k / 24))
        else:
            x, yb = lerp(140, 160, (k - 24) / 14), FL + (round(40 * ((k - 42) / 12) ** 2) if k >= 42 else 0)
        hero(d, x, yb, st if 24 <= k < 38 else 0)
    return im


def frame(i):
    img = low_frame(i).resize((W, H), Image.NEAREST)
    d = ImageDraw.Draw(img)
    s, k = divmod(i % N, SEG)
    pay = s == 4 and k >= 42
    sm = f"{s + 1}/4 {TYPES[ORDER[s]]}" if s < 4 else ("5/4?! THE FLOOR" if pay else "DODGED IT")
    errs = []
    for t, size, cy in (("HE FOUND" if pay else "FLOOR 1 HAS", 52, 300), ("A 5TH" if pay else "4 WAYS TO DIE", 52, 380), (sm, 36, 460)):
        kw = dict(font=font(size), anchor="mm", stroke_width=6)
        box = d.textbbox((CX, cy), t, **kw)
        if box[0] < SAFE[0] or box[1] < SAFE[1] or box[2] > SAFE[2] or box[3] > SAFE[3]:
            errs.append(f"f{i}: '{t}' box {box} outside safe zone")
        d.text((CX, cy), t, fill=FL0 if size < 52 else WHITE, stroke_fill=BLACK, **kw)
    return img, errs


def make_audio(path):
    import numpy as np, wave
    sr = 44100
    out = np.zeros(int(sr * DUR))

    def note(m, t0, dur, amp):
        a, b = int(t0 * sr), int(min(t0 + dur, DUR - 0.05) * sr)
        if a < b:
            tt = np.arange(b - a) / sr
            env = np.minimum(1, tt / 0.005) * np.exp(-tt * 4) * np.clip((tt[-1] - tt) / 0.005, 0, 1)
            out[a:b] += amp * np.sign(np.sin(2 * np.pi * 440 * 2 ** ((m - 69) / 12) * tt)) * env

    B = 0.375
    for b in range(40):
        note((45, 45, 52, 52, 48, 48, 50, 52)[b % 8], b * B, 0.8 * B, 0.3)
        if b % 2 == 0:
            note((69, 72, 76, 72, 74, 72, 71, 67)[b // 2 % 8], b * B, 0.9 * B, 0.25)
    for t0 in [s * 3 + DEATH_K[ORDER[s]] / FPS for s in range(4)] + [13.4]:
        note(28, t0, 0.15, 0.5)
        for j, m in enumerate((67, 63, 60, 55)):
            note(m, t0 + 0.1 + j * 0.13, 0.12, 0.4)
    out *= 0.5 / max(float(np.abs(out).max()), 1e-9)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(np.round(out * 32767).astype("<i2").tobytes())


def cmd(audio):
    a = ["-i", WAV] if audio else ["-f", "lavfi", "-t", "15", "-i", "anullsrc=r=48000:cl=stereo"]
    return ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
            "-r", str(FPS), "-i", "-", *a, "-map", "0:v", "-map", "1:a", "-shortest", "-t", "15",
            "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-ar", "48000", "-ac", "2", "-movflags", "+faststart", OUT]


def render(audio):
    p = subprocess.Popen(cmd(audio), stdin=subprocess.PIPE)
    errs = []
    for i in range(N):
        img, e = frame(i)
        errs += e
        if i == COVER_I:
            img.save(COVER)
        p.stdin.write(img.tobytes())
    p.stdin.close()
    return errs, p.wait()


def probe():
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                        "-of", "default=nw=1", OUT], capture_output=True, text=True).stdout
    kv = [ln.partition("=")[::2] for ln in o.splitlines()]
    g = lambda key: next((v for k, v in kv if k == key and v != "N/A"), "0")
    return "codec_type=audio" in o, float(g("duration")), f"{g('width')}x{g('height')}"


if __name__ == "__main__":
    os.makedirs("docs", exist_ok=True)
    os.makedirs("build", exist_ok=True)
    sc = len(open(__file__, encoding="utf-8").read())
    print(f"SCRIPT_CHARS={sc} ORDER={ORDER}")
    audio, errs, rc = False, [], 1
    try:
        make_audio(WAV)
        errs, rc = render(True)
        audio = rc == 0
    except Exception as ex:
        print(f"chiptune failed: {ex!r}")
    if not audio:
        try:
            errs, rc = render(False)
        except Exception as ex:
            print(f"PROBE: silent render failed: {ex!r} -> FAIL")
            sys.exit(1)
    print("AUDIO=chiptune" if audio else "AUDIO=silent")
    has_a, dur, size = probe()
    ok = rc == 0 and not errs and has_a and 14.9 <= dur <= 15.1 and size == f"{W}x{H}" and sc <= 11000
    print(f"PROBE: size={size} audio_stream={has_a} duration={dur:.3f}s errors={len(errs)} chars={sc} -> {'OK' if ok else 'FAIL'}")
    for e in errs[:20]:
        print("  " + e)
    sys.exit(0 if ok else 1)
