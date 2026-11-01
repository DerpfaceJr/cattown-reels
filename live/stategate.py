#!/usr/bin/env python3
# stategate.py - fail the reel if the hero's position changed fewer than N times inside any shot.
# Reads out/raw/status.json (changes = seconds since recording start when hero x,y,floor changed).
import json, sys
cfg = json.load(open(sys.argv[1]))
try:
    st = json.load(open('out/raw/status.json'))
except Exception as e:
    print(f'STATE_FAIL no status.json: {e}'); sys.exit(1)
N = int(cfg.get('min_moves_per_shot', 3))
bad = 0
for i, s in enumerate(cfg['shots']):
    t = st.get(s['take'], {})
    a = float(t.get('lead', 0)) + float(s['start']); b = a + float(s['dur'])
    n = sum(1 for c in t.get('changes', []) if a <= c < b)
    ok = n >= N
    bad += 0 if ok else 1
    print(f"STATE shot {i} take {s['take']} window {a:.2f}-{b:.2f}s hero_moves {n} min {N} {'OK' if ok else 'FAIL'}")
for k, t in st.items():
    print(f"STATE_TAKE {k} state_changes {t.get('state_changes', 0)} hero_moves {t.get('hero_moves', 0)} keys_sent {t.get('keys_sent', 0)} retries {t.get('retries', 0)} floor_max {t.get('floor_max', 0)} kills {t.get('kills', 0)}")
print('STATE_OK' if not bad else f'STATE_FAIL {bad} shot(s) under {N} hero moves')
sys.exit(1 if bad else 0)
