import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {SCROLLABLE,inspectInitial,assertTranslation,assertUnchanged,assertClipping,assertHover,assertSameFill,
  assertHorizontalEnd,assertVerticalEnd,scrollableNegativeControls} from './scrollable-comparator.mjs';
import {SCROLLABLE_CAPTURES,SCROLLABLE_NEGATIVE_CONTROLS,compareScrollableBehavior,validateScrollableEvidence,validateScrollablePixels}
  from './scrollable-pair-comparator.mjs';

// ORIGINAL SYNTHETIC REPORT FIXTURES ONLY. These records and their placeholder
// hashes exercise comparator rejection; they are NOT screenshots or runtime proof.
// Runtime evidence must be independently captured by scrollable-oracle-browser.mjs.
const digest=label=>createHash('sha256').update(`synthetic test fixture: ${label}`).digest('hex');
const copy=value=>structuredClone(value);
const full=(rgba_sha256)=>({status:'passed',checked_pixels:250000,rgba_sha256});
const method='full viewport screenshot; integer canvas origin; no cropping, resampling or replacement';
const labels=['heading','horizontal','vertical'];
function fixture(runtime='rust') {
  const moon=runtime==='moonbit';
  const features=Object.fromEntries(labels.map((name,i)=>[name,{
    bounds:{x:[18,51,34][i],y:[23,83,236][i],width:[170,110,90][i]+(moon?7:0),height:[15,12,12][i]},
    pixels:[600,250,180][i]+(moon?10:0),shape_sha256:digest(`${runtime} ${name} artificial ink`),
  }]));
  const initial={geometry:{green:{x:33,y:59,width:434,height:150},blue:{x:16,y:42,width:468,height:458}},
    features:copy(features),observed:'opaque border bounds and neutral-ink features from full screenshot'};
  const shift=(feature,dx=0,dy=0)=>({...copy(feature),bounds:{...feature.bounds,x:feature.bounds.x+dx,y:feature.bounds.y+dy}});
  const horizontal={status:'passed',measurement:'screenshot feature displacement in CSS pixels',deltas:Object.fromEntries(labels.map(label=>{
    const dx=label==='horizontal'?-12:0;return [label,{dx,dy:0,before:copy(features[label]),after:shift(features[label],dx)}];
  }))};
  const vertical={status:'passed',measurement:'screenshot feature displacement in CSS pixels',deltas:Object.fromEntries(labels.map(label=>{
    const before=horizontal.deltas[label].after;return [label,{dx:0,dy:-12,before:copy(before),after:shift(before,0,-12)}];
  }))};
  const hover={status:'passed',unhovered_rgba:moon?[217,230,229,255]:[218,231,230,255],
    hovered_rgba:moon?[193,218,203,255]:[194,219,204,255],measurement:'Actual uniform interior fill patch'};
  const clipped={status:'passed',rgba:copy(hover.unhovered_rgba)};
  const horizontalEndpoint={status:'passed',right_border_x:466,checked_border_pixels:110};
  const verticalEndpoint={status:'passed',bottom_border_y:483,checked_border_pixels:468,checked_padding_pixels:8000};
  const result={runtime,status:runtime==='rust'?'rust_oracle_passed':'moonbit_profile_passed',candidate:'implemented',comparison:'not_run',
    scope:'SYNTHETIC TEST FIXTURE, NOT RUNTIME EVIDENCE',profile:{width:500,height:500,dpr:1,wheel:'trusted Chromium pixel wheel'},
    source:{id:'scrollable',source:SCROLLABLE.source,source_blob:SCROLLABLE.sourceBlob,upstream_revision:SCROLLABLE.revision,
      width:500,height:500,dpr:1,status:'paired_profile',candidate:'implemented'},
    build:{lab_revision:'a'.repeat(40),lab_tracked_dirty:false,upstream:{revision:SCROLLABLE.revision},moonbit:{revision:'b'.repeat(40)},
      implemented:['scrollable'],rust_implemented:['scrollable'],rust_bundled:true,
      runtime_sha256_by_example:{scrollable:digest('candidate ESM')},
      rust:{source_modified:false,packaging:{upstream_files_modified:false},
        files:{'scrollable.js':digest('Rust bindings'),'scrollable_bg.wasm':digest('Rust WASM')}}},
    canvas:{bounds:{x:0,y:0,width:500,height:500},backing:{width:500,height:500}},
    initial,checks:{horizontal,vertical_propagation:vertical,initial_hover:copy(hover),hover_after_scroll:copy(hover),
      clipped_pointer:clipped,clipping:{status:'passed',checked_outside_pixels:2240,measurement:'Retained blue padding strips outside inner viewport'},
      horizontal_endpoint:horizontalEndpoint,vertical_endpoint:verticalEndpoint},
    captures:{},operations:[],requests:(runtime==='rust'?['scrollable.js','scrollable_bg.wasm']:['scrollable.mjs']).map(file=>
      ({url:`http://127.0.0.1:1234/gpui-conformance/${runtime}/${file}`,status:200})),errors:[],console:[]};
  const aliases={pointer_only:'initial_unhover',clipped_pointer_only:'x12',x12_hover_restored:'x12',outside_x:'outside_before',
    vertical_top_restore:'x12_unhover',horizontal_end_repeat:'horizontal_end',horizontal_top_restore:'initial_hover',
    horizontal_top_repeat:'initial_hover',vertical_end_repeat:'vertical_end',vertical_top_return:'initial_unhover',vertical_top_repeat:'initial_unhover'};
  const measurements={initial_unhover:initial,initial_hover:hover,x12:horizontal,x12_unhover:clipped,y12:vertical,
    horizontal_end:horizontalEndpoint,vertical_end:verticalEndpoint,outside_before:true};
  for(const name of SCROLLABLE_CAPTURES) {
    const rgba=digest(`${runtime} artificial ${aliases[name]||name} image`);
    result.captures[name]={file:`scrollable-${runtime}-${name}-dpr1.png`,png_sha256:digest(`${runtime} artificial ${name} PNG`),
      rgba_sha256:rgba,width:500,height:500,stable:true,last_error:null,measurement:copy(measurements[name]??full(rgba)),method};
  }
  result.checks.anonymous_pointer_no_redraw=copy(result.captures.pointer_only.measurement);
  result.checks.outside_inner_wheel=copy(result.captures.outside_x.measurement);
  const operations=[['initial_hover',100,134,0,-1],['x12',100,134,12,0],['x12_unhover',29,134,0,-1],
    ['x12_hover_restored',100,134,0,-1],['y12',100,134,0,12],['outside_before',8,134,12,0],
    ['outside_x',8,134,12,0],['vertical_top_restore',8,134,0,-100000],['horizontal_end',100,134,100000,0],
    ['horizontal_end_repeat',100,134,100000,0],['horizontal_top_restore',100,134,-100000,0],
    ['horizontal_top_repeat',100,134,-100000,0],['vertical_end',8,300,0,100000],
    ['vertical_end_repeat',8,300,0,100000],['vertical_top_return',8,300,0,-100000],['vertical_top_repeat',8,300,0,-100000]];
  result.operations=operations.map(([name,x,y,deltaX,deltaY],i)=>({name,x,y,deltaX,deltaY,status:'passed',
    post_delivery_animation_frames:2,delivery:{status:'passed',events:[{type:'wheel',x,y,deltaX,deltaY,
      deltaMode:0,trusted:true,target:'CANVAS',time:10+i*10,defaultPrevented:true}]}}));
  result.events=result.operations.flatMap(o=>copy(o.delivery.events));
  const pointer=(x,y,time)=>({type:'pointermove',x,y,trusted:true,target:'CANVAS',pointerType:'mouse',time});
  result.checks.initial_pointer_delivery={status:'passed',events:[pointer(8,300,1),pointer(100,134,2)]};
  result.pointer_events=[...copy(result.checks.initial_pointer_delivery.events),pointer(29,134,25)];
  result.negative_controls=SCROLLABLE_NEGATIVE_CONTROLS.map(name=>({name,rejected:true,input:'intentionally corrupted screenshot/event evidence'}));
  bindControls(result);return result;
}
function bindControls(result) {
  result.negative_controls_capture_sha256=Object.fromEntries(Object.entries(result.captures).map(([name,c])=>[name,c.rgba_sha256]));
}
function reject(mutate,pattern) {
  const rust=fixture('rust'),moon=fixture('moonbit');mutate(moon,rust);
  assert.throws(()=>compareScrollableBehavior(rust,moon),pattern);
}

