#!/usr/bin/env python3
"""gates.py - put every gate result into docs/<reel>-status.json and a small docs/<reel>-gates.json.

usage (Commit render step): python3 live/gates.py <reel>
env: O_LINECOUNT O_RECORD O_SHOTS O_STATE O_CUT O_PROBE O_MOTION (step outcomes), PASS (yes|no),
     OLD_BLOB (git blob of docs/<reel>.mp4 at HEAD, '' if none), NEW_BLOB (blob of this run's mp4, '' if none),
     RUN_ID, KIT_SHA.
Only the GATES line / gates object counts as proof that a render passed. A file left in the repo does not.
whatif7v: adds the linecount step (default success when the workflow has no such step) and a linecount= field.
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


def fnum(pat, s):
    m = re.search(pat, s or "")
    return float(m.group(1)) if m else None


STEPS = ["linecount", "record", "shots", "state", "cut", "probe", "motion"]
outcome = {k: (os.environ.get("O_" + k.upper(), "") or "not_run") for k in STEPS}
if "O_LINECOUNT" not in os.environ:
    outcome["linecount"] = "success"  # older workflows without a LINECOUNT step
failing = next((k for k in STEPS if outcome[k] != "success"), None)
passed = os.environ.get("PASS") == "yes"
RUN = os.environ.get("RUN_ID", "")
KIT = os.environ.get("KIT_SHA", "")

lc_counts = last("LINECOUNT ")
lc_text = last("LINECOUNT_TEXT")
if "LINECOUNT_FAIL" in lines or (lc_text and "MISMATCH" in lc_text):
    linecount = "FAIL"
elif "LINECOUNT_OK" in lines and lc_text and lc_text.endswith("OK"):
    linecount = "OK"
elif lc_counts and "n/a" in lc_counts:
    linecount = "n/a"
else:
    linecount = "not_run"

probe = last("WF_PROBE")
dims = re.search(r"(\d{3,4})x(\d{3,4})", probe or "")
dur = fnum(r"([\d.]+)\s*s\b", probe)

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
errors = [l[:200] for l in lines if re.search(r"Traceback|Error|_FAIL|_MISS|MISMATCH|\bFAIL\b", l)][-15:]

old, new = os.environ.get("OLD_BLOB", ""), os.environ.get("NEW_BLOB", "")
mp4 = None
mp4_path = f"docs/{R}.mp4"
if passed and new and new != old and os.path.exists(mp4_path):
    b = open(mp4_path, "rb").read()
    mp4 = {"new": True, "render_blob": new, "previous_blob": old or None, "bytes": len(b),
           "sha256": hashlib.sha256(b).hexdigest(), "run_id": RUN, "kit_sha": KIT}

GATES = (f"GATES pass={'yes' if passed else 'no'} failing_step={failing or 'none'} run={RUN} kit={KIT[:8]} "
         f"linecount={linecount} "
         f"probe={(dims.group(0) if dims else None)} dur={dur} "
         f"motion_min_1s={min1} first_s={first} frozen_runs={None if frozen is None else int(frozen)} "
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
    "linecount": {"verdict": linecount, "counts": lc_counts, "text": lc_text, "src": last("LINECOUNT_SRC"),
                  "spans": last("LINECOUNT_SPANS"), "mismatch": [l for l in lines if l.startswith("LINECOUNT_MISMATCH")]},
    "wf_probe": {"line": probe, "dims": dims.group(0) if dims else None, "duration_s": dur},
    "motion": {"verdict": motion_verdict, "min_1s": min1, "min_1s_at": min1_at, "first_second": first,
               "frozen_runs": frozen, "frozen": frozen_lines, "freezedetect": last("FREEZEDETECT"),
               "per_shot": per_shot, "per_second": per_second},
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

status = {"GATES": GATES, "gates": gates}
status.update(takes if isinstance(takes, dict) else {"takes": takes})
json.dump(status, open(f"docs/{R}-status.json", "w"), indent=1)
json.dump({"GATES": GATES, **gates}, open(f"docs/{R}-gates.json", "w"), indent=1)
print(GATES)
print(f"GATES_JSON docs/{R}-gates.json and docs/{R}-status.json")
