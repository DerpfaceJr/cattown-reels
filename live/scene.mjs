// Clowder post-intro scene recorder for @clowderai Reel B "One goal, five cats". v1 (Director Clip). Not run yet.
// Usage: node live/scene.mjs live/reels/clowderB.json (the workflow serves DerpfaceJr/cat-town on :3000 first).
// Same virtual clock as live/cinema.mjs (installClock copied). The pre-roll lets any app intro play out with NO input and is not captured.
// Scripted input is limited to cfg.recorder.actions and every one is logged: CLICK <selector> ... / API <METHOD> <path> ...
// GUESS: the page picks up the demo goal (POST /api/chat {cat:'mayor',mode:'demo',goal:true}) without a reload.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const cfgPath = process.argv[2];
if (!cfgPath) { console.log('USAGE node live/scene.mjs live/reels/<reel>.json'); process.exit(2); }
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const R = cfg.recorder;
const FPS = R.fps ?? 30;
const FRAMES = R.frames ?? 360;
const BASE = 1000 / FPS;
const MAXSUB = R.maxSubStepMs ?? 33.34;
const SEG = R.steps || [];
const URL_ = cfg.app.url;
const ORIGIN = new URL(URL_).origin;
const OUT = R.framesDir;
const REEL = cfg.reel;
const outRe = new RegExp('^docs/' + REEL + '[.-]');
for (const p of Object.values(cfg.outputs)) if (!outRe.test(p)) throw new Error('output path must be docs/' + REEL + '.*: ' + p);
const REC = cfg.outputs.rec;
const G = cfg.gates || {};

fs.mkdirSync(OUT, { recursive: true });
for (const f of fs.readdirSync(OUT)) if (f.endsWith('.png')) fs.unlinkSync(path.join(OUT, f));
fs.mkdirSync(path.dirname(REC), { recursive: true });

// Frame names follow the pattern live/assemble.py reads (GUESS: a %0Nd or {i:0Nd} .png pattern), else cfg.recorder.frameName.
function frameNamer() {
  let src = '';
  try { src = fs.readFileSync('live/assemble.py', 'utf8'); } catch {}
  let how = 'assemble.py';
  let m = src.match(/([A-Za-z_-]*)%0(\d)d\.png/) || src.match(/([A-Za-z_-]*)\{[A-Za-z_]+:0(\d)d\}\.png/);
  if (!m) { how = 'config'; m = String(R.frameName || 'frame_%05d.png').match(/([A-Za-z_-]*)%0(\d)d\.png/); }
  const pre = m[1], w = +m[2];
  console.log(`FRAME_NAME ${pre}%0${w}d.png from=${how}`);
  return (i) => pre + String(i).padStart(w, '0') + '.png';
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitServer(url, ms = 120000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try { const r = await fetch(url); if (r.status < 500) return r.status; } catch {}
    await sleep(1000);
  }
  throw new Error('SERVER_TIMEOUT ' + url);
}

// ---------- runs in the page before any app script (addInitScript); same clock as cinema.mjs ----------
function installClock(o) {
  const START = Date.parse(o.startIso);
  let now = 0, nextId = 1, raf = [];
  const timers = new Map();
  const RealDate = Date;
  class VDate extends RealDate {
    constructor(...a) { if (a.length) super(...a); else super(START + now); }
    static now() { return START + now; }
  }
  window.Date = VDate;
  Object.defineProperty(performance, 'now', { value: () => now, configurable: true });
  window.setTimeout = (fn, ms = 0, ...args) => { const id = nextId++; timers.set(id, { at: now + Math.max(0, +ms || 0), fn, args, every: 0 }); return id; };
  window.setInterval = (fn, ms = 0, ...args) => { const id = nextId++; const e = Math.max(1, +ms || 0); timers.set(id, { at: now + e, fn, args, every: e }); return id; };
  window.clearTimeout = window.clearInterval = (id) => { timers.delete(id); };
  window.requestAnimationFrame = (cb) => { const id = nextId++; raf.push({ id, cb }); return id; };
  window.cancelAnimationFrame = (id) => { raf = raf.filter((r) => r.id !== id); };
  window.requestIdleCallback = (cb) => window.setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 0 }), 1);
  window.cancelIdleCallback = (id) => { timers.delete(id); };
  function fire(t) {
    try { typeof t.fn === 'function' ? t.fn(...t.args) : (0, eval)(String(t.fn)); }
    catch (e) { console.error('VCLOCK_ERR timer ' + (e && e.message)); }
  }
  function runTimers(until) {
    for (let guard = 0; guard < 20000; guard++) {
      let best = null, bid = 0;
      for (const [id, t] of timers) if (t.at <= until && (!best || t.at < best.at)) { best = t; bid = id; }
      if (!best) return;
      if (best.at > now) now = best.at;
      if (best.every) best.at += best.every; else timers.delete(bid);
      fire(best);
    }
    console.error('VCLOCK_ERR timer guard hit');
  }
  const anim0 = new WeakMap();
  function syncAnims() {
    if (!o.syncCss || !document.getAnimations) return;
    for (const a of document.getAnimations()) {
      try {
        if (!anim0.has(a)) { anim0.set(a, now - (a.currentTime || 0)); a.pause(); }
        const t = now - anim0.get(a);
        const end = a.effect && a.effect.getComputedTiming().endTime;
        if (Number.isFinite(end) && t >= end) a.finish(); else a.currentTime = t;
      } catch {}
    }
  }
  window.__step = (ms) => {
    const target = now + ms;
    runTimers(target);
    now = target;
    const q = raf; raf = [];
    for (const r of q) { try { r.cb(now); } catch (e) { console.error('VCLOCK_ERR raf ' + (e && e.message)); } }
    runTimers(now);
    syncAnims();
  };
  window.__vnow = () => now;
  const intro = { t0: null, gone: null }; window.__intro = intro;
  const watch = () => {
    const el = document.querySelector('.intro-cinema');
    if (el && intro.t0 === null) intro.t0 = now;
    else if (!el && intro.t0 !== null && intro.gone === null) intro.gone = now;
  };
  const boot = () => {
    if (!document.getElementById('__rec_css')) {
      const s = document.createElement('style'); s.id = '__rec_css'; s.textContent = o.hideCss || '';
      (document.head || document.documentElement).appendChild(s);
    }
    new MutationObserver(watch).observe(document.documentElement, { childList: true, subtree: true });
    watch();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true }); else boot();
}

