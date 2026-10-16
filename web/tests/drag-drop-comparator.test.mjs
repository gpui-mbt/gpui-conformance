import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {DRAG_DROP,ENGINE,EMBEDDED_FONTS,COLORS,sha256,decodePng,assertProvenance,
  provenanceNegativeControls,assertCurrentBuild,discoverGeometry,assertPaint,assertPreview,
  makeProfile,validateProfile,validateOperations,profileNegativeControls} from './drag-drop-comparator.mjs';

// Independently authored synthetic rejection fixtures. They are not observed
// Rust screenshots, a candidate renderer, or runtime conformance evidence.
const WHITE=[255,255,255,255],BLACK=[0,0,0,255];
const geometry={sources:[{x:192,y:166,width:128,height:128},{x:336,y:166,width:128,height:128},{x:480,y:166,width:128,height:128}],target:{x:144,y:354,width:512,height:128}};
function rect(image,r,color) {
  for(let y=r.y;y<r.y+r.height;y++)for(let x=r.x;x<r.x+r.width;x++)image.data.set(color,4*(y*800+x));
}
function ring(image,r,color,width) {
  for(const edge of [{...r,height:width},{...r,y:r.y+r.height-width,height:width},{...r,width},{...r,x:r.x+r.width-width,width}])rect(image,edge,color);
}
function fixture(state) {
  const image={width:800,height:600,data:new Uint8Array(800*600*4)};rect(image,{x:0,y:0,width:800,height:600},WHITE);
  for(let index=0;index<3;index++) {
    const r=geometry.sources[index],hover=state.active===null&&state.pointer.x>=r.x&&state.pointer.x<r.x+128&&state.pointer.y>=r.y&&state.pointer.y<r.y+128;
    if(hover)rect(image,r,COLORS[index].map((v,i)=>i===3?255:Math.round(v*.2+255*.8)));
    ring(image,r,COLORS[index],2);
  }
  if(state.target!==null)rect(image,geometry.target,COLORS[state.target].map((v,i)=>i===3?255:Math.round(v*.5+255*.5)));
  ring(image,geometry.target,state.target===null?BLACK:COLORS[state.target],3);
  if(state.active!==null) {
    const color=COLORS[state.active],r={x:state.pointer.x-60,y:state.pointer.y-25,width:120,height:50};
    for(let y=r.y;y<r.y+r.height;y++)for(let x=r.x;x<r.x+r.width;x++) {
      const offset=4*(y*800+x);for(let channel=0;channel<3;channel++)image.data[offset+channel]=Math.round(color[channel]*.5+image.data[offset+channel]*.5);
    }
  }
  return image;
}
function resultFixture(profile) {
  const events=[],mouse_events=[],operations=[];
  for(const operation of profile.operations) {
    const pointer=operation.expected.map(event=>({...event,trusted:true,target:'CANVAS'}));
    const mouse={...operation.mouse_expected,trusted:true,target:'CANVAS'};
    operations.push({...structuredClone(operation),input_method:'CDP.Input.dispatchMouseEvent',input_acknowledged:true,status:'delivered',post_delivery_animation_frames:2,events:pointer,mouse_events:[mouse]});
    events.push(...pointer);mouse_events.push(mouse);
  }
  return {operations,events,mouse_events,operation_start:0,mouse_operation_start:0,captures:structuredClone(profile.captures)};
}
function provenance() {
  const files=Object.fromEntries(['drag_drop.js','drag_drop_bg.wasm','host.mjs'].map(name=>[name,'1'.repeat(64)]));
  files['unchanged-source/drag_drop.rs']=DRAG_DROP.sourceSha256;files['packaging-Cargo.toml']='2'.repeat(64);
  const fonts=Object.fromEntries(Object.entries(EMBEDDED_FONTS).map(([path,sha256])=>{const file='embedded-font-inputs/'+path.split('/').at(-1);files[file]=sha256;return [path,{file,sha256}];}));
  const source={id:'drag_drop',source:DRAG_DROP.source,source_blob:DRAG_DROP.sourceBlob,source_sha256:DRAG_DROP.sourceSha256,
    upstream_revision:DRAG_DROP.revision,status:'rust_oracle_only',candidate:'not_implemented',width:800,height:600,dpr:1};
  const catalog={upstream:{repository:'zed-industries/zed',revision:DRAG_DROP.revision},moonbit:ENGINE,examples:[]};
  const build={upstream:catalog.upstream,moonbit:ENGINE,lab_tracked_dirty:false,lab_revision:'a'.repeat(40),lab_tree:'b'.repeat(40),
    rust_bundled:true,implemented:['hello_world'],rust_implemented:['drag_drop'],rust_oracle_only:[source],
    moonbit_host_files_sha256:{'load-timing.mjs':'3'.repeat(64)},rust:{source_modified:false,source_revision:DRAG_DROP.revision,source_tree:DRAG_DROP.tree,oracle_only:true,implemented_subset:null,
      build_completed_at_utc:'2026-10-16T17:00:00Z',toolchain:'rustc 1.93.0-nightly (synthetic)',bindings:'wasm-bindgen 0.2.129',
      packaging:{upstream_files_modified:false,additional_bins:[{name:'drag_drop',source:DRAG_DROP.source}],manifest_sha256:'2'.repeat(64)},
      files,embedded_fonts:fonts,command:['cargo','+nightly-2026-10-14','build','--locked','--bin','drag_drop']}};
  return {build,catalog};
}

