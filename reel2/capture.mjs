// Reel 2 footage capture: opens the Clowder / cat-town app in Demonstration mode
// at a 1080x1920 viewport, records ~25 s to reel2/out/footage.webm and logs a
// blank-frame check (mean brightness of 3 sampled frames). Prints only what it measured.
import { chromium } from 'playwright';
import fs from 'node:fs';

const URL = process.env.APP_URL || 'http://localhost:3000/';
const SECS = Number(process.env.CAPTURE_SECS || 25);
const OUT = 'reel2/out';
const W = 1080, H = 1920;
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const ctx = await browser.newContext({
  viewport: { width: W, height: H }, deviceScaleFactor: 1,
  recordVideo: { dir: OUT, size: { width: W, height: H } },
});
const page = await ctx.newPage();
page.on('console', (m) => console.log('[page]', m.type(), m.text()));
page.on('pageerror', (e) => console.log('[pageerror]', e.message));

console.log('OPEN', URL);
await page.goto(URL, { waitUntil: 'load', timeout: 60000 });

// Enter Demonstration mode if the app shows a button for it.
let clicked = false;
for (const label of [/demonstration/i, /\bdemo\b/i]) {
  const b = page.getByRole('button', { name: label }).first();
  if (await b.count()) {
    await b.click().catch((e) => console.log('WARN demo click failed', e.message));
    console.log('DEMO_BUTTON clicked', String(label));
    clicked = true;
    break;
  }
}
if (!clicked) console.log('DEMO_BUTTON not found (app may already be in demo mode)');

const hasCanvas = await page.waitForSelector('canvas', { timeout: 60000 }).then(() => true, () => false);
console.log('CANVAS', hasCanvas ? 'found' : 'NOT FOUND');

// Record SECS seconds, taking 3 sample screenshots at 1/4, 2/4, 3/4.
const step = (SECS * 1000) / 4;
const shots = [];
for (let i = 1; i <= 3; i++) {
  await page.waitForTimeout(step);
  const p = `${OUT}/sample${i}.png`;
  await page.screenshot({ path: p });
  shots.push(p);
}
await page.waitForTimeout(step);

const video = page.video();
await ctx.close(); // flushes the webm
const raw = video ? await video.path() : null;
const dest = `${OUT}/footage.webm`;
if (raw && fs.existsSync(raw)) {
  fs.renameSync(raw, dest);
  console.log('FOOTAGE', dest, fs.statSync(dest).size, 'bytes');
} else {
  console.log('FOOTAGE MISSING');
}

// Blank-frame check in a separate, non-recording context.
const chk = await (await browser.newContext()).newPage();
let blank = 0;
for (const [i, p] of shots.entries()) {
  const b64 = fs.readFileSync(p).toString('base64');
  const mean = await chk.evaluate(async (data) => {
    const img = new Image();
    img.src = 'data:image/png;base64,' + data;
    await img.decode();
    const c = document.createElement('canvas');
    c.width = img.width; c.height = img.height;
    const g = c.getContext('2d');
    g.drawImage(img, 0, 0);
    const d = g.getImageData(0, 0, c.width, c.height).data;
    let s = 0, n = 0;
    for (let k = 0; k < d.length; k += 16) { s += 0.299 * d[k] + 0.587 * d[k + 1] + 0.114 * d[k + 2]; n++; }
    return s / n;
  }, b64);
  const isBlank = mean < 8 || mean > 247;
  if (isBlank) blank++;
  console.log(`BLANK_CHECK frame${i + 1} mean=${mean.toFixed(1)} ${isBlank ? 'BLANK' : 'ok'}`);
}
console.log(`BLANK_FRAMES=${blank}/3`);
await browser.close();
