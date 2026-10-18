import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';

// Geometry and behavior follow the unchanged pinned example and GPUI internals.
// This module consumes actual screenshots. It does not represent Rust scroll state.
export const SCROLLABLE = Object.freeze({width:500,height:500,step:12,
  revision:'5a5fbe79917971a4d52a96b6ddb04da198a5012e',
  source:'crates/gpui/examples/scrollable.rs',sourceBlob:'c81795618875aecf06e06043bd1709c48630b58f'});
export const SOURCE_CONSTRAINTS = Object.freeze([
  'scrollable.rs:13-45: p4, 5000px blue body, 2000x150px green child, both-axis overflow and hover',
  'gpui/src/elements/div.rs:2457-2485: padding-aware maximum and prepaint clamping',
  'gpui/src/elements/div.rs:3331-3385: dominant-axis wheel handling; no propagation stop',
  'gpui/src/elements/div.rs:2845-2868,3460-3480; window.rs:4470-4495: anonymous hover has no move-only notify; real wheel redraw applies current hitbox hover',
  'gpui/src/window.rs:1173-1194,4172-4208: clipped hit testing, intersected masks and descendant translations',
  'gpui_web/src/events.rs:641-671: preventDefault and negated browser pixel deltas',
  'gpui_web/src/window.rs:107-147: full-host canvas; requested native window bounds are ignored',
]);
const GREEN=[0,128,0,255],BLUE=[0,0,255,255],WHITE=[255,255,255,255];
const digest=data=>createHash('sha256').update(data).digest('hex');
const equalColor=(a,b)=>a.every((v,i)=>v===b[i]);

