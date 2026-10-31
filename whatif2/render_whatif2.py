#!/usr/bin/env python3
"""@whatifrpg Post 2 Reel "PICK ONE. WE BUILD IT." (render spec v1.1, artifact 71de3cf2).
DRAFT renderer, copied from whatif1/render_whatif1.py. Never run yet.
Every frame is drawn in code with Pillow: no camera, no image or video model.
Audio: an original square-wave chiptune made with numpy (seed 20261101, peak about
-6 dBFS, written with the built-in wave module). If that fails, a silent anullsrc
track is used instead. The log prints AUDIO=chiptune or AUDIO=silent.
Font: DejaVu Sans Mono Bold stands in for Press Start 2P, as in whatif1.
Run from the repo root."""
import math, os, random, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 1080, 1920, 30, 10.0
N = int(FPS * DUR)
LW, LH = 270, 480            # pixel-art canvas, scaled 4x (nearest)
OUT, COVER = "docs/whatif2.mp4", "docs/whatif2_cover.png"
WAV = "build/whatif2_audio.wav"   # temp file, not committed
SAFE = (90, 250, 900, 1500)  # text safe zone x0, y0, x1, y1
CX = 495
SEED = 20261101

SKY0, SKY1 = (27, 21, 48), (46, 34, 80)
STAR = (244, 241, 234)
FRAME, HILITE = (68, 70, 94), (255, 209, 102)
HERO, FACE = (76, 201, 240), (244, 241, 234)
WHITE, BLACK = (255, 255, 255), (0, 0, 0)
GOLD = (255, 209, 102)
TRUNK = (101, 67, 33)
FLOOR = {"crypt": (94, 84, 142), "forest": (45, 106, 79), "lava": (208, 0, 0), "ice": (72, 202, 228)}
DETAIL = {"crypt": (244, 241, 234), "forest": (149, 213, 178), "lava": (255, 186, 8), "ice": (202, 240, 248)}

FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_fc = {}


def font(size):
    size = max(8, int(round(size)))
    if size not in _fc:
        path = next((p for p in FONTS if os.path.exists(p)), None)
        _fc[size] = ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)
    return _fc[size]


def scene_of(t):
    return 1 if t < 1.5 else 2 if t < 6.5 else 3 if t < 8.5 else 4


def lit_of(t):
    return min(3, int((t - 1.5) / 1.25))


def shade(c, k):
    return tuple(int(v * k) for v in c)


# ---- tiles: 80x80 pixel art, icons only, no text ----
TS = 80
TILES = [("crypt", 34, 140), ("forest", 134, 140), ("lava", 34, 235), ("ice", 134, 235)]
NAMES = ["CRYPT?", "FOREST?", "LAVA?", "ICE?"]


def bone(d, x0, y0, x1, y1, c):
    d.line((x0, y0, x1, y1), fill=c, width=3)
    for x, y in ((x0, y0), (x1, y1)):
        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=c)


def tile(kind, idle):
    base, det = FLOOR[kind], DETAIL[kind]
    im = Image.new("RGB", (TS, TS), base)
    d = ImageDraw.Draw(im)
    dark = shade(base, 0.7)
    if kind == "crypt":
        for y in (20, 40, 60):
            d.line((0, y, TS - 1, y), fill=dark)
        o = idle  # bones rattle 1 px
        d.rectangle((32, 14 + o, 47, 27 + o), fill=det)          # skull
        d.rectangle((35, 28 + o, 44, 31 + o), fill=det)
        d.rectangle((35, 19 + o, 38, 22 + o), fill=base)
        d.rectangle((41, 19 + o, 44, 22 + o), fill=base)
        bone(d, 22 + o, 44, 57 + o, 64, det)
        bone(d, 22 - o, 64, 57 - o, 44, det)
    elif kind == "forest":
        d.rectangle((0, 66, TS - 1, TS - 1), fill=dark)
        s = 1 if idle else -1  # leaves sway
        for x, h in ((14, 34), (40, 46), (64, 30)):
            d.rectangle((x - 2, 62, x + 2, 72), fill=TRUNK)
            d.polygon([(x - 11, 64), (x + 11, 64), (x + s * 2, 64 - h)], fill=det)
    elif kind == "lava":
        for x, y, r in ((10, 12, 9), (52, 20, 12), (24, 54, 11), (62, 62, 8)):
            d.ellipse((x - r, y - r, x + r, y + r), fill=shade(base, 0.6))
        pts = ((18, 30), (48, 46), (66, 34), (34, 68)) if idle else ((26, 22), (40, 58), (60, 50), (14, 44))
        for x, y in pts:  # bubbles
            d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=det)
            d.point((x - 1, y - 2), fill=WHITE)
    else:  # ice
        for pl in (((8, 10), (24, 30), (20, 50), (36, 70)), ((70, 8), (52, 26), (60, 44)), ((44, 40), (66, 58), (72, 76))):
            d.line(pl, fill=det, width=2)
        gx, gy = (20, 18) if idle else (58, 54)  # glint
        d.line((gx - 4, gy, gx + 4, gy), fill=WHITE)
        d.line((gx, gy - 4, gx, gy + 4), fill=WHITE)
    return im


