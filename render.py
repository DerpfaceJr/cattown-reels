# Clowder Reel 1: Pillow frames piped to ffmpeg. DURATION_S=2 to smoke-test.
import math, os, random, subprocess, sys, textwrap
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
N = int(round(float(os.environ.get("DURATION_S", "20")) * FPS))
OUT, POSTER = "docs/reel1.mp4", "docs/reel1_poster.png"
INK, RED, ROAD = (59, 47, 47), (192, 57, 43), "#d9b98a"
COL = {"mayor": "#f2a14f", "director": "#f3e3c3", "critic": "#f2a14f", "helper": "#9a9a9a"}
TASKS = ("plan a launch", "post on IG", "build a game")
HOUSES = [(540, 950, "#c0392b"), (220, 640, "#3a7bd5"), (540, 640, "#e84393"),
          (860, 640, "#8e44ad"), (220, 1270, "#e67e22"), (860, 1270, "#16a085")]
PATH = [(540, 1010), (540, 1110), (700, 1110), (700, 1300), (800, 1300)]
TOES = ((-0.62, -0.5), (-0.22, -0.82), (0.22, -0.82), (0.62, -0.5))
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
random.seed(7)
SCRIB = [[random.uniform(-7, 7) for _ in range(16)] for _ in TASKS]

@lru_cache(None)
def font(size):
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except (TypeError, OSError):
        ok = os.path.exists(DEJAVU)
        return ImageFont.truetype(DEJAVU, size) if ok else ImageFont.load_default()

def say(d, xy, text, size, anchor="mm"):
    d.text(xy, text, font=font(size), fill=INK, anchor=anchor)

def prog(t, a, b):
    return max(0.0, min(1.0, (t-a) / (b-a)))

def ease(x):  # cubic in-out
    x = prog(x, 0, 1)
    return 4*x**3 if x < 0.5 else 1 - (2-2*x)**3 / 2

def pop(x):  # ease-out-back
    x = prog(x, 0, 1) - 1
    return 1 + 2.7*x**3 + 1.7*x**2

def fade(t, a, b):
    return min(ease((t-a) / 0.4), ease((b-t) / 0.3))

def pts(x, y, s, *v):
    return [(x + a*s, y + b*s) for a, b in zip(v[::2], v[1::2])]