test('synthetic reports compare actual geometry/displacements without cross-renderer ink or image equality',()=>{
  const rust=fixture('rust'),moon=fixture('moonbit');
  const before=[copy(rust),copy(moon)];const result=compareScrollableBehavior(rust,moon);
  assert.equal(result.status,'passed');assert.equal(result.comparison,'screenshot_derived_behavior');
  assert.deepEqual(result.displacement.horizontal.horizontal,{rust:{dx:-12,dy:0},moonbit:{dx:-12,dy:0}});
  assert.deepEqual(result.displacement.vertical.heading,{rust:{dx:0,dy:-12},moonbit:{dx:0,dy:-12}});
  assert.equal(result.clipping.checked_outside_pixels_per_renderer,2240);
  assert.equal(result.integrity.rust.capture_count,19);assert.equal(result.integrity.moonbit.wheel_operation_count,16);
  assert.equal(result.integrity.rust.full_image_recoveries.length,11);
  assert.equal(result.wheel_delivery.operations.length,16);
  assert.deepEqual(result.wheel_delivery.operations[1],{name:'x12',
    rust:{x:100,y:134,deltaX:12,deltaY:0,events:rust.operations[1].delivery.events},
    moonbit:{x:100,y:134,deltaX:12,deltaY:0,events:moon.operations[1].delivery.events}});
  assert.equal(result.integrity.moonbit.negative_controls.length,9);
  assert.notDeepEqual(rust.initial.features,moon.initial.features);
  assert.notEqual(rust.captures.initial_unhover.rgba_sha256,moon.captures.initial_unhover.rgba_sha256);
  assert.deepEqual([rust,moon],before,'Comparator must never modify evidence');
  assert(result.unverified.includes('private Rust scroll offsets'));
  assert(result.unverified.includes('cross-renderer complete RGBA image equality'));
});

