import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {SCROLLABLE,assertImage,inspectInitial,assertTranslation,assertUnchanged,assertClipping,assertHover,
  assertSameFill,assertHorizontalEnd,assertVerticalEnd,assertWheelDelivery,scrollableNegativeControls}
  from './scrollable-comparator.mjs';

// Validate independently retained browser reports. Full-image hashes are compared
// only WITHIN one renderer; renderer-to-renderer text ink/pixels may differ.
// This module does not read or infer private Rust scrolling state.
export const SCROLLABLE_CAPTURES=Object.freeze([
  'initial_unhover','pointer_only','initial_hover','x12','clipped_pointer_only',
  'x12_unhover','x12_hover_restored','y12','outside_before','outside_x',
  'vertical_top_restore','horizontal_end','horizontal_end_repeat','horizontal_top_restore',
  'horizontal_top_repeat','vertical_end','vertical_end_repeat','vertical_top_return','vertical_top_repeat',
]);
export const SCROLLABLE_NEGATIVE_CONTROLS=Object.freeze([
  'no_horizontal_movement','wrong_scroll_axis','no_vertical_propagation','leaked_clip_pixel',
  'hover_never_changes','clipped_off_pointer_still_hovers','horizontal_endpoint_missing',
  'vertical_endpoint_missing','wheel_not_delivered',
]);
const LABELS=['heading','horizontal','vertical'];
const FULL_PIXELS=500*500;
const HASH=/^[0-9a-f]{64}$/;
const REVISION=/^[0-9a-f]{40}$/;
const SCREENSHOT_METHOD='full viewport screenshot; integer canvas origin; no cropping, resampling or replacement';
const clone=value=>structuredClone(value);
const passed=(value,label)=>assert.equal(value?.status,'passed',`${label}: passed evidence required`);
const hash=(value,label)=>assert(typeof value==='string'&&HASH.test(value),`${label}: SHA-256 required`);
const object=(value,label)=>assert(value&&typeof value==='object'&&!Array.isArray(value),`${label}: object required`);
const sameKeys=(value,keys,label)=>assert.deepEqual(Object.keys(value).sort(),[...keys].sort(),`${label}: complete named evidence required`);
const color=(rgba,label)=>{
  assert(Array.isArray(rgba)&&rgba.length===4,`${label}: actual RGBA patch required`);
  assert(rgba.every(v=>Number.isInteger(v)&&v>=0&&v<=255),`${label}: byte channels required`);
  assert.equal(rgba[3],255,`${label}: opaque composite patch required`);
};
function rect(bounds,label) {
  object(bounds,label);sameKeys(bounds,['x','y','width','height'],label);
  assert(Object.values(bounds).every(Number.isInteger),`${label}: integer screenshot bounds required`);
  assert(bounds.x>=0&&bounds.y>=0&&bounds.width>0&&bounds.height>0&&
    bounds.x+bounds.width<=500&&bounds.y+bounds.height<=500,`${label}: nonempty bounds inside full screenshot`);
}
function feature(value,label) {
  object(value,label);rect(value.bounds,`${label} bounds`);
  assert(Number.isInteger(value.pixels)&&value.pixels>=20&&
    value.pixels<=value.bounds.width*value.bounds.height,`${label}: measurable ink population required`);
  hash(value.shape_sha256,`${label} ink shape`);
}
function initialEvidence(value) {
  object(value,'initial screenshot evidence');object(value.geometry,'initial border geometry');
  sameKeys(value.geometry,['green','blue'],'initial border geometry');
  const {green:g,blue:b}=value.geometry;
  rect(g,'green border');rect(b,'blue border');
  assert.deepEqual({x:b.x,width:b.width},{x:16,width:468},'Root p4 and opaque blue border width');
  assert.deepEqual({x:g.x,width:g.width,height:g.height},{x:33,width:434,height:150},'Opaque inner border and clipped extent');
  assert(b.y>=32&&b.y<=80,'Bounded heading/blue top');
  assert.equal(g.y,b.y+17,'Nested top padding');assert.equal(b.y+b.height,500,'Initial blue body reaches clip bottom');
  object(value.features,'initial ink features');sameKeys(value.features,LABELS,'initial ink features');
  for(const label of LABELS)feature(value.features[label],`initial ${label}`);
  assert(value.features.heading.bounds.y>12,'Heading must survive the small vertical step');
  assert(value.features.horizontal.bounds.x-g.x>12,'Horizontal label must survive the small X step');
  return value;
}
function translation(value,axis) {
  passed(value,`${axis} displacement`);object(value.deltas,`${axis} deltas`);
  sameKeys(value.deltas,LABELS,`${axis} label deltas`);
  for(const label of LABELS) {
    const delta=value.deltas[label],dx=axis==='horizontal'&&label==='horizontal'?-12:0,dy=axis==='vertical'?-12:0;
    assert.equal(delta.dx,dx,`${axis}/${label}: observed CSS X displacement`);
    assert.equal(delta.dy,dy,`${axis}/${label}: observed CSS Y displacement`);
    feature(delta.before,`${axis}/${label} before`);feature(delta.after,`${axis}/${label} after`);
    assert.deepEqual(delta.after.bounds,{...delta.before.bounds,x:delta.before.bounds.x+dx,y:delta.before.bounds.y+dy},
      `${axis}/${label}: independently measured before/after bounds must agree with displacement`);
    assert.equal(delta.before.pixels,delta.after.pixels,`${axis}/${label}: within-renderer ink population`);
    assert.equal(delta.before.shape_sha256,delta.after.shape_sha256,`${axis}/${label}: within-renderer translated ink shape`);
  }
}
function hover(value,label) {
  passed(value,label);color(value.unhovered_rgba,`${label} unhovered`);color(value.hovered_rgba,`${label} hovered`);
  assert(value.unhovered_rgba[0]-value.hovered_rgba[0]>=5&&value.unhovered_rgba[2]-value.hovered_rgba[2]>=5,
    `${label}: actual interior patch must visibly change on hover`);
}
function unchanged(value,capture,label) {
  passed(value,label);assert.equal(value.checked_pixels,FULL_PIXELS,`${label}: complete image coverage required`);
  hash(value.rgba_sha256,`${label} image`);
  assert.equal(value.rgba_sha256,capture.rgba_sha256,`${label}: measurement must bind its retained capture`);
}
function wheelProfile(g) {
  const x=100,y=g.y+75,outsideX=8,clippedX=g.x-4;
  return [
    ['initial_hover',x,y,0,-1],['x12',x,y,12,0],['x12_unhover',clippedX,y,0,-1],
    ['x12_hover_restored',x,y,0,-1],['y12',x,y,0,12],
    ['outside_before',outsideX,y,12,0],['outside_x',outsideX,y,12,0],
    ['vertical_top_restore',outsideX,y,0,-100000],['horizontal_end',x,y,100000,0],
    ['horizontal_end_repeat',x,y,100000,0],['horizontal_top_restore',x,y,-100000,0],
    ['horizontal_top_repeat',x,y,-100000,0],['vertical_end',8,300,0,100000],
    ['vertical_end_repeat',8,300,0,100000],['vertical_top_return',8,300,0,-100000],
    ['vertical_top_repeat',8,300,0,-100000],
  ].map(([name,x,y,deltaX,deltaY])=>({name,x,y,deltaX,deltaY}));
}
const RECOVERIES=Object.freeze([
  ['initial_unhover','pointer_only'],['x12','clipped_pointer_only'],['x12','x12_hover_restored'],
  ['outside_before','outside_x'],['x12_unhover','vertical_top_restore'],
  ['horizontal_end','horizontal_end_repeat'],['initial_hover','horizontal_top_restore'],
  ['initial_hover','horizontal_top_repeat'],['vertical_end','vertical_end_repeat'],
  ['initial_unhover','vertical_top_return'],['initial_unhover','vertical_top_repeat'],
]);

