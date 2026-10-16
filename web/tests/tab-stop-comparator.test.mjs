import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {TAB_STOP,STOPS,ENGINE,EMBEDDED_FONTS,assertProvenance,provenanceNegativeControls,decodePng,discoverBorder,assertBorder,assertNoBorder,sourceGeometry,
  validateTraversal,validateClicks,makeProfile,validateOperations,traversalNegativeControls} from './tab-stop-comparator.mjs';

// Synthetic sensitivity fixtures only. These literal positions are neither an
// observed baseline nor program execution. No passing fixture can certify Rust.
const WHITE=[255,255,255,255],BLACK=[0,0,0,255],BLUE=[0,0,255,255];
const PHYSICAL={item0:{x:16,y:54,width:768,height:40},item1:{x:16,y:106,width:768,height:40},
  item2:{x:16,y:158,width:768,height:40},item4:{x:16,y:262,width:768,height:40},
  el1:{x:16,y:314,width:378,height:40},el2:{x:406,y:314,width:378,height:40},
  group1_child1:{x:16,y:366,width:768,height:40},group1_child2:{x:16,y:406,width:768,height:40},
  group1_child3:{x:16,y:446,width:768,height:40},group2_child1:{x:16,y:498,width:768,height:40},
  group2_child2:{x:16,y:538,width:768,height:40},group2_child3:{x:16,y:578,width:768,height:22}};
const ORDER=['item0','item1','item4','item2','el1','el2','group1_child1','group1_child2','group1_child3','group2_child1','group2_child2','group2_child3'];
function rect(image,box,color) {
  for(let y=Math.max(0,box.y);y<Math.min(600,box.y+box.height);y++)for(let x=Math.max(0,box.x);x<Math.min(800,box.x+box.width);x++)
    image.data.set(color,4*(y*800+x));
}
function ring(image,box,color,width) {
  rect(image,{...box,height:width},color);rect(image,{...box,y:box.y+box.height-width,height:width},color);
  rect(image,{...box,width},color);rect(image,{...box,x:box.x+box.width-width,width},color);
}
function fixture(focus=null,message='initial') {
  const image={width:800,height:600,data:new Uint8Array(800*600*4)};rect(image,{x:0,y:0,width:800,height:600},WHITE);
  for(const y of [54,106,158,210,262])ring(image,{x:16,y,width:768,height:40},y===210?[153,153,153,255]:BLACK,1);
  for(const name of ORDER.slice(4))rect(image,{...PHYSICAL[name],height:40},BLACK);
  // Artificial message ink is intentionally unlike real text.
  const seed={initial:1,forward:2,reverse:3,el1:4,el2:5}[message];
  for(let x=20;x<180+seed*7;x+=7)rect(image,{x,y:20+seed,width:3,height:9},BLACK);
  if(focus)ring(image,{...PHYSICAL[focus],height:40},BLUE,3);
  return image;
}
function captures() {
  const images={initial:fixture()};
  for(const name of ORDER){images['forward_'+name]=fixture(name,'forward');images['reverse_'+name]=fixture(name,'reverse');}
  images.forward_wrap=fixture('item0','forward');images.reverse_wrap=fixture('group2_child3','reverse');
  images.root_reset=fixture(null,'reverse');images.root_tab=fixture('item0','forward');
  for(let index=0;index<ORDER.length;index++) {
    const name=ORDER[index];images['click_'+name]=fixture(name,name==='el1'||name==='el2'?name:'forward');
    images['after_click_'+name]=fixture(ORDER[(index+1)%ORDER.length],'forward');
  }
  images.click_non_stop=fixture(null,'forward');images.after_non_stop=fixture('item0','forward');return images;
}
const images=captures();

