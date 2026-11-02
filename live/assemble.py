#!/usr/bin/env python3
"""assemble.py - clowderA (Cat Town intro) frames -> docs/clowderA.mp4, plus probe and gate-line helpers.

usage: python3 live/assemble.py live/reels/clowderA.json              # cut: push-in edit + measured plates + chiptune + encode
       python3 live/assemble.py live/reels/clowderA.json --probe      # WF_PROBE line, exit 1 on any spec miss
       python3 live/assemble.py live/reels/clowderA.json --gatelines  # copy recorder log lines into gates/status json
Encode settings are the ones cut.sh uses (libx264 high crf 20 preset medium yuv420p, aac 128k stereo, faststart).
cut.sh itself is not reused: it cuts .shots out of recorded takes, and this reel is one continuous frame sequence.
Plates are drawn with Pillow onto full-frame transparent PNGs, so each TEXTBOX line is the exact box that is drawn.
Plate x,y = top-left of the backed box; text is inset by pad. Fail if x0<0, x1>xMax, y0<yMin or y1>yMax.
Optional cfg["edit"]["pushIn"]: a slow centred zoom on the REAL recorded frames during named held steps (see push_in).
"""
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
mode = sys.argv[2] if len(sys.argv) > 2 else "--cut"
R = cfg["reel"]
OUTS = cfg["outputs"]
for _p in OUTS.values():
    if not re.match(rf"^docs/{re.escape(R)}[.-]", _p):
        print(f"CUT_FAIL output path must be docs/{R}.*: {_p}")
        sys.exit(1)
MP4 = OUTS["mp4"]
W, H = 1080, 1920
FPS = int(cfg["recorder"].get("fps", 30))
DUR = float(cfg["gates"]["probe"]["durS"])


def probe():
    if not os.path.exists(MP4):
        print(f"WF_PROBE FAIL missing {MP4}")
        return 1
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,codec_name,width,height,pix_fmt:format=duration", "-of", "json", MP4],
                       capture_output=True, text=True)
    if r.returncode:
        print("WF_PROBE FAIL ffprobe " + r.stderr[:200])
        return 1
    j = json.loads(r.stdout)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), {})
    d = float(j.get("format", {}).get("duration", 0) or 0)
    want = cfg["gates"]["probe"]
    bad = []
    if (v.get("width"), v.get("height")) != (want["width"], want["height"]):
        bad.append("dims")
    if abs(d - DUR) > 0.1:
        bad.append("duration")
    if v.get("codec_name") != "h264":
        bad.append("vcodec")
    if v.get("pix_fmt") != "yuv420p":
        bad.append("pix_fmt")
    if a.get("codec_name") != "aac":
        bad.append("acodec")
    line = (f"{v.get('width')}x{v.get('height')} {d:.3f} s {v.get('codec_name')}/{a.get('codec_name')} "
            f"{v.get('pix_fmt')} {os.path.getsize(MP4):,} bytes")
    if bad:
        print(f"WF_PROBE FAIL {line} bad={','.join(bad)}")
        return 1
    print(f"WF_PROBE OK {line}")
    return 0


def gatelines():
    log = f"docs/{R}-log.txt"
    keys = ("SERVER", "PLAN", "PREROLL", "INTRO_PLAYED", "STEP ", "CINEMATIC", "INTRO_END", "INTRO_DRIFT",
            "CAM_EVENTS", "HTTP_403", "RELOAD", "PAGE_ERRORS", "FRAMES", "RESULT", "SKIP", "SETUP", "NETWORK_IDLE",
            "TEXTBOX", "AUDIO", "WF_PROBE", "APP", "CUT", "PUSHIN", "FOOTAGE")
    lines = []
    if os.path.exists(log):
        lines = [l[:240] for l in open(log, encoding="utf-8", errors="replace").read().splitlines() if l.startswith(keys)]
    for p in (OUTS["gates"], OUTS["status"]):
        try:
            j = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            print(f"GATELINES_SKIP {p} {e}")
            continue
        j["recorder_lines"] = lines[-80:]
        json.dump(j, open(p, "w", encoding="utf-8"), indent=1)
    print(f"GATELINES n={len(lines)}")
    return 0


