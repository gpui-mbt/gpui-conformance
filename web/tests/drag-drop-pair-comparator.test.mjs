import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {readFile,mkdtemp,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {DRAG_DROP,EMBEDDED_FONTS,SOURCE_CONSTRAINTS,sha256,makeProfile,discoverGeometry,assertPaint,assertPreview,validateOperations,decodePng,assertCurrentBuild} from './drag-drop-comparator.mjs';
import {DRAG_CANDIDATE,HISTORICAL_PAIR,POPOVER_PAIR,PAIR_REVISION,REQUIRED_HOSTS,SUITE_INPUTS,GRAPHICS_ARGS,HTML_ENTRYPOINTS,validateRuntimeResponses,runtimeResponsePath,requiresRuntimeRetention,captureBinding,validateCaptureBindings,inputEvidence,validateInputEvidence,
  assertPairedProvenance,pairedProvenanceNegativeControls,expectedRuntimeFiles,requiredRuntimeFiles,validateReport,loadEvidence,validatePixels,validateTransport,assertCaptureDigests,assertExecutedBytes,compareMeasurements,compareBehavior,pairedPixelNegativeControls,pairedEvidenceNegativeControls} from './drag-drop-pair-comparator.mjs';
import {RUST_WORKER,evidenceFilename,assertUploadSafeFilename,deriveRustWorkerBytes,assertRustWorkerSource,assertRustWorkerResponse} from './drag-drop-runtime-evidence.mjs';
import {syntheticPixels,syntheticFrame,syntheticGeometry} from './drag-drop-pair-fixtures.mjs';
const workerTemplate=readFileSync(new URL('./fixtures/drag-drop-wasm-thread-0cf96c7-worker.js.txt',import.meta.url));
const sourcePin=path=>path===RUST_WORKER.lock_path?RUST_WORKER.lock_sha256:path===RUST_WORKER.template_path?RUST_WORKER.template_sha256:undefined;
function bindingFixture(runtime='rust',names=['initial']) {
  const report={runtime,capture_session:runtime==='rust'?'11111111-1111-4111-8111-111111111111':'22222222-2222-4222-8222-222222222222',
    input_evidence:{file:`drag-drop-${runtime}-trusted-input.json`,sha256:'f'.repeat(64)},captures:{},
    suite_inputs:SUITE_INPUTS.map(path=>({path,file:evidenceFilename(runtime,'suite',path),sha256:Object.values(HTML_ENTRYPOINTS).find(entry=>entry.source===path)?.sha256||sourcePin(path)||'a'.repeat(64)}))};
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
  files['Cargo.lock']=RUST_WORKER.lock_sha256;files['unchanged-source/drag_drop.rs']=DRAG_DROP.sourceSha256;files['index.html']=HTML_ENTRYPOINTS.rust.sha256;
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
  const runtime_responses=paths.map((path,index)=>({path,response_id:index+1,
    resource_type:path.endsWith('.html')?'document':path.endsWith('.ttf')?'font':path.endsWith('.wasm')?'fetch':'script',
    url:'http://127.0.0.1:12345/gpui-conformance/'+(path.endsWith('.html')?`${runtime}/?example=drag_drop`:path),
    status:200,sha256:hashes[path]}));
  for(const entry of runtime_responses) {
    entry.file=evidenceFilename(runtime,'asset',entry.url,entry.response_id);
    entry.binding={runtime,session:bindingFixture(runtime).capture_session};
  }
  const report={runtime,status:`${runtime}_profile_captured`,mode:'paired_profile_capture',profile_revision:PAIR_REVISION,candidate:'implemented',comparison:'not_run',conformance:'not_claimed',
    environment:{browser:'141.0.0.0',node:'v22.0.0',platform:'linux',arch:'x64',playwright:'1.56.1',graphics_requested:GRAPHICS_ARGS},
    graphics_actual:{gpu:{devices:[{deviceString:'Synthetic SwiftShader metadata only'}]}},source_constraints:SOURCE_CONSTRAINTS,
    graphics_evidence:{file:`drag-drop-${runtime}-graphics.json`,sha256:'f'.repeat(64)},
    errors:[],console:[],profile:{width:800,height:600,dpr:1},canvas:{bounds:{x:0,y:0,width:800,height:600},backing:{width:800,height:600}},
    transport:{active_tag:'TEXTAREA',canvas_tab_index:-1},build,catalog,source:assertPairedProvenance(build,catalog),provenance_negative_controls:pairedProvenanceNegativeControls(build,catalog),
    build_evidence:{file:`drag-drop-${runtime}-build-manifest.json`,sha256:sha256(manifestBytes)},catalog_evidence:{file:`drag-drop-${runtime}-catalog.json`,sha256:sha256(catalogBytes)},
    decoder:{name:'Pillow',version:'12.0.0',sha256:'f'.repeat(64)},runtime_responses,
    requests:runtime_responses.map(entry=>({url:entry.url,status:200,response_id:entry.response_id,resource_type:entry.resource_type})),served_requests:runtime_responses.map(entry=>({url:new URL(entry.url).pathname+new URL(entry.url).search,status:200,sha256:entry.sha256}))};
  Object.assign(report,bindingFixture(runtime,Object.keys(makeProfile(syntheticGeometry).captures)));report.operations=makeProfile(syntheticGeometry).operations;
  if(runtime==='rust')appendWorker(report);
  return {report,manifestBytes,catalogBytes};
}
function appendWorker(report,id=report.requests.length+1,url='blob:http://127.0.0.1:12345/11111111-2222-4333-8444-555555555555') {
  const loader=report.runtime_responses.find(entry=>entry.path===RUST_WORKER.loader_path);
  const response={path:runtimeResponsePath(url),url,status:200,response_id:id,resource_type:'script',
    sha256:sha256(deriveRustWorkerBytes(loader?.url||'http://127.0.0.1:12345/gpui-conformance/rust/drag_drop.js')),
    file:evidenceFilename(report.runtime,'asset',url,id),binding:{runtime:report.runtime,session:report.capture_session}};
  report.runtime_responses.push(response);report.requests.push({url,status:200,response_id:id,resource_type:'script'});return response;
}
let synthetic,measured;
const fixtures=()=>synthetic??=syntheticPixels();
const measurement=()=>measured??=validatePixels(fixtures().report,fixtures().retained);
test('current pair binds the exact pattern-capable shared core',()=>{
  assert.equal(DRAG_CANDIDATE.revision,'3bea4fea2dd54768a3859c7c881dda2a60fa5bbd');
  assert.equal(DRAG_CANDIDATE.tree,'25b0647f974d8b6ffd46c1a15c7eeb5ef7e4fe85');
});
test('paired exact current pins reject historical source-only claims',async()=>{
  const {report}=metadata();assert.equal(assertPairedProvenance(report.build,report.catalog).candidate,'implemented');
  assert.equal(pairedProvenanceNegativeControls(report.build,report.catalog).length,19);
  const absent=structuredClone(report.catalog);absent.examples=[];assert.throws(()=>assertPairedProvenance(report.build,absent));
  const historical=structuredClone(report.build),historicalCatalog=structuredClone(report.catalog);
  historical.moonbit={repository:'gpui-mbt/gpui.mbt',revision:'eb968228bbea56aff13721dc427875c2dacffc14',tree:'ae9072d350ef6d1546e408226218ec08efc96552'};
  historicalCatalog.moonbit=historical.moonbit;assert.throws(()=>assertPairedProvenance(historical,historicalCatalog),/Exact reviewed candidate core/);
  const actual=JSON.parse(await readFile(new URL('../examples.json',import.meta.url)));
  assert.deepEqual(actual.moonbit,{
    repository:'gpui-mbt/gpui.mbt',revision:'3bea4fea2dd54768a3859c7c881dda2a60fa5bbd',tree:'25b0647f974d8b6ffd46c1a15c7eeb5ef7e4fe85',
  },'Integrated catalog uses the current pattern-capable core');
  assert.deepEqual(actual.moonbit,DRAG_CANDIDATE,'Current live pair requires this exact new source profile');
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
test('actual HTML execution entrypoints cannot escape retained response checks',async()=>{
  for(const runtime of ['rust','moonbit']) {
    const {report}=metadata(runtime),source=await readFile(new URL(runtime==='rust'?'../rust/index.html':'../moonbit/site/index.html',import.meta.url));
    const injected=Buffer.concat([source,Buffer.from('<script>globalThis.injected_unpinned_execution=true</script>')]);
    validateReport(report,runtime);
    report.requests.push({url:`http://localhost/gpui-conformance/${runtime}/?example=drag_drop`,status:200,response_id:999,resource_type:'document'});
    report.served_requests.push({url:`/gpui-conformance/${runtime}/?example=drag_drop`,status:200,sha256:sha256(injected)});
    assert.throws(()=>validateReport(report,runtime),`${runtime}: unretained executable HTML must fail`);
    assert(requiredRuntimeFiles(runtime).includes(`${runtime}/index.html`));
  }
});
test('source HTML pins reject missing, changed, wrong-route and inline-injected entrypoints',async()=>{
  for(const runtime of ['rust','moonbit']) {
    const {report}=metadata(runtime),definition=HTML_ENTRYPOINTS[runtime];validateReport(report,runtime);
    const source=await readFile(new URL('../../'+definition.source,import.meta.url));assert.equal(sha256(source),definition.sha256);
    const inline=Buffer.concat([source,Buffer.from('\n<script>globalThis.unreviewed=true</script>\n')]);
    const response=report.runtime_responses.find(entry=>entry.path===definition.path);
    assert.equal(runtimeResponsePath(response.url),definition.path);assert(requiresRuntimeRetention(response.url,'document'));
    assert(requiresRuntimeRetention('http://localhost/extensionless-entry','document'));
    assert(requiresRuntimeRetention('http://localhost/extensionless-code','script'));
    assertExecutedBytes({runtime_responses:[response]},{assets:{[definition.path]:source},responses:{[response.response_id]:source}});
    assert.throws(()=>assertExecutedBytes({runtime_responses:[response]},{assets:{[definition.path]:inline},responses:{[response.response_id]:inline}}));
    for(const mutate of [
      r=>{r.runtime_responses=r.runtime_responses.filter(entry=>entry.path!==definition.path);},
      r=>{r.runtime_responses.find(entry=>entry.path===definition.path).sha256=sha256(inline);},
      r=>{r.suite_inputs.find(entry=>entry.path===definition.source).sha256=sha256(inline);},
      r=>{r.runtime_responses.find(entry=>entry.path===definition.path).resource_type='other';},
      r=>{const entry=r.runtime_responses.find(value=>value.path===definition.path);entry.url=entry.url.replace('drag_drop','hello_world');},
    ]){const changed=structuredClone(report);mutate(changed);assert.throws(()=>validateReport(changed,runtime));}
    const wrong=structuredClone(report),entry=wrong.runtime_responses.find(value=>value.path===definition.path);
    entry.sha256=sha256(inline);wrong.served_requests.find(value=>value.url===new URL(entry.url).pathname+new URL(entry.url).search).sha256=entry.sha256;
    if(runtime==='rust')wrong.build.rust.files['index.html']=entry.sha256;
    assert.throws(()=>validateReport(wrong,runtime),'Changing generated HTML and its report/manifest hashes cannot bypass original source pins');
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
    const report={...structuredClone(synthetic.report),...bindingFixture(runtime,Object.keys(synthetic.report.captures)),profile_revision:PAIR_REVISION},assets={},responses={};
    for(const name of Object.keys(report.captures))Object.assign(report.captures[name],synthetic.report.captures[name]);
    report.runtime_responses=requiredRuntimeFiles(runtime).map((path,index)=>{
      assets[path]=path===RUST_WORKER.wasm_path?Buffer.concat([Buffer.from('synthetic WASM container, never executable'),workerTemplate]):Buffer.from('synthetic integrity-test asset '+path);
      responses[index+1]=assets[path];return {path,response_id:index+1,url:'http://127.0.0.1:12345/gpui-conformance/'+path,sha256:sha256(assets[path])};
    });
    report.build={rust:{files:{...Object.fromEntries(Object.entries(assets).map(([path,bytes])=>[path.slice(5),sha256(bytes)])),'Cargo.lock':RUST_WORKER.lock_sha256}}};
    const inputBytes=Buffer.from(JSON.stringify(inputEvidence(report))),files={...synthetic.retained,assets,responses,inputBytes};
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
    const bytes=Buffer.from('original unit-only executable bytes'),report={runtime_responses:[{path,response_id:1,sha256:sha256(bytes)}]};
    assertExecutedBytes(report,{assets:{[path]:bytes},responses:{1:bytes}});
    assert.throws(()=>assertExecutedBytes(report,{assets:{[path]:Buffer.from('changed')},responses:{1:bytes}}));
    assert.throws(()=>assertExecutedBytes(report,{assets:{[path]:bytes},responses:{1:Buffer.from('changed')}}));
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

test('generated wasm_thread bytes reproduce the failed digest only from the pinned source and exact loader URL',async()=>{
  assert.equal(workerTemplate.length,964);assert.equal(sha256(workerTemplate),RUST_WORKER.template_sha256);
  const lock=await readFile(new URL('../rust/Cargo.lock',import.meta.url));assert.equal(sha256(lock),RUST_WORKER.lock_sha256);
  assert(lock.includes(Buffer.from(`name = "wasm_thread"\nversion = "0.3.3"\nsource = "git+https://github.com/zed-industries/wasm_thread?rev=${RUST_WORKER.revision}#${RUST_WORKER.revision}"`)));
  const url='http://127.0.0.1:46561/gpui-conformance/rust/drag_drop.js',body=deriveRustWorkerBytes(url);
  assert.equal(body.length,1000);assert.equal(sha256(body),'1d49b54f3942aed12fce148a7409b23e44ac32a342b747acd5fece6d6b75a8fb');
  assert.notEqual(sha256(deriveRustWorkerBytes(url.replace('46561','46562'))),sha256(body));
  // This source-derived reconstruction is not the unavailable failed-run body.
  for(const bad of ['https://127.0.0.1:46561/gpui-conformance/rust/drag_drop.js',url+'?old=1',url+'#old',
    url.replace('127.0.0.1','localhost'),url.replace('rust/drag_drop','moonbit/drag_drop'),url.replace('127.0.0.1','user@127.0.0.1')])
    assert.throws(()=>deriveRustWorkerBytes(bad));
});
test('generated scripts require current original loader and WASM bytes with the complete pinned template',()=>{
  const loader=Buffer.from('Synthetic pinned loader bytes, never claimed actual'),wasm=Buffer.concat([Buffer.from('Synthetic WASM container'),workerTemplate]);
  const assets={[RUST_WORKER.loader_path]:loader,[RUST_WORKER.wasm_path]:wasm};
  const build={rust:{files:{'drag_drop.js':sha256(loader),'drag_drop_bg.wasm':sha256(wasm),'Cargo.lock':RUST_WORKER.lock_sha256}}};
  assertRustWorkerSource(build,assets);
  for(const path of [RUST_WORKER.loader_path,RUST_WORKER.wasm_path]) {
    assert.throws(()=>assertRustWorkerSource(build,{...assets,[path]:Buffer.from('changed')}));
    assert.throws(()=>assertRustWorkerSource(build,{...assets,[path]:undefined}));
  }
  for(const changed of [Buffer.from('no template'),Buffer.from(wasm.map((byte,index)=>index===50?byte^1:byte))]) {
    const rebased=structuredClone(build);rebased.rust.files['drag_drop_bg.wasm']=sha256(changed);
    assert.throws(()=>assertRustWorkerSource(rebased,{...assets,[RUST_WORKER.wasm_path]:changed}),'Report hash changes cannot invent the exact embedded source template');
  }
});
test('generated Rust responses retain each cached URL request and reject unmatched or borrowed execution',()=>{
  const {report}=metadata('rust');validateReport(report,'rust');
  const first=report.runtime_responses.at(-1),second=appendWorker(report,first.response_id+1,first.url);
  assert.notEqual(first.file,second.file);assert.equal(validateRuntimeResponses(report).generated_worker_responses,2);
  assert(!report.served_requests.some(entry=>entry.url===first.url),'No invented HTTP server observations for generated blobs');
  for(const mutate of [
    r=>{r.runtime_responses.at(-1).sha256=sha256(Buffer.concat([deriveRustWorkerBytes(r.runtime_responses.find(x=>x.path===RUST_WORKER.loader_path).url),Buffer.from('\nself.injected=true;')]));},
    r=>{r.runtime_responses.at(-1).resource_type='fetch';},r=>{r.runtime_responses.at(-1).status=404;},
    r=>{r.runtime_responses.at(-1).url=r.runtime_responses.at(-1).url.replace('12345','12346');},
    r=>{r.runtime_responses.at(-1).binding.runtime='moonbit';},r=>{r.runtime_responses.at(-1).binding.session='other-session';},
    r=>{r.runtime_responses.at(-1).response_id=first.response_id;},r=>{delete r.runtime_responses.at(-1).response_id;},
    r=>{r.runtime_responses.at(-1).file=first.file;},r=>{r.requests.pop();},r=>{r.runtime_responses.pop();},
    r=>{r.runtime_responses.at(-1).sha256=sha256(deriveRustWorkerBytes('http://127.0.0.1:12346/gpui-conformance/rust/drag_drop.js'));},
    r=>{r.runtime_responses=r.runtime_responses.filter(entry=>entry.path!==RUST_WORKER.loader_path);},
  ]) {const changed=structuredClone(report);mutate(changed);assert.throws(()=>validateRuntimeResponses(changed));}
  const absent=metadata('rust').report;absent.runtime_responses.pop();absent.requests.pop();assert.throws(()=>validateRuntimeResponses(absent),/worker response required/);
  const candidate=metadata('moonbit').report;appendWorker(candidate);assert.throws(()=>validateRuntimeResponses(candidate),/Only the source-derived Rust worker/);
  for(const url of ['blob:http://127.0.0.1:12345/not-a-generated-uuid','blob:http://127.0.0.1:9999/11111111-2222-4333-8444-555555555555',
    'data:application/javascript,self.injected=true','http://evil.test/worker.js'])
    assert.throws(()=>assertRustWorkerResponse({...first,url},'http://127.0.0.1:12345/gpui-conformance/rust/drag_drop.js'));
});
test('portable evidence filenames preserve raw URL and distinct response identity without lossy path sanitization',()=>{
  const urls=['http://127.0.0.1:46561/a/b','http://127.0.0.1:46561/a_b','http://127.0.0.1:46561/a%2Fb',
    'blob:http://127.0.0.1:46561/704fdaeb-7974-4057-adb4-93c68b8173c4',
    'http://localhost/../../CON?.=x:*|<>"\\\u0000\n','http://localhost/日本語/é','http://localhost/日本語/e\u0301',
    'http://localhost/\ud800','http://localhost/\ud801','data:text/javascript,'+'x'.repeat(20000)];
  const files=urls.map(url=>evidenceFilename('rust','asset',url,1));assert.equal(new Set(files).size,urls.length);
  for(const file of files){assertUploadSafeFilename(file);assert(file.length<120);assert(!/[<>:"/\\|?*\u0000-\u001f]/.test(file));}
  for(const url of urls) {
    assert.equal(evidenceFilename('rust','asset',url,1),evidenceFilename('rust','asset',url,1));
    assert.notEqual(evidenceFilename('rust','asset',url,1),evidenceFilename('rust','asset',url,2));
    assert.notEqual(evidenceFilename('rust','asset',url,1),evidenceFilename('moonbit','asset',url,1));
  }
  for(const file of ['../escape','a:b','a\\b','a/b','CON','nul.txt','aux.bin','filename.','日本語','x'.repeat(201),'trailing '])assert.throws(()=>assertUploadSafeFilename(file));
  for(const id of [0,-1,1.1,NaN,Infinity,Number.MAX_SAFE_INTEGER+1])assert.throws(()=>evidenceFilename('rust','asset',urls[0],id));
});
test('unknown script URL variants are retained upload-safely and still fail exact provenance',()=>{
  for(const runtime of ['rust','moonbit'])for(const url of ['http://127.0.0.1:12345/gpui-conformance/evil.js',
    'http://127.0.0.1:12345/gpui-conformance/a_b.js','http://127.0.0.1:12345/gpui-conformance/a/b.js',
    'http://127.0.0.1:12345/gpui-conformance/日本語.js','data:text/javascript,globalThis.bad=1']) {
    const {report}=metadata(runtime),response_id=100;
    const response={path:runtimeResponsePath(url),url,status:200,response_id,resource_type:'script',
      sha256:sha256(Buffer.from('unreviewed')),file:evidenceFilename(runtime,'asset',url,response_id),binding:{runtime,session:report.capture_session}};
    assertUploadSafeFilename(response.file);report.runtime_responses.push(response);report.requests.push({url,status:200,response_id,resource_type:'script'});
    report.served_requests.push({url:new URL(url).pathname,status:200,sha256:response.sha256});
    assert(requiresRuntimeRetention(url,'script'));assert.throws(()=>validateRuntimeResponses(report));
  }
});
test('every repeated generated response is independently reread and matched to the current derivation',()=>{
  const url='http://127.0.0.1:12345/gpui-conformance/rust/drag_drop.js',blob='blob:http://127.0.0.1:12345/11111111-2222-4333-8444-555555555555';
  const loader=Buffer.from('Synthetic loader source'),wasm=Buffer.concat([Buffer.from('Synthetic wasm container'),workerTemplate]),body=deriveRustWorkerBytes(url);
  const entries=[[RUST_WORKER.loader_path,url,loader],[RUST_WORKER.wasm_path,url.replace('.js','_bg.wasm'),wasm],[blob,blob,body],[blob,blob,body]];
  const report={runtime:'rust',build:{rust:{files:{'drag_drop.js':sha256(loader),'drag_drop_bg.wasm':sha256(wasm),'Cargo.lock':RUST_WORKER.lock_sha256}}},
    runtime_responses:entries.map(([path,url,bytes],index)=>({path,url,response_id:index+1,sha256:sha256(bytes)}))};
  const files={assets:Object.fromEntries(entries.map(([path,,bytes])=>[path,bytes])),responses:Object.fromEntries(entries.map(([,,bytes],index)=>[index+1,bytes]))};
  assertExecutedBytes(report,files);
  for(const response_id of [1,2,3,4])for(const bytes of [undefined,Buffer.from('changed original response')])
    assert.throws(()=>assertExecutedBytes(report,{...files,responses:{...files.responses,[response_id]:bytes}}));
  const changed=structuredClone(report);changed.runtime_responses[0].url=url.replace('12345','12346');
  assert.throws(()=>assertExecutedBytes(changed,files),'Changing reported loader URL cannot relabel original generated bytes');
});

test('current pair profile rejects historical identity and cross-profile reuse',()=>{
  assert.equal(PAIR_REVISION,'drag_drop_paired_pointer_v6_pattern_pin');
  assert.deepEqual(HISTORICAL_PAIR,{revision:'drag_drop_paired_pointer_v4_uniform_list_pin',
    candidate:{repository:'gpui-mbt/gpui.mbt',revision:'89108ad966c2d37b0cb44909b1aac3ecfa8e3c4a',tree:'dd5612a412d251b468c358a25baa0b0dd592c807'}});
  assert(Object.isFrozen(HISTORICAL_PAIR));assert(Object.isFrozen(HISTORICAL_PAIR.candidate));
  assert.notDeepEqual(DRAG_CANDIDATE,HISTORICAL_PAIR.candidate);
  for(const runtime of ['rust','moonbit']) {
    const {report}=metadata(runtime);validateReport(report,runtime);
    const oldLabel=structuredClone(report);oldLabel.profile_revision=HISTORICAL_PAIR.revision;
    assert.throws(()=>validateReport(oldLabel,runtime),'Old profile label cannot qualify current bytes');
    for(const pin of [HISTORICAL_PAIR.candidate,
      {...DRAG_CANDIDATE,revision:HISTORICAL_PAIR.candidate.revision},
      {...DRAG_CANDIDATE,tree:HISTORICAL_PAIR.candidate.tree}]) {
      const reused=structuredClone(report);
      reused.build.moonbit=structuredClone(pin);reused.catalog.moonbit=structuredClone(pin);
      assert.throws(()=>assertPairedProvenance(reused.build,reused.catalog),/Exact reviewed candidate core/);
      assert.throws(()=>validateReport(reused,runtime),'A current label cannot qualify old or mixed core identities');
      reused.profile_revision=HISTORICAL_PAIR.revision;
      assert.throws(()=>validateReport(reused,runtime),'Historical evidence remains historical');
    }
  }
});


test('pattern profile rejects retired popover pins and missing or mixed identities for both runtimes',()=>{
  assert.equal(PAIR_REVISION,'drag_drop_paired_pointer_v6_pattern_pin');
  assert.deepEqual(POPOVER_PAIR,{revision:'drag_drop_paired_pointer_v5_popover_pin',candidate:{repository:'gpui-mbt/gpui.mbt',
    revision:'e160f5ec7bf0c6f43738d0bdcf837098299d5569',tree:'96d62ea12a6824ee20d04cb913191bc23a424522'}});
  assert(Object.isFrozen(POPOVER_PAIR));assert(Object.isFrozen(POPOVER_PAIR.candidate));
  assert(Object.isFrozen(DRAG_CANDIDATE));
  for(const runtime of ['rust','moonbit']) {
    const current=metadata(runtime).report;validateReport(current,runtime);
    for(const revision of [undefined,null,POPOVER_PAIR.revision,'unrecognized_profile']) {
      const wrong=structuredClone(current);
      if(revision===undefined)delete wrong.profile_revision;else wrong.profile_revision=revision;
      assert.throws(()=>validateReport(wrong,runtime),'Exact current label is mandatory');
    }
    for(const pin of [POPOVER_PAIR.candidate,
      {...DRAG_CANDIDATE,revision:POPOVER_PAIR.candidate.revision},
      {...DRAG_CANDIDATE,tree:POPOVER_PAIR.candidate.tree}]) {
      const wrong=structuredClone(current);wrong.build.moonbit=structuredClone(pin);wrong.catalog.moonbit=structuredClone(pin);
      assert.throws(()=>assertPairedProvenance(wrong.build,wrong.catalog),'Matching catalog/build cannot bless retired or mixed pins');
      assert.throws(()=>validateReport(wrong,runtime),'Current label cannot qualify retired or mixed pins');
      wrong.profile_revision=POPOVER_PAIR.revision;
      assert.throws(()=>validateReport(wrong,runtime),'Retired evidence remains historical');
    }
  }
});
