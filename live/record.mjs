#!/usr/bin/env node
// record.mjs v6 - capture live Daily Tower footage FRAME BY FRAME on a virtual clock.
// usage: node live/record.mjs live/reels/<reel>.json   (repo root)
// Input facts (read from daily-tower-web js/main.js): keydown on window, e.code in
// ArrowUp/Down/Left/Right, WASD, Space=wait; #retry button restarts after death; state is module-scoped.
// harness="tower": the recorder serves main.js/render3d.js with a READ-ONLY hook appended
// (window.__dt.state, window.__dt3 camera refs) so it can path the hero and log positions.
// v6 (why): SwiftShader draws a 1080x1080 three.js frame only ~4x/s, so real-time recordVideo
// repeated each drawn frame ~8x (choppy, near-zero diffs). Now an init script owns time:
// performance.now / Date.now / requestAnimationFrame are virtual. Each captured frame advances the
// clock exactly 1/30 s, flushes the game's rAF callbacks, renders ONCE (game render calls are
// suppressed, the harness draws after setting the orbit camera), then page.screenshot grabs the
// 1080x1920 viewport. ffmpeg assembles the JPEGs at 30 fps. Game speed and orbit are smooth no matter
// how slow SwiftShader is. All moves are real Playwright key presses, sent every `inputEvery` frames.
// The 3D camera orbit and camScale are harness-only (disclose them in the caption).
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const cfgPath = process.argv[2];
if (!cfgPath) { console.error('usage: node live/record.mjs <config.json>'); process.exit(2); }
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const RAW = 'out/raw';
const STATUS = path.join(RAW, 'status.json');
const W = 1080, H = 1920, FPS = 30, DT = 1000 / FPS;
fs.mkdirSync(RAW, { recursive: true });
const log = (...a) => console.log(...a);
const sleep = (ms) => new Promise((r) => setTimeout(r, Math.max(0, ms)));
const DIRKEY = { up: 'ArrowUp', down: 'ArrowDown', left: 'ArrowLeft', right: 'ArrowRight' };
const first = (e) => String(e && e.message ? e.message : e).split('\n')[0];

// Virtual clock. Real time (auto-pumped rAF) until the first __vstep, then fully manual.
const VCLOCK = `(() => {
  if (window.__vstep) return;
  const rp = performance.now.bind(performance), rd = Date.now.bind(Date), rRAF = window.requestAnimationFrame.bind(window);
  const d0 = rd() - rp();
  let manual = false, vt = 0, q = [], id = 0;
  performance.now = () => (manual ? vt : rp());
  Date.now = () => (manual ? Math.floor(d0 + vt) : rd());
  window.requestAnimationFrame = (cb) => { const i = ++id; q.push([i, cb]); return i; };
  window.cancelAnimationFrame = (i) => { q = q.filter((e) => e[0] !== i); };
  const flush = (t) => { const cur = q; q = []; for (const e of cur) { try { e[1](t); } catch (err) { window.__recErr = String(err); } } };
  const pump = () => { if (!manual) flush(rp()); rRAF(pump); };
  rRAF(pump);
  window.__vstep = (ms) => {
    if (!manual) { manual = true; vt = rp(); }
    vt += ms; flush(vt);
    if (window.__orbitTick) window.__orbitTick(vt);
    return vt;
  };
})();`;

async function hookGame(page, name, st) {
  await page.route(/\/js\/main\.js(\?.*)?$/, async (route) => {
    const resp = await route.fetch();
    let body = await resp.text();
    body = "import * as __F from './floors.js';\n" + body + '\n;window.__dt={get state(){return state;},F:__F};\n';
    st.hook_main = true;
    await route.fulfill({ status: resp.status(), contentType: 'application/javascript', body });
  });
  await page.route(/\/js\/render3d\.js(\?.*)?$/, async (route) => {
    const resp = await route.fetch();
    let body = await resp.text();
    const anchor = 'return function paint(s) {';
    if (body.includes(anchor)) { body = body.replace(anchor, 'window.__dt3={renderer,scene,camera,look,CAM_OFFSET};\n  ' + anchor); st.hook_3d = true; }
    else log(`HOOK3D_ANCHOR_MISSING ${name}`);
    await route.fulfill({ status: resp.status(), contentType: 'application/javascript', body });
  });
}

