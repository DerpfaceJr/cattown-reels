// hooks6v.mjs - ESM load hook. Patches live/record.mjs in memory (v2):
//  - per-take mode ('hunt' default | 'die'), seed, and life counter (window.__recMode / __recSeed / __recLife)
//  - die mode (scripted input policy, disclose it): chase foes, never attack them, skip potions and stairs.
//    Once next to a foe the hero alternates: wait (the foe hits it) and sidestep (the foe follows), so it
//    keeps moving on screen and loses HP until it dies. After a death the fail screen is held for
//    take.retryHoldFrames (default 24 = 0.8 s), then #retry is clicked and the hero goes again.
//  - #over (the game's own 'You fell' panel) is lifted above the recorder backdrop so it is on camera.
//  - logs: TAKE_MODE, HP <take> t= a->b, DEATH <take> t= floor= turns= cause=, OVER_SCREEN (computed style
//    of #over at the first death), DEATH_TALLY, HP_CHANGES. status.json gets deaths + death_t per take.
// Every anchor must match exactly or the run fails (no silent partial patch).
const P = [
  ['over-cause',
    "if (s.over) return { act: 'retry', ...info };",
    "if (s.over) return { act: 'retry', cause: String((s.log || []).slice(-2).join(' / ') || 'unknown').slice(0, 120), ...info };"],
  ['die-foes',
    "if (p.hp > p.maxHp * 0.35) for (const k of foes) goals.add(k);",
    "const MODE = window.__recMode || 'hunt', SEED = window.__recSeed || 0, LIFE = window.__recLife || 0;\n  if (MODE === 'die') {\n    const adj = s.enemies.filter((e) => Math.abs(e.x - p.x) + Math.abs(e.y - p.y) === 1);\n    if (adj.length) {\n      if (s.turns % 2 === 0) return { act: 'wait', ...info };\n      const DD = [['up', 0, -1], ['down', 0, 1], ['left', -1, 0], ['right', 1, 0]];\n      const fr = DD.filter(([, dx, dy]) => { const x = p.x + dx, y = p.y + dy; return x >= 0 && y >= 0 && x < WW && y < HH && T[y][x] !== F.WALL && T[y][x] !== F.PILLAR && T[y][x] !== F.STAIRS && !foes.has(key(x, y)); });\n      return { act: fr.length ? fr[(SEED + LIFE + s.turns) % fr.length][0] : 'wait', ...info };\n    }\n  }\n  if (MODE === 'die' || p.hp > p.maxHp * 0.35) for (const k of foes) goals.add(k);"],
  ['die-potions',
    "if (p.hp < p.maxHp) for (const q of s.potions) goals.add(key(q.x, q.y));",
    "if (MODE !== 'die' && p.hp < p.maxHp) for (const q of s.potions) goals.add(key(q.x, q.y));"],
  ['die-stairs',
    "if (stx) goals.add(key(stx.x, stx.y));",
    "if (stx && MODE !== 'die') goals.add(key(stx.x, stx.y));"],
  ['seed-dirs',
    "const D = [['up', 0, -1], ['down', 0, 1], ['left', -1, 0], ['right', 1, 0]];",
    "const D0 = [['up', 0, -1], ['down', 0, 1], ['left', -1, 0], ['right', 1, 0]];\n  const D = D0.slice(SEED % 4).concat(D0.slice(0, SEED % 4));"],
  ['die-free-no-stairs',
    "const free = (x, y) => x >= 0 && y >= 0 && x < WW && y < HH && T[y][x] !== F.WALL && T[y][x] !== F.PILLAR;",
    "const free = (x, y) => x >= 0 && y >= 0 && x < WW && y < HH && T[y][x] !== F.WALL && T[y][x] !== F.PILLAR && !(MODE === 'die' && T[y][x] === F.STAIRS);"],
  ['seed-wander',
    "const start = key(p.x, p.y);",
    "if (SEED && s.turns < 1 + ((SEED + LIFE) % 4)) { const okw = D.filter(([, dx, dy]) => free(p.x + dx, p.y + dy)); if (okw.length) return { act: okw[(SEED + LIFE + s.turns) % okw.length][0], ...info }; }\n  const start = key(p.x, p.y);"],
  ['seed-fallback',
    "ok[(s.turns + p.x + p.y) % ok.length][0]",
    "ok[(s.turns + p.x + p.y + SEED + LIFE) % ok.length][0]"],
  ['stage-over',
    "image-rendering:pixelated}`;",
    "image-rendering:pixelated}\n#over:not([hidden]){display:block!important;position:fixed!important;inset:auto!important;left:140px!important;top:700px!important;width:800px!important;height:auto!important;max-height:640px!important;overflow:hidden!important;box-sizing:border-box!important;margin:0!important;transform:none!important;padding:36px 40px!important;background:rgba(12,10,16,0.86)!important;border-radius:24px!important;color:#fff!important;font:600 40px 'DejaVu Sans',sans-serif!important;text-align:center!important;z-index:2147483647!important}\n#over:not([hidden]) *{color:#fff!important;font-family:'DejaVu Sans',sans-serif!important}`;"],
  ['take-mode',
    "const tr = { changes: [], samples: [], lastPos: null, lastSig: null, stateChanges: 0, sent: 0, retries: 0, floorMax: 0, kills: 0 };",
    "await page.evaluate(([m, sd]) => { window.__recMode = m; window.__recSeed = sd; window.__recLife = 0; }, [take.mode || 'hunt', take.seed || 0]);\n  const HOLD = Math.max(1, take.retryHoldFrames ?? 24);\n  log(`TAKE_MODE ${name} mode=${take.mode || 'hunt'} seed=${take.seed || 0} retry_hold_frames=${HOLD}`);\n  const tr = { changes: [], samples: [], lastPos: null, lastSig: null, stateChanges: 0, sent: 0, retries: 0, floorMax: 0, kills: 0, deaths: [], deathT: [], overF: null, overLogged: false, lastHp: null, hpLogged: 0, hpChanges: 0 };"],
  ['death-log',
    "if (f % every === 0) await act(page, plan, tr);",
    "if (plan.act === 'retry') {\n      if (tr.overF === null) {\n        tr.overF = f; tr.deaths.push(plan.cause || 'unknown'); tr.deathT.push(+t.toFixed(3));\n        log(`DEATH ${name} t=${t.toFixed(2)} floor=${plan.floor} turns=${plan.turns} kills=${plan.kills} cause=${JSON.stringify(plan.cause || 'unknown')}`);\n        if (!tr.overLogged) { tr.overLogged = true; const ov = await page.evaluate(() => { const o = document.getElementById('over'); if (!o) return 'missing'; const r = o.getBoundingClientRect(), cs = getComputedStyle(o); return `display=${cs.display} z=${cs.zIndex} hidden=${o.hidden} rect=${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.right)},${Math.round(r.bottom)}`; }).catch((e) => 'eval failed ' + first(e)); log(`OVER_SCREEN ${name} ${ov}`); }\n      }\n      if (f - tr.overF >= HOLD) { tr.overF = null; await act(page, plan, tr); await page.evaluate(() => { window.__recLife = (window.__recLife || 0) + 1; if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); }); }\n    } else {\n      tr.overF = null;\n      if (plan.act !== 'none' && plan.hp !== tr.lastHp) { if (tr.lastHp !== null) { tr.hpChanges++; if (tr.hpLogged < 80) { tr.hpLogged++; log(`HP ${name} t=${t.toFixed(2)} ${tr.lastHp}->${plan.hp}`); } } tr.lastHp = plan.hp; }\n      if (f % every === 0) await act(page, plan, tr);\n    }"],
  ['death-tally',
    "log(`HERO_PATH ${name} ${tr.samples.join(' ')}`);",
    "log(`HERO_PATH ${name} ${tr.samples.join(' ')}`);\n  log(`DEATH_TALLY ${name} n=${tr.deaths.length} distinct_raw_causes=${new Set(tr.deaths).size} distinct_killers=${new Set(tr.deaths.map((c) => String(c).split(' / ')[0].replace(/ for \\d+\\.?$/, ''))).size} times=${tr.deathT.join(',')}`);\n  log(`HP_CHANGES ${name} n=${tr.hpChanges}`);\n  st.deaths = tr.deaths; st.death_t = tr.deathT;"],
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
  console.log('PATCH6V ok ' + P.length + ' patches applied to live/record.mjs (v2)');
  return { format: 'module', source: src, shortCircuit: true };
}
