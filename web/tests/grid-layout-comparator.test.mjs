import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {GRID_LAYOUT,assertProvenance,provenanceNegativeControls,discoverGeometry,inspectLayout,sourceExpectations,makeProfile,validateProfile,validateOperations,profileNegativeControls,assertCurrentBuild,sha256} from './grid-layout-comparator.mjs';
import {validateReport,verifyBehavior,validateCaptureBindings,validateRuntimeResponses,assertExecutedBytes,evidenceNegativeControls,inputEvidence,validateInputEvidence,requiresRuntimeRetention,assertRetainedSupport} from './grid-layout-runtime-evidence.mjs';
import {RUST_WORKER,deriveRustWorkerBytes,evidenceFilename} from './grid-layout-worker-evidence.mjs';
import {frame,pixels,provenance,fixture} from './fixtures/grid-layout-fixtures.mjs';

test('synthetic source-only provenance keeps exact engine/source/catalog and all eight fonts',()=>{
  const {build,catalog}=provenance();assert.equal(assertProvenance(build,catalog).source_blob,GRID_LAYOUT.sourceBlob);
  assert(provenanceNegativeControls(build,catalog).every(entry=>entry.rejected));
  for(const mutate of [b=>{b.rust.files['index.html']='0'.repeat(64);},b=>{b.rust.files['Cargo.lock']='0'.repeat(64);},
    b=>{b.rust.source_revision='d9afb21688e04f89d9e94d96d33eb530aef90886';},b=>{b.rust_oracle_only[0].width=800;}]) {
    const b=structuredClone(build);mutate(b);assert.throws(()=>assertProvenance(b,catalog));
  }
  const changed=structuredClone(catalog);changed.examples.push({id:'grid_layout',moonbit:'implemented'});
  assert.throws(()=>assertProvenance(build,changed));
});
test('synthetic solid-color bounds are discovered independently from source expectations',()=>{
  for(const width of [399,400,401,500])for(const inset of [0,1]) {
    const image=frame(width,inset),geometry=discoverGeometry(image),expected=sourceExpectations(width);
    assert.equal(geometry.regions.content.left,Math.ceil(expected.regions.content.left+inset));
    assert.equal(geometry.regions.content.bottom,Math.floor(expected.regions.content.bottom-inset));
    assert.equal(inspectLayout(image).source_expectations.mode,width<400?'stack':'grid');
  }
  const displaced=frame(500);displaced.data.copyWithin(500*4,0,499*500*4);
  assert.equal(discoverGeometry(displaced).regions.toc.top,discoverGeometry(frame(500)).regions.toc.top+1);
});
test('synthetic independent viewport evidence covers breakpoint and repeated resize restoration',()=>{
  const {report,retained}=fixture();assert.equal(validateOperations(report).requested_resizes,7);
  assert.equal(validateProfile(retained.images).threshold,'399 stacks;400/401/500 use grid');
  const changed=structuredClone(report);changed.events.reverse();assert.throws(()=>validateOperations(changed));
});
test('corrupted evidence controls reject missing/moved fills, wrong threshold/order/spans/gaps and resize delivery',()=>{
  const {report,retained}=fixture(),controls=profileNegativeControls(retained.images,report);
  assert(controls.length>=19);assert(controls.every(c=>c.rejected&&c.kind==='corrupted_evidence_sensitivity_not_executed_mutant'));
});
test('no blank, translucent, wrong-sized or outline-only image provides solid regions',()=>{
  for(const mutate of [image=>image.data.fill(255),image=>{image.width=299;},image=>{image.data[3]=254;},
    image=>{for(let p=0;p<image.width*image.height;p++)if(image.data[p*4]===255&&image.data[p*4+1]===0)image.data.set([80,80,80,255],p*4); }]) {
    const image=frame();mutate(image);assert.throws(()=>discoverGeometry(image));
  }
});
test('original pixels, rather than reported geometry or pass flags, control results',()=>{
  const {report,retained}=fixture();report.discovered_geometry={content:{left:1}};report.passed=true;
  for(const capture of Object.values(report.captures)){capture.expected={};capture.pass=true;}
  assert.equal(verifyBehavior(report,retained).paint.observations.threshold400.source_expectations.mode,'grid');
});
test('synthetic v3-style execution provenance requires HTML, loader, wasm and actual generated worker response',()=>{
  const {report,retained}=fixture();validateReport(report,'rust');assertExecutedBytes(report,retained);
  const controls=evidenceNegativeControls(report,retained);assert(controls.length>=10);assert(controls.every(c=>c.rejected));
  for(const path of ['rust/index.html','rust/grid_layout.js','rust/grid_layout_bg.wasm']) {
    const copy=structuredClone(report);copy.runtime_responses=copy.runtime_responses.filter(r=>r.path!==path);
    assert.throws(()=>validateRuntimeResponses(copy));
  }
  const workerless=structuredClone(report);workerless.runtime_responses=workerless.runtime_responses.filter(r=>!r.url.startsWith('blob:'));
  assert.throws(()=>validateRuntimeResponses(workerless));
});
test('unexpected inline/blob/external executed response fails closed and raw bytes stay separately retained',()=>{
  const {report,retained}=fixture();
  for(const url of ['blob:http://127.0.0.1:12345/not-an-id','data:text/javascript,alert(1)','https://example.com/foreign.js']) {
    const copy=structuredClone(report),entry=copy.runtime_responses.at(-1);entry.url=entry.path=url;
    assert.throws(()=>validateRuntimeResponses(copy));
  }
  const copy=structuredClone(report);copy.requests.push({url:'http://127.0.0.1:12345/unexpected.js',status:200,response_id:99,resource_type:'script'});
  assert.throws(()=>validateRuntimeResponses(copy));
  assert(requiresRuntimeRetention('blob:http://127.0.0.1:12345/'+report.capture_session,'script'));
  const altered={...retained,responses:{...retained.responses,6:Buffer.from('corrupt generated worker')}};
  assert.throws(()=>assertExecutedBytes(report,altered));
});
test('worker derivation is pinned to exact source template and grid loader route',()=>{
  const bytes=deriveRustWorkerBytes('http://127.0.0.1:12345/gpui-conformance/rust/grid_layout.js');
  assert(bytes.includes(Buffer.from('/rust/grid_layout.js')));assert(!bytes.includes(Buffer.from(RUST_WORKER.marker)));
  assert.throws(()=>deriveRustWorkerBytes('http://127.0.0.1:12345/gpui-conformance/rust/drag_drop.js'));
  assert.throws(()=>deriveRustWorkerBytes('https://example.com/gpui-conformance/rust/grid_layout.js'));
  assert.notEqual(evidenceFilename('rust','asset','a/b',1),evidenceFilename('rust','asset','a_b',1));
});
test('capture binding and retained raw input reject swapped states and cross-runtime borrowing',()=>{
  const {report,retained}=fixture();validateCaptureBindings(report);validateInputEvidence(report,JSON.parse(retained.inputBytes));
  const swapped=structuredClone(report);[swapped.captures.initial,swapped.captures.narrow399]=[swapped.captures.narrow399,swapped.captures.initial];
  assert.throws(()=>validateCaptureBindings(swapped));
  const changed=structuredClone(report);changed.operations[0].events[0].width++;
  assert.throws(()=>validateInputEvidence(changed,JSON.parse(retained.inputBytes)));
  assert.deepEqual(inputEvidence(report),JSON.parse(retained.inputBytes));
});
test('historical source-only evidence cannot be relabeled as the current suite or catalog',()=>{
  const {report}=fixture(),catalogBytes=readFileSync(new URL('./fixtures/grid-layout-rust-only-catalog-b0781104.json',import.meta.url));report.catalog_evidence.sha256=sha256(catalogBytes);
  const checkout={revision:report.build.lab_revision,tree:report.build.lab_tree,trackedDirty:false,catalogBytes};assertCurrentBuild(report,checkout);
  for(const change of [{revision:'0'.repeat(40)},{tree:'0'.repeat(40)},{trackedDirty:true},{catalogBytes:Buffer.from('{}')}])
    assert.throws(()=>assertCurrentBuild(report,{...checkout,...change}));
});