test('report explicitly retains unequal actual fill pairs and per-channel differences',()=>{
  const result=compareScrollableBehavior(fixture('rust'),fixture('moonbit'));
  assert.deepEqual(result.hover_fill.unhovered,{rust_rgba:[218,231,230,255],moonbit_rgba:[217,230,229,255],
    moonbit_minus_rust_rgba:[-1,-1,-1,0],equal:false});
  assert.deepEqual(result.hover_fill.hovered,{rust_rgba:[194,219,204,255],moonbit_rgba:[193,218,203,255],
    moonbit_minus_rust_rgba:[-1,-1,-1,0],equal:false});
  assert.equal(result.hover_fill.all_measured_patches_equal,false);
  assert.deepEqual(result.hover_fill.clipped_pointer,result.hover_fill.unhovered);
});

test('equal measured fill colors may be reported when supported, without claiming full-image parity',()=>{
  const rust=fixture('rust'),moon=fixture('moonbit');
  moon.checks.initial_hover=copy(rust.checks.initial_hover);moon.checks.hover_after_scroll=copy(rust.checks.hover_after_scroll);
  moon.checks.clipped_pointer=copy(rust.checks.clipped_pointer);
  moon.captures.initial_hover.measurement=copy(moon.checks.initial_hover);
  moon.captures.x12_unhover.measurement=copy(moon.checks.clipped_pointer);
  const result=compareScrollableBehavior(rust,moon);
  assert.equal(result.hover_fill.all_measured_patches_equal,true);
  assert.deepEqual(result.hover_fill.hovered.moonbit_minus_rust_rgba,[0,0,0,0]);
});

for(const [name,mutate] of [
  ['failed profile',r=>r.status='failed'],['wrong runtime',r=>r.runtime='rust'],
  ['self-certified comparison',r=>r.comparison='passed'],['missing candidate',r=>r.candidate='not_implemented'],
  ['runtime error',r=>r.errors.push('uncaught')],['retained failure',r=>r.failure='old failure'],
])test(`reject ${name}`,()=>reject(mutate));

test('each runtime is mandatory and must be supplied in its proper side',()=>{
  const rust=fixture('rust'),moon=fixture('moonbit');
  assert.throws(()=>compareScrollableBehavior(moon,rust),/identified runtime/);
  assert.throws(()=>compareScrollableBehavior(rust,rust),/identified runtime/);
  assert.throws(()=>compareScrollableBehavior(rust,undefined));
});