// Runs in the page: BFS from the hero to the nearest enemy (if HP ok), potion (if hurt) or stairs.
function PLAN() {
  const d = window.__dt; const s = d && d.state;
  if (!s) return { act: 'none' };
  const p = s.player;
  const info = { x: p.x, y: p.y, hp: p.hp, floor: s.floor, turns: s.turns, kills: s.kills };
  if (s.over) return { act: 'retry', ...info };
  const F = d.F, T = s.tiles, HH = T.length, WW = T[0].length;
  const key = (x, y) => y * WW + x;
  const foes = new Set(s.enemies.map((e) => key(e.x, e.y)));
  const goals = new Set();
  if (p.hp > p.maxHp * 0.35) for (const k of foes) goals.add(k);
  if (p.hp < p.maxHp) for (const q of s.potions) goals.add(key(q.x, q.y));
  let stx = s.stairs;
  if (!stx) for (let y = 0; y < HH; y++) for (let x = 0; x < WW; x++) if (T[y][x] === F.STAIRS) stx = { x, y };
  if (stx) goals.add(key(stx.x, stx.y));
  const D = [['up', 0, -1], ['down', 0, 1], ['left', -1, 0], ['right', 1, 0]];
  const free = (x, y) => x >= 0 && y >= 0 && x < WW && y < HH && T[y][x] !== F.WALL && T[y][x] !== F.PILLAR;
  const start = key(p.x, p.y);
  const firstStep = new Map([[start, null]]);
  const q = [[p.x, p.y]];
  while (q.length) {
    const [x, y] = q.shift();
    const k0 = key(x, y);
    if (k0 !== start && goals.has(k0)) return { act: firstStep.get(k0), ...info };
    if (k0 !== start && foes.has(k0)) continue;
    for (const [n, dx, dy] of D) {
      const nx = x + dx, ny = y + dy, k = key(nx, ny);
      if (!free(nx, ny) || firstStep.has(k)) continue;
      firstStep.set(k, firstStep.get(k0) ?? n);
      q.push([nx, ny]);
    }
  }
  const ok = D.filter(([, dx, dy]) => free(p.x + dx, p.y + dy));
  return { act: ok.length ? ok[(s.turns + p.x + p.y) % ok.length][0] : 'wait', ...info };
}

function track(tr, plan, t) {
  if (plan.act === 'none') return;
  const pos = `${plan.x},${plan.y},${plan.floor}`;
  const sig = `${pos},${plan.turns},${plan.hp}`;
  if (tr.lastPos !== null && pos !== tr.lastPos) {
    tr.changes.push(+t.toFixed(3));
    if (tr.samples.length < 12) tr.samples.push(`${t.toFixed(2)}s:(${plan.x},${plan.y})f${plan.floor}`);
  }
  if (tr.lastSig !== null && sig !== tr.lastSig) tr.stateChanges++;
  tr.lastPos = pos; tr.lastSig = sig;
  tr.floorMax = Math.max(tr.floorMax, plan.floor || 0); tr.kills = Math.max(tr.kills, plan.kills || 0);
}

async function act(page, plan, tr) {
  if (plan.act === 'retry') { tr.retries++; await page.evaluate(() => document.getElementById('retry')?.click()); }
  else if (DIRKEY[plan.act]) { await page.keyboard.press(DIRKEY[plan.act]); tr.sent++; }
  else if (plan.act === 'wait') { await page.keyboard.press('Space'); tr.sent++; }
}

// Harness-only camera: size the drawing buffer (renderPx, else CSS size), pull the camera closer
// (scale < 1) and orbit around the hero at `speed` rad/s of VIRTUAL time. The game's own
// renderer.render calls are suppressed (counted); the harness draws exactly once per __vstep.
async function startOrbit(page, speed, scale, px) {
  return page.evaluate(({ speed, scale, px }) => {
    const g = window.__dt3; if (!g) return 'no_dt3';
    const c = g.renderer.domElement;
    const w = c.clientWidth, h = c.clientHeight;
    g.renderer.setPixelRatio(1);
    g.renderer.setSize(px || w, px ? Math.round((px * h) / w) : h, false);
    g.camera.aspect = w / h; g.camera.updateProjectionMatrix();
    const r = Math.hypot(g.CAM_OFFSET.x, g.CAM_OFFSET.z) * scale, y0 = g.CAM_OFFSET.y * scale;
    const draw = g.renderer.render.bind(g.renderer);
    window.__gameRenders = 0; window.__recFrames = 0;
    g.renderer.render = () => { window.__gameRenders++; };
    let t0 = null;
    window.__orbitTick = (now) => {
      if (t0 === null) t0 = now;
      const a = ((now - t0) / 1000) * speed;
      g.CAM_OFFSET.set(Math.sin(a) * r, y0, Math.cos(a) * r);
      g.camera.position.copy(g.look).add(g.CAM_OFFSET);
      g.camera.lookAt(g.look);
      try { draw(g.scene, g.camera); window.__recFrames++; } catch (e) { window.__recErr = String(e); }
    };
    return `ok buffer=${c.width}x${c.height} css=${w}x${h} r=${r.toFixed(2)} y=${y0.toFixed(2)} render=once_per_captured_frame`;
  }, { speed, scale, px });
}

