import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {FOCUS_VISIBLE,COLORS,GEOMETRY,inspectState,assertPanelSame,assertPanelDifferent,
  assertUnchanged,assertDelivery,assertProvenance,provenanceNegativeControls,focusVisibleNegativeControls} from './focus-visible-comparator.mjs';

// SYNTHETIC COMPARATOR FIXTURES ONLY: these are neither browser captures nor
// Rust/candidate runtime evidence. Coordinates and colors are independently
// spelled out here so a changed implementation constant cannot change the test
// oracle silently. Artificial ink is not an emulation of either text renderer.
const WIDTH=800,HEIGHT=600;
const ROOT=[243,244,246,255],PANEL=[219,234,254,255],BLUE=[37,99,235,255];
const HOVER=[29,78,216,255],YELLOW=[251,191,36,255],GREEN=[16,185,129,255];
const BUTTONS=[{x:32,y:208,width:736,height:64},{x:32,y:319,width:736,height:64},
  {x:32,y:430,width:736,height:64}];
const PANEL_BOUNDS={x:32,y:95,width:736,height:58};
const copy=image=>({...image,data:image.data.slice()});
function rect(image,x,y,width,height,color) {
  for(let yy=Math.max(0,y);yy<Math.min(image.height,y+height);yy++)
    for(let xx=Math.max(0,x);xx<Math.min(image.width,x+width);xx++)
      image.data.set(color,4*(yy*image.width+xx));
}
function ink(image,x,y,width,color,variant=0) {
  for(let offset=0;offset<width;offset+=7) {
    rect(image,x+offset,y,3,9,color);
    rect(image,x+offset+3,y+2+(variant%3),2,2,color);
  }
}
function fixture({focus=0,modality='mouse',hover=0,message=0,
  rings,ringWidth=4,buttonOffset={x:0,y:0},buttonSize={width:736,height:64},forceHover=false}={}) {
  const image={width:WIDTH,height:HEIGHT,data:new Uint8Array(WIDTH*HEIGHT*4)};
  rect(image,0,0,WIDTH,HEIGHT,ROOT);
  rect(image,32,95,736,58,PANEL);
  ink(image,32,43,245,[17,24,39,255]);
  ink(image,48,116,200+message*7,[30,58,138,255],message);
  for(const [index,b] of BUTTONS.entries()) {
    const ordinal=index+1,x=b.x+buttonOffset.x,y=b.y+buttonOffset.y;
    const {width,height}=buttonSize;
    ink(image,32,b.y-23,250+index*35,[55,65,81,255]);
    const fill=(hover===ordinal&&(modality==='mouse'||forceHover))?HOVER:BLUE;
    let ring=null;
    if(focus===ordinal)ring=ordinal===1?YELLOW:ordinal===2?(modality==='keyboard'?GREEN:null):modality==='keyboard'?GREEN:YELLOW;
    if(rings&&Object.hasOwn(rings,ordinal))ring=rings[ordinal];
    rect(image,x,y,width,height,fill);
    if(ring) {
      rect(image,x,y,width,ringWidth,ring);rect(image,x,y+height-ringWidth,width,ringWidth,ring);
      rect(image,x,y,ringWidth,height,ring);rect(image,x+width-ringWidth,y,ringWidth,height,ring);
    }
    ink(image,190,y+27,340,[255,255,255,255]);
  }
  return image;
}
function recolor(image,before,after) {
  const changed=copy(image);
  for(let p=0;p<changed.data.length;p+=4)
    if(before.every((channel,index)=>changed.data[p+index]===channel))changed.data.set(after,p);
  return changed;
}
const state=(focus=0,modality='mouse',hover=0)=>({focus,modality,hover});

