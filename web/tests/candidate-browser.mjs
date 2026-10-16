import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, join, extname, sep } from 'node:path';
const require = createRequire(join(process.env.PLAYWRIGHT_ROOT, 'package.json'));
const { chromium } = require('playwright');
const site = resolve(process.argv[2] || '_build/browser-lab');
const evidence = resolve(process.env.BROWSER_EVIDENCE || '_build/browser-example-evidence');
const required = process.argv.includes('--require-rust');
const manifest = JSON.parse(await readFile(join(site, 'build-manifest.json'), 'utf8'));
const paired = Boolean(manifest.rust_bundled);
await mkdir(evidence, { recursive: true });
const types = { '.html':'text/html', '.js':'text/javascript', '.mjs':'text/javascript', '.css':'text/css', '.json':'application/json', '.ttf':'font/ttf', '.wasm':'application/wasm' };
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://localhost');
    if (!url.pathname.startsWith('/gpui-conformance/')) throw new Error('Outside test site');
    let relative = decodeURIComponent(url.pathname.slice('/gpui-conformance/'.length));
    if (!relative || relative.endsWith('/')) relative += 'index.html';
    const path = resolve(site, relative);
    if (!path.startsWith(site + sep)) throw new Error('Outside test site');
    const content = await readFile(path);
    response.writeHead(200, { 'content-type': types[extname(path)] || 'application/octet-stream', 'Cross-Origin-Opener-Policy':'same-origin', 'Cross-Origin-Embedder-Policy':'require-corp', 'Cross-Origin-Resource-Policy':'same-origin' }); response.end(content);
  } catch { response.writeHead(404); response.end('Not found'); }
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
let browser;
const report = { overall: 'failed', candidate: 'failed', rust: 'not_run', comparison: 'unverified', verified: [], unverified: ['native parity', 'text shaping and rasterization', 'application event handling', 'IME and interactive examples'], operations: [], errors: [], console: [], requests: [] };
report.build = manifest;
report.environment = {platform: process.platform, arch: process.arch, node: process.version, graphics: 'Chromium with SwiftShader requested; raw backend logs retained'};
let page;
try {
  assert(!required || paired, 'Required Rust bundle is missing');
  browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  report.environment.browser = await browser.version();
  page = await browser.newPage({ viewport: { width: 1400, height: 950 }, deviceScaleFactor: 1 });
  const errors = report.errors; page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => report.console.push({type: message.type(), text: message.text()}));
  page.on('response', response => report.requests.push({url: response.url(), status: response.status()}));
  await page.addInitScript(() => {
    globalThis.browserEvents = [];
    for (const type of ['pointerdown', 'pointerup', 'click', 'keydown', 'keyup']) {
      addEventListener(type, event => globalThis.browserEvents.push({type, key: event.key, x: event.clientX, y: event.clientY, trusted: event.isTrusted, target: event.target.tagName, time: performance.now()}), true);
    }
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/gpui-conformance/`);
  async function waitForNewDocuments() {
    await page.waitForFunction(paired => ['moon', ...(paired ? ['rust'] : [])].every(side => {
      const iframe = document.getElementById(side + '-frame');
      try {
        return iframe.contentWindow.location.href === iframe.src &&
          iframe.contentDocument.documentElement.dataset.runtimeStatus === (side === 'moon' ? 'ready' : 'initialized');
      } catch { return false; }
    }), paired, {timeout:60000});
  }
  await waitForNewDocuments();
  assert.match(manifest.lab_revision, /^[0-9a-f]{40}$/);
  assert.equal(await page.locator('#moon-source').getAttribute('href'),
    `https://github.com/gpui-mbt/gpui-conformance/blob/${manifest.lab_revision}/web/moonbit/hello_world/hello_world.mbt`);
  assert.equal(typeof manifest.lab_tracked_dirty, 'boolean');
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
  assert.deepEqual(swatches.map(s => [s.color.red,s.color.green,s.color.blue]), [[255,0,0],[0,128,0],[0,0,255],[255,255,0],[0,0,0],[255,255,255]]);
  await writeFile(join(evidence, 'moonbit-scene.json'), JSON.stringify(frame, null, 2));
  report.text_metrics = await moon.locator('canvas').evaluate(canvas => {
    const {frame, metadata} = globalThis.gpuiExample;
    const item = frame.snapshot.items.find(item => item.kind === 'text');
    const context = canvas.getContext('2d');
    context.save();
    context.font = `${item.font_size}px "${metadata.font_family}"`;
    const m = context.measureText(item.text);
    context.restore();
    const metrics = Object.fromEntries(['width','fontBoundingBoxAscent','fontBoundingBoxDescent',
      'actualBoundingBoxAscent','actualBoundingBoxDescent','actualBoundingBoxLeft','actualBoundingBoxRight']
      .map(key => [key, m[key]]));
    return {font: metadata.font_family, font_size: item.font_size, bounds: item.bounds, ...metrics,
      baseline: item.bounds.y + (item.bounds.height - m.fontBoundingBoxAscent - m.fontBoundingBoxDescent) / 2 + m.fontBoundingBoxAscent};
  });
  async function captureCanvas(locator, side) {
    await locator.scrollIntoViewIfNeeded();
    const bounds = await locator.boundingBox();
    assert.equal(bounds.width, 500); assert.equal(bounds.height, 500);
    const clip = {x: Math.ceil(bounds.x), y: Math.ceil(bounds.y), width: 500, height: 500};
    report.captures ||= {};
    report.captures[side] = {bounds, clip, method:'integer CSS pixel page clip; no rescaling or masking'};
    return page.screenshot({clip});
  }
  await writeFile(join(evidence, 'moonbit.png'), await captureCanvas(moon.locator('canvas'), 'moonbit'));
  report.candidate = 'passed';
  if (paired) {
    report.rust = 'failed';
    await page.frameLocator('#rust-frame').locator('html[data-runtime-status="initialized"]').waitFor({timeout: 60000});
    assert.equal(await page.evaluate(() => crossOriginIsolated), true);
    for (const id of ['rust-frame', 'moon-frame']) {
      const url = await page.locator('#' + id).getAttribute('src');
      assert.equal(new URL(url).origin, new URL(page.url()).origin);
    }
    const rust = page.frameLocator('#rust-frame');
    assert.equal(await rust.locator('html').evaluate(() => crossOriginIsolated), true);
    const probes = [[150,272,255,0,0], [190,272,0,128,0], [230,272,0,0,255], [270,272,255,255,0], [310,272,0,0,0], [350,272,255,255,255]];
    async function inspectCanvas(locator, side) {
      const buffer = await captureCanvas(locator, side);
      const pixels = await page.evaluate(async ({url, probes}) => {
        const image = new Image(); image.src = url; await image.decode();
        const canvas = document.createElement('canvas'); canvas.width = 500; canvas.height = 500;
        const context = canvas.getContext('2d', {willReadFrequently:true}); context.drawImage(image, 0, 0);
        return probes.map(([x,y]) => [...context.getImageData(x,y,1,1).data].slice(0,3));
      }, {url: 'data:image/png;base64,' + buffer.toString('base64'), probes});
      return {buffer, pixels};
    }
    const expected = probes.map(p => p.slice(2));
    let observed;
    const deadline = Date.now() + 30000;
    do {
      observed = await inspectCanvas(rust.locator('canvas'), 'rust');
      if (JSON.stringify(observed.pixels) === JSON.stringify(expected)) break;
      await page.waitForTimeout(200);
    } while (Date.now() < deadline);
    await writeFile(join(evidence, 'rust.png'), observed.buffer);
    report.probes = {coordinates: probes.map(p => p.slice(0,2)), expected, rust: observed.pixels, moonbit: (await inspectCanvas(moon.locator('canvas'), 'moonbit')).pixels};
    const offsets = Object.fromEntries(['rust','moonbit'].map(side => [side, {
      x: report.captures[side].clip.x - report.captures[side].bounds.x,
      y: report.captures[side].clip.y - report.captures[side].bounds.y,
    }]));
    assert(Math.abs(offsets.rust.x - offsets.moonbit.x) < 1e-7);
    assert(Math.abs(offsets.rust.y - offsets.moonbit.y) < 1e-7);
    report.capture_alignment = {offsets, equal_fractional_offsets: true};
    assert.deepEqual(report.probes.rust, expected, 'Real Rust canvas must render all six color probes');
    assert.deepEqual(report.probes.moonbit, expected);
    assert(report.requests.some(r => r.url.includes('/rust/') && r.url.endsWith('.wasm') && r.status === 200), 'Actual WASM response required');
    for (const [side, pane] of [['rust',rust], ['moonbit',moon]]) {
      await pane.locator('canvas').click({position:{x:150,y:272}});
      await page.keyboard.press('Enter');
      const events = await pane.locator('html').evaluate(() => browserEvents);
      assert(events.some(e => e.type === 'click' && e.trusted));
      assert(events.some(e => e.type === 'keydown' && e.key === 'Enter' && e.trusted));
      await writeFile(join(evidence, side + '-browser-events.json'), JSON.stringify(events, null, 2));
      assert.deepEqual((await inspectCanvas(pane.locator('canvas'), side)).pixels, expected);
      report.operations.push({side, action:'pointer click then Enter', delivery:'passed', color_probes_after:'passed', application_handling:'not_applicable_static_example'});
    }
    report.rust = 'passed';
    report.comparison = 'color_probes_matched_pixel_parity_unverified';
    report.verified.push('same-origin compiled Rust WASM and MoonBit JS', '500x500 viewports', 'six rendered swatch RGB probes', 'trusted browser click/key delivery; static swatches retained');
  }
  await page.screenshot({ path: join(evidence, 'hello-world-pair.png'), fullPage: true });
  await page.selectOption('#fixture', 'text_layout');
  await waitForNewDocuments();
  const textFrame = await moon.locator('html').evaluate(() => globalThis.gpuiExample);
  assert.equal(textFrame.metadata.id, 'text_layout');
  assert.deepEqual([textFrame.metadata.width,textFrame.metadata.height], [800,600]);
  assert.equal(textFrame.frame.snapshot.items.filter(i => i.kind === 'text').length,15);
  assert.equal(textFrame.frame.snapshot.clip_chains.length,2);
  assert.equal(textFrame.frame.conformance,'unverified');
  assert.equal(textFrame.frame.text_styles.filter(s=>s.decoration==='underline').length,3);
  assert.equal(textFrame.frame.text_styles.filter(s=>s.decoration==='line_through').length,3);
  for (const side of ['moon', ...(paired ? ['rust'] : [])]) {
    const bounds = await page.locator('#' + side + '-frame').boundingBox();
    assert.deepEqual([bounds.width,bounds.height],[800,600]);
  }
  assert.equal(await page.locator('#moon-source').getAttribute('href'),
    `https://github.com/gpui-mbt/gpui-conformance/blob/${manifest.lab_revision}/web/moonbit/text_layout/text_layout.mbt`);
  await writeFile(join(evidence,'text-layout-moonbit-scene.json'),JSON.stringify(textFrame,null,2));
  await moon.locator('canvas').screenshot({path:join(evidence,'text-layout-moonbit.png')});
  if (paired) {
    assert(report.requests.some(r => r.url.endsWith('/rust/text_layout_bg.wasm') && r.status===200), 'Actual text_layout WASM response required');
    // A canvas existing is insufficient: wait for dark ink in the first text line.
    const rustCanvas = page.frameLocator('#rust-frame').locator('canvas');
    let ink = false;
    for (let attempt=0; attempt<100 && !ink; attempt++) {
      const buffer=await rustCanvas.screenshot();
      ink = await page.evaluate(async url => {
        const img=new Image(); img.src=url; await img.decode();
        const c=document.createElement('canvas');c.width=800;c.height=600;
        const ctx=c.getContext('2d');ctx.drawImage(img,0,0);
        const pixels=ctx.getImageData(16,16,120,26).data;
        for(let i=0;i<pixels.length;i+=4) if(pixels[i]<100 && pixels[i+1]<100 && pixels[i+2]<100) return true;
        return false;
      },'data:image/png;base64,'+buffer.toString('base64'));
      if (ink) await writeFile(join(evidence,'text-layout-rust.png'),buffer);
      else await page.waitForTimeout(200);
    }
    assert(ink,'Upstream text_layout must render actual dark text ink');
  }
  report.operations.push({action:'select text_layout',candidate:'15 text scene items, decorated runs and clip chains',rust:paired?'actual WASM and text ink verified':'not_run',comparison:'unverified'});
  await page.screenshot({path:join(evidence,'text-layout-pair.png'),fullPage:true});
  await page.selectOption('#fixture', 'input');
  assert.equal(await page.locator('#moon-frame').isVisible(), false);
  assert.equal(await page.locator('#moon-frame').getAttribute('src'), null);
  assert.equal(await page.locator('#rust-frame').getAttribute('src'), null);
  report.operations.push({action:'select missing input port', result:'both_frames_cleared'});
  await page.selectOption('#fixture', 'hello_world');
  await waitForNewDocuments();
  const previous = await page.locator('#moon-frame').getAttribute('src');
  await page.locator('#settings button').click();
  assert.notEqual(await page.locator('#moon-frame').getAttribute('src'), previous);
  await waitForNewDocuments();
  report.operations.push({action:'reload both', result:'runtimes_initialized'});
  await page.setViewportSize({width:390,height:850});
  for (const id of ['rust-frame','moon-frame']) {
    if (id === 'rust-frame' && !paired) continue;
    const bounds = await page.locator('#' + id).boundingBox();
    assert.equal(bounds.width,500); assert.equal(bounds.height,500);
  }
  await page.screenshot({path:join(evidence,'mobile.png'),fullPage:true});
  report.verified.push('missing-port clearing', 'reload both', 'fixed viewport in narrow layout');
  assert.deepEqual(errors, []);
  report.overall = 'passed';
  console.log(paired ? 'PASS: actual Rust WASM and MoonBit JS rendered on one origin; screenshots, browser events and color probes retained. Pixel parity UNVERIFIED.' : 'PASS: compiled MoonBit; Rust comparison NOT RUN.');
} catch (error) {
  report.failure = error.stack;
  if (page) await page.screenshot({path:join(evidence,'failure.png'),fullPage:true}).catch(() => {});
  throw error;
} finally {
  await writeFile(join(evidence, 'result.json'), JSON.stringify(report, null, 2) + '\n');
  if (browser) await browser.close();
  await new Promise(done => server.close(done));
}