// Frame-by-frame capture: plan -> (key every `inputEvery` frames) -> advance clock 1/30 s + render once -> screenshot.
async function capture(page, name, take, st, dir) {
  const total = Math.round((take.seconds ?? 8) * FPS);
  const every = Math.max(1, take.inputEvery ?? 3);
  const budget = (take.maxWallSec ?? 600) * 1000;
  const quality = take.jpegQuality ?? 92;
  const tr = { changes: [], samples: [], lastPos: null, lastSig: null, stateChanges: 0, sent: 0, retries: 0, floorMax: 0, kills: 0 };
  fs.mkdirSync(dir, { recursive: true });
  const w0 = Date.now();
  let n = 0, vt0 = null, vt1 = null;
  for (let f = 0; f < total; f++) {
    const t = f / FPS;
    let plan;
    try { plan = await page.evaluate(PLAN); } catch (e) { st.reason = `plan error: ${first(e)}`; break; }
    track(tr, plan, t);
    if (f % every === 0) await act(page, plan, tr);
    let vt;
    try { vt = await page.evaluate((ms) => window.__vstep(ms), DT); } catch (e) { st.reason = `vstep error: ${first(e)}`; break; }
    if (vt0 === null) vt0 = vt; vt1 = vt;
    await page.screenshot({ path: path.join(dir, `f${String(f).padStart(5, '0')}.jpg`), type: 'jpeg', quality });
    n++;
    if (Date.now() - w0 > budget) { st.reason = `capture over wall budget ${budget / 1000}s at frame ${f + 1}/${total}`; break; }
  }
  const wall = (Date.now() - w0) / 1000;
  const msf = Math.round((wall * 1000) / Math.max(1, n));
  const r = await page.evaluate(() => ({ h: window.__recFrames || 0, g: window.__gameRenders || 0, e: window.__recErr || '' })).catch(() => ({ h: -1, g: -1, e: 'eval failed' }));
  const vspan = vt0 === null ? 0 : (vt1 - vt0 + DT) / 1000;
  log(`CAPTURE_FRAMES ${name} ${n}/${total} wall=${wall.toFixed(1)}s ms_per_frame=${msf} virtual_s=${vspan.toFixed(3)} input_every=${every}f harness_renders=${r.h} game_render_calls_suppressed=${r.g}${r.e ? ' RENDER_ERR ' + r.e : ''}`);
  if (n < total) st.reason ||= `short capture ${n}/${total}`;
  Object.assign(st, { changes: tr.changes, hero_moves: tr.changes.length, state_changes: tr.stateChanges, keys_sent: tr.sent, retries: tr.retries, floor_max: tr.floorMax, kills: tr.kills });
  st.capture = { frames: n, total, wall_s: +wall.toFixed(1), ms_per_frame: msf, harness_renders: r.h, virtual_s: +vspan.toFixed(3) };
  log(`TAKE_STATE_CHANGES ${name} ${tr.stateChanges} HERO_MOVES ${tr.changes.length} KEYS_SENT ${tr.sent} RETRIES ${tr.retries} FLOOR_MAX ${tr.floorMax} KILLS ${tr.kills}`);
  log(`HERO_PATH ${name} ${tr.samples.join(' ')}`);
  return n;
}

function encode(dir, out) {
  const r = spawnSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-framerate', String(FPS), '-i', path.join(dir, 'f%05d.jpg'),
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '14', '-pix_fmt', 'yuv420p', '-r', String(FPS), out], { encoding: 'utf8' });
  if (r.status !== 0) return `ffmpeg failed: ${String(r.stderr || r.error || 'unknown').split('\n')[0]}`;
  return '';
}

const STAGE_CSS = `#__recbg{position:fixed;inset:0;background:#0d0f14;z-index:2147483645}
#game{position:fixed!important;left:0!important;top:420px!important;width:1080px!important;height:1080px!important;max-width:none!important;max-height:none!important;margin:0!important;z-index:2147483646!important;image-rendering:pixelated}`;