// A fixture validates comparator rejection sensitivity only. Passing this
// source contract cannot certify that the pinned program has been executed.
test('source contract pins the untouched focus_visible example and DPR 1 geometry',()=>{
  assert.equal(FOCUS_VISIBLE.revision,'5a5fbe79917971a4d52a96b6ddb04da198a5012e');
  assert.equal(FOCUS_VISIBLE.source,'crates/gpui/examples/focus_visible.rs');
  assert.equal(FOCUS_VISIBLE.sourceBlob,'c5b3d5dfec3a189d088a621baff55eb55a121b6c');
  assert.equal(FOCUS_VISIBLE.width,WIDTH);assert.equal(FOCUS_VISIBLE.height,HEIGHT);
  assert.equal(FOCUS_VISIBLE.dpr,1);
  for(const [name,color] of Object.entries({root:ROOT,panel:PANEL,blue:BLUE,hover:HOVER,yellow:YELLOW,green:GREEN}))
    assert.deepEqual(COLORS[name],color,`pinned ${name} palette`);
  assert.deepEqual(GEOMETRY.buttons,BUTTONS);assert.deepEqual(GEOMETRY.panel,PANEL_BOUNDS);
});

for(const modality of ['mouse','keyboard'])for(const focus of [0,1,2,3]) {
  test(`synthetic ${modality} focus ${focus}: source-prescribed rings and geometry are accepted`,()=>{
    const image=fixture({focus,modality}),before=copy(image);
    const result=inspectState(image,state(focus,modality));
    assert.equal(result.status,'passed');assert.deepEqual(result.expected,state(focus,modality));
    assert.deepEqual(result.geometry,{panel:PANEL_BOUNDS,buttons:BUTTONS});
    const ring=focus===1?'yellow':focus===2?(modality==='keyboard'?'green':null):focus===3?(modality==='keyboard'?'green':'yellow'):null;
    assert.deepEqual(result.buttons.map(({button,ring,fill})=>({button,ring,fill})),
      [1,2,3].map(button=>({button,ring:button===focus?ring:null,fill:'blue'})));
    assert.deepEqual(image,before,'inspection must not modify the retained pixels');
  });
}

for(const hover of [1,2,3]) {
  test(`synthetic pointer hover ${hover}: only its blue fill changes`,()=>{
    const image=fixture({focus:hover,hover});
    assert.doesNotThrow(()=>inspectState(image,state(hover,'mouse',hover)));
    assert.throws(()=>inspectState(image,state(hover,'mouse',0)));
    assert.throws(()=>inspectState(fixture({focus:hover}),state(hover,'mouse',hover)));
  });
  test(`synthetic keyboard focus ${hover}: pointer hover remains suppressed`,()=>{
    const image=fixture({focus:hover,modality:'keyboard',hover});
    assert.doesNotThrow(()=>inspectState(image,state(hover,'keyboard',hover)));
    assert.throws(()=>inspectState(fixture({focus:hover,modality:'keyboard',hover,forceHover:true}),state(hover,'keyboard',hover)));
  });
}

test('each focused ring must belong to the expected button, including keyboard wrap and reverse destinations',()=>{
  for(const [actual,expected] of [[1,2],[2,3],[3,1],[3,2],[2,1],[1,3]])
    assert.throws(()=>inspectState(fixture({focus:actual,modality:'keyboard'}),state(expected,'keyboard')));
});

test('regular focus stays yellow; focus-visible is keyboard-only; keyboard green overrides combined yellow',()=>{
  for(const [options,expected] of [
    [{focus:1,rings:{1:null}},state(1)],
    [{focus:1,rings:{1:GREEN}},state(1)],
    [{focus:1,modality:'keyboard',rings:{1:GREEN}},state(1,'keyboard')],
    [{focus:2,rings:{2:GREEN}},state(2)],
    [{focus:2,modality:'keyboard',rings:{2:null}},state(2,'keyboard')],
    [{focus:2,modality:'keyboard',rings:{2:YELLOW}},state(2,'keyboard')],
    [{focus:3,rings:{3:GREEN}},state(3)],
    [{focus:3,modality:'keyboard',rings:{3:YELLOW}},state(3,'keyboard')],
    [{rings:{1:YELLOW}},state()],
    [{focus:1,rings:{2:GREEN}},state(1)],
  ])assert.throws(()=>inspectState(fixture(options),expected));
});