export function validateScrollableEvidence(result,runtime=result?.runtime) {
  assert(['rust','moonbit'].includes(runtime),'Expected Rust or MoonBit runtime');object(result,`${runtime} result`);
  assert.equal(result.runtime,runtime,'Independent correctly identified runtime evidence required');
  assert.equal(result.status,runtime==='rust'?'rust_oracle_passed':'moonbit_profile_passed',`${runtime}: completed runtime profile required`);
  assert.equal(result.candidate,'implemented',`${runtime}: implemented candidate required`);
  assert.equal(result.comparison,'not_run',`${runtime}: raw profile must not self-certify paired comparison`);
  assert.equal(result.failure,undefined,`${runtime}: failed evidence cannot pass`);
  assert.deepEqual(result.errors,[],`${runtime}: no runtime errors allowed`);
  assert.deepEqual(result.profile,{width:500,height:500,dpr:1,wheel:'trusted Chromium pixel wheel'},'Only the measured 500x500 DPR 1 profile is paired');
  assert.deepEqual(result.canvas,{bounds:{x:0,y:0,width:500,height:500},backing:{width:500,height:500}},'Full-size integer-origin canvas required');
  assert.deepEqual(result.source,{id:'scrollable',source:SCROLLABLE.source,source_blob:SCROLLABLE.sourceBlob,
    upstream_revision:SCROLLABLE.revision,width:500,height:500,dpr:1,status:'paired_profile',candidate:'implemented'},'Pinned paired source identity required');
  const build=result.build;object(build,'build manifest');
  assert(REVISION.test(build.lab_revision),'Committed lab revision required');assert.equal(build.lab_tracked_dirty,false,'Clean tracked lab build required');
  assert.equal(build.upstream?.revision,SCROLLABLE.revision,'Pinned upstream revision required');
  assert(REVISION.test(build.moonbit?.revision),'Pinned MoonBit revision required');
  assert.equal(build.rust_bundled,true,'Actual Rust bundle required');
  assert.equal(build.rust?.source_modified,false,'Rust source must remain unchanged');
  assert.equal(build.rust?.packaging?.upstream_files_modified,false,'Rust packaging must not alter upstream files');
  assert(build.implemented?.includes('scrollable'),'Built MoonBit scrollable implementation required');
  assert(build.rust_implemented?.includes('scrollable'),'Built unchanged Rust scrollable implementation required');
  hash(build.runtime_sha256_by_example?.scrollable,'MoonBit runtime artifact');
  for(const file of ['scrollable.js','scrollable_bg.wasm'])hash(build.rust.files?.[file],`Rust ${file}`);
  assert(Array.isArray(result.requests),'Actual runtime HTTP requests required');
  for(const file of runtime==='rust'?['scrollable.js','scrollable_bg.wasm']:['scrollable.mjs'])
    assert(result.requests.some(r=>{
      try{return r.status===200&&new URL(r.url).pathname.endsWith(`/${runtime}/${file}`);}catch{return false;}
    }),`${runtime}: delivered ${file} HTTP 200 required`);

  initialEvidence(result.initial);const {green:g}=result.initial.geometry;
  const captures=result.captures;object(captures,'retained captures');
  for(const name of SCROLLABLE_CAPTURES)assert(captures[name],`${runtime}: missing ${name} capture`);
  for(const [name,capture] of Object.entries(captures)) {
    object(capture,`${name} capture`);assert.equal(capture.stable,true,`${name}: two stable valid screenshots required`);
    assert.equal(capture.last_error,null,`${name}: failed screenshot predicate`);
    assert.equal(capture.width,500,`${name}: full screenshot width`);assert.equal(capture.height,500,`${name}: full screenshot height`);
    hash(capture.png_sha256,`${name} PNG`);hash(capture.rgba_sha256,`${name} RGBA`);
    assert.equal(capture.file,`scrollable-${runtime}-${name}-dpr1.png`,`${name}: independent runtime capture filename`);
    assert.equal(capture.method,SCREENSHOT_METHOD,`${name}: full unmodified screenshot required`);
  }
  assert.deepEqual(captures.initial_unhover.measurement,result.initial,'Initial geometry must bind the initial capture measurement');
  const checks=result.checks;object(checks,'runtime checks');
  translation(checks.horizontal,'horizontal');translation(checks.vertical_propagation,'vertical');
  assert.deepEqual(captures.x12.measurement,checks.horizontal,'X displacement must bind actual X capture');
  assert.deepEqual(captures.y12.measurement,checks.vertical_propagation,'Y displacement must bind actual Y capture');
  for(const label of LABELS)assert.deepEqual(checks.horizontal.deltas[label].after,checks.vertical_propagation.deltas[label].before,
    `${label}: both checks must measure the same intermediate x12 capture`);
  hover(checks.initial_hover,'initial hover');hover(checks.hover_after_scroll,'hover after scroll');
  assert.deepEqual(checks.initial_hover,checks.hover_after_scroll,'Horizontal motion must preserve actual uniform hover patches');
  assert.deepEqual(captures.initial_hover.measurement,checks.initial_hover,'Hover must bind actual hover capture');
  passed(checks.clipped_pointer,'clipped-off pointer');color(checks.clipped_pointer.rgba,'clipped-off pointer fill');
  assert.deepEqual(checks.clipped_pointer.rgba,checks.initial_hover.unhovered_rgba,'Clipped-off pointer must retain unhovered interior fill');
  assert.deepEqual(captures.x12_unhover.measurement,checks.clipped_pointer,'Clipped pointer must bind its actual capture');
  passed(checks.clipping,'inner clipping');assert.equal(checks.clipping.checked_outside_pixels,2240,'Both retained blue padding strips must be checked');
  passed(checks.horizontal_endpoint,'horizontal endpoint');
  assert.equal(checks.horizontal_endpoint.right_border_x,g.x+g.width-1,'Visible clamped endpoint right border');
  assert.equal(checks.horizontal_endpoint.checked_border_pixels,110,'Complete endpoint right-border probe');
  assert.deepEqual(captures.horizontal_end.measurement,checks.horizontal_endpoint,'Endpoint must bind horizontal capture');
  passed(checks.vertical_endpoint,'vertical endpoint');
  assert.equal(checks.vertical_endpoint.bottom_border_y,483,'Clamped blue bottom border above root padding');
  assert.equal(checks.vertical_endpoint.checked_border_pixels,468,'Complete blue bottom-border probe');
  assert.equal(checks.vertical_endpoint.checked_padding_pixels,8000,'Fixed 16px root bottom padding required');
  assert.deepEqual(captures.vertical_end.measurement,checks.vertical_endpoint,'Endpoint must bind vertical capture');
  for(const [reference,name] of RECOVERIES) {
    assert.equal(captures[name].rgba_sha256,captures[reference].rgba_sha256,`${name}: complete image must recover/repeat ${reference}`);
    unchanged(captures[name].measurement,captures[name],name);
  }
  unchanged(checks.anonymous_pointer_no_redraw,captures.pointer_only,'anonymous move-only hover');
  assert.deepEqual(checks.anonymous_pointer_no_redraw,captures.pointer_only.measurement,'Move-only no-redraw check must bind capture');
  unchanged(checks.outside_inner_wheel,captures.outside_x,'outside inner wheel');
  assert.deepEqual(checks.outside_inner_wheel,captures.outside_x.measurement,'Outside wheel check must bind capture');
  for(const [a,b] of [['initial_unhover','initial_hover'],['initial_hover','x12'],['x12','x12_unhover'],['x12','y12'],
    ['initial_hover','horizontal_end'],['x12','horizontal_end'],['initial_unhover','vertical_end']])
    assert.notEqual(captures[a].rgba_sha256,captures[b].rgba_sha256,`${a}/${b}: changed behavior requires independently different actual images`);

  const expectedOperations=wheelProfile(g);assert(Array.isArray(result.operations),'Ordered wheel operations required');
  assert.deepEqual(result.operations.map(o=>o.name),expectedOperations.map(o=>o.name),'Complete ordered wheel profile required');
  const delivered=[];
  for(const [i,expected] of expectedOperations.entries()) {
    const operation=result.operations[i];passed(operation,expected.name);
    for(const [key,value] of Object.entries(expected))assert.equal(operation[key],value,`${expected.name}: exact wheel ${key}`);
    assert.equal(operation.post_delivery_animation_frames,2,`${expected.name}: delivery must precede capture settling`);
    passed(operation.delivery,`${expected.name} delivery`);
    assert(Array.isArray(operation.delivery.events),`${expected.name}: retained wheel events required`);
    assertWheelDelivery(operation.delivery.events,expected);
    for(const event of operation.delivery.events) {
      assert.equal(event.type,'wheel',`${expected.name}: actual wheel event type required`);
      assert(Number.isFinite(event.deltaX)&&Number.isFinite(event.deltaY),`${expected.name}: finite wheel deltas required`);
      assert(Number.isFinite(event.time)&&event.time>=0,`${expected.name}: event timestamp required`);
      delivered.push(event);
    }
  }
  assert.deepEqual(result.events,delivered,'Complete delivered event log must match individually checked operations');
  assert(delivered.every((event,i)=>!i||event.time>=delivered[i-1].time),'Wheel log must preserve delivery chronology');
  passed(checks.initial_pointer_delivery,'initial pointer delivery');
  assert(Array.isArray(checks.initial_pointer_delivery.events)&&checks.initial_pointer_delivery.events.length>0,'Initial trusted pointer events required');
  assert(Array.isArray(result.pointer_events),'Complete pointer delivery log required');
  assert.deepEqual(result.pointer_events.slice(0,checks.initial_pointer_delivery.events.length),checks.initial_pointer_delivery.events,
    'Initial pointer evidence must be retained in full pointer log');
  const points=[{x:8,y:300},{x:100,y:g.y+75},{x:g.x-4,y:g.y+75}];
  for(const point of points)assert(result.pointer_events.some(e=>e.type==='pointermove'&&e.trusted===true&&e.target==='CANVAS'&&
    e.pointerType==='mouse'&&e.x===point.x&&e.y===point.y),`Trusted pointer delivery required at ${point.x},${point.y}`);
  for(const point of points.slice(0,2))assert(checks.initial_pointer_delivery.events.some(e=>e.type==='pointermove'&&e.trusted===true&&
    e.target==='CANVAS'&&e.pointerType==='mouse'&&e.x===point.x&&e.y===point.y),'Initial pointer moves must precede initial hover wheel');

  assert(Array.isArray(result.negative_controls),'Negative controls required');
  assert.deepEqual(result.negative_controls.map(c=>c.name).sort(),[...SCROLLABLE_NEGATIVE_CONTROLS].sort(),'All nine distinct named negative controls required');
  for(const control of result.negative_controls) {
    assert.equal(control.rejected,true,`${control.name}: failed negative control`);
    assert.equal(control.input,'intentionally corrupted screenshot/event evidence',`${control.name}: corrupted-copy control provenance required`);
  }
  assert.deepEqual(result.negative_controls_capture_sha256,Object.fromEntries(Object.entries(captures).map(([name,c])=>[name,c.rgba_sha256])),
    'Negative controls must be bound to this completed capture set; stale controls are invalid');
  return {runtime,capture_count:Object.keys(captures).length,wheel_operation_count:expectedOperations.length,
    negative_controls:clone(result.negative_controls),full_image_recoveries:RECOVERIES.map(([reference,capture])=>({reference,capture,
      checked_pixels:FULL_PIXELS,rgba_sha256:captures[capture].rgba_sha256}))};
}

