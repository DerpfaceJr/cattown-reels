#!/usr/bin/env node
// record.mjs v3 - screen-record live Daily Tower footage driven by real keyboard input.
// usage: node live/record.mjs live/reels/<reel>.json   (repo root)
// Input facts (read from daily-tower-web js/main.js): keydown on window, e.code in
// ArrowUp/Down/Left/Right, WASD, Space=wait; #retry button restarts after death; state is module-scoped.
// harness="tower": the recorder serves main.js/render3d.js with a READ-ONLY hook appended
// (window.__dt.state, window.__dt3 camera refs) so it can path the hero and log positions.
// All moves are real Playwright key presses. The 3D camera orbit is harness-only (disclose it).
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const cfgPath = process.argv[2];
if (!cfgPath) { console.error('usage: node live/record.mjs <config.json>'); process.exit(2); }
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const RAW = 'out/raw';
const STATUS = path.join(RAW, 'status.json');
const W = 1080, H = 1920;
fs.mkdirSync(RAW, { recursive: true });
const log = (...a) => console.log(...a);
const sleep = (ms) => new Promise((r) => setTimeout(r, Math.max(0, ms)));
const DIRKEY = { up: 'ArrowUp', down: 'ArrowDown', left: 'ArrowLeft', right: 'ArrowRight' };

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
  const first = new Map([[start, null]]);
  const q = [[p.x, p.y]];
  while (q.length) {
    const [x, y] = q.shift();
    const k0 = key(x, y);
    if (k0 !== start && goals.has(k0)) return { act: first.get(k0), ...info };
    if (k0 !== start && foes.has(k0)) continue;
    for (const [n, dx, dy] of D) {
      const nx = x + dx, ny = y + dy, k = key(nx, ny);
      if (!free(nx, ny) || first.has(k)) continue;
      first.set(k, first.get(k0) ?? n);
      q.push([nx, ny]);
    }
  }
  const ok = D.filter(([, dx, dy]) => free(p.x + dx, p.y + dy));
  return { act: ok.length ? ok[(s.turns + p.x + p.y) % ok.length][0] : 'wait', ...info };
}

async function drive(page, name, t0, deadline, gapMs, st) {
  const changes = []; const samples = [];
  let lastPos = null, lastSig = null, stateChanges = 0, sent = 0, retries = 0, floorMax = 0, kills = 0;
  while (Date.now() < deadline) {
    let plan;
    try { plan = await page.evaluate(PLAN); } catch (e) { log(`PLAN_ERROR ${name} ${e.message.split('\n')[0]}`); break; }
    const t = (Date.now() - t0) / 1000;
    if (plan.act !== 'none') {
      const pos = `${plan.x},${plan.y},${plan.floor}`;
      const sig = `${pos},${plan.turns},${plan.hp}`;
      if (lastPos !== null && pos !== lastPos) {
        changes.push(+t.toFixed(3));
        if (samples.length < 12) samples.push(`${t.toFixed(2)}s:(${plan.x},${plan.y})f${plan.floor}`);
      }
      if (lastSig !== null && sig !== lastSig) stateChanges++;
      lastPos = pos; lastSig = sig;
      floorMax = Math.max(floorMax, plan.floor); kills = Math.max(kills, plan.kills);
    }
    if (plan.act === 'retry') { retries++; await page.evaluate(() => document.getElementById('retry')?.click()); }
    else if (DIRKEY[plan.act]) { await page.keyboard.press(DIRKEY[plan.act], { delay: 30 }); sent++; }
    else if (plan.act === 'wait') { await page.keyboard.press('Space', { delay: 30 }); sent++; }
    await sleep(Math.min(gapMs, deadline - Date.now()));
  }
  Object.assign(st, { changes, hero_moves: changes.length, state_changes: stateChanges, keys_sent: sent, retries, floor_max: floorMax, kills });
  log(`TAKE_STATE_CHANGES ${name} ${stateChanges} HERO_MOVES ${changes.length} KEYS_SENT ${sent} RETRIES ${retries} FLOOR_MAX ${floorMax} KILLS ${kills}`);
  log(`HERO_PATH ${name} ${samples.join(' ')}`);
}