for(const [name,mutate] of [
  ['wrong source path',r=>r.source.source='another.rs'],['wrong source blob',r=>r.source.source_blob='0'.repeat(40)],
  ['historical Rust-only record',r=>r.source.status='rust_oracle_only'],
  ['dirty build',r=>r.build.lab_tracked_dirty=true],['missing clean flag',r=>delete r.build.lab_tracked_dirty],
  ['mismatched lab revision',r=>r.build.lab_revision='c'.repeat(40)],
  ['mismatched candidate revision',r=>r.build.moonbit.revision='c'.repeat(40)],
  ['mismatched runtime hash',r=>r.build.runtime_sha256_by_example.scrollable=digest('different ESM')],
  ['mismatched full build manifest',r=>r.build.compiler='different compiler'],
  ['unbundled Rust',r=>r.build.rust_bundled=false],['modified upstream source',r=>r.build.rust.source_modified=true],
  ['modified upstream packaging',r=>r.build.rust.packaging.upstream_files_modified=true],
  ['missing Rust implementation',r=>r.build.rust_implemented=[]],['missing MoonBit implementation',r=>r.build.implemented=[]],
  ['missing artifact hash',r=>delete r.build.rust.files['scrollable_bg.wasm']],
  ['missing delivered runtime request',r=>r.requests=[]],['failed delivered runtime request',r=>r.requests[0].status=404],
  ['wrong runtime delivery path',r=>r.requests[0].url=r.requests[0].url.replace('/moonbit/','/rust/')],
])test(`reject provenance: ${name}`,()=>reject(mutate));

test('even two matching results cannot weaken pinned source/build/profile requirements',()=>{
  for(const mutate of [r=>r.build.upstream.revision='c'.repeat(40),r=>r.source.source_blob='c'.repeat(40),
    r=>r.build.lab_revision='working-tree',r=>r.profile.dpr=2,r=>r.profile.width=499,
    r=>r.profile.wheel='synthetic dispatchEvent',r=>r.canvas.bounds.x=0.5,r=>r.canvas.backing.width=1000]) {
    const rust=fixture('rust'),moon=fixture('moonbit');mutate(rust);mutate(moon);
    assert.throws(()=>compareScrollableBehavior(rust,moon));
  }
});

for(const name of SCROLLABLE_CAPTURES)test(`require retained ${name} capture`,()=>reject(r=>delete r.captures[name],/missing .* capture/));
for(const [name,mutate] of [
  ['unstable capture',r=>r.captures.x12.stable=false],['failed capture predicate',r=>r.captures.x12.last_error='wrong pixels'],
  ['cropped capture',r=>r.captures.x12.width=499],['resampled method',r=>r.captures.x12.method='cropped and resampled'],
  ['missing image hash',r=>delete r.captures.x12.rgba_sha256],
  ['reused Rust image',r=>r.captures.x12.file='scrollable-rust-x12-dpr1.png'],
  ['disconnected initial measurement',r=>r.captures.initial_unhover.measurement.features.heading.pixels++],
  ['disconnected movement measurement',r=>r.captures.x12.measurement.deltas.horizontal.dx=0],
])test(`reject screenshot evidence: ${name}`,()=>reject(mutate));

test('additional independently retained captures are allowed and included in control binding',()=>{
  const rust=fixture('rust'),moon=fixture('moonbit');
  for(const result of [rust,moon]) {
    result.captures.extra_diagnostic={...copy(result.captures.x12),file:`scrollable-${result.runtime}-extra_diagnostic-dpr1.png`};
    bindControls(result);
  }
  assert.equal(compareScrollableBehavior(rust,moon).integrity.rust.capture_count,20);
});

test('reject changed opaque geometry even when internally valid in the second report',()=>{
  reject(r=>{
    r.initial.geometry.green.y++;r.initial.geometry.blue.y++;r.initial.geometry.blue.height--;
    r.captures.initial_unhover.measurement=copy(r.initial);
  });
  reject(r=>{r.initial.geometry.green.width=433;r.captures.initial_unhover.measurement=copy(r.initial);},/inner border/);
});