for(const ringWidth of [1,2,3,5,8])test(`reject a ${ringWidth}px focus ring instead of exactly 4px`,()=>{
  assert.throws(()=>inspectState(fixture({focus:1,ringWidth}),state(1)));
  assert.throws(()=>inspectState(fixture({focus:3,modality:'keyboard',ringWidth}),state(3,'keyboard')));
});

for(const [name,options] of [
  ['shifted right',{buttonOffset:{x:1,y:0}}],['shifted down',{buttonOffset:{x:0,y:1}}],
  ['narrowed',{buttonSize:{width:735,height:64}}],['shortened',{buttonSize:{width:736,height:63}}],
  ['widened',{buttonSize:{width:737,height:64}}],['taller',{buttonSize:{width:736,height:65}}],
])test(`reject ${name} source geometry`,()=>assert.throws(()=>inspectState(fixture(options),state())));

for(const [name,color,replacement,options] of [
  ['root',ROOT,[242,244,246,255],{}],['panel',PANEL,[219,234,253,255],{}],
  ['button',BLUE,[37,100,235,255],{}],['hover',HOVER,[28,78,216,255],{hover:2}],
  ['yellow ring',YELLOW,[250,191,36,255],{focus:1}],
  ['green ring',GREEN,[16,184,129,255],{focus:2,modality:'keyboard'}],
])test(`reject a one-channel wrong ${name} palette`,()=>{
  assert.throws(()=>inspectState(recolor(fixture(options),color,replacement),state(options.focus||0,options.modality||'mouse',options.hover||0)));
});

test('reject malformed, cropped, truncated, transparent, blank, and DPR 2 images',()=>{
  const good=fixture();
  for(const image of [null,{}, {...good,width:799},{...good,height:599},
    {...good,data:good.data.slice(0,-1)}, {...good,data:good.data.slice(0,-4)},
    {...good,data:new Uint8Array(good.data.length+4)},
    {...good,data:new Uint8Array(good.data.length)},
    {width:1600,height:1200,data:new Uint8Array(1600*1200*4)},
    recolor(good,ROOT,[...ROOT.slice(0,3),254]),
  ])assert.throws(()=>inspectState(image,state()));
});

test('panel equality ignores independent focus/hover changes but requires every retained panel pixel',()=>{
  const initial=fixture(),focused=fixture({focus:3,modality:'keyboard'}),hovered=fixture({hover:2});
  assert.doesNotThrow(()=>assertPanelSame(initial,focused));
  assert.doesNotThrow(()=>assertPanelSame(initial,hovered));
  const changed=copy(initial);changed.data[4*(120*WIDTH+70)]^=1;
  assert.throws(()=>assertPanelSame(initial,changed));
  assert.throws(()=>assertPanelDifferent(initial,changed),'one corrupted pixel is not a meaningful message change');
  assert.throws(()=>assertPanelDifferent(initial,focused));
});

test('activation needs a real message-panel change; rings, hover, and title changes cannot substitute',()=>{
  const initial=fixture(),activated=fixture({focus:1,hover:1,message:1});
  assert.doesNotThrow(()=>assertPanelDifferent(initial,activated));
  for(const unchanged of [copy(initial),fixture({focus:1}),fixture({hover:1})])
    assert.throws(()=>assertPanelDifferent(initial,unchanged));
  const titleChanged=copy(initial);titleChanged.data[4*(43*WIDTH+32)]^=1;
  assert.throws(()=>assertPanelDifferent(initial,titleChanged));
});

test('press-down and outside-release evidence reject early or unintended message activation',()=>{
  const before=fixture({focus:1,message:1});
  const down=fixture({focus:2,hover:2,message:1});
  const outsideUp=fixture({focus:2,message:1});
  assert.doesNotThrow(()=>assertPanelSame(before,down));
  assert.doesNotThrow(()=>assertPanelSame(down,outsideUp));
  assert.throws(()=>assertPanelSame(before,fixture({focus:2,hover:2,message:2})));
  assert.throws(()=>assertPanelSame(down,fixture({focus:2,message:2})));
});

