// Build the catalog first, then run with PLAYWRIGHT_ROOT pointing to the pinned
// Playwright installation. This tests release coherence, not rendering parity.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, resolve, sep } from 'node:path';

const require = createRequire(process.env.PLAYWRIGHT_ROOT
  ? join(resolve(process.env.PLAYWRIGHT_ROOT), 'package.json') : import.meta.url);
const { chromium } = require('playwright');
const site = resolve(process.argv[2] || '_build/catalog');
// Preserve the exact document bytes before simulating another loose-asset release.
const savedHTML = await readFile(join(site, 'index.html'), 'utf8');
const sourceHTML = await readFile(new URL('../catalog/index.html', import.meta.url), 'utf8');
const legacyHTML = sourceHTML.replace(/\s*<section\b[^>]*class="examples-section"[^>]*>[\s\S]*?<\/section>/, '')
  .replace(/\s*<p\b[^>]*id="browser-(?:current-note|current-pins)"[^>]*>[\s\S]*?<\/p>/g, '')
  .replace(/\s*<p><a id="browser-inventory">[\s\S]*?<\/a><\/p>/, '');
assert(!legacyHTML.includes('id="example-list"'), 'The legacy document fixture must omit the entire gallery');
assert(!legacyHTML.includes('id="browser-current-pins"'), 'Legacy documents predate current/evidence pin separation');
const legacyData = JSON.parse(await readFile(join(site, 'data.json'), 'utf8'));
delete legacyData.browser.current_pins;
delete legacyData.browser.inventory_url;
delete legacyData.browser.pins_match_current_inventory;
for (const example of legacyData.browser_examples) {
  delete example.implementation;
  delete example.feature_tags;
  if (example.thumbnail) delete example.thumbnail.pins;
}
const inventory = JSON.parse(await readFile(new URL('../web/examples.json', import.meta.url), 'utf8'));
const retainedResult = JSON.parse(await readFile(new URL('../web/evidence/20261016/result.json', import.meta.url), 'utf8'));
const rawLabBase = (process.env.CATALOG_BROWSER_LAB_BASE_URL || '').trim();
const labBase = rawLabBase ? new URL(rawLabBase).origin : '';
// 17 declared ports minus the one retained hello_world comparison.
const expectedUnverifiedExamples = 16;
const implemented = ['hello_world', 'text', 'text_layout', 'text_wrapper', 'input', 'dynamic_fonts', 'hello_web', 'tree', 'scrollable', 'focus_visible', 'tab_stop', 'drag_drop', 'uniform_list', 'grid_layout', 'anchor', 'gradient', 'popover'];
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript',
  '.css': 'text/css', '.json': 'application/json', '.png': 'image/png' };
const server = createServer(async (request, response) => {
  try {
    const { pathname } = new URL(request.url, 'http://localhost');
    if (pathname === '/favicon.ico') { response.writeHead(204); response.end(); return; }
    const mount = ['/gpui-conformance/', '/saved-release/', '/legacy-document/', '/legacy-data/', '/legacy-failure/']
      .find(prefix => pathname.startsWith(prefix));
    if (!mount) throw new Error('Outside test site');
    const relative = decodeURIComponent(pathname.slice(mount.length)) || 'index.html';
    const path = resolve(site, relative);
    if (!path.startsWith(site + sep)) throw new Error('Outside test site');
    let content;
    if (relative === 'index.html' && mount === '/saved-release/') content = savedHTML;
    else if (relative === 'index.html' && ['/legacy-document/', '/legacy-failure/'].includes(mount)) content = legacyHTML;
    else if (relative === 'index.html' && mount === '/legacy-data/') content = sourceHTML;
    else content = await readFile(path);
    response.writeHead(200, { 'content-type': types[extname(path)] || 'application/octet-stream',
      'cache-control': 'no-store' });
    response.end(content);
  } catch {
    response.writeHead(404); response.end('Not found');
  }
});
await new Promise((done, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', done);
});