async function startOrbit(page, speed) {
  return page.evaluate((speed) => {
    const g = window.__dt3; if (!g) return 'no_dt3';
    const c = g.renderer.domElement;
    const w = c.clientWidth, h = c.clientHeight;
    g.renderer.setSize(w, h, false); // setPixelRatio already applied: buffer = CSS size x DPR
    g.camera.aspect = w / h; g.camera.updateProjectionMatrix();
    const r = Math.hypot(g.CAM_OFFSET.x, g.CAM_OFFSET.z), y0 = g.CAM_OFFSET.y, t0 = performance.now();
    const tick = (now) => {
      const a = ((now - t0) / 1000) * speed;
      g.CAM_OFFSET.set(Math.sin(a) * r, y0, Math.cos(a) * r);
      g.camera.position.copy(g.look).add(g.CAM_OFFSET);
      g.camera.lookAt(g.look);
      g.renderer.render(g.scene, g.camera);
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    return `ok ${c.width}x${c.height}`;
  }, speed);
}

const STAGE_CSS = `#__recbg{position:fixed;inset:0;background:#0d0f14;z-index:2147483645}
#game{position:fixed!important;left:0!important;top:420px!important;width:1080px!important;height:1080px!important;max-width:none!important;max-height:none!important;margin:0!important;z-index:2147483646!important;image-rendering:pixelated}`;

async function recordTake(take) {
  const name = take.name;
  const url = take.file ? pathToFileURL(path.resolve(take.file)).href : take.url;
  const seconds = take.seconds ?? 8;
  const dir = path.join(RAW, name);
  const dst = path.join(RAW, `${name}.webm`);
  const st = { ok: false, url, seconds, lead: 0, reason: '' };
  const tower = take.harness === 'tower';
  const is3d = /3d\.html/.test(url);

  const browser = await chromium.launch({
    headless: true,
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
  const context = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, recordVideo: { dir, size: { width: W, height: H } } });
  const page = await context.newPage();
  const t0 = Date.now();
  page.on('console', (m) => { if (m.type() === 'error') log(`CONSOLE_ERROR ${name} ${m.text()}`); });
  page.on('pageerror', (e) => log(`PAGE_ERROR ${name} ${e.message}`));
  page.on('dialog', (d) => d.dismiss().catch(() => {}));

  let canvasFound = false;
  try {
    if (tower) await hookGame(page, name, st);
    await page.goto(url, { waitUntil: 'load', timeout: 30000 });
    const el = await page.waitForSelector('canvas', { state: 'visible', timeout: 20000 }).catch(() => null);
    canvasFound = !!el;
    if (!el) { st.reason = 'no canvas'; log(`CANVAS_FOUND=false ${name}`); }
    if (tower && el) {
      await page.addStyleTag({ content: STAGE_CSS });
      await page.evaluate(() => { const b = document.createElement('div'); b.id = '__recbg'; document.body.appendChild(b); });
      const ready = await page.waitForFunction(() => window.__dt && window.__dt.state, null, { timeout: 20000 }).then(() => true).catch(() => false);
      if (!ready) st.reason = 'harness hook missing (window.__dt)';
      if (ready && is3d) {
        const gl = await page.waitForFunction(() => window.__dt3 && document.getElementById('game').dataset.gl, null, { timeout: 25000 }).then(() => true).catch(() => false);
        if (!gl) st.reason = '3d renderer not ready (window.__dt3)';
        else log(`ORBIT ${name} ${await startOrbit(page, take.orbit ?? 0.35)} speed=${take.orbit ?? 0.35}rad/s (harness-only camera)`);
      }
      await sleep(400);
    }
    if (el) {
      const info = await el.evaluate((c) => ({ w: c.width, h: c.height, r: c.getBoundingClientRect().toJSON() }));
      log(`CANVAS_FOUND=true ${name} CANVAS_SIZE=${info.w}x${info.h} CSS=${Math.round(info.r.width)}x${Math.round(info.r.height)} TOP=${Math.round(info.r.y)}`);
      if (is3d && info.w < 600) st.reason ||= `3d canvas too small ${info.w}x${info.h}`;
    }
    st.lead = (Date.now() - t0) / 1000;
    if (!st.reason) {
      if (tower) await drive(page, name, t0, Date.now() + seconds * 1000, take.gapMs ?? 110, st);
      else await sleep(seconds * 1000);
    }
  } catch (e) {
    st.reason = `error: ${e.message.split('\n')[0]}`;
  }

  const video = page.video();
  await context.close();
  await browser.close();
  try {
    fs.renameSync(await video.path(), dst);
    fs.rmSync(dir, { recursive: true, force: true });
    st.bytes = fs.statSync(dst).size;
  } catch (e) {
    st.reason ||= `no video: ${e.message}`;
  }
  st.ok = canvasFound && !st.reason && st.bytes > 0;
  log(`TAKE ${name} URL ${url} FILE ${dst} BYTES ${st.bytes ?? 0} LEAD ${st.lead.toFixed(2)} HOOK main=${!!st.hook_main} 3d=${!!st.hook_3d}`);
  if (!st.ok) log(`TAKE_FAIL ${name} ${st.reason || 'unknown'}`);
  return st;
}

const status = {};
for (const take of cfg.takes) {
  try { status[take.name] = await recordTake(take); }
  catch (e) { log(`TAKE_FAIL ${take.name} crash: ${e.message}`); status[take.name] = { ok: false, reason: e.message }; }
  fs.writeFileSync(STATUS, JSON.stringify(status, null, 2));
}
log(`RECORD_DONE ok=${Object.values(status).filter((s) => s.ok).length}/${cfg.takes.length}`);