test('stale key and stale focus captures cannot mutate the retained message or full image',()=>{
  for(const options of [{focus:2,modality:'keyboard',message:2},{focus:3,message:3}]) {
    const before=fixture(options),after=copy(before);
    assert.doesNotThrow(()=>assertUnchanged(before,after));
    assert.doesNotThrow(()=>assertPanelSame(before,after));
    assert.throws(()=>assertUnchanged(before,fixture({...options,message:options.message+1})));
    assert.throws(()=>assertPanelSame(before,fixture({...options,message:options.message+1})));
  }
});

test('full-image equality includes alpha and the last physical pixel, without masks',()=>{
  const before=fixture();assert.doesNotThrow(()=>assertUnchanged(before,copy(before)));
  for(const offset of [0,3,4*(43*WIDTH+32),before.data.length-1]) {
    const after=copy(before);after.data[offset]^=1;
    assert.throws(()=>assertUnchanged(before,after));
  }
  assert.throws(()=>assertUnchanged(before,{...before,data:before.data.slice(0,-4)}));
  assert.throws(()=>assertPanelSame(before,{...before,width:799}));
  assert.throws(()=>assertPanelDifferent(before,{...before,height:599}));
});

const keyEvent=(type,key='Tab',code='Tab',extra={})=>({type,key,code,trusted:true,target:'TEXTAREA',
  shiftKey:false,ctrlKey:false,altKey:false,metaKey:false,repeat:false,...extra});
const pointerEvent=(type='pointerdown',extra={})=>({type,trusted:true,target:'CANVAS',pointerType:'mouse',
  x:100,y:240,button:0,...extra});
const keyExpected=(type,key='Tab',code='Tab',extra={})=>({type,key,code,shiftKey:false,
  ctrlKey:false,altKey:false,metaKey:false,...extra});

test('trusted keyboard delivery records the exact keydown/keyup order and requested modifiers',()=>{
  const events=[keyEvent('keydown'),keyEvent('keyup')];
  const expected=[keyExpected('keydown'),keyExpected('keyup')];
  const before=structuredClone({events,expected});
  assert.equal(assertDelivery(events,expected).status,'passed');
  assert.deepEqual({events,expected},before,'delivery validation must not rewrite evidence');
  const shifted=[keyEvent('keydown','Tab','Tab',{shiftKey:true}),keyEvent('keyup','Tab','Tab',{shiftKey:true})];
  assert.equal(assertDelivery(shifted,expected.map(e=>({...e,shiftKey:true}))).status,'passed');
  assert.equal(assertDelivery(events.map(e=>({...e,target:'CANVAS'})),expected).status,'passed');
  for(const [key,code] of [['Enter','Enter'],[' ','Space']])
    assert.equal(assertDelivery([keyEvent('keydown',key,code),keyEvent('keyup',key,code)],
      [keyExpected('keydown',key,code),keyExpected('keyup',key,code)]).status,'passed');
});

test('delivery rejects missing, extra, duplicate, reversed, and substituted keyboard events',()=>{
  const down=keyEvent('keydown'),up=keyEvent('keyup');
  const expected=[keyExpected('keydown'),keyExpected('keyup')];
  for(const events of [[],[down],[up],[up,down],[down,down],[down,up,up],
    [keyEvent('keydown','Enter','Enter'),up],[down,keyEvent('keyup','Tab','Enter')],
    [pointerEvent(),up],
  ])assert.throws(()=>assertDelivery(events,expected));
});

for(const [name,change] of [
  ['untrusted',{trusted:false}],['missing trust',{trusted:undefined}],['wrong target',{target:'BODY'}],
  ['wrong key',{key:'Enter'}],['wrong code',{code:'Enter'}],['unexpected Shift',{shiftKey:true}],
  ['unexpected Control',{ctrlKey:true}],['unexpected Alt',{altKey:true}],['unexpected Meta',{metaKey:true}],
])test(`reject ${name} keyboard evidence`,()=>{
  const events=[keyEvent('keydown','Tab','Tab',change),keyEvent('keyup')];
  assert.throws(()=>assertDelivery(events,[keyExpected('keydown'),keyExpected('keyup')]));
});