def caption(img, text, alpha, y=300, size=64):  # IG safe zone: y in 260..H-390
    if alpha <= 0:
        return
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d, lines, lh = ImageDraw.Draw(layer), textwrap.wrap(text, 1760 // size), int(size*1.25)
    bw = max(d.textlength(l, font=font(size)) for l in lines) + 80
    bh = lh*len(lines) + 50
    y = max(260, min(y + (1-alpha)*30, H - 390 - bh))
    d.rounded_rectangle([(W-bw)/2, y, (W+bw)/2, y+bh], 36, (255, 255, 255, 240))
    for i, line in enumerate(lines):
        say(d, (W/2, y + 25 + (i+0.5)*lh), line, size)
    layer.putalpha(layer.getchannel("A").point(lambda v: int(v*alpha)))
    img.alpha_composite(layer)

def cat(d, x, y, s, role):
    if s < 0.05:
        return
    c, k, S = COL[role], max(2, int(3*s)), lambda *v: pts(x, y, s, *v)
    for col, w in ((INK, 18), (c, 11)):  # tail
        d.line(S(34, 30, 72, 0, 66, -40), col, int(w*s), "curve")
    if role == "mayor":  # teal cape
        d.polygon(S(-36, -22, 36, -22, 54, 48, -54, 48), "#1f9e9a", INK)
    d.rounded_rectangle(S(-40, -25, 40, 45), int(26*s), c, INK, k)
    if role == "director":  # olive outfit
        d.rounded_rectangle(S(-40, 8, 40, 45), int(16*s), "#6b7a2f", INK, k)
    for e in (-1, 1):
        d.polygon(S(6*e, -80, 32*e, -64, 30*e, -110), c, INK)
    d.ellipse(S(-36, -86, 36, -22), c, INK, k)
    for e in (-1, 1):
        d.ellipse(S(13*e-5, -59, 13*e+5, -49), INK)
        if role == "critic":  # spectacles
            d.ellipse(S(13*e-12, -66, 13*e+12, -42), None, INK, k)
            d.line(S(-3, -54, 3, -54), INK, k)

def leaders(d):
    cat(d, 450, 1040, 0.6, "mayor")
    cat(d, 860, 1350, 0.6, "director")

def card(d, x, y, s, label):
    d.rounded_rectangle(pts(x, y, s, -55, -35, 55, 35), int(8*s), "#fffdf6", INK, 3)
    say(d, (x, y), label, int(30*s))

def base(z=1.0):  # the town, zoomed by z about the centre
    img = Image.new("RGBA", (W, H))
    d, rw, wins = ImageDraw.Draw(img), 28*z, []
    d.rectangle([0, 0, W, H], "#7cc36a")
    for v, u in ((800, 380), (1110, 700)):
        yy, xx = 960 + (v-960)*z, 540 + (u-540)*z
        d.rectangle([0, yy-rw, W, yy+rw], ROAD)
        d.rectangle([xx-rw, 0, xx+rw, H], ROAD)
    for hx, hy, roof in HOUSES:
        x, y, w = 540 + (hx-540)*z, 960 + (hy-960)*z, 60*z
        d.rectangle(pts(x, y, w, -1, -0.6, 1, 0.9), "#f4ead2", INK, 3)
        d.polygon(pts(x, y, w, -1.2, -0.55, 0, -1.4, 1.2, -0.55), roof, INK)
        for a, b in ((-0.75, -0.3), (0.3, 0.75)):
            wins.append(pts(x, y, w, a, -0.3, b, 0.15))
            d.rectangle(wins[-1], "#bfe3f2", INK, 2)
        d.rectangle(pts(x, y, w, -0.18, 0.3, 0.18, 0.9), "#8a5a3b")
    return img, d, wins

def along(path, p):
    f = p * (len(path) - 1)
    i = min(int(f), len(path) - 2)
    (ax, ay), (bx, by), f = path[i], path[i+1], f - i
    return ax + (bx-ax)*f, ay + (by-ay)*f

def shade(img, rgb, a):
    img.alpha_composite(Image.new("RGBA", img.size, rgb + (int(a),)))
    return ImageDraw.Draw(img)

def intro(t):
    img = Image.new("RGBA", (W, H), (251, 243, 224))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([170, 840, 910, 1330], 30, "#fffdf6", INK, 5)
    for i, task in enumerate(TASKS):
        y = 930 + i*130
        d.rectangle([220, y-28, 276, y+28], None, INK, 5)
        say(d, (310, y), task, 60, "lm")
        n = int(16 * prog(t, 0.1 + 0.3*i, 0.5 + 0.3*i))
        if n >= 2:
            d.line([(300 + k*36, y + 40 + j) for k, j in enumerate(SCRIB[i][:n])], RED, 5, "curve")
    r = 95 * pop(prog(t, 1.2, 1.5))
    if r > 5:  # paw stamp
        d.ellipse(pts(770, 1220, r, -0.6, -0.3, 0.6, 0.6), RED)
        for x, y in TOES:
            d.ellipse(pts(770, 1220, r, x-0.22, y-0.22, x+0.22, y+0.22), RED)
    caption(img, "I gave my to-do list to a town of cats", fade(t, -1, 2.3), size=76)
    return img

def mayor_scene(t):
    z = 2.4 - 1.4*ease(prog(t, 2, 4))
    img, d, _ = base(z)
    cat(d, 540 - 90*z, 960 + 80*z, 0.6*z, "mayor")
    caption(img, "The Mayor hands out the work", fade(t, 2.2, 6))
    return img

def recruit(t):
    img, d, _ = base()
    leaders(d)
    card(d, *along(PATH, ease(prog(t, 6.3, 8.2))), 1.0, "task")
    for i, hx in enumerate((640, 750, 860)):
        cat(d, hx, 1440, 0.45*pop(prog(t, 8.3 + 0.3*i, 8.6 + 0.3*i)), "helper")
    caption(img, "Directors recruit their own teams", fade(t, 6, 10))
    return img

def gallery(t):
    img, _, _ = base()
    d = shade(img, (40, 60, 40), 150)
    d.rectangle([230, 560, 850, 1260], "#fffaf0", "#8a5a3b", 22)
    say(d, (540, 640), "GALLERY", 80)
    for i, (label, sx) in enumerate((("script", 420), ("code", 860), ("review", 660))):
        p = ease(prog(t, 10.6 + 0.9*i, 11.3 + 0.9*i))
        if p > 0:
            card(d, sx + (540-sx)*p, 1380 - (250 + 130*i)*p, 1.6, label)
    for i, role in enumerate(COL):
        cat(d, 190 + 220*i, 1480 - 18*abs(math.sin(t*5 + i)), 0.75, role)
    caption(img, "Everything they make lands in the gallery", fade(t, 10, 14))
    return img

def quest(t):
    img, _, _ = base()
    d = shade(img, (60, 40, 20), 160)
    bot = 630 + 640*ease(prog(t, 14.2, 15.2))
    d.rectangle([250, 600, 830, bot], "#f3e2b3", "#8a6a3b", 4)
    for i, (txt, size) in enumerate((("QUEST:", 90), ("owner step:", 70), ("sign in", 100))):
        if 780 + i*170 < bot:
            say(d, (540, 730 + i*170), txt, size)
    for yy in (600, bot):
        d.rounded_rectangle([220, yy-26, 860, yy+26], 26, "#c89a5a", INK, 4)
    caption(img, "I only get the quests they can't do", fade(t, 14, 17))
    return img

def dusk(t):
    img, d, wins = base()
    leaders(d)
    d = shade(img, (30, 25, 80), 140*ease(prog(t, 17, 18)))
    for i, r in enumerate(wins):
        if t > 17.4 + 0.08*i:
            d.rectangle(r, "#ffd84a", INK, 2)
    caption(img, "Clowder", fade(t, 17.6, 99), 520, 170)
    caption(img, "a town of AI cats", fade(t, 17.8, 99), 780, 56)
    caption(img, "made with AI + code", fade(t, 18, 99), 900, 48)
    return img

SCENES = [(2, intro), (6, mayor_scene), (10, recruit), (14, gallery), (17, quest), (99, dusk)]

def frame(t):
    i = next(i for i, (end, _) in enumerate(SCENES) if t < end)
    img, u = SCENES[i][1](t), (t - SCENES[i-1][0]) / 0.4
    if i and u < 1:  # crossfade in
        img = Image.blend(SCENES[i-1][1](t), img, ease(u))
    return img.convert("RGB")

def main():
    os.makedirs("docs", exist_ok=True)
    cmd = ("ffmpeg -hide_banner -loglevel warning -y -f rawvideo -pix_fmt rgb24 -s 1080x1920 -r 30 -i - "
           "-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 "
           "-map 0:v -map 1:a -c:v libx264 -pix_fmt yuv420p -profile:v high -crf 20 "
           "-c:a aac -b:a 128k -shortest -movflags +faststart " + OUT).split()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(N):
        proc.stdin.write(frame(n / FPS).tobytes())
    proc.stdin.close()
    if proc.wait():
        sys.exit(f"ffmpeg exited {proc.returncode}")
    frame(540 / FPS).save(POSTER)
    print(N, "frames:", OUT, POSTER)

if __name__ == "__main__":
    main()