for(const axis of ['horizontal','vertical_propagation'])for(const label of labels) {
  test(`reject altered ${axis}/${label} observed movement`,()=>reject(r=>{
    const d=r.checks[axis].deltas[label];d.dx++;d.after.bounds.x++;
    r.captures[axis==='horizontal'?'x12':'y12'].measurement=copy(r.checks[axis]);
  },/displacement/));
  test(`reject ${axis}/${label} stated movement unsupported by bounds`,()=>reject(r=>{
    r.checks[axis].deltas[label].after.bounds.y++;
  },/before\/after bounds/));
  test(`reject ${axis}/${label} changing within-renderer ink shape`,()=>reject(r=>{
    r.checks[axis].deltas[label].after.shape_sha256=digest('changed artificial ink');
  },/translated ink shape/));
  test(`reject ${axis}/${label} changing within-renderer ink count`,()=>reject(r=>{
    r.checks[axis].deltas[label].after.pixels++;
  },/ink population/));
}

test('displacement comparisons require the identical intermediate x12 feature measurements',()=>reject(r=>{
  const d=r.checks.vertical_propagation.deltas.horizontal;d.before.bounds.x++;d.after.bounds.x++;
  r.captures.y12.measurement=copy(r.checks.vertical_propagation);
},/same intermediate/));

for(const [name,mutate] of [
  ['failed clipping',r=>r.checks.clipping.status='failed'],['incomplete outside pixels',r=>r.checks.clipping.checked_outside_pixels=2239],
  ['hover never changes',r=>r.checks.initial_hover.hovered_rgba=copy(r.checks.initial_hover.unhovered_rgba)],
  ['nonopaque fill',r=>r.checks.initial_hover.hovered_rgba[3]=128],
  ['missing fill',r=>delete r.checks.initial_hover.hovered_rgba],
  ['scroll changes fill',r=>r.checks.hover_after_scroll.unhovered_rgba[0]--],
  ['clipped-off pointer still hovers',r=>r.checks.clipped_pointer.rgba=copy(r.checks.initial_hover.hovered_rgba)],
  ['failed clipped-pointer check',r=>r.checks.clipped_pointer.status='failed'],
  ['missing right endpoint border',r=>r.checks.horizontal_endpoint.right_border_x=465],
  ['incomplete right endpoint border',r=>r.checks.horizontal_endpoint.checked_border_pixels=109],
  ['failed vertical endpoint',r=>r.checks.vertical_endpoint.status='failed'],
  ['missing bottom endpoint border',r=>r.checks.vertical_endpoint.bottom_border_y=484],
  ['incomplete bottom endpoint border',r=>r.checks.vertical_endpoint.checked_border_pixels=467],
  ['changed root bottom padding',r=>r.checks.vertical_endpoint.checked_padding_pixels=7999],
])test(`reject measured behavior: ${name}`,()=>reject(mutate));

for(const name of ['pointer_only','clipped_pointer_only','x12_hover_restored','outside_x','vertical_top_restore',
  'horizontal_end_repeat','horizontal_top_restore','horizontal_top_repeat','vertical_end_repeat','vertical_top_return','vertical_top_repeat']) {
  test(`reject incomplete full-image equality in ${name}`,()=>reject(r=>r.captures[name].measurement.checked_pixels=249999,/complete image coverage/));
  test(`reject changed full-image repeat/recovery in ${name}`,()=>reject(r=>{
    r.captures[name].rgba_sha256=digest('changed one physical pixel');r.captures[name].measurement.rgba_sha256=r.captures[name].rgba_sha256;
    bindControls(r);
  },/complete image must recover/));
}

test('unchanged blank/same captures cannot pass changed movement/hover/endpoint evidence',()=>reject(r=>{
  const rgba=r.captures.initial_unhover.rgba_sha256;
  for(const c of Object.values(r.captures)){c.rgba_sha256=rgba;if(c.measurement?.rgba_sha256)c.measurement.rgba_sha256=rgba;}
  r.checks.anonymous_pointer_no_redraw.rgba_sha256=rgba;r.checks.outside_inner_wheel.rgba_sha256=rgba;bindControls(r);
},/independently different/));

for(const name of ['initial_hover','x12','x12_unhover','x12_hover_restored','y12','outside_before','outside_x','vertical_top_restore',
  'horizontal_end','horizontal_end_repeat','horizontal_top_restore','horizontal_top_repeat','vertical_end','vertical_end_repeat',
  'vertical_top_return','vertical_top_repeat'])test(`require completed delivered ${name} wheel operation`,()=>reject(r=>{
  r.operations=r.operations.filter(o=>o.name!==name);
},/Complete ordered wheel profile/));

