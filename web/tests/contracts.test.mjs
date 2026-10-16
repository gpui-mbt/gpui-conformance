import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { selectExample, rustExampleUrl, moonbitExampleUrl } from '../routing.mjs';
import { validateFrame, drawFrame, roundedDashSegments } from '../moonbit/site/render.mjs';
const catalog = JSON.parse(await readFile(new URL('../examples.json', import.meta.url), 'utf8'));

test('the catalog maps upstream names rather than substituting Weekboard', () => {
  assert.equal(catalog.examples.length, 13);
  assert.deepEqual(catalog.examples.filter(e => e.moonbit === 'implemented').map(e => e.id), ['hello_world', 'text', 'text_layout', 'text_wrapper', 'input', 'dynamic_fonts', 'hello_web', 'tree', 'scrollable', 'focus_visible', 'tab_stop', 'drag_drop', 'uniform_list']);
  assert.equal(selectExample(catalog, 'hello_world').source, 'crates/gpui/examples/hello_world.rs');
  assert.throws(() => selectExample(catalog, 'unknown'));
});
test('all current browser routes share the published core commit and exact tree', () => {
  assert.equal(catalog.upstream.revision, '5a5fbe79917971a4d52a96b6ddb04da198a5012e');
  assert.equal(catalog.moonbit.revision, 'b9916950350b7d433ecca0d6fa88e39c957b8b6b');
  assert.equal(catalog.moonbit.tree, 'be95df375c707bd6cf961ef7959e93772b34a966');
  const routes = {hello_world:'hello-world',text:'text',text_layout:'text-layout',
    text_wrapper:'text-wrapper',input:'input',dynamic_fonts:'dynamic-fonts',
    hello_web:'prime-sieve',tree:'tree',scrollable:'scrollable',focus_visible:'focus-visible',tab_stop:'tab-stop',drag_drop:'drag-drop',uniform_list:'uniform-list'};
  assert.deepEqual(Object.fromEntries(catalog.examples.map(example => [example.id, example.rust_route])), routes);
  assert.equal(catalog.examples.filter(example => example.source.startsWith('crates/gpui/examples/')).length, 11);
  assert.deepEqual(catalog.examples.filter(example => example.source.startsWith('crates/gpui_web/examples/')).map(example => example.id),
    ['dynamic_fonts', 'hello_web']);
  for (const example of catalog.examples.filter(example => example.moonbit === 'implemented')) {
    assert.equal(rustExampleUrl('https://example.test/lab/', example), `https://example.test/lab/rust/?example=${example.id}`);
    assert.equal(moonbitExampleUrl('https://example.test/lab/', example), `https://example.test/lab/moonbit/?example=${example.id}`);
  }
});
test('a selected example resolves the same pair under a GitHub Pages subpath', () => {
  const example = selectExample(catalog, 'hello_world');
  assert.equal(rustExampleUrl('https://example.test/gpui-conformance/', example), 'https://example.test/gpui-conformance/rust/?example=hello_world');
  assert.equal(moonbitExampleUrl('https://gpui-mbt.github.io/gpui-conformance/?example=hello_world', example), 'https://gpui-mbt.github.io/gpui-conformance/moonbit/?example=hello_world');
});
test('missing implementations and runtimes cannot be treated as a pair', () => {
  // Rust-only baseline entries must never imply a compiled candidate pair.
  const missing = { id: 'unimplemented_fixture', moonbit: 'not_implemented' };
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
  assert.equal(catalog.moonbit.revision, 'b9916950350b7d433ecca0d6fa88e39c957b8b6b');
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

test('Prime sieve routes the real interactive 640x560 pair with unchanged source pins',async()=>{
  const example=selectExample(catalog,'hello_web');
  assert.deepEqual([example.width,example.height,example.interactive],[640,560,true]);
  assert.equal(example.source,'crates/gpui_web/examples/hello_web/main.rs');
  assert.equal(example.source_blob,'31f30431e2a15963d7277047d0301e2510a90616');
  assert.equal(rustExampleUrl('https://example.test/lab/',example),'https://example.test/lab/rust/?example=hello_web');
  assert.equal(moonbitExampleUrl('https://example.test/lab/',example),'https://example.test/lab/moonbit/?example=hello_web');
  const source=await readFile(new URL('../../'+example.candidate_source,import.meta.url),'utf8');
  for(const api of ['request_layout','prepaint','paint_snapshot','dispatch_pointer']) assert(source.includes(api));
  const worker=await readFile(new URL('../moonbit/site/prime-worker.mjs',import.meta.url),'utf8');
  assert.match(worker,/import \{ hello_web_count \} from '.\/hello_web.mjs'/);
  assert.match(worker,/hello_web_count\(start, end\)/);
});
test('rounded fills are explicit validated host extensions and never implicit scene capabilities',()=>{
  const f=frame();f.decorations=[];f.rounded_fills=[{id:1,radius:6}];
  validateFrame(f);
  f.rounded_fills[0].id=999;assert.throws(()=>validateFrame(f));
  f.rounded_fills[0].id=1;f.rounded_fills[0].radius=17;assert.throws(()=>validateFrame(f));
  f.rounded_fills[0].radius=NaN;assert.throws(()=>validateFrame(f));
});

test('text uses its pinned, interactive upstream typography pair', async () => {
  const example = selectExample(catalog,'text');
  assert.equal(example.source,'crates/gpui/examples/text.rs');
  assert.equal(example.candidate_source,'web/moonbit/text/text.mbt');
  assert.deepEqual([example.width,example.height,example.interactive],[920,720,true]);
  assert.match(example.source_blob,/^[0-9a-f]{40}$/);
  assert.equal(rustExampleUrl('https://example.test/lab/',example),'https://example.test/lab/rust/?example=text');
  assert.equal(moonbitExampleUrl('https://example.test/lab/',example),'https://example.test/lab/moonbit/?example=text');
  const source=await readFile(new URL('../../web/moonbit/text/text.mbt',import.meta.url),'utf8');
  for(const fragment of ['text_characters()', 'text_scales()', 'request_layout','prepaint','paint_snapshot','text_frame']) {
    assert(source.includes(fragment),'Missing typography component: '+fragment);
  }
});
test('scroll extension clips only body items and rejects out-of-range geometry', () => {
  const f=frame();
  f.snapshot.items.push({id:100,kind:'quad',bounds:{x:0,y:60,width:12,height:16},
    color:{red:0,green:0,blue:0,alpha:255}});
  f.scroll={first_id:100,top:52,height:668,y:50,max:100};
  const calls=[];
  const ctx=new Proxy({}, {get:(_obj,key)=>(...args)=>calls.push([key,...args])});
  drawFrame(ctx,f,{width:920,height:720},1);
  assert.deepEqual(calls.filter(c=>c[0]==='translate'),[['translate',0,-50]]);
  assert(calls.some(c=>JSON.stringify(c)==='["rect",0,52,920,668]'));
  f.scroll.y=101;
  assert.throws(()=>validateFrame(f),/scroll/);
});

test('input uses real upstream source, the MoonBit TextField, and an isolated browser transport', async () => {
  const example = selectExample(catalog, 'input');
  assert.deepEqual([example.width, example.height, example.interactive], [300,300,true]);
  assert.equal(example.candidate_source, 'web/moonbit/input/input.mbt');
  assert.equal(example.source_blob, '106d06dc7e3ab225d0fda1aee009f601767b34da');
  assert.equal(moonbitExampleUrl('https://example.test/lab/',example), 'https://example.test/lab/moonbit/?example=input');
  const source = await readFile(new URL('../moonbit/input/input.mbt', import.meta.url), 'utf8');
  for (const symbol of ['@text_field.TextField::new', 'update_composition', 'commit_composition', 'cancel_composition', 'paint_items', 'request_layout', 'SceneSnapshot::new']) {
    assert(source.includes(symbol), symbol);
  }
  const host = await readFile(new URL('../moonbit/site/input-host.mjs', import.meta.url), 'utf8');
  for (const event of ['compositionstart', 'compositionupdate', 'compositionend', 'beforeinput', 'copy', 'cut', 'paste']) assert(host.includes(event));
  assert(!host.includes('new TextField('));
});
test('text_run host draws a translated run but rejects unsafe geometry', () => {
  const f=frame(); f.decorations=[];
  f.snapshot.items.push({kind:'text_run',id:9,bounds:{x:0,y:0,width:20,height:30},
    text_origin:{x:2,y:1},text:'hi',font_size:24,color:{red:0,green:0,blue:0,alpha:255},
    transform:{a:1,b:0,c:0,d:1,tx:12,ty:34}});
  const calls=[];
  const ctx=new Proxy({}, {get:(_obj,key)=>(...args)=>{calls.push([key,...args]);if(key==='measureText')return {width:20,fontBoundingBoxAscent:20,fontBoundingBoxDescent:4};}});
  drawFrame(ctx,f,{width:300,height:300,font_family:'IBM Plex Sans'},1);
  assert(calls.some(call=>call[0]==='fillText' && call[1]==='hi' && call[2]===14));
  f.snapshot.items[1].transform.a=2;
  assert.throws(()=>validateFrame(f));
});


test('tree is a source-pinned, font-free 51-level real Element pair', async () => {
  const example = selectExample(catalog, 'tree');
  assert.equal(example.source_blob, '891be4790a59ae258da3380d2ef54fba26979346');
  assert.deepEqual([example.width,example.height,example.interactive], [300,300,false]);
  assert.equal(rustExampleUrl('https://example.test/lab/', example), 'https://example.test/lab/rust/?example=tree');
  const source = await readFile(new URL('../../' + example.candidate_source, import.meta.url), 'utf8');
  for (const api of ['Dimension::auto()', 'with_child', 'request_layout', 'prepaint', 'paint_snapshot']) assert(source.includes(api));
  assert(!source.includes('SceneItem::quad'));
});

test('scrollable routes the pinned core-backed nested viewport pair', async () => {
  const example=selectExample(catalog,'scrollable');
  assert.deepEqual([example.width,example.height,example.interactive],[500,500,true]);
  assert.equal(example.source_blob,'c81795618875aecf06e06043bd1709c48630b58f');
  assert.equal(catalog.moonbit.revision,'b9916950350b7d433ecca0d6fa88e39c957b8b6b');
  assert.equal(rustExampleUrl('https://example.test/lab/',example),'https://example.test/lab/rust/?example=scrollable');
  assert.equal(moonbitExampleUrl('https://example.test/lab/',example),'https://example.test/lab/moonbit/?example=scrollable');
  const source=await readFile(new URL('../../'+example.candidate_source,import.meta.url),'utf8');
  for(const api of ['with_scroll_offset','scroll_viewport','tree.scroll_wheel','dispatch_pointer','request_layout_with_device_scale','paint_snapshot'])
    assert(source.includes(api),api);
  const host=await readFile(new URL('../moonbit/site/scrollable-host.mjs',import.meta.url),'utf8');
  assert(host.includes('runtime.scrollable_wheel'));
  assert(!host.includes('scrollLeft')&&!host.includes('scrollTop')&&!host.includes('context.translate'));
});

test('focus_visible is a pinned interactive core-backed candidate with unverified browser parity', async () => {
  const example = selectExample(catalog, 'focus_visible');
  assert.equal(example.title, 'Focus-visible');
  assert.equal(example.rust_route, 'focus-visible');
  assert.equal(example.source, 'crates/gpui/examples/focus_visible.rs');
  assert.equal(example.source_blob, 'c5b3d5dfec3a189d088a621baff55eb55a121b6c');
  assert.equal(example.candidate_source, 'web/moonbit/focus_visible/focus_visible.mbt');
  assert.equal(example.moonbit, 'implemented');
  assert.deepEqual([example.width, example.height, example.interactive], [800,600,true]);
  assert.throws(() => selectExample(catalog, 'focus-visible'), /Unknown upstream example/);
  const source = await readFile(new URL('../../' + example.candidate_source, import.meta.url), 'utf8');
  for (const api of ['@element.Element::root', 'request_layout_with_device_scale', '.prepaint()',
    'paint_snapshot', 'tree.dispatch_input', 'tree.focus_prev()', 'tree.focus_next()',
    'tree.focus_owner()', 'tree.is_focus_visible', 'state.modality.after_input']) assert(source.includes(api), api);
  const host = await readFile(new URL('../moonbit/site/focus-visible-host.mjs', import.meta.url), 'utf8');
  for (const name of ['focus_visible_pointer', 'focus_visible_key', 'focus_visible_wheel', 'focus_visible_leave'])
    assert(host.includes(`runtime.${name}`), name);
  assert(!host.includes('setPointerCapture'));
  for (const boundary of ['persistent input tree', 'core flat tab traversal', 'focus ownership',
    'host boundaries', 'paired browser execution', 'pixel qualification remain unverified',
    'Nested tab groups', 'touch', 'pointer capture', 'native', 'full-image', 'text parity'])
    assert(example.implementation_note.includes(boundary), boundary);
  // Source/runtime wiring checks do not provide a measurement or a saved image.
  for (const key of ['result_url', 'result_date', 'changed_pixels', 'total_pixels', 'thumbnail', 'evidence_scope'])
    assert.equal(example[key], undefined, key);
});


test('pinned PNG decoder is installed before independent comparator unit tests', async () => {
  const workflow = await readFile(new URL('../../.github/workflows/browser-examples.yml', import.meta.url), 'utf8');
  const install = 'python3 -m pip install Pillow==12.0.0';
  assert.equal(workflow.split(install).length - 1, 1, 'One shared exact decoder version');
  const decoder = workflow.indexOf(install);
  const unitTests = workflow.indexOf('node --test web/tests/*.test.mjs');
  assert(decoder >= 0 && unitTests > decoder, 'PNG-decoding unit tests require Pillow before the host gate');
  assert(workflow.indexOf('node web/tests/compare-focus-visible-results.mjs') > unitTests,
    'Retained browser evidence uses the same installed decoder later');
});

test('tab_stop is a source-pinned genuine group candidate without borrowed runtime qualification', async () => {
  const entry = selectExample(catalog, 'tab_stop');
  assert.equal(entry.moonbit, 'implemented'); assert.equal(entry.rust, undefined);
  assert.equal(entry.source_blob, 'cc7c34a9979ce4027578ec2c358f503d944ee26f');
  assert.equal(entry.source, 'crates/gpui/examples/tab_stop.rs');
  assert.equal(entry.candidate_source, 'web/moonbit/tab_stop/tab_stop.mbt');
  assert.equal(rustExampleUrl('https://example.test/lab/', entry), 'https://example.test/lab/rust/?example=tab_stop');
  assert.equal(moonbitExampleUrl('https://example.test/lab/', entry), 'https://example.test/lab/moonbit/?example=tab_stop');
  const source = await readFile(new URL('../../' + entry.candidate_source, import.meta.url), 'utf8');
  for (const api of ['@element.Element::root', 'request_layout_with_device_scale', '.prepaint()', 'paint_snapshot', 'tree.with_layout_bounds(prepainted)', '.with_tab_group_index(Some(group_index))', 'tree.focus_prev()', 'tree.focus_next()', 'tree.focus_owner()', 'state.modality.after_input']) assert(source.includes(api), api);
  const adapter = await readFile(new URL('../moonbit/site/tab-stop-host.mjs', import.meta.url), 'utf8');
  assert(adapter.includes('createFocusVisibleHost'));
  for (const forbidden of ['focus_next','focus_prev','getBoundingClientRect','tab_order','pending_keyboard','message =']) assert(!adapter.includes(forbidden),forbidden);
  for (const key of ['result_url','result_date','changed_pixels','total_pixels','thumbnail','evidence_scope']) assert.equal(entry[key], undefined,key);
  assert(entry.implementation_note.includes('remain unverified'));
});


test('drag_drop uses a source-pinned typed core session without borrowed qualification', async () => {
  const entry=selectExample(catalog,'drag_drop');
  assert.equal(entry.moonbit,'implemented');assert.equal(entry.rust,undefined);
  assert.equal(entry.source_blob,'8f038ef3308fee9b097e7289665c9fa47cd6945b');
  assert.equal(entry.source,'crates/gpui/examples/drag_drop.rs');
  assert.equal(entry.candidate_source,'web/moonbit/drag_drop/drag_drop.mbt');
  assert.deepEqual([entry.width,entry.height,entry.interactive],[800,600,true]);
  const source=await readFile(new URL('../../'+entry.candidate_source,import.meta.url),'utf8');
  for(const api of ['@element.DragSession[DragInfo]','@element.DragSession::new()',
    '@element.Element::root','request_layout_with_device_scale','.prepaint()',
    '.paint_snapshot(scale)','state.session.dispatch','@element.Dropped(target, payload)'])
    assert(source.includes(api),api);
  const adapter=await readFile(new URL('../moonbit/site/drag-drop-host.mjs',import.meta.url),'utf8');
  for(const forbidden of ['DragSession','Math.hypot','drop_on','cursor_offset','source_id','target_id'])
    assert(!adapter.includes(forbidden),forbidden);
  for(const key of ['result_url','result_date','changed_pixels','total_pixels','thumbnail','evidence_scope'])
    assert.equal(entry[key],undefined,key);
  for(const boundary of ['typed core DragSession','host boundaries','native','GPU shadow-kernel','full-image parity remain unverified'])
    assert(entry.implementation_note.includes(boundary),boundary);
});

test('uniform-list registration states its strict typography limitation', async () => {
  const entry=selectExample(catalog,'uniform_list');
  assert.equal(entry.source,'crates/gpui/examples/uniform_list.rs');
  assert.equal(entry.source_blob,'4a2c4788b192d802ee3d51714c250e7c5a82db76');
  assert.equal(entry.candidate_source,'web/moonbit/uniform_list/uniform_list.mbt');
  assert.deepEqual([entry.width,entry.height],[300,300]);
  assert.match(entry.implementation_note,/Strict text-envelope.*right-edge.*Item 3/);
  assert.match(entry.implementation_note,/not a passed full-text comparison/);
  assert.match(entry.implementation_note,/font-free GPUI diagnostic/);
});