// ---------- main ----------
console.log(`PLAN scene_ms=${SEG.reduce((a, s) => a + s.ms, 0)} frames=${FRAMES} out_ms=${(FRAMES * BASE).toFixed(0)} steps=${SEG.map((s) => s.name + ':' + s.ms).join(',')}`);
const nameOf = frameNamer();
const status = await waitServer(URL_);
console.log(`SERVER status=${status} url=${URL_}`);
const browser = await chromium.launch({ args: R.chromiumArgs });
const context = await browser.newContext({ viewport: R.viewport, deviceScaleFactor: R.deviceScaleFactor, serviceWorkers: 'block' });
await context.addInitScript(installClock, { startIso: R.clock.startIso, syncCss: R.syncCssAnimations !== false, hideCss: R.hideCss });
await context.addInitScript((k) => { try { localStorage.setItem(k, '1'); } catch {} }, R.setupSeenKey ?? 'clowder.setup.seen');
console.log(`SETUP_SEED key=${R.setupSeenKey ?? 'clowder.setup.seen'}`);
const page = await context.newPage();

let n403 = 0; const urls403 = [];
page.on('response', (r) => { if (r.status() === 403) { n403++; if (urls403.length < 10) urls403.push(r.request().method() + ' ' + r.url()); } });
let navs = 0;
page.on('framenavigated', (f) => { if (f === page.mainFrame() && f.url().startsWith('http')) navs++; });
const pageErrors = [];
page.on('console', (m) => { const t = m.text(); if (/VCLOCK_ERR/.test(t)) pageErrors.push(t.slice(0, 200)); });
page.on('pageerror', (e) => pageErrors.push(String(e.message).slice(0, 200)));

await page.goto(URL_, { waitUntil: 'load', timeout: 120000 });
await page.waitForLoadState('networkidle', { timeout: R.networkIdleMs ?? 20000 }).catch(() => console.log('NETWORK_IDLE timeout (continuing)'));

// Pre-roll (not captured, no input): if the intro mounts, let it run to its end; if it never mounts within introWaitMs, go on.
const realStart = Date.now();
const CAP = R.preRollCapMs ?? 30000, WAIT = R.introWaitMs ?? 4000, SETTLE = R.settleMs ?? 1500;
let pre = await page.evaluate(() => ({ t0: window.__intro.t0, gone: window.__intro.gone, now: window.__vnow() }));
while (pre.now < CAP) {
  if (pre.t0 === null && pre.now >= WAIT) break;
  if (pre.gone !== null && pre.now >= pre.gone + SETTLE) break;
  pre = await page.evaluate((dt) => { window.__step(dt); return { t0: window.__intro.t0, gone: window.__intro.gone, now: window.__vnow() }; }, BASE);
  await sleep(R.preRollRealMs ?? 20);
}
const introState = pre.t0 === null ? 'none' : (pre.gone === null ? 'still_showing' : 'played_and_closed');
console.log(`PREROLL virtual_ms=${pre.now.toFixed(0)} real_ms=${Date.now() - realStart} intro=${introState} (not captured, no input)`);

