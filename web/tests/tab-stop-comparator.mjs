import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
// Transport assertions are shared; no old focus-visible runner or renderer is changed.
export {assertDelivery} from './focus-visible-comparator.mjs';

export const TAB_STOP=Object.freeze({width:800,height:600,dpr:1,
  revision:'5a5fbe79917971a4d52a96b6ddb04da198a5012e',
  source:'crates/gpui/examples/tab_stop.rs',sourceBlob:'cc7c34a9979ce4027578ec2c358f503d944ee26f',
  sourceSha256:'be187a56c091ee0b609fa396cae4a13b49dcf98ff9e602d8caed3126de3f6a8e'});
export const ENGINE=Object.freeze({repository:'gpui-mbt/gpui.mbt',
  revision:'61b237b0963c3252736a27293aa1f5b7de3886fa',tree:'29449e394c0faf2b25beb2a1b6a4bce2806b3231'});
export const EMBEDDED_FONTS=Object.freeze({
  "assets/fonts/ibm-plex-sans/IBMPlexSans-Regular.ttf": "975dcda37d80f038dcd143c22e33ca2d97a0cc5a929aace1c749153b0fe1afa5",
  "assets/fonts/ibm-plex-sans/IBMPlexSans-Italic.ttf": "a9c6ef9942c49e49d11e11a6dacc0b3a087978757e9b22a06b8ac22a6400fb15",
  "assets/fonts/ibm-plex-sans/IBMPlexSans-SemiBold.ttf": "a20caf8286023a6a7a85e40b1d2a4ae9fc3e3b1f9eda8f4c542dd4986af67bb1",
  "assets/fonts/ibm-plex-sans/IBMPlexSans-SemiBoldItalic.ttf": "147106b619423a82b40f6d64bace074ad5b786e59f48023bda69d63b1755fb82",
  "assets/fonts/lilex/Lilex-Regular.ttf": "8a467ad5a1941dc7c9cebaee34e3ed9364a73b48393034e363e4b528bd711d04",
  "assets/fonts/lilex/Lilex-Bold.ttf": "3369214e2ecddb45ae5024b11d45dd637e99e9d2127ab729817d41d72b8a9c68",
  "assets/fonts/lilex/Lilex-Italic.ttf": "a6e52046b91ed12a6af50bb74e70e27dea4a54eab2bed8947db4c1128ba83d45",
  "assets/fonts/lilex/Lilex-BoldItalic.ttf": "9629bd65ee7376879414560e37281653ca82dcf33e143d7473341b2f88206985"
});
export const STOPS=Object.freeze(['item0','item1','item4','item2','el1','el2',
  'group1_child1','group1_child2','group1_child3','group2_child1','group2_child2','group2_child3']);