// Decode files outside this module with a real PNG decoder. Passing header/hash
// metadata is insufficient: data must contain the complete decoded RGBA pixels.
// This separate validator also accepts historical Rust-only reports, without
// changing their provenance/status or presenting them as a paired execution.
export function validateScrollablePixels(report,images) {
  object(report,'pixel report');object(images,'decoded capture images');
  assert.equal(report.profile?.dpr,1,'Decoded-pixel pairing is scoped to DPR 1');
  const captures=report.captures;object(captures,'retained captures');
  for(const name of SCROLLABLE_CAPTURES) {
    assert(captures[name],`${name}: retained capture required for pixel revalidation`);
    assert(images[name],`${name}: decoded image required for pixel revalidation`);
  }
  sameKeys(images,Object.keys(captures),'decoded capture image set');
  const verifiedHashes={};
  for(const [name,capture] of Object.entries(captures)) {
    const image=images[name];
    assert(image?.data instanceof Uint8Array,`${name}: actual decoded Uint8Array RGBA bytes required`);
    assertImage(image,1);
    assert.equal(image.width,capture.width,`${name}: decoded width must match capture`);
    assert.equal(image.height,capture.height,`${name}: decoded height must match capture`);
    const actual=createHash('sha256').update(image.data).digest('hex');
    assert.equal(actual,capture.rgba_sha256,`${name}: complete decoded RGBA SHA-256 must match retained report`);
    verifiedHashes[name]=actual;
  }
  const initial=inspectInitial(images.initial_unhover,1);
  assert.deepEqual(report.initial,initial,'Declared initial geometry/features must be recomputed from actual decoded pixels');
  const measurements={initial_unhover:initial,outside_before:true};
  measurements.pointer_only=assertUnchanged(images.initial_unhover,images.pointer_only,1);
  assert.deepEqual(inspectInitial(images.initial_hover,1).geometry,initial.geometry,'Actual hover redraw must retain initial opaque border geometry');
  measurements.initial_hover=assertHover(images.initial_unhover,images.initial_hover,initial,1);
  measurements.x12=assertTranslation(images.initial_hover,images.x12,initial,{afterX:-12},1);
  measurements.clipped_pointer_only=assertUnchanged(images.x12,images.clipped_pointer_only,1);
  const clipping=assertClipping(images.initial_unhover,images.x12_unhover,initial,1);
  measurements.x12_unhover=assertSameFill(images.initial_unhover,images.x12_unhover,initial,1);
  const hoverAfterScroll=assertHover(images.x12_unhover,images.x12,initial,1);
  measurements.x12_hover_restored=assertUnchanged(images.x12,images.x12_hover_restored,1);
  measurements.y12=assertTranslation(images.x12,images.y12,initial,{beforeX:-12,afterX:-12,afterY:-12},1);
  measurements.outside_x=assertUnchanged(images.outside_before,images.outside_x,1);
  measurements.vertical_top_restore=assertUnchanged(images.x12_unhover,images.vertical_top_restore,1);
  measurements.horizontal_end=assertHorizontalEnd(images.horizontal_end,initial,1);
  measurements.horizontal_end_repeat=assertUnchanged(images.horizontal_end,images.horizontal_end_repeat,1);
  measurements.horizontal_top_restore=assertUnchanged(images.initial_hover,images.horizontal_top_restore,1);
  measurements.horizontal_top_repeat=assertUnchanged(images.initial_hover,images.horizontal_top_repeat,1);
  measurements.vertical_end=assertVerticalEnd(images.vertical_end,1);
  measurements.vertical_end_repeat=assertUnchanged(images.vertical_end,images.vertical_end_repeat,1);
  measurements.vertical_top_return=assertUnchanged(images.initial_unhover,images.vertical_top_return,1);
  measurements.vertical_top_repeat=assertUnchanged(images.initial_unhover,images.vertical_top_repeat,1);
  for(const name of SCROLLABLE_CAPTURES)assert.deepEqual(captures[name].measurement,measurements[name],
    `${name}: declared capture measurement must match actual decoded pixel predicate`);
  const checks={anonymous_pointer_no_redraw:measurements.pointer_only,initial_hover:measurements.initial_hover,
    horizontal:measurements.x12,clipping,clipped_pointer:measurements.x12_unhover,hover_after_scroll:hoverAfterScroll,
    vertical_propagation:measurements.y12,outside_inner_wheel:measurements.outside_x,
    horizontal_endpoint:measurements.horizontal_end,vertical_endpoint:measurements.vertical_end};
  object(report.checks,'recorded pixel checks');
  for(const [name,actual] of Object.entries(checks))assert.deepEqual(report.checks[name],actual,
    `${name}: declared check must match recomputed decoded-pixel evidence`);
  const controls=scrollableNegativeControls(images,initial,1);
  assert.deepEqual(report.negative_controls,controls,'All nine negative controls must be recomputed from these decoded captures');
  // Historical Rust-only reports predate this binding; paired provenance
  // validation independently requires it. Never add it to a historical report.
  if(report.negative_controls_capture_sha256!==undefined)assert.deepEqual(report.negative_controls_capture_sha256,verifiedHashes,
    'Negative controls must bind the actual decoded capture hashes');
  return {status:'passed',capture_count:Object.keys(captures).length,checked_pixels_per_capture:FULL_PIXELS,
    checked_rgba_pixels:Object.keys(captures).length*FULL_PIXELS,
    full_image_recoveries:RECOVERIES.length,negative_controls:clone(controls)};
}

