import assert from 'node:assert/strict';
import {readFile,realpath,stat} from 'node:fs/promises';
import {readFileSync} from 'node:fs';
import {resolve,join,sep} from 'node:path';
import {sha256,ORACLE,SOURCES,CATALOG_BYTES,PROFILE_REVISION,VIEWPORT_SEQUENCE,GRAPHICS_ARGS,assertProvenance,assertViewport,validateOperations,decodePng,sourceStructure,buttonTarget,colorObservations} from './gradient-comparator.mjs';
import {RUST_WORKER,evidenceFilename,assertUploadSafeFilename,deriveRustWorkerBytes,assertRustWorkerSource,assertRustWorkerResponse,assertLocalRuntimeURL} from './gradient-worker-evidence.mjs';
import {classifyBackend} from './gradient-backend-observer.mjs';
export const SUITE_INPUTS=[
 'web/rust/index.html','web/gradient/host.mjs','web/rust/Cargo.lock',RUST_WORKER.template_path,
 'web/oracles/gradient.json','web/oracles/gradient-sources.json','web/tests/fixtures/gradient-rust-only-catalog.json',
 'web/scripts/build_moonbit.py','web/scripts/build_rust.py','web/scripts/prepare_gradient_site.py','web/scripts/decode_gradient_png.py','web/load-timing.mjs',
 'web/tests/gradient-worker-evidence.mjs','web/tests/gradient-backend-observer.mjs','web/tests/gradient-comparator.mjs',
 'web/tests/gradient-runtime-evidence.mjs','web/tests/gradient-oracle-browser.mjs','web/tests/verify-gradient-results.mjs','.github/workflows/gradient-oracle.yml',
];
export function runtimeResponsePath(url){const u=new URL(url);if(u.protocol==='blob:')return u.href;assertLocalRuntimeURL(url);assert(u.pathname.startsWith('/gpui-conformance/'));const p=u.pathname.slice('/gpui-conformance/'.length);return p.endsWith('/')?p+'index.html':p;}
export const requiresRuntimeRetention=(url,type)=>['document','script','font','stylesheet'].includes(type)||/\.(wasm|mjs|js|html|ttf|css)(?:\?|$)/.test(url);
export function captureBinding(report,state){return {runtime:'rust',session:report.capture_session,state:state.name,after_operation:state.after_operation,route:'/rust/?example=gradient',document_id:report.document_id,viewport:{width:state.width,height:state.height,dpr:1}};}
export function inputEvidence(r){return {capture_session:r.capture_session,document_id:r.document_id,navigation_count:r.navigation_count,operations:r.operations,events:r.events,backend:r.backend,initial_viewport:r.initial_viewport};}
export function validateReport(r) {
 assert.equal(r.status,'rust_profile_captured');assert.equal(r.runtime,'rust');assert.equal(r.candidate,'not_implemented');assert.equal(r.comparison,'not_run');assert.equal(r.conformance,'not_claimed');assert.equal(r.profile_revision,PROFILE_REVISION);assert.deepEqual(r.profile,VIEWPORT_SEQUENCE);assert.equal(r.failure,undefined);
 assert.match(r.capture_session||'',/^[0-9a-f-]{36}$/);assertProvenance(r.build,r.catalog);assert.deepEqual(r.errors,[]);assert.equal(r.environment.playwright,'1.56.1');assert.deepEqual(r.environment.graphics_requested,GRAPHICS_ARGS);
 assert.match(r.environment.browser,/^\d+\.\d+\.\d+\.\d+$/);assert.equal(r.environment.platform,'linux');assert.equal(r.environment.arch,'x64');assert(r.graphics_actual?.gpu);
 assertViewport(r.initial_viewport,VIEWPORT_SEQUENCE[0]);validateOperations(r);assert.deepEqual(r.backend,classifyBackend(r.backend));
 assert.deepEqual(Object.keys(r.captures),VIEWPORT_SEQUENCE.map(s=>s.name));
 for(const state of VIEWPORT_SEQUENCE){const c=r.captures[state.name];assertViewport(c.viewport,state);assert.deepEqual(c.binding,captureBinding(r,state));assert(c.stable&&c.attempts.length>=2);assert.equal(c.file,c.attempts.at(-1).file);assert.equal(c.stability_file,c.attempts.at(-2).file);assert.notEqual(c.file,c.stability_file);
  for(const [i,a] of c.attempts.entries()){assert.equal(a.file,`gradient-rust-${state.name}-sample-${i+1}-dpr1.png`);assert.equal(a.request_ordinal,i+1);assert.equal(a.method,'Playwright.page.screenshot');assert.deepEqual(a.binding,c.binding);}
 }
 assert.deepEqual(r.suite_inputs.map(s=>s.path),SUITE_INPUTS);
 assert.deepEqual(r.support_files.map(s=>s.path).sort(),Object.keys(r.build.rust.files).filter(p=>p.startsWith('support-source/')||p.startsWith('unchanged-source/')||p.startsWith('embedded-font-inputs/')||['Cargo.lock','packaging-Cargo.toml'].includes(p)).map(p=>'rust/'+p).sort());
 const expected={...Object.fromEntries(Object.entries(r.build.rust.files).map(([k,v])=>['rust/'+k,v])),'load-timing.mjs':r.build.moonbit_host_files_sha256['load-timing.mjs']};
 const required=['rust/index.html','rust/host.mjs','rust/gradient.js','rust/gradient_bg.wasm','load-timing.mjs'];
 const loader=r.runtime_responses.find(e=>e.path===RUST_WORKER.loader_path);assert(loader,'Actual loader response required');
 assert.equal(new URL(loader.url).search,'');
 const ids=new Set();for(const e of r.runtime_responses){assert(!ids.has(e.response_id));ids.add(e.response_id);assert.equal(e.path,runtimeResponsePath(e.url));assert.equal(e.file,evidenceFilename('rust','asset',e.url,e.response_id));assert.equal(e.status,200);
  if(e.path.startsWith('blob:'))assertRustWorkerResponse(e,loader.url);
  else{assert.equal(new URL(e.url).origin,new URL(loader.url).origin);assert.equal(e.sha256,expected[e.path],`Unexpected or wrong actual executed bytes ${e.path}`);if(e.path==='rust/index.html')assert.equal(new URL(e.url).search,'?example=gradient');else assert.equal(new URL(e.url).search,'');}
 }
 for(const path of required)assert(r.runtime_responses.some(e=>e.path===path),`Missing executed response ${path}`);
 assert(r.runtime_responses.some(e=>e.path.startsWith('blob:')),'Generated worker response required');
 for(const req of r.requests)if(requiresRuntimeRetention(req.url,req.resource_type))assert(r.runtime_responses.some(e=>e.response_id===req.response_id&&e.url===req.url&&e.status===req.status),'Every executable response retained');
}
export async function loadEvidence(directory,r) {
 const root=await realpath(directory);const used=new Set();
 async function bytes(entry,hashKey='sha256') {assertUploadSafeFilename(entry.file);const path=await realpath(join(root,entry.file));assert(path.startsWith(root+sep));assert((await stat(path)).isFile());const data=await readFile(path);assert.equal(sha256(data),entry[hashKey],`Original ${entry.file}`);return data;}
 const build=await bytes(r.build_evidence),catalog=await bytes(r.catalog_evidence);assert.deepEqual(JSON.parse(build),r.build);assert.deepEqual(catalog,CATALOG_BYTES);
 for(const e of r.suite_inputs){assert.equal(e.file,evidenceFilename('rust','suite',e.path));const b=await bytes(e);assert.deepEqual(b,readFileSync(resolve(e.path)),`Current suite source ${e.path}`);}
 for(const e of r.support_files){assert.equal(e.file,evidenceFilename('rust','input',e.path));assert.equal(e.sha256,r.build.rust.files[e.path.slice(5)]);await bytes(e);}
 const assets={},responses={};for(const e of r.runtime_responses){assert(!used.has(e.file));used.add(e.file);const b=await bytes(e);assets[e.path]=b;responses[e.response_id]=b;}
 assertRustWorkerSource(r.build,assets);const loader=r.runtime_responses.find(e=>e.path===RUST_WORKER.loader_path);
 for(const e of r.runtime_responses)if(e.path.startsWith('blob:'))assert.deepEqual(responses[e.response_id],deriveRustWorkerBytes(loader.url));
 const input=JSON.parse(await bytes(r.input_evidence));assert.deepEqual(input,inputEvidence(r));assert.deepEqual(JSON.parse(await bytes(r.graphics_evidence)),r.graphics_actual);
 const images={},stableImages={};
 for(const state of VIEWPORT_SEQUENCE){const c=r.captures[state.name];let final,stable;
  for(const a of c.attempts){const b=await bytes(a,'png_sha256');const image=decodePng(b);assert.equal(image.width,state.width);assert.equal(image.height,state.height);assert.equal(sha256(image.data),a.rgba_sha256);if(a.file===c.file)final=image;if(a.file===c.stability_file)stable=image;}
  assert(final&&stable);assert.deepEqual(final.data,stable.data,'Two actual original complete RGBA captures stabilized');assert.equal(sha256(final.data),c.rgba_sha256);images[state.name]=final;stableImages[state.name]=stable;
 }
 return {images,stableImages,assets,responses,input};
}
export function verifyBehavior(r,files) {
 const geometry={},observations={};
 for(const state of VIEWPORT_SEQUENCE){const image=files.images[state.name];const g=sourceStructure(image);geometry[state.name]=g;observations[state.name]=colorObservations(image,state.space,g);
  const polygon=g.colored.at(-1),canvasWidth=state.width-32;
  assert(Math.abs(polygon.x-.1*canvasWidth)<=1,'Source polygon X excludes canvas origin.x');
  assert(Math.abs(polygon.width-.8*canvasWidth)<=2,'Source polygon width');assert(Math.abs(polygon.height-50)<=1,'Tight source polygon height is 50, not nominal 80');
 }
 for(const op of r.operations.filter(o=>o.action==='click')){const index=VIEWPORT_SEQUENCE.findIndex(s=>s.name===op.name);assert.deepEqual(op.target,buttonTarget(files.images[VIEWPORT_SEQUENCE[index-1].name]),'Target derived from prior original PNG');}
 for(const phase of ['wide','tall']) {
  assert.deepEqual(files.images[phase+'Srgb'].data,files.images[phase+'Restored'].data,'Complete sRGB restoration');
  assert.notDeepEqual(files.images[phase+'Srgb'].data,files.images[phase+'Oklab'].data,'Actual toggle changes original render');
  for(const index of [0,1]){const box=geometry[phase+'Srgb'].colored[index];for(let y=box.y;y<box.y+box.height;y++)for(let x=box.x;x<box.x+box.width;x++){const p=(y*files.images[phase+'Srgb'].width+x)*4;assert.deepEqual(files.images[phase+'Srgb'].data.slice(p,p+4),files.images[phase+'Oklab'].data.slice(p,p+4),'Source solid does not change with color-space toggle');}}
  // Exclude label-only changes: at least one original interior gradient pixel changes.
  let changed=false;for(const box of geometry[phase+'Srgb'].colored.slice(2,-1)){for(let y=box.y+4;y<box.y+box.height-4;y++)for(let x=box.x+4;x<box.x+box.width-4;x++){const p=(y*files.images[phase+'Srgb'].width+x)*4;if(!Buffer.from(files.images[phase+'Srgb'].data.slice(p,p+4)).equals(Buffer.from(files.images[phase+'Oklab'].data.slice(p,p+4))))changed=true;}}
  assert(changed,'Gradient interior changed after real click');
 }
 assert.deepEqual(files.images.wideSrgb.data,files.images.wideAgain.data,'Real viewport round trip restores full original frame');
 return {status:'verified_bounded_structure_interaction_restoration',geometry,color_observations:observations,color_equivalence:'pending_source_and_original_artifact_review_no_tolerance_fitted',backend:r.backend.observed,unverified:ORACLE.unverified};
}
export function negativeControls(report,files) {
 const rejected=[],test=(name,run)=>{assert.throws(run,name);rejected.push({name,rejected:true,kind:'synthetic_corrupted_evidence_not_actual_engine_mutant'});};
 for(const [name,mutate] of [
  ['wrong_source',r=>{r.build.rust_oracle_only[0].source_blob='0'.repeat(40);}],['wrong_runtime',r=>{r.runtime='moonbit';}],
  ['wrong_profile',r=>{r.profile[0].width++;}],['untrusted_input',r=>{r.operations[0].events.forEach(e=>e.trusted=false);}],
  ['wrong_capture_binding',r=>{r.captures.wideSrgb.binding.state='wideOklab';}],['missing_wasm',r=>{r.runtime_responses=r.runtime_responses.filter(e=>!e.path.endsWith('.wasm'));}],
  ['wrong_source_support',r=>{r.build.rust.files['support-source/crates/gpui/src/color.rs']='0'.repeat(64);}],
 ]){const r=structuredClone(report);mutate(r);test(name,()=>validateReport(r));}
 const changed=structuredClone(files);changed.images.wideRestored.data[0]^=1;test('changed_original_restoration_RGBA',()=>verifyBehavior(report,changed));
 return rejected;
}