let browser;
try {
  browser = await chromium.launch({ headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.setDefaultTimeout(10000);
  const errors = [];
  const pageErrors = [];
  const expectedHTTP503Errors = [];
  const looseRequests = [];
  const legacyRequests = [];
  let looseMode = 'stale';
  page.on('pageerror', error => { pageErrors.push(error.message); errors.push(error.message); });
  page.on('console', message => {
    if (message.type() !== 'error') return;
    if (message.location().url === `${origin}/legacy-failure/data.json` && /503/.test(message.text())) {
      expectedHTTP503Errors.push(message.text());
    } else errors.push(message.text());
  });
  page.on('requestfailed', request => errors.push(`${request.url()}: ${request.failure()?.errorText}`));
  // Deterministically model independently cached old JS/CSS/JSON and a later
  // failed deployment. No actual cache timing is assumed by this test.
  await page.route(/\/(?:app\.js|style\.css|data\.json)(?:\?.*)?$/, route => {
    const path = new URL(route.request().url()).pathname;
    const name = path.split('/').at(-1);
    if (path.startsWith('/legacy-')) {
      legacyRequests.push(path);
      if (path === '/legacy-data/data.json') {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(legacyData) });
      }
      if (path === '/legacy-failure/data.json') {
        return route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":"temporarily unavailable"}' });
      }
      return route.continue();
    }
    looseRequests.push({ mode: looseMode, name });
    const stale = { 'app.js': 'throw new Error("stale loose catalog script executed");',
      'style.css': 'body { display: none !important; }',
      'data.json': JSON.stringify({ revision: 'stale-incompatible-release', cases: [] }) };
    return route.fulfill({ status: looseMode === 'failed' ? 503 : 200,
      contentType: types[extname(name)], body: looseMode === 'failed' ? 'deployment unavailable' : stale[name] });
  });

  const origin = `http://127.0.0.1:${server.address().port}`;
  const visibleExamples = '#example-list > .example-card:not([hidden])';
  const visibleCases = '#case-list > .case-row:not([hidden])';
  async function assertCount(selector, count) {
    await page.waitForFunction(({ selector, count }) => document.querySelectorAll(selector).length === count,
      { selector, count });
    assert.equal(await page.locator(selector).count(), count);
  }
  async function assertReady() {
    await assertCount('#example-list > .example-card', 17);
    await assertCount('#case-list > .case-row', 153);
    await assertCount(visibleExamples, 17);
    await assertCount(visibleCases, 153);
    assert.equal(await page.locator('#example-count').textContent(), '17 / 17 examples を表示');
    assert.equal(await page.locator('#result-count').textContent(), '153 / 153 件を表示');
    assert.equal(await page.locator('#examples-empty').isVisible(), false);
    assert.equal(await page.locator('#empty-state').isVisible(), false);
    assert.equal(await page.locator('script[src], link[rel="stylesheet"]').count(), 0,
      'The generated document must carry its own application and styles');
    assert.equal(await page.locator('script#catalog-data[type="application/json"]').count(), 1);
    const previews = page.locator('#example-list .example-preview img');
    assert.equal(await previews.count(), 4, 'Four retained captures; text, input, dynamic_fonts, tree, scrollable, focus_visible, tab_stop, drag_drop, uniform_list and grid_layout have no saved previews');
    assert.equal(await page.locator('#example-list a').evaluateAll(nodes => nodes.filter(node => node.textContent === '撮影記録').length), 3);
    assert.equal(await page.locator('#example-list a').evaluateAll(nodes => nodes.filter(node => node.textContent === 'gpui.rs の保存画像').length), 3);
    assert.equal(await page.locator('#example-list').evaluate(node => getComputedStyle(node).display), 'grid',
      'Embedded styles must apply even when loose CSS is stale or unavailable');
    // Finish lazy image requests before navigating again, and verify retained
    // evidence images also resolve relative to the saved-document route.
    for (const image of await page.locator('.example-preview img').all()) {
      await image.scrollIntoViewIfNeeded();
      await image.evaluate(node => node.decode());
    }
    assert.deepEqual(await previews.evaluateAll(nodes => nodes.map(node => [node.naturalWidth, node.naturalHeight])),
      [[500, 500], [800, 600], [800, 600], [640, 560]]);
    const data = await page.locator('#catalog-data').evaluate(node => JSON.parse(node.textContent));
    assert.equal(data.browser.implemented_count, 17);
    assert.equal(data.browser.evidence_count, 1);
    assert.equal(await page.locator('#examples-summary').textContent(), '17 examples · gpui.mbt 実装 17 件 · 保存済み比較 1 件');
    assert.deepEqual(data.browser_examples.map(example => example.id), implemented);
    const coreExamples = data.browser_examples.filter(example => example.source_path.startsWith('crates/gpui/examples/'));
    const webExamples = data.browser_examples.filter(example => example.source_path.startsWith('crates/gpui_web/examples/'));
    assert.equal(coreExamples.length, 15, 'Fifteen core GPUI sources, including the new popover');
    assert.equal(webExamples.length, 2, 'Only dynamic_fonts and hello_web come from gpui_web');
    assert.deepEqual(webExamples.map(example => example.id), ['dynamic_fonts', 'hello_web']);
    assert.deepEqual(data.browser_examples.map(example => example.source_path), inventory.examples.map(example => example.source));
    assert.equal(data.browser.current_status, 'unverified');
    assert.equal(data.browser.changed_pixels, 1532, 'The historical hello_world score must stay unchanged');
    assert.equal(data.browser.pins_match_current_inventory, false);
    assert.deepEqual(data.browser.pins.map(pin => pin.revision),
      ['upstream', 'moonbit'].map(kind => retainedResult.build[kind].revision));
    assert.deepEqual(data.browser.current_pins.map(pin => pin.revision),
      ['upstream', 'moonbit'].map(kind => inventory[kind].revision));
    assert.equal(data.browser.current_pins[1].tree, '96d62ea12a6824ee20d04cb913191bc23a424522');
    assert.equal(data.browser.current_pins[1].revision, 'e160f5ec7bf0c6f43738d0bdcf837098299d5569');
    for (const [id, pins] of [['browser-pins', data.browser.pins], ['browser-current-pins', data.browser.current_pins]]) {
      assert.deepEqual(await page.locator(`#${id} a`).evaluateAll(nodes => nodes.map(node => node.href)), pins.map(pin => pin.url));
    }
    assert.match(await page.locator('#browser-current-note').textContent(), /とは異なる pin.*未検証/);
    assert.equal(await page.locator('#browser-inventory').getAttribute('href'), data.browser.inventory_url);
    assert.equal(await page.locator('.evidence-provenance').count(), 4);
    for (const preview of await page.locator('.evidence-provenance').all()) {
      assert.match(await preview.textContent(), /現行 inventory とは異なります/);
      assert.deepEqual(await preview.locator('a').evaluateAll(nodes => nodes.map(node => node.href)), data.browser.pins.map(pin => pin.url));
    }
    const scrollable = page.locator('.example-card:has(#example-scrollable)');
    assert.equal(await scrollable.count(), 1);
    assert.equal(await scrollable.locator('.case-status').textContent(), '未検証 · unverified');
    assert.equal(await scrollable.locator('.example-preview img').count(), 0);
    assert.equal(await scrollable.locator('.evidence-provenance').count(), 0);
    assert.match(await scrollable.locator('.preview-label').textContent(), /保存画像なし/);
    const focus = page.locator('.example-card:has(#example-focus_visible)');
    assert.equal(await focus.count(), 1);
    assert.equal(await focus.locator('.case-status').textContent(), '未検証 · unverified');
    assert.equal(await focus.locator('.example-preview img, .evidence-provenance').count(), 0);
    assert.match(await focus.locator('.preview-label').textContent(), /保存画像なし/);
    assert.match(await focus.locator('.implementation-label').textContent(), /800×600/);
    const focusData = data.browser_examples.find(example => example.id === 'focus_visible');
    assert.equal(focusData.interactive, true);
    assert.equal(focusData.execution, 'unverified');
    assert.equal(focusData.evidence_available, false);
    for (const key of ['result_url', 'result_date', 'changed_pixels', 'total_pixels', 'thumbnail', 'evidence_scope'])
      assert.equal(focusData[key], null, key);
    assert.equal(await focus.locator('.case-links a').evaluateAll(nodes =>
      nodes.find(node => node.textContent === '上流ソース')?.href),
    'https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/focus_visible.rs');
    assert.deepEqual(await focus.locator('.evidence-links a').allTextContents(), labBase ? ['ライブ比較を開く'] : []);
    const tabStop = page.locator('.example-card:has(#example-tab_stop)');
    assert.equal(await tabStop.count(), 1);
    assert.equal(await tabStop.getAttribute('data-implementation'), 'implemented');
    assert.equal(await tabStop.locator('.case-status').textContent(), '未検証 · unverified');
    assert.equal(await tabStop.locator('.implementation-label').textContent(), 'gpui.mbt 実装あり · 800×600');
    assert.equal(await tabStop.locator('.example-preview img, .evidence-provenance, .evidence-date').count(), 0);
    assert.match(await tabStop.locator('.preview-label').textContent(), /保存画像なし/);
    assert.match(await tabStop.locator('.evidence-note').textContent(), /保存済み比較結果・画像はなく.*未検証/);
    const tabStopData = data.browser_examples.find(example => example.id === 'tab_stop');
    assert.equal(tabStopData.implemented, true);
    assert.equal(tabStopData.implementation.status, 'implemented');
    assert.equal(tabStopData.interactive, true);
    assert.deepEqual([tabStopData.width, tabStopData.height], [800, 600]);
    assert.equal(tabStopData.suite_type, 'browser');
    assert.equal(tabStopData.status, 'unverified');
    assert.equal(tabStopData.execution, 'unverified');
    assert.equal(tabStopData.evidence_available, false);
    for (const key of ['result_url', 'result_date', 'changed_pixels', 'total_pixels', 'thumbnail', 'evidence_scope'])
      assert.equal(tabStopData[key], null, `tab_stop ${key}`);
    assert.equal(tabStopData.source_path, 'crates/gpui/examples/tab_stop.rs');
    assert.equal(tabStopData.source_revision, '5a5fbe79917971a4d52a96b6ddb04da198a5012e');
    assert.equal(tabStopData.source_url,
      'https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/tab_stop.rs');
    assert.equal(tabStopData.implementation.source_url,
      `https://github.com/gpui-mbt/gpui-conformance/blob/${data.revision}/web/moonbit/tab_stop/tab_stop.mbt`);
    assert.equal(tabStopData.inventory_url,
      `https://github.com/gpui-mbt/gpui-conformance/blob/${data.revision}/web/examples.json`);
    assert.deepEqual(await tabStop.locator('.case-links:not(.evidence-links) a').evaluateAll(nodes =>
      nodes.map(node => [node.textContent, node.href])),
    [['上流ソース', tabStopData.source_url], ['gpui.mbt 実装', tabStopData.implementation.source_url]]);
    assert.deepEqual(await tabStop.locator('.evidence-links a').evaluateAll(nodes => nodes.map(node => [node.textContent, node.href])),
      labBase ? [['ライブ比較を開く', `${labBase}/?example=tab_stop`]] : []);
    const tabStopRow = page.locator('#case-list > .case-row[data-suite="browser"]').filter({
      has: page.getByRole('heading', { name: 'tab_stop', exact: true }),
    });
    assert.equal(await tabStopRow.count(), 1);
    assert.equal(await tabStopRow.getAttribute('data-status'), 'unverified');
    assert.equal(await tabStopRow.locator('.case-status').textContent(), '未検証 · unverified');
    assert.deepEqual(await tabStopRow.locator('.case-links a').evaluateAll(nodes => nodes.map(node => [node.textContent, node.href])),
      [['source', tabStopData.source_url], ['inventory', tabStopData.inventory_url],
        ...(labBase ? [['ライブ比較', `${labBase}/?example=tab_stop`]] : [])]);
    const dragDrop = page.locator('.example-card:has(#example-drag_drop)');
    assert.equal(await dragDrop.count(), 1);
    assert.equal(await dragDrop.getAttribute('data-implementation'), 'implemented');
    assert.equal(await dragDrop.locator('.case-status').textContent(), '未検証 · unverified');
    assert.equal(await dragDrop.locator('.implementation-label').textContent(), 'gpui.mbt 実装あり · 800×600');
    assert.equal(await dragDrop.locator('.example-preview img, .evidence-provenance, .evidence-date').count(), 0);
    assert.match(await dragDrop.locator('.preview-label').textContent(), /保存画像なし/);
    assert.match(await dragDrop.locator('.evidence-note').textContent(), /保存済み比較結果・画像はなく.*未検証/);
    const dragDropData = data.browser_examples.find(example => example.id === 'drag_drop');
    assert.equal(dragDropData.implemented, true);
    assert.equal(dragDropData.implementation.status, 'implemented');
    assert.equal(dragDropData.interactive, true);
    assert.deepEqual([dragDropData.width, dragDropData.height], [800, 600]);
    assert.equal(dragDropData.suite_type, 'browser');
    assert.equal(dragDropData.status, 'unverified');
    assert.equal(dragDropData.execution, 'unverified');
    assert.equal(dragDropData.evidence_available, false);
    for (const key of ['result_url', 'result_date', 'changed_pixels', 'total_pixels', 'thumbnail', 'evidence_scope'])
      assert.equal(dragDropData[key], null, `drag_drop ${key}`);
    assert.equal(dragDropData.source_path, 'crates/gpui/examples/drag_drop.rs');
    assert.equal(dragDropData.source_revision, '5a5fbe79917971a4d52a96b6ddb04da198a5012e');
    assert.equal(dragDropData.source_url,
      'https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/drag_drop.rs');
    assert.equal(dragDropData.implementation.source_url,
      `https://github.com/gpui-mbt/gpui-conformance/blob/${data.revision}/web/moonbit/drag_drop/drag_drop.mbt`);
    assert.equal(dragDropData.inventory_url,
      `https://github.com/gpui-mbt/gpui-conformance/blob/${data.revision}/web/examples.json`);
    assert.deepEqual(await dragDrop.locator('.case-links:not(.evidence-links) a').evaluateAll(nodes =>
      nodes.map(node => [node.textContent, node.href])),
    [['上流ソース', dragDropData.source_url], ['gpui.mbt 実装', dragDropData.implementation.source_url]]);
    assert.deepEqual(await dragDrop.locator('.evidence-links a').evaluateAll(nodes => nodes.map(node => [node.textContent, node.href])),
      labBase ? [['ライブ比較を開く', `${labBase}/?example=drag_drop`]] : []);
    const dragDropRow = page.locator('#case-list > .case-row[data-suite="browser"]').filter({
      has: page.getByRole('heading', { name: 'drag_drop', exact: true }),
    });
    assert.equal(await dragDropRow.count(), 1);
    assert.equal(await dragDropRow.getAttribute('data-status'), 'unverified');
    assert.equal(await dragDropRow.locator('.case-status').textContent(), '未検証 · unverified');
    assert.deepEqual(await dragDropRow.locator('.case-links a').evaluateAll(nodes => nodes.map(node => [node.textContent, node.href])),
      [['source', dragDropData.source_url], ['inventory', dragDropData.inventory_url],
        ...(labBase ? [['ライブ比較', `${labBase}/?example=drag_drop`]] : [])]);
    const uniformData = data.browser_examples.find(example => example.id === 'uniform_list');
    const uniformCard = page.locator('.example-card:has(#example-uniform_list)');
    assert.equal(await uniformCard.count(), 1);
    assert.equal(uniformData.status, 'unverified');
    assert.equal(uniformData.evidence_available, false);
    assert.match(uniformData.implementation.note, /right-edge.*Item 3/);
    assert.match(await uniformCard.textContent(), /文字の右端/);
    assert.equal(await uniformCard.locator('.example-preview img, .evidence-provenance, .evidence-date').count(), 0);
    const gridData = data.browser_examples.find(example => example.id === 'grid_layout');
    const gridCard = page.locator('.example-card:has(#example-grid_layout)');
    assert.equal(await gridCard.count(), 1);
    assert.equal(gridData.implemented, true);assert.equal(gridData.interactive, true);
    assert.equal(gridData.status, 'unverified');assert.equal(gridData.execution, 'unverified');
    assert.equal(gridData.evidence_available, false);
    for (const key of ['result_url', 'result_date', 'changed_pixels', 'total_pixels', 'thumbnail', 'evidence_scope'])
      assert.equal(gridData[key], null, `grid_layout ${key}`);
    assert.deepEqual([gridData.width, gridData.height], [500, 500]);
    assert(gridData.feature_tags.includes('container query'));
    assert.match(gridData.implementation.note, /two host layout passes.*not Rust callback-count parity/);
    assert.match(await gridCard.textContent(), /399\/400\/401\/500px/);
    assert.equal(await gridCard.locator('.example-preview img, .evidence-provenance, .evidence-date').count(), 0);
    assert.deepEqual(await gridCard.locator('.evidence-links a').evaluateAll(nodes => nodes.map(node => [node.textContent, node.href])),
      labBase ? [['ライブ比較を開く', `${labBase}/?example=grid_layout`]] : []);
    const gradientData=data.browser_examples.find(e=>e.id==='gradient'),gradientCard=page.locator('.example-card:has(#example-gradient)');
    assert.equal(await gradientCard.count(),1);assert.equal(gradientData.status,'unverified');assert.equal(gradientData.execution,'unverified');assert.equal(gradientData.evidence_available,false);
    for(const key of ['result_url','result_date','changed_pixels','total_pixels','thumbnail','evidence_scope'])assert.equal(gradientData[key],null);
    assert.deepEqual([gradientData.width,gradientData.height],[960,600]);assert.match(gradientData.implementation.note,/960×600 and 600×960, DPR1/);
    assert.equal(await gradientCard.locator('.example-preview img, .evidence-provenance, .evidence-date').count(),0);
    assert.deepEqual(await gradientCard.locator('.evidence-links a').evaluateAll(nodes=>nodes.map(n=>[n.textContent,n.href])),labBase?[['ライブ比較を開く',`${labBase}/?example=gradient`]]:[]);
    const anchorData = data.browser_examples.find(example => example.id === 'anchor');
    const anchorCard = page.locator('.example-card:has(#example-anchor)');
    assert.equal(await anchorCard.count(), 1);
    assert.equal(anchorData.implemented, true);assert.equal(anchorData.interactive, true);
    assert.equal(anchorData.status, 'unverified');assert.equal(anchorData.execution, 'unverified');
    assert.equal(anchorData.evidence_available, false);
    for (const key of ['result_url', 'result_date', 'changed_pixels', 'total_pixels', 'thumbnail', 'evidence_scope'])
      assert.equal(anchorData[key], null, `anchor ${key}`);
    assert.deepEqual([anchorData.width, anchorData.height], [750, 600]);
    assert.equal(anchorData.source_path, 'crates/gpui/examples/anchor.rs');
    assert(anchorData.feature_tags.includes('anchor'));
    assert.match(anchorData.implementation.note, /widths 750 and 480, height 600, DPR1/);
    assert.match(anchorData.implementation.note, /Paired browser.*remain unverified/);
    assert.match(await anchorCard.textContent(), /750\/480px/);
    assert.equal(await anchorCard.locator('.example-preview img, .evidence-provenance, .evidence-date').count(), 0);
    assert.deepEqual(await anchorCard.locator('.evidence-links a').evaluateAll(nodes => nodes.map(node => [node.textContent, node.href])),
      labBase ? [['ライブ比較を開く', `${labBase}/?example=anchor`]] : []);
    const popoverData = data.browser_examples.find(example => example.id === 'popover');
    const popoverCard = page.locator('.example-card:has(#example-popover)');
    assert.equal(await popoverCard.count(), 1);
    assert.equal(popoverData.implemented, true);
    assert.equal(popoverData.implementation.status, 'implemented');
    assert.equal(popoverData.interactive, true);
    assert.deepEqual([popoverData.width, popoverData.height], [800, 600]);
    assert.equal(popoverData.status, 'unverified');
    assert.equal(popoverData.execution, 'unverified');
    assert.equal(popoverData.evidence_available, false);
    for (const key of ['result_url', 'result_date', 'changed_pixels', 'total_pixels', 'thumbnail', 'evidence_scope'])
      assert.equal(popoverData[key], null, `popover ${key}`);
    assert.equal(popoverData.source_path, 'crates/gpui/examples/popover.rs');
    assert.equal(popoverData.source_url,
      'https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/popover.rs');
    assert.equal(popoverData.implementation.source_url,
      `https://github.com/gpui-mbt/gpui-conformance/blob/${data.revision}/web/moonbit/popover/popover.mbt`);
    assert.match(popoverData.implementation.note, /Paired browser, native, text, shadow, full-image and callback-count parity remain unverified/);
    assert.equal(await popoverCard.locator('.case-status').textContent(), '未検証 · unverified');
    assert.equal(await popoverCard.locator('.example-preview img, .evidence-provenance, .evidence-date').count(), 0);
    assert.match(await popoverCard.locator('.preview-label').textContent(), /保存画像なし/);
    assert.deepEqual(await popoverCard.locator('.evidence-links a').evaluateAll(nodes => nodes.map(node => [node.textContent, node.href])),
      labBase ? [['ライブ比較を開く', `${labBase}/?example=popover`]] : []);
    const popoverRow = page.locator('#case-list > .case-row[data-suite="browser"]').filter({
      has: page.getByRole('heading', { name: 'popover', exact: true }),
    });
    assert.equal(await popoverRow.count(), 1);
    assert.equal(await popoverRow.getAttribute('data-status'), 'unverified');
    assert.deepEqual(await popoverRow.locator('.case-links a').evaluateAll(nodes => nodes.map(node => [node.textContent, node.href])),
      [['source', popoverData.source_url], ['inventory', popoverData.inventory_url],
        ...(labBase ? [['ライブ比較', `${labBase}/?example=popover`]] : [])]);
    assert.equal(data.browser_examples.filter(example => example.status === 'unverified').length, expectedUnverifiedExamples);
    assert.equal(data.browser_examples.filter(example => example.status === 'unsupported').length, 0);
    assert.deepEqual(await page.locator('.example-card[data-implementation="implemented"] .example-id').allTextContents(), implemented);
    assert.equal(await page.locator('#catalog-revision').textContent(), `Catalog source ${data.revision.slice(0, 12)}`);
    const comparisonLinks = await page.locator('#example-list a').evaluateAll(nodes =>
      nodes.filter(node => node.textContent === 'ライブ比較を開く').map(node => node.href).sort());
    assert.deepEqual(comparisonLinks, labBase ? implemented.map(id => `${labBase}/?example=${id}`).sort() : []);
    assert.equal(await page.locator('#case-list a').evaluateAll(nodes =>
      nodes.filter(node => node.textContent === 'ライブ比較').length), labBase ? implemented.length : 0);
    assert.deepEqual(looseRequests, [], 'A coherent release must never request loose JS, CSS, or JSON');
    assert.deepEqual(errors, []);
    return { revision: data.revision, release: await page.locator('meta[name="catalog-release"]').getAttribute('content') };
  }

  const firstResponse = await page.goto(`${origin}/gpui-conformance/`);
  assert.equal(await firstResponse.text(), savedHTML);
  const firstRelease = await assertReady();
  assert.match(firstRelease.release, /^[a-f0-9]{64}$/);

  // Gallery search and implementation filters combine; native form reset also
  // restores the count and empty-state message after the asynchronous handler.
  await page.selectOption('#implementation-filter', 'implemented');
  await assertCount(visibleExamples, 17);
  await page.fill('#example-search', '  TEXT_WRAPPER  ');
  await assertCount(visibleExamples, 1);
  assert.equal(await page.locator(`${visibleExamples} .example-id`).textContent(), 'text_wrapper');
  await page.selectOption('#implementation-filter', 'not_implemented');
  await assertCount(visibleExamples, 0);
  assert.equal(await page.locator('#examples-empty').isVisible(), true);
  await page.fill('#example-search', '');
  await assertCount(visibleExamples, 0);
  assert.equal(await page.locator('#examples-empty').isVisible(), true);
  await page.locator('#example-filters button[type="reset"]').click();
  await assertCount(visibleExamples, 17);
  await page.fill('#example-search', '  TAB_STOP  ');
  await page.selectOption('#implementation-filter', 'implemented');
  await assertCount(visibleExamples, 1);
  assert.equal(await page.locator(`${visibleExamples} .example-id`).textContent(), 'tab_stop');
  await page.selectOption('#implementation-filter', 'not_implemented');
  await assertCount(visibleExamples, 0);
  assert.equal(await page.locator('#examples-empty').isVisible(), true);
  await page.locator('#example-filters button[type="reset"]').click();
  await assertCount(visibleExamples, 17);
  await page.fill('#example-search', 'crates/gpui/examples/tab_stop.rs');
  await assertCount(visibleExamples, 1);
  assert.equal(await page.locator(`${visibleExamples} .example-id`).textContent(), 'tab_stop');
  await page.locator('#example-filters button[type="reset"]').click();
  await assertCount(visibleExamples, 17);
  assert.equal(await page.locator('#implementation-filter').inputValue(), '');
  assert.equal(await page.locator('#example-search').inputValue(), '');
  await page.fill('#example-search', ' DRAG_DROP ');
  await assertCount(visibleExamples, 1);
  assert.equal(await page.locator(`${visibleExamples} .example-id`).textContent(), 'drag_drop');
  await page.locator('#example-filters button[type="reset"]').click();
  await assertCount(visibleExamples, 17);
  await page.fill('#example-search', 'FOCUS_VISIBLE');
  await assertCount(visibleExamples, 1);
  assert.equal(await page.locator(`${visibleExamples} .example-id`).textContent(), 'focus_visible');
  await page.locator('#example-filters button[type="reset"]').click();
  await assertCount(visibleExamples, 17);

  // The full coverage catalog stays usable and independent of gallery filters.
  await page.selectOption('#suite-filter', 'browser');
  await assertCount(visibleCases, 17);
  await page.selectOption('#status-filter', 'unsupported');
  await assertCount(visibleCases, 0);
  assert.equal(await page.locator('#empty-state').isVisible(), true);
  await page.fill('#search', '  TAB_STOP  ');
  await assertCount(visibleCases, 0);
  await page.selectOption('#status-filter', 'unverified');
  await assertCount(visibleCases, 1);
  assert.equal(await page.locator(`${visibleCases} h3`).textContent(), 'tab_stop');
  await page.selectOption('#status-filter', 'unsupported');
  await page.fill('#search', 'text_wrapper');
  await assertCount(visibleCases, 0);
  assert.equal(await page.locator('#empty-state').isVisible(), true);
  await page.selectOption('#status-filter', 'unverified');
  await assertCount(visibleCases, 1);
  assert.equal(await page.locator(`${visibleCases} h3`).textContent(), 'text_wrapper');
  await page.fill('#search', '');
  await assertCount(visibleCases, expectedUnverifiedExamples);
  await page.selectOption('#suite-filter', 'native');
  await assertCount(visibleCases, 2);
  await page.selectOption('#suite-filter', 'headless');
  await page.selectOption('#status-filter', 'pass');
  await assertCount(visibleCases, 131);
  await page.locator('#clear-filters').click();
  await assertCount(visibleCases, 153);
  for (const selector of ['#search', '#suite-filter', '#status-filter']) {
    assert.equal(await page.locator(selector).inputValue(), '');
  }
  assert.deepEqual(await assertReady(), firstRelease);

  looseMode = 'failed';
  await page.reload();
  assert.deepEqual(await assertReady(), firstRelease);
  // A complete previously saved document remains coherent after the server's
  // loose assets change. Only retained image bytes remain external resources.
  const savedResponse = await page.goto(`${origin}/saved-release/`);
  assert.equal(await savedResponse.text(), savedHTML);
  assert.deepEqual(await assertReady(), firstRelease);
  await page.fill('#example-search', 'text_layout');
  await assertCount(visibleExamples, 1);
  await page.locator('#example-filters button[type="reset"]').click();
  await assertCount(visibleExamples, 17);
  assert.deepEqual(await assertReady(), firstRelease);

  // Older cached HTML has no feature-gallery elements. The loose current app
  // must preserve the coverage table and display a refresh notice, not throw.
  for (const fixture of ['legacy-document', 'legacy-data']) {
    await page.goto(`${origin}/${fixture}/`);
    await assertCount(visibleCases, 153);
    assert.equal(await page.locator('#example-list > .example-card').count(), 0);
    assert.equal(await page.locator('#example-list').count(), fixture === 'legacy-document' ? 0 : 1);
    assert.match(await page.locator('#scope-note').textContent(), /古いページまたはカタログ形式/);
    const refresh = page.locator('#scope-note a');
    assert.equal(await refresh.textContent(), '最新版を読み込む');
    const refreshURL = new URL(await refresh.getAttribute('href'), page.url());
    assert.equal(refreshURL.origin, origin);
    assert(refreshURL.searchParams.has('catalog-refresh'));
    for (const asset of ['app.js', 'style.css', 'data.json']) {
      assert(legacyRequests.includes(`/${fixture}/${asset}`), `${fixture} must exercise loose ${asset}`);
    }
    await page.selectOption('#suite-filter', 'browser');
    await assertCount(visibleCases, 17);
    await page.fill('#search', 'text_wrapper');
    await assertCount(visibleCases, 1);
    await page.locator('#clear-filters').click();
    await assertCount(visibleCases, 153);
    assert.deepEqual(errors, []);
  }
  // Reproduce the former catch-handler crash: old HTML has no gallery summary,
  // and loading data fails before any rows exist. Only the intentional HTTP
  // status may reach the console; the recovery UI must not throw another error.
  const failureResponse = page.waitForResponse(response => response.url() === `${origin}/legacy-failure/data.json`);
  await page.goto(`${origin}/legacy-failure/`);
  assert.equal((await failureResponse).status(), 503);
  await page.waitForFunction(() => document.getElementById('scope-note')?.textContent.includes('(503)'));
  assert.equal(await page.locator('#example-list, #examples-summary').count(), 0);
  assert.equal(await page.locator('#case-list > .case-row').count(), 0);
  assert.match(await page.locator('#scope-note').textContent(), /カタログを読み込めませんでした/);
  assert.equal(await page.locator('#scope-note a').textContent(), '最新版を読み込む');
  assert.match(await page.locator('#result-count').textContent(), /テスト一覧を表示できません/);
  assert.deepEqual(pageErrors, [], 'Legacy failure handling must not throw on missing gallery elements');
  assert.deepEqual(errors, [], 'Only the intentional data.json HTTP 503 console error is expected');
  assert(expectedHTTP503Errors.length <= 1);
  assert.deepEqual(looseRequests, []);
  console.log('PASS: atomic catalog; 17 cards, 153 rows, 17 implemented ports (fifteen core GPUI and two gpui_web sources), unverified tab_stop, drag_drop, uniform_list, grid_layout, anchor and popover without borrowed evidence, comparison links, search/filter/reset, repeat load, and saved HTML survive stale/failed loose assets with no loose-asset requests. Legacy HTML/data retain coverage; missing-gallery HTTP 503 recovery has no unhandled errors.');
} finally {
  if (browser) await browser.close();
  server.closeAllConnections();
  await new Promise(done => server.close(done));
}
