// hooks6v.mjs - ESM load hook. Patches live/record.mjs in memory:
//  - per-take mode ('hunt' default | 'die') and seed (window.__recMode / __recSeed set before capture)
//  - die mode: always chase foes, ignore potions, never take stairs (stays on floor 1),
//    and when HP <= 60% stand still (Space) next to a foe so the hero dies. Inputs are scripted: disclose.
//  - seed: rotates BFS direction order, seeded opening wander each life, seeded fallback, so takes differ
//  - DEATH <take> t= floor= cause=<last game log lines> per death, DEATH_TALLY per take
// Every anchor must match exactly or the run fails (no silent partial patch).
const P = [
  ['over-cause',
    "if (s.over) return { act: 'retry', ...info };",
    "if (s.over) return { act: 'retry', cause: String((s.log || []).slice(-2).join(' / ') || 'unknown').slice(0, 120), ...info };"],
  ['die-foes',
    "if (p.hp > p.maxHp * 0.35) for (const k of foes) goals.add(k);",
    "const MODE = window.__recMode || 'hunt', SEED = window.__recSeed || 0;\n  if (MODE === 'die' || p.hp > p.maxHp * 0.35) for (const k of foes) goals.add(k);\n  if (MODE === 'die' && p.hp <= p.maxHp * 0.6) { for (const e of s.enemies) if (Math.abs(e.x - p.x) + Math.abs(e.y - p.y) === 1) return { act: 'wait', ...info }; }"],
  ['die-potions',
    "if (p.hp < p.maxHp) for (const q of s.potions) goals.add(key(q.x, q.y));",
    "if (MODE !== 'die' && p.hp < p.maxHp) for (const q of s.potions) goals.add(key(q.x, q.y));"],
  ['die-stairs',
    "if (stx) goals.add(key(stx.x, stx.y));",
    "if (stx && MODE !== 'die') goals.add(key(stx.x, stx.y));"],
  ['seed-dirs',
    "const D = [['up', 0, -1], ['down', 0, 1], ['left', -1, 0], ['right', 1, 0]];",
    "const D0 = [['up', 0, -1], ['down', 0, 1], ['left', -1, 0], ['right', 1, 0]];\n  const D = D0.slice(SEED % 4).concat(D0.slice(0, SEED % 4));"],
  ['seed-wander',
    "const start = key(p.x, p.y);",
    "if (SEED && s.turns < 1 + (SEED % 4)) { const okw = D.filter(([, dx, dy]) => free(p.x + dx, p.y + dy)); if (okw.length) return { act: okw[(SEED + s.turns) % okw.length][0], ...info }; }\n  const start = key(p.x, p.y);"],
  ['seed-fallback',
    "ok[(s.turns + p.x + p.y) % ok.length][0]",
    "ok[(s.turns + p.x + p.y + SEED) % ok.length][0]"],
  ['take-mode',
    "const tr = { changes: [], samples: [], lastPos: null, lastSig: null, stateChanges: 0, sent: 0, retries: 0, floorMax: 0, kills: 0 };",
    "await page.evaluate(([m, sd]) => { window.__recMode = m; window.__recSeed = sd; }, [take.mode || 'hunt', take.seed || 0]);\n  log(`TAKE_MODE ${name} mode=${take.mode || 'hunt'} seed=${take.seed || 0}`);\n  const tr = { changes: [], samples: [], lastPos: null, lastSig: null, stateChanges: 0, sent: 0, retries: 0, floorMax: 0, kills: 0, deaths: [] };"],
  ['death-log',
    "if (f % every === 0) await act(page, plan, tr);",
    "if (f % every === 0) { if (plan.act === 'retry') { tr.deaths.push(plan.cause || 'unknown'); log(`DEATH ${name} t=${t.toFixed(2)} floor=${plan.floor} cause=${JSON.stringify(plan.cause || 'unknown')}`); } await act(page, plan, tr); }"],
  ['death-tally',
    "log(`HERO_PATH ${name} ${tr.samples.join(' ')}`);",
    "log(`HERO_PATH ${name} ${tr.samples.join(' ')}`);\n  log(`DEATH_TALLY ${name} n=${tr.deaths.length} distinct_raw_causes=${new Set(tr.deaths).size}`);\n  st.deaths = tr.deaths;"],
];

export async function load(url, context, nextLoad) {
  const r = await nextLoad(url, context);
  if (!/\/live\/record\.mjs$/.test(url)) return r;
  let src = typeof r.source === 'string' ? r.source : new TextDecoder().decode(r.source);
  const miss = [];
  for (const [label, a, b] of P) {
    if (src.includes(a)) src = src.replace(a, () => b);
    else miss.push(label);
  }
  if (miss.length) throw new Error('PATCH6V_MISS ' + miss.join(','));
  console.log('PATCH6V ok ' + P.length + ' patches applied to live/record.mjs');
  return { format: 'module', source: src, shortCircuit: true };
}
