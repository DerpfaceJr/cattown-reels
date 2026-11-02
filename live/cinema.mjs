// Cat Town intro-cinematic recorder for @clowderai Reel A "Opening night". Draft v2 (Reel Builder). Not run yet.
// Usage: node live/cinema.mjs live/reels/clowderA.json (workflow serves DerpfaceJr/cat-town first: DEMO_MODE=1 npm start on :3000).
// Steps come from timing: t0 = when div.intro-cinema mounts, then a lookup over INTRO_STEPS (open 1.2/descend 3.2/hello 3.6/ask 3.6/tour 5/outro 2 s).
// End = window CustomEvent 'cinematic' {on:false}. SKIP TRAPS: Escape, or pointerdown held 700 ms on the overlay.
// NO-INPUT RULE: no clicks, pointer events or key presses anywhere in this script.
// Self-check: INTRO_END drift = (end event - t0) - 18600 ms; out of tolerance fails the run instead of mislabeling steps.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const cfgPath = process.argv[2] || 'live/reels/clowderA.json';
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const R = cfg.recorder;
const FPS = R.fps ?? 30;
const FRAMES = R.frames ?? 450;
const BASE = 1000 / FPS;
const SEG = R.steps; // [{name, ms, speed}] in app order
const NAMES = SEG.map((s) => s.name);
const INTRO_MS = SEG.reduce((a, s) => a + s.ms, 0);
const OUT_MS = SEG.reduce((a, s) => a + s.ms / s.speed, 0);
const URL_ = cfg.app.url;
const OUT = R.framesDir;
for (const p of Object.values(cfg.outputs)) if (!/^docs\/clowderA[.-]/.test(p)) throw new Error('output path must be docs/clowderA.*: ' + p);
const REC = cfg.outputs.rec;

