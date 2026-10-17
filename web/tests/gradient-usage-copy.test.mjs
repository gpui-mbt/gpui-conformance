import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { selectExample, rustExampleUrl, moonbitExampleUrl } from '../routing.mjs';

const catalog = JSON.parse(readFileSync(new URL('../examples.json', import.meta.url), 'utf8'));
const app = readFileSync(new URL('../app.js', import.meta.url), 'utf8');
const gradientUsage = 'Click the sRGB/Oklab color-space toggle independently in each pane.';
const primeUsage = 'Use the preset and Count Primes controls independently in each pane. CPU work timings are not render-startup benchmarks.';
const anchorUsage = 'Hover the eight buttons independently in each pane. Supported viewport profile: 750 or 480 × 600 at DPR 1; paired conformance remains unverified.';
const staticUsage = 'The upstream example has no interactive controls.';

// Execute the real app with synthetic DOM/network boundaries. This checks host
// copy and routing, not compiled runtime behavior or rendered conformance.
async function loadApp(id, { rustBundled = true, isolated = true, data = catalog } = {}) {
  const elements = new Map();
  const element = () => ({
    textContent: '', hidden: false, style: {}, parentElement: { style: {} }, listeners: {},
    append() {}, removeAttribute(name) { delete this[name]; },
    addEventListener(name, fn) { this.listeners[name] = fn; },
  });
  const get = id => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  const starts = [];
  const location = { href: `https://example.test/lab/?example=${id}` };
  const sandbox = {
    URL, location, crossOriginIsolated: isolated,
    document: { getElementById: get, createElement: element },
    history: { replaceState(_state, _unused, url) { location.href = url.href; } },
    fetch: async path => ({ ok: true, json: async () => path === './examples.json'
      ? data : { rust_bundled: rustBundled, lab_revision: 'test-revision' } }),
    selectExample, rustExampleUrl, moonbitExampleUrl,
    createLoadComparison: () => ({ cancel() {}, start(value) { starts.push(value); } }),
  };
  await vm.runInNewContext(`(async () => {${app.replace(/^import .*;\n/gm, '')}})()`, sandbox);
  return { get, starts, location, select(id) { get('fixture').value = id; get('fixture').listeners.change(); } };
}

function expectedNotice(example, usage, rustBundled = true, isolated = true) {
  return `${example.title} · fixed ${example.width} × ${example.height} logical pixels · ${rustBundled ? 'Both compiled runtimes requested from this origin; rendering results are recorded by browser E2E.' : 'MoonBit port requested; Rust artifact missing.'} ${usage}${rustBundled && !isolated ? ' This host lacks the COOP/COEP headers required by Rust WASM.' : ''}`;
}

test('gradient usage names the current rendered color-space labels', () => {
  const source = readFileSync(new URL('../moonbit/gradient/gradient.mbt', import.meta.url), 'utf8');
  assert.match(source, /if id == 101 \{ if oklab\.val \{ "Oklab" \} else \{ "sRGB" \} \}/);
  assert(app.includes(gradientUsage));
});

test('gradient notice describes its toggle while preserving runtime and isolation notices', async () => {
  const example = selectExample(catalog, 'gradient');
  for (const rustBundled of [true, false]) for (const isolated of [true, false]) {
    const f = await loadApp('gradient', { rustBundled, isolated });
    assert.equal(f.get('notice').textContent, expectedNotice(example, gradientUsage, rustBundled, isolated));
    assert.doesNotMatch(f.get('notice').textContent, /Count Primes|preset|CPU work/);
    assert.equal(f.starts.length, 1);
    assert.equal(f.starts[0].urls.moon, 'https://example.test/lab/moonbit/?example=gradient');
    assert.equal(f.starts[0].urls.rust, rustBundled ? 'https://example.test/lab/rust/?example=gradient' : null);
  }
});

test('all other current routes retain their existing notice text', async () => {
  for (const example of catalog.examples.filter(example => example.id !== 'gradient')) {
    const f = await loadApp(example.id);
    const usage = example.id === 'anchor' ? anchorUsage : example.interactive ? primeUsage : staticUsage;
    assert.equal(f.get('notice').textContent, expectedNotice(example, usage), example.id);
  }
});

test('switching and reloading examples never leaves stale gradient instructions', async () => {
  const f = await loadApp('gradient');
  for (const [id, usage] of [['hello_web', primeUsage], ['gradient', gradientUsage], ['anchor', anchorUsage], ['hello_world', staticUsage], ['gradient', gradientUsage]]) {
    f.select(id);
    assert.equal(f.get('notice').textContent, expectedNotice(selectExample(catalog, id), usage));
    assert.equal(new URL(f.location.href).searchParams.get('example'), id);
  }
  let prevented = false;
  f.get('settings').listeners.submit({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(f.get('notice').textContent, expectedNotice(selectExample(catalog, 'gradient'), gradientUsage));
});

test('a missing gradient implementation keeps the unavailable boundary', async () => {
  const data = structuredClone(catalog);
  selectExample(data, 'gradient').moonbit = 'not_implemented';
  const f = await loadApp('gradient', { data });
  assert.equal(f.get('notice').textContent, `${selectExample(data, 'gradient').title}: gpui.mbt not implemented. Neither runtime is substituted.`);
  assert.equal(f.starts.length, 0);
});