export const SOURCE_CONSTRAINTS=Object.freeze([
  'tab_stop.rs:22-27: item0[1], item1[2], item2[3], item3 non-stop, item4[2]; source order breaks equal-index ties',
  'tab_stop.rs:30-31,75-94: initially focused non-stop root; flex-column, p4, gap3, white background',
  'tab_stop.rs:42-50: every Tab/Shift-Tab action changes the source-authored message',
  'tab_stop.rs:56-73,98-115: focused eligible cards/buttons use exactly 3px gpui::blue() border; black buttons use shadow_sm',
  'tab_stop.rs:119-142: only el1[4] and el2[5] have click-message listeners',
  'tab_stop.rs:145-191: default-Block non-stop groups 6 and 7, each containing three local stops 1..3; no invented group/card listeners',
  'Group containers have literal anchors [6,6] and [7,7]; focusing a group is not assumed to enter its first child',
  'Natural content can exceed the 600px window; discovery records observed geometry and clipping without changing upstream source',
  'Border1-to3 changes flex allocation; geometry and exact 12px gaps must be measured within each screenshot, never assembled across focused frames',
  'Only full original screenshots and trusted input are focus evidence; DOM focus and runtime-private diagnostics are not',
]);
export const sha256=data=>createHash('sha256').update(data).digest('hex');
const HASH=/^[0-9a-f]{64}$/;
export function assertProvenance(build,catalog) {
  assert.equal(build.upstream?.repository,'zed-industries/zed');
  assert.equal(build.upstream?.revision,TAB_STOP.revision);
  assert.deepEqual(build.moonbit,ENGINE,'Baseline must preserve the existing engine pin');
  assert.deepEqual(catalog.upstream,build.upstream);assert.deepEqual(catalog.moonbit,build.moonbit);
  assert.equal(build.lab_tracked_dirty,false);assert.match(build.lab_revision||'',/^[0-9a-f]{40}$/);assert.match(build.lab_tree||'',/^[0-9a-f]{40}$/);
  assert.equal(build.rust_bundled,true);assert.equal(build.rust?.source_modified,false);
  assert.equal(build.rust?.oracle_only,true);assert.equal(build.rust?.packaging?.upstream_files_modified,false);
  assert.deepEqual(build.rust_implemented,['tab_stop'],'This independent job must build only the explicit oracle');
  assert(!build.implemented?.includes('tab_stop'),'No MoonBit counterpart may be claimed');
  const entries=catalog.examples.filter(entry=>entry.id==='tab_stop');assert.equal(entries.length,1);
  for(const [key,value] of Object.entries({source:TAB_STOP.source,source_blob:TAB_STOP.sourceBlob,
    moonbit:'not_implemented',rust:'oracle_only',width:800,height:600}))assert.equal(entries[0][key],value);
  assert(!entries[0].candidate_source,'An unimplemented counterpart must have no candidate source');
  const records=build.rust_oracle_only.filter(entry=>entry.id==='tab_stop');assert.equal(records.length,1);
  for(const [key,value] of Object.entries({source:TAB_STOP.source,source_blob:TAB_STOP.sourceBlob,
    source_sha256:TAB_STOP.sourceSha256,upstream_revision:TAB_STOP.revision,
    status:'rust_oracle_only',candidate:'not_implemented',width:800,height:600,dpr:1}))assert.equal(records[0][key],value);
  assert(Number.isFinite(Date.parse(build.rust.build_completed_at_utc||'')),'Actual build completion timestamp required');
  assert.match(build.rust.toolchain||'',/^rustc 1\./);assert.match(build.rust.bindings||'',/^wasm-bindgen 0\.2\.129$/);
  assert.deepEqual(build.rust.packaging.additional_bins,[{name:'tab_stop',source:TAB_STOP.source}]);
  for(const file of ['tab_stop.js','tab_stop_bg.wasm','host.mjs','unchanged-source/tab_stop.rs','packaging-Cargo.toml'])
    assert.match(build.rust.files?.[file]||'',HASH,`Pinned Rust file ${file}`);
  assert.equal(build.rust.files['unchanged-source/tab_stop.rs'],TAB_STOP.sourceSha256);
  assert.equal(build.rust.files['packaging-Cargo.toml'],build.rust.packaging.manifest_sha256,'Retained relocated Cargo manifest hash');
  const fonts=Object.values(build.rust.embedded_fonts||{});assert.equal(fonts.length,8,'All eight upstream embedded font inputs required');
  assert.deepEqual(Object.fromEntries(Object.entries(build.rust.embedded_fonts).map(([path,font])=>[path,font.sha256])),EMBEDDED_FONTS,'Exact upstream embedded-font bytes');
  for(const font of fonts) {assert.match(font.sha256||'',HASH);assert.equal(build.rust.files[font.file],font.sha256);}
  assert(build.rust.command.includes('+nightly-2026-10-14'));assert(build.rust.command.includes('--locked'));
  assert.deepEqual(build.rust.command.filter((_argument,index,array)=>array[index-1]==='--bin'),['tab_stop']);
  assert.match(build.moonbit_host_files_sha256?.['load-timing.mjs']||'',HASH);
  return records[0];
}
export function assertCurrentTabStopBuild(report,checkout) {
  assert(checkout&&typeof checkout==='object'&&!Array.isArray(checkout),'Current Git checkout context required');
  const {revision,tree,trackedDirty,catalogBytes}=checkout;
  assert.match(typeof revision==='string'?revision:'',/^[0-9a-f]{40}$/,'Current checkout revision required');
  assert.match(typeof tree==='string'?tree:'',/^[0-9a-f]{40}$/,'Current checkout tree required');
  assert.equal(trackedDirty,false,'Current checkout must have no dirty tracked files');
  assert.equal(report.build?.lab_revision,revision,'Historical build cannot be relabeled onto current checkout');
  assert.equal(report.build?.lab_tree,tree,'Retained build tree must match the actual current checkout tree');
  assert(catalogBytes instanceof Uint8Array&&catalogBytes.length>0,'Actual current catalog bytes required');
  assert.match(report.catalog_evidence?.sha256||'',HASH,'Retained catalog SHA256 required');
  assert.equal(sha256(catalogBytes),report.catalog_evidence.sha256,'Actual current catalog bytes must match retained provenance');
  assert.deepEqual(JSON.parse(Buffer.from(catalogBytes).toString('utf8')),report.catalog,'Actual current catalog identity');
  return {revision,tree,tracked_dirty:false,catalog_sha256:report.catalog_evidence.sha256};
}
export function provenanceNegativeControls(build,catalog) {
  assertProvenance(build,catalog);
  return [
    ['wrong_source',b=>{b.rust_oracle_only[0].source_blob='0'.repeat(40);}],
    ['modified_archive',b=>{b.rust.packaging.upstream_files_modified=true;}],
    ['dirty_lab',b=>{b.lab_tracked_dirty=true;}],
    ['candidate_claim',b=>{b.implemented.push('tab_stop');}],
    ['wrong_engine',b=>{b.moonbit.revision='0'.repeat(40);}],
    ['missing_wasm',b=>{delete b.rust.files['tab_stop_bg.wasm'];}],
    ['missing_font',b=>{delete b.rust.embedded_fonts[Object.keys(b.rust.embedded_fonts)[0]];}],
  ].map(([name,mutate])=>{const copy=structuredClone(build);mutate(copy);
    assert.throws(()=>assertProvenance(copy,catalog),name);return {name,rejected:true};});
}
export function decodePng(bytes) {
  assert(Buffer.isBuffer(bytes)&&bytes.length>0&&bytes.length<=8*1024*1024,'Bounded original PNG bytes required');
  const decoder=fileURLToPath(new URL('../scripts/decode_oracle_png.py',import.meta.url));
  const decoded=spawnSync('python3',[decoder],{input:bytes,timeout:10000,maxBuffer:800*600*4+4096});
  if(decoded.error)throw decoded.error;
  assert.equal(decoded.status,0,`Pinned Pillow decode failed: ${decoded.stderr?.toString().slice(0,2048)}`);
  assert.equal(decoded.stdout.length,8+800*600*4,'Exact bounded decoder output required');
  assert.equal(decoded.stdout.readUInt32BE(0),800);assert.equal(decoded.stdout.readUInt32BE(4),600);
  return {width:800,height:600,data:new Uint8Array(decoded.stdout.subarray(8))};
}
export function assertImage(image) {
  assert.equal(image.width,800);assert.equal(image.height,600);
  assert(image.data instanceof Uint8Array);assert.equal(image.data.length,800*600*4);
}
const sameColor=(data,offset,color)=>color.every((value,index)=>data[offset+index]===value);
const BLUE=[0,0,255,255];
export function discoverBorder(image) {
  assertImage(image);let left=800,top=600,right=-1,bottom=-1,count=0;
  for(let y=0;y<600;y++)for(let x=0;x<800;x++)if(sameColor(image.data,4*(y*800+x),BLUE)) {
    left=Math.min(left,x);top=Math.min(top,y);right=Math.max(right,x);bottom=Math.max(bottom,y);count++;
  }
  return count?{bounds:{x:left,y:top,width:right-left+1,height:bottom-top+1},blue_pixels:count,
    viewport_clipped:left===0||top===0||right===799||bottom===599}:null;
}
export function assertBorder(image,rect) {
  const observed=discoverBorder(image);assert(observed,'A visible source-authored blue focus border is required');
  assert.deepEqual(observed.bounds,rect,'Expected independently established physical focus destination');
  assert(rect.width>12&&rect.height>6,'A measurable focus-border region is required');
  let checked=0;
  for(let y=0;y<600;y++)for(let x=0;x<800;x++) {
    const inside=x>=rect.x&&x<rect.x+rect.width&&y>=rect.y&&y<rect.y+rect.height;
    const blue=sameColor(image.data,4*(y*800+x),BLUE);
    if(blue)assert(inside,'No additional blue destination is permitted');
  }
  // Vertical edges remain measurable when a lower control overflows the viewport.
  for(let y=rect.y+3;y<rect.y+rect.height-(rect.y+rect.height===600?0:3);y++)
    for(const x of [rect.x,rect.x+1,rect.x+2,rect.x+rect.width-3,rect.x+rect.width-2,rect.x+rect.width-1]) {
      assert(sameColor(image.data,4*(y*800+x),BLUE),`Exactly 3px blue side border at ${x},${y}`);checked++;
    }
  for(let x=rect.x+3;x<rect.x+rect.width-3;x++)for(let y=rect.y;y<rect.y+3;y++) {
    assert(sameColor(image.data,4*(y*800+x),BLUE),'Exactly 3px blue top border');checked++;
  }
  // Fourth inward pixel must not be blue, rejecting an over-wide border.
  for(const x of [rect.x+3,rect.x+rect.width-4])for(let y=rect.y+4;y<rect.y+rect.height-4;y++)
    assert(!sameColor(image.data,4*(y*800+x),BLUE),'Border must not exceed 3px');
  if(rect.y+rect.height<600)for(let x=rect.x+3;x<rect.x+rect.width-3;x++)for(let y=rect.y+rect.height-3;y<rect.y+rect.height;y++)
    assert(sameColor(image.data,4*(y*800+x),BLUE),'Exactly 3px blue bottom border');
  return {...observed,checked_border_pixels:checked};
}
export function assertNoBorder(image) {assert.equal(discoverBorder(image),null,'Non-stop root must have no blue ring');}
export function messageDigest(image,bottom) {
  assertImage(image);assert(Number.isInteger(bottom)&&bottom>16&&bottom<100,'Observed first-card top bounds the source message');
  const bytes=new Uint8Array((bottom-16)*768*4);
  for(let y=16;y<bottom;y++)bytes.set(image.data.subarray(4*(y*800+16),4*(y*800+784)),(y-16)*768*4);
  return sha256(bytes);
}
const BLACK=[0,0,0,255],WHITE=[255,255,255,255],DISABLED=[153,153,153,255];
const CARD_NAMES=['item0','item1','item2','item3','item4'];
function pixelIs(image,x,y,color) {return sameColor(image.data,4*(y*800+x),color);}
function runs(length,predicate) {
  const found=[];let start=null;
  for(let index=0;index<=length;index++) {
    const selected=index<length&&predicate(index);
    if(selected&&start===null)start=index;
    if(!selected&&start!==null){found.push({start,length:index-start});start=null;}
  }
  return found;
}
function solid(image,rect,color,label) {
  for(let y=rect.y;y<rect.y+rect.height;y++)for(let x=rect.x;x<rect.x+rect.width;x++)
    assert(pixelIs(image,x,y,color),`${label}: source color at ${x},${y}`);
}
function cardStyle(image,rect,index,focused) {
  if(focused){assertBorder(image,rect);return;}
  const color=index===3?DISABLED:BLACK;
  for(const edge of [{...rect,height:1},{...rect,y:rect.y+rect.height-1,height:1},
    {...rect,width:1},{...rect,x:rect.x+rect.width-1,width:1}])solid(image,edge,color,'Exactly 1px source card border');
  // The interior adjacent to each border excludes central text. A source hover
  // is black alpha 0.1 over white, with the two possible UNORM8 roundings only.
  const fills=index===3?[WHITE]:[WHITE,[229,229,229,255],[230,230,230,255]];
  for(const x of [rect.x+1,rect.x+rect.width-2])for(let y=rect.y+1;y<rect.y+rect.height-1;y++)
    assert(fills.some(color=>pixelIs(image,x,y,color)),'A normal card border must remain exactly 1px, with source white/hover interior');
}
export function frameGeometry(image) {
  assertImage(image);
  // Both full-width edges independently expose the five cards, ordinary row,
  // and two default-Block groups. Shadows/label ink are not border geometry.
  const palette=[BLACK,BLUE,DISABLED];
  const vertical=runs(600,y=>[16,783].every(x=>palette.some(color=>pixelIs(image,x,y,color))));
  assert.equal(vertical.length,8,'Each frame must independently expose five cards, one row and two Block groups');
  const controls={};
  for(let index=0;index<5;index++) {
    const run=vertical[index];assert(run.length<=40,'Source h10 cards may flex-shrink but cannot grow beyond their outer basis');
    controls[CARD_NAMES[index]]={x:16,y:run.start,width:768,height:run.length};
  }
  const row=vertical[5];assert.equal(row.length,40,'Source ordinary h10 buttons');
  const horizontal=runs(800,x=>[BLACK,BLUE].some(color=>pixelIs(image,x,row.start,color)));
  assert.equal(horizontal.length,2,'Two ordinary buttons must be independently located in this frame');
  for(let index=0;index<2;index++)controls['el'+(index+1)]={x:horizontal[index].start,y:row.start,width:horizontal[index].length,height:row.length};
  assert.equal(controls.el1.x,16);assert.equal(controls.el2.x+controls.el2.width,784);
  assert.equal(controls.el2.x-(controls.el1.x+controls.el1.width),12,'Same-frame source row gap3');
  for(let index=1;index<vertical.length;index++)
    assert.equal(vertical[index].start-(vertical[index-1].start+vertical[index-1].length),12,'Same-frame source column gap3');
  for(let group=1;group<=2;group++) {
    const block=vertical[5+group];assert.equal(block.length,3*40,'Three source h10 children in each default-Block group');
    for(let child=1;child<=3;child++)controls[`group${group}_child${child}`]={x:16,y:block.start+(child-1)*40,width:768,height:40};
  }
  const observed=discoverBorder(image);
  const focused=observed?Object.keys(controls).find(name=>JSON.stringify(controls[name])===JSON.stringify(observed.bounds)):null;
  assert(!observed||focused,'The unique blue border must coincide with a physical source control in this same frame');
  assert.notEqual(focused,'item3','The non-stop fourth source card must never display a blue focus border');
  const message_bottom=controls.item0.y-12;
  assert(message_bottom>16&&message_bottom<100,'Source message precedes first card and gap3');
  const lineHeight=message_bottom-16;
  for(let index=0;index<5;index++) {
    const name=CARD_NAMES[index],border=focused===name?3:1;
    assert(controls[name].height>=lineHeight+2*border,'Source card auto-minimum includes the same single-line text height and its own borders');
    cardStyle(image,controls[name],index,focused===name);
  }
  if(observed)assertBorder(image,controls[focused]);
  // Equal flex1 content boxes include their own source border widths. Comparing
  // differently focused screenshots would incorrectly manufacture an 8px gap.
  assert.equal(controls.el1.width-2*(focused==='el1'?3:1),controls.el2.width-2*(focused==='el2'?3:1),
    'Source flex1 ordinary buttons must have equal inner widths in each frame');
  for(const name of STOPS.slice(4)) {
    const rect=controls[name],border=focused===name?3:1;
    solid(image,{x:rect.x+border,y:rect.y+border,width:5,height:rect.height-2*border},BLACK,'Source black button fill');
  }
  return {controls,observed_focus:focused,message_bottom,
    observed_blue_border:observed,geometry_scope:'Independently parsed same-frame source controls; no cross-frame rectangle assembly'};
}
export function sourceGeometry(images) {
  return {frames:Object.fromEntries(Object.entries(images).map(([name,image])=>[name,frameGeometry(image)])),
    geometry_scope:'State-specific actual screenshot geometry constrained by source paint order and exact same-frame gaps'};
}
function assertFrame(image,frame,focus) {
  assert.deepEqual(frameGeometry(image),frame,'Geometry must be independently derived from this exact screenshot');
  if(focus===null||focus==='item3')assertNoBorder(image);
  else assertBorder(image,frame.controls[focus]);
}
function validateFrames(images,geometry,profile) {
  for(const [name,spec] of Object.entries(profile.captures)) {
    assert(images[name]&&geometry.frames[name],`${name}: original image and its own geometry required`);
    assertFrame(images[name],geometry.frames[name],spec.focus);
    const canonical=spec.focus&&spec.focus!=='item3'?'forward_'+spec.focus:'initial';
    assert.deepEqual(geometry.frames[name].controls,geometry.frames[canonical].controls,
      `${name}: same-focus physical geometry must remain consistent across reverse/pointer/message states`);
    assert.equal(geometry.frames[name].message_bottom,geometry.frames.initial.message_bottom,'Source single-line message geometry');
  }
}
const message=(images,geometry,name)=>messageDigest(images[name],geometry.frames[name].message_bottom);
export function validateTraversal(images,geometry) {
  const profile=makeProfile();validateFrames(images,geometry,profile);
  const initial=message(images,geometry,'initial'),forward=message(images,geometry,'forward_item0');
  const reverse=message(images,geometry,'reverse_group2_child3');
  assert.notEqual(initial,forward,'First Tab must visibly change source message');
  assert.notEqual(forward,reverse,'Shift-Tab must visibly change source message');
  for(const [name,spec] of Object.entries(profile.captures))
    assert.equal(message(images,geometry,name),{initial,forward,reverse}[spec.message],'Source-authored traversal message relation');
  return {status:'source_order_and_message_relations_passed',geometry,
    limitation:'Pixel relations establish message changes, not OCR or exact literal-text validation'};
}
export function traversalNegativeControls(images,geometry) {
  validateTraversal(images,geometry);
  const rejected=(name,action)=>{assert.throws(action,`${name} survived`);return {name,rejected:true,
    input:'Corrupted copies of actual captures, never another Rust execution'};};
  const controls=[rejected('flattened_order_second_tab',()=>validateTraversal({...images,forward_item1:images.forward_group1_child1},geometry)),
    rejected('repeated_index_cards_swapped',()=>validateTraversal({...images,forward_item1:images.forward_item4},geometry)),
    rejected('wrong_reverse_wrap',()=>validateTraversal({...images,reverse_wrap:images.reverse_item0},geometry))];
  const moved={...images.forward_item1,data:images.forward_item1.data.slice()};moved.data.set(BLUE,4*(8*800+8));
  controls.push(rejected('moved_or_extra_border',()=>assertFrame(moved,geometry.frames.forward_item1,'item1')));
  const mixed=structuredClone(geometry);
  mixed.frames.forward_el1.controls.el2=geometry.frames.forward_el2.controls.el2;
  controls.push(rejected('cross_frame_ordinary_geometry',()=>validateTraversal(images,mixed)));
  return controls;
}
class NeedsFrame extends Error {constructor(name){super(name);this.capture=name;}}
const inside=(rect,{x,y})=>x>=rect.x&&x<rect.x+rect.width&&y>=rect.y&&y<rect.y+rect.height;
export function movingEdgePoint(initial,current,target) {
  const before=initial.controls[target],now=current.controls[target];
  assert.equal(current.observed_focus,target,'Moving-edge intent requires the intended current focused control');
  let point;
  if(target==='item0') {
    assert.equal(now.y,before.y);assert.equal(now.y+now.height-(before.y+before.height),1,'Source fixed-profile card must expose its observed new 1px bottom edge');
    point={x:Math.floor(now.x+now.width/2),y:now.y+now.height-1};
  }else if(target==='el1') {
    assert.equal(now.x+now.width-(before.x+before.width),2,'Source border1-to3 exposes new 2px right edge');
    point={x:now.x+now.width-1,y:Math.floor(now.y+now.height/2)};
  }else {
    assert.equal(target,'el2');assert.equal(before.x-now.x,2,'Source border1-to3 exposes new 2px left edge');
    point={x:now.x,y:Math.floor(now.y+now.height/2)};
  }
  assert(inside(now,point)&&!inside(before,point),'Trusted edge click must be inside current visual bounds and outside frozen initial bounds');
  return point;
}
export function makeProfile(frames=null) {
  const operations=[],captures={};let pointer={x:0,y:0};
  const mods={shiftKey:false,ctrlKey:false,altKey:false,metaKey:false};
  const add=(name,action,expected)=>operations.push({name,action,expected});
  const move=(name,x,y)=>{add(name,{kind:'move',x,y},[{type:'pointermove',x,y,button:-1,buttons:0,pointerType:'mouse',...mods}]);pointer={x,y};};
  const mouse=(name,down)=>add(name,{kind:'mouse',down},[{type:down?'pointerdown':'pointerup',...pointer,button:0,buttons:down?1:0,pointerType:'mouse',...mods}]);
  const key=(name,key,type='press',shift=false)=>add(name,{kind:'key',key,type},
    (type==='press'?['keydown','keyup']:[type==='down'?'keydown':'keyup']).map(type=>({type,key,
      code:key==='Shift'?'ShiftLeft':key,...mods,shiftKey:shift,repeat:false})));
  const capture=(name,focus,message)=>{captures[name]={after_operation:operations.length,focus,message};};
  const tab=(name,focus,reverse=false)=>{
    if(reverse)key(name+'_shift_down','Shift','down',true);
    key(name+'_tab','Tab','press',reverse);if(reverse)key(name+'_shift_up','Shift','up');
    capture(name,focus,reverse?'reverse':'forward');
  };
  const click=(name,point,focus,message)=>{
    move(name+'_move',point.x,point.y);mouse(name+'_down',true);mouse(name+'_up',false);capture(name,focus,message);
  };
  const need=(name,focus)=>{
    if(!frames[name])throw new NeedsFrame(name);
    assert.equal(frames[name].observed_focus,focus==='item3'?null:focus,`${name}: current-frame focus intent`);return frames[name];
  };
  const center=(frame,target)=>{const rect=frame.controls[target];return {x:Math.floor(rect.x+rect.width/2),y:Math.floor(rect.y+rect.height/2)};};
  move('initial_pointer',8,8);capture('initial',null,'initial');
  for(const name of STOPS)tab('forward_'+name,name);tab('forward_wrap','item0');
  for(const name of [...STOPS].reverse())tab('reverse_'+name,name,true);tab('reverse_wrap','group2_child3',true);
  if(!frames)return {operations,captures,complete:false,phase:'traversal'};
  try {
    click('root_reset',{x:8,y:550},null,'reverse');tab('root_tab','item0');
    let current='root_tab';
    for(let index=0;index<STOPS.length;index++) {
      const name=STOPS[index];
      click('click_'+name,center(need(current,name),name),name,name==='el1'||name==='el2'?name:'forward');
      current='after_click_'+name;tab(current,STOPS[(index+1)%STOPS.length]);
    }
    click('click_non_stop',center(need(current,'item0'),'item3'),'item3','forward');tab('after_non_stop','item0');
    click('edge_root_reset',{x:8,y:550},null,'forward');tab('edge_card_focus','item0');
    const edge=(prefix,source,target,next)=>{
      const point=movingEdgePoint(need('initial',null),need(source,target),target);
      move(prefix+'_move',point.x,point.y);capture(prefix+'_hover',target,'forward');
      mouse(prefix+'_down_event',true);capture(prefix+'_down',target,'forward');
      mouse(prefix+'_up_event',false);capture(prefix+'_click',target,target==='item0'?'forward':target);
      tab(prefix+'_next',next);
    };
    edge('edge_card','edge_card_focus','item0','item1');
    tab('edge_before_el1_item4','item4');tab('edge_before_el1_item2','item2');tab('edge_el1_focus','el1');
    edge('edge_el1','edge_el1_focus','el1','el2');edge('edge_el2','edge_el1_next','el2','group1_child1');
  }catch(error) {
    if(error instanceof NeedsFrame)return {operations,captures,complete:false,blocked_on_capture:error.capture};
    throw error;
  }
  return {operations,captures,complete:true};
}
export function validateOperations(result,geometry) {
  const profile=makeProfile(geometry.frames);assert(profile.complete,'Complete current-frame profile geometry required');
  assert.equal(result.operations.length,profile.operations.length,'Complete fixed source/input profile required');
  assert(Array.isArray(result.startup_events));assert.equal(result.operation_start,result.startup_events.length);
  assert.deepEqual(result.events.slice(0,result.operation_start),result.startup_events,'Startup prefix must be preserved');
  for(const event of result.startup_events)assert(event.type==='pointermove'&&event.trusted===true&&event.x===0&&event.y===0,'Only the optional initial browser pointer move can precede the profile');
  const flattened=[];
  for(let index=0;index<profile.operations.length;index++) {
    const actual=result.operations[index],expected=profile.operations[index];
    assert.equal(actual.name,expected.name);assert.equal(actual.status,'delivered');
    assert.deepEqual(actual.expected,expected.expected,'Report expectations cannot redefine the source input plan');
    assertDelivery(actual.events,expected.expected);flattened.push(...actual.events);
  }
  assert.deepEqual(result.events.slice(result.operation_start),flattened,'Whole trusted operation sequence must be retained without gaps');
  assert.deepEqual(Object.keys(result.captures).sort(),Object.keys(profile.captures).sort(),'Complete capture inventory');
  for(const [name,expected] of Object.entries(profile.captures))assert.equal(result.captures[name].after_operation,expected.after_operation,`${name}: capture position`);
  return {status:'passed',operations:profile.operations.length,captures:Object.keys(profile.captures).length};
}
import {assertDelivery} from './focus-visible-comparator.mjs';
export function validateClicks(images,geometry) {
  const profile=makeProfile(geometry.frames);assert(profile.complete,'All current-frame click and edge captures required');
  validateFrames(images,geometry,profile);
  const values=Object.fromEntries([['initial','initial'],['forward','forward_item0'],['reverse','reverse_group2_child3'],
    ['el1','click_el1'],['el2','click_el2']].map(([kind,name])=>[kind,message(images,geometry,name)]));
  assert.equal(new Set(Object.values(values)).size,5,'All five source-authored message categories must be visibly distinct');
  for(const [name,spec] of Object.entries(profile.captures))assert.equal(message(images,geometry,name),values[spec.message],
    `${name}: only source-authored Tab, reverse or el1/el2 click message may change`);
  return {status:'passed',listeners:['el1','el2'],non_listeners:STOPS.filter(name=>!['el1','el2'].includes(name)).concat(['root','item3']),
    moving_edges:['item0 newly visible 1px bottom edge','el1 newly visible 2px right edge','el2 newly visible 2px left edge']};
}