export function compareScrollableBehavior(rust,moonbit) {
  const integrity={rust:validateScrollableEvidence(rust,'rust'),moonbit:validateScrollableEvidence(moonbit,'moonbit')};
  assert.deepEqual(rust.build,moonbit.build,'Both profiles must come from the identical clean committed build manifest');
  assert.deepEqual(rust.source,moonbit.source,'Both profiles must identify the exact same pinned source/blob');
  assert.deepEqual(rust.profile,moonbit.profile,'Both profiles must use the identical browser input profile');
  assert.deepEqual(rust.initial.geometry,moonbit.initial.geometry,'Actual initial opaque border geometry must match across renderers');
  const displacement={};
  for(const [axis,key] of [['horizontal','horizontal'],['vertical','vertical_propagation']]) {
    displacement[axis]=Object.fromEntries(LABELS.map(label=>{
      const a=rust.checks[key].deltas[label],b=moonbit.checks[key].deltas[label];
      assert.deepEqual({dx:a.dx,dy:a.dy},{dx:b.dx,dy:b.dy},`${axis}/${label}: cross-renderer observed displacement`);
      return [label,{rust:{dx:a.dx,dy:a.dy},moonbit:{dx:b.dx,dy:b.dy}}];
    }));
  }
  assert.equal(rust.checks.clipping.checked_outside_pixels,moonbit.checks.clipping.checked_outside_pixels,'Same complete clipping probes');
  for(const key of ['horizontal_endpoint','vertical_endpoint'])assert.deepEqual(rust.checks[key],moonbit.checks[key],`Same measured ${key} border/padding evidence`);
  const hoverFill={};
  for(const [label,a,b] of [
    ['unhovered',rust.checks.initial_hover.unhovered_rgba,moonbit.checks.initial_hover.unhovered_rgba],
    ['hovered',rust.checks.initial_hover.hovered_rgba,moonbit.checks.initial_hover.hovered_rgba],
    ['clipped_pointer',rust.checks.clipped_pointer.rgba,moonbit.checks.clipped_pointer.rgba],
  ]) {
    hoverFill[label]={rust_rgba:clone(a),moonbit_rgba:clone(b),moonbit_minus_rust_rgba:b.map((v,i)=>v-a[i]),equal:a.every((v,i)=>v===b[i])};
  }
  return {status:'passed',comparison:'screenshot_derived_behavior',
    scope:'Pinned unchanged scrollable.rs; independent Rust WASM and MoonBit browser screenshots; 500x500 CSS pixels; DPR 1; trusted pixel wheels',
    source:clone(rust.source),profile:clone(rust.profile),
    build:{lab_revision:rust.build.lab_revision,lab_tracked_dirty:false,upstream_revision:rust.build.upstream.revision,moonbit_revision:rust.build.moonbit.revision},
    initial_opaque_border_geometry:clone(rust.initial.geometry),displacement,
    clipping:{status:'passed',checked_outside_pixels_per_renderer:2240,
      rust_checked_outside_pixels:rust.checks.clipping.checked_outside_pixels,moonbit_checked_outside_pixels:moonbit.checks.clipping.checked_outside_pixels},
    hover_fill:{...hoverFill,all_measured_patches_equal:Object.values(hoverFill).every(pair=>pair.equal),
      observation:'Each renderer independently changes its actual interior patch on hover and restores unhovered fill for the clipped-off pointer'},
    endpoints:{horizontal:clone(rust.checks.horizontal_endpoint),vertical:clone(rust.checks.vertical_endpoint)},
    integrity,wheel_delivery:{status:'passed',operation_count_per_renderer:16,
      coordinates_and_deltas:'all retained operations and trusted canvas events exactly match the source-derived profile',
      operations:rust.operations.map((operation,i)=>{
        const observed=value=>({x:value.x,y:value.y,deltaX:value.deltaX,deltaY:value.deltaY,events:clone(value.delivery.events)});
        return {name:operation.name,rust:observed(operation),moonbit:observed(moonbit.operations[i])};
      })},
    unverified:['cross-renderer text ink shape and rasterization parity','cross-renderer complete RGBA image equality',
      'native renderer parity','private Rust scroll offsets','other browsers/GPUs','other viewport sizes','other DPRs',
      'line/page wheel deltas','diagonal wheel gestures','touch/momentum'],
  };
}