export function assertImage(image,dpr=1) {
  assert([1,2].includes(dpr),'Only integer DPR 1 and 2 are supported');
  assert.equal(image.width,500*dpr,'Full 500 CSS-pixel image width required');
  assert.equal(image.height,500*dpr,'Full 500 CSS-pixel image height required');
  assert.equal(image.data.length,image.width*image.height*4,'Complete RGBA pixels required');
}
export function pixel(image,x,y) {
  assert(Number.isInteger(x)&&Number.isInteger(y)&&x>=0&&y>=0&&x<image.width&&y<image.height,'Pixel is inside full image');
  const offset=4*(y*image.width+x);return Array.from(image.data.subarray(offset,offset+4));
}
function scan(image,rect,predicate) {
  const points=[];
  for(let y=Math.max(0,Math.ceil(rect.y));y<Math.min(image.height,rect.y+rect.height);y++)
    for(let x=Math.max(0,Math.ceil(rect.x));x<Math.min(image.width,rect.x+rect.width);x++)
      if(predicate(pixel(image,x,y)))points.push([x,y]);
  if(!points.length)return null;
  let left=Infinity,top=Infinity,right=-1,bottom=-1;
  for(const [x,y] of points){left=Math.min(left,x);top=Math.min(top,y);right=Math.max(right,x);bottom=Math.max(bottom,y);}
  return {bounds:{x:left,y:top,width:right-left+1,height:bottom-top+1},pixels:points.length,
    shape_sha256:digest(JSON.stringify(points.map(([x,y])=>[x-left,y-top])))};
}
const whole=image=>({x:0,y:0,width:image.width,height:image.height});
const neutral=p=>p[3]===255&&p[0]<96&&p[1]<96&&p[2]<96;
const scaled=(r,dpr)=>Object.fromEntries(Object.entries(r).map(([k,v])=>[k,v*dpr]));
const unscaled=(r,dpr)=>Object.fromEntries(Object.entries(r).map(([k,v])=>[k,v/dpr]));
function paletteBounds(image,color) {return scan(image,whole(image),p=>equalColor(p,color))?.bounds;}
function textFeatures(image,geometry,dy,dpr) {
  const top=geometry.green.y+dy,bottom=top+geometry.green.height;
  const regions={heading:{x:0,y:0,width:500,height:geometry.blue.y+dy},
    horizontal:{x:geometry.green.x,y:top,width:geometry.green.width,height:geometry.green.height},
    vertical:{x:17,y:bottom,width:466,height:500-bottom}};
  return Object.fromEntries(Object.entries(regions).map(([name,r])=>{
    const feature=scan(image,scaled(r,dpr),neutral);
    assert(feature&&feature.pixels>=20*dpr*dpr,`${name}: a nonempty, measurable neutral-ink feature is required`);
    return [name,feature];
  }));
}
export function inspectInitial(image,dpr=1) {
  assertImage(image,dpr);
  const greenPhysical=paletteBounds(image,GREEN),bluePhysical=paletteBounds(image,BLUE);
  assert(greenPhysical&&bluePhysical,'Actual opaque green and blue borders are required');
  const green=unscaled(greenPhysical,dpr),blue=unscaled(bluePhysical,dpr);
  assert.deepEqual({x:blue.x,width:blue.width},{x:16,width:468},'Root p4 and blue body width');
  assert.deepEqual({x:green.x,width:green.width,height:green.height},{x:33,width:434,height:150},'Nested border, padding, 150px height and clipped width');
  assert.equal(green.y,blue.y+17,'Inner top follows blue border and padding');
  assert(blue.y>=32&&blue.y<=80,'Heading has a bounded single-line layout');
  assert.equal(blue.y+blue.height,500,'Initial tall blue body reaches root clip bottom');
  assert.deepEqual(pixel(image,0,0),WHITE,'Full white root background');
  const geometry={green,blue};const features=textFeatures(image,geometry,0,dpr);
  assert(features.heading.bounds.y>12*dpr,'Small vertical step must not clip the heading ink');
  assert(features.horizontal.bounds.x-green.x*dpr>12*dpr,'Small horizontal step must not clip label ink');
  return {geometry,features,observed:'opaque border bounds and neutral-ink features from full screenshot'};
}
export function assertTranslation(before,after,initial,{beforeX=0,beforeY=0,afterX=0,afterY=0}={},dpr=1) {
  assertImage(before,dpr);assertImage(after,dpr);
  const a=textFeatures(before,initial.geometry,beforeY,dpr),b=textFeatures(after,initial.geometry,afterY,dpr);
  const deltas={};
  for(const name of Object.keys(a)) {
    const dx=(name==='horizontal'?afterX-beforeX:0)*dpr,dy=(afterY-beforeY)*dpr;
    assert.deepEqual(b[name].bounds,{...a[name].bounds,x:a[name].bounds.x+dx,y:a[name].bounds.y+dy},`${name}: observed ink translation`);
    assert.equal(b[name].pixels,a[name].pixels,`${name}: preserve ink population`);
    assert.equal(b[name].shape_sha256,a[name].shape_sha256,`${name}: preserve translated ink shape`);
    deltas[name]={dx:dx/dpr,dy:dy/dpr,before:a[name],after:b[name]};
  }
  const green=unscaled(paletteBounds(after,GREEN),dpr),blue=unscaled(paletteBounds(after,BLUE),dpr);
  assert.deepEqual(green,{...initial.geometry.green,y:initial.geometry.green.y+afterY},'Inner clip stays fixed in X while its child translates');
  assert.equal(blue.x,initial.geometry.blue.x);assert.equal(blue.width,initial.geometry.blue.width);
  assert.equal(blue.y,initial.geometry.blue.y+afterY,'Outer top border translates vertically');
  return {status:'passed',measurement:'screenshot feature displacement in CSS pixels',deltas};
}
export function assertUnchanged(before,after,dpr=1) {
  assertImage(before,dpr);assertImage(after,dpr);
  assert.equal(digest(before.data),digest(after.data),'Complete rendered image must remain unchanged');
  return {status:'passed',checked_pixels:before.width*before.height,rgba_sha256:digest(after.data)};
}
function assertSolid(image,rect,color,dpr,label) {
  const r=scaled(rect,dpr);let checked=0;
  for(let y=r.y;y<r.y+r.height;y++)for(let x=r.x;x<r.x+r.width;x++) {
    assert.deepEqual(pixel(image,x,y),color,`${label}: pixel ${x},${y}`);checked++;
  }
  return checked;
}
export function assertClipping(reference,image,initial,dpr=1) {
  assertImage(reference,dpr);assertImage(image,dpr);const g=initial.geometry.green;
  let checked=0;
  for(const rect of [{x:17,y:g.y+40,width:16,height:70},{x:g.x+g.width,y:g.y+40,width:16,height:70}]) {
    const r=scaled(rect,dpr);
    for(let y=r.y;y<r.y+r.height;y++)for(let x=r.x;x<r.x+r.width;x++) {
      assert.deepEqual(pixel(image,x,y),pixel(reference,x,y),`Clipped outside strip changed at ${x},${y}`);checked++;
    }
  }
  return {status:'passed',checked_outside_pixels:checked,measurement:'Retained blue padding strips outside inner viewport'};
}
function probeFill(image,initial,dpr) {
  const g=initial.geometry.green,r={x:g.x+g.width-40,y:g.y+70,width:5,height:5};
  const color=pixel(image,r.x*dpr,r.y*dpr);assertSolid(image,r,color,dpr,'Uniform green fill probe');return color;
}
export function assertHover(unhovered,hovered,initial,dpr=1) {
  assertImage(unhovered,dpr);assertImage(hovered,dpr);
  const a=probeFill(unhovered,initial,dpr),b=probeFill(hovered,initial,dpr);
  assert(a[0]-b[0]>=5&&a[2]-b[2]>=5,'Hover must visibly increase green fill against the pale background');
  assert.equal(a[3],255);assert.equal(b[3],255);
  return {status:'passed',unhovered_rgba:a,hovered_rgba:b,measurement:'Actual uniform interior fill patch'};
}
export function assertSameFill(a,b,initial,dpr=1) {
  const before=probeFill(a,initial,dpr),after=probeFill(b,initial,dpr);
  assert.deepEqual(after,before,'Clipped-off pointer must leave the visible child unhovered');
  return {status:'passed',rgba:after};
}
export function assertHorizontalEnd(image,initial,dpr=1) {
  assertImage(image,dpr);const g=initial.geometry.green;
  const checked=assertSolid(image,{x:g.x+g.width-1,y:g.y+20,width:1,height:110},GREEN,dpr,'Horizontal endpoint right border');
  assert.equal(scan(image,scaled(g,dpr),neutral),null,'Horizontal label is offscreen at the right endpoint');
  return {status:'passed',right_border_x:g.x+g.width-1,checked_border_pixels:checked};
}
export function assertVerticalEnd(image,dpr=1) {
  assertImage(image,dpr);
  const border=assertSolid(image,{x:16,y:483,width:468,height:1},BLUE,dpr,'Vertical endpoint bottom border');
  const padding=assertSolid(image,{x:0,y:484,width:500,height:16},WHITE,dpr,'Vertical endpoint root bottom padding');
  assert.equal(scan(image,whole(image),neutral),null,'All labels are above the viewport at vertical endpoint');
  assert.equal(paletteBounds(image,GREEN),undefined,'Green child is above the viewport at vertical endpoint');
  return {status:'passed',bottom_border_y:483,checked_border_pixels:border,checked_padding_pixels:padding};
}
export function assertWheelDelivery(events,{deltaX,deltaY,x,y}) {
  assert(events.length>0,'A delivered wheel event is required');
  for(const event of events) {
    assert.equal(event.trusted,true,'Trusted browser wheel delivery');assert.equal(event.target,'CANVAS');
    assert.equal(event.deltaMode,0,'Pixel wheel mode');assert.equal(event.defaultPrevented,true,'GPUI web wheel listener prevented browser scrolling');
    assert.equal(event.x,x);assert.equal(event.y,y);
  }
  assert.equal(events.reduce((n,e)=>n+e.deltaX,0),deltaX,'Delivered X delta');
  assert.equal(events.reduce((n,e)=>n+e.deltaY,0),deltaY,'Delivered Y delta');
  return {status:'passed',events};
}

