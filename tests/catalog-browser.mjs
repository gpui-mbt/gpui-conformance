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
const legacyHTML = sourceHTML.replace(/\s*<section\b[^>]*class="examples-section"[^>]*>[\s\S]*?<\/section>/, '');
assert(!legacyHTML.includes('id="example-list"'), 'The legacy document fixture must omit the entire gallery');
const legacyData = JSON.parse(await readFile(join(site, 'data.json'), 'utf8'));
for (const example of legacyData.browser_examples) {
  delete example.implementation;
  delete example.feature_tags;
}
const rawLabBase = (process.env.CATALOG_BROWSER_LAB_BASE_URL || '').trim();
const labBase = rawLabBase ? new URL(rawLabBase).origin : '';
const implemented = ['hello_world', 'text_layout', 'text_wrapper'];
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
    await assertCount('#example-list > .example-card', 7);
    await assertCount('#case-list > .case-row', 143);
    await assertCount(visibleExamples, 7);
    await assertCount(visibleCases, 143);
    assert.equal(await page.locator('#example-count').textContent(), '7 / 7 examples を表示');
    assert.equal(await page.locator('#result-count').textContent(), '143 / 143 件を表示');
    assert.equal(await page.locator('#examples-empty').isVisible(), false);
    assert.equal(await page.locator('#empty-state').isVisible(), false);
    assert.equal(await page.locator('script[src], link[rel="stylesheet"]').count(), 0,
      'The generated document must carry its own application and styles');
    assert.equal(await page.locator('script#catalog-data[type="application/json"]').count(), 1);
    const previews = page.locator('#example-list .example-preview img');
    assert.equal(await previews.count(), 3, 'Each implemented example has its own retained capture');
    assert.equal(await page.locator('#example-list a').evaluateAll(nodes => nodes.filter(node => node.textContent === '撮影記録').length), 2);
    assert.equal(await page.locator('#example-list a').evaluateAll(nodes => nodes.filter(node => node.textContent === 'gpui.rs の保存画像').length), 2);
    assert.equal(await page.locator('#example-list').evaluate(node => getComputedStyle(node).display), 'grid',
      'Embedded styles must apply even when loose CSS is stale or unavailable');
    // Finish lazy image requests before navigating again, and verify retained
    // evidence images also resolve relative to the saved-document route.
    for (const image of await page.locator('.example-preview img').all()) {
      await image.scrollIntoViewIfNeeded();
      await image.evaluate(node => node.decode());
    }
    assert.deepEqual(await previews.evaluateAll(nodes => nodes.map(node => [node.naturalWidth, node.naturalHeight])),
      [[500, 500], [800, 600], [800, 600]]);
    const data = await page.locator('#catalog-data').evaluate(node => JSON.parse(node.textContent));
    assert.equal(data.browser.implemented_count, 3);
    assert.deepEqual(await page.locator('.example-card[data-implementation="implemented"] .example-id').allTextContents(), implemented);
    assert.equal(await page.locator('#catalog-revision').textContent(), `Catalog source ${data.revision.slice(0, 12)}`);
    const comparisonLinks = await page.locator('#example-list a').evaluateAll(nodes =>
      nodes.filter(node => node.textContent === 'ライブ比較を開く').map(node => node.href).sort());
    assert.deepEqual(comparisonLinks, labBase ? implemented.map(id => `${labBase}/?example=${id}`).sort() : []);
    assert.equal(await page.locator('#case-list a').evaluateAll(nodes =>
      nodes.filter(node => node.textContent === 'ライブ比較').length), labBase ? 3 : 0);
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
  await assertCount(visibleExamples, 3);
  await page.fill('#example-search', '  TEXT_WRAPPER  ');
  await assertCount(visibleExamples, 1);
  assert.equal(await page.locator(`${visibleExamples} .example-id`).textContent(), 'text_wrapper');
  await page.selectOption('#implementation-filter', 'not_implemented');
  await assertCount(visibleExamples, 0);
  assert.equal(await page.locator('#examples-empty').isVisible(), true);
  await page.fill('#example-search', '');
  await assertCount(visibleExamples, 4);
  await page.locator('#example-filters button[type="reset"]').click();
  await assertCount(visibleExamples, 7);
  assert.equal(await page.locator('#implementation-filter').inputValue(), '');
  assert.equal(await page.locator('#example-search').inputValue(), '');

  // The full coverage catalog stays usable and independent of gallery filters.
  await page.selectOption('#suite-filter', 'browser');
  await assertCount(visibleCases, 7);
  await page.selectOption('#status-filter', 'unsupported');
  await assertCount(visibleCases, 4);
  await page.fill('#search', 'text_wrapper');
  await assertCount(visibleCases, 0);
  assert.equal(await page.locator('#empty-state').isVisible(), true);
  await page.selectOption('#status-filter', 'unverified');
  await assertCount(visibleCases, 1);
  assert.equal(await page.locator(`${visibleCases} h3`).textContent(), 'text_wrapper');
  await page.fill('#search', '');
  await page.selectOption('#suite-filter', 'native');
  await assertCount(visibleCases, 2);
  await page.selectOption('#suite-filter', 'headless');
  await page.selectOption('#status-filter', 'pass');
  await assertCount(visibleCases, 131);
  await page.locator('#clear-filters').click();
  await assertCount(visibleCases, 143);
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
  await assertCount(visibleExamples, 7);
  assert.deepEqual(await assertReady(), firstRelease);

  // Older cached HTML has no feature-gallery elements. The loose current app
  // must preserve the coverage table and display a refresh notice, not throw.
  for (const fixture of ['legacy-document', 'legacy-data']) {
    await page.goto(`${origin}/${fixture}/`);
    await assertCount(visibleCases, 143);
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
    await assertCount(visibleCases, 7);
    await page.fill('#search', 'text_wrapper');
    await assertCount(visibleCases, 1);
    await page.locator('#clear-filters').click();
    await assertCount(visibleCases, 143);
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
  console.log('PASS: atomic catalog; 7 cards, 143 rows, 3 implemented ports, comparison links, search/filter/reset, repeat load, and saved HTML survive stale/failed loose assets with no loose-asset requests. Legacy HTML/data retain coverage; missing-gallery HTTP 503 recovery has no unhandled errors.');
} finally {
  if (browser) await browser.close();
  server.closeAllConnections();
  await new Promise(done => server.close(done));
}