for(const [name,mutate] of [
  ['pending wheel operation',r=>r.operations[1].status='pending_pixels'],
  ['pending wheel delivery',r=>r.operations[1].delivery.status='pending'],
  ['untrusted wheel',r=>r.operations[1].delivery.events[0].trusted=false],
  ['wheel sent outside canvas',r=>r.operations[1].delivery.events[0].target='BODY'],
  ['wrong wheel coordinate',r=>r.operations[1].delivery.events[0].x=99],
  ['wrong profile coordinate',r=>r.operations[1].x=99],
  ['wrong wheel delta',r=>r.operations[1].delivery.events[0].deltaX=11],
  ['wrong profile delta',r=>r.operations[1].deltaX=11],
  ['not prevented wheel',r=>r.operations[1].delivery.events[0].defaultPrevented=false],
  ['line-mode wheel',r=>r.operations[1].delivery.events[0].deltaMode=1],
  ['undelivered wheel',r=>r.operations[1].delivery.events=[]],
  ['capture before settling',r=>r.operations[1].post_delivery_animation_frames=0],
  ['non-wheel event',r=>r.operations[1].delivery.events[0].type='pointermove'],
  ['event log truncated',r=>r.events.pop()],
  ['event log reordered',r=>r.events.reverse()],
  ['missing event timestamp',r=>delete r.operations[1].delivery.events[0].time],
  ['initial pointer not delivered',r=>r.checks.initial_pointer_delivery.status='failed'],
  ['untrusted initial pointer',r=>r.checks.initial_pointer_delivery.events[1].trusted=false],
  ['missing clipped-off pointer delivery',r=>r.pointer_events.pop()],
  ['pointer log disconnected',r=>r.pointer_events[0].x=9],
])test(`reject transport evidence: ${name}`,()=>reject(mutate));

test('multiple trusted wheel events may sum to the exact operation delta',()=>{
  const rust=fixture('rust'),moon=fixture('moonbit');
  const original=moon.operations[1].delivery.events[0];
  moon.operations[1].delivery.events=[{...original,deltaX:5},{...original,deltaX:7,time:original.time+1}];
  moon.events=moon.operations.flatMap(o=>copy(o.delivery.events));
  assert.equal(compareScrollableBehavior(rust,moon).status,'passed');
});

for(const name of SCROLLABLE_NEGATIVE_CONTROLS) {
  test(`require negative control ${name} by its exact name`,()=>reject(r=>{
    r.negative_controls=r.negative_controls.filter(c=>c.name!==name);
  },/nine distinct named negative controls/));
  test(`reject surviving negative control ${name}`,()=>reject(r=>{
    r.negative_controls.find(c=>c.name===name).rejected=false;
  },new RegExp(`${name}: failed negative control`)));
}

test('reject duplicate, unknown, stale or misleading negative controls',()=>{
  reject(r=>r.negative_controls[8]=copy(r.negative_controls[0]),/nine distinct/);
  reject(r=>r.negative_controls[8].name='old_wheel_control',/nine distinct/);
  reject(r=>delete r.negative_controls_capture_sha256,/stale controls/);
  reject(r=>r.negative_controls_capture_sha256.y12=digest('previous run y12'),/stale controls/);
  reject(r=>r.negative_controls[0].input='engine mutation coverage',/corrupted-copy control provenance/);
});

test('standalone evidence integrity validation is available without claiming a pair',()=>{
  assert.equal(validateScrollableEvidence(fixture('rust')).runtime,'rust');
  assert.equal(validateScrollableEvidence(fixture('moonbit'),'moonbit').runtime,'moonbit');
});


