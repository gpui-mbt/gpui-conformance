import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {TAB_STOP,STOPS,ENGINE,EMBEDDED_FONTS,assertProvenance,provenanceNegativeControls,assertCurrentTabStopBuild,sha256,decodePng,discoverBorder,assertBorder,assertNoBorder,frameGeometry,sourceGeometry,movingEdgePoint,
  validateTraversal,validateClicks,makeProfile,validateOperations,traversalNegativeControls} from './tab-stop-comparator.mjs';

// Synthetic sensitivity fixtures only. Layouts below are independently authored
// unit inputs, never an observed oracle or a claim that Rust/candidate executed.
const WHITE=[255,255,255,255],BLACK=[0,0,0,255],BLUE=[0,0,255,255];
const ORDER=['item0','item1','item4','item2','el1','el2','group1_child1','group1_child2','group1_child3','group2_child1','group2_child2','group2_child3'];
function rect(image,box,color) {
  for(let y=Math.max(0,box.y);y<Math.min(600,box.y+box.height);y++)for(let x=Math.max(0,box.x);x<Math.min(800,box.x+box.width);x++)
    image.data.set(color,4*(y*800+x));
}
function ring(image,box,color,width) {
  rect(image,{...box,height:width},color);rect(image,{...box,y:box.y+box.height-width,height:width},color);
  rect(image,{...box,width},color);rect(image,{...box,x:box.x+box.width-width,width},color);
}
function layout(focus,variant=0) {
  const heights=[33,33,34,33,33];
  if(focus==='item0'){heights[0]++;heights[2]--;}
  if(focus==='item1'){heights[1]++;heights[2]--;}
  if(focus==='item4'){heights[4]++;heights[2]--;}
  // An alternate synthetic header/card allocation proves production parsing has
  // no hidden table of the actual baseline's y/height values.
  heights[4]-=variant;let y=54+variant;const controls={};
  for(let index=0;index<5;index++){controls['item'+index]={x:16,y,width:768,height:heights[index]};y+=heights[index]+12;}
  const widths=focus==='el1'?[380,376]:focus==='el2'?[376,380]:[378,378];
  controls.el1={x:16,y,width:widths[0],height:40};controls.el2={x:16+widths[0]+12,y,width:widths[1],height:40};y+=52;
  for(let group=1;group<=2;group++){for(let child=1;child<=3;child++)controls[`group${group}_child${child}`]={x:16,y:y+(child-1)*40,width:768,height:40};y+=132;}
  return controls;
}
function fixture(focus=null,message='initial',variant=0) {
  const image={width:800,height:600,data:new Uint8Array(800*600*4)};rect(image,{x:0,y:0,width:800,height:600},WHITE);
  const controls=layout(focus,variant);
  for(let index=0;index<5;index++)ring(image,controls['item'+index],index===3?[153,153,153,255]:BLACK,1);
  for(const name of ORDER.slice(4))rect(image,controls[name],BLACK);
  const seed={initial:1,forward:2,reverse:3,el1:4,el2:5}[message];
  for(let x=20;x<180+seed*7;x+=7)rect(image,{x,y:20+seed,width:3,height:9},BLACK);
  if(ORDER.includes(focus))ring(image,controls[focus],BLUE,3);
  return image;
}
function captures() {
  const images={},frames={};let profile=makeProfile();
  while(true) {
    for(const [name,spec] of Object.entries(profile.captures))if(!images[name]) {
      images[name]=fixture(spec.focus,spec.message);frames[name]=frameGeometry(images[name]);
    }
    if(profile.complete)return {images,profile};profile=makeProfile(frames);
  }
}
const {images,profile}=captures();