def rgba(c):
    name, _, a = str(c).partition("@")
    base = {"black": (0, 0, 0), "white": (255, 255, 255)}[name]
    return base + (round(255 * float(a or 1)),)


def step_spans(rc):
    """Output-time span (s) of each recorder step. Frame 0 = intro mount (t0), as in cinema.mjs."""
    spans, t = {}, 0.0
    for s in rc["steps"]:
        d = float(s["ms"]) / float(s["speed"]) / 1000.0
        spans[s["name"]] = (t, t + d)
        t += d
    return spans


def push_in(frames, rc):
    """Slow centred push-in on the REAL recorded frames, only inside the held steps listed in cfg["edit"]["pushIn"].
    This is ordinary editing of live footage (a digital crop + resize, i.e. a Ken Burns style zoom). No pixels are
    generated and nothing is added that the app did not render. Outside those spans frames are copied unchanged.
    The zoom is linear (constant speed) inside a span; on the next step's first frame it is back to 1.0, which reads
    as a cut at the step boundary. Optional "tailS" limits a span to the last tailS seconds of its step(s), so the
    zoom covers only a held tail and still resets exactly on the step boundary.
    Returns the list of frames to encode, or None on a config error."""
    from PIL import Image
    ed = (cfg.get("edit") or {}).get("pushIn") or []
    if not ed:
        print("PUSHIN none")
        return frames
    spans = step_spans(rc)
    zoom = [1.0] * len(frames)
    for e in ed:
        names = e["steps"]
        missing = [n for n in names if n not in spans]
        if missing:
            print(f"CUT_FAIL pushIn unknown step(s) {missing}")
            return None
        a_t = min(spans[n][0] for n in names)
        b_t = max(spans[n][1] for n in names)
        tail = e.get("tailS")
        if tail is not None:
            a_t = max(a_t, b_t - float(tail))
        a, b = round(a_t * FPS), min(len(frames), round(b_t * FPS))
        z1 = float(e["zoomTo"])
        if not (1.0 < z1 <= 1.35) or b - a < 2:
            print(f"CUT_FAIL pushIn bad span or zoom {e}")
            return None
        for i in range(a, b):
            zoom[i] = 1.0 + (z1 - 1.0) * (i - a) / (b - a - 1)
        print(f"PUSHIN steps={'+'.join(names)}{'' if tail is None else f' tailS={float(tail):.2f}'} "
              f"t={a_t:.3f}-{b_t:.3f}s frames={a}-{b - 1} zoom=1.000->{z1:.3f} "
              f"linear centred (edit of live footage)")
    out = "out/frames_edit"
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, "*.png")):
        os.remove(f)
    res, edited = [], 0
    for i, f in enumerate(frames):
        dst = os.path.join(out, os.path.basename(f))
        z = zoom[i]
        if z == 1.0:
            shutil.copyfile(f, dst)
        else:
            im = Image.open(f)
            im.load()
            w, h = im.size
            cw, ch = w / z, h / z
            box = ((w - cw) / 2, (h - ch) / 2, (w + cw) / 2, (h + ch) / 2)
            im.resize((w, h), Image.LANCZOS, box=box).save(dst)
            edited += 1
        res.append(dst)
    print(f"PUSHIN_FRAMES edited={edited} copied={len(frames) - edited} of {len(frames)}")
    return res