// Actual synthetic RGBA byte fixtures, still NOT runtime rendering proof. The
// artificial ink pattern follows the existing screenshot-comparator test style;
// it does not imitate font shaping or any renderer's private state.
function syntheticPixels({dx=0,dy=0,hover=false}={}) {
  const width=500,height=500,data=new Uint8Array(width*height*4),root={x:0,y:0,width:500,height:500};
  function rect(x,y,w,h,rgba,clip=root) {
    for(let yy=Math.max(0,y,clip.y);yy<Math.min(500,y+h,clip.y+clip.height);yy++)
      for(let xx=Math.max(0,x,clip.x);xx<Math.min(500,x+w,clip.x+clip.width);xx++)data.set(rgba,4*(yy*width+xx));
  }
  function box(x,y,w,h,fill,border,clip=root) {
    rect(x,y,w,h,fill,clip);rect(x,y,w,1,border,clip);rect(x,y+h-1,w,1,border,clip);
    rect(x,y,1,h,border,clip);rect(x+w-1,y,1,h,border,clip);
  }
  function ink(x,y,w,clip=root) {
    for(let offset=0;offset<w;offset+=6) {
      rect(x+offset,y,3,8,[0,0,0,255],clip);rect(x+offset+3,y+3,2,2,[0,0,0,255],clip);
    }
  }
  rect(0,0,500,500,[255,255,255,255]);
  box(16,42+dy,468,5000,[242,242,255,255],[0,0,255,255]);
  const clip={x:33,y:59+dy,width:434,height:150};
  box(33+dx,59+dy,2000,150,hover?[194,219,204,255]:[218,231,230,255],[0,128,0,255],clip);
  ink(16,22+dy,240);ink(50+dx,80+dy,90,clip);ink(33,235+dy,80);
  return {width,height,data};
}
let pixelProfileBaseline;
function pixelProfile() {
  if(!pixelProfileBaseline) {
    const report=fixture('rust'),images={
      initial_unhover:syntheticPixels(),initial_hover:syntheticPixels({hover:true}),
      x12:syntheticPixels({dx:-12,hover:true}),x12_unhover:syntheticPixels({dx:-12}),
      y12:syntheticPixels({dx:-12,dy:-12,hover:true}),outside_before:syntheticPixels({dx:-12,dy:-12}),
      horizontal_end:syntheticPixels({dx:-1566,hover:true}),vertical_end:syntheticPixels({dy:-4558}),
    };
    for(const [reference,name] of [['initial_unhover','pointer_only'],['x12','clipped_pointer_only'],['x12','x12_hover_restored'],
      ['outside_before','outside_x'],['x12_unhover','vertical_top_restore'],['horizontal_end','horizontal_end_repeat'],
      ['initial_hover','horizontal_top_restore'],['initial_hover','horizontal_top_repeat'],['vertical_end','vertical_end_repeat'],
      ['initial_unhover','vertical_top_return'],['initial_unhover','vertical_top_repeat']])images[name]=images[reference];
    const initial=inspectInitial(images.initial_unhover);
    const measurements={initial_unhover:initial,initial_hover:assertHover(images.initial_unhover,images.initial_hover,initial),
      x12:assertTranslation(images.initial_hover,images.x12,initial,{afterX:-12}),
      x12_unhover:assertSameFill(images.initial_unhover,images.x12_unhover,initial),
      y12:assertTranslation(images.x12,images.y12,initial,{beforeX:-12,afterX:-12,afterY:-12}),
      outside_before:true,horizontal_end:assertHorizontalEnd(images.horizontal_end,initial),vertical_end:assertVerticalEnd(images.vertical_end)};
    for(const [reference,name] of [['initial_unhover','pointer_only'],['x12','clipped_pointer_only'],['x12','x12_hover_restored'],
      ['outside_before','outside_x'],['x12_unhover','vertical_top_restore'],['horizontal_end','horizontal_end_repeat'],
      ['initial_hover','horizontal_top_restore'],['initial_hover','horizontal_top_repeat'],['vertical_end','vertical_end_repeat'],
      ['initial_unhover','vertical_top_return'],['initial_unhover','vertical_top_repeat']])
      measurements[name]=assertUnchanged(images[reference],images[name]);
    report.initial=copy(initial);
    Object.assign(report.checks,{anonymous_pointer_no_redraw:copy(measurements.pointer_only),initial_hover:copy(measurements.initial_hover),
      horizontal:copy(measurements.x12),clipping:assertClipping(images.initial_unhover,images.x12_unhover,initial),
      clipped_pointer:copy(measurements.x12_unhover),hover_after_scroll:assertHover(images.x12_unhover,images.x12,initial),
      vertical_propagation:copy(measurements.y12),outside_inner_wheel:copy(measurements.outside_x),
      horizontal_endpoint:copy(measurements.horizontal_end),vertical_endpoint:copy(measurements.vertical_end)});
    for(const [name,image] of Object.entries(images)) {
      report.captures[name].rgba_sha256=createHash('sha256').update(image.data).digest('hex');
      report.captures[name].measurement=copy(measurements[name]);
    }
    report.negative_controls=scrollableNegativeControls(images,initial);bindControls(report);
    pixelProfileBaseline={report,images};
  }
  return {report:copy(pixelProfileBaseline.report),images:{...pixelProfileBaseline.images}};
}