test('only explicitly requested event fields are matched; event count and sequence are always exact',()=>{
  const event=keyEvent('keydown','Enter','Enter',{time:1234,repeat:true});
  assert.equal(assertDelivery([event],[{type:'keydown',key:'Enter',code:'Enter'}]).status,'passed');
  assert.throws(()=>assertDelivery([event],[{type:'keydown',repeat:false}]));
  assert.throws(()=>assertDelivery([event,keyEvent('keyup','Enter','Enter')],[{type:'keydown'}]));
  assert.throws(()=>assertDelivery([event],[{key:'Enter'}]));
  assert.throws(()=>assertDelivery([],[]));
});

test('trusted mouse pointer evidence requires canvas targeting and exact requested positions/buttons',()=>{
  const events=[pointerEvent('pointermove'),pointerEvent('pointerdown'),pointerEvent('pointerup')];
  const expected=events.map(({type,x,y,button})=>({type,x,y,button}));
  assert.equal(assertDelivery(events,expected).status,'passed');
  for(const change of [{trusted:false},{target:'BODY'},{pointerType:'pen'},{pointerType:undefined},
    {x:99},{y:239},{button:2}]) {
    const altered=events.map(e=>({...e}));altered[1]={...altered[1],...change};
    assert.throws(()=>assertDelivery(altered,expected));
  }
  assert.throws(()=>assertDelivery([events[0],events[2],events[1]],expected));
  assert.throws(()=>assertDelivery(events.slice(1),expected));
});

test('trusted wheel delivery requires canvas, pixel mode, prevented default, and requested deltas',()=>{
  const event={type:'wheel',trusted:true,target:'CANVAS',x:8,y:300,deltaX:0,deltaY:1,
    deltaMode:0,defaultPrevented:true};
  const expected=[{type:'wheel',x:8,y:300,deltaX:0,deltaY:1}];
  assert.equal(assertDelivery([event],expected).status,'passed');
  for(const change of [{trusted:false},{target:'BODY'},{deltaMode:1},{defaultPrevented:false},
    {deltaX:1},{deltaY:0},{x:9},{y:301}])assert.throws(()=>assertDelivery([{...event,...change}],expected));
  assert.throws(()=>assertDelivery([],expected));
});

test('empty title, panel message, section labels, or button labels cannot certify a blank fixture',()=>{
  for(const [name,bounds,color] of [
    ['heading',{x:32,y:32,width:736,height:39},ROOT],
    ['message',{x:48,y:111,width:704,height:26},PANEL],
    ...[177,288,399].map((y,index)=>[`section ${index+1}`,{x:32,y,width:736,height:23},ROOT]),
    ...BUTTONS.map((b,index)=>[`button ${index+1}`,{x:40,y:b.y+8,width:720,height:48},BLUE]),
  ]) {
    const image=fixture();rect(image,bounds.x,bounds.y,bounds.width,bounds.height,color);
    assert.throws(()=>inspectState(image,state()),`${name} must contain independently observable ink`);
  }
});


test('message activation threshold counts changed pixels rather than changed channels',()=>{
  const before=fixture();
  for(const count of [1,19,20]) {
    const after=copy(before);
    rect(after,500,120,count,1,[0,0,0,255]);
    if(count<20)assert.throws(()=>assertPanelDifferent(before,after));
    else assert.equal(assertPanelDifferent(before,after).changed_pixels,20);
  }
});

