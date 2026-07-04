/**
 * Real-browser smoke driver (no Playwright): serve web/ over HTTP, run the
 * smoke page in headless Chrome, decode the result and assert.
 *
 *   node web/runtime/scripts/browser-smoke/run.mjs
 *
 * Lives outside test/ so `node --test` never imports it. Skips cleanly (exit 0)
 * if Chrome isn't installed. JSXGraph is vendored into ./vendor on first run
 * (downloaded from the pinned CDN); the vendor dir is gitignored.
 */
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = join(here, '..', '..', '..'); // .../web
const vendor = join(here, 'vendor');
const PORT = Number(process.env.SMOKE_PORT || 8123);
const VERSION = '1.10.1';

const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
].filter(Boolean);

function findChrome() {
  return CHROME_CANDIDATES.find((p) => existsSync(p));
}

async function ensureVendor() {
  mkdirSync(vendor, { recursive: true });
  const files = {
    'jsxgraphcore.js': `https://cdn.jsdelivr.net/npm/jsxgraph@${VERSION}/distrib/jsxgraphcore.js`,
    'jsxgraph.css': `https://cdn.jsdelivr.net/npm/jsxgraph@${VERSION}/distrib/jsxgraph.css`,
  };
  for (const [name, url] of Object.entries(files)) {
    const dest = join(vendor, name);
    if (existsSync(dest)) continue;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`download failed (${res.status}): ${url}`);
    writeFileSync(dest, Buffer.from(await res.arrayBuffer()));
  }
}

async function waitForServer(url, timeoutMs) {
  const t0 = Date.now();
  for (;;) {
    try {
      const r = await fetch(url);
      if (r.ok || r.status === 404) return; // server is up
    } catch {
      /* not yet */
    }
    if (Date.now() - t0 > timeoutMs) throw new Error('server did not start: ' + url);
    await new Promise((r) => setTimeout(r, 100));
  }
}

async function main() {
  const chrome = findChrome();
  if (!chrome) {
    console.log('SKIP: no Chrome/Chromium found (set CHROME_PATH to run).');
    process.exit(0);
  }
  await ensureVendor();

  const server = spawn('python3', ['-m', 'http.server', String(PORT)], {
    cwd: webRoot,
    stdio: 'ignore',
  });
  const wantShot = process.argv.includes('--screenshot');
  let result;
  try {
    await waitForServer(`http://localhost:${PORT}/`, 8000);
    // --fixture NAME runs a different committed fixture (default ex_general).
    const fi = process.argv.indexOf('--fixture');
    const fixture = fi !== -1 ? process.argv[fi + 1] : '';
    const base = `http://localhost:${PORT}/runtime/scripts/browser-smoke/smoke.html`;
    const url = fixture ? `${base}?fixture=${encodeURIComponent(fixture)}` : base;

    // Optional: capture a PNG for visual inspection / a future visual-regression
    // baseline. (A strict pixel diff vs the Cairo SVG would be flaky — different
    // text/AA engines — so this is for eyeballing, not an automated equality.)
    if (wantShot) {
      const shot = join(here, 'screenshot.png');
      spawnSync(
        chrome,
        [
          '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
          '--disable-extensions', '--force-device-scale-factor=1',
          '--virtual-time-budget=15000', '--run-all-compositor-stages-before-draw',
          '--window-size=620,440', `--screenshot=${shot}`, url,
        ],
        { encoding: 'utf8', timeout: 60000 },
      );
      if (existsSync(shot)) console.log('screenshot:', shot);
      else console.log('screenshot: (not produced)');
    }

    const r = spawnSync(
      chrome,
      [
        '--headless=new',
        '--disable-gpu',
        '--no-sandbox',
        '--no-first-run',
        '--disable-extensions',
        '--virtual-time-budget=15000',
        '--run-all-compositor-stages-before-draw',
        '--dump-dom',
        url,
      ],
      { encoding: 'utf8', timeout: 60000 },
    );
    const dom = r.stdout || '';
    const m = dom.match(/RESULT_START([A-Za-z0-9+/=]*)RESULT_END/);
    if (!m) {
      console.error('No result marker in DOM. First 800 chars:\n' + dom.slice(0, 800));
      if (r.stderr) console.error('stderr:\n' + r.stderr.slice(0, 800));
      throw new Error('smoke page produced no result');
    }
    result = JSON.parse(Buffer.from(m[1], 'base64').toString('utf8'));
  } finally {
    server.kill();
  }

  for (const c of result.checks) {
    console.log(`${c.pass ? 'PASS' : 'FAIL'}  ${c.name}${c.info ? ` (${c.info})` : ''}`);
  }
  if (result.errors.length) console.log('errors:', result.errors);
  console.log(result.ok ? '\nOK — runtime drives live JSXGraph' : '\nFAILED');
  process.exit(result.ok ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
