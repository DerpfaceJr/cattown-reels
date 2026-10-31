#!/usr/bin/env python3
# @whatifrpg Reel 7 'N LINES / ONE HERO', 15 s loop (plan 3e9e9e3e).
# Shows the real source of hero() from whatif6/render_whatif6.py and draws the sprite with that same function.
import hashlib, inspect, math, os, subprocess, sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "whatif6"))
import render_whatif6 as w6

W, H, FPS, DUR, N = 1080, 1920, 30, 15.0, 450
OUT, COVER, WAV = "docs/whatif7.mp4", "docs/whatif7_cover.png", "build/whatif7.wav"
w6.OUT, w6.WAV = OUT, WAV  # reuse w6.cmd() and w6.probe() with Reel 7 paths (verified in main)
SAFE, CX, COVER_I = (90, 250, 900, 1500), 495, 8
HERO_SRC = "whatif6@e707723"
SRC = inspect.getsource(w6.hero)
CODE = [ln for ln in SRC.splitlines() if ln.strip()]
HL = len(CODE)
RLINES = [j for j, ln in enumerate(CODE) if ln.strip().startswith("r(")]
STEPL = next((j for j, ln in enumerate(CODE) if "if step" in ln), -1)
B0, B1, P0 = 30, 300, 330  # build 1-10 s, legs 10-11 s, payoff 11-15 s
S = (B1 - B0) / HL
LHT = min(30, 380 // HL)
FS = LHT - 6
SY, GY, HX = 940, 40, 34  # stage top (full res), floor row and hero x (stage px, x12)
WALL, BG, PANEL, HI, DIM, TXT = (40, 36, 58), (18, 16, 28), (12, 10, 20), (60, 50, 20), (24, 22, 34), (230, 230, 240)


class Lim:  # passes only the first m rectangle() calls of hero() to the real canvas
    def __init__(s, d, m):
        s.d, s.m, s.n = d, m, 0

    def rectangle(s, *a, **k):
        if s.n < s.m:
            s.d.rectangle(*a, **k)
        s.n += 1


def state(i):  # -> (highlighted line or -1, typed fraction, rectangles shown)
    if B0 <= i < B1:
        j = int((i - B0) / S)
        t = min(1.0, (i - B0 - j * S) / (S * 0.6))
        return j, t, sum(1 for r in RLINES if r < j or (r == j and t >= 1))
    return (STEPL if B1 <= i < P0 else -1), 1.0, 99


def stage(i, m):
    room = not (B0 <= i < P0)
    im = Image.new("RGB", (90, 45), WALL if room else BG)
    d = ImageDraw.Draw(im)
    if room:
        for r, y in enumerate(range(0, GY, 6)):
            d.line((0, y, 89, y), fill=(30, 26, 44))
            for x in range(6 * (r % 2), 90, 12):
                d.line((x, y, x, y + 5), fill=(30, 26, 44))
        d.rectangle((0, GY, 89, 44), fill=w6.FLOOR1)
        fl = i * 8 // 30 % 2
        w6.torch(d, 12, 16, fl)
        w6.torch(d, 69, 16, fl)
    yb, step = GY, 0
    if B1 <= i < P0:
        step = i // 5 % 2
    elif 0 <= i - P0 < 108:
        k = (i - P0) % 36
        yb, step = GY - round(10 * math.sin(math.pi * k / 36)), 1 if k else 0
    w6.hero(Lim(d, m), HX, yb, step)
    return im.resize((W, 540), Image.NEAREST)


def frame(i):
    img = Image.new("RGB", (W, H), DIM)
    j, t, m = state(i)
    img.paste(stage(i, m), (0, SY))
    d = ImageDraw.Draw(img)
    d.rectangle((90, 505, 900, 905), fill=PANEL)
    errs = []

    def chk(s, box):
        if box[0] < SAFE[0] or box[1] < SAFE[1] or box[2] > SAFE[2] or box[3] > SAFE[3]:
            errs.append(f"f{i}: '{s.strip()}' box {box} outside safe zone")

    f = w6.font(FS)
    for n, ln in enumerate(CODE):
        if B0 <= i < B1 and n > j:
            break
        y = 520 + n * LHT
        chk(ln, d.textbbox((100, y), ln, font=f))
        if n == j:
            d.rectangle((92, y - 3, 898, y + LHT - 4), fill=HI)
            ln = ln[:round(len(ln) * t)]
        d.text((100, y), ln, font=f, fill=w6.FL0 if n == j else TXT)
    if i < B0 or i >= P0 + 108:
        sm = "NO DRAWING APP"
    elif i < B1:
        sm = f"LINE {j + 1}/{HL}"
    elif i < P0:
        sm = "step=1 SWAPS LEGS"
    else:
        sm = "SAME CODE. IT HOPS."
    for s, size, cy in ((f"{HL} LINES", 52, 300), ("ONE HERO", 52, 380), (sm, 36, 460)):
        kw = dict(font=w6.font(size), anchor="mm", stroke_width=6)
        chk(s, d.textbbox((CX, cy), s, **kw))
        d.text((CX, cy), s, fill=w6.FL0 if size < 52 else w6.WHITE, stroke_fill=w6.BLACK, **kw)
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
        note((45, 45, 52, 52, 48, 48, 50, 52)[b % 8], b * B, 0.8 * B, 0.25)
        if b % 2 == 0:
            note((69, 72, 76, 72, 74, 72, 71, 67)[b // 2 % 8], b * B, 0.9 * B, 0.18)
    for n in range(HL):
        t0 = (B0 + n * S) / FPS
        note(84, t0, 0.04, 0.2)
        if n in RLINES:
            note(76, t0 + 0.6 * S / FPS, 0.1, 0.35)
    for h in range(3):
        for q, m in enumerate((60, 64, 67, 72)):
            note(m, (P0 + 36 * h) / FPS + q * 0.06, 0.08, 0.35)
    out *= 0.5 / max(float(np.abs(out).max()), 1e-9)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(np.round(out * 32767).astype("<i2").tobytes())


def render(audio):
    p = subprocess.Popen(w6.cmd(audio), stdin=subprocess.PIPE)
    errs = []
    for i in range(N):
        img, e = frame(i)
        errs += e
        if i == COVER_I:
            img.save(COVER)
        p.stdin.write(img.tobytes())
    p.stdin.close()
    return errs, p.wait()


if __name__ == "__main__":
    os.makedirs("docs", exist_ok=True)
    os.makedirs("build", exist_ok=True)
    sc = len(open(__file__, encoding="utf-8").read())
    sha = hashlib.sha1(SRC.encode()).hexdigest()[:12]
    try:  # honesty: one rectangle() per 'r(' line in both leg states; paths really routed to Reel 7
        calls = []
        for st in (0, 1):
            c = Lim(None, 0)
            w6.hero(c, HX, GY, st)
            calls.append(c.n)
        routed = OUT in w6.cmd(True) and OUT in w6.cmd(False) and WAV in w6.cmd(True)
    except Exception as ex:
        calls, routed = [repr(ex)], False
    match = bool(RLINES) and calls == [len(RLINES)] * 2 and STEPL >= 0
    print(f"SCRIPT_CHARS={sc} HERO_SRC={HERO_SRC} HERO_LINES={HL} HERO_SHA1={sha} RECTS={len(RLINES)} RECT_CALLS={calls} STEPL={STEPL} ROUTED={routed}")
    if not (match and routed):
        print("PROBE: hero/rect mismatch or paths not routed to Reel 7, not rendering -> FAIL")
        sys.exit(1)
    if os.path.exists(OUT):
        os.remove(OUT)
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
    built = os.path.isfile(OUT)
    has_a, dur, size = w6.probe() if built else (False, 0.0, "none")
    ok = rc == 0 and built and not errs and has_a and 14.9 <= dur <= 15.1 and size == f"{W}x{H}" and sc <= 11000
    print(f"PROBE: size={size} audio_stream={has_a} duration={dur:.3f}s errors={len(errs)} chars={sc} -> {'OK' if ok else 'FAIL'}")
    for e in errs[:20]:
        print("  " + e)
    sys.exit(0 if ok else 1)
