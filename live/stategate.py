#!/usr/bin/env python3
# stategate.py - fail the reel if the hero's position changed fewer than N times inside any shot,
# or (require_distinct_paths) if two takes walk the same opening path (HERO_PATH lines in the log).
import json, re, sys
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
    if not isinstance(t, dict):
        continue
    print(f"STATE_TAKE {k} state_changes {t.get('state_changes', 0)} hero_moves {t.get('hero_moves', 0)} keys_sent {t.get('keys_sent', 0)} retries {t.get('retries', 0)} floor_max {t.get('floor_max', 0)} kills {t.get('kills', 0)} deaths {len(t.get('deaths', []) or [])}")

# Distinct opening paths: compare the first (up to) 8 logged positions of each take.
paths = {}
try:
    for line in open(f"docs/{cfg['reel']}-log.txt", encoding='utf8', errors='replace'):
        m = re.match(r'HERO_PATH (\S+) ?(.*)', line.strip())
        if m:
            paths[m.group(1)] = re.findall(r'\((-?\d+,-?\d+)\)f(\d+)', m.group(2))
except Exception as e:
    print(f'PATHS_UNREADABLE {e}')
same = 0
names = sorted(paths)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b = paths[names[i]], paths[names[j]]
        k = min(len(a), len(b), 8)
        eq = k > 0 and a[:k] == b[:k]
        same += 1 if eq else 0
        print(f"PATH_COMPARE {names[i]} vs {names[j]} first {k} positions {'SAME' if eq else 'DIFFER'}")
if cfg.get('require_distinct_paths') and same:
    print(f'PATHS_FAIL {same} take pair(s) share the same opening path')
    bad += 1
print('STATE_OK' if not bad else f'STATE_FAIL {bad} check(s) failed (min {N} hero moves per shot, distinct paths)')
sys.exit(1 if bad else 0)