function captureFixtures() {
  const specs={
    initial:{focus:0,modality:'mouse',hover:0,message:0},
    tab1:{focus:1,modality:'keyboard',hover:0,message:4},
    tab2:{focus:2,modality:'keyboard',hover:0,message:4},
    tab3:{focus:3,modality:'keyboard',hover:0,message:4},
    wrap1:{focus:1,modality:'keyboard',hover:0,message:4},
    reverse3:{focus:3,modality:'keyboard',hover:0,message:5},
    reverse2:{focus:2,modality:'keyboard',hover:0,message:5},
    reverse1:{focus:1,modality:'keyboard',hover:0,message:5},
    reverse_wrap3:{focus:3,modality:'keyboard',hover:0,message:5},
    click1:{focus:1,modality:'mouse',hover:1,message:1},
    click2:{focus:2,modality:'mouse',hover:2,message:2},
    click3:{focus:3,modality:'mouse',hover:3,message:3},
    down2:{focus:2,modality:'mouse',hover:2,message:3},
    outside_up2:{focus:2,modality:'mouse',hover:0,message:3},
    key2:{focus:2,modality:'keyboard',hover:0,message:3},
    hover_suppressed2:{focus:2,modality:'keyboard',hover:2,message:3},
    move2:{focus:2,modality:'mouse',hover:2,message:3},
    next_after_move3:{focus:3,modality:'keyboard',hover:2,message:4},
    root_reset:{focus:0,modality:'mouse',hover:0,message:4},
    root_tab1:{focus:1,modality:'keyboard',hover:0,message:4},
    enter_down1:{focus:1,modality:'keyboard',hover:0,message:4},
    enter_up1:{focus:1,modality:'keyboard',hover:0,message:1},
    space_down2:{focus:2,modality:'keyboard',hover:0,message:4},
    space_up2:{focus:2,modality:'keyboard',hover:0,message:2},
    stale_key_before:{focus:1,modality:'keyboard',hover:0,message:4},
    stale_key_after:{focus:1,modality:'keyboard',hover:0,message:4},
    stale_focus_before:{focus:2,modality:'keyboard',hover:0,message:4},
    stale_focus_after:{focus:2,modality:'mouse',hover:2,message:4},
  };
  return {specs,captures:Object.fromEntries(Object.entries(specs).map(([name,options])=>[name,fixture(options)]))};
}
function operationFixtures() {
  return [{name:'synthetic_tab_transport',events:[keyEvent('keydown'),keyEvent('keyup')],
    expected:[keyExpected('keydown'),keyExpected('keyup')]},
    {name:'synthetic_click_transport',events:[pointerEvent('pointerdown'),pointerEvent('pointerup')],
      expected:[{type:'pointerdown',x:100,y:240,button:0},{type:'pointerup',x:100,y:240,button:0}]}];
}
const fingerprint=captures=>Object.fromEntries(Object.entries(captures)
  .map(([name,image])=>[name,createHash('sha256').update(image.data).digest('hex')]));

test('all retained-capture negative controls reject intentional synthetic corruptions without altering evidence',()=>{
  const {specs,captures}=captureFixtures(),operations=operationFixtures();
  // Independently validate every fixture before asking deliberately wrong
  // questions of it: missing or invalid fixtures must never count as rejection.
  for(const [name,options] of Object.entries(specs))
    assert.equal(inspectState(captures[name],options).status,'passed',name);
  const before=fingerprint(captures),operationsBefore=structuredClone(operations);
  const controls=focusVisibleNegativeControls(captures,operations);
  const expectedNames=[
    'wrong_forward_target','wrong_reverse_order','wrong_wrap_target','keyboard_ring_missing',
    'mouse_ring_shown_for_button2','both_styles_wrong_precedence','keyboard_hover_not_suppressed',
    'mousemove_did_not_change_modality','mousemove_lost_focus_next_tab_wrong',
    'ring_narrower_than_four_pixels','ring_wider_than_four_pixels','shifted_button_geometry',
    'premature_mouse_activation','outside_release_activated','enter_down_activated_early',
    'space_down_activated_early','stale_other_key_activation','stale_focus_generation_activation',
    'activation_message_never_changed','missing_delivery','untrusted_delivery','wrong_event_target','wrong_event_order',
  ];
  assert.deepEqual(controls.map(control=>control.name),expectedNames);
  assert(controls.every(control=>control.rejected===true&&typeof control.failure==='string'&&control.failure.length>0));
  assert.deepEqual(fingerprint(captures),before,'corruption controls must use copies of retained capture pixels');
  assert.deepEqual(operations,operationsBefore,'corruption controls must preserve retained delivery evidence');
});

