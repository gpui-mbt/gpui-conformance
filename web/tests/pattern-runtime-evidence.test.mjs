import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {PATTERN_WORKER,sha256,derivePatternWorkerBytes,assertPatternWorkerInputs,assertPatternWorkerResponse} from './pattern-runtime-evidence.mjs';
const loader='http://127.0.0.1:40489/gpui-conformance/rust/pattern.js';
const url='blob:http://127.0.0.1:40489/336231f0-247d-491a-9abe-de677c45d357';
const bytes=derivePatternWorkerBytes(loader),response={url,type:'script',status:200,sha256:sha256(bytes)};
const template=readFileSync(new URL('./fixtures/drag-drop-wasm-thread-0cf96c7-worker.js.txt',import.meta.url)),lock=readFileSync(new URL('../rust/Cargo.lock',import.meta.url));
function fixtures(){
 // Mock byte containers exercise identity validation, not browser/WASM execution.
 const assets={'rust/pattern.js':Buffer.from('mock compiled loader'),'rust/pattern_bg.wasm':Buffer.concat([Buffer.from('mock wasm bytes'),template])};
 const build={rust:{files:{'Cargo.lock':PATTERN_WORKER.lock_sha256,'pattern.js':sha256(assets['rust/pattern.js']),'pattern_bg.wasm':sha256(assets['rust/pattern_bg.wasm'])}}};
 return {assets,build};
}
test('single pinned-template substitution matches the observed V3 worker identity',()=>{
 assert.equal(bytes.length,998);assert.equal(sha256(bytes),'7bb2ecebea43e54fc43ee34a7579972275b23de0dbc8b3a0f93858829d53f810');
 assert.doesNotThrow(()=>assertPatternWorkerResponse(response,loader,bytes));
});
test('worker mutation and false declared hash are rejected',()=>{
 const changed=Buffer.from(bytes);changed[20]^=1;
 assert.throws(()=>assertPatternWorkerResponse(response,loader,changed));
 assert.throws(()=>assertPatternWorkerResponse({...response,sha256:sha256(changed)},loader,changed));
});
test('worker origin, canonical UUID, response type and status fail closed',()=>{
 for(const patch of [{url:url.replace('40489','40490')},{url:url+'?query=1'},{url:'data:text/javascript,hello'},{url:url.replace('336231f0','not-a-uuid')},{type:'fetch'},{status:404}])assert.throws(()=>assertPatternWorkerResponse({...response,...patch},loader,bytes));
});
test('loader is exactly pattern runtime on canonical ephemeral loopback',()=>{
 for(const wrong of [loader.replace('/pattern.js','/drag_drop.js'),loader+'?x=1',loader.replace('127.0.0.1','example.com'),loader.replace('http:','https:')])assert.throws(()=>derivePatternWorkerBytes(wrong));
});
test('served loader, WASM and retained lock hashes must match',()=>{
 const {assets,build}=fixtures();assert.doesNotThrow(()=>assertPatternWorkerInputs(build,assets,lock));
 for(const path of Object.keys(assets)){assert.throws(()=>assertPatternWorkerInputs(build,{...assets,[path]:Buffer.from('changed')},lock));const missing={...assets};delete missing[path];assert.throws(()=>assertPatternWorkerInputs(build,missing,lock));}
 assert.throws(()=>assertPatternWorkerInputs(build,assets,Buffer.from('changed lock')));
 assert.throws(()=>assertPatternWorkerInputs({rust:{files:{...build.rust.files,'Cargo.lock':'0'.repeat(64)}}},assets,lock));
});
test('matching WASM manifest hash cannot substitute for full embedded worker template',()=>{
 const {assets,build}=fixtures();assets['rust/pattern_bg.wasm']=Buffer.from('no worker template');build.rust.files['pattern_bg.wasm']=sha256(assets['rust/pattern_bg.wasm']);
 assert.throws(()=>assertPatternWorkerInputs(build,assets,lock),/embed the exact/);
});
test('retained actual V3 compiled inputs and worker bytes validate', {skip:!process.env.PATTERN_WORKER_ACTUAL},()=>{
 const dir=process.env.PATTERN_WORKER_ACTUAL,records=JSON.parse(readFileSync(join(dir,'responses.json'))),assets={};
 const build=JSON.parse(readFileSync(process.env.PATTERN_RUST_MANIFEST));
 for(const record of records){const actual=readFileSync(join(dir,record.file));assert.equal(sha256(actual),record.sha256);if(record.url.startsWith('blob:'))assertPatternWorkerResponse(record,loader,actual);else assets[new URL(record.url).pathname.replace('/gpui-conformance/','')]=actual;}
 assertPatternWorkerInputs(build,assets,lock);
});
