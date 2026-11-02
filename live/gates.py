#!/usr/bin/env python3
"""gates.py - put every gate result into docs/<reel>-status.json and a small docs/<reel>-gates.json.

usage (Commit render step): python3 live/gates.py <reel>
env: O_<STEP> step outcomes for each step in STEPS (default record,shots,state,cut,probe,motion),
     STEPS (optional comma list to override), PASS (yes|no),
     OLD_BLOB (git blob of docs/<reel>.mp4 at HEAD, '' if none), NEW_BLOB (blob of this run's mp4, '' if none),
     RUN_ID, KIT_SHA.
Only the GATES line / gates object counts as proof that a render passed. A file left in the repo does not.
Copied from whatif6v-staging @ 0afc6d2f with: comma-safe WF_PROBE parsing, codec logging, and the
HTTP_403 / CINEMATIC / RELOAD / CAM_EVENTS / LINECOUNT gates. Any of those reporting FAIL forces pass=no.
"""
import hashlib
import json
import os
import re
import sys

R = sys.argv[1]
LOG = f"docs/{R}-log.txt"
lines = open(LOG, encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(LOG) else []


def last(prefix):
    hits = [l for l in lines if l.startswith(prefix)]
    return hits[-1] if hits else None


def last_any(key):
    hits = [l for l in lines if key in l]
    return hits[-1] if hits else None


def fnum(pat, s):
    m = re.search(pat, s or "")
    return float(m.group(1)) if m else None


STEPS = [s.strip() for s in (os.environ.get("STEPS") or "record,shots,state,cut,probe,motion").split(",") if s.strip()]
outcome = {k: (os.environ.get("O_" + k.upper(), "") or "not_run") for k in STEPS}
failing = next((k for k in STEPS if outcome[k] != "success"), None)
passed = os.environ.get("PASS") == "yes"
RUN = os.environ.get("RUN_ID", "")
KIT = os.environ.get("KIT_SHA", "")

# --- WF_PROBE: accept space- or comma-separated forms, e.g.
#   'WF_PROBE OK 1080x1920 15.000 s h264/aac 2,990,258 bytes'
#   'WF_PROBE,1080,1920,15.000,h264,aac'  or  'WF_PROBE width=1080,height=1920,duration=15.000,codec=h264'
probe = last_any("WF_PROBE")
pw = ph = dur = None
vcodec = acodec = None
if probe:
    m = re.search(r"(\d{3,4})\s*[x×]\s*(\d{3,4})", probe)
    if not m:
        m = re.search(r"width[=:]\s*(\d{3,4}).*?height[=:]\s*(\d{3,4})", probe)
    if not m:
        m = re.search(r"WF_PROBE[^\d]*?(\d{3,4})\s*,\s*(\d{3,4})\b", probe)
    if m:
        pw, ph = int(m.group(1)), int(m.group(2))
    dur = (fnum(r"duration[=:]\s*([\d.]+)", probe)
           or fnum(r"\b(\d{1,3}\.\d+)\s*s\b", probe)
           or fnum(r"[ ,](\d{1,3}\.\d{1,3})(?:[ ,]|$)", probe))
    cm = re.search(r"(?:vcodec|codec)[=:]\s*([A-Za-z0-9_]+)", probe) or re.search(r"\b(h264|hevc|h265|vp9|av1|mpeg4)\b", probe)
    vcodec = cm.group(1) if cm else None
    am = re.search(r"acodec[=:]\s*([A-Za-z0-9_]+)", probe) or re.search(r"\b(aac|opus|mp3|vorbis)\b", probe)
    acodec = am.group(1) if am else None
dims = f"{pw}x{ph}" if pw and ph else None
print(f"WF_PROBE_PARSED dims={dims} dur={dur} vcodec={vcodec} acodec={acodec} line={probe!r}")

min1_line = last("MOTION_MIN_1S")
min1 = fnum(r"MOTION_MIN_1S ([\d.]+)", min1_line)
min1_at = fnum(r"starting ([\d.]+)s", min1_line)
first = fnum(r"FIRST_SECOND_MOTION ([\d.]+)", last("FIRST_SECOND_MOTION"))
frozen = fnum(r"FROZEN_RUNS (\d+)", last("FROZEN_RUNS"))
motion_verdict = last("MOTION_OK") or last("MOTION_FAIL")
per_second = []
for l in lines:
    m = re.match(r"^\s+(\d+)s\s+([\d.]+)", l)
    if m:
        per_second.append([int(m.group(1)), float(m.group(2))])
per_shot = [l for l in lines if l.startswith("PER_SHOT_MOTION")]
frozen_lines = [l.strip() for l in lines if l.strip().startswith("FROZEN ")]

g3 = [l for l in lines if l.startswith("GATE3D")]
gate3d = "OK" if "GATE3D OK" in lines else ("FAIL" if g3 else "n/a")
state = "OK" if "STATE_OK" in lines else (last("STATE_FAIL") or "not_run")
deaths_line = last("DEATHS_ON_SCREEN")
deaths = fnum(r"DEATHS_ON_SCREEN (\d+)", deaths_line)


# --- named gates written by the recorder as '<NAME>_OK ...', '<NAME> OK ...', '<NAME>_FAIL ...' or '<NAME> FAIL ...'
def gate(name):
    hits = [l for l in lines if l.startswith(name)]
    if not hits:
        return {"verdict": "not_run", "line": None}
    h = hits[-1]
    if re.match(rf"^{name}(_| )FAIL\b", h) or re.search(r"\bFAIL\b", h):
        return {"verdict": "FAIL", "line": h[:200]}
    if re.match(rf"^{name}(_| )OK\b", h):
        return {"verdict": "OK", "line": h[:200]}
    return {"verdict": "seen", "line": h[:200]}


named = {n: gate(n) for n in ["HTTP_403", "CINEMATIC", "RELOAD", "CAM_EVENTS", "LINECOUNT"]}
# HTTP_403: fail on any 403 even if the recorder forgot to say FAIL
n403 = fnum(r"(?:n|count)=(\d+)", named["HTTP_403"]["line"])
if n403 is not None and n403 > 0:
    named["HTTP_403"]["verdict"] = "FAIL"
for n, g in named.items():
    if g["verdict"] == "FAIL":
        passed = False
        failing = failing or n.lower()

boxes = []
for l in lines:
    if l.startswith("TEXTBOX"):
        m = re.search(r"(\d+),(\d+),(\d+),(\d+) safe=(\w+)", l)
        if m:
            boxes.append({"x0": int(m.group(1)), "y0": int(m.group(2)), "x1": int(m.group(3)), "y1": int(m.group(4)),
                          "safe": m.group(5), "line": l[:160]})
tb_max_x = max((b["x1"] for b in boxes), default=None)
tb_safe = (all(b["safe"] == "OK" for b in boxes) if boxes else None)
audio_line = next((l for l in reversed(lines) if "AUDIO=" in l), None)
audio = (re.search(r"AUDIO=(\S+)", audio_line).group(1) if audio_line else None)
footage = last("FOOTAGE")
errors = [l[:200] for l in lines if re.search(r"Traceback|Error|_FAIL|_MISS|\bFAIL\b", l)][-15:]

old, new = os.environ.get("OLD_BLOB", ""), os.environ.get("NEW_BLOB", "")
mp4 = None
mp4_path = f"docs/{R}.mp4"
if passed and new and new != old and os.path.exists(mp4_path):
    b = open(mp4_path, "rb").read()
    mp4 = {"new": True, "render_blob": new, "previous_blob": old or None, "bytes": len(b),
           "sha256": hashlib.sha256(b).hexdigest(), "run_id": RUN, "kit_sha": KIT}

GATES = (f"GATES pass={'yes' if passed else 'no'} failing_step={failing or 'none'} run={RUN} kit={KIT[:8]} "
         f"probe={dims} dur={dur} vcodec={vcodec} acodec={acodec} "
         f"motion_min_1s={min1} first_s={first} frozen_runs={None if frozen is None else int(frozen)} "
         f"http403={named['HTTP_403']['verdict']} cinematic={named['CINEMATIC']['verdict']} "
         f"reload={named['RELOAD']['verdict']} cam_events={named['CAM_EVENTS']['verdict']} "
         f"linecount={named['LINECOUNT']['verdict']} "
         f"gate3d={gate3d} state={state} deaths_on_screen={None if deaths is None else int(deaths)} "
         f"textbox_max_x={tb_max_x} textbox_safe={tb_safe} audio={audio} "
         f"mp4={'new:' + new[:10] if mp4 else 'none'}")

gates = {
    "pass": passed,
    "failing_step": failing,
    "step_outcomes": outcome,
    "run_id": RUN,
    "kit_sha": KIT,
    "mp4": mp4,
    "mp4_note": ("new render committed" if mp4 else ("no new mp4: gates failed, any old docs/%s.mp4 was deleted" % R if not passed else "gates passed but mp4 blob equals HEAD; not a new render")),
    "wf_probe": {"line": probe, "dims": dims, "duration_s": dur, "vcodec": vcodec, "acodec": acodec},
    "motion": {"verdict": motion_verdict, "min_1s": min1, "min_1s_at": min1_at, "first_second": first,
               "frozen_runs": frozen, "frozen": frozen_lines, "freezedetect": last("FREEZEDETECT"),
               "per_shot": per_shot, "per_second": per_second},
    "named_gates": named,
    "gate3d": {"verdict": gate3d, "lines": g3},
    "state": state,
    "deaths_on_screen": {"n": deaths, "line": deaths_line},
    "textbox": {"max_x": tb_max_x, "all_safe": tb_safe, "boxes": boxes},
    "audio": {"value": audio, "line": audio_line},
    "footage": footage,
    "errors": errors,
    "log_tail": [l[:200] for l in lines[-30:]],
}

try:
    takes = json.load(open("out/raw/status.json"))
except Exception as e:  # record step may not have written it
    takes = {"status_json_error": str(e)}

os.makedirs("docs", exist_ok=True)
status = {"GATES": GATES, "gates": gates}
status.update(takes if isinstance(takes, dict) else {"takes": takes})
json.dump(status, open(f"docs/{R}-status.json", "w"), indent=1)
json.dump({"GATES": GATES, **gates}, open(f"docs/{R}-gates.json", "w"), indent=1)
print(GATES)
print(f"GATES_JSON docs/{R}-gates.json and docs/{R}-status.json")
sys.exit(0)