def cut():
    from PIL import Image, ImageDraw, ImageFont
    rc = cfg["recorder"]
    frames = sorted(glob.glob(os.path.join(rc["framesDir"], "*.png")))
    need = int(rc["frames"])
    print(f"FRAMES_IN n={len(frames)} need={need}")
    if len(frames) != need:
        print("CUT_FAIL frame count mismatch")
        return 1
    if abs(need / FPS - DUR) > 0.05:
        print(f"CUT_FAIL frames/fps={need / FPS:.3f}s but probe durS={DUR}")
        return 1
    edited = push_in(frames, rc)
    if edited is None:
        return 1
    frames_dir = os.path.dirname(edited[0]) if edited else rc["framesDir"]
    T = cfg["text"]
    band = T["band"]
    font_path = "/usr/share/fonts/truetype/dejavu/" + T.get("font", "DejaVuSans-Bold.ttf")
    if not os.path.exists(font_path):
        print(f"CUT_FAIL font missing: {font_path}")
        return 1
    os.makedirs("out/plates", exist_ok=True)
    plates, unsafe = [], 0
    for p in T["plates"]:
        fs, pad, gap = int(p["fontsize"]), int(p.get("pad", 18)), int(p.get("lineGap", 12))
        font = ImageFont.truetype(font_path, fs)
        x, y = int(p["x"]), int(p["y"])
        txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dt = ImageDraw.Draw(txt)
        bbs = []
        for i, line in enumerate(p["lines"]):
            pos = (x + pad, y + pad + i * (fs + gap))
            bbs.append(dt.textbbox(pos, line, font=font))
            dt.text(pos, line, font=font, fill=rgba(p.get("fontcolor", "white")))
        n = len(p["lines"])
        x0 = min(x, int(math.floor(min(b[0] for b in bbs))) - pad)
        y0 = min(y, int(math.floor(min(b[1] for b in bbs))) - pad)
        x1 = int(math.ceil(max(b[2] for b in bbs))) + pad
        y1 = max(y + 2 * pad + n * fs + (n - 1) * gap, int(math.ceil(max(b[3] for b in bbs))) + pad)
        box = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(box).rectangle([x0, y0, x1 - 1, y1 - 1], fill=rgba(p.get("boxcolor", "black@0.72")))
        img = Image.alpha_composite(box, txt)
        png = f"out/plates/{p['label']}.png"
        img.save(png)
        s, e = float(p["start"]), float(p["end"])
        ok = (x0 >= 0 and x1 <= band["xMax"] and y0 >= band["yMin"] and y1 <= band["yMax"]
              and 0 <= s < e <= DUR + 1e-6)
        unsafe += 0 if ok else 1
        print(f"TEXTBOX {R} {p['label']} {max(0, x0)},{max(0, y0)},{x1},{y1} safe={'OK' if ok else 'FAIL'} "
              f"t={s}-{e} fs={fs} band=x<={band['xMax']},y{band['yMin']}-{band['yMax']}")
        plates.append({"png": png, "start": s, "end": e})
    if unsafe:
        print(f"CUT_FAIL {unsafe} text plate(s) outside the safe band")
        return 1
    au = cfg["audio"]
    af = au["ffmpeg"]
    if au.get("thirdPartyMusic") is not False or au.get("source") != "code" or not af.startswith("aevalsrc="):
        print("CUT_FAIL audio must be code-made aevalsrc with thirdPartyMusic false")
        return 1
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-framerate", str(FPS), "-pattern_type", "glob", "-i", os.path.join(frames_dir, "*.png")]
    for pl in plates:
        cmd += ["-i", pl["png"]]
    cmd += ["-f", "lavfi", "-i", af]
    chain = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[b0]"
    for k, pl in enumerate(plates, 1):
        chain += (f";[b{k - 1}][{k}:v]overlay=0:0:eof_action=repeat:"
                  f"enable='between(t,{pl['start']},{pl['end']})'[b{k}]")
    chain += f";[b{len(plates)}]format=yuv420p[v]"
    cmd += ["-filter_complex", chain, "-map", "[v]", "-map", f"{len(plates) + 1}:a:0",
            "-frames:v", str(int(round(DUR * FPS))),
            "-c:v", "libx264", "-profile:v", "high", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
            "-ac", "2", "-c:a", "aac", "-b:a", "128k", "-t", f"{DUR}", "-movflags", "+faststart", MP4]
    os.makedirs(os.path.dirname(MP4), exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not os.path.exists(MP4):
        print("CUT_FAIL ffmpeg " + (r.stderr or "")[-600:].replace("\n", " | "))
        return 1
    print(f"{au.get('logLine', 'AUDIO=chiptune')} source=code third_party_music=no")
    print("FOOTAGE live=1 fallback=0 of 1 shots (continuous intro capture; edit=push-in on held steps only)")
    print(f"CUT OK {MP4} FRAMES {int(round(DUR * FPS))} BYTES {os.path.getsize(MP4)}")
    return 0


if __name__ == "__main__":
    sys.exit({"--probe": probe, "--gatelines": gatelines}.get(mode, cut)())
