import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, join, extname, sep } from 'node:path';
const require = createRequire(join(process.env.PLAYWRIGHT_ROOT, 'package.json'));
const { chromium } = require('playwright');
const site = resolve(process.argv[2] || '_build/browser-lab');
const evidence = resolve('_build/browser-example-evidence');
await mkdir(evidence, { recursive: true });
const types = { '.html':'text/html', '.js':'text/javascript', '.mjs':'text/javascript', '.css':'text/css', '.json':'application/json', '.ttf':'font/ttf' };
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://localhost');
    if (!url.pathname.startsWith('/gpui-conformance/')) throw new Error('Outside test site');
    let relative = decodeURIComponent(url.pathname.slice('/gpui-conformance/'.length));
    if (!relative || relative.endsWith('/')) relative += 'index.html';
    const path = resolve(site, relative);
    if (!path.startsWith(site + sep)) throw new Error('Outside test site');
    const content = await readFile(path);
    response.writeHead(200, { 'content-type': types[extname(path)] || 'application/octet-stream' }); response.end(content);
  } catch { response.writeHead(404); response.end('Not found'); }
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
let browser;
const report = { candidate: 'failed', rust: 'not_run', comparison: 'unverified' };
try {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 }, deviceScaleFactor: 1 });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/gpui-conformance/`);
  const moon = page.frameLocator('#moon-frame');
  await moon.locator('html[data-runtime-status="ready"]').waitFor({ timeout: 30000 });
  const frame = await moon.locator('html').evaluate(() => globalThis.gpuiExample);
  assert.equal(frame.metadata.id, 'hello_world');
  assert.equal(frame.metadata.text, 'Hello, World!');
  assert.equal(frame.frame.snapshot.items.length, 8);
  assert.equal(frame.frame.conformance, 'unverified');
  const swatches = frame.frame.snapshot.items.filter(item => item.kind === 'quad' && item.id !== 1);
  assert.equal(swatches.length, 6);
  assert.equal(swatches[0].bounds.x, 134); assert.equal(swatches[0].bounds.y, 256);
  assert.equal(swatches[5].bounds.x, 334);
  assert.deepEqual(swatches.map(s => [s.color.red,s.color.green,s.color.blue]), [[255,0,0],[0,255,0],[0,0,255],[255,255,0],[0,0,0],[255,255,255]]);
  await page.screenshot({ path: join(evidence, 'hello-world-moonbit.png'), fullPage: true });
  await page.selectOption('#fixture', 'input');
  assert.equal(await page.locator('#moon-frame').isVisible(), false);
  assert.equal(await page.locator('#moon-frame').getAttribute('src'), null);
  assert.equal(await page.locator('#rust-frame').getAttribute('src'), null);
  await page.selectOption('#fixture', 'hello_world');
  await moon.locator('html[data-runtime-status="ready"]').waitFor();
  assert.deepEqual(errors, []);
  report.candidate = 'passed';
  console.log('PASS: real compiled MoonBit browser frame; missing ports clear both iframes. Rust comparison NOT RUN.');
} finally {
  await writeFile(join(evidence, 'result.json'), JSON.stringify(report, null, 2) + '\n');
  if (browser) await browser.close();
  await new Promise(done => server.close(done));
}
