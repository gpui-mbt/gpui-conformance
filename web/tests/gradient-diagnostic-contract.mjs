import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
export const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
export const REVISION='5a5fbe79917971a4d52a96b6ddb04da198a5012e';
export const SOURCE_REGISTRY_SHA256='95d6e03ef3ba1be0fa56ce91516073a2954a30d70a83974f58e62f158dbf8a99';
export const TREE='990fb995914d51a546b20e5cf0382dafc105c299';
export function decode(bytes) {
 const p=spawnSync('python3',[fileURLToPath(new URL('../scripts/decode_gradient_diagnostic_png.py',import.meta.url))],{input:bytes,maxBuffer:8*1024*1024});
 assert.equal(p.status,0,p.stderr?.toString());assert.equal(p.stdout.readUInt32BE(0),1000);assert.equal(p.stdout.readUInt32BE(4),900);
 const data=p.stdout.subarray(8);assert.equal(data.length,1000*900*4);return data;
}
export function validateProfile(p) {
 assert.equal(p.kind,'synthetic_rust_gpu_diagnostic_only');assert.equal(p.original_example,false);
 assert.deepEqual(p.viewport,{width:1000,height:900,dpr:1});assert.equal(p.cases.length,36);
 assert.equal(p.equal_stop_rule,'unresolved_until_actual_backend_observation');
 assert.equal(new Set(p.cases.map(c=>c.id)).size,36);
 for(const c of p.cases) {
  assert(['Srgb','Oklab'].includes(c.color_space));
  const [x,y,w,h]=c.bounds;assert([x,y,w,h].every(Number.isInteger));assert(x>=0&&y>=0&&x+w<=1000&&y+h<=900);
  if(c.id.endsWith('equal-stops')){assert.equal(w,161);assert.equal(c.angle,90);assert.deepEqual(c.stops,[.5,.5]);}
 }
 return p;
}
export function samples(rgba,profile) {
 assert.equal(rgba.length,1000*900*4);
 const pixel=(x,y)=>Array.from(rgba.subarray((y*1000+x)*4,(y*1000+x)*4+4));
 return profile.cases.map(c=>{
  const [x,y,w,h]=c.bounds,cx=x+Math.floor(w/2),cy=y+Math.floor(h/2);
  const points=c.kind==='path'||c.kind==='clip'?[31,44,45,46,55,65,78].map(d=>[cx,y+d]):[-1,0,1].map(d=>[cx+d,cy]);
  return {id:c.id,bounds:c.bounds,points:points.map(([x,y])=>({x,y,fragment_center:[x+.5,y+.5],rgba:pixel(x,y)})),
   horizontal_center_scanline:Array.from({length:w},(_,i)=>({x:x+i,y:cy,rgba:pixel(x+i,cy)})),
   interpretation:'raw_observation_only_no_expected_rule'};
 });
}
export function validateManifest(m) {
 assert.equal(m.kind,'synthetic_rust_gpu_diagnostic_only');assert.equal(m.original_example,false);
 assert.equal(m.candidate,'not_implemented');assert.equal(m.conformance,'not_claimed');
 assert.equal(m.upstream_revision,REVISION);assert.equal(m.upstream_tree,TREE);
 assert.equal(m.packaging.upstream_files_modified,false);assert.equal(m.packaging.original_example,false);
 for(const name of ['main.rs','profile.json','gradient_diagnostic.js','gradient_diagnostic_bg.wasm','Cargo.lock','packaging-Cargo.toml'])assert.match(m.files[name]||'',/^[a-f0-9]{64}$/);
}

export function validatePinnedSources(assets) {
 assert.equal(sha256(assets.get('upstream-sources.json')),SOURCE_REGISTRY_SHA256,'Frozen pinned source registry');
 const registry=JSON.parse(assets.get('upstream-sources.json'));
 for(const item of registry.sources)assert.equal(sha256(assets.get('upstream-source/'+item.path)),item.sha256,'Exact pinned renderer source '+item.path);
}
