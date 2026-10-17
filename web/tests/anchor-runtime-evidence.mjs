// Isolated anchor source-only evidence contract; historical profiles are unchanged.
import assert from 'node:assert/strict';
import {readFile,realpath,stat} from 'node:fs/promises';
import {resolve,join,basename,sep} from 'node:path';
import {createHash} from 'node:crypto';
import {ANCHOR,SOURCE_CONSTRAINTS,PROFILE_REVISION,VIEWPORT_SEQUENCE,UNVERIFIED,sha256,decodePng,
  validateProfile,validateOperations,profileNegativeControls,assertCurrentBuild,assertProvenance,provenanceNegativeControls} from './anchor-comparator.mjs';
import {RUST_WORKER,evidenceFilename,assertUploadSafeFilename,assertLocalRuntimeURL,deriveRustWorkerBytes,assertRustWorkerSource,assertRustWorkerResponse} from './anchor-worker-evidence.mjs';
export {assertCurrentBuild};
export const HTML_ENTRYPOINTS=Object.freeze({rust:Object.freeze({path:'rust/index.html',source:'web/rust/index.html',sha256:'8f6806a2ae5f935a8212171af3890fb1460c5ab30a357032bf541222b2bd6669'})});
const HASH=/^[0-9a-f]{64}$/;
const hash=(value,label)=>assert.match(value||'',HASH,label);
export const SUITE_INPUTS=Object.freeze([
  'web/rust/index.html','web/rust/host.mjs',RUST_WORKER.lock_path,RUST_WORKER.template_path,
  'web/tests/anchor-worker-evidence.mjs','web/tests/anchor-runtime-evidence.mjs',
  'web/tests/fixtures/anchor-rust-only-catalog-a20e5888.json','web/scripts/prepare_anchor_site.py',
  'web/scripts/build_moonbit.py','web/scripts/build_rust.py','web/load-timing.mjs','web/oracles/anchor.json',
  'web/tests/anchor-comparator.mjs','web/tests/anchor-oracle-browser.mjs',
  'web/tests/verify-anchor-results.mjs','web/scripts/decode_anchor_png.py',
  '.github/workflows/anchor-oracle.yml',
]);
export const GRAPHICS_ARGS=Object.freeze(['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']);
export function runtimeResponsePath(url) {
  const parsed=new URL(url);if(!['http:','https:'].includes(parsed.protocol))return parsed.href;
  const path=parsed.pathname.replace(/^\/gpui-conformance\//,'');
  return path.endsWith('/')?path+'index.html':path;
}
export function requiresRuntimeRetention(url,resourceType) {
  return ['document','script','font','stylesheet'].includes(resourceType)||/\.(html|mjs|js|wasm|ttf|css)$/.test(runtimeResponsePath(url));
}
export function captureBinding(report,name,index) {
  return {runtime:report.runtime,session:report.capture_session,state:name,after_operation:index+1,
    route:`/${report.runtime}/?example=anchor`,document_id:report.document_id,
    viewport:{width:VIEWPORT_SEQUENCE.find(state=>state.name===name).width,height:600,dpr:1}};
}
export function validateCaptureBindings(report) {
  assert.match(report.capture_session||'',/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/,'Fresh per-runtime capture session required');
  assert.deepEqual(Object.keys(report.captures),VIEWPORT_SEQUENCE.map(state=>state.name));
  assert.equal(report.input_evidence?.file,`anchor-${report.runtime}-trusted-input.json`);hash(report.input_evidence.sha256,'Raw transport evidence');
  for(const [index,[name,capture]] of Object.entries(report.captures).entries()) {
    assert.deepEqual(capture.binding,captureBinding(report,name,index-1),'Runtime/session/operation capture origin');
    assert.equal(capture.after_operation,index,'Each actual state has its own capture');
    assert(capture.attempts.length>=2,'Two independent screenshot requests required');
    for(const [attemptIndex,attempt] of capture.attempts.entries()) {
      assert.equal(attempt.file,`anchor-${report.runtime}-${name}-sample-${attemptIndex+1}-dpr1.png`,'No swapped captures or cross-runtime borrowing');
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
    document_id:report.document_id,navigation_count:report.navigation_count,initial_viewport:report.initial_viewport,
    startup_events:report.startup_events,
    operation_start:report.operation_start,
    operations:report.operations,events:report.events};
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
export function evidenceNegativeControls(report,files) {
  validateCaptureBindings(report);validateInputEvidence(report,JSON.parse(files.inputBytes));
  assertExecutedBytes(report,files);assertCaptureDigests(report,files);
  const rejected=[],check=(name,run)=>{assert.throws(run,name);rejected.push({name,rejected:true,kind:'corrupted_evidence_sensitivity_not_executed_mutant'});};
  const clone=()=>structuredClone(report);
  const swapped=clone();[swapped.captures.wideTopLeft,swapped.captures.wideTopRight]=[swapped.captures.wideTopRight,swapped.captures.wideTopLeft];
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
export function expectedRuntimeFiles(build,runtime) {
  assert.equal(runtime,'rust');
  return {...Object.fromEntries(Object.entries(build.rust.files).map(([file,digest])=>['rust/'+file,digest])),
    'load-timing.mjs':build.moonbit_host_files_sha256['load-timing.mjs']};
}
export function requiredRuntimeFiles(runtime) {
  assert.equal(runtime,'rust');return ['rust/index.html','rust/host.mjs','rust/anchor.js','rust/anchor_bg.wasm','load-timing.mjs'];
}
export function validateReport(report,runtime) {
  assert.equal(report.runtime,runtime);assert.equal(runtime,'rust');
  assert.equal(report.status,`${runtime}_profile_captured`);assert.equal(report.mode,'source_only_profile_capture');
  assert.equal(report.profile_revision,PROFILE_REVISION);assert.equal(report.candidate,'not_implemented');
  assert.equal(report.comparison,'not_run');assert.equal(report.conformance,'not_claimed');assert.equal(report.failure,undefined);
  assert.equal(Object.keys(report.captures).length,report.operations.length+1,'Initial frame plus all operation captures');
  assert(report.environment&&typeof report.environment==='object','Actual independent runtime environment');
  assert.match(report.environment.browser||'',/^\d+\.\d+\.\d+\.\d+$/);assert.match(report.environment.node||'',/^v\d+\.\d+\.\d+$/);
  assert.equal(report.environment.playwright,'1.56.1');assert.equal(report.environment.platform,'linux');assert.equal(report.environment.arch,'x64');
  assert.deepEqual(report.environment.graphics_requested,GRAPHICS_ARGS);
  assert(report.graphics_actual&&typeof report.graphics_actual==='object','Actual browser graphics observation required');
  const gpu=report.graphics_actual.gpu,renderer=gpu?.auxAttributes?.glRenderer||gpu?.devices?.map(device=>device.deviceString).join(' ');
  assert.match(renderer||'',/swiftshader/i,'Actual measured Chromium software renderer');
  assert.equal(report.graphics_evidence?.file,`anchor-${runtime}-graphics.json`);hash(report.graphics_evidence.sha256,'Retained actual graphics observation');
  assert.deepEqual(report.errors,[]);assert(report.console.every(entry=>entry.type!=='error'));
  assert.deepEqual(report.profile,{widths:[750,480],height:600,dpr:1});assert.deepEqual(report.source_constraints,SOURCE_CONSTRAINTS);
  assert.equal(report.transport?.canvas_tab_index,-1,'Canvas is not a DOM tab stop');
  assert.deepEqual(report.source,assertProvenance(report.build,report.catalog));
  assert.deepEqual(report.provenance_negative_controls,provenanceNegativeControls(report.build,report.catalog));
  for(const key of ['build_evidence','catalog_evidence']){assert.equal(report[key].file,`anchor-${runtime}-${key==='build_evidence'?'build-manifest':'catalog'}.json`);hash(report[key].sha256,key);}
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
        assert.equal(url.search,'?example=anchor','Actual current example document route');
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

export function assertRetainedSupport(entry,bytes,build,wasm) {
  assert(bytes instanceof Uint8Array,'Actual retained support bytes');assert.equal(entry.bytes,bytes.length);
  assert.equal(sha256(bytes),entry.sha256,'Unchanged source/manifest/lock/font bytes');
  assert.equal(entry.sha256,build.rust.files[entry.path.slice(5)]);
  if(entry.path.endsWith('.rs')) {
    assert.equal(entry.sha256,ANCHOR.sourceSha256);
    assert.equal(createHash('sha1').update(Buffer.from(`blob ${bytes.length}\0`)).update(bytes).digest('hex'),ANCHOR.sourceBlob);
  }
  if(entry.path.endsWith('.ttf'))assert(wasm.includes(bytes),'Actual served Rust WASM embeds each complete pinned font');
}

export async function strictLocalReader(directory) {
  const root=await realpath(resolve(directory));
  return async(file,digest,max=64*1024*1024)=>{
    assertUploadSafeFilename(file);
    assert(file===basename(file)&&file!=='.'&&file!=='..'&&!file.includes('\\'),'Direct local evidence filename');
    const path=await realpath(join(root,file));assert(path.startsWith(root+sep));assert.equal(path,join(root,file),'Independent regular evidence, not symlink aliases');const info=await stat(path);
    assert(info.isFile()&&info.nlink===1&&info.size>0&&info.size<=max,'Bounded nonempty independently retained file');const bytes=await readFile(path);assert.equal(sha256(bytes),digest,`${file}: raw bytes hash`);return bytes;
  };
}
export async function loadEvidence(directory,report) {
  const local=await strictLocalReader(directory);
  const manifestBytes=await local(report.build_evidence.file,report.build_evidence.sha256),catalogBytes=await local(report.catalog_evidence.file,report.catalog_evidence.sha256);
  assert.deepEqual(JSON.parse(manifestBytes),report.build);assert.deepEqual(JSON.parse(catalogBytes),report.catalog);
  const decoder=await local(`anchor-${report.runtime}-png-decoder.py`,report.decoder.sha256);
  assert.equal(sha256(decoder),sha256(await readFile(new URL('../scripts/decode_anchor_png.py',import.meta.url))));
  const inputBytes=await local(report.input_evidence.file,report.input_evidence.sha256);
  validateInputEvidence(report,JSON.parse(inputBytes));
  const graphicsBytes=await local(report.graphics_evidence.file,report.graphics_evidence.sha256);
  assert.deepEqual(JSON.parse(graphicsBytes),report.graphics_actual,'Report cannot substitute the measured graphics observation');
  assert.deepEqual(report.suite_inputs.map(entry=>entry.path),SUITE_INPUTS,'Exact current suite inputs required');
  const suiteInputs={};for(const entry of report.suite_inputs) {
    suiteInputs[entry.path]=await local(entry.file,entry.sha256);assert.equal(entry.bytes,suiteInputs[entry.path].length);
    assert.deepEqual(suiteInputs[entry.path],await readFile(new URL('../../'+entry.path,import.meta.url)),'Retained source must match actual current clean checkout');
  }
  const assets={},responses={};for(const entry of report.runtime_responses) {
    const bytes=await local(entry.file,entry.sha256);assert.equal(entry.bytes,bytes.length,'Original response byte count');responses[entry.response_id]=bytes;assets[entry.path]=bytes;
  }
  assertExecutedBytes(report,{assets,responses});
  for(const [path,bytes] of Object.entries(assets)) {
    const html=Object.values(HTML_ENTRYPOINTS).find(value=>value.path===path);
    const current=html?.source||(path==='rust/host.mjs'?'web/rust/host.mjs':path==='load-timing.mjs'?'web/load-timing.mjs':
      Object.hasOwn(report.build.moonbit_host_files_sha256,path)?'web/moonbit/site/'+path.slice('moonbit/'.length):null);
    if(current)assert.deepEqual(bytes,await readFile(new URL('../../'+current,import.meta.url)),'Served HTML/host/renderer must match the actual current checkout');
  }
  const support={},support_negative_controls=[];
  const expectedSupport=['rust/unchanged-source/anchor.rs','rust/packaging-Cargo.toml','rust/Cargo.lock',...Object.values(report.build.rust.embedded_fonts).map(font=>'rust/'+font.file)];
  assert.deepEqual(report.support_files.map(entry=>entry.path).sort(),expectedSupport.sort());
  for(const entry of report.support_files) {
    assert.equal(entry.file,evidenceFilename(report.runtime,'input',entry.path));
    support[entry.path]=await local(entry.file,entry.sha256);
    const wasm=assets['rust/anchor_bg.wasm'];assertRetainedSupport(entry,support[entry.path],report.build,wasm);
    const corrupted=Buffer.from(support[entry.path]);corrupted[0]^=1;
    assert.throws(()=>assertRetainedSupport(entry,corrupted,report.build,wasm));
    support_negative_controls.push({name:'corrupted_'+entry.path.replaceAll('/','_'),rejected:true,kind:'corrupted_evidence_sensitivity_not_executed_mutant'});
  }
  const images={},stableImages={},used=new Set();
  for(const [name,capture] of Object.entries(report.captures)) {
    assert(capture.stable&&capture.file!==capture.stability_file);assert(capture.attempts.length>=2);
    assert.equal(capture.attempts.at(-1).file,capture.file);assert.equal(capture.attempts.at(-2).file,capture.stability_file);
    for(let index=0;index<capture.attempts.length;index++) {
      const attempt=capture.attempts[index];assert.equal(attempt.file,`anchor-${report.runtime}-${name}-sample-${index+1}-dpr1.png`);
      assert(!used.has(attempt.file));used.add(attempt.file);const bytes=await local(attempt.file,attempt.png_sha256,8*1024*1024);assert.equal(bytes.length,attempt.bytes,'Complete original PNG byte count');const image=decodePng(bytes);
      assert.equal(sha256(image.data),attempt.rgba_sha256);assert.equal(attempt.width,VIEWPORT_SEQUENCE.find(state=>state.name===name).width);assert.equal(attempt.height,600);assert.equal(image.width,attempt.width);assert.equal(image.height,attempt.height);
      if(attempt.file===capture.file)images[name]=image;if(attempt.file===capture.stability_file)stableImages[name]=image;
    }
    assert.equal(sha256(images[name].data),capture.rgba_sha256);assert.equal(sha256(stableImages[name].data),capture.stability_rgba_sha256);
    assert.equal(sha256(images[name].data),sha256(stableImages[name].data),'Two original independently decoded stable samples');
    await local(capture.file,capture.png_sha256);await local(capture.stability_file,capture.stability_png_sha256);
  }
  return {manifestBytes,catalogBytes,inputBytes,graphicsBytes,suiteInputs,assets,responses,support,support_negative_controls,images,stableImages};
}
export function verifyBehavior(report,retained) {
  validateReport(report,'rust');
  const paint=validateProfile(retained.images),delivery=validateOperations(report,retained.images);
  assert.deepEqual(validateProfile(retained.stableImages),paint,'Both independently requested original image sets');
  assertCaptureDigests(report,retained);
  return {status:'rust_source_profile_verified',runtime:'rust',candidate:'not_implemented',comparison:'not_run',conformance:'not_claimed',
    source:report.source,paint,delivery,
    negative_controls:[...profileNegativeControls(retained.images,report),...evidenceNegativeControls(report,retained),...(retained.support_negative_controls||[])],
    unverified:UNVERIFIED};
}