test('source identity and twelve-stop hierarchy are pinned independently of fixtures',()=>{
  assert.equal(TAB_STOP.revision,'5a5fbe79917971a4d52a96b6ddb04da198a5012e');
  assert.equal(TAB_STOP.sourceBlob,'cc7c34a9979ce4027578ec2c358f503d944ee26f');
  assert.equal(TAB_STOP.sourceSha256,'be187a56c091ee0b609fa396cae4a13b49dcf98ff9e602d8caed3126de3f6a8e');
  assert.deepEqual(STOPS,ORDER);assert.deepEqual([TAB_STOP.width,TAB_STOP.height,TAB_STOP.dpr],[800,600,1]);
});
test('synthetic topology accepts repeated-index order, reverse/wrap, source-only listeners and disclosed clipping',()=>{
  const geometry=sourceGeometry(images);assert.deepEqual(geometry.stops,PHYSICAL);
  assert.deepEqual(geometry.non_stop_card,{x:16,width:768,y:210,height:40});assert.equal(geometry.message_bottom,42);
  assert.equal(validateTraversal(images,geometry).status,'source_order_and_message_relations_passed');
  assert.equal(validateClicks(images,geometry).status,'passed');
  assert.equal(discoverBorder(images.forward_group2_child3).viewport_clipped,true);
  assert.equal(traversalNegativeControls(images,geometry).length,4);
});
test('geometry is rederived and wrong initial-card location cannot self-certify a ring fixture',()=>{
  const changed={...images,initial:fixture()};rect(changed.initial,{x:16,y:106,width:768,height:40},WHITE);
  assert.throws(()=>sourceGeometry(changed),/five initial/);
  assert.throws(()=>sourceGeometry({...images,forward_item1:images.forward_item4}));
  assert.throws(()=>sourceGeometry({...images,forward_group1_child2:images.forward_group1_child3}));
});
test('three-pixel blue ring rejects missing/narrow/wide/additional borders',()=>{
  assertNoBorder(images.initial);assert.throws(()=>assertNoBorder(images.forward_item0));
  for(const width of [1,2,4]) {
    const image=fixture();ring(image,PHYSICAL.item0,BLUE,width);
    assert.throws(()=>assertBorder(image,PHYSICAL.item0));
  }
  const extra=fixture('item0','forward');rect(extra,{x:8,y:8,width:1,height:1},BLUE);
  assert.throws(()=>assertBorder(extra,PHYSICAL.item0));
});
test('flattened hierarchy differs at second Tab and cannot be blessed by regenerated metadata',()=>{
  const geometry=sourceGeometry(images);
  assert.throws(()=>validateTraversal({...images,forward_item1:images.forward_group1_child1},geometry));
  assert.throws(()=>sourceGeometry({...images,forward_item1:images.forward_group1_child1}));
  assert.throws(()=>validateTraversal({...images,reverse_item1:images.reverse_item4},geometry));
  assert.throws(()=>validateTraversal({...images,forward_wrap:images.forward_item1},geometry));
});
test('authored message relationships reject no-op Tab and invented card/group listeners',()=>{
  const geometry=sourceGeometry(images);
  assert.throws(()=>validateTraversal({...images,forward_item0:fixture('item0','initial')},geometry));
  assert.throws(()=>validateTraversal({...images,reverse_item0:fixture('item0','forward')},geometry));
  for(const name of ['item1','group1_child2'])assert.throws(()=>validateClicks({...images,['click_'+name]:fixture(name,'el1')},geometry));
  assert.throws(()=>validateClicks({...images,click_el1:fixture('el1','forward')},geometry));
});
test('complete independently delivered operation fixture validates successfully before corruption checks',()=>{
  const geometry=sourceGeometry(images),profile=makeProfile(geometry);
  assert.equal(profile.operations.length,109);assert.equal(Object.keys(profile.captures).length,55);
  const operations=profile.operations.map(operation=>({name:operation.name,expected:structuredClone(operation.expected),status:'delivered',
    events:operation.expected.map(event=>({...event,trusted:true,target:event.type.startsWith('key')?'TEXTAREA':'CANVAS',defaultPrevented:true}))}));
  const result={operations,captures:profile.captures,startup_events:[],operation_start:0,events:operations.flatMap(operation=>operation.events)};
  assert.equal(validateOperations(result,geometry).status,'passed');
  const changed=structuredClone(result);changed.operations[2].events[0].trusted=false;
  assert.throws(()=>validateOperations(changed,geometry),/Trusted/);
  const missing=structuredClone(result);missing.operations.pop();assert.throws(()=>validateOperations(missing,geometry),/Complete/);
  const relabeled=structuredClone(result);relabeled.operations[2].expected[0].key='x';assert.throws(()=>validateOperations(relabeled,geometry),/redefine/);
  const gap=structuredClone(result);gap.events.pop();assert.throws(()=>validateOperations(gap,geometry),/without gaps/);
});
function png(width=800,height=600) {
  const run=spawnSync('python3',['-c',`from PIL import Image; import sys; Image.new('RGBA',(${width},${height}),(1,2,3,255)).save(sys.stdout.buffer,format='PNG')`],{maxBuffer:1024*1024});
  assert.equal(run.status,0);return run.stdout;
}
test('pinned local Pillow decoder preserves complete RGBA and fails on invalid/truncated/wrong-size input',()=>{
  const bytes=png(),decoded=decodePng(bytes);assert.equal(decoded.data.length,1920000);
  assert.deepEqual(Array.from(decoded.data.subarray(0,4)),[1,2,3,255]);
  assert.deepEqual(Array.from(decoded.data.subarray(-4)),[1,2,3,255]);
  assert.throws(()=>decodePng(Buffer.from('invalid')));assert.throws(()=>decodePng(bytes.subarray(0,32)));
  assert.throws(()=>decodePng(png(799,600)));assert.throws(()=>decodePng(Buffer.alloc(8*1024*1024+1)));
});

