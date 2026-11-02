#!/usr/bin/env python3
# shots6v.py - Reel 6: choose the shot windows from the logged DEATH times so deaths are on screen.
# Each death shot ends `post` s after a death (the held fail screen is visible at the end of the shot).
# Rewrites the runner's copy of the reel config (never committed; the workflow restores it) and saves
# docs/<reel>-shots.json. Exit 1 (no render) if fewer than min_deaths_on_screen shots show a death
# tail_min..tail_max s before the shot ends.
# v3: shots_from_deaths.counter_fmt (e.g. "DEATH {n}") puts a counter on every shot that shows a
#     death, numbered in reel order (it counts deaths shown in this Reel, not all deaths in the takes).
import json, sys
cfg_path = sys.argv[1]
cfg = json.load(open(cfg_path))
try:
    st = json.load(open('out/raw/status.json'))
except Exception as e:
    print(f'DEATHS_ON_SCREEN 0 FAIL no status.json: {e}'); sys.exit(1)
P = cfg.get('shots_from_deaths') or {}
durs = [float(d) for d in P.get('durs', [2.2, 2.1, 2.1, 2.2, 2.1, 2.1, 2.2])]
post = float(P.get('post', 0.6))
need = int(P.get('min_deaths_on_screen', 2))
lo, hi = float(P.get('tail_min', 0.3)), float(P.get('tail_max', 0.8))
min_start = float(P.get('min_start', 0.3))
fmt = P.get('counter_fmt')
N = int(cfg.get('min_moves_per_shot', 3))
takes = [t['name'] for t in cfg['takes']]
secs = {t['name']: float(t.get('seconds', 8)) for t in cfg['takes']}
lead = {k: float((st.get(k) or {}).get('lead', 0) or 0) for k in takes}
W = max(durs)

def moves(k, a, b):
    return sum(1 for c in (st.get(k) or {}).get('changes', []) if lead[k] + a <= c < lead[k] + b)

def free(k, a, b, used):
    return all(b <= x or a >= y for (kk, x, y) in used if kk == k)

per = {k: [float(t) for t in ((st.get(k) or {}).get('death_t') or [])] for k in takes}
for k in takes:
    print(f"DEATH_TIMES {k} n={len(per[k])} " + ' '.join(f'{t:.2f}' for t in per[k]))

used, picks = [], []
queues = {k: list(per[k]) for k in takes}
while len(picks) < len(durs) and any(queues.values()):
    for k in takes:
        if len(picks) >= len(durs):
            break
        while queues[k]:
            t = queues[k].pop(0)
            b = t - lead[k] + post
            a = b - W
            if a < min_start or b > secs[k] - 0.05:
                print(f'DEATH_SKIP {k} t={t:.2f} window outside take'); continue
            if not free(k, a, b, used):
                print(f'DEATH_SKIP {k} t={t:.2f} overlaps a chosen window'); continue
            m = moves(k, a, b)
            if m < N:
                print(f'DEATH_SKIP {k} t={t:.2f} only {m} hero moves'); continue
            used.append((k, a, b)); picks.append((k, t)); break

shots = []
for i, (k, t) in enumerate(picks):
    d = durs[i]
    b = t - lead[k] + post
    shots.append({'take': k, 'start': round(b - d, 3), 'dur': d, 'death_t': round(t, 3)})

ti = len(shots)
while len(shots) < len(durs):
    d = durs[len(shots)]
    best = None
    order = takes[ti % len(takes):] + takes[:ti % len(takes)]
    for k in order:
        a = min_start
        while a + d <= secs[k] - 0.05 + 1e-9:
            if free(k, a, a + d, used):
                m = moves(k, a, a + d)
                if best is None or m > best[0]:
                    best = (m, k, a)
            a = round(a + 0.1, 3)
        if best and best[0] >= N:
            break
    if not best:
        print('DEATHS_ON_SCREEN 0 FAIL no free window left for a filler shot'); sys.exit(1)
    m, k, a = best
    used.append((k, a, a + d)); shots.append({'take': k, 'start': round(a, 3), 'dur': d}); ti += 1

orig = cfg.get('shots') or []
if orig and orig[0].get('text_top'):
    shots[0]['text_top'] = orig[0]['text_top']
if orig and orig[-1].get('text_bottom'):
    shots[-1]['text_bottom'] = orig[-1]['text_bottom']

on = 0
for i, s in enumerate(shots):
    k = s['take']; a = lead[k] + s['start']; b = a + s['dur']
    ds = [t for t in per[k] if a <= t <= b and lo <= b - t <= hi]
    on += 1 if ds else 0
    if ds and fmt:
        s['counter'] = fmt.format(n=on)
    tag = f't={ds[0]:.2f} tail={b - ds[0]:.2f}s' if ds else 'none'
    print(f"SHOT_PLAN {i} take {k} start {s['start']:.2f} dur {s['dur']:.2f} hero_moves {moves(k, s['start'], s['start'] + s['dur'])} death_on_screen {tag} counter {s.get('counter', '-')}")
print(f"SHOTS_TOTAL {sum(s['dur'] for s in shots):.2f}s from_deaths={len(picks)} fillers={len(shots) - len(picks)}")
ok = on >= need
print(f"DEATHS_ON_SCREEN {on} min {need} {'OK' if ok else 'FAIL'}")
if not ok:
    sys.exit(1)
cfg['shots'] = shots
json.dump(cfg, open(cfg_path, 'w'), indent=1)
json.dump({'shots': shots}, open(f"docs/{cfg['reel']}-shots.json", 'w'), indent=1)
