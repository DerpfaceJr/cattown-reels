#!/usr/bin/env node
// record.mjs v2 — screen-record live game pages as real moving footage (Playwright video).
// usage: node live/record.mjs live/reels/<reel>.json        (run from repo root)
// Writes out/raw/<take>.webm per take + out/raw/status.json ({take:{ok,lead,...}}),
// which cut.sh reads to offset trims past page-load time and to apply fallback_to_scene.
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

// Default script for unknown controls: focus canvas, then cycle common game keys and
// canvas clicks every 250-400 ms so the picture keeps changing.
function defaultActions(box) {
  const keys = ['ArrowUp', 'ArrowRight', 'ArrowDown', 'ArrowLeft', 'KeyW', 'KeyA', 'KeyS', 'KeyD', 'Space', 'Enter'];
  const pts = [[0.5, 0.5], [0.3, 0.65], [0.7, 0.4], [0.5, 0.8], [0.25, 0.3], [0.75, 0.7]];
  const at = ([fx, fy]) => ({ x: Math.round(box.x + box.width * fx), y: Math.round(box.y + box.height * fy) });
  const list = [{ type: 'click', ...at([0.5, 0.5]) }];
  for (let i = 0; i < 40; i++) {
    const gapMs = 250 + ((i * 37) % 151); // deterministic 250-400 ms jitter
    list.push({ type: 'key', key: keys[i % keys.length], repeat: 1, gapMs });
    if (i % 3 === 2) list.push({ type: 'click', ...at(pts[(i / 3 | 0) % pts.length]), gapMs });
  }
  return list;
}

async function runOne(page, a, deadline) {
  const left = () => deadline - Date.now();
  switch (a.type) {
    case 'key':
      for (let i = 0; i < (a.repeat ?? 1) && left() > 0; i++) {
        if (a.holdMs) { await page.keyboard.down(a.key); await sleep(Math.min(a.holdMs, left())); await page.keyboard.up(a.key); }
        else await page.keyboard.press(a.key, { delay: 60 }); // short hold so keydown-polling games notice
        await sleep(Math.min(a.gapMs ?? 300, left()));
      }
      break;
    case 'click':
      await page.mouse.click(a.x, a.y, { delay: 40 });
      await sleep(Math.min(a.gapMs ?? 300, left()));
      break;
    case 'wait':
      await sleep(Math.min(a.ms ?? 500, left()));
      break;
    case 'mouse_sweep': { // slow held drag, e.g. OrbitControls camera orbit on the three.js page
      const [x0, y0] = a.from, [x1, y1] = a.to, steps = a.steps ?? 30;
      await page.mouse.move(x0, y0);
      await page.mouse.down({ button: a.button ?? 'left' });
      for (let i = 1; i <= steps && left() > 0; i++) {
        await page.mouse.move(x0 + ((x1 - x0) * i) / steps, y0 + ((y1 - y0) * i) / steps);
        await sleep(a.stepMs ?? 40);
      }
      await page.mouse.up({ button: a.button ?? 'left' });
      break;
    }
    default:
      log(`ACTION_UNKNOWN ${JSON.stringify(a)}`);
  }
}

// Loop the action list until the take's recording window closes.
async function runActions(page, actions, deadline) {
  while (Date.now() < deadline) {
    for (const a of actions) {
      if (Date.now() >= deadline) return;
      await runOne(page, a, deadline);
    }
  }
}

async function recordTake(take) {
  const name = take.name;
  const url = take.file ? pathToFileURL(path.resolve(take.file)).href : take.url;
  const seconds = take.seconds ?? 8;
  const dir = path.join(RAW, name);
  const dst = path.join(RAW, `${name}.webm`);
  const st = { ok: false, url, seconds, lead: 0, reason: '' };

  const browser = await chromium.launch({
    headless: true,
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
  const context = await browser.newContext({
    viewport: { width: W, height: H },
    deviceScaleFactor: 1,
    recordVideo: { dir, size: { width: W, height: H } },
  });
  const page = await context.newPage();
  const t0 = Date.now(); // video starts ~here; cut.sh skips `lead` seconds of load time
  page.on('console', (m) => { if (m.type() === 'error') log(`CONSOLE_ERROR ${name} ${m.text()}`); });
  page.on('pageerror', (e) => log(`PAGE_ERROR ${name} ${e.message}`));

  let canvasFound = false;
  try {
    await page.goto(url, { waitUntil: 'load', timeout: 30000 });
    const el = await page.waitForSelector('canvas', { state: 'visible', timeout: 20000 }).catch(() => null);
    canvasFound = !!el;
    let box = { x: 0, y: 0, width: W, height: H };
    if (el) {
      const info = await el.evaluate((c) => ({ w: c.width, h: c.height, r: c.getBoundingClientRect().toJSON() }));
      log(`CANVAS_FOUND=true ${name} CANVAS_SIZE=${info.w}x${info.h} CSS=${Math.round(info.r.width)}x${Math.round(info.r.height)}`);
      if (info.r.width > 0 && info.r.height > 0) box = info.r;
    } else {
      log(`CANVAS_FOUND=false ${name}`);
      st.reason = 'no canvas';
    }
    st.lead = (Date.now() - t0) / 1000;
    const actions = take.actions?.length ? take.actions : defaultActions(box);
    await runActions(page, actions, Date.now() + seconds * 1000);
  } catch (e) {
    st.reason = `error: ${e.message.split('\n')[0]}`;
  }

  const video = page.video();
  await context.close(); // flushes the .webm
  await browser.close();
  try {
    fs.renameSync(await video.path(), dst);
    fs.rmSync(dir, { recursive: true, force: true });
    st.bytes = fs.statSync(dst).size;
  } catch (e) {
    st.reason ||= `no video: ${e.message}`;
  }
  st.ok = canvasFound && !st.reason && st.bytes > 0;
  log(`TAKE ${name} URL ${url} FILE ${dst} BYTES ${st.bytes ?? 0} LEAD ${st.lead.toFixed(2)}`);
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