test('source-pinned provenance accepts a complete synthetic build manifest before rejecting corruptions',()=>{
  const source={id:'tab_stop',source:'crates/gpui/examples/tab_stop.rs',source_blob:'cc7c34a9979ce4027578ec2c358f503d944ee26f',
    source_sha256:'be187a56c091ee0b609fa396cae4a13b49dcf98ff9e602d8caed3126de3f6a8e',
    upstream_revision:'5a5fbe79917971a4d52a96b6ddb04da198a5012e',status:'rust_oracle_only',candidate:'not_implemented',width:800,height:600,dpr:1};
  const upstream={repository:'zed-industries/zed',revision:'5a5fbe79917971a4d52a96b6ddb04da198a5012e'};
  const files=Object.fromEntries(['tab_stop.js','tab_stop_bg.wasm','host.mjs','packaging-Cargo.toml'].map(name=>[name,'a'.repeat(64)]));
  files['unchanged-source/tab_stop.rs']=source.source_sha256;
  const embedded_fonts=Object.fromEntries(Object.entries(EMBEDDED_FONTS).map(([path,sha256])=>{
    const file='embedded-font-inputs/'+path.split('/').at(-1);files[file]=sha256;return [path,{file,sha256}];}));
  const build={upstream,moonbit:ENGINE,lab_tracked_dirty:false,lab_revision:'b'.repeat(40),lab_tree:'c'.repeat(40),rust_bundled:true,
    implemented:['hello_world'],rust_implemented:['tab_stop'],rust_oracle_only:[source],moonbit_host_files_sha256:{'load-timing.mjs':'d'.repeat(64)},
    rust:{source_modified:false,oracle_only:true,build_completed_at_utc:'2026-10-16T00:00:00+00:00',
      toolchain:'rustc 1.93.0-nightly (synthetic)',bindings:'wasm-bindgen 0.2.129',
      command:['cargo','+nightly-2026-10-14','build','--locked','--bin','tab_stop'],embedded_fonts,files,
      packaging:{upstream_files_modified:false,manifest_sha256:'a'.repeat(64),additional_bins:[{name:'tab_stop',source:source.source}]}}};
  const catalog={upstream,moonbit:ENGINE,examples:[{id:'tab_stop',source:source.source,source_blob:source.source_blob,
    moonbit:'not_implemented',rust:'oracle_only',width:800,height:600}]};
  assert.equal(assertProvenance(build,catalog).id,'tab_stop');
  assert.equal(provenanceNegativeControls(build,catalog).length,7);
  const forged=structuredClone(catalog);forged.examples[0].moonbit='implemented';assert.throws(()=>assertProvenance(build,forged));
});