const fails = [];
if (introState === 'still_showing') fails.push('INTRO_NOT_CLOSED');
const clicks = [], api = [];
async function doAction(a, f) {
  if (a.type === 'click') {
    try {
      await page.click(a.selector, { timeout: 3000, force: true });
      clicks.push({ frame: f, selector: a.selector, ok: true });
      console.log(`CLICK ${a.selector} frame=${f} ok=yes${a.why ? ' why=' + a.why : ''}`);
    } catch (e) {
      clicks.push({ frame: f, selector: a.selector, ok: false });
      console.log(`CLICK ${a.selector} frame=${f} ok=no err=${String(e.message).split('\n')[0].slice(0, 120)}`);
      if (a.required) fails.push('CLICK ' + a.selector);
    }
  } else if (a.type === 'api') {
    const r0 = { frame: f, method: a.method || 'POST', path: a.path, body: a.body || null, status: null, bytes: null, required: !!a.required };
    api.push(r0);
    console.log(`API ${r0.method} ${a.path} frame=${f} body=${JSON.stringify(a.body || {})}`);
    r0.p = fetch(ORIGIN + a.path, { method: r0.method, headers: { 'content-type': 'application/json' }, body: a.body ? JSON.stringify(a.body) : undefined })
      .then(async (res) => { r0.status = res.status; console.log(`API_STATUS ${a.path} status=${res.status}`); try { r0.bytes = (await res.text()).length; } catch {} })
      .catch((e) => { r0.status = 'error'; console.log(`API_STATUS ${a.path} error=${String(e.message).slice(0, 120)}`); });
  }
}

const actions = (R.actions || []).map((a) => ({ ...a }));
const stepOf = (ms) => { let acc = 0; for (const s of SEG) { acc += s.ms; if (ms < acc) return s.name; } return 'after'; };
let lastStep = null, introFrames = 0, setupFrames = 0;
const setupRe = R.setupRe || '';
for (let f = 0; f < FRAMES; f++) {
  const tOut = f * BASE;
  for (const a of actions) if (!a.done && tOut >= (a.atMs ?? 0)) { a.done = true; await doAction(a, f); }
  const st = stepOf(tOut);
  if (st !== lastStep) { console.log(`STEP ${st} frame=${f} t=${(tOut / 1000).toFixed(2)}s`); lastStep = st; }
  const pr = await page.evaluate(([ms, sub, re]) => {
    let l = ms;
    while (l > 1e-6) { const d = Math.min(sub, l); window.__step(d); l -= d; }
    let setup = false;
    if (re) {
      const rx = new RegExp(re, 'i');
      for (const d of document.querySelectorAll('dialog[open],[role="dialog"],[aria-modal="true"]')) {
        if (d.getClientRects().length && rx.test(d.textContent || '')) { setup = true; break; }
      }
    }
    return { intro: !!document.querySelector('.intro-cinema'), setup };
  }, [BASE, MAXSUB, setupRe]);
  if (pr.intro) introFrames++;
  if (pr.setup) setupFrames++;
  if (R.realMsPerFrame) await sleep(R.realMsPerFrame);
  await page.screenshot({ path: path.join(OUT, nameOf(f)), type: 'png' });
}
await Promise.race([Promise.all(api.map((r) => r.p)), sleep(5000)]);

const written = fs.readdirSync(OUT).filter((f) => f.endsWith('.png')).length;
console.log(`FRAMES_WRITTEN n=${written} of ${FRAMES}`);
console.log(`INTRO_IN_CAPTURE frames=${introFrames}`);
console.log(`SETUP_DIALOG frames=${setupFrames}`);
console.log(`INPUT clicks=${clicks.length} api=${api.length}`);
if (written !== FRAMES) fails.push('FRAMES');
if (introFrames > 0) fails.push('INTRO_IN_CAPTURE');
if (setupFrames > 0) fails.push('SETUP_DIALOG');
for (const r of api) if (r.required && !(typeof r.status === 'number' && r.status >= 200 && r.status < 300)) fails.push('API ' + r.path);
if (n403 > (G.http403Max ?? 0)) fails.push('HTTP_403');
if (Math.max(0, navs - 1) > (G.reloadMax ?? 0)) fails.push('RELOAD');

const rec = {
  reel: REEL, url: URL_, frames: FRAMES, fps: FPS, recorder: 'scene.mjs',
  plan: { steps: SEG }, preRoll: { virtualMs: Math.round(pre.now), intro: introState },
  clicks, api: api.map(({ p, ...r }) => r), introFrames, setupFrames, framesWritten: written,
  http403: n403, urls403, reloads: Math.max(0, navs - 1), pageErrors: pageErrors.slice(0, 20), fails,
};
fs.writeFileSync(REC, JSON.stringify(rec, null, 2));
console.log(`HTTP_403 n=${n403}${urls403.length ? ' urls=' + urls403.join(' | ') : ''}`);
console.log(`RELOAD n=${Math.max(0, navs - 1)}`);
console.log(`PAGE_ERRORS n=${pageErrors.length}`);
console.log(`RESULT pass=${fails.length ? 'no' : 'yes'} failing=${fails.join(',') || 'none'}`);
await browser.close();
process.exit(fails.length ? 3 : 0);