async function recordTake(take) {
  const name = take.name;
  const url = take.file ? pathToFileURL(path.resolve(take.file)).href : take.url;
  const seconds = take.seconds ?? 8;
  const tower = take.harness === 'tower';
  const is3d = /3d\.html/.test(url);
  const frameMode = tower;
  const dir = path.join(RAW, name);
  const dst = path.join(RAW, frameMode ? `${name}.mp4` : `${name}.webm`);
  const st = { ok: false, url, seconds, lead: 0, reason: '', mode: frameMode ? 'frames' : 'realtime' };

  const browser = await chromium.launch({
    headless: true,
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
  const ctxOpts = { viewport: { width: W, height: H }, deviceScaleFactor: 1 };
  if (!frameMode) ctxOpts.recordVideo = { dir, size: { width: W, height: H } };
  const context = await browser.newContext(ctxOpts);
  if (frameMode) await context.addInitScript(VCLOCK);
  const page = await context.newPage();
  const t0 = Date.now();
  page.on('console', (m) => { if (m.type() === 'error') log(`CONSOLE_ERROR ${name} ${m.text()}`); });
  page.on('pageerror', (e) => log(`PAGE_ERROR ${name} ${e.message}`));
  page.on('dialog', (d) => d.dismiss().catch(() => {}));

  let canvasFound = false, n = 0;
  try {
    if (tower) await hookGame(page, name, st);
    await page.goto(url, { waitUntil: 'load', timeout: 30000 });
    const el = await page.waitForSelector('canvas', { state: 'visible', timeout: 20000 }).catch(() => null);
    canvasFound = !!el;
    if (!el) { st.reason = 'no canvas'; log(`CANVAS_FOUND=false ${name}`); }
    if (tower && el) {
      await page.addStyleTag({ content: STAGE_CSS });
      await page.evaluate(() => { const b = document.createElement('div'); b.id = '__recbg'; document.body.appendChild(b); });
      const ready = await page.waitForFunction(() => window.__dt && window.__dt.state && window.__vstep, null, { timeout: 20000 }).then(() => true).catch(() => false);
      if (!ready) st.reason = 'harness hook or virtual clock missing (window.__dt / __vstep)';
      if (ready && is3d) {
        const gl = await page.waitForFunction(() => window.__dt3 && document.getElementById('game').dataset.gl, null, { timeout: 25000 }).then(() => true).catch(() => false);
        if (!gl) st.reason = '3d renderer not ready (window.__dt3)';
        else {
          const sp = take.orbit ?? 0.5, sc = take.camScale ?? 1, px = take.renderPx ?? 0;
          log(`ORBIT ${name} ${await startOrbit(page, sp, sc, px)} speed=${sp}rad/s(virtual) camScale=${sc} renderPx=${px || 'css'} (harness-only camera)`);
        }
      }
      await sleep(200);
    }
    if (el) {
      const info = await el.evaluate((c) => ({ w: c.width, h: c.height, r: c.getBoundingClientRect().toJSON() }));
      log(`CANVAS_FOUND=true ${name} CANVAS_SIZE=${info.w}x${info.h} CSS=${Math.round(info.r.width)}x${Math.round(info.r.height)} TOP=${Math.round(info.r.y)}`);
      if (is3d && info.w < 600 && !take.renderPx) st.reason ||= `3d canvas too small ${info.w}x${info.h}`;
    }
    if (!st.reason && frameMode) {
      st.lead = 0; // footage time 0 = first captured frame
      n = await capture(page, name, take, st, dir);
    } else if (!st.reason) {
      st.lead = (Date.now() - t0) / 1000;
      await sleep(seconds * 1000);
    }
  } catch (e) {
    st.reason ||= `error: ${first(e)}`;
  }

  const video = frameMode ? null : page.video();
  await context.close().catch(() => {});
  await browser.close().catch(() => {});
  try {
    if (frameMode) {
      if (n > 0) { const err = encode(dir, dst); if (err) st.reason ||= err; }
      fs.rmSync(dir, { recursive: true, force: true });
    } else {
      fs.renameSync(await video.path(), dst);
      fs.rmSync(dir, { recursive: true, force: true });
    }
    st.bytes = fs.existsSync(dst) ? fs.statSync(dst).size : 0;
  } catch (e) {
    st.reason ||= `no video: ${first(e)}`;
  }
  st.ok = canvasFound && !st.reason && (st.bytes || 0) > 0;
  log(`TAKE ${name} MODE ${st.mode} URL ${url} FILE ${dst} BYTES ${st.bytes ?? 0} LEAD ${st.lead.toFixed(2)} HOOK main=${!!st.hook_main} 3d=${!!st.hook_3d}`);
  if (st.ok) log(`TAKE_OK ${name}`); else log(`TAKE_FAIL ${name} ${st.reason || 'unknown'}`);
  return st;
}

const status = {};
for (const take of cfg.takes) {
  try { status[take.name] = await recordTake(take); }
  catch (e) { status[take.name] = { ok: false, lead: 0, reason: `crash: ${first(e)}` }; log(`TAKE_FAIL ${take.name} crash ${first(e)}`); }
  fs.writeFileSync(STATUS, JSON.stringify(status, null, 2));
}
const okN = Object.values(status).filter((s) => s.ok).length;
log(`TAKES ${okN}/${cfg.takes.length} ok`);
process.exit(okN ? 0 : 1);