test('negative controls require valid baseline captures and delivered operation evidence',()=>{
  const {captures}=captureFixtures();
  assert.throws(()=>focusVisibleNegativeControls({...captures,initial:fixture({focus:1})},operationFixtures()));
  for(const name of ['initial','reverse3','click2','enter_up1','stale_key_before']) {
    const incomplete={...captures};delete incomplete[name];
    assert.throws(()=>focusVisibleNegativeControls(incomplete,operationFixtures()),`${name}: missing evidence is not a negative-control success`);
  }
  assert.throws(()=>focusVisibleNegativeControls(captures,[]));
  const operations=operationFixtures();operations[1].events[0].trusted=false;
  assert.throws(()=>focusVisibleNegativeControls(captures,operations));
});


test('unsupported focus, modality, and hover expectations are rejected rather than inferred',()=>{
  const image=fixture();
  for(const options of [{focus:-1,modality:'mouse'},{focus:4,modality:'mouse'},
    {focus:'1',modality:'mouse'},{focus:0,modality:'touch'},{focus:0},
    {focus:0,modality:'mouse',hover:4},{focus:0,modality:'mouse',hover:'1'}])
    assert.throws(()=>inspectState(image,options));
});

test('extra control or ring-colored pixels outside source geometry are rejected',()=>{
  for(const color of [BLUE,HOVER,YELLOW,GREEN]) {
    const image=fixture();rect(image,100,550,1,1,color);
    assert.throws(()=>inspectState(image,state()));
  }
});


// These hashes and records are synthetic, including all build identities. They
// exercise evidence validation and must never be presented as a recorded build.
const syntheticDigest=label=>createHash('sha256').update(`synthetic provenance fixture: ${label}`).digest('hex');
function provenanceFixture() {
  const upstream={repo:'https://github.com/zed-industries/zed',revision:'5a5fbe79917971a4d52a96b6ddb04da198a5012e'};
  const moonbit={repo:'https://example.invalid/synthetic-candidate',revision:'a'.repeat(40)};
  const record={id:'focus_visible',source:'crates/gpui/examples/focus_visible.rs',
    source_blob:'c5b3d5dfec3a189d088a621baff55eb55a121b6c',
    upstream_revision:'5a5fbe79917971a4d52a96b6ddb04da198a5012e',
    width:800,height:600,dpr:1,status:'rust_oracle_only',candidate:'not_implemented'};
  const manifest={upstream:structuredClone(upstream),moonbit:structuredClone(moonbit),
    lab_revision:'b'.repeat(40),lab_tracked_dirty:false,rust_bundled:true,
    implemented:['tree'],rust_implemented:['tree','focus_visible'],rust_oracle_only:[record],
    rust:{source_modified:false,packaging:{upstream_files_modified:false},files:{
      'focus_visible.js':syntheticDigest('bindings'),
      'focus_visible_bg.wasm':syntheticDigest('wasm'),
      'host.mjs':syntheticDigest('host'),
    }}};
  const catalog={upstream,moonbit,examples:[{id:'tree',moonbit:'implemented'},
    {id:'focus_visible',moonbit:'not_implemented'}]};
  return {manifest,catalog};
}

test('synthetic provenance accepts only a clean, unchanged, explicitly Rust-only source record',()=>{
  const {manifest,catalog}=provenanceFixture(),before=structuredClone({manifest,catalog});
  const record=assertProvenance(manifest,catalog);
  assert.deepEqual(record,manifest.rust_oracle_only[0]);
  assert.equal(record.status,'rust_oracle_only');assert.equal(record.candidate,'not_implemented');
  assert.deepEqual({manifest,catalog},before);
});