test('historical source-only baseline retains exact pins and rejects the current matched candidate',async()=>{
  const historical=await readFile(new URL('./fixtures/drag-drop-rust-only-catalog-e278fce4.json',import.meta.url));
  assert.equal(sha256(historical),'1253dd309c2ef1b652d249929bc2d7a3878f767a05e98dc6af7797326cb19c5b');
  const catalog=JSON.parse(historical);
  const current=JSON.parse(await readFile(new URL('../examples.json',import.meta.url)));
  assert.equal(current.examples.find(entry=>entry.id==='drag_drop').moonbit,'implemented');
  assert.deepEqual(COLORS,[[0,0,255,255],[255,0,0,255],[0,128,0,255]]);
  assert.deepEqual(catalog.moonbit,ENGINE);assert(!catalog.examples.some(entry=>entry.id==='drag_drop'));
  const record=JSON.parse(await readFile(new URL('../oracles/drag_drop.json',import.meta.url)));
  assert.equal(record.source_blob,DRAG_DROP.sourceBlob);assert.equal(record.source_sha256,DRAG_DROP.sourceSha256);
  const {build,catalog:synthetic}=provenance();assertProvenance(build,synthetic);assert.throws(()=>assertProvenance(build,current));assert.equal(provenanceNegativeControls(build,synthetic).length,9);
  const candidate=structuredClone(synthetic);candidate.examples.push({id:'drag_drop',moonbit:'implemented'});assert.throws(()=>assertProvenance(build,candidate));
});
test('strict current-checkout binding rejects historical relabels, dirty files and changed catalog bytes',()=>{
  const {build,catalog}=provenance(),catalogBytes=Buffer.from(JSON.stringify(catalog)),report={build,catalog,catalog_evidence:{sha256:sha256(catalogBytes)}};
  const checkout={revision:build.lab_revision,tree:build.lab_tree,trackedDirty:false,catalogBytes};assertCurrentBuild(report,checkout);
  for(const change of [{revision:'c'.repeat(40)},{tree:'c'.repeat(40)},{trackedDirty:true},{catalogBytes:Buffer.from('{}')}])assert.throws(()=>assertCurrentBuild(report,{...checkout,...change}));
});
test('synthetic full profile tests threshold, preview, all colors, excluded target edge and exact trusted transport',()=>{
  const profile=makeProfile(geometry),images=Object.fromEntries(Object.entries(profile.captures).map(([name,state])=>[name,fixture(state)])),result=resultFixture(profile);
  assert.equal(profile.complete,true);assert.deepEqual(discoverGeometry(images.initial),geometry);
  assert.equal(profile.captures.exact_two.active,null);assert.equal(profile.captures.over_two.active,0);assert.equal(profile.captures.return_toward_origin.active,0);
  assert.equal(profile.captures.far_release_only.active,null);assert.equal(profile.captures.far_release_only.target,null);
  assert.equal(profile.captures.outside_target_rejected.target,2);assert.equal(profile.captures.inside_target_accepted.target,1);assert.equal(profile.captures.exclusive_target_rejected.target,1);
  assert(Object.keys(validateProfile(images,geometry)).length>50);assert.equal(validateOperations(result,geometry).operations,profile.operations.length);
  assert(profileNegativeControls(images,geometry,result).every(control=>control.rejected));
  const shifted=fixture(profile.captures.threshold_stage),state=profile.captures.threshold_stage;
  assert.throws(()=>assertPreview(shifted,geometry,{...state,pointer:{x:105,y:60}},true),'Off-center activation must not create an invented visible grip shift');
  const opaque=fixture(state);rect(opaque,{x:48,y:44,width:104,height:1},COLORS[0]);assert.throws(()=>assertPreview(opaque,geometry,state,true));
  const duplicate=structuredClone(result);duplicate.operations.find(operation=>operation.duplicate).mouse_events=[];
  duplicate.mouse_events=duplicate.operations.flatMap(operation=>operation.mouse_events);validateOperations(duplicate,geometry);
});
test('PNG decoder rejects corrupt and wrongly sized original samples',()=>{
  assert.throws(()=>decodePng(Buffer.from('not png')));assert.throws(()=>decodePng(Buffer.alloc(8*1024*1024+1)));
  const png=spawnSync('python3',['-c',"from PIL import Image; import sys; Image.new('RGBA',(800,600),'white').save(sys.stdout.buffer,format='PNG')"]);
  assert.equal(png.status,0);assert.throws(()=>decodePng(Buffer.concat([png.stdout,Buffer.from('trailing')])));
  const badCrc=Buffer.from(png.stdout);badCrc[29]^=1;assert.throws(()=>decodePng(badCrc));assert.equal(decodePng(png.stdout).data.length,800*600*4);
  const small=spawnSync('python3',['-c',"from PIL import Image; import sys; Image.new('RGBA',(10,10),'white').save(sys.stdout.buffer,format='PNG')"]);
  assert.throws(()=>decodePng(small.stdout));
});

test('historical dedicated workflow remains immutable Rust-only evidence',async()=>{
  const workflow=await readFile(new URL('./fixtures/drag-drop-rust-only-workflow-e278fce4.yml',import.meta.url),'utf8');
  assert.equal(sha256(workflow),'5cc9503a50823a57dabbaa2792fc372ea7dc11d0c622db511af4981dea15ec79');
  assert.match(workflow,/--oracle-only --extra-example drag_drop/);assert.match(workflow,/timeout-minutes: 75/);
  assert.match(workflow,/Pillow==12\.0\.0/);assert.match(workflow,/playwright@1\.56\.1/);
  assert.match(workflow,/verify-drag-drop-results\.mjs/);assert.match(workflow,/if: always\(\)/);
  assert(!workflow.includes('--candidate'));assert(!workflow.includes('--implemented-example'));
  const runner=await readFile(new URL('./drag-drop-oracle-browser.mjs',import.meta.url),'utf8');
  assert.match(runner,/Input\.dispatchMouseEvent/);assert.match(runner,/original oracle evidence is never overwritten/);
  assert(!runner.includes('dispatchEvent('));assert(!runner.includes('wasmBindings.'));
});
