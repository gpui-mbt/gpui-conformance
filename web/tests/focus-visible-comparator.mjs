import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';

// These are source-derived constraints on independently captured browser pixels,
// not a substitute renderer or a representation of private GPUI focus state.
export const FOCUS_VISIBLE=Object.freeze({width:800,height:600,dpr:1,
  revision:'5a5fbe79917971a4d52a96b6ddb04da198a5012e',
  source:'crates/gpui/examples/focus_visible.rs',sourceBlob:'c5b3d5dfec3a189d088a621baff55eb55a121b6c'});
export const COLORS=Object.freeze({root:[243,244,246,255],panel:[219,234,254,255],
  blue:[37,99,235,255],hover:[29,78,216,255],yellow:[251,191,36,255],green:[16,185,129,255]});
export const GEOMETRY=Object.freeze({panel:{x:32,y:95,width:736,height:58},
  buttons:[208,319,430].map(y=>({x:32,y,width:736,height:64}))});
export const SOURCE_CONSTRAINTS=Object.freeze([
  'focus_visible.rs:25-48: signed tab indices 1,2,3; all buttons are stops; initial non-stop root focus',
  'focus_visible.rs:83-217: p8/gap6 root, 64px buttons, 4px yellow focus and green focus-visible overrides, blue/hover fills',
  'window.rs:2186,5636-5645: initially Mouse; KeyDown selects Keyboard; MouseMove/MouseDown select Mouse; releases/wheel preserve modality',
  'window.rs:797-807: keyboard modality suppresses hover without moving the pointer',
  'gpui_web/src/events.rs:704-810: hidden textarea keyboard transport; modifier-only keys do not dispatch GPUI KeyDown/KeyUp',
  'elements/div.rs:3016-3078: unmodified activation down records focus generation; activation up checks generation, not down/up key identity',
  'gpui_web/events.rs:1016-1033,545-557: trusted desktop textarea Enter beforeinput inserts no text; it dispatches internal Enter down/up, so activation can complete before physical keyup',
  'elements/div.rs:3084-3132: primary click requires completed inside release; outside release clears pending click; secondary does not call on_click',
  'Focus is inferred only from rendered rings and subsequent navigation; DOM focus is transport, not the GPUI focus oracle',
  '800x600 DPR1 geometry is source-derived and must pass actual CI screenshots; no high-DPR, OCR, native or cross-renderer text claim',
]);
export function assertProvenance(manifest,catalog) {
  assert.equal(manifest.upstream?.revision,FOCUS_VISIBLE.revision,'Pinned upstream revision');
  assert.equal(manifest.lab_tracked_dirty,false,'Clean tracked lab source is required');
  assert.match(manifest.lab_revision||'',/^[0-9a-f]{40}$/,'Lab revision must be retained');
  assert.equal(manifest.rust_bundled,true,'Actual Rust WASM must be bundled');
  assert.equal(manifest.rust?.source_modified,false,'Upstream Rust example must be unchanged');
  assert.equal(manifest.rust?.packaging?.upstream_files_modified,false,'Archived upstream files must be unchanged');
  assert.deepEqual(catalog.upstream,manifest.upstream,'Catalog and manifest upstream identity');
  assert.deepEqual(catalog.moonbit,manifest.moonbit,'Catalog and manifest candidate pin');
  assert(!catalog.examples.some(entry=>entry.id==='focus_visible'&&entry.moonbit==='implemented'),'No candidate implementation may be implied');
  assert(!manifest.implemented.includes('focus_visible'),'Rust-only example must not be a compiled candidate');
  assert(manifest.rust_implemented.includes('focus_visible'),'Rust example must be compiled');
  const records=manifest.rust_oracle_only.filter(entry=>entry.id==='focus_visible');
  assert.equal(records.length,1,'One explicit Rust-only source record required');
  const record=records[0];
  for(const [key,value] of Object.entries({source:FOCUS_VISIBLE.source,source_blob:FOCUS_VISIBLE.sourceBlob,
    upstream_revision:FOCUS_VISIBLE.revision,width:800,height:600,dpr:1,status:'rust_oracle_only',candidate:'not_implemented'}))
    assert.equal(record[key],value,`Oracle provenance ${key}`);
  for(const file of ['focus_visible.js','focus_visible_bg.wasm','host.mjs'])
    assert.match(manifest.rust.files[file]||'',/^[0-9a-f]{64}$/,`Manifest SHA256 required for ${file}`);
  return record;
}
export function provenanceNegativeControls(manifest,catalog) {
  assertProvenance(manifest,catalog);
  const changes=[
    ['dirty_lab',value=>{value.lab_tracked_dirty=true;}],
    ['wrong_upstream',value=>{value.upstream.revision='0'.repeat(40);}],
    ['modified_source',value=>{value.rust.source_modified=true;}],
    ['modified_archive',value=>{value.rust.packaging.upstream_files_modified=true;}],
    ['wrong_example_blob',value=>{value.rust_oracle_only.find(entry=>entry.id==='focus_visible').source_blob='0'.repeat(40);}],
    ['missing_runtime_hash',value=>{delete value.rust.files['focus_visible_bg.wasm'];}],
    ['candidate_claim',value=>{value.implemented.push('focus_visible');}],
  ];
  return changes.map(([name,mutate])=>{
    const copy=structuredClone(manifest);mutate(copy);
    assert.throws(()=>assertProvenance(copy,catalog),`${name}: provenance negative control survived`);
    return {name,rejected:true,input:'Intentionally corrupted copy of retained build provenance'};
  });
}
const digest=data=>createHash('sha256').update(data).digest('hex');
const matches=(data,index,color)=>color.every((value,channel)=>data[index+channel]===value);
const palette=Object.values(COLORS).slice(2);
export function assertImage(image) {
  assert.equal(image.width,800,'Full 800 CSS-pixel DPR1 image width required');
  assert.equal(image.height,600,'Full 600 CSS-pixel DPR1 image height required');
  assert.equal(image.data.length,800*600*4,'Complete RGBA pixels required');
}
export function pixel(image,x,y) {
  assert(Number.isInteger(x)&&Number.isInteger(y)&&x>=0&&y>=0&&x<image.width&&y<image.height);
  return Array.from(image.data.subarray(4*(y*image.width+x),4*(y*image.width+x)+4));
}
function boundsOf(image,colors,region={x:0,y:0,width:800,height:600}) {
  let left=800,top=600,right=-1,bottom=-1,pixels=0;
  for(let y=region.y;y<region.y+region.height;y++)for(let x=region.x;x<region.x+region.width;x++) {
    const index=4*(y*image.width+x);
    if(colors.some(color=>matches(image.data,index,color))) {
      left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);pixels++;
    }
  }
  return pixels?{bounds:{x:left,y:top,width:right-left+1,height:bottom-top+1},pixels}:null;
}
function solid(image,rect,color,label) {
  let checked=0;
  for(let y=rect.y;y<rect.y+rect.height;y++)for(let x=rect.x;x<rect.x+rect.width;x++) {
    assert(matches(image.data,4*(y*image.width+x),color),`${label}: incorrect pixel ${x},${y}`);checked++;
  }
  return checked;
}
function ink(image,rect,predicate,label) {
  let count=0;
  for(let y=rect.y;y<rect.y+rect.height;y++)for(let x=rect.x;x<rect.x+rect.width;x++) {
    const offset=4*(y*image.width+x);
    if(predicate(image.data[offset],image.data[offset+1],image.data[offset+2],image.data[offset+3]))count++;
  }
  assert(count>=20,`${label}: nonempty rendered ink required`);return count;
}
const dark=(r,g,b,a)=>a===255&&r<100&&g<110&&b<160;
const white=(r,g,b,a)=>a===255&&r>225&&g>225&&b>225;
function ringFor(button,focus,modality) {
  if(button!==focus)return null;
  if(button===1)return 'yellow';
  if(modality==='keyboard')return 'green';
  return button===3?'yellow':null;
}
export function inspectState(image,{focus,modality,hover=0}) {
  assertImage(image);
  assert([0,1,2,3].includes(focus),'Expected GPUI focus target must be root or button 1..3');
  assert(['mouse','keyboard'].includes(modality),'Expected modality must be explicit');
  assert([0,1,2,3].includes(hover),'Expected pointer hover target must be explicit');
  let checked=0;
  for(const rect of [{x:0,y:0,width:800,height:16},{x:0,y:16,width:16,height:584},
    {x:784,y:16,width:16,height:584},{x:16,y:584,width:768,height:16}])
    checked+=solid(image,rect,COLORS.root,'Root padding');
  const panel=boundsOf(image,[COLORS.panel]);
  assert.deepEqual(panel?.bounds,GEOMETRY.panel,'Source-derived message panel geometry');
  const buttons=GEOMETRY.buttons.map((rect,index)=>{
    const button=index+1,ring=ringFor(button,focus,modality),fill=modality==='mouse'&&hover===button?'hover':'blue';
    const observed=boundsOf(image,palette,{x:0,y:rect.y-8,width:800,height:80});
    assert.deepEqual(observed?.bounds,rect,`Button ${button}: source-derived geometry`);
    // Straight edges avoid rounded-corner antialiasing and central label ink.
    const edge=COLORS[ring||fill];
    for(const edgeRect of [
      {x:rect.x+10,y:rect.y,width:rect.width-20,height:4},
      {x:rect.x+10,y:rect.y+rect.height-4,width:rect.width-20,height:4},
      {x:rect.x,y:rect.y+10,width:4,height:rect.height-20},
      {x:rect.x+rect.width-4,y:rect.y+10,width:4,height:rect.height-20}])
      checked+=solid(image,edgeRect,edge,`Button ${button}: ${ring||'absent'} ring, exactly 4px`);
    for(const fillRect of [
      {x:rect.x+10,y:rect.y+4,width:rect.width-20,height:5},
      {x:rect.x+10,y:rect.y+rect.height-9,width:rect.width-20,height:5},
      {x:rect.x+4,y:rect.y+10,width:5,height:rect.height-20},
      {x:rect.x+rect.width-9,y:rect.y+10,width:5,height:rect.height-20}])
      checked+=solid(image,fillRect,COLORS[fill],`Button ${button}: ${fill} fill and inner ring boundary`);
    const labelInk=ink(image,{x:rect.x+12,y:rect.y+10,width:rect.width-24,height:rect.height-20},white,`Button ${button} label`);
    return {button,ring,fill,label_ink_pixels:labelInk,observed:observed.bounds};
  });
  // Disallow shifted/extra controls and unexpected focus-colored pixels outside
  // the three source-defined button boxes, not just a few passing sample points.
  for(let y=0;y<600;y++)for(let x=0;x<800;x++) {
    const offset=4*(y*800+x);
    if(palette.some(color=>matches(image.data,offset,color)))
      assert(GEOMETRY.buttons.some(rect=>x>=rect.x&&x<rect.x+rect.width&&y>=rect.y&&y<rect.y+rect.height),
        `Unexpected button/ring palette outside geometry at ${x},${y}`);
  }
  const text={heading:ink(image,{x:32,y:32,width:736,height:39},dark,'Title'),
    message:ink(image,{x:48,y:111,width:704,height:26},dark,'Message panel'),
    labels:[177,288,399].map(y=>ink(image,{x:32,y,width:736,height:23},dark,'Section label'))};
  return {status:'passed',expected:{focus,modality,hover},geometry:GEOMETRY,buttons,text,
    checked_solid_pixels:checked,measurement:'Independent full RGBA screenshot geometry, straight ring edges and fill patches; ink presence only'};
}
function regionBytes(image,rect) {
  assertImage(image);const output=new Uint8Array(rect.width*rect.height*4);
  for(let row=0;row<rect.height;row++)output.set(image.data.subarray(
    4*((rect.y+row)*800+rect.x),4*((rect.y+row)*800+rect.x+rect.width)),row*rect.width*4);
  return output;
}
export function assertPanelSame(before,after) {
  const a=digest(regionBytes(before,GEOMETRY.panel)),b=digest(regionBytes(after,GEOMETRY.panel));
  assert.equal(b,a,'Message panel must remain pixel-identical');
  return {status:'passed',rgba_sha256:b,region:GEOMETRY.panel,meaning:'same within-renderer message pixels; not OCR'};
}
export function assertPanelDifferent(before,after) {
  const a=regionBytes(before,GEOMETRY.panel),b=regionBytes(after,GEOMETRY.panel);
  let different=0;for(let index=0;index<a.length;index+=4)if(!matches(b,index,a.subarray(index,index+4)))different++;
  assert(different>=20,'Message panel must visibly change (at least 20 pixels)');
  return {status:'passed',changed_pixels:different,before_sha256:digest(a),after_sha256:digest(b),region:GEOMETRY.panel};
}
export function assertUnchanged(before,after) {
  assertImage(before);assertImage(after);
  assert.equal(digest(after.data),digest(before.data),'Complete rendered image must remain unchanged');
  return {status:'passed',rgba_sha256:digest(after.data),checked_pixels:800*600};
}
export function assertDelivery(events,expected) {
  assert(expected.length>0,'A nonempty expected event sequence is required');
  assert.equal(events.length,expected.length,'Exact delivered event count is required');
  for(let index=0;index<expected.length;index++) {
    const event=events[index],wanted=expected[index];
    assert(['pointermove','pointerdown','pointerup','keydown','keyup','wheel','beforeinput'].includes(wanted.type),'Explicit supported expected event type is required');
    assert.equal(event.trusted,true,'Trusted browser delivery is required');
    assert(['pointermove','pointerdown','pointerup','keydown','keyup','wheel','beforeinput'].includes(event.type),'Supported observed transport event');
    if(event.type==='beforeinput') {
      assert.equal(event.target,'TEXTAREA','Beforeinput transport must be textarea');
      assert(['insertLineBreak','insertParagraph'].includes(event.inputType),'Only source-handled Enter beforeinput');
      assert.equal(event.isComposing,false);assert.equal(event.cancelable,true);assert.equal(event.defaultPrevented,true);
      assert.equal(event.data,null,'Enter beforeinput must not contain inserted text');
    } else if(event.type.startsWith('key'))assert(['TEXTAREA','CANVAS'].includes(event.target),'Keyboard transport target must be GPUI input');
    else assert.equal(event.target,'CANVAS','Pointer/wheel transport target must be canvas');
    if(event.type.startsWith('pointer'))assert.equal(event.pointerType,'mouse','Mouse pointer evidence required');
    if(event.type==='wheel') {assert.equal(event.deltaMode,0);assert.equal(event.defaultPrevented,true);}
    for(const [key,value] of Object.entries(wanted))assert.equal(event[key],value,`Delivered event ${index}: ${key}`);
  }
  return {status:'passed',events,expected,meaning:'Trusted browser transport evidence, not private GPUI state'};
}

