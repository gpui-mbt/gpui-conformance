// Independent reread: hashes, decoded original PNGs and raw observations only.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {resolve,join,sep} from 'node:path';
import {sha256,decode,validateProfile,validateManifest,samples,validatePinnedSources} from './gradient-diagnostic-contract.mjs';
import {classifyBackend} from './gradient-backend-observer.mjs';
const root=resolve(process.argv[2]||'_build/gradient-diagnostic-evidence');
const report={status:'failed',kind:'synthetic_rust_gpu_diagnostic_verification',conformance:'not_claimed',equal_stop_expected_rule:'not_inferred',tolerance:'none'};
async function retained(record){assert(record&&/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(record.file));const p=resolve(root,record.file);assert(p.startsWith(root+sep));const bytes=await readFile(p);assert.equal(sha256(bytes),record.sha256);if(record.bytes!==undefined)assert.equal(bytes.length,record.bytes);return bytes;}
try {
 const result=JSON.parse(await readFile(join(root,'gradient-diagnostic-result.json')));
 assert.equal(result.status,'captured_raw_observations');assert.equal(result.original_example,false);assert.equal(result.conformance,'not_claimed');assert.deepEqual(result.errors,[]);
 const manifest=JSON.parse(await retained(result.manifest));validateManifest(manifest);
 const assets=new Map();for(const input of result.inputs){const bytes=await retained(input);if(input.suite_path){assert.equal(sha256(bytes),sha256(await readFile(new URL('../../'+input.suite_path,import.meta.url))),'Current review/capture source');}if(input.path){assert.equal(sha256(bytes),manifest.files[input.path]);assert(!assets.has(input.path));assets.set(input.path,bytes);}}
 assert.deepEqual([...assets.keys()].sort(),Object.keys(manifest.files).sort());
 validatePinnedSources(assets);
 const profile=validateProfile(JSON.parse(assets.get('profile.json')));
 assert.equal(manifest.packaging.diagnostic_source_sha256,sha256(assets.get('main.rs')));
 assert.equal(manifest.packaging.manifest_sha256,sha256(assets.get('packaging-Cargo.toml')));
 const local=await readFile(new URL('../gradient-diagnostic/main.rs',import.meta.url));assert.equal(sha256(local),sha256(assets.get('main.rs')),'Current reviewed diagnostic source');
 assert.equal(sha256(await readFile(new URL('../gradient-diagnostic/profile.json',import.meta.url))),sha256(assets.get('profile.json')));
 const actual=new Map();const responseOrdinals=new Set();const origin=new URL(result.url).origin;
 const template=await readFile(new URL('./fixtures/drag-drop-wasm-thread-0cf96c7-worker.js.txt',import.meta.url));
 assert.equal(sha256(template),'43f6beda7493508d3d8b6760d680195b08cc756db89e8aba6bbd5e1ce6da2ca4');
 assert(assets.get('gradient_diagnostic_bg.wasm').includes(template),'Compiled actual WASM worker template');
 for(const response of result.responses){assert(!responseOrdinals.has(response.ordinal));responseOrdinals.add(response.ordinal);const bytes=await retained(response),url=new URL(response.url);assert.equal(url.origin,origin);assert.equal(response.status,200);
  if(url.protocol==='blob:') {assert.equal(response.type,'script');assert.equal(bytes.toString(),template.toString().replace('WASM_BINDGEN_SHIM_URL',origin+'/gradient_diagnostic.js'));}
  else {assert.equal(url.protocol,'http:');const path=url.pathname==='/'?'index.html':decodeURIComponent(url.pathname.slice(1));assert(assets.has(path),'Unexpected runtime response '+path);assert.equal(sha256(bytes),manifest.files[path]);actual.set(path,bytes);}
 }
 for(const name of ['index.html','host.mjs','gradient_diagnostic.js','gradient_diagnostic_bg.wasm'])assert(actual.has(name),'Missing actual executed response '+name);
 assert.deepEqual(result.canvas,[{width:1000,height:900,bounds:{x:0,y:0,width:1000,height:900}}]);
 assert.equal(result.stable.length,2);assert.notEqual(...result.stable);const frames=[];
 for(const screenshot of result.screenshots){const bytes=await retained(screenshot),rgba=decode(bytes);assert.equal(sha256(rgba),screenshot.rgba_sha256);if(result.stable.includes(screenshot.file))frames.push(rgba);}
 assert.equal(frames.length,2);assert(frames[0].equals(frames[1]));assert(frames[1].equals(await retained(result.raw_rgba)));
 assert.deepEqual(samples(frames[1],profile),result.samples);
 assert.deepEqual(classifyBackend(result.backend),result.backend);
 report.backend=result.backend;report.backend_qualified=['webgpu_visible_canvas_configured','webgl_visible_canvas_context_returned'].includes(result.backend.observed);report.format_observed=result.backend.formats.length===1;report.semantic_conformance_verified=false;report.samples=result.samples;report.status='verified_raw_observations';
 report.qualifications=['PNG/RGBA captures cannot identify shader-internal NaN/Inf; exact equal-stop output bytes are backend-qualified observations only.','Missing backend or format remains unknown; no WebGPU, Metal or cross-backend parity inferred.','No expected color rule, tolerance fit, candidate comparison or conformance pass.'];
 // Negative controls prove byte corruption is rejected by the same digest primitive.
 const mutated=Buffer.from(frames[1]);mutated[0]^=1;assert.notEqual(sha256(mutated),result.raw_rgba.sha256);report.negative_controls={one_byte_rgba_mutation_rejected:true};
 console.log('Verified raw synthetic Rust GPU observations; no expected-color or parity claim.');
}catch(error){report.failure=String(error.stack);process.exitCode=1;}
finally{await writeFile(join(root,'gradient-diagnostic-verification.json'),JSON.stringify(report,null,2)+'\n');}
