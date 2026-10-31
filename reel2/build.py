#!/usr/bin/env python3
"""Reel 2 builder: real Clowder app footage + AI TTS voices + town music ducked
under the voices + burned-in captions. Input reel2/out/footage.webm,
output docs/reel2.mp4 (1080x1920, H.264 + AAC). Posts nothing.

Logs: VOICE=piper|espeak, MUSIC=town|standin (standin = audio.js values not
read, so the caption's 'app's own town track' line would need changing).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SR = 1080, 1920, 30, 44100
SAFE_X0, SAFE_X1, SAFE_Y0, SAFE_Y1 = 90, 860, 250, 1500
FOOTAGE = "reel2/out/footage.webm"
WORK = "reel2/out/build"
OUT = "docs/reel2.mp4"
APP_DIR = os.environ.get("APP_DIR", "app")
PIPER_MODEL = os.environ.get("PIPER_MODEL", "reel2/voices/en_US-ljspeech-medium.onnx")
FONT_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"]
MIN_DUR, MAX_DUR = 15.0, 35.0

# (role, spoken line, on-screen caption, stamp). Roles/order match caption 0c082783.
LINES = [
    ("hook", "Even my AI has a critic.", "Even my AI has a critic.", None),
    ("mayor", "The Mayor hands out the work.", "The Mayor hands out the work", None),
    ("director", "A Director plans it, and recruits a team.", "A Director plans it and recruits a team", None),
    ("scholar", "The Scholar does the research.", "The Scholar does the research", None),
    ("critic", "And the Critic sends drafts back. Fix this.", "The Critic sends drafts back", "FIX THIS"),
    ("cta", "Which cat would you hire first?", "Which cat would you hire first?", None),
]


def run(cmd, **kw):
    print("$", " ".join(cmd[:6]), "..." if len(cmd) > 6 else "")
    return subprocess.run(cmd, check=True, **kw)


# ---------- voices ----------
def piper_tts(text, path):
    if not (shutil.which("piper") and os.path.exists(PIPER_MODEL)):
        return False
    try:
        subprocess.run(["piper", "-m", PIPER_MODEL, "-f", path], input=text.encode(),
                       check=True, capture_output=True, timeout=180)
        return os.path.exists(path) and os.path.getsize(path) > 2000
    except Exception as e:  # noqa: BLE001
        print("piper failed:", e)
        return False


def espeak_tts(text, path):
    run(["espeak-ng", "-v", "en-us", "-s", "150", "-w", path, text])


def read_wav(path):
    with wave.open(path) as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise SystemExit(f"expected 16-bit wav: {path}")
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        t = np.arange(int(len(x) * SR / sr)) / SR
        x = np.interp(t, np.arange(len(x)) / sr, x).astype(np.float32)
    return x


def make_voices():
    paths = [os.path.join(WORK, f"v{i}.wav") for i in range(len(LINES))]
    engine = "piper"
    for (_, said, _, _), p in zip(LINES, paths):
        if not piper_tts(said, p):
            engine = "espeak"
            break
    if engine == "espeak":  # never mix engines
        for (_, said, _, _), p in zip(LINES, paths):
            espeak_tts(said, p)
    print(f"VOICE={engine}")
    clips = []
    for p in paths:
        c = read_wav(p)
        clips.append(c / (np.abs(c).max() + 1e-9) * 0.8)
    return clips


# ---------- music ----------
def town_params():
    p = os.path.join(APP_DIR, "public", "audio.js")
    if not os.path.exists(p):
        print("audio.js not found at", p)
        return None
    src = open(p, encoding="utf-8", errors="ignore").read()
    m = re.search(r"(?:bpm|BPM|tempo)\s*[:=]\s*(\d{2,3})", src)
    if not m:
        print("audio.js found but no bpm/tempo value matched")
        return None
    return {"bpm": int(m.group(1))}


def synth_music(dur, bpm):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    beat = 60.0 / bpm
    bar = 4 * beat
    chords = [[261.63, 329.63, 392.0], [196.0, 246.94, 293.66],
              [220.0, 261.63, 329.63], [174.61, 220.0, 261.63]]
    for k in range(int(dur / bar) + 1):
        a, b = int(k * bar * SR), min(n, int((k + 1) * bar * SR))
        if a >= n:
            break
        tt = t[a:b] - k * bar
        env = np.minimum(1, tt / 0.3) * np.clip((bar - tt) / 0.3, 0, 1)
        for f in chords[k % 4]:
            out[a:b] += ((np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * env * 0.12).astype(np.float32)
    for j in range(int(dur / beat) + 1):
        a = int(j * beat * SR)
        if a >= n:
            break
        L = min(n - a, int(0.25 * SR))
        tt = np.arange(L) / SR
        f = chords[(j // 4) % 4][0] / 2
        out[a:a + L] += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 12) * 0.15).astype(np.float32)
    return out / (np.abs(out).max() + 1e-9)


def smooth(mask, k):
    c = np.cumsum(np.concatenate([[0.0], mask]))
    sm = (c[k:] - c[:-k]) / k
    left = k // 2
    return np.concatenate([np.zeros(left), sm, np.zeros(len(mask) - len(sm) - left)])


# ---------- captions ----------
def font(size):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    print("WARNING: DejaVu not found, using Pillow default font")
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if d.textlength(trial, font=f) <= maxw:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def caption_png(text, path, stamp=None):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(64)
    lines = wrap(d, text, f, SAFE_X1 - SAFE_X0 - 60)
    if len(lines) > 2:
        raise SystemExit(f"CAPTION TOO LONG (>2 lines): {text!r}")
    lh = 80
    y0 = SAFE_Y1 - (lh * len(lines) + 40)
    d.rounded_rectangle([SAFE_X0, y0, SAFE_X1, SAFE_Y1], radius=28, fill=(20, 18, 30, 190))
    boxes = []
    for i, line in enumerate(lines):
        x = SAFE_X0 + (SAFE_X1 - SAFE_X0 - d.textlength(line, font=f)) / 2
        y = y0 + 20 + i * lh
        d.text((x, y), line, font=f, fill=(255, 255, 255, 255))
        boxes.append(d.textbbox((x, y), line, font=f))
    if stamp:
        sf = font(110)
        sx = SAFE_X0 + (SAFE_X1 - SAFE_X0 - d.textlength(stamp, font=sf)) / 2
        sy = 420
        bb = d.textbbox((sx, sy), stamp, font=sf)
        rect = [bb[0] - 24, bb[1] - 20, bb[2] + 24, bb[3] + 20]
        d.rectangle(rect, outline=(220, 40, 40, 255), width=10)
        d.text((sx, sy), stamp, font=sf, fill=(220, 40, 40, 255))
        boxes.append((rect[0] - 5, rect[1] - 5, rect[2] + 5, rect[3] + 5))
    for b in boxes:
        if b[0] < SAFE_X0 or b[2] > SAFE_X1 or b[1] < SAFE_Y0 or b[3] > SAFE_Y1:
            raise SystemExit(f"SAFE ZONE FAIL {text!r} {stamp!r} bbox={b}")
    img.save(path)


# ---------- main ----------
def main():
    if not os.path.exists(FOOTAGE) or os.path.getsize(FOOTAGE) < 10000:
        raise SystemExit(f"MISSING FOOTAGE {FOOTAGE}")
    os.makedirs(WORK, exist_ok=True)
    os.makedirs("docs", exist_ok=True)

    clips = make_voices()
    t, spans = 0.4, []
    for c in clips:
        spans.append((t, t + len(c) / SR))
        t += len(c) / SR + 0.6
    dur = min(max(t + 1.0, MIN_DUR + 1.0), MAX_DUR - 1.0)
    n = int(dur * SR)
    print(f"timeline: voice ends {spans[-1][1]:.2f}s, total {dur:.2f}s")

    voice = np.zeros(n, np.float32)
    mask = np.zeros(n)
    for (s, e), c in zip(spans, clips):
        a = int(s * SR)
        L = min(len(c), n - a)
        voice[a:a + L] += c[:L]
        mask[a:a + L] = 1.0

    params = town_params()
    print("MUSIC=town" if params else "MUSIC=standin", json.dumps(params or {}))
    mus = synth_music(dur, params["bpm"] if params else 96)
    duck_db = -12.0 * smooth(mask, int(0.08 * SR))
    mus = mus * 0.35 * (10 ** (duck_db / 20))
    fade = int(0.8 * SR)
    mus[-fade:] *= np.linspace(1, 0, fade)
    mix = voice + mus
    mix = mix / max(1.0, np.abs(mix).max() / 0.95)
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    wav_path = os.path.join(WORK, "mix.wav")
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.repeat(pcm, 2).tobytes())

    pngs, shows = [], []
    for i, ((_, _, cap, stamp), (s, e)) in enumerate(zip(LINES, spans)):
        p = os.path.join(WORK, f"cap{i}.png")
        caption_png(cap, p, stamp)
        pngs.append(p)
        start = 0.0 if i == 0 else s
        end = spans[i + 1][0] if i + 1 < len(spans) else dur
        shows.append((start, end))

    cmd = ["ffmpeg", "-y", "-hide_banner", "-i", FOOTAGE, "-i", wav_path]
    for p in pngs:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", p]
    fc = [f"[0:v]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
          f"tpad=stop_mode=clone:stop_duration={MAX_DUR:.0f}[v0]"]
    for i, (s, e) in enumerate(shows):
        fc.append(f"[v{i}][{i + 2}:v]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})'[v{i + 1}]")
    cmd += ["-filter_complex", ";".join(fc), "-map", f"[v{len(shows)}]", "-map", "1:a",
            "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", str(SR),
            "-movflags", "+faststart", OUT]
    run(cmd)

    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                         "stream=codec_type,codec_name,width,height:format=duration",
                         "-of", "json", OUT], capture_output=True, text=True, check=True)
    info = json.loads(pr.stdout)
    streams = info.get("streams", [])
    vid = [s for s in streams if s.get("codec_type") == "video"]
    aud = [s for s in streams if s.get("codec_type") == "audio"]
    d = float(info.get("format", {}).get("duration", 0))
    print("FFPROBE", json.dumps(info))
    errs = []
    if not aud:
        errs.append("no audio stream")
    if not vid or (vid[0].get("width"), vid[0].get("height")) != (W, H):
        errs.append("video is not 1080x1920")
    if not (MIN_DUR <= d <= MAX_DUR):
        errs.append(f"duration {d:.2f}s outside {MIN_DUR}-{MAX_DUR}s")
    if errs:
        raise SystemExit("CHECK FAIL: " + "; ".join(errs))
    print(f"CHECK OK {OUT} {os.path.getsize(OUT)} bytes, {d:.2f}s")


if __name__ == "__main__":
    main()
    sys.exit(0)
