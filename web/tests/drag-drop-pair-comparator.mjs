import assert from 'node:assert/strict';
import {readFile,realpath,stat} from 'node:fs/promises';
import {resolve,join,basename,sep} from 'node:path';
import {createHash} from 'node:crypto';
import {DRAG_DROP,EMBEDDED_FONTS,SOURCE_CONSTRAINTS,sha256,decodePng,discoverGeometry,assertPaint,validateProfile,
  validateOperations,profileNegativeControls,makeProfile,assertCurrentBuild} from './drag-drop-comparator.mjs';
import {RUST_WORKER,evidenceFilename,assertUploadSafeFilename,assertLocalRuntimeURL,deriveRustWorkerBytes,assertRustWorkerSource,assertRustWorkerResponse} from './drag-drop-runtime-evidence.mjs';
export {assertCurrentBuild};

// Exact published identity for the independently reviewed additive drag-session core.
export const DRAG_CANDIDATE=Object.freeze({repository:'gpui-mbt/gpui.mbt',
  revision:'fc53cb382c66f68bfc1b3e1cc72d01056cd3c625',tree:'c9ec59c5fbdbd84548b7d6ffe2c99b8403509db9'});
export const PAIR_REVISION='drag_drop_paired_pointer_v3';
export const REQUIRED_HOSTS=['moonbit/host.mjs','moonbit/render.mjs','moonbit/drag-drop-host.mjs','moonbit/focus-visible-host.mjs','moonbit/tab-stop-host.mjs','load-timing.mjs'];
export const HTML_ENTRYPOINTS=Object.freeze({
  rust:Object.freeze({path:'rust/index.html',source:'web/rust/index.html',sha256:'8f6806a2ae5f935a8212171af3890fb1460c5ab30a357032bf541222b2bd6669'}),
  moonbit:Object.freeze({path:'moonbit/index.html',source:'web/moonbit/site/index.html',sha256:'847518c000f713324bfd495925416fb8f7d2b2400273a8cb602c7906c7019f84'}),
});
export function runtimeResponsePath(url) {
  const parsed=new URL(url);if(!['http:','https:'].includes(parsed.protocol))return parsed.href;
  const path=parsed.pathname.replace(/^\/gpui-conformance\//,'');
  return path.endsWith('/')?path+'index.html':path;
}
export function requiresRuntimeRetention(url,resourceType) {
  return ['document','script','font','stylesheet'].includes(resourceType)||/\.(html|mjs|js|wasm|ttf|css)$/.test(runtimeResponsePath(url));
}
const HASH=/^[0-9a-f]{64}$/;
const hash=(value,label)=>assert.match(value||'',HASH,label);
const sameKeys=(value,keys,label)=>assert.deepEqual(Object.keys(value).sort(),[...keys].sort(),label);
export const SUITE_INPUTS=Object.freeze([
  'web/rust/index.html','web/moonbit/site/index.html',RUST_WORKER.lock_path,RUST_WORKER.template_path,
  'web/tests/drag-drop-runtime-evidence.mjs',
  'web/moonbit/drag_drop/drag_drop.mbt','web/moonbit/drag_drop/moon.pkg',
  'web/moonbit/drag_drop/drag_drop_wbtest.mbt','web/scripts/build_moonbit.py','web/scripts/build_rust.py',
  'web/tests/drag-drop-comparator.mjs','web/tests/drag-drop-pair-comparator.mjs',
  'web/tests/drag-drop-pair-browser.mjs','web/tests/compare-drag-drop-results.mjs',
  'web/scripts/decode_drag_drop_png.py',
]);
const GRAPHICS_ARGS=Object.freeze(['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']);
export {GRAPHICS_ARGS};
export function captureBinding(report,name,index) {
  return {runtime:report.runtime,session:report.capture_session,state:name,after_operation:index+1,
    route:`/${report.runtime}/?example=drag_drop`};
}
export function validateCaptureBindings(report) {
  assert.match(report.capture_session||'',/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/,'Fresh per-runtime capture session required');
  assert.equal(report.input_evidence?.file,`drag-drop-${report.runtime}-trusted-input.json`);hash(report.input_evidence.sha256,'Raw transport evidence');
  for(const [index,[name,capture]] of Object.entries(report.captures).entries()) {
    assert.deepEqual(capture.binding,captureBinding(report,name,index),'Runtime/session/operation capture origin');
    assert.equal(capture.after_operation,index+1,'Each unchanged operation has its own capture');
    assert(capture.attempts.length>=2,'Two independent screenshot requests required');
    for(const [attemptIndex,attempt] of capture.attempts.entries()) {
      assert.equal(attempt.file,`drag-drop-${report.runtime}-${name}-sample-${attemptIndex+1}-dpr1.png`,'No swapped captures or cross-runtime borrowing');
      assert.deepEqual(attempt.binding,capture.binding);assert.equal(attempt.request_ordinal,attemptIndex+1);
      assert.equal(attempt.method,'Playwright.page.screenshot');
    }
    assert(capture.stable);assert.equal(capture.file,capture.attempts.at(-1).file);
    assert.equal(capture.stability_file,capture.attempts.at(-2).file);assert.notEqual(capture.file,capture.stability_file);
  }
  assert.deepEqual(report.suite_inputs.map(entry=>entry.path),SUITE_INPUTS);
  for(const entry of report.suite_inputs) {
    assert.equal(entry.file,evidenceFilename(report.runtime,'suite',entry.path));hash(entry.sha256,'Current source bytes');
    const html=Object.values(HTML_ENTRYPOINTS).find(value=>value.source===entry.path);
    if(html)assert.equal(entry.sha256,html.sha256,'Exact source HTML entrypoint; no extra inline execution');
    if(entry.path===RUST_WORKER.lock_path)assert.equal(entry.sha256,RUST_WORKER.lock_sha256,'Pinned worker dependency lock');
    if(entry.path===RUST_WORKER.template_path)assert.equal(entry.sha256,RUST_WORKER.template_sha256,'Pinned generated worker source template');
  }
}
export function inputEvidence(report) {
  return {runtime:report.runtime,capture_session:report.capture_session,profile_revision:report.profile_revision,
    startup_events:report.startup_events,startup_mouse_events:report.startup_mouse_events,
    operation_start:report.operation_start,mouse_operation_start:report.mouse_operation_start,
    operations:report.operations,events:report.events,mouse_events:report.mouse_events};
}
export function validateInputEvidence(report,evidence) {
  assert.deepEqual(evidence,inputEvidence(report),'Report cannot fabricate or remove delivery independently of retained raw transport');
}
export function assertCaptureDigests(report,retained) {
  for(const [name,capture] of Object.entries(report.captures)) {
    assert.equal(sha256(retained.images[name].data),capture.rgba_sha256,'Original final RGBA binding');
    assert.equal(sha256(retained.stableImages[name].data),capture.stability_rgba_sha256,'Original stability RGBA binding');
    assert.equal(capture.rgba_sha256,capture.stability_rgba_sha256,'Complete RGBA must stabilize independently');
  }
}
export function assertExecutedBytes(report,files) {
  for(const entry of report.runtime_responses) {
    assert.equal(sha256(files.assets[entry.path]),entry.sha256,'Actual retained executed runtime bytes required');
    assert.equal(sha256(files.responses[entry.response_id]),entry.sha256,'Every original response retained separately, including cached blob URLs');
  }
  if(report.runtime==='rust') {
    assertRustWorkerSource(report.build,files.assets);
    const loader=report.runtime_responses.find(entry=>entry.path===RUST_WORKER.loader_path);
    for(const entry of report.runtime_responses)if(new URL(entry.url).protocol==='blob:')
      assert.deepEqual(files.responses[entry.response_id],deriveRustWorkerBytes(loader.url),'Original generated bytes equal the current served WASM template and loader URL derivation');
  }
}
export function pairedEvidenceNegativeControls(report,files) {
  validateCaptureBindings(report);validateInputEvidence(report,JSON.parse(files.inputBytes));
  assertExecutedBytes(report,files);assertCaptureDigests(report,files);
  const rejected=[],check=(name,run)=>{assert.throws(run,name);rejected.push({name,rejected:true});};
  const clone=()=>structuredClone(report);
  const swapped=clone();[swapped.captures.color0_accepted,swapped.captures.color1_accepted]=[swapped.captures.color1_accepted,swapped.captures.color0_accepted];
  check('swapped_capture_origin',()=>validateCaptureBindings(swapped));
  const borrowed=clone();borrowed.captures.initial.binding.runtime=report.runtime==='rust'?'moonbit':'rust';
  check('cross_runtime_capture_borrowing',()=>validateCaptureBindings(borrowed));
  const missing=clone();missing.operations[1].events=[];
  check('removed_original_delivery',()=>validateInputEvidence(missing,JSON.parse(files.inputBytes)));
  const fabricated=clone();fabricated.operations[1].events.push({...fabricated.operations[1].events[0]});
  check('fabricated_original_delivery',()=>validateInputEvidence(fabricated,JSON.parse(files.inputBytes)));
  for(const path of requiredRuntimeFiles(report.runtime)) {
    const corrupted={...files,assets:{...files.assets,[path]:Buffer.from('corrupted executed asset')}};
    check('wrong_executed_'+path.replaceAll('/','_'),()=>assertExecutedBytes(report,corrupted));
  }
  for(const entry of report.runtime_responses)if(entry.url&&new URL(entry.url).protocol==='blob:') {
    for(const [kind,bytes] of [['corrupted',Buffer.from('altered generated worker')],['missing',undefined]])
      check(`${kind}_generated_response_${entry.response_id}`,()=>assertExecutedBytes(report,{...files,responses:{...files.responses,[entry.response_id]:bytes}}));
  }
  const original=files.images.initial,changed={...original,data:original.data.slice()};changed.data[0]^=1;
  check('original_rgba_tampering',()=>assertCaptureDigests(report,{...files,images:{...files.images,initial:changed}}));
  return rejected;
}
export function assertPairedProvenance(build,catalog) {
  assert.match(DRAG_CANDIDATE.revision||'',/^[0-9a-f]{40}$/,'Exact reviewed public drag-session core commit');
  assert.match(DRAG_CANDIDATE.tree||'',/^[0-9a-f]{40}$/,'Exact reviewed public drag-session core tree');
  assert.equal(build.upstream?.repository,'zed-industries/zed');assert.equal(build.upstream?.revision,DRAG_DROP.revision);
  assert.deepEqual(build.moonbit,DRAG_CANDIDATE,'Exact reviewed candidate core commit/tree');
  assert.deepEqual(catalog.upstream,build.upstream);assert.deepEqual(catalog.moonbit,build.moonbit);
  assert.equal(build.lab_tracked_dirty,false);assert.match(build.lab_revision||'',/^[0-9a-f]{40}$/);assert.match(build.lab_tree||'',/^[0-9a-f]{40}$/);
  assert.equal(build.rust_bundled,true);assert.equal(build.rust?.source_modified,false);assert.equal(build.rust.packaging?.upstream_files_modified,false);
  assert.equal(build.rust.source_revision,DRAG_DROP.revision);assert.equal(build.rust.source_tree,DRAG_DROP.tree);
  assert.equal(build.rust.oracle_only,false);assert.deepEqual(build.rust.implemented_subset,['drag_drop']);
  assert.deepEqual(build.rust_implemented,['drag_drop']);assert.deepEqual(build.rust_oracle_only,[],'Historical extra-oracle records cannot certify an implemented pair');
  assert(build.implemented.includes('drag_drop'));assert.deepEqual(build.implemented_sources?.drag_drop,{source:DRAG_DROP.source,source_blob:DRAG_DROP.sourceBlob});
  const entries=catalog.examples.filter(entry=>entry.id==='drag_drop');assert.equal(entries.length,1);
  for(const [key,value] of Object.entries({moonbit:'implemented',source:DRAG_DROP.source,source_blob:DRAG_DROP.sourceBlob,
    candidate_source:'web/moonbit/drag_drop/drag_drop.mbt',width:800,height:600}))assert.equal(entries[0][key],value);
  assert.notEqual(entries[0].rust,'oracle_only');
  assert.deepEqual(build.rust_subset_sources,[{id:'drag_drop',source:DRAG_DROP.source,source_blob:DRAG_DROP.sourceBlob,
    source_sha256:DRAG_DROP.sourceSha256,upstream_revision:DRAG_DROP.revision,status:'implemented_subset',candidate:'implemented'}]);
  assert.deepEqual(build.rust.packaging.additional_bins,[{name:'drag_drop',source:DRAG_DROP.source}]);
  assert(build.rust.command.includes('+nightly-2026-10-14'));assert(build.rust.command.includes('--locked'));
  assert.deepEqual(build.rust.command.filter((_value,index,array)=>array[index-1]==='--bin'),['drag_drop']);
  assert.match(build.rust.toolchain||'',/^rustc 1\./);assert.equal(build.rust.bindings,'wasm-bindgen 0.2.129');
  assert(Number.isFinite(Date.parse(build.rust.build_completed_at_utc||'')));
  for(const file of ['drag_drop.js','drag_drop_bg.wasm','host.mjs','packaging-Cargo.toml'])hash(build.rust.files?.[file],file);
  assert.equal(build.rust.files['unchanged-source/drag_drop.rs'],DRAG_DROP.sourceSha256);
  assert.equal(build.rust.files['index.html'],HTML_ENTRYPOINTS.rust.sha256,'Exact built Rust HTML entrypoint');
  assert.equal(build.rust.files['Cargo.lock'],RUST_WORKER.lock_sha256,'Exact built Rust dependency lock');
  assert.equal(build.rust.files['packaging-Cargo.toml'],build.rust.packaging.manifest_sha256);
  assert.deepEqual(Object.fromEntries(Object.entries(build.rust.embedded_fonts||{}).map(([path,font])=>[path,font.sha256])),EMBEDDED_FONTS);
  for(const font of Object.values(build.rust.embedded_fonts))assert.equal(build.rust.files[font.file],font.sha256);
  assert.match(build.compiler||'',/^moon \S+[^\n]*\nmoonc \S+/,'Measured MoonBit CLI and compiler versions');
  assert.equal(build.moonbit_unit_tests,'passed');assert.equal(build.comparison_status,'unverified');
  hash(build.runtime_sha256_by_example?.drag_drop,'Actual compiled candidate');
  for(const file of REQUIRED_HOSTS)hash(build.moonbit_host_files_sha256?.[file],file);
  assert.deepEqual(build.font_sha256_by_file,Object.fromEntries(['IBMPlexSans-Regular.ttf','IBMPlexSans-Italic.ttf','IBMPlexSans-SemiBold.ttf'].map(name=>[name,EMBEDDED_FONTS['assets/fonts/ibm-plex-sans/'+name]])));
  assert.equal(build.font_sha256,build.font_sha256_by_file['IBMPlexSans-Regular.ttf']);
  return {id:'drag_drop',source:DRAG_DROP.source,source_blob:DRAG_DROP.sourceBlob,source_sha256:DRAG_DROP.sourceSha256,
    upstream_revision:DRAG_DROP.revision,width:800,height:600,dpr:1,status:'paired_profile',candidate:'implemented'};
}
export function pairedProvenanceNegativeControls(build,catalog) {
  assertPairedProvenance(build,catalog);
  return [['dirty_lab',b=>{b.lab_tracked_dirty=true;}],['wrong_core_commit',b=>{b.moonbit.revision='0'.repeat(40);}],
    ['historical_baseline_core',b=>{b.moonbit={repository:'gpui-mbt/gpui.mbt',revision:'eb968228bbea56aff13721dc427875c2dacffc14',tree:'ae9072d350ef6d1546e408226218ec08efc96552'};}],
    ['wrong_core_tree',b=>{b.moonbit.tree='0'.repeat(40);}],['modified_source',b=>{b.rust.source_modified=true;}],
    ['wrong_source_tree',b=>{b.rust.source_tree='0'.repeat(40);}],
    ['wrong_source_blob',b=>{b.rust_subset_sources[0].source_blob='0'.repeat(40);}],
    ['historical_oracle_claim',b=>{b.rust.oracle_only=true;}],['missing_subset',b=>{b.rust.implemented_subset=null;}],
    ['missing_wasm_hash',b=>{delete b.rust.files['drag_drop_bg.wasm'];}],
    ['missing_built_worker_lock',b=>{delete b.rust.files['Cargo.lock'];}],
    ['wrong_built_worker_lock',b=>{b.rust.files['Cargo.lock']='0'.repeat(64);}],
    ['wrong_rust_html_entrypoint',b=>{b.rust.files['index.html']='0'.repeat(64);}],
    ['missing_candidate_hash',b=>{delete b.runtime_sha256_by_example.drag_drop;}],
    ['missing_host_hash',b=>{delete b.moonbit_host_files_sha256['moonbit/drag-drop-host.mjs'];}],
    ['missing_renderer_hash',b=>{delete b.moonbit_host_files_sha256['moonbit/render.mjs'];}],
    ['missing_compiler',b=>{delete b.compiler;}],['wrong_font',b=>{b.font_sha256_by_file['IBMPlexSans-Regular.ttf']='0'.repeat(64);}]]
    .map(([name,mutate])=>{const copy=structuredClone(build);mutate(copy);assert.throws(()=>assertPairedProvenance(copy,catalog),name);return {name,rejected:true};});
}
export function expectedRuntimeFiles(build,runtime) {
  if(runtime==='rust')return {...Object.fromEntries(Object.entries(build.rust.files).map(([file,digest])=>['rust/'+file,digest])),
    'load-timing.mjs':build.moonbit_host_files_sha256['load-timing.mjs']};
  assert.equal(runtime,'moonbit');
  return {...build.moonbit_host_files_sha256,'moonbit/drag_drop.mjs':build.runtime_sha256_by_example.drag_drop,
    [HTML_ENTRYPOINTS.moonbit.path]:HTML_ENTRYPOINTS.moonbit.sha256,
    ...Object.fromEntries(Object.entries(build.font_sha256_by_file).map(([file,digest])=>['moonbit/'+file,digest]))};
}
export function requiredRuntimeFiles(runtime) {
  return runtime==='rust'?['rust/index.html','rust/host.mjs','rust/drag_drop.js','rust/drag_drop_bg.wasm','load-timing.mjs']:
    ['moonbit/index.html','moonbit/drag_drop.mjs',...REQUIRED_HOSTS,'moonbit/IBMPlexSans-Regular.ttf'];
}
export function validateReport(report,runtime) {
  assert.equal(report.runtime,runtime);assert(['rust','moonbit'].includes(runtime));
  assert.equal(report.status,`${runtime}_profile_captured`);assert.equal(report.mode,'paired_profile_capture');
  assert.equal(report.profile_revision,PAIR_REVISION);assert.equal(report.candidate,'implemented');
  assert.equal(report.comparison,'not_run');assert.equal(report.conformance,'not_claimed');assert.equal(report.failure,undefined);
  assert.equal(Object.keys(report.captures).length,54);assert.equal(report.operations.length,54,'Complete fixed source profile required');
  assert(report.environment&&typeof report.environment==='object','Actual independent runtime environment');
  assert.match(report.environment.browser||'',/^\d+\.\d+\.\d+\.\d+$/);assert.match(report.environment.node||'',/^v\d+\.\d+\.\d+$/);
  assert.equal(report.environment.playwright,'1.56.1');assert.equal(report.environment.platform,'linux');assert.equal(report.environment.arch,'x64');
  assert.deepEqual(report.environment.graphics_requested,GRAPHICS_ARGS);
  assert(report.graphics_actual&&typeof report.graphics_actual==='object','Actual browser graphics observation required');
  const gpu=report.graphics_actual.gpu,renderer=gpu?.auxAttributes?.glRenderer||gpu?.devices?.map(device=>device.deviceString).join(' ');
  assert.match(renderer||'',/swiftshader/i,'Actual measured Chromium software renderer');
  assert.equal(report.graphics_evidence?.file,`drag-drop-${runtime}-graphics.json`);hash(report.graphics_evidence.sha256,'Retained actual graphics observation');
  assert.deepEqual(report.errors,[]);assert(report.console.every(entry=>entry.type!=='error'));
  assert.deepEqual(report.profile,{width:800,height:600,dpr:1});assert.deepEqual(report.source_constraints,SOURCE_CONSTRAINTS);
  assert.deepEqual(report.canvas,{bounds:{x:0,y:0,width:800,height:600},backing:{width:800,height:600}});
  assert.equal(report.transport?.canvas_tab_index,-1,'Canvas is not a DOM tab stop');
  assert.deepEqual(report.source,assertPairedProvenance(report.build,report.catalog));
  assert.deepEqual(report.provenance_negative_controls,pairedProvenanceNegativeControls(report.build,report.catalog));
  for(const key of ['build_evidence','catalog_evidence']){assert.equal(report[key].file,`drag-drop-${runtime}-${key==='build_evidence'?'build-manifest':'catalog'}.json`);hash(report[key].sha256,key);}
  validateCaptureBindings(report);
  assert.equal(report.decoder.name,'Pillow');assert.equal(report.decoder.version,'12.0.0');hash(report.decoder.sha256,'Decoder source');
  return validateRuntimeResponses(report);
}
export function validateRuntimeResponses(report) {
  const runtime=report.runtime,files=expectedRuntimeFiles(report.build,runtime),seen=new Set(),responseIds=new Set();
  const document=report.runtime_responses.find(entry=>entry.path===HTML_ENTRYPOINTS[runtime].path);
  assert(document,'Actual runtime document required');const origin=assertLocalRuntimeURL(document.url).origin;
  const loader=report.runtime_responses.find(entry=>entry.path===RUST_WORKER.loader_path);
  let generated=0;
  for(const response of report.runtime_responses) {
    assert(Number.isSafeInteger(response.response_id)&&response.response_id>0&&!responseIds.has(response.response_id),'Distinct actual executable response');responseIds.add(response.response_id);
    assert.deepEqual(response.binding,{runtime,session:report.capture_session},'Same-runtime/session response ownership');
    assert.equal(response.status,200);const url=new URL(response.url);
    assert.equal(runtimeResponsePath(response.url),response.path);
    assert(requiresRuntimeRetention(response.url,response.resource_type),'Actual executable/document/font response type');
    if(url.protocol==='blob:') {
      assert.equal(runtime,'rust','Only the source-derived Rust worker can generate executable blobs');assert(loader,'Actual pinned worker loader response');
      assertRustWorkerResponse(response,loader.url);generated++;
    } else {
      assert.equal(assertLocalRuntimeURL(response.url).origin,origin,'Actual local runtime server');
      assert(Object.hasOwn(files,response.path),'All executed dependencies must be pinned');assert.equal(response.sha256,files[response.path]);
      if(response.path===HTML_ENTRYPOINTS[runtime].path) {
        assert.equal(response.resource_type,'document');assert.equal(url.pathname,`/gpui-conformance/${runtime}/`);
        assert.equal(url.search,'?example=drag_drop','Actual current example document route');
      } else assert.equal(response.url,origin+'/gpui-conformance/'+response.path,'Exact served dependency URL');
      assert(report.served_requests.some(entry=>entry.url===url.pathname+url.search&&entry.status===200&&entry.sha256===response.sha256),'Server byte observation');
    }
    assert.equal(response.file,evidenceFilename(runtime,'asset',response.url,response.response_id));
    assert(report.requests.some(entry=>entry.url===response.url&&entry.status===200&&entry.response_id===response.response_id&&entry.resource_type===response.resource_type),'Browser request observation');seen.add(response.path);
  }
  for(const path of requiredRuntimeFiles(runtime))assert(seen.has(path),`Actual required runtime dependency: ${path}`);
  if(runtime==='rust')assert(generated>0,'Actual source-generated Rust worker response required');
  const requestIds=new Set();
  for(const request of report.requests) {
    assert(Number.isSafeInteger(request.response_id)&&request.response_id>0&&!requestIds.has(request.response_id),'Distinct browser response identity');requestIds.add(request.response_id);
    if(requiresRuntimeRetention(request.url,request.resource_type))
      assert(report.runtime_responses.some(response=>response.url===request.url&&response.response_id===request.response_id),'Every code/font request must retain actual response bytes');
  }
  return {status:'passed',runtime,loaded_dependencies:seen.size,generated_worker_responses:generated};
}

export async function loadEvidence(directory,report) {
  const root=await realpath(resolve(directory));
  const local=async(file,digest,max=64*1024*1024)=>{
    assertUploadSafeFilename(file);
    assert(typeof file==='string'&&file===basename(file)&&file!=='.'&&file!=='..'&&!file.includes('\\'),'Direct local evidence filename');
    const path=await realpath(join(root,file));assert(path.startsWith(root+sep));assert.equal(path,join(root,file),'Independent regular evidence, not symlink aliases');const info=await stat(path);
    assert(info.isFile()&&info.nlink===1&&info.size>0&&info.size<=max,'Bounded nonempty independently retained file');const bytes=await readFile(path);assert.equal(sha256(bytes),digest,`${file}: raw bytes hash`);return bytes;
  };
  const manifestBytes=await local(report.build_evidence.file,report.build_evidence.sha256),catalogBytes=await local(report.catalog_evidence.file,report.catalog_evidence.sha256);
  assert.deepEqual(JSON.parse(manifestBytes),report.build);assert.deepEqual(JSON.parse(catalogBytes),report.catalog);
  const decoder=await local(`drag-drop-${report.runtime}-png-decoder.py`,report.decoder.sha256);
  assert.equal(sha256(decoder),sha256(await readFile(new URL('../scripts/decode_drag_drop_png.py',import.meta.url))));
  const inputBytes=await local(report.input_evidence.file,report.input_evidence.sha256);
  validateInputEvidence(report,JSON.parse(inputBytes));
  const graphicsBytes=await local(report.graphics_evidence.file,report.graphics_evidence.sha256);
  assert.deepEqual(JSON.parse(graphicsBytes),report.graphics_actual,'Report cannot substitute the measured graphics observation');
  assert.deepEqual(report.suite_inputs.map(entry=>entry.path),SUITE_INPUTS,'Exact current suite inputs required');
  const suiteInputs={};for(const entry of report.suite_inputs) {
    suiteInputs[entry.path]=await local(entry.file,entry.sha256);
    assert.deepEqual(suiteInputs[entry.path],await readFile(new URL('../../'+entry.path,import.meta.url)),'Retained source must match actual current clean checkout');
  }
  const assets={},responses={};for(const entry of report.runtime_responses) {
    const bytes=await local(entry.file,entry.sha256);responses[entry.response_id]=bytes;assets[entry.path]=bytes;
  }
  assertExecutedBytes(report,{assets,responses});
  for(const [path,bytes] of Object.entries(assets)) {
    const html=Object.values(HTML_ENTRYPOINTS).find(value=>value.path===path);
    const current=html?.source||(path==='rust/host.mjs'?'web/rust/host.mjs':path==='load-timing.mjs'?'web/load-timing.mjs':
      Object.hasOwn(report.build.moonbit_host_files_sha256,path)?'web/moonbit/site/'+path.slice('moonbit/'.length):null);
    if(current)assert.deepEqual(bytes,await readFile(new URL('../../'+current,import.meta.url)),'Served HTML/host/renderer must match the actual current checkout');
  }
  const support={};
  const expectedSupport=['rust/unchanged-source/drag_drop.rs','rust/packaging-Cargo.toml','rust/Cargo.lock',...Object.values(report.build.rust.embedded_fonts).map(font=>'rust/'+font.file)];
  assert.deepEqual(report.support_files.map(entry=>entry.path).sort(),expectedSupport.sort());
  for(const entry of report.support_files) {
    assert.equal(entry.file,evidenceFilename(report.runtime,'input',entry.path));
    assert.equal(entry.sha256,report.build.rust.files[entry.path.slice(5)]);support[entry.path]=await local(entry.file,entry.sha256);
    if(entry.path.endsWith('.rs'))assert.equal(createHash('sha1').update(Buffer.from(`blob ${support[entry.path].length}\0`)).update(support[entry.path]).digest('hex'),DRAG_DROP.sourceBlob);
  }
  const images={},stableImages={},used=new Set();
  for(const [name,capture] of Object.entries(report.captures)) {
    assert(capture.stable&&capture.file!==capture.stability_file);assert(capture.attempts.length>=2);
    assert.equal(capture.attempts.at(-1).file,capture.file);assert.equal(capture.attempts.at(-2).file,capture.stability_file);
    for(let index=0;index<capture.attempts.length;index++) {
      const attempt=capture.attempts[index];assert.equal(attempt.file,`drag-drop-${report.runtime}-${name}-sample-${index+1}-dpr1.png`);
      assert(!used.has(attempt.file));used.add(attempt.file);const image=decodePng(await local(attempt.file,attempt.png_sha256,8*1024*1024));
      assert.equal(sha256(image.data),attempt.rgba_sha256);assert.equal(attempt.width,800);assert.equal(attempt.height,600);
      if(attempt.file===capture.file)images[name]=image;if(attempt.file===capture.stability_file)stableImages[name]=image;
    }
    assert.equal(sha256(images[name].data),capture.rgba_sha256);assert.equal(sha256(stableImages[name].data),capture.stability_rgba_sha256);
    assert.equal(sha256(images[name].data),sha256(stableImages[name].data),'Two original independently decoded stable samples');
    await local(capture.file,capture.png_sha256);await local(capture.stability_file,capture.stability_png_sha256);
  }
  return {manifestBytes,catalogBytes,inputBytes,graphicsBytes,suiteInputs,assets,responses,support,images,stableImages};
}
export function validatePixels(report,retained) {
  const geometry=discoverGeometry(retained.images.initial),profile=makeProfile(geometry);
  assert.equal(profile.operations.length,54);assert.equal(Object.keys(profile.captures).length,54);
  sameKeys(retained.images,Object.keys(profile.captures),'All 54 actual original final images');
  sameKeys(retained.stableImages,Object.keys(profile.captures),'All 54 independent stable images');
  // Only the original decoded PNG supplies geometry. Optional candidate model
  // diagnostics and report-provided checks/state/geometry are deliberately unused.
  const delivery=validateTransport(report,geometry),paint=validateProfile(retained.images,geometry);
  const stableGeometry=discoverGeometry(retained.stableImages.initial);assert.deepEqual(stableGeometry,geometry);
  assert.deepEqual(validateProfile(retained.stableImages,stableGeometry),paint);
  assertCaptureDigests(report,retained);
  return {geometry,profile,paint,delivery};
}
export function validateTransport(report,geometry) {
  const delivery=validateOperations(report,geometry);
  assert.equal(report.operation_start,report.startup_events.length);assert.equal(report.mouse_operation_start,report.startup_mouse_events.length);
  assert.deepEqual(report.events.slice(0,report.operation_start),report.startup_events);
  assert.deepEqual(report.mouse_events.slice(0,report.mouse_operation_start),report.startup_mouse_events);
  for(const stream of [report.events,report.mouse_events])for(let index=0;index<stream.length;index++) {
    const event=stream[index];assert(Number.isFinite(event.time)&&event.time>=0,'Actual trusted transport time');
    if(index)assert(event.time>=stream[index-1].time,'Trusted delivery chronology');
    assert.equal(typeof event.defaultPrevented,'boolean','Measured post-delivery suppression');
    if(event.type.startsWith('pointer'))for(const key of ['shiftKey','ctrlKey','altKey','metaKey'])assert.equal(event[key],false,'Unmodified fixed source profile');
  }
  return delivery;
}
export function compareMeasurements(rust,moonbit) {
  assert.deepEqual(moonbit.geometry,rust.geometry,'Independent PNG-derived source geometry must agree');
  assert.deepEqual(moonbit.profile,rust.profile,'Independent source-derived trusted operation plans must agree');
  assert.deepEqual(moonbit.paint,rust.paint,'Both original pixel sets pass unchanged bounded source predicates');
  assert.equal(moonbit.delivery.operations,rust.delivery.operations);
  // Browser suppression may differ. Each actual duplicate-up / optional mouse
  // delivery has already been checked separately; never invent missing events.
  return {status:'source_measurements_agree',operations:54,states:54,
    duplicate_releases:{rust:rust.delivery.duplicate_releases,moonbit:moonbit.delivery.duplicate_releases}};
}
export function pairedPixelNegativeControls(report,retained,measured) {
  const rejected=profileNegativeControls(retained.images,measured.geometry,report);
  const check=(name,run)=>{assert.throws(run,name);rejected.push({name,rejected:true});};
  const profile=measured.profile,images=retained.images;
  // Source checks alone are used here so falsified self-reported checks cannot
  // make a corrupt paint/input sample pass a cross-runtime equality comparison.
  check('wrong_green_128',()=>{
    const state=profile.captures.color2_accepted,image={...images.color2_accepted,data:images.color2_accepted.data.slice()};
    const r=measured.geometry.target;image.data.set([0,255,0,255],4*((r.y+10)*800+r.x));
    assertPaint(image,measured.geometry,state);
  });
  check('swapped_accepted_capture',()=>assertPaint(images.color1_accepted,measured.geometry,profile.captures.color0_accepted));
  const input=structuredClone(report),operation=input.operations.find(entry=>entry.name==='far_release_only');
  operation.events[0].x=operation.action.x-1;
  input.events=input.operations.flatMap(entry=>entry.events);
  check('fabricated_plan_and_delivered_far_release',()=>validateOperations(input,measured.geometry));
  const duplicate=structuredClone(report),up=duplicate.operations.find(entry=>entry.duplicate);
  const event={type:'pointerup',...up.mouse_expected,pointerType:'mouse',trusted:true,target:'CANVAS'};
  up.events=[event,event];check('fabricated_duplicate_up_count',()=>validateOperations(duplicate,measured.geometry));
  return rejected;
}
export function validateCurrentSources(report,sourceBytes) {
  for(const entry of report.suite_inputs) {
    assert(sourceBytes[entry.path] instanceof Uint8Array,'Retained current suite source bytes required');
    assert.equal(sha256(sourceBytes[entry.path]),entry.sha256,'Actual current source bytes');
  }
}
export function compareBehavior(rust,moonbit,retained) {
  validateReport(rust,'rust');validateReport(moonbit,'moonbit');assert(retained.rust&&retained.moonbit);
  assert.notEqual(rust.capture_session,moonbit.capture_session,'Each runtime is independently executed in a fresh context');
  assert.deepEqual(rust.build,moonbit.build);assert.deepEqual(rust.catalog,moonbit.catalog);
  assert.deepEqual(rust.environment,moonbit.environment);
  assert.equal(rust.build_evidence.sha256,moonbit.build_evidence.sha256);assert.equal(rust.catalog_evidence.sha256,moonbit.catalog_evidence.sha256);
  const checked={};
  for(const [runtime,report] of [['rust',rust],['moonbit',moonbit]]) {
    const files=retained[runtime];assert.equal(sha256(files.manifestBytes),report.build_evidence.sha256);assert.equal(sha256(files.catalogBytes),report.catalog_evidence.sha256);
    assert.equal(sha256(files.inputBytes),report.input_evidence.sha256);validateInputEvidence(report,JSON.parse(files.inputBytes));
    assert.equal(sha256(files.graphicsBytes),report.graphics_evidence.sha256);assert.deepEqual(JSON.parse(files.graphicsBytes),report.graphics_actual);
    validateCurrentSources(report,files.suiteInputs);
    assertExecutedBytes(report,files);
    const supportPaths=['rust/unchanged-source/drag_drop.rs','rust/packaging-Cargo.toml','rust/Cargo.lock',...Object.values(report.build.rust.embedded_fonts).map(font=>'rust/'+font.file)];
    assert.deepEqual(report.support_files.map(entry=>entry.path).sort(),supportPaths.sort(),'All pinned source/font inputs required');
    sameKeys(files.support,supportPaths,'Actual retained source/font inputs');
    for(const entry of report.support_files) {
      assert.equal(sha256(files.support[entry.path]),entry.sha256,'Actual retained source/font bytes required');
      assert.equal(entry.sha256,report.build.rust.files[entry.path.slice(5)]);
    }
    checked[runtime]=validatePixels(report,files);
    checked[runtime].negative_controls=[...pairedPixelNegativeControls(report,files,checked[runtime]),...pairedEvidenceNegativeControls(report,files)];
  }
  const wasm=retained.rust.assets['rust/drag_drop_bg.wasm'];
  for(const [path,bytes] of Object.entries(retained.rust.support)) {
    assert.deepEqual(bytes,retained.moonbit.support[path],'Both independently retained immutable support inputs');
    if(path.endsWith('.ttf'))assert(wasm.includes(bytes),'Actual served Rust WASM embeds each complete pinned font');
  }
  const agreement=compareMeasurements(checked.rust,checked.moonbit);
  return {status:'passed',comparison:'independently_decoded_drag_drop_source_behavior',conformance:'bounded_source_profile_only',
    scope:'Actual unchanged Rust WASM and compiled MoonBit; separate 54-operation/54-state source profile at 800x600 DPR1',
    source:rust.source,build:{lab_revision:rust.build.lab_revision,lab_tree:rust.build.lab_tree,moonbit:rust.build.moonbit,upstream:rust.build.upstream},
    agreement,geometry:checked.rust.geometry,paint:checked.rust.paint,
    delivery:{rust:checked.rust.delivery,moonbit:checked.moonbit.delivery},
    negative_controls:{rust:checked.rust.negative_controls,moonbit:checked.moonbit.negative_controls},
    unverified:['Exact text/OCR, glyph/antialiasing or full-image equality','GPU shadow blur-kernel equality','Native parity',
      'Native/global capture, touch and OS drag','Other browsers/GPUs/viewports/DPRs',
      'Foreign payloads, rejecting predicates, nested/overlapping targets','Internal payload/activation grip identity',
      'Negative or fractional grips (source-derived candidate tests only; not this unchanged baseline)']};
}
