import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdtemp,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {DRAG_DROP,EMBEDDED_FONTS,SOURCE_CONSTRAINTS,sha256,makeProfile,discoverGeometry,assertPaint,assertPreview,validateOperations,decodePng,assertCurrentBuild} from './drag-drop-comparator.mjs';
import {DRAG_CANDIDATE,PAIR_REVISION,REQUIRED_HOSTS,SUITE_INPUTS,GRAPHICS_ARGS,captureBinding,validateCaptureBindings,inputEvidence,validateInputEvidence,
  assertPairedProvenance,pairedProvenanceNegativeControls,expectedRuntimeFiles,requiredRuntimeFiles,validateReport,loadEvidence,validatePixels,validateTransport,assertCaptureDigests,assertExecutedBytes,compareMeasurements,compareBehavior,pairedPixelNegativeControls,pairedEvidenceNegativeControls} from './drag-drop-pair-comparator.mjs';
import {syntheticPixels,syntheticFrame,syntheticGeometry} from './drag-drop-pair-fixtures.mjs';
function bindingFixture(runtime='rust',names=['initial']) {
  const report={runtime,capture_session:runtime==='rust'?'11111111-1111-4111-8111-111111111111':'22222222-2222-4222-8222-222222222222',
    input_evidence:{file:`drag-drop-${runtime}-trusted-input.json`,sha256:'f'.repeat(64)},captures:{},
    suite_inputs:SUITE_INPUTS.map(path=>({path,file:`drag-drop-${runtime}-suite-${path.replaceAll('/','_')}.bin`,sha256:'a'.repeat(64)}))};
  for(const [index,name] of names.entries()) {
    const binding=captureBinding(report,name,index);
    const attempts=[1,2].map(number=>({file:`drag-drop-${runtime}-${name}-sample-${number}-dpr1.png`,binding,request_ordinal:number,method:'Playwright.page.screenshot'}));
    report.captures[name]={attempts,binding,after_operation:index+1,stable:true,file:attempts[1].file,stability_file:attempts[0].file};
  }
  return report;
}
// Synthetic metadata cannot stand in for compiled/runtime/original-byte evidence.
function metadata(runtime='rust') {
  const upstream={repository:'zed-industries/zed',revision:DRAG_DROP.revision};
  const files=Object.fromEntries(['host.mjs','drag_drop.js','drag_drop_bg.wasm','packaging-Cargo.toml'].map(file=>[file,'a'.repeat(64)]));
  files['unchanged-source/drag_drop.rs']=DRAG_DROP.sourceSha256;
  const embedded_fonts=Object.fromEntries(Object.entries(EMBEDDED_FONTS).map(([path,sha256])=>{
    const file='embedded-font-inputs/'+path.split('/').at(-1);files[file]=sha256;return [path,{file,sha256}];}));
  const build={upstream,moonbit:DRAG_CANDIDATE,lab_revision:'b'.repeat(40),lab_tree:'c'.repeat(40),lab_tracked_dirty:false,rust_bundled:true,
    compiler:'moon 0.1.synthetic\nmoonc v0.1.synthetic',moonbit_unit_tests:'passed',comparison_status:'unverified',font_sha256:EMBEDDED_FONTS['assets/fonts/ibm-plex-sans/IBMPlexSans-Regular.ttf'],
    implemented:['hello_world','drag_drop'],implemented_sources:{drag_drop:{source:DRAG_DROP.source,source_blob:DRAG_DROP.sourceBlob}},
    runtime_sha256_by_example:{drag_drop:'d'.repeat(64)},font_sha256_by_file:Object.fromEntries(['IBMPlexSans-Regular.ttf','IBMPlexSans-Italic.ttf','IBMPlexSans-SemiBold.ttf'].map(name=>[name,EMBEDDED_FONTS['assets/fonts/ibm-plex-sans/'+name]])),
    moonbit_host_files_sha256:Object.fromEntries([...REQUIRED_HOSTS,'moonbit/another-static-import.mjs'].map(file=>[file,'e'.repeat(64)])),
    rust_implemented:['drag_drop'],rust_oracle_only:[],rust_subset_sources:[{id:'drag_drop',source:DRAG_DROP.source,source_blob:DRAG_DROP.sourceBlob,
      source_sha256:DRAG_DROP.sourceSha256,upstream_revision:DRAG_DROP.revision,status:'implemented_subset',candidate:'implemented'}],
    rust:{source_modified:false,source_revision:DRAG_DROP.revision,source_tree:DRAG_DROP.tree,oracle_only:false,implemented_subset:['drag_drop'],toolchain:'rustc 1.93.0-nightly (synthetic)',bindings:'wasm-bindgen 0.2.129',
      build_completed_at_utc:'2026-10-16T00:00:00Z',command:['cargo','+nightly-2026-10-14','build','--locked','--bin','drag_drop'],embedded_fonts,files,
      packaging:{upstream_files_modified:false,manifest_sha256:'a'.repeat(64),additional_bins:[{name:'drag_drop',source:DRAG_DROP.source}]}}};
  const catalog={upstream,moonbit:DRAG_CANDIDATE,examples:[{id:'drag_drop',moonbit:'implemented',source:DRAG_DROP.source,source_blob:DRAG_DROP.sourceBlob,
    candidate_source:'web/moonbit/drag_drop/drag_drop.mbt',width:800,height:600}]};
  const manifestBytes=Buffer.from(JSON.stringify(build)),catalogBytes=Buffer.from(JSON.stringify(catalog));
  const paths=requiredRuntimeFiles(runtime),hashes=expectedRuntimeFiles(build,runtime);
  const runtime_responses=paths.map((path,index)=>({path,response_id:index+1,url:'http://localhost/gpui-conformance/'+path,status:200,sha256:hashes[path],file:`drag-drop-${runtime}-asset-${path.replaceAll('/','_')}-response-${index+1}.bin`}));
  const report={runtime,status:`${runtime}_profile_captured`,mode:'paired_profile_capture',profile_revision:PAIR_REVISION,candidate:'implemented',comparison:'not_run',conformance:'not_claimed',
    environment:{browser:'141.0.0.0',node:'v22.0.0',platform:'linux',arch:'x64',playwright:'1.56.1',graphics_requested:GRAPHICS_ARGS},
    graphics_actual:{gpu:{devices:[{deviceString:'Synthetic SwiftShader metadata only'}]}},source_constraints:SOURCE_CONSTRAINTS,
    graphics_evidence:{file:`drag-drop-${runtime}-graphics.json`,sha256:'f'.repeat(64)},
    errors:[],console:[],profile:{width:800,height:600,dpr:1},canvas:{bounds:{x:0,y:0,width:800,height:600},backing:{width:800,height:600}},
    transport:{active_tag:'TEXTAREA',canvas_tab_index:-1},build,catalog,source:assertPairedProvenance(build,catalog),provenance_negative_controls:pairedProvenanceNegativeControls(build,catalog),
    build_evidence:{file:`drag-drop-${runtime}-build-manifest.json`,sha256:sha256(manifestBytes)},catalog_evidence:{file:`drag-drop-${runtime}-catalog.json`,sha256:sha256(catalogBytes)},
    decoder:{name:'Pillow',version:'12.0.0',sha256:'f'.repeat(64)},runtime_responses,
    requests:runtime_responses.map(entry=>({url:entry.url,status:200,response_id:entry.response_id})),served_requests:runtime_responses.map(entry=>({url:new URL(entry.url).pathname,status:200,sha256:entry.sha256}))};
  Object.assign(report,bindingFixture(runtime,Object.keys(makeProfile(syntheticGeometry).captures)));report.operations=makeProfile(syntheticGeometry).operations;
  return {report,manifestBytes,catalogBytes};
}
let synthetic,measured;
const fixtures=()=>synthetic??=syntheticPixels();
const measurement=()=>measured??=validatePixels(fixtures().report,fixtures().retained);
test('current pair binds the exact published reviewed additive drag-session core',()=>{
  assert.equal(DRAG_CANDIDATE.revision,'fc53cb382c66f68bfc1b3e1cc72d01056cd3c625');
  assert.equal(DRAG_CANDIDATE.tree,'c9ec59c5fbdbd84548b7d6ffe2c99b8403509db9');
});
test('paired exact current pins reject historical source-only claims',async()=>{
  const {report}=metadata();assert.equal(assertPairedProvenance(report.build,report.catalog).candidate,'implemented');
  assert.equal(pairedProvenanceNegativeControls(report.build,report.catalog).length,15);
  const absent=structuredClone(report.catalog);absent.examples=[];assert.throws(()=>assertPairedProvenance(report.build,absent));
  const historical=structuredClone(report.build),historicalCatalog=structuredClone(report.catalog);
  historical.moonbit={repository:'gpui-mbt/gpui.mbt',revision:'eb968228bbea56aff13721dc427875c2dacffc14',tree:'ae9072d350ef6d1546e408226218ec08efc96552'};
  historicalCatalog.moonbit=historical.moonbit;assert.throws(()=>assertPairedProvenance(historical,historicalCatalog),/Exact reviewed candidate core/);
  const actual=JSON.parse(await readFile(new URL('../examples.json',import.meta.url)));
  assert.deepEqual(actual.moonbit,DRAG_CANDIDATE,'Integrated catalog uses this exact reviewed public core');
  const entry=actual.examples.find(value=>value.id==='drag_drop');assert(entry);assert.equal(entry.moonbit,'implemented');
  assert.equal(entry.source_blob,DRAG_DROP.sourceBlob);assert.equal(entry.candidate_source,'web/moonbit/drag_drop/drag_drop.mbt');
});
test('both runtimes require actual executed assets, graphics and current paired labels',()=>{
  for(const runtime of ['rust','moonbit']) {
    const {report}=metadata(runtime);validateReport(report,runtime);
    for(const mutate of [r=>r.runtime_responses.pop(),r=>{r.status='rust_discovery_captured';},
      r=>{r.graphics_actual={gpu:{device:'unsupported'}};},r=>{r.environment.playwright='1.57.0';},
      r=>{r.graphics_actual.gpu.auxAttributes={glRenderer:'Different active renderer'};},
      r=>{delete r.graphics_evidence;},r=>{r.transport.canvas_tab_index=0;},
      r=>{r.runtime_responses[0].sha256='0'.repeat(64);},
      r=>{r.runtime_responses[0].response_id+=100;},
      r=>{r.requests.push({url:'http://localhost/gpui-conformance/unretained.mjs',status:200});}]) {
      const wrong=structuredClone(report);mutate(wrong);assert.throws(()=>validateReport(wrong,runtime));
    }
    assert(Object.hasOwn(expectedRuntimeFiles(metadata('moonbit').report.build,'moonbit'),'moonbit/another-static-import.mjs'));
  }
});
test('capture ownership rejects swapped states, cross-runtime borrowing and fabricated sample requests',()=>{
  for(const runtime of ['rust','moonbit']) {
    const report=bindingFixture(runtime);validateCaptureBindings(report);
    for(const mutate of [r=>{r.captures.initial.attempts[0].file='drag-drop-other-initial-sample-1-dpr1.png';},
      r=>{r.captures.initial.binding.runtime=runtime==='rust'?'moonbit':'rust';},
      r=>{r.captures.initial.binding.state='color0_accepted';},r=>{r.captures.initial.attempts[1].request_ordinal=1;},
      r=>{r.captures.initial.stability_file=r.captures.initial.file;},r=>{r.captures.initial.attempts[0].method='synthetic';}]) {
      const wrong=structuredClone(report);mutate(wrong);assert.throws(()=>validateCaptureBindings(wrong));
    }
  }
});
test('synthetic unchanged 54-operation profile independently passes source measurements',()=>{
  fixtures();measurement();
  assert.deepEqual(measured.geometry,syntheticGeometry);assert.equal(measured.profile.operations.length,54);assert.equal(Object.keys(measured.paint).length,54);
  const release=synthetic.report.operations.find(entry=>entry.name==='far_release_only');
  assert.deepEqual(release.action,{kind:'releaseAt',x:400,y:420});assert.deepEqual(release.prior_pointer,{x:400,y:232});
  assert.equal(release.events.length,1);assert.equal(release.events[0].type,'pointerup');
  assert.equal(measured.profile.captures.exact_two.active,null);assert.equal(measured.profile.captures.over_two.active,0);
  assert.equal(measured.profile.captures.return_toward_origin.active,0);assert.equal(measured.profile.captures.far_release_only.target,null);
  assert.equal(compareMeasurements(measured,measured).states,54);
});
test('synthetic paint and input corrupted controls run independently for each runtime',()=>{
  measurement();
  for(const runtime of ['rust','moonbit']) {
    const report={...synthetic.report,runtime};const controls=pairedPixelNegativeControls(report,synthetic.retained,measured);
    assert.equal(controls.length,19);assert(controls.every(control=>control.rejected));
  }
});
test('synthetic evidence controls independently reject runtime borrowing, altered assets and fabricated delivery',()=>{
  fixtures();
  for(const runtime of ['rust','moonbit']) {
    const report={...structuredClone(synthetic.report),...bindingFixture(runtime,Object.keys(synthetic.report.captures)),profile_revision:PAIR_REVISION},assets={};
    for(const name of Object.keys(report.captures))Object.assign(report.captures[name],synthetic.report.captures[name]);
    report.runtime_responses=requiredRuntimeFiles(runtime).map(path=>{
      assets[path]=Buffer.from('synthetic integrity-test asset '+path);return {path,sha256:sha256(assets[path])};
    });
    const inputBytes=Buffer.from(JSON.stringify(inputEvidence(report))),files={...synthetic.retained,assets,inputBytes};
    assert.equal(pairedEvidenceNegativeControls(report,files).length,requiredRuntimeFiles(runtime).length+5);
  }
});
test('synthetic pure comparison cannot accept same incorrect geometry or report-provided geometry',()=>{
  measurement();
  const altered=structuredClone(measured);altered.geometry.sources[0].y++;assert.throws(()=>compareMeasurements(measured,altered));
  const wrong={...synthetic.report,discovered_geometry:{invented:true},diagnostics:{target:'red'},checks:{pass:true}};
  assert.deepEqual(discoverGeometry(synthetic.retained.images.initial),measured.geometry);
  const images={...synthetic.retained.images,color0_accepted:synthetic.retained.images.color1_accepted};
  assert.throws(()=>assertPaint(images.color0_accepted,measured.geometry,measured.profile.captures.color0_accepted));
  const opaque=syntheticFrame(measured.profile.captures.threshold_stage);
  opaque.data.set([0,0,255,255],4*(44*800+48));assert.throws(()=>assertPreview(opaque,measured.geometry,measured.profile.captures.threshold_stage,true));
  assert.equal(wrong.diagnostics.target,'red'); // Diagnostics were never consulted by any predicate.
});
test('raw transport rejects missing/fabricated delivery, moves on release, stale coordinates and bad chronology',()=>{
  fixtures();
  const source={...synthetic.report,runtime:'rust',capture_session:'unit-only',profile_revision:PAIR_REVISION},raw=structuredClone(inputEvidence(source));
  validateInputEvidence(source,raw);
  for(const mutate of [r=>{r.operations[1].events=[];},r=>{r.events[1].trusted=false;},
    r=>{r.operations.find(entry=>entry.name==='far_release_only').events[0].type='pointermove';}]) {
    const wrong=structuredClone(source);mutate(wrong);assert.throws(()=>validateInputEvidence(wrong,raw));assert.throws(()=>validateOperations(wrong,syntheticGeometry));
  }
  const changed=structuredClone(source),operation=changed.operations.find(entry=>entry.name==='far_release_only');
  operation.action.y--;operation.expected[0].y--;operation.events[0].y--;
  assert.throws(()=>validateOperations(changed,syntheticGeometry),'Source geometry prevents jointly fabricated expected/delivered coordinates');
  for(const mutate of [r=>{r.events[1].time=-1;},r=>{r.events[1].shiftKey=true;},r=>{r.events[1].defaultPrevented=null;}]) {
    const wrong=structuredClone(source);mutate(wrong);assert.throws(()=>validateTransport(wrong,syntheticGeometry));
  }
});
test('raw duplicate release checks actual pointer delivery and optional compatibility mouse suppression',()=>{
  fixtures();
  const report=structuredClone(synthetic.report);
  for(const operation of report.operations)if(operation.duplicate) {
    operation.events=[{...operation.mouse_expected,type:'pointerup',pointerType:'mouse',trusted:true,target:'CANVAS',
      time:operation.mouse_events[0].time-0.5,defaultPrevented:true,shiftKey:false,ctrlKey:false,altKey:false,metaKey:false}];
    operation.mouse_events=[];
  }
  report.events=report.operations.flatMap(entry=>entry.events);report.mouse_events=report.operations.flatMap(entry=>entry.mouse_events);
  const result=validateTransport(report,syntheticGeometry);assert(result.duplicate_releases.every(entry=>entry.pointer_events===1&&!entry.browser_suppressed&&entry.mouse_events===0));
});
test('original decoded image and executed asset byte tampering fail independent integrity checks',()=>{
  fixtures();
  const image={...synthetic.retained.images.initial,data:synthetic.retained.images.initial.data.slice()};image.data[0]^=1;
  assert.throws(()=>assertCaptureDigests(synthetic.report,{...synthetic.retained,images:{...synthetic.retained.images,initial:image}}));
  for(const runtime of ['rust','moonbit'])for(const path of requiredRuntimeFiles(runtime)) {
    const bytes=Buffer.from('original unit-only executable bytes'),report={runtime_responses:[{path,sha256:sha256(bytes)}]};
    assertExecutedBytes(report,{assets:{[path]:bytes}});
    assert.throws(()=>assertExecutedBytes(report,{assets:{[path]:Buffer.from('changed')}}));
  }
});
test('immutable current-checkout identity rejects dirty or mismatched historical reuse',()=>{
  const catalog={synthetic:true},catalogBytes=Buffer.from(JSON.stringify(catalog));
  const report={build:{lab_revision:'a'.repeat(40),lab_tree:'b'.repeat(40)},catalog,catalog_evidence:{sha256:sha256(catalogBytes)}};
  const checkout={revision:report.build.lab_revision,tree:report.build.lab_tree,trackedDirty:false,catalogBytes};assertCurrentBuild(report,checkout);
  for(const change of [{revision:'c'.repeat(40)},{tree:'c'.repeat(40)},{trackedDirty:true},{catalogBytes:Buffer.from('{}')}])assert.throws(()=>assertCurrentBuild(report,{...checkout,...change}));
});
test('original PNG decoder rejects tampered bytes and non-profile dimensions',()=>{
  const png=spawnSync('python3',['-c',"from PIL import Image; import sys; Image.new('RGBA',(800,600),'white').save(sys.stdout.buffer,format='PNG')"]);
  assert.equal(png.status,0);assert.equal(decodePng(png.stdout).data.length,1920000);
  const changed=Buffer.from(png.stdout);changed[29]^=1;assert.throws(()=>decodePng(changed));
  assert.throws(()=>decodePng(Buffer.concat([png.stdout,Buffer.from('trailing')])));
  const small=spawnSync('python3',['-c',"from PIL import Image; import sys; Image.new('RGBA',(799,600),'white').save(sys.stdout.buffer,format='PNG')"]);assert.throws(()=>decodePng(small.stdout));
});
test('retained loader rejects forged manifest bytes before accepting any runtime pixels',async()=>{
  const directory=await mkdtemp(join(tmpdir(),'drag-drop-pair-unit-'));
  try {
    const report={build_evidence:{file:'drag-drop-rust-build-manifest.json',sha256:'a'.repeat(64)}};
    await writeFile(join(directory,report.build_evidence.file),'forged');await assert.rejects(()=>loadEvidence(directory,report),/raw bytes hash/);
  }finally{await rm(directory,{recursive:true,force:true});}
});
test('equal synthetic measurements cannot certify paired execution without actual retained build and runtime bytes',()=>{
  fixtures();
  const rust=metadata('rust'),moonbit=metadata('moonbit');
  assert.throws(()=>compareBehavior(rust.report,moonbit.report,{rust:synthetic.retained,moonbit:synthetic.retained}));
});
test('current pair workflow retains independent failures and never substitutes source-only artifacts',async()=>{
  const workflow=await readFile(new URL('../../.github/workflows/drag-drop-oracle.yml',import.meta.url),'utf8');
  assert.match(workflow,/name: Drag-drop source behavior pair/);assert.match(workflow,/--implemented-example drag_drop/);
  assert.match(workflow,/drag-drop-pair-browser\.mjs _build\/drag-drop-browser-lab --candidate/);
  assert.match(workflow,/compare-drag-drop-results\.mjs/);assert.match(workflow,/Pillow==12\.0\.0/);assert.match(workflow,/playwright@1\.56\.1/);
  assert.match(workflow,/if: always\(\)/);assert.match(workflow,/moonbit-build\.log/);assert.match(workflow,/rust-build\.log/);
  assert(!workflow.includes('--oracle-only'));assert(!workflow.includes('drag-drop-oracle-browser.mjs'));
  const browser=await readFile(new URL('./drag-drop-pair-browser.mjs',import.meta.url),'utf8');
  assert.match(browser,/Input\.dispatchMouseEvent/);assert.match(browser,/SystemInfo\.getInfo/);
  assert(!browser.includes('dispatchEvent('));assert(!browser.includes('drag_drop_state('));
});
