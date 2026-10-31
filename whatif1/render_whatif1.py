#!/usr/bin/env python3
"""@whatifrpg Post 1 Reel (render spec v2, artifact 22cb75c4). DRAFT renderer.
Every frame is drawn in code with Pillow: no camera, no image or video model.
ffmpeg encodes 1080x1920 H.264 yuv420p + a silent AAC track (anullsrc).
Font: DejaVu Sans Mono Bold (fonts-dejavu-core) stands in for Press Start 2P,
which is not bundled in this repo. Run from the repo root."""
import math, os, random, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 1080, 1920, 30, 10.0
N = int(FPS * DUR)
LW, LH = 270, 480            # pixel-art canvas, scaled 4x (nearest)
OUT, COVER = "docs/whatif1.mp4", "docs/whatif1_cover.png"
SAFE = (90, 250, 900, 1500)  # text safe zone x0, y0, x1, y1
CX = 495
SEED = 20261031

SKY0, SKY1 = (27, 21, 48), (46, 34, 80)
STAR = (244, 241, 234)
STONE, SHADOW, MORTAR = (107, 110, 140), (68, 70, 94), (42, 43, 61)
WIN, WIN_OFF = (255, 209, 102), (138, 106, 42)
HERO, FACE = (76, 201, 240), (244, 241, 234)
BUB, BUBTXT = (244, 241, 234), (27, 21, 48)
PINK, GOLD = (239, 71, 111), (255, 209, 102)
WHITE, BLACK = (255, 255, 255), (0, 0, 0)
GROUND, GROUND_TOP = (34, 28, 52), (58, 51, 85)

FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_fc = {}


def font(size):
    size = max(8, int(round(size)))
    if size not in _fc:
        path = next((p for p in FONTS if os.path.exists(p)), None)
        _fc[size] = ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)
    return _fc[size]


def ease(u):
    u = max(0.0, min(1.0, u))
    return 0.5 - 0.5 * math.cos(math.pi * u)


def scene_of(t):
    return 1 if t < 2 else 2 if t < 4.5 else 3 if t < 6.5 else 4 if t < 8.5 else 5


def pop(t, t0):
    return 1.3 - 0.3 * min(1.0, (t - t0) * FPS / 6)


# ---- world: tall pixel canvas with transparent sky ----
WW, WH, GY, FH = LW, 960, 900, 96
TX0, TX1 = 70, 200
def ftop(k): return GY - k * FH
def fbot(k): return GY - (k - 1) * FH

ICONS = {1: "slime", 2: "spikes", 3: "chest", 4: "bat", 5: "door"}
QMARK = [" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "]