test('recompute a complete synthetic pixel profile and all nine controls from real RGBA bytes',()=>{
  const {report,images}=pixelProfile(),before=copy(report);
  const verified=validateScrollablePixels(report,images);
  assert.equal(verified.status,'passed');assert.equal(verified.capture_count,19);
  assert.equal(verified.checked_rgba_pixels,4750000);assert.equal(verified.full_image_recoveries,11);
  assert.deepEqual(verified.negative_controls.map(c=>c.name),SCROLLABLE_NEGATIVE_CONTROLS);
  assert.deepEqual(report,before,'Pixel revalidation must never rewrite the report');
  assert.equal(validateScrollableEvidence(report).runtime,'rust','Synthetic pixel report remains structurally valid');
});

test('reject unchanged stale reports paired with unrelated pixels, even if PNG metadata would match',()=>{
  const {report,images}=pixelProfile();
  images.x12={...images.x12,data:images.x12.data.slice()};images.x12.data[0]^=1;
  assert.throws(()=>validateScrollablePixels(report,images),/x12: complete decoded RGBA SHA-256/);
});

test('reject unchanged pixels paired with stale declared measurements despite correct RGBA hashes',()=>{
  const {report,images}=pixelProfile();
  report.checks.hover_after_scroll.unhovered_rgba[0]--;
  assert.throws(()=>validateScrollablePixels(report,images),/hover_after_scroll: declared check must match recomputed/);
});

test('reject same pixels reused as all captures with matching freshly declared RGBA hashes',()=>{
  const {report,images}=pixelProfile(),image=images.initial_unhover;
  for(const name of Object.keys(images)){images[name]=image;report.captures[name].rgba_sha256=report.captures.initial_unhover.rgba_sha256;}
  bindControls(report);
  assert.throws(()=>validateScrollablePixels(report,images),/Hover must visibly/);
});

test('reject pixel changes that update hashes but fail full-image recovery',()=>{
  const {report,images}=pixelProfile();
  images.horizontal_top_repeat={...images.horizontal_top_repeat,data:images.horizontal_top_repeat.data.slice()};
  images.horizontal_top_repeat.data[0]^=1;
  report.captures.horizontal_top_repeat.rgba_sha256=createHash('sha256').update(images.horizontal_top_repeat.data).digest('hex');
  report.captures.horizontal_top_repeat.measurement.rgba_sha256=report.captures.horizontal_top_repeat.rgba_sha256;bindControls(report);
  assert.throws(()=>validateScrollablePixels(report,images),/Complete rendered image must remain unchanged/);
});

test('decoded image validation requires every capture, complete typed bytes and declared dimensions',()=>{
  const {report,images}=pixelProfile();
  for(const [label,mutate] of [
    ['missing capture',value=>delete value.x12],['extra image',value=>value.unknown=value.x12],
    ['no decoded bytes',value=>value.x12={width:500,height:500}],
    ['ordinary array',value=>value.x12={...value.x12,data:[]}],
    ['truncated bytes',value=>value.x12={...value.x12,data:value.x12.data.slice(0,-4)}],
    ['cropped dimensions',value=>value.x12={...value.x12,width:499}],
  ]) {
    const changed={...images};mutate(changed);assert.throws(()=>validateScrollablePixels(report,changed),undefined,label);
  }
});

test('negative controls are independently rerun against decoded images',()=>{
  const {report,images}=pixelProfile();report.negative_controls[0].rejected=false;
  assert.throws(()=>validateScrollablePixels(report,images),/nine negative controls must be recomputed/);
});

test('coordinated stale report/capture measurements cannot override unchanged actual screenshot features',()=>{
  const {report,images}=pixelProfile();
  report.checks.horizontal.deltas.horizontal.dx=0;
  report.captures.x12.measurement=copy(report.checks.horizontal);
  assert.throws(()=>validateScrollablePixels(report,images),/x12: declared capture measurement must match actual decoded pixel predicate/);
});