for(const [name,mutate] of [
  ['dirty tracked source',m=>m.lab_tracked_dirty=true],
  ['missing clean-source flag',m=>delete m.lab_tracked_dirty],
  ['missing lab revision',m=>delete m.lab_revision],
  ['non-SHA lab revision',m=>m.lab_revision='working-tree'],
  ['short lab revision',m=>m.lab_revision='a'.repeat(39)],
  ['wrong upstream revision',m=>m.upstream.revision='c'.repeat(40)],
  ['missing bundled Rust',m=>m.rust_bundled=false],
  ['changed upstream source',m=>m.rust.source_modified=true],
  ['missing unchanged-source flag',m=>delete m.rust.source_modified],
  ['changed upstream archive',m=>m.rust.packaging.upstream_files_modified=true],
  ['missing archive-preservation flag',m=>delete m.rust.packaging.upstream_files_modified],
  ['missing Rust implementation',m=>m.rust_implemented=['tree']],
  ['missing source record',m=>m.rust_oracle_only=[]],
  ['duplicate source records',m=>m.rust_oracle_only.push(structuredClone(m.rust_oracle_only[0]))],
  ['wrong source path',m=>m.rust_oracle_only[0].source='crates/gpui/examples/tree.rs'],
  ['wrong source blob',m=>m.rust_oracle_only[0].source_blob='c'.repeat(40)],
  ['wrong source revision',m=>m.rust_oracle_only[0].upstream_revision='c'.repeat(40)],
  ['wrong source width',m=>m.rust_oracle_only[0].width=799],
  ['wrong source height',m=>m.rust_oracle_only[0].height=599],
  ['wrong source DPR',m=>m.rust_oracle_only[0].dpr=2],
  ['paired status claim',m=>m.rust_oracle_only[0].status='paired_profile'],
  ['candidate source-record claim',m=>m.rust_oracle_only[0].candidate='implemented'],
  ['compiled candidate claim',m=>m.implemented.push('focus_visible')],
])test(`reject synthetic provenance with ${name}`,()=>{
  const {manifest,catalog}=provenanceFixture();mutate(manifest);
  assert.throws(()=>assertProvenance(manifest,catalog));
});

for(const file of ['focus_visible.js','focus_visible_bg.wasm','host.mjs'])
  for(const [name,value] of [['missing',undefined],['short','a'.repeat(63)],['nonhex','z'.repeat(64)]])
    test(`reject ${name} ${file} runtime hash`,()=>{
      const {manifest,catalog}=provenanceFixture();
      if(value===undefined)delete manifest.rust.files[file];else manifest.rust.files[file]=value;
      assert.throws(()=>assertProvenance(manifest,catalog));
    });

test('catalog identity cannot disagree with the retained manifest or imply a candidate implementation',()=>{
  for(const mutate of [c=>c.upstream.revision='c'.repeat(40),c=>c.moonbit.revision='c'.repeat(40),
    c=>c.examples.find(e=>e.id==='focus_visible').moonbit='implemented']) {
    const {manifest,catalog}=provenanceFixture();mutate(catalog);
    assert.throws(()=>assertProvenance(manifest,catalog));
  }
  const {manifest,catalog}=provenanceFixture();
  manifest.upstream.revision='c'.repeat(40);catalog.upstream.revision='c'.repeat(40);
  assert.throws(()=>assertProvenance(manifest,catalog),'two matching wrong pins cannot weaken the exact upstream contract');
});

test('all seven provenance corruption controls reject and preserve original synthetic evidence',()=>{
  const {manifest,catalog}=provenanceFixture(),before=structuredClone({manifest,catalog});
  const controls=provenanceNegativeControls(manifest,catalog);
  assert.deepEqual(controls.map(c=>c.name),['dirty_lab','wrong_upstream','modified_source','modified_archive',
    'wrong_example_blob','missing_runtime_hash','candidate_claim']);
  assert(controls.every(c=>c.rejected===true));
  assert.deepEqual({manifest,catalog},before);
  manifest.lab_tracked_dirty=true;
  assert.throws(()=>provenanceNegativeControls(manifest,catalog),'a failed baseline is not valid negative-control evidence');
});
