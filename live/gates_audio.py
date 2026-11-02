#!/usr/bin/env python3
"""Fill the top-level 'audio' field of docs/<reel>-gates.json from the recorder/assemble 'AUDIO src=' log line.
Runs right after live/gates.py in the clowder job (gates.py left its 'audio' field null for this line format).
Usage: python3 live/gates_audio.py <reel>"""
import json, os, re, sys

reel = sys.argv[1]
gates_path = f"docs/{reel}-gates.json"
log_path = f"docs/{reel}-log.txt"
line = None
try:
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            m = re.search(r"AUDIO src=.*", raw)
            if m and not raw.startswith("GATES_AUDIO"):
                line = m.group(0).strip()
except FileNotFoundError:
    pass
if not os.path.exists(gates_path):
    print(f"GATES_AUDIO skipped: no {gates_path}")
    sys.exit(0)
with open(gates_path, encoding="utf-8") as fh:
    data = json.load(fh)
if line:
    rest = line.split("src=", 1)[1]
    src = re.split(r"\s+\w+=", rest, maxsplit=1)[0].strip()
    kv = dict(re.findall(r"(\w+)=(\S+)", rest))
    data["audio"] = {
        "line": line,
        "src": src,
        "source": kv.get("source"),
        "third_party_music": kv.get("third_party_music"),
    }
    print(f"GATES_AUDIO set audio.src={src} source={kv.get('source')} third_party_music={kv.get('third_party_music')}")
else:
    print("GATES_AUDIO missing: no audio line in the log; audio field left as is")
with open(gates_path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)
