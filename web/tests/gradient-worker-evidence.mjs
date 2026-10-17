// Bounded provenance for wasm_thread's source-generated worker, never a blob allowlist.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {sha256} from './gradient-comparator.mjs';
export const RUST_WORKER=Object.freeze({
  dependency:'wasm_thread',version:'0.3.3',revision:'0cf96c7708dfb97ccf3da50347e25edcf75d6937',
  template_path:'web/tests/fixtures/drag-drop-wasm-thread-0cf96c7-worker.js.txt',
  template_sha256:'43f6beda7493508d3d8b6760d680195b08cc756db89e8aba6bbd5e1ce6da2ca4',
  lock_path:'web/rust/Cargo.lock',lock_sha256:'d60bd2d8e87639d33f67b740796a06078c2c2e3df9593dcbd699c4abc37919da',
  loader_path:'rust/gradient.js',wasm_path:'rust/gradient_bg.wasm',marker:'WASM_BINDGEN_SHIM_URL',
});
const template=readFileSync(new URL('./fixtures/drag-drop-wasm-thread-0cf96c7-worker.js.txt',import.meta.url));
assert.equal(sha256(template),RUST_WORKER.template_sha256,'Exact pinned wasm_thread source template');
assert.equal(template.length,964);assert.equal(template.toString().split(RUST_WORKER.marker).length,2);
export function assertUploadSafeFilename(file) {
  assert(typeof file==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,199}$/.test(file),'Portable ASCII evidence filename');
  assert(!/[. ]$/.test(file)&&!/^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)/i.test(file),'No platform-reserved evidence filename');
  return file;
}
export function evidenceFilename(runtime,kind,identity,ordinal=0) {
  assert(['rust','moonbit'].includes(runtime));assert(['asset','suite','input'].includes(kind));
  assert(typeof identity==='string'&&identity.length>0);assert(Number.isSafeInteger(ordinal)&&ordinal>=0);
  assert(kind==='asset'?ordinal>0:ordinal===0);
  // The response ordinal is injective within the runtime/session; the full raw
  // URL digest binds identity without unsafe characters, lossy sanitization or truncation.
  return assertUploadSafeFilename(`gradient-${runtime}-${kind}-${ordinal}-${sha256(Buffer.from(JSON.stringify(identity)))}.bin`);
}
export function assertLocalRuntimeURL(value) {
  const url=new URL(value);assert.equal(value,url.href,'Canonical actual runtime URL');
  assert.equal(url.protocol,'http:');assert.equal(url.hostname,'127.0.0.1');
  assert(Number(url.port)>0&&Number(url.port)<=65535,'Actual ephemeral loopback server port');
  assert.equal(url.username,'');assert.equal(url.password,'');assert.equal(url.hash,'');return url;
}
export function deriveRustWorkerBytes(loaderURL) {
  const loader=assertLocalRuntimeURL(loaderURL);
  assert.equal(loader.pathname,'/gpui-conformance/'+RUST_WORKER.loader_path);assert.equal(loader.search,'');
  // This is exactly get_worker_script's single template.replace operation at
  // the Cargo.lock-pinned wasm_thread revision, with no JS evaluation.
  return Buffer.from(template.toString().replace(RUST_WORKER.marker,loader.href));
}
export function assertRustWorkerSource(build,assets) {
  assert.equal(build.rust.files['Cargo.lock'],RUST_WORKER.lock_sha256,'Exact built worker dependency lock');
  for(const path of [RUST_WORKER.loader_path,RUST_WORKER.wasm_path]) {
    assert(assets[path] instanceof Uint8Array,`Actual retained generated-worker input ${path}`);
    assert.equal(sha256(assets[path]),build.rust.files[path.slice(5)],'Generated worker inputs must match current compiled build');
  }
  assert(Buffer.from(assets[RUST_WORKER.wasm_path]).includes(template),'Actual served Rust WASM embeds the complete exact pinned worker template');
}
export function assertRustWorkerResponse(response,loaderURL) {
  const loader=assertLocalRuntimeURL(loaderURL),url=new URL(response.url);
  assert.equal(response.resource_type,'script');assert.equal(url.protocol,'blob:');assert.equal(url.origin,loader.origin,'Same-runtime generated worker origin');
  assert.equal(response.url,url.href);
  assert(response.url.startsWith('blob:'+loader.origin+'/'),'Exact local object URL prefix');
  assert.match(response.url.slice(('blob:'+loader.origin+'/').length),/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/,'Actual generated object URL');
  assert.equal(response.sha256,sha256(deriveRustWorkerBytes(loaderURL)),'Exact source-derived wasm_thread worker response');
}