fs.mkdirSync(OUT, { recursive: true });
for (const f of fs.readdirSync(OUT)) if (f.endsWith('.png')) fs.unlinkSync(path.join(OUT, f));
fs.mkdirSync(path.dirname(REC), { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitServer(url, ms = 120000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try { const r = await fetch(url); if (r.status < 500) return r.status; } catch {}
    await sleep(1000);
  }
  throw new Error('SERVER_TIMEOUT ' + url);
}

// app-time ms to advance for outMs of output time, starting at app time appT (piecewise over step speeds; 1x after the intro)
function appAdvance(appT, outMs) {
  let t = appT, left = outMs, acc = 0;
  for (const s of SEG) {
    const end = acc + s.ms;
    if (t < end && left > 0) { const use = Math.min((end - t) / s.speed, left); t += use * s.speed; left -= use; }
    acc = end;
  }
  return (t - appT) + left;
}
function stepAt(appT) {
  if (appT < 0) return null;
  let acc = 0;
  for (const s of SEG) { acc += s.ms; if (appT < acc) return s.name; }
  return 'after';
}

// ---------- runs in the page before any app script (addInitScript) ----------
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
  // CSS animations and transitions follow the virtual clock too
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
  // one __step = one rAF = one town.js tick with dt = ms
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

  // Verified hooks: window CustomEvent 'cinematic' and the .intro-cinema mount/unmount
  const cam = []; window.__cam = cam;
  window.addEventListener('cinematic', (e) => {
    const d = e && e.detail;
    cam.push({ t: now, on: d && typeof d === 'object' && 'on' in d ? d.on : null });
  });
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

// ---------- per-frame probe, runs in the page (read-only, no input) ----------
function probeFn(setupRe) {
  const ov = document.querySelector('.intro-cinema');
  let skipVisible = false;
  for (const s of document.querySelectorAll('.intro-cinema .intro-skip, .intro-cinema .intro-hold')) {
    if (getComputedStyle(s).display !== 'none' && s.getClientRects().length) skipVisible = true;
  }
  let setup = false;
  if (setupRe) {
    const re = new RegExp(setupRe, 'i');
    // Verified: 'Set up Clowder' is <dialog class="setup-hub"> opened via showModal (cat-town public/setup-hub.js); this probe counts any visible dialog whose text matches setupRe.
    for (const d of document.querySelectorAll('dialog[open],[role="dialog"],[aria-modal="true"],.modal')) {
      if (d.closest('.intro-cinema')) continue;
      if (d.getClientRects().length && re.test(d.textContent || '')) { setup = true; break; }
    }
  }
  const end = window.__cam.find((c) => c.on === false);
  return {
    now: window.__vnow(), overlay: !!ov, bodyCine: document.body ? document.body.classList.contains('cinematic') : false,
    t0: window.__intro.t0, gone: window.__intro.gone, cam: window.__cam.length, endT: end ? end.t : null, skipVisible, setup,
  };
}

// ---------- main ----------
console.log(`PLAN intro_ms=${INTRO_MS} out_ms=${OUT_MS.toFixed(0)} frames_needed=${Math.ceil(OUT_MS / BASE)} frames=${FRAMES} speeds=${SEG.map((s) => s.name + ':' + s.speed).join(',')}`);
if (OUT_MS > FRAMES * BASE) { console.log('PLAN_FAIL intro does not fit in the clip'); process.exit(4); }

const status = await waitServer(URL_);
console.log(`SERVER status=${status} url=${URL_}`);
const browser = await chromium.launch({ args: R.chromiumArgs });
// Fresh context: no storageState, so storage starts empty. reducedMotion deliberately NOT set (flight mode, not cards).
const context = await browser.newContext({ viewport: R.viewport, deviceScaleFactor: R.deviceScaleFactor, serviceWorkers: 'block' });
await context.addInitScript(installClock, { startIso: R.clock.startIso, syncCss: R.syncCssAnimations !== false, hideCss: R.hideCss });
// Pre-seed the app's own flag so 'Set up Clowder' never auto-opens (cat-town public/setup-hub.js: SEEN_KEY 'clowder.setup.seen'; autoOpenOnce returns early when it is set). Storage is otherwise fresh; no input of any kind.
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
// GUESS: the Mayor model and other assets finish loading in REAL time by networkidle; the app's own wait (max 3 s) runs on the virtual clock, so a slow fetch could let it time out before the model is ready
await page.waitForLoadState('networkidle', { timeout: R.networkIdleMs ?? 20000 }).catch(() => console.log('NETWORK_IDLE timeout (continuing)'));

// Pre-roll: step the clock without capturing until .intro-cinema mounts, capped at preRollCapMs virtual.
// GUESS: DEMO_MODE=1 is not read-only (shouldPlayIntro returns false when state.readOnly, even with ?intro); INTRO_PLAYED shows it
const realStart = Date.now();
let pre = await page.evaluate(() => ({ t0: window.__intro.t0, now: window.__vnow() }));
while (pre.t0 === null && pre.now < R.preRollCapMs) {
  pre = await page.evaluate((dt) => { window.__step(dt); return { t0: window.__intro.t0, now: window.__vnow() }; }, BASE);
  await sleep(R.preRollRealMs ?? 25); // let real network/decoding catch up between virtual steps
}
console.log(`PREROLL virtual_ms=${pre.now.toFixed(0)} real_ms=${Date.now() - realStart} t0=${pre.t0 === null ? 'none' : pre.t0.toFixed(0)}`);
console.log(`INTRO_PLAYED ${pre.t0 === null ? 'no' : 'yes'}`);

const rec = { reel: cfg.reel, url: URL_, frames: FRAMES, fps: FPS, plan: { introMs: INTRO_MS, outMs: Math.round(OUT_MS), steps: SEG } };
function finish(fails, extra) {
  Object.assign(rec, extra, { http403: n403, urls403, reloads: Math.max(0, navs - 1), pageErrors: pageErrors.slice(0, 20), fails });
  fs.writeFileSync(REC, JSON.stringify(rec, null, 2));
  console.log(`HTTP_403 n=${n403}${urls403.length ? ' urls=' + urls403.join(' | ') : ''}`);
  console.log(`RELOAD n=${Math.max(0, navs - 1)}`);
  console.log(`PAGE_ERRORS n=${pageErrors.length}`);
  console.log(`RESULT pass=${fails.length ? 'no' : 'yes'} failing=${fails.join(',') || 'none'}`);
}
if (pre.t0 === null) {
  finish(['INTRO_PLAYED'], { introPlayed: false });
  await browser.close();
  process.exit(3);
}

const G = cfg.gates || {};
// GUESS: town.js clamps tick dt at or above 33.3 ms, so sub-steps of maxSubStepMs are not cut; INTRO_DRIFT catches it if wrong
const MAXSUB = R.maxSubStepMs ?? 33.34;
const TOL = R.endDriftTolMs ?? 150;
const t0 = pre.t0;
const seen = new Map();
let endFrame = null, endT = null, skipFrames = 0, setupFrames = 0;

// Capture loop: probe (read-only), screenshot, then advance the virtual clock. No input of any kind.
for (let i = 0; i < FRAMES; i++) {
  const p = await page.evaluate(probeFn, R.setupRe || '');
  const appT = p.now - t0;
  const name = stepAt(appT);
  if (name && NAMES.includes(name) && !seen.has(name)) { seen.set(name, i); console.log(`STEP ${name} frame=${i} app_ms=${appT.toFixed(0)}`); }
  if (p.skipVisible) skipFrames++;
  if (p.setup) setupFrames++;
  if (endFrame === null && p.endT !== null) { endFrame = i; endT = p.endT; }
  await page.screenshot({ path: path.join(OUT, String(i + 1).padStart(5, '0') + '.png') });
  // sped-up steps advance more app time per output frame; split into sub-steps so each tick's dt stays <= MAXSUB
  const adv = appAdvance(appT, BASE);
  const n = Math.max(1, Math.ceil(adv / MAXSUB - 1e-9));
  await page.evaluate(([d, k]) => { for (let j = 0; j < k; j++) window.__step(d); }, [adv / n, n]);
}

const fin = await page.evaluate(() => ({ cam: window.__cam.length, gone: window.__intro.gone, now: window.__vnow() }));
const missing = NAMES.filter((s) => !seen.has(s));
// GUESS: the intro's own clock starts on the tick after .intro-cinema mounts (adds up to ~1 tick of drift, inside TOL)
const drift = endT === null ? null : (endT - t0) - INTRO_MS;
const nPng = fs.readdirSync(OUT).filter((f) => f.endsWith('.png')).length;
console.log(`CINEMATIC seen=${NAMES.filter((s) => seen.has(s)).join(',')}${missing.length ? ' missing=' + missing.join(',') : ''}`);
console.log(`CAM_EVENTS n=${fin.cam}`);
console.log(`INTRO_END frame=${endFrame === null ? 'none' : endFrame} drift_ms=${drift === null ? 'na' : drift.toFixed(0)}`);
console.log(`SKIP_VISIBLE frames=${skipFrames}`);
console.log(`SETUP_WINDOW frames=${setupFrames}`);
console.log(`FRAMES n=${nPng}`);

const fails = [];
if (n403 > (G.http403Max ?? 0)) fails.push('HTTP_403');
if (missing.length) fails.push('CINEMATIC');
if (Math.max(0, navs - 1) > (G.reloadMax ?? 0)) fails.push('RELOAD');
if (fin.cam < (G.camEventsMin ?? 1)) fails.push('CAM_EVENTS');
if (endFrame === null || endFrame >= (G.introEndByFrame ?? FRAMES)) fails.push('INTRO_END');
if (drift !== null && Math.abs(drift) > TOL) fails.push('INTRO_DRIFT');
if (skipFrames) fails.push('SKIP_VISIBLE');
if (setupFrames) fails.push('SETUP_WINDOW');
if (nPng !== FRAMES) fails.push('FRAMES');

finish(fails, { introPlayed: true, t0, stepFrames: Object.fromEntries(seen), endFrame, driftMs: drift, camEvents: fin.cam, introGone: fin.gone, skipFrames, setupFrames, framesWritten: nPng });
await browser.close();
process.exit(fails.length ? 2 : 0);
