// Source-derived wasm_thread worker identity, scoped only to pattern's loader.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
export const sha256=bytes=>createHash('sha256').update(bytes).digest('hex');
export const PATTERN_WORKER=Object.freeze({
 dependency:'wasm_thread',version:'0.3.3',revision:'0cf96c7708dfb97ccf3da50347e25edcf75d6937',
 template_path:'web/tests/fixtures/drag-drop-wasm-thread-0cf96c7-worker.js.txt',
 template_sha256:'43f6beda7493508d3d8b6760d680195b08cc756db89e8aba6bbd5e1ce6da2ca4',
 lock_sha256:'d60bd2d8e87639d33f67b740796a06078c2c2e3df9593dcbd699c4abc37919da',
 loader_path:'rust/pattern.js',wasm_path:'rust/pattern_bg.wasm',marker:'WASM_BINDGEN_SHIM_URL',
});
const template=readFileSync(new URL('./fixtures/drag-drop-wasm-thread-0cf96c7-worker.js.txt',import.meta.url));
assert.equal(sha256(template),PATTERN_WORKER.template_sha256);assert.equal(template.length,964);
assert.equal(template.toString().split(PATTERN_WORKER.marker).length,2);
function loaderURL(value){
 const url=new URL(value);assert.equal(url.href,value);assert.equal(url.protocol,'http:');assert.equal(url.hostname,'127.0.0.1');
 assert(Number(url.port)>0&&Number(url.port)<=65535);assert.equal(url.username,'');assert.equal(url.password,'');assert.equal(url.hash,'');assert.equal(url.search,'');
 assert.equal(url.pathname,'/gpui-conformance/'+PATTERN_WORKER.loader_path);return url;
}
export function derivePatternWorkerBytes(loader){return Buffer.from(template.toString().replace(PATTERN_WORKER.marker,loaderURL(loader).href));}
export function assertPatternWorkerInputs(build,assets,lockBytes){
 assert.equal(build.rust.files['Cargo.lock'],PATTERN_WORKER.lock_sha256);assert.equal(sha256(lockBytes),PATTERN_WORKER.lock_sha256,'Actual retained Cargo.lock bytes');
 for(const path of [PATTERN_WORKER.loader_path,PATTERN_WORKER.wasm_path]){
  assert(assets[path] instanceof Uint8Array,`Missing actual served worker input ${path}`);
  assert.equal(sha256(assets[path]),build.rust.files[path.slice(5)],'Served worker input differs from compiled manifest');
 }
 assert(Buffer.from(assets[PATTERN_WORKER.wasm_path]).includes(template),'Served pattern WASM must embed the exact pinned dependency worker template');
}
export function assertPatternWorkerResponse(response,loader,bytes){
 const expectedLoader=loaderURL(loader),url=new URL(response.url);
 assert.equal(response.type,'script');assert.equal(response.status,200);assert.equal(url.protocol,'blob:');assert.equal(response.url,url.href);
 assert.equal(url.origin,expectedLoader.origin,'Worker must belong to this actual runtime origin');
 const prefix='blob:'+expectedLoader.origin+'/';assert(response.url.startsWith(prefix));assert.match(response.url.slice(prefix.length),/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/);
 assert.equal(sha256(bytes),response.sha256,'Retained worker bytes differ from response');
 assert.equal(response.sha256,sha256(derivePatternWorkerBytes(loader)),'Worker differs from source-derived pinned wasm_thread template');
}
