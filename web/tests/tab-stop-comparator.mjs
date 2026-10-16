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
  const {revision,trackedDirty,catalogBytes}=checkout;
  assert.match(typeof revision==='string'?revision:'',/^[0-9a-f]{40}$/,'Current checkout revision required');
  assert.equal(trackedDirty,false,'Current checkout must have no dirty tracked files');
  assert.equal(report.build?.lab_revision,revision,'Historical build cannot be relabeled onto current checkout');
  assert(catalogBytes instanceof Uint8Array&&catalogBytes.length>0,'Actual current catalog bytes required');
  assert.match(report.catalog_evidence?.sha256||'',HASH,'Retained catalog SHA256 required');
  assert.equal(sha256(catalogBytes),report.catalog_evidence.sha256,'Actual current catalog bytes must match retained provenance');
  assert.deepEqual(JSON.parse(Buffer.from(catalogBytes).toString('utf8')),report.catalog,'Actual current catalog identity');
  return {revision,tracked_dirty:false,catalog_sha256:report.catalog_evidence.sha256};
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
export function sourceGeometry(images) {
  const geometry={};for(const name of STOPS) {
    const border=discoverBorder(images['forward_'+name]);assert(border,`${name}: discovery must expose a blue border`);
    geometry[name]=border.bounds;
  }
  assert.equal(new Set(Object.values(geometry).map(rect=>JSON.stringify(rect))).size,12,'Twelve distinct physical destinations');
  // These constraints come from source paint order, not report-provided labels.
  const cards=['item0','item1','item2','item4'];
  for(const name of cards) {assert.equal(geometry[name].x,16);assert.equal(geometry[name].width,768);}
  for(let i=1;i<cards.length;i++)assert(geometry[cards[i]].y>geometry[cards[i-1]].y,'Card identity follows source screen position');
  // The fifth source card is item4, not the visually higher item2. Repeated index2 is positional.
  assert(geometry.item4.y>geometry.item2.y,'Repeated-index item4 is the fifth source card');
  assert(geometry.el1.y>geometry.item4.y);assert.equal(geometry.el1.y,geometry.el2.y);
  assert.equal(geometry.el1.x,16);assert.equal(geometry.el2.x+geometry.el2.width,784);
  assert.equal(geometry.el1.width,geometry.el2.width);assert.equal(geometry.el1.height,geometry.el2.height);
  assert.equal(geometry.el2.x-(geometry.el1.x+geometry.el1.width),12,'Source row gap3');
  let previous=geometry.el1;
  for(const name of STOPS.slice(6)) {
    const rect=geometry[name];assert.equal(rect.x,16);assert.equal(rect.width,768);
    assert(rect.y>=previous.y+previous.height,'Default Block group children follow source vertical paint order');previous=rect;
  }
  // Initial screenshot independently exposes all five card edge runs, including non-stop item3.
  const runs=[];let start=null;
  for(let y=geometry.item0.y;y<geometry.el1.y;y++) {
    const dark=[16,783].every(x=>imageDark(images.initial,x,y));
    if(dark&&start===null)start=y;
    if(!dark&&start!==null){runs.push({y:start,height:y-start});start=null;}
  }
  if(start!==null)runs.push({y:start,height:geometry.el1.y-start});
  assert.equal(runs.length,5,'Exactly five initial source-card border runs, including the non-stop fourth card');
  for(const [name,index] of [['item0',0],['item1',1],['item2',2],['item4',4]]) {
    assert.equal(geometry[name].y,runs[index].y,'Observed ring must match independently detected initial card position');
    assert.equal(geometry[name].height,runs[index].height,'Card height must remain unchanged on focus');
  }
  return {stops:geometry,non_stop_card:{x:16,width:768,...runs[3]},message_bottom:geometry.item0.y-12,
    geometry_scope:'Observed actual Rust geometry constrained independently by source paint order; clipped lower borders remain disclosed'};
}
function imageDark(image,x,y) {
  const offset=4*(y*800+x);return image.data[offset+3]===255&&image.data[offset]<230&&image.data[offset+1]<230&&image.data[offset+2]<230;
}
export function validateTraversal(images,geometry) {
  assertNoBorder(images.initial);
  for(const name of STOPS) {
    assertBorder(images['forward_'+name],geometry.stops[name]);
    assertBorder(images['reverse_'+name],geometry.stops[name]);
  }
  assertBorder(images.forward_wrap,geometry.stops.item0);
  assertBorder(images.reverse_wrap,geometry.stops.group2_child3);
  const initial=messageDigest(images.initial,geometry.message_bottom);
  const forward=messageDigest(images.forward_item0,geometry.message_bottom);
  const reverse=messageDigest(images.reverse_group2_child3,geometry.message_bottom);
  assert.notEqual(initial,forward,'First Tab must visibly change source message');
  assert.notEqual(forward,reverse,'Shift-Tab must visibly change source message');
  for(const name of STOPS) {
    assert.equal(messageDigest(images['forward_'+name],geometry.message_bottom),forward,'All forward actions have the same source message');
    assert.equal(messageDigest(images['reverse_'+name],geometry.message_bottom),reverse,'All reverse actions have the same source message');
  }
  return {status:'source_order_and_message_relations_passed',geometry,
    limitation:'Pixel relations establish message changes, not OCR or exact literal-text validation'};
}
export function traversalNegativeControls(images,geometry) {
  validateTraversal(images,geometry);
  const rejected=(name,action)=>{assert.throws(action,`${name} survived`);return {name,rejected:true,
    input:'Corrupted copies of actual captures, never another Rust execution'};};
  const flat={...images,forward_item1:images.forward_group1_child1};
  // Flattening [6,1] to [1] puts a group child at the second Tab, before item1[2].
  const controls=[rejected('flattened_order_second_tab',()=>validateTraversal(flat,geometry)),
    rejected('repeated_index_cards_swapped',()=>validateTraversal({...images,forward_item1:images.forward_item4},geometry)),
    rejected('wrong_reverse_wrap',()=>validateTraversal({...images,reverse_wrap:images.reverse_item0},geometry))];
  const moved={...images.forward_item1,data:images.forward_item1.data.slice()};
  moved.data.set(BLUE,4*(8*800+8));
  controls.push(rejected('moved_or_extra_border',()=>assertBorder(moved,geometry.stops.item1)));
  return controls;
}
export function makeProfile(geometry=null) {
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
    key(name+'_tab','Tab','press',reverse);
    if(reverse)key(name+'_shift_up','Shift','up');
    capture(name,focus,reverse?'reverse':'forward');
  };
  const click=(name,rect,focus,message)=>{
    move(name+'_move',Math.floor(rect.x+rect.width/2),Math.floor(rect.y+rect.height/2));
    mouse(name+'_down',true);mouse(name+'_up',false);capture(name,focus,message);
  };
  move('initial_pointer',8,8);capture('initial',null,'initial');
  for(const name of STOPS)tab('forward_'+name,name);
  tab('forward_wrap','item0');
  for(const name of [...STOPS].reverse())tab('reverse_'+name,name,true);
  tab('reverse_wrap','group2_child3',true);
  if(geometry) {
    click('root_reset',{x:4,y:546,width:8,height:8},null,'reverse');
    tab('root_tab','item0');
    for(let index=0;index<STOPS.length;index++) {
      const name=STOPS[index];
      click('click_'+name,geometry.stops[name],name,name==='el1'||name==='el2'?name:'forward');
      tab('after_click_'+name,STOPS[(index+1)%STOPS.length]);
    }
    click('click_non_stop',geometry.non_stop_card,null,'forward');
    tab('after_non_stop','item0');
  }
  return {operations,captures};
}
export function validateOperations(result,geometry) {
  const profile=makeProfile(geometry);
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
// Imported locally as well as re-exported above for independent report checks.
import {assertDelivery} from './focus-visible-comparator.mjs';
export function validateClicks(images,geometry) {
  assertNoBorder(images.root_reset);assertNoBorder(images.click_non_stop);
  assertBorder(images.root_tab,geometry.stops.item0);assertBorder(images.after_non_stop,geometry.stops.item0);
  const forward=messageDigest(images.forward_item0,geometry.message_bottom);
  const reverse=messageDigest(images.reverse_group2_child3,geometry.message_bottom);
  assert.equal(messageDigest(images.root_reset,geometry.message_bottom),reverse,'Root has no click-message listener');
  const messages={};
  for(let index=0;index<STOPS.length;index++) {
    const name=STOPS[index];assertBorder(images['click_'+name],geometry.stops[name]);
    assertBorder(images['after_click_'+name],geometry.stops[STOPS[(index+1)%STOPS.length]]);
    const digest=messageDigest(images['click_'+name],geometry.message_bottom);
    if(name==='el1'||name==='el2'){assert.notEqual(digest,forward,'Source button listener must visibly change the message');messages[name]=digest;}
    else assert.equal(digest,forward,'Cards and group buttons have no invented click-message listeners');
    assert.equal(messageDigest(images['after_click_'+name],geometry.message_bottom),forward);
  }
  assert.notEqual(messages.el1,messages.el2,'Two authored click messages must be visually distinct');
  assert.equal(messageDigest(images.click_non_stop,geometry.message_bottom),forward,'Non-stop card has no click-message listener');
  return {status:'passed',listeners:['el1','el2'],non_listeners:STOPS.filter(name=>!['el1','el2'].includes(name)).concat(['root','item3'])};
}