# ---- hero (same sprite as Post 1) ----
HOME = (116, 335)  # centred under the grid (full res y ~1340)
SPOT = [(x + TS // 2 - 8, y + TS - 14) for _, x, y in TILES]


def hero(d, x, yb, step, down=False):
    x, yb = int(x), int(yb)
    d.rectangle((x, yb - 24, x + 15, yb - 8), fill=HERO)
    d.rectangle((x + 2, yb - 22, x + 13, yb - 14), fill=FACE)
    ey = yb - 17 if down else yb - 20  # looks down in scene 4
    d.rectangle((x + 4, ey, x + 5, ey + 1), fill=BLACK)
    d.rectangle((x + 10, ey, x + 11, ey + 1), fill=BLACK)
    a, b = (1, 4) if step else (4, 1)
    d.rectangle((x + 2, yb - 8, x + 5, yb - a), fill=HERO)
    d.rectangle((x + 10, yb - 8, x + 13, yb - b), fill=HERO)


def hop(p, q, u):  # 6-frame hop with a 20 px arc
    u = max(0.0, min(1.0, u))
    return p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u - 20 * math.sin(math.pi * u), 0 < u < 1


def hero_state(t):
    if t < 1.5:
        return HOME[0], HOME[1], False
    if t < 6.5:
        k = lit_of(t)
        u = (t - 1.5 - 1.25 * k) * FPS / 6
        return hop(HOME if k == 0 else SPOT[k - 1], SPOT[k], u)
    return hop(SPOT[3], HOME, (t - 6.5) * FPS / 6)


# ---- pixel '?' (art, not text) ----
QMARK = [" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "]
QB = 4
QX, QY = 124 - 10, 228 - 14  # grid centre


def q_y(t):  # drops from full-res y 250 in 8 frames with one bounce
    u = (t - 6.5) * FPS
    y0 = 62
    if u < 6:
        return y0 + (QY - y0) * (u / 6) ** 2
    if u < 8:
        return QY - 6 * math.sin(math.pi * (u - 6) / 2)
    return QY


def qmark(d, y):
    y = int(y)
    cells = [(c, r) for r, row in enumerate(QMARK) for c, ch in enumerate(row) if ch == "#"]
    for c, r in cells:
        d.rectangle((QX + c * QB - 1, y + r * QB - 1, QX + c * QB + QB, y + r * QB + QB), fill=BLACK)
    for c, r in cells:
        d.rectangle((QX + c * QB, y + r * QB, QX + c * QB + QB - 1, y + r * QB + QB - 1), fill=GOLD)


SKY = Image.new("RGB", (LW, LH))
_d = ImageDraw.Draw(SKY)
for _y in range(LH):
    _k = _y / (LH - 1)
    _d.line((0, _y, LW, _y), fill=tuple(int(a + (b - a) * _k) for a, b in zip(SKY0, SKY1)))
_r = random.Random(SEED)
STARS = [(_r.randrange(LW), _r.randrange(LH - 60), _r.random() * 6.283) for _ in range(70)]


def low_frame(t, i):
    im = SKY.copy()
    d = ImageDraw.Draw(im)
    for sx, sy, ph in STARS:
        if math.sin(t * 3 + ph) > -0.4:
            d.point((sx, sy), fill=STAR)
    s = scene_of(t)
    idle = (i // 4) % 2
    lit = lit_of(t) if s == 2 else None
    bright = 0.925 + 0.075 * math.sin(2 * math.pi * 4 * t) if s == 1 else 1.0  # 0.85-1.0 at 4 Hz
    jit = random.Random(SEED + i)
    order = [j for j in range(4) if j != lit] + ([lit] if lit is not None else [])
    for j in order:
        kind, x, y = TILES[j]
        tl = tile(kind, idle)
        if bright < 1.0:
            tl = tl.point(lambda v, b=bright: int(v * b))
        size, fc = TS, FRAME
        if lit is not None:
            if j == lit:  # highlight: gold frame, 1.1x
                tl = tl.resize((88, 88), Image.NEAREST)
                size, fc, x, y = 88, HILITE, x - 4, y - 4
            else:         # others dimmed to 50%
                tl = tl.point(lambda v: v // 2)
        if s == 3:        # tiles shake
            x += jit.randint(-1, 1)
            y += jit.randint(-1, 1)
        d.rectangle((x - 2, y - 2, x + size + 1, y + size + 1), fill=fc)
        im.paste(tl, (x, y))
    if s >= 3:
        qmark(d, q_y(t))
    hx, hyb, moving = hero_state(t)
    hero(d, hx, hyb, moving and idle, down=(s == 4))
    return im


def overlay(img, t, i):
    d = ImageDraw.Draw(img)
    boxes = []

    def txt(s, size, cy, kind="main", fill=WHITE, x=CX):
        kw = dict(font=font(size), anchor="mm", stroke_width=6)
        boxes.append((kind, d.textbbox((x, cy), s, **kw)))
        d.text((x, cy), s, fill=fill, stroke_fill=BLACK, **kw)

    s = scene_of(t)
    if s == 1:  # full size from frame 0, shake +-3 px for 4 frames
        dx = (3, -3, 3, -3)[i] if i < 4 else 0
        txt("PICK ONE.", 56, 300, x=CX + dx)
        txt("WE BUILD IT.", 56, 380, x=CX + dx)
        txt("IN DEVELOPMENT", 32, 460, kind="small", fill=STAR)
    elif s == 2:
        k = lit_of(t)
        txt(NAMES[k], 56, 340)
        txt(f"OPTION {k + 1} OF 4", 32, 460, kind="small", fill=STAR)
    elif s == 3:
        txt("WHICH ONE", 56, 300)
        txt("IS NEXT?", 56, 380)
        txt("IN DEVELOPMENT", 32, 460, kind="small", fill=STAR)
    else:
        txt("COMMENT A", 48, 300)
        txt("THEME BELOW", 48, 380)
        txt("IN DEVELOPMENT", 40, 1400, kind="small", fill=STAR)
        ay = 1455 + 3 * math.sin(4 * math.pi * t)  # arrow bobs 3 px at 2 Hz (art)
        d.rectangle((CX - 10, ay - 15, CX + 10, ay), fill=WHITE, outline=BLACK, width=3)
        d.polygon([(CX - 26, ay), (CX + 26, ay), (CX, ay + 22)], fill=WHITE, outline=BLACK)
    return boxes


def check(i, t, img, boxes):
    e = []
    if img.size != (W, H) or img.mode != "RGB":
        e.append(f"f{i}: frame {img.size} {img.mode}")
    main = sum(1 for k, _ in boxes if k == "main")
    small = len(boxes) - main
    if main > 2 or small > 1:
        e.append(f"f{i}: {main} main / {small} small lines")
    for k, (x0, y0, x1, y1) in boxes:
        if x0 < SAFE[0] or y0 < SAFE[1] or x1 > SAFE[2] or y1 > SAFE[3]:
            e.append(f"f{i}: {k} text box {(x0, y0, x1, y1)} outside safe zone")
    return e


# ---- audio: original chiptune, numpy only, no samples ----
def make_audio(path):
    import numpy as np
    import wave
    sr = 48000
    n = int(sr * DUR)
    out = np.zeros(n)
    rng = np.random.default_rng(SEED)

    def note(f, t0, dur, amp):
        a, b = int(t0 * sr), min(n, int((t0 + dur) * sr))
        if a >= b:
            return
        tt = np.arange(b - a) / sr
        sq = np.sign(np.sin(2 * np.pi * f * tt))
        env = np.minimum(1.0, tt / 0.005) * np.exp(-tt * 5) * np.clip((dur - tt) / 0.02, 0, 1)
        out[a:b] += amp * sq * env

    E8 = 60 / 120 / 2                      # 120 BPM, 8th notes
    LEAD = (440.0, 523.25, 659.25, 880.0)  # A-C-E-A arpeggio
    BASS = (110.0, 110.0, 87.31, 98.0)     # 4-bar loop in A minor: A A F G
    for k in range(int(DUR / E8)):
        t0 = k * E8
        note(LEAD[k % 4], t0, E8 * 0.9, 0.5)
        if k % 2 == 0:
            note(BASS[(k // 8) % 4], t0, E8 * 1.8, 0.35)
    hl = int(0.03 * sr)
    henv = np.exp(-np.arange(hl) / (0.006 * sr))
    for b in range(int(DUR / (2 * E8))):   # seeded noise-hat on every beat
        a = int(b * 2 * E8 * sr)
        m = min(hl, n - a)
        hit = np.diff(rng.standard_normal(hl + 1))
        out[a:a + m] += 0.2 * hit[:m] * henv[:m]
    peak = float(np.max(np.abs(out)))
    if peak <= 0:
        raise ValueError("silent mix")
    out *= 10 ** (-6 / 20) / peak          # peak about -6 dBFS
    fade = int(0.05 * sr)                  # 50 ms fade-in, no fade-out
    out[:fade] *= np.linspace(0.0, 1.0, fade)
    pcm = np.round(out * 32767).astype("<i2")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(np.repeat(pcm, 2).tobytes())


def cmd(audio):
    a = ["-i", WAV] if audio else ["-f", "lavfi", "-t", str(DUR), "-i", "anullsrc=r=48000:cl=stereo"]
    return ["ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            *a, "-map", "0:v", "-map", "1:a", "-shortest",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-movflags", "+faststart", OUT]


# ---- render (REWRITTEN tail: the original end of render() was not readable) ----
def render(audio):
    p = subprocess.Popen(cmd(audio), stdin=subprocess.PIPE)
    errs = []
    try:
        for i in range(N):
            t = i / FPS
            img = low_frame(t, i).resize((W, H), Image.NEAREST)  # 270x480 -> 1080x1920 (4x)
            boxes = overlay(img, t, i)
            errs += check(i, t, img, boxes)
            if i == 0:
                img.save(COVER)  # cover = frame 0 (hook with all 4 tiles)
            try:
                p.stdin.write(img.tobytes())
            except BrokenPipeError:
                print(f"ffmpeg closed its input at frame {i}", file=sys.stderr)
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
    has_audio, dur = False, 0.0
    for line in r.stdout.splitlines():
        k, _, v = line.partition("=")
        if k == "codec_type" and v.strip() == "audio":
            has_audio = True
        elif k == "duration":
            try:
                dur = float(v)
            except ValueError:
                pass
    return r.returncode, has_audio, dur


if __name__ == "__main__":
    os.makedirs("docs", exist_ok=True)
    os.makedirs("build", exist_ok=True)
    audio, errs, rc = False, [], 1
    try:
        make_audio(WAV)
        errs, rc = render(True)
        audio = rc == 0
        if not audio:
            print(f"chiptune encode failed (ffmpeg exit {rc}), falling back to silent", file=sys.stderr)
    except Exception as ex:
        print(f"chiptune failed: {ex!r}, falling back to silent", file=sys.stderr)
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
    ok = prc == 0 and has_audio and 9.9 <= dur <= 10.1
    print(f"PROBE: audio_stream={has_audio} duration={dur:.3f}s -> {'OK' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)
    print(f"OK: wrote {OUT} and {COVER} ({N} frames, {W}x{H}, {FPS} fps)")
