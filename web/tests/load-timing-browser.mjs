// Instrumentation tests with explicitly synthetic runtimes. Not conformance or speed evidence.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
const require = createRequire(join(process.env.PLAYWRIGHT_ROOT, 'package.json'));
const { chromium } = require('playwright');
const web = new URL('../', import.meta.url);
const requested = [];
let behavior = 'normal';
let bundled = true;
const documentPairs = new Map();
const catalog = { upstream: { repository: 'zed-industries/zed', revision: 'test' }, moonbit: { revision: 'test' }, examples: [
  { id: 'hello_world', title: 'Hello', moonbit: 'implemented', source: 'hello_world.rs', width: 500, height: 500 },
  { id: 'input', title: 'Input', moonbit: 'not_implemented', source: 'input.rs' },
] };
const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  requested.push({ path: url.pathname, run: url.searchParams.get('run') });
  res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
  res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');
  try {
    if (url.pathname === '/lab/examples.json' || url.pathname === '/lab/build-manifest.json') {
      res.setHeader('content-type', 'application/json');
      res.end(JSON.stringify(url.pathname.includes('examples') ? catalog : { rust_bundled: bundled, lab_revision: 'test' })); return;
    }
    if (/\/lab\/(moonbit|rust)\/$/.test(url.pathname)) {
      const side = url.pathname.includes('rust') ? 'rust' : 'moon';
      res.setHeader('content-type', 'text/html');
      const mode = behavior;
      if (mode === 'normal' && bundled) {
        // Neither response is released until BOTH navigation requests arrive.
        // A serialized implementation waiting for the first host would deadlock and fail.
        const run = url.searchParams.get('run');
        let pair = documentPairs.get(run);
        if (!pair) {
          let release;
          const ready = new Promise(resolve => { release = resolve; });
          pair = { count: 0, ready, release }; documentPairs.set(run, pair);
        }
        if (++pair.count === 2) pair.release();
        await pair.ready;
      }
      res.end(`<script type="module">
        import { createHostTiming } from '../load-timing.mjs';
        const timing = createHostTiming('${side}');
        globalThis.signal = () => timing.complete(['./payload.js'], 'synthetic runtime');
        if ('${mode}' === 'fail' && '${side}' === 'rust') timing.fail();
        else if ('${mode}' !== 'hang' || '${side}' !== 'rust') {
          await (await fetch('./payload.js')).text();
          await new Promise(resolve => setTimeout(resolve, 30));
          signal();
        }
      </script>`); return;
    }
    if (url.pathname.endsWith('/payload.js')) {
      res.setHeader('content-type', 'text/javascript');
      res.setHeader('cache-control', 'public, max-age=3600');
      await new Promise(resolve => setTimeout(resolve, url.pathname.includes('rust') ? 40 : 10));
      res.end('// synthetic payload only'); return;
    }
    let name = url.pathname.replace('/lab/', '') || 'index.html';
    // Bound timeout only for this failure-path fixture, not in published code.
    let content = await readFile(new URL(name, web), 'utf8');
    if (name === 'app.js') content = content.replace("output: $('load-results')", "output: $('load-results'), timeoutMs: 1000");
    res.setHeader('content-type', name.endsWith('.html') ? 'text/html' : name.endsWith('.css') ? 'text/css' : 'text/javascript');
    res.end(content);
  } catch { res.writeHead(404); res.end('missing'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
try {
  browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined });
  const page = await browser.newPage();
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/lab/`);
  const waitDone = () => page.waitForFunction(() => globalThis.gpuiLoadComparison && Object.values(gpuiLoadComparison.sides).every(side => side.status !== 'loading'));
  await waitDone();
  const first = await page.evaluate(() => gpuiLoadComparison);
  assert.deepEqual(first.launchOrder, ['rust', 'moon']);
  assert.equal(first.cache, 'normal-browser-cache-uncontrolled');
  assert.equal(first.firstPresentedFrame, 'unavailable');
  assert(first.launchSkewMs >= 0);
  for (const side of Object.values(first.sides)) {
    assert.equal(side.status, 'complete');
    assert(side.documentMs >= 0 && side.payloadMs >= side.documentMs);
    assert(side.runtimeSignalMs >= side.payloadMs + 20);
    assert(side.files.every(file => !new URL(file.url).searchParams.has('run')), 'Asset cache conditions must stay explicit');
  }
  assert.equal(requested.filter(r => r.run === first.id).length, 2);
  await page.locator('#settings button').click();
  await waitDone();
  const second = await page.evaluate(() => gpuiLoadComparison);
  assert.notEqual(second.id, first.id);
  assert.deepEqual(second.launchOrder, ['moon', 'rust']);

  // Rapid starts discard pending generations. Forged source and stale run messages are ignored.
  behavior = 'hang';
  await page.evaluate(() => {
    const form = document.getElementById('settings');
    for (let n = 0; n < 3; n++) form.dispatchEvent(new Event('submit', { cancelable: true }));
  });
  await page.waitForFunction(() => gpuiLoadComparison.sides.moon.status === 'complete');
  const pending = await page.evaluate(() => gpuiLoadComparison);
  await page.evaluate(({ old, current }) => {
    const message = { protocol: 'gpui-load-timing-v1', side: 'rust', example: current.example, status: 'failed', run: current.id };
    // The parent itself is not an allowed runtime source.
    dispatchEvent(new MessageEvent('message', { origin: location.origin, source: window, data: message }));
    const frame = document.getElementById('rust-frame');
    dispatchEvent(new MessageEvent('message', { origin: location.origin, source: frame.contentWindow, data: { ...message, run: old.id } }));
    dispatchEvent(new MessageEvent('message', { origin: 'https://other.example', source: frame.contentWindow, data: message }));
  }, { old: first, current: pending });
  assert.equal((await page.evaluate(() => gpuiLoadComparison)).sides.rust.status, 'loading');
  await waitDone();
  assert.equal((await page.evaluate(() => gpuiLoadComparison)).sides.rust.status, 'timeout');
  await page.frameLocator('#rust-frame').locator('html').evaluate(() => signal());
  assert.equal((await page.evaluate(() => gpuiLoadComparison)).sides.rust.status, 'timeout');

  behavior = 'fail';
  await page.locator('#settings button').click(); await waitDone();
  assert.equal((await page.evaluate(() => gpuiLoadComparison)).sides.rust.status, 'failed');
  await page.selectOption('#fixture', 'input');
  assert.equal(await page.evaluate(() => gpuiLoadComparison), null);
  assert.equal(await page.locator('#rust-frame').getAttribute('src'), null);
  assert.match(await page.locator('#load-results').textContent(), /Select an implemented pair/);
  behavior = 'normal';
  await page.selectOption('#fixture', 'hello_world'); await waitDone();
  assert.equal((await page.evaluate(() => gpuiLoadComparison)).sides.rust.status, 'complete');
  bundled = false;
  await page.reload(); await waitDone();
  const unpaired = await page.evaluate(() => gpuiLoadComparison);
  assert.equal(unpaired.sides.rust.status, 'unavailable');
  assert.equal(unpaired.sides.moon.status, 'complete');
  assert.deepEqual(unpaired.launchOrder, ['moon']);
  assert.equal(unpaired.launchSkewMs, null);
  assert.equal(await page.locator('#rust-frame').getAttribute('src'), null);
  assert.deepEqual(errors, []);
  console.log('PASS: synthetic load instrumentation; common clock, alternating launch, repeat/rapid reload, unavailable ports, failure/timeout, stale and spoofed signals. Not runtime performance evidence.');
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
