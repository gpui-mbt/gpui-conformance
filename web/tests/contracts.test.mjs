import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { selectExample, rustExampleUrl, moonbitExampleUrl } from '../routing.mjs';
import { validateFrame, drawFrame, roundedDashSegments } from '../moonbit/site/render.mjs';
const catalog = JSON.parse(await readFile(new URL('../examples.json', import.meta.url), 'utf8'));

test('the catalog maps upstream names rather than substituting Weekboard', () => {
  assert.equal(catalog.examples.length, 7);
  assert.deepEqual(catalog.examples.filter(e => e.moonbit === 'implemented').map(e => e.id), ['hello_world', 'text_layout', 'text_wrapper']);
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
  return { ok: true, conformance: 'unverified', snapshot: { schema_version: 1, items: [{ id: 1, kind: 'quad', bounds: { x: 0, y: 0, width: 32, height: 32 }, color: { red: 255, green: 0, blue: 0, alpha: 255 } }] }, decorations: [{ id: 1, radius: 6, border_width: 1, border: '#ffffff', border_style: 'dashed' }] };
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
  const invalidRadius = frame(); invalidRadius.decorations[0].radius = 100;
  assert.throws(() => drawFrame(context, invalidRadius, { width: 500, height: 500 }, 1));
  assert.equal(calls, 0);
});
test('the canvas adapter uses MoonBit-provided bounds and border styles', () => {
  const calls = [];
  const context = new Proxy({}, { get: (_object, key) => (...args) => { calls.push([key, ...args]); } });
  drawFrame(context, frame(), { width: 500, height: 500 }, 2);
  assert(calls.some(call => JSON.stringify(call) === JSON.stringify(['roundRect', 0, 0, 32, 32, 6])));
  assert.equal(calls.filter(call => call[0] === 'moveTo').length, 39);
  assert(calls.some(call => call[0] === 'arc'));
  assert(calls.every(call => call[0] !== 'setLineDash' || call[1].length === 0));
});
test('the page preserves a visible unverified boundary and clears stale runtime frames', async () => {
  const html = await readFile(new URL('../index.html', import.meta.url), 'utf8');
  const app = await readFile(new URL('../app.js', import.meta.url), 'utf8');
  assert.match(html, /Conformance: UNVERIFIED/);
  assert.match(app, /clearFrames\(\)/);
  assert(!html.includes('Weekboard'));
  assert(!app.includes('gpui-mbt.github.io/gpui.mbt'));
});

test('32px rounded borders have 39 two-pixel dashes starting at the top-left tangent', () => {
  const layout = roundedDashSegments({x:134,y:256,width:32,height:32}, 6, 1);
  assert.equal(layout.count, 39);
  assert.equal(layout.dash_length, 2);
  assert(Math.abs(layout.perimeter - (80 + 12 * Math.PI)) < 1e-10);
  assert(Math.abs(layout.period * layout.count - layout.perimeter) < 1e-10);
  assert.deepEqual(layout.dashes[0], [['moveTo',140,256.5],['lineTo',142,256.5]]);
  assert(layout.period - layout.dash_length > 1);
  assert.throws(() => roundedDashSegments({x:0,y:0,width:32,height:32}, 0, 1));
});


test('text_layout routes the real second pair and retains its upstream viewport', () => {
  const example = selectExample(catalog, 'text_layout');
  assert.equal(example.source, 'crates/gpui/examples/text_layout.rs');
  assert.equal(example.candidate_source, 'web/moonbit/text_layout/text_layout.mbt');
  assert.deepEqual([example.width, example.height, example.interactive], [800, 600, false]);
  assert.equal(rustExampleUrl('https://example.test/lab/', example), 'https://example.test/lab/rust/?example=text_layout');
  assert.match(example.source_blob, /^[0-9a-f]{40}$/);
});

test('text_wrapper routes the real third pair with pinned sources and its upstream viewport', async () => {
  const example = selectExample(catalog, 'text_wrapper');
  assert.equal(catalog.upstream.revision, '5a5fbe79917971a4d52a96b6ddb04da198a5012e');
  assert.equal(catalog.moonbit.revision, '01818aa4e96fc21d1676f747a6b23d91445648a1');
  assert.equal(example.source, 'crates/gpui/examples/text_wrapper.rs');
  assert.equal(example.candidate_source, 'web/moonbit/text_wrapper/text_wrapper.mbt');
  assert.deepEqual([example.width, example.height, example.interactive], [800, 600, false]);
  assert.match(example.source_blob, /^[0-9a-f]{40}$/);
  assert.equal(rustExampleUrl('https://example.test/gpui-conformance/', example), 'https://example.test/gpui-conformance/rust/?example=text_wrapper');
  assert.equal(moonbitExampleUrl('https://example.test/gpui-conformance/', example), 'https://example.test/gpui-conformance/moonbit/?example=text_wrapper');
  // The link points to actual candidate source, not a substitute or generated frame.
  const source = await readFile(new URL('../../' + example.candidate_source, import.meta.url), 'utf8');
  assert.match(source, /request_layout/);
  assert.match(source, /prepaint/);
  assert.match(source, /snapshot/);
  const app = await readFile(new URL('../app.js', import.meta.url), 'utf8');
  assert(app.includes('catalog.upstream.revision}/${example.source}'));
  assert(app.includes('build.lab_revision}/${example.candidate_source}'));
});

test('text styling and clipping are validated before drawing', () => {
  const f = frame();
  f.snapshot.items.push({id:2,kind:'text',bounds:{x:3,y:5,width:10,height:26},color:{red:0,green:0,blue:0,alpha:255},text:'A',font_size:16,clip_chain_id:7});
  f.snapshot.clip_chains = [{id:7,rects:[{x:1,y:2,width:30,height:40}]}];
  f.text_styles = [{id:2,style:'italic',weight:800,decoration:'underline'}];
  const calls = [];
  const ctx = new Proxy({}, {get:(_object,key) => (...args) => {
    calls.push([key,...args]);
    if (key === 'measureText') return {width:10,fontBoundingBoxAscent:16,fontBoundingBoxDescent:4};
  }});
  drawFrame(ctx,f,{width:800,height:600,font_family:'IBM Plex Sans'},1);
  assert(calls.some(c => JSON.stringify(c) === JSON.stringify(['rect',1,2,30,40])));
  assert(calls.some(c => c[0] === 'fillRect' && c[1] === 3 && c[3] === 10));
  f.text_styles[0].weight = 900;
  assert.throws(() => validateFrame(f));
  f.text_styles[0].weight = 800;
  f.snapshot.items[1].clip_chain_id = 99;
  assert.throws(() => validateFrame(f));
});