test('source identity and twelve-stop hierarchy remain pinned independently of fixtures',()=>{
  assert.equal(TAB_STOP.revision,'5a5fbe79917971a4d52a96b6ddb04da198a5012e');
  assert.equal(TAB_STOP.sourceBlob,'cc7c34a9979ce4027578ec2c358f503d944ee26f');
  assert.equal(TAB_STOP.sourceSha256,'be187a56c091ee0b609fa396cae4a13b49dcf98ff9e602d8caed3126de3f6a8e');
  assert.deepEqual(STOPS,ORDER);assert.deepEqual([TAB_STOP.width,TAB_STOP.height,TAB_STOP.dpr],[800,600,1]);
});
test('each frame independently exposes current physical card/button geometry and exact source gaps',()=>{
  const initial=frameGeometry(images.initial),first=frameGeometry(images.forward_item0),left=frameGeometry(images.forward_el1),right=frameGeometry(images.forward_el2);
  assert.equal(initial.controls.item0.height,33);assert.equal(first.controls.item0.height,34);
  assert.equal(left.controls.el1.width,380);assert.equal(left.controls.el2.width,376);
  assert.equal(right.controls.el1.width,376);assert.equal(right.controls.el2.width,380);
  for(const frame of [initial,first,left,right])assert.equal(frame.controls.el2.x-frame.controls.el1.x-frame.controls.el1.width,12);
  const alternate=frameGeometry(fixture('item0','forward',2));assert.equal(alternate.controls.item0.y,56);
  assert.notDeepEqual(alternate.controls,first.controls,'No fixed observed-y lookup table may be the parser');
});
test('state-specific source order, same-focus reverse geometry and authored messages pass complete synthetic evidence',()=>{
  const geometry=sourceGeometry(images);
  assert.equal(validateTraversal(images,geometry).status,'source_order_and_message_relations_passed');
  assert.equal(validateClicks(images,geometry).status,'passed');assert.equal(traversalNegativeControls(images,geometry).length,5);
  assert.equal(profile.operations.length,128);assert.equal(Object.keys(profile.captures).length,72);
});
test('cross-frame assembly and stale geometry cannot manufacture a passing same-frame gap',()=>{
  const geometry=sourceGeometry(images),mixed=structuredClone(geometry);
  mixed.frames.forward_el1.controls.el2=geometry.frames.forward_el2.controls.el2;
  assert.throws(()=>validateTraversal(images,mixed),/this exact screenshot/);
  const assembled=fixture('el1','forward'),row=layout('el1').el1;
  rect(assembled,{x:396,y:row.y,width:12,height:40},WHITE);
  rect(assembled,{x:404,y:row.y,width:380,height:40},BLACK);
  assert.throws(()=>frameGeometry(assembled),/gap3/);
  const stale=structuredClone(geometry);stale.frames.forward_item0.controls=geometry.frames.initial.controls;
  assert.throws(()=>validateTraversal(images,stale),/this exact screenshot/);
  const inconsistent={...images,reverse_item0:fixture('item0','reverse',2)};
  assert.throws(()=>validateTraversal(inconsistent,sourceGeometry(inconsistent)),/same-focus physical geometry/);
});
test('initial black1px and opacity card borders plus focused blue3px reject wrong widths/colors and moved borders',()=>{
  assertNoBorder(images.initial);assert.throws(()=>assertNoBorder(images.forward_item0));
  for(const width of [1,2,4]) {const image=fixture();ring(image,layout(null).item0,BLUE,width);assert.throws(()=>frameGeometry(image));}
  const wide=fixture();ring(wide,layout(null).item1,BLACK,2);assert.throws(()=>frameGeometry(wide),/exactly 1px/);
  const gray=fixture();ring(gray,layout(null).item3,BLACK,1);assert.throws(()=>frameGeometry(gray),/source color/);
  const moved=fixture('item0','forward');rect(moved,{x:8,y:8,width:1,height:1},BLUE);assert.throws(()=>frameGeometry(moved),/physical source control/);
});
test('flattened second Tab, wrong repeated-index order, reverse/wrap and unexpected focus changes are rejected',()=>{
  const geometry=sourceGeometry(images);
  assert.throws(()=>validateTraversal({...images,forward_item1:images.forward_group1_child1},geometry));
  assert.throws(()=>validateTraversal({...images,forward_item1:images.forward_item4},sourceGeometry({...images,forward_item1:images.forward_item4})));
  assert.throws(()=>validateTraversal({...images,reverse_item1:images.reverse_item4},geometry));
  assert.throws(()=>validateTraversal({...images,forward_wrap:images.forward_item1},geometry));
  const changed={...images,edge_card_down:fixture(null,'forward')};
  assert.throws(()=>validateClicks(changed,sourceGeometry(changed)),/blue focus border/);
});
test('moving-edge points are derived from current frames and deliberately exclude frozen initial hit bounds',()=>{
  const geometry=sourceGeometry(images),initial=geometry.frames.initial;
  assert.deepEqual(movingEdgePoint(initial,geometry.frames.edge_card_focus,'item0'),{x:400,y:87});
  assert.deepEqual(movingEdgePoint(initial,geometry.frames.edge_el1_focus,'el1'),{x:395,y:300});
  assert.deepEqual(movingEdgePoint(initial,geometry.frames.edge_el1_next,'el2'),{x:404,y:300});
  for(const target of ['item0','el1','el2'])assert.throws(()=>movingEdgePoint(initial,{...initial,observed_focus:target},target),/new [12]px/);
  assert.throws(()=>movingEdgePoint(initial,geometry.frames.forward_el2,'el1'),/intended current focused/);
  const point=profile.operations.find(operation=>operation.name==='edge_el1_move');assert.equal(point.expected[0].x,395);
});
test('adaptive source plan pauses for the immediately preceding capture rather than reusing old focus geometry',()=>{
  const frames=sourceGeometry(Object.fromEntries(Object.entries(images).filter(([name])=>Object.hasOwn(makeProfile().captures,name)))).frames;
  const paused=makeProfile(frames);assert.equal(paused.blocked_on_capture,'root_tab');assert.equal(paused.operations.length,57);
  assert.equal(profile.complete,true);assert.equal(profile.captures.edge_card_down.focus,'item0');assert.equal(profile.captures.edge_el2_next.focus,'group1_child1');
});
test('authored message relations reject no-op Tab and invented card/group listeners',()=>{
  const geometry=sourceGeometry(images);
  assert.throws(()=>validateTraversal({...images,forward_item0:fixture('item0','initial')},geometry));
  for(const name of ['item1','group1_child2'])assert.throws(()=>validateClicks({...images,['click_'+name]:fixture(name,'el1')},geometry));
  assert.throws(()=>validateClicks({...images,edge_el1_click:fixture('el1','forward')},geometry));
});
test('complete trusted operation fixture passes before stale edge coordinates, missing or relabeled input are rejected',()=>{
  const geometry=sourceGeometry(images);
  const operations=profile.operations.map(operation=>({name:operation.name,expected:structuredClone(operation.expected),status:'delivered',
    events:operation.expected.map(event=>({...event,trusted:true,target:event.type.startsWith('key')?'TEXTAREA':'CANVAS',defaultPrevented:true}))}));
  const result={operations,captures:profile.captures,startup_events:[],operation_start:0,events:operations.flatMap(operation=>operation.events)};
  assert.equal(validateOperations(result,geometry).status,'passed');
  const changed=structuredClone(result);changed.operations[2].events[0].trusted=false;assert.throws(()=>validateOperations(changed,geometry),/Trusted/);
  const missing=structuredClone(result);missing.operations.pop();assert.throws(()=>validateOperations(missing,geometry),/Complete/);
  const stale=structuredClone(result),edge=stale.operations.find(operation=>operation.name==='edge_el1_move');edge.expected[0].x=393;edge.events[0].x=393;
  assert.throws(()=>validateOperations(stale,geometry),/redefine/);
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

test('current-checkout binding accepts exact clean Git HEAD and current catalog bytes',()=>{
  const revision='1234567890abcdef1234567890abcdef12345678',tree='a'.repeat(40);
  const catalogBytes=Buffer.from('{"examples":[{"id":"tab_stop","moonbit":"not_implemented"}]}\n');
  const report={build:{lab_revision:revision,lab_tree:tree},catalog:JSON.parse(catalogBytes),catalog_evidence:{sha256:sha256(catalogBytes)}};
  assert.deepEqual(assertCurrentTabStopBuild(report,{revision,tree,trackedDirty:false,catalogBytes}),{
    revision,tree,tracked_dirty:false,catalog_sha256:sha256(catalogBytes)});
});
test('current-checkout binding rejects a stale valid revision, dirty tracked state, and changed catalog bytes',()=>{
  const revision='1234567890abcdef1234567890abcdef12345678',tree='a'.repeat(40),catalogBytes=Buffer.from('{"examples":[]}\n');
  const report={build:{lab_revision:revision,lab_tree:tree},catalog:JSON.parse(catalogBytes),catalog_evidence:{sha256:sha256(catalogBytes)}};
  const checkout={revision,tree,trackedDirty:false,catalogBytes};
  assert.throws(()=>assertCurrentTabStopBuild(report,{...checkout,revision:'fedcba0987654321fedcba0987654321fedcba09'}),/cannot be relabeled/);
  assert.throws(()=>assertCurrentTabStopBuild({...report,build:{lab_revision:'0'.repeat(40)}},checkout),/cannot be relabeled/);
  assert.throws(()=>assertCurrentTabStopBuild(report,{...checkout,trackedDirty:true}),/dirty tracked/);
  assert.throws(()=>assertCurrentTabStopBuild(report,{...checkout,tree:'b'.repeat(40)}),/tree must match/);
  // Equal parsed JSON with different whitespace must still fail exact-byte binding.
  assert.throws(()=>assertCurrentTabStopBuild(report,{...checkout,catalogBytes:Buffer.from('{ "examples": [] }\n')}),/catalog bytes/);
  assert.throws(()=>assertCurrentTabStopBuild({...report,catalog:{examples:[{id:'forged'}]}},checkout),/catalog identity/);
});
test('current-checkout binding fails closed on malformed Git context and missing raw catalog bytes',()=>{
  const revision='1234567890abcdef1234567890abcdef12345678',tree='a'.repeat(40),catalogBytes=Buffer.from('{"examples":[]}\n');
  const report={build:{lab_revision:revision,lab_tree:tree},catalog:JSON.parse(catalogBytes),catalog_evidence:{sha256:sha256(catalogBytes)}};
  const checkout={revision,tree,trackedDirty:false,catalogBytes};
  for(const malformed of [null,undefined,[],{}, {...checkout,revision:''},{...checkout,revision:'a'.repeat(39)},
    {...checkout,revision:123},{...checkout,tree:undefined},{...checkout,tree:'b'.repeat(39)},{...checkout,tree:123},{...checkout,trackedDirty:undefined},{...checkout,trackedDirty:'false'},
    {...checkout,catalogBytes:undefined},{...checkout,catalogBytes:catalogBytes.toString()},
    {...checkout,catalogBytes:Buffer.alloc(0)}])
    assert.throws(()=>assertCurrentTabStopBuild(report,malformed));
  assert.throws(()=>assertCurrentTabStopBuild({...report,catalog_evidence:{sha256:'invalid'}},checkout),/SHA256/);
});