def icon(d, kind, x, y, i):
    if kind == "slime":
        d.ellipse((x, y + 5, x + 15, y + 15), fill=(123, 211, 137))
        d.point([(x + 5, y + 9), (x + 10, y + 9)], fill=BLACK)
    elif kind == "spikes":
        for s in range(4):
            d.polygon([(x + s * 4, y + 15), (x + s * 4 + 2, y + 4), (x + s * 4 + 3, y + 15)], fill=(201, 194, 184))
    elif kind == "chest":
        d.rectangle((x + 1, y + 6, x + 14, y + 15), fill=(156, 91, 46))
        d.rectangle((x + 1, y + 9, x + 14, y + 10), fill=GOLD)
        d.rectangle((x + 7, y + 9, x + 8, y + 12), fill=GOLD)
    elif kind == "bat":
        wy = y + 2 if (i // 4) % 2 else y + 12
        c = (106, 76, 147)
        d.polygon([(x + 6, y + 7), (x, wy), (x + 6, y + 10)], fill=c)
        d.polygon([(x + 9, y + 7), (x + 15, wy), (x + 9, y + 10)], fill=c)
        d.ellipse((x + 5, y + 5, x + 10, y + 11), fill=c)
    else:  # door
        d.rectangle((x + 2, y, x + 13, y + 15), fill=(90, 58, 34))
        d.point((x + 10, y + 8), fill=GOLD)


def stone_floor(d, k, i):
    y0, y1 = ftop(k), fbot(k)
    d.rectangle((TX0, y0, TX1, y1), fill=STONE)
    for r, yy in enumerate(range(y0 + 12, y1, 12)):
        d.line((TX0, yy, TX1, yy), fill=MORTAR)
        for xx in range(TX0 + (10 if r % 2 else 0), TX1, 20):
            d.line((xx, yy - 12, xx, yy), fill=MORTAR)
    d.rectangle((TX1 - 8, y0, TX1, y1), fill=SHADOW)
    for wx in (TX0 + 14, TX1 - 34):
        lit = random.Random(k * 1000 + i // 5 + wx).random() > 0.15
        d.rectangle((wx, y0 + 16, wx + 11, y0 + 33), fill=WIN if lit else WIN_OFF)
    for s in range(3):  # stair tiles
        d.rectangle((TX1 - 38 + s * 8, y1 - 4 - (s + 1) * 6, TX1 - 9, y1 - 4), fill=SHADOW)
    d.rectangle((TX0, y1 - 4, TX1, y1), fill=MORTAR)
    icon(d, ICONS[k], 127, y1 - 20, i)


def empty_floor(d, k, lava):
    y0, y1 = ftop(k), fbot(k)
    d.rectangle((TX0, y0, TX1, y1), fill=MORTAR)
    for x in range(TX0, TX1, 8):
        d.line((x, y0, x + 3, y0), fill=STAR)
        d.line((x, y1, x + 3, y1), fill=STAR)
    for y in range(y0, y1, 8):
        d.line((TX0, y, TX0, y + 3), fill=STAR)
        d.line((TX1, y, TX1, y + 3), fill=STAR)
    if lava > 0:
        lx = TX0 + 2 + int((TX1 - TX0 - 4) * min(1.0, lava))
        d.rectangle((TX0 + 2, y1 - 30, lx, y1 - 2), fill=PINK)
        for x in range(TX0 + 2, lx - 2, 6):
            d.rectangle((x, y1 - 34, x + 2, y1 - 31), fill=GOLD)
    else:
        qx, qy = (TX0 + TX1) // 2 - 10, y0 + FH // 2 - 14
        for r, row in enumerate(QMARK):
            for c, ch in enumerate(row):
                if ch == "#":
                    d.rectangle((qx + c * 4, qy + r * 4, qx + c * 4 + 3, qy + r * 4 + 3), fill=GOLD)


def hero(d, x, yb, step):
    x, yb = int(x), int(yb)
    d.rectangle((x, yb - 24, x + 15, yb - 8), fill=HERO)
    d.rectangle((x + 2, yb - 22, x + 13, yb - 14), fill=FACE)
    d.rectangle((x + 4, yb - 20, x + 5, yb - 19), fill=BLACK)
    d.rectangle((x + 10, yb - 20, x + 11, yb - 19), fill=BLACK)
    a, b = (1, 4) if step else (4, 1)
    d.rectangle((x + 2, yb - 8, x + 5, yb - a), fill=HERO)
    d.rectangle((x + 10, yb - 8, x + 13, yb - b), fill=HERO)


def hero_state(t):
    if t < 2:
        return TX0 + 20, fbot(1), False
    if t < 4.5:
        f = 4 * ease((t - 2) / 2.5)
        return TX0 + 10 + (f % 1) * (TX1 - TX0 - 50), fbot(1) - f * FH, True
    if t < 7.6:
        return TX1 - 44, fbot(5), False
    if t < 8.2:
        u = (t - 7.6) / 0.6
        return TX1 - 44 + (127 - (TX1 - 44)) * u, fbot(5) + (fbot(6) - fbot(5)) * u, True
    return 127, fbot(6), False


def draw_world(t, i):
    w = Image.new("RGBA", (WW, WH), (0, 0, 0, 0))
    d = ImageDraw.Draw(w)
    d.rectangle((0, GY, WW, WH), fill=GROUND)
    d.rectangle((0, GY, WW, GY + 1), fill=GROUND_TOP)
    for k in range(1, 6):
        stone_floor(d, k, i)
    lava = ((t - 6.5) * FPS - 8) / 12 if t >= 6.5 else 0.0
    empty_floor(d, 6, max(lava, 0.0))
    if t >= 8.5:
        empty_floor(d, 7, 0)
    x, yb, walk = hero_state(t)
    hero(d, x, yb - 4, walk and (i // 4) % 2)
    return w


def cam(t):
    return int(round(480 + (150 - 480) * ease((t - 2) / 2.5))) if t >= 2 else 480


SKY = Image.new("RGB", (LW, LH))
_d = ImageDraw.Draw(SKY)
for _y in range(LH):
    _k = _y / (LH - 1)
    _d.line((0, _y, LW, _y), fill=tuple(int(a + (b - a) * _k) for a, b in zip(SKY0, SKY1)))
_r = random.Random(SEED)
STARS = [(_r.randrange(LW), _r.randrange(LH - 60), _r.random() * 6.283) for _ in range(70)]


def low_frame(t, i):
    im = SKY.copy().convert("RGBA")
    d = ImageDraw.Draw(im)
    for sx, sy, ph in STARS:
        if math.sin(t * 3 + ph) > -0.4:
            d.point((sx, sy), fill=STAR)
    w = draw_world(t, i)
    if t < 8.5:
        vt = cam(t)
        im.alpha_composite(w.crop((0, vt, LW, vt + LH)))
    else:  # wide shot: whole tower plus the new '?' floor
        im.alpha_composite(w.crop((0, 200, LW, WH)).resize((170, 480), Image.NEAREST), (50, 0))
    if scene_of(t) == 4:
        a = 0.6 * math.sin(math.pi * (t - 6.5)) ** 2
        vt = cam(t)
        ov = Image.new("RGBA", (LW, LH), (0, 0, 0, 0))
        ImageDraw.Draw(ov).rectangle((TX0 - 4, ftop(6) - vt - 4, TX1 + 4, fbot(6) - vt + 4), fill=GOLD + (int(255 * a),))
        im.alpha_composite(ov)
    return im.convert("RGB")


def overlay(img, t):
    d = ImageDraw.Draw(img)
    boxes = []

    def txt(s, size, cy, kind="main", fill=WHITE, stroke=6, sc=1.0, x=CX):
        kw = dict(font=font(size * sc), anchor="mm", stroke_width=stroke)
        boxes.append((kind, d.textbbox((x, cy), s, **kw)))
        d.text((x, cy), s, fill=fill, stroke_fill=BLACK, **kw)

    s = scene_of(t)
    if s == 1:
        if t < 1:
            p = pop(t, 0)
            txt("WHAT IF YOU", 48, 420, sc=p)
            txt("CLIMBED A TOWER", 48, 500, sc=p)
        else:
            txt("EVERY DAY?", 56, 460, sc=pop(t, 1))
    elif s == 2:
        p = pop(t, 2)
        txt("ONE NEW FLOOR", 56, 420, sc=p)
        txt("EACH DAY", 56, 500, sc=p)
    elif s == 3:
        p = pop(t, 4.5)
        txt("YOUR COMMENT =", 48, 1220, sc=p)
        txt("TOMORROW'S FLOOR", 48, 1290, sc=p)
        j = (t - 4.5) * FPS
        off = int(W * (1 - min(j, 10) / 10) ** 2)
        d.rounded_rectangle((120 + off, 980, 870 + off, 1080), radius=18, fill=BUB, outline=BUBTXT, width=4)
        if j >= 10:  # text appears once the bubble stops, so it never leaves the safe zone
            d.rectangle((126, 960, 294, 1000), fill=PINK)
            txt("EXAMPLE", 24, 980, kind="small", stroke=0, x=210)
            txt("@you: add a lava trap", 24, 1030, kind="small", fill=BUBTXT, stroke=0)
    elif s == 4:
        txt("FLOOR 6: LAVA", 56, 420, sc=pop(t, 6.5))
        txt("EXAMPLE PICK", 32, 490, kind="small")
        k = 1 - (t - 6.5) * FPS / 8
        if k > 0.05:  # bubble shrinks into the empty floor
            cx, cy = 495 + 45 * (1 - k), 1030 - 142 * (1 - k)
            d.rectangle((cx - 375 * k, cy - 50 * k, cx + 375 * k, cy + 50 * k), fill=BUB, outline=BUBTXT, width=4 if k > 0.3 else 1)
    else:
        p = pop(t, 8.5)
        txt("COMMENT", 48, 700, sc=p)
        txt("TOMORROW'S FLOOR", 48, 770, sc=p)
        txt("IN DEVELOPMENT", 40, 1380, kind="small", fill=STAR)
        ay = 1450 + 12 * math.sin(4 * math.pi * t)
        d.rectangle((CX - 10, ay - 25, CX + 10, ay - 5), fill=WHITE, outline=BLACK, width=3)
        d.polygon([(CX - 30, ay - 5), (CX + 30, ay - 5), (CX, ay + 25)], fill=WHITE, outline=BLACK)
    return boxes


def check(i, t, img, boxes):
    e = []
    if img.size != (W, H) or img.mode != "RGB":
        e.append(f"f{i}: frame {img.size} {img.mode}")
    main = sum(1 for k, _ in boxes if k == "main")
    small = len(boxes) - main
    lim = 2 if scene_of(t) == 3 else 1  # scene 3: comment + EXAMPLE tag inside the bubble
    if main > 2 or small > lim:
        e.append(f"f{i}: {main} main / {small} small lines")
    for k, (x0, y0, x1, y1) in boxes:
        if x0 < SAFE[0] or y0 < SAFE[1] or x1 > SAFE[2] or y1 > SAFE[3]:
            e.append(f"f{i}: {k} text box {(x0, y0, x1, y1)} outside safe zone")
    return e


CMD = ["ffmpeg", "-y", "-loglevel", "error",
       "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
       "-f", "lavfi", "-t", str(DUR), "-i", "anullsrc=r=48000:cl=stereo",
       "-map", "0:v", "-map", "1:a", "-shortest",
       "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", OUT]


def main():
    os.makedirs("docs", exist_ok=True)
    p = subprocess.Popen(CMD, stdin=subprocess.PIPE)
    errs, n = [], 0
    try:
        for i in range(N):
            fi = min(i, N - 7)  # last 6 frames hold for a clean loop
            t = fi / FPS
            img = low_frame(t, fi).resize((W, H), Image.NEAREST)
            boxes = overlay(img, t)
            errs += check(i, t, img, boxes)
            if errs:
                break
            if i == 90:
                img.save(COVER)
            data = img.tobytes()
            assert len(data) == W * H * 3
            p.stdin.write(data)
            n += 1
    finally:
        p.stdin.close()
        rc = p.wait()
    if errs:
        print("SELF-CHECK FAILED:", *errs[:10], sep="\n")
        if os.path.exists(OUT):
            os.remove(OUT)
        sys.exit(1)
    if n != N or rc != 0:
        print(f"FAILED: frames={n}/{N} ffmpeg rc={rc}")
        sys.exit(1)
    print(f"OK frames={n} out={OUT} bytes={os.path.getsize(OUT)}")


if __name__ == "__main__":
    main()
