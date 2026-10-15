import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { selectExample, rustExampleUrl, moonbitExampleUrl } from '../routing.mjs';
import { validateFrame, drawFrame } from '../moonbit/site/render.mjs';
const catalog = JSON.parse(await readFile(new URL('../examples.json', import.meta.url), 'utf8'));

test('the catalog maps upstream names rather than substituting Weekboard', () => {
  assert.equal(catalog.examples.length, 7);
  assert.deepEqual(catalog.examples.filter(e => e.moonbit === 'implemented').map(e => e.id), ['hello_world']);
  assert.equal(selectExample(catalog, 'hello_world').source, 'crates/gpui/examples/hello_world.rs');
  assert.throws(() => selectExample(catalog, 'unknown'));
});
test('a selected example resolves the same pair under a GitHub Pages subpath', () => {
  const example = selectExample(catalog, 'hello_world');
  assert.equal(rustExampleUrl('https://example.test/gpui-conformance/', example), 'https://example.test/gpui-conformance/rust/?example=hello_world');
  assert.equal(moonbitExampleUrl('https://gpui-mbt.github.io/gpui-conformance/?example=hello_world', example), 'https://gpui-mbt.github.io/gpui-conformance/moonbit/?example=hello_world');
});
test('missing implementations and runtimes cannot be treated as a pair', () => {
  const missing = selectExample(catalog, 'input');
  assert.equal(moonbitExampleUrl('https://example.test/lab/', missing), null);
  assert.equal(rustExampleUrl('https://example.test/lab/', missing), null);
});
function frame() {
  return { ok: true, conformance: 'unverified', snapshot: { schema_version: 1, items: [{ id: 1, kind: 'quad', bounds: { x: 0, y: 0, width: 32, height: 32 }, color: { red: 255, green: 0, blue: 0, alpha: 255 } }] }, decorations: [{ id: 1, radius: 6, border_width: 1, border: '#ffffff', dash: [3, 3] }] };
}
test('the host refuses a fabricated pass and unsupported scene primitives', () => {
  assert.throws(() => validateFrame({ ...frame(), conformance: 'pass' }));
  const bad = frame(); bad.snapshot.items[0].kind = 'image';
  assert.throws(() => validateFrame(bad));
  const unknown = frame(); unknown.decorations[0].id = 2;
  assert.throws(() => validateFrame(unknown));
});
test('the host validates every item before making drawing calls', () => {
  const bad = frame(); bad.snapshot.items[0].color.red = -1;
  let calls = 0;
  const context = new Proxy({}, { get: () => () => { calls++; } });
  assert.throws(() => drawFrame(context, bad, { width: 500, height: 500 }, 1));
  assert.equal(calls, 0);
});
test('the canvas adapter uses MoonBit-provided bounds and border styles', () => {
  const calls = [];
  const context = new Proxy({}, { get: (_object, key) => (...args) => { calls.push([key, ...args]); } });
  drawFrame(context, frame(), { width: 500, height: 500 }, 2);
  assert(calls.some(call => JSON.stringify(call) === JSON.stringify(['roundRect', 0, 0, 32, 32, 6])));
  assert(calls.some(call => call[0] === 'setLineDash' && JSON.stringify(call[1]) === '[3,3]'));
});
test('the page preserves a visible unverified boundary and clears stale runtime frames', async () => {
  const html = await readFile(new URL('../index.html', import.meta.url), 'utf8');
  const app = await readFile(new URL('../app.js', import.meta.url), 'utf8');
  assert.match(html, /Conformance: UNVERIFIED/);
  assert.match(app, /clearFrames\(\)/);
  assert(!html.includes('Weekboard'));
  assert(!app.includes('gpui-mbt.github.io/gpui.mbt'));
});