// Deliberately corrupted COPIES prove comparator rejection, not engine mutation
// coverage. They never replace retained screenshots or count as Rust execution.
export function scrollableNegativeControls(captures,initial,dpr=1) {
  const controls=[];
  const reject=(name,fn)=>{let rejected=false;try{fn();}catch{rejected=true;}assert(rejected,`${name}: negative control survived`);controls.push({name,rejected,input:'intentionally corrupted screenshot/event evidence'});};
  assertTranslation(captures.initial_hover,captures.x12,initial,{afterX:-12},dpr);
  assertTranslation(captures.x12,captures.y12,initial,{beforeX:-12,afterX:-12,afterY:-12},dpr);
  reject('no_horizontal_movement',()=>assertTranslation(captures.initial_hover,captures.initial_hover,initial,{afterX:-12},dpr));
  reject('wrong_scroll_axis',()=>assertTranslation(captures.initial_hover,captures.x12,initial,{afterY:-12},dpr));
  reject('no_vertical_propagation',()=>assertTranslation(captures.x12,captures.x12,initial,{beforeX:-12,afterX:-12,afterY:-12},dpr));
  const bad={...captures.x12_unhover,data:captures.x12_unhover.data.slice()};
  bad.data.set(GREEN,4*((initial.geometry.green.y+50)*dpr*bad.width+29*dpr));
  reject('leaked_clip_pixel',()=>assertClipping(captures.initial_unhover,bad,initial,dpr));
  reject('hover_never_changes',()=>assertHover(captures.x12_unhover,captures.x12_unhover,initial,dpr));
  reject('clipped_off_pointer_still_hovers',()=>assertSameFill(captures.initial_unhover,captures.x12,initial,dpr));
  reject('horizontal_endpoint_missing',()=>assertHorizontalEnd(captures.initial_hover,initial,dpr));
  reject('vertical_endpoint_missing',()=>assertVerticalEnd(captures.initial_unhover,dpr));
  reject('wheel_not_delivered',()=>assertWheelDelivery([],{deltaX:12,deltaY:0,x:100,y:100}));
  return controls;
}