// Corrupt copies of actual retained pixels/events. These controls test comparator
// sensitivity only; they are never presented as additional Rust executions.
export function focusVisibleNegativeControls(captures,operations=[]) {
  const controls=[];
  const baselines={initial:[0,'mouse'],tab1:[1,'keyboard'],tab2:[2,'keyboard'],tab3:[3,'keyboard'],
    wrap1:[1,'keyboard'],reverse3:[3,'keyboard'],reverse2:[2,'keyboard'],reverse1:[1,'keyboard'],reverse_wrap3:[3,'keyboard'],
    click1:[1,'mouse',1],click2:[2,'mouse',2],click3:[3,'mouse',3],down2:[2,'mouse',2],outside_up2:[2,'mouse'],
    key2:[2,'keyboard'],hover_suppressed2:[2,'keyboard',2],move2:[2,'mouse',2],next_after_move3:[3,'keyboard',2],
    root_reset:[0,'mouse'],root_tab1:[1,'keyboard'],enter_down1:[1,'keyboard'],enter_up1:[1,'keyboard'],
    space_down2:[2,'keyboard'],space_up2:[2,'keyboard'],stale_key_before:[1,'keyboard'],stale_key_after:[1,'keyboard'],
    stale_focus_before:[2,'keyboard'],stale_focus_after:[2,'mouse',2]};
  for(const [name,[focus,modality,hover=0]] of Object.entries(baselines)) {
    assert(captures[name],`${name}: retained baseline capture is required`);
    inspectState(captures[name],{focus,modality,hover});
  }
  for(const [before,after] of [['click3','down2'],['down2','outside_up2'],['click1','enter_down1'],['enter_down1','enter_up1'],
    ['click1','enter_up1'],['click2','space_up2'],['stale_key_before','stale_key_after'],['stale_focus_before','stale_focus_after']])
    assertPanelSame(captures[before],captures[after]);
  assertPanelDifferent(captures.root_tab1,captures.enter_down1);
  assertPanelDifferent(captures.space_down2,captures.space_up2);
  const reject=(name,run)=>{
    let failure;try{run();}catch(error){failure=error.message;}
    assert(failure,`${name}: negative control survived`);
    controls.push({name,rejected:true,failure,input:'Intentionally corrupted independent screenshot/event evidence'});
  };
  const state=(name,focus,modality='keyboard',hover=0)=>inspectState(captures[name],{focus,modality,hover});
  state('initial',0,'mouse');state('tab1',1);state('tab2',2);state('tab3',3);
  reject('wrong_forward_target',()=>state('tab1',2));
  reject('wrong_reverse_order',()=>state('reverse3',2));
  reject('wrong_wrap_target',()=>state('wrap1',3));
  reject('keyboard_ring_missing',()=>state('click2',2,'keyboard',2));
  reject('mouse_ring_shown_for_button2',()=>state('tab2',2,'mouse'));
  reject('both_styles_wrong_precedence',()=>state('click3',3,'keyboard',3));
  const hoverLeak={...captures.hover_suppressed2,data:Uint8Array.from(captures.hover_suppressed2.data)};
  hoverLeak.data.set(COLORS.hover,4*(323*800+50));
  reject('keyboard_hover_not_suppressed',()=>inspectState(hoverLeak,{focus:2,modality:'keyboard',hover:2}));
  reject('mousemove_did_not_change_modality',()=>state('hover_suppressed2',2,'mouse',2));
  reject('mousemove_lost_focus_next_tab_wrong',()=>state('next_after_move3',1));
  const copy=name=>({...captures[name],data:Uint8Array.from(captures[name].data)});
  const narrow=copy('tab2');narrow.data.set(COLORS.blue,4*(320*800+50));
  reject('ring_narrower_than_four_pixels',()=>inspectState(narrow,{focus:2,modality:'keyboard'}));
  const wide=copy('tab2');wide.data.set(COLORS.green,4*(323*800+50));
  reject('ring_wider_than_four_pixels',()=>inspectState(wide,{focus:2,modality:'keyboard'}));
  const shifted=copy('initial');shifted.data.set(COLORS.blue,4*(208*800+31));
  reject('shifted_button_geometry',()=>inspectState(shifted,{focus:0,modality:'mouse'}));
  reject('premature_mouse_activation',()=>assertPanelSame(captures.click3,captures.click2));
  reject('outside_release_activated',()=>assertPanelSame(captures.down2,captures.click2));
  reject('enter_beforeinput_activation_missing',()=>assertPanelDifferent(captures.root_tab1,captures.root_tab1));
  reject('space_down_activated_early',()=>assertPanelSame(captures.space_down2,captures.space_up2));
  reject('stale_other_key_activation',()=>assertPanelSame(captures.stale_key_before,captures.click1));
  reject('stale_focus_generation_activation',()=>assertPanelSame(captures.stale_focus_before,captures.click2));
  reject('activation_message_never_changed',()=>assertPanelDifferent(captures.enter_down1,captures.enter_down1));
  for(const operation of operations)assertDelivery(operation.events,operation.expected);
  const operation=operations.find(operation=>operation.expected.length>1)||operations[0];
  assert(operation,'Actual retained operation evidence is required for delivery controls');
  reject('missing_delivery',()=>assertDelivery([],operation.expected));
  reject('untrusted_delivery',()=>assertDelivery(operation.events.map(event=>({...event,trusted:false})),operation.expected));
  reject('wrong_event_target',()=>assertDelivery(operation.events.map(event=>({...event,target:'BODY'})),operation.expected));
  if(operation.events.length>1)reject('wrong_event_order',()=>assertDelivery([...operation.events].reverse(),operation.expected));
  return controls;
}
