import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {UNIFORM_LIST,assertProvenance,provenanceNegativeControls,discoverGeometry,makeProfile,validateProfile,validateOperations,profileNegativeControls,assertCurrentBuild,sha256} from './uniform-list-comparator.mjs';
import {validateReport,verifyBehavior,validateCaptureBindings,validateRuntimeResponses,assertExecutedBytes,evidenceNegativeControls,inputEvidence,validateInputEvidence,requiresRuntimeRetention,assertRetainedSupport} from './uniform-list-runtime-evidence.mjs';
import {RUST_WORKER,deriveRustWorkerBytes,evidenceFilename} from './uniform-list-worker-evidence.mjs';
import {frame,pixels,provenance,fixture} from './fixtures/uniform-list-fixtures.mjs';

test('synthetic source-only provenance keeps exact engine/source/catalog and all eight fonts',()=>{
  const {build,catalog}=provenance();assert.equal(assertProvenance(build,catalog).source_blob,UNIFORM_LIST.sourceBlob);
  assert(provenanceNegativeControls(build,catalog).every(entry=>entry.rejected));
  for(const mutate of [b=>{b.rust.files['index.html']='0'.repeat(64);},b=>{b.rust.files['Cargo.lock']='0'.repeat(64);},
    b=>{b.rust.source_revision='d9afb21688e04f89d9e94d96d33eb530aef90886';},b=>{b.rust_oracle_only[0].width=800;}]) {
    const b=structuredClone(build);mutate(b);assert.throws(()=>assertProvenance(b,catalog));
  }
  const changed=structuredClone(catalog);changed.examples.push({id:'uniform_list',moonbit:'implemented'});
  assert.throws(()=>assertProvenance(build,changed));
});
test('synthetic geometry is measured from pixels, never fixed at26',()=>{
  for(const pitch of [26,31]) {
    const p=pixels(pitch);assert.equal(p.geometry.pitch,pitch);const result=validateProfile(p.images,p.geometry);
    assert.equal(result.measured_pitch,pitch);assert.equal(result.observed_content_scanlines,50*pitch);
    assert.equal(result.row_rasters.length,50);assert.equal(new Set(result.row_rasters.map(row=>row.sha256)).size,50);
    assert.equal(result.hypothesis_matches_observation,pitch===26);
  }
});
test('synthetic independent raw wheel evidence checks every state and strict stream order',()=>{
  const {report,geometry}=fixture();assert.equal(validateOperations(report,geometry).pixel_wheels,report.operations.length);
  assert.equal(makeProfile(geometry).captures.x_only_partial.offset,geometry.pitch-1);
  assert.equal(makeProfile(geometry).captures.mixed_y_partial.offset,geometry.pitch-1);
  const changed=structuredClone(report);changed.events.reverse();assert.throws(()=>validateOperations(changed,geometry));
});
test('observable corrupted-evidence controls reject unchanged scroll, bad ordering, clamps, edge erasure and bad delivery',()=>{
  const {report,retained,geometry}=fixture();const controls=profileNegativeControls(retained.images,geometry,report);
  assert(controls.length>=16);assert(controls.every(c=>c.rejected&&c.kind==='corrupted_evidence_sensitivity_not_executed_mutant'));
});
test('no blank/colored/translucent/shifted image or wrong dimensions can provide geometry',()=>{
  for(const mutate of [image=>image.data.fill(255),image=>{image.width=299;},image=>{image.data[3]=254;},
    image=>{image.data[4*(30*300+200)]=0;},image=>{image.data[4*(30*300+10)]=0;}]) {
    const image=frame();mutate(image);assert.throws(()=>discoverGeometry(image));
  }
});
test('exact original raster progression, rather than self-reported pitch/offset/pass, controls result',()=>{
  const {report,retained}=fixture();report.discovered_geometry={pitch:1};report.passed=true;
  for(const capture of Object.values(report.captures)){capture.offset=999;capture.pass=true;}
  assert.equal(verifyBehavior(report,retained).paint.measured_pitch,26);
});
test('synthetic v3-style execution provenance requires HTML, loader, wasm and actual generated worker response',()=>{
  const {report,retained}=fixture();validateReport(report,'rust');assertExecutedBytes(report,retained);
  const controls=evidenceNegativeControls(report,retained);assert(controls.length>=10);assert(controls.every(c=>c.rejected));
  for(const path of ['rust/index.html','rust/uniform_list.js','rust/uniform_list_bg.wasm']) {
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
test('worker derivation is pinned to exact source template and uniform loader route',()=>{
  const bytes=deriveRustWorkerBytes('http://127.0.0.1:12345/gpui-conformance/rust/uniform_list.js');
  assert(bytes.includes(Buffer.from('/rust/uniform_list.js')));assert(!bytes.includes(Buffer.from(RUST_WORKER.marker)));
  assert.throws(()=>deriveRustWorkerBytes('http://127.0.0.1:12345/gpui-conformance/rust/drag_drop.js'));
  assert.throws(()=>deriveRustWorkerBytes('https://example.com/gpui-conformance/rust/uniform_list.js'));
  assert.notEqual(evidenceFilename('rust','asset','a/b',1),evidenceFilename('rust','asset','a_b',1));
});
test('capture binding and retained raw input reject swapped states and cross-runtime borrowing',()=>{
  const {report,retained}=fixture();validateCaptureBindings(report);validateInputEvidence(report,JSON.parse(retained.inputBytes));
  const swapped=structuredClone(report);[swapped.captures.initial,swapped.captures.at_row_boundary]=[swapped.captures.at_row_boundary,swapped.captures.initial];
  assert.throws(()=>validateCaptureBindings(swapped));
  const changed=structuredClone(report);changed.operations[0].events[0].deltaY++;
  assert.throws(()=>validateInputEvidence(changed,JSON.parse(retained.inputBytes)));
  assert.deepEqual(inputEvidence(report),JSON.parse(retained.inputBytes));
});
test('historical source-only evidence cannot be relabeled as the current suite or catalog',()=>{
  const {report}=fixture(),catalogBytes=readFileSync(new URL('../examples.json',import.meta.url));report.catalog_evidence.sha256=sha256(catalogBytes);
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
  const source={path:'rust/unchanged-source/uniform_list.rs',bytes:bytes.length,sha256:sha256(bytes)};
  assert.throws(()=>assertRetainedSupport(source,bytes,{rust:{files:{[source.path.slice(5)]:sha256(bytes)}}},bytes));
});