test('retained font/source input checks reject corruption and missing font embedding independently',()=>{
  const bytes=Buffer.from('synthetic font bytes, not a real upstream font'),path='rust/embedded-font-inputs/test.ttf';
  const entry={path,bytes:bytes.length,sha256:sha256(bytes)},build={rust:{files:{[path.slice(5)]:sha256(bytes)}}};
  assertRetainedSupport(entry,bytes,build,Buffer.concat([Buffer.from('synthetic wasm'),bytes]));
  assert.throws(()=>assertRetainedSupport(entry,Buffer.from('corrupted'),build,bytes));
  assert.throws(()=>assertRetainedSupport(entry,bytes,build,Buffer.from('wasm without font')));
  const source={path:'rust/unchanged-source/grid_layout.rs',bytes:bytes.length,sha256:sha256(bytes)};
  assert.throws(()=>assertRetainedSupport(source,bytes,{rust:{files:{[source.path.slice(5)]:sha256(bytes)}}},bytes));
});

test('exposed gray gap width is measured separately from uncertain fill edges',()=>{
  const image=frame(399),result=inspectLayout(image);
  assert.deepEqual(result.measured_exposed_gaps.map(gap=>gap.pixels),[4,4,4,4]);
  for(let x=0;x<399;x++)for(const y of [48,49])image.data.set([254,254,254,255],4*(y*399+x));
  assert.throws(()=>inspectLayout(image),/exposed gap/);
});
