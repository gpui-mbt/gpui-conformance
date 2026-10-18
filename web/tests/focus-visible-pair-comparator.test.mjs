import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {deflateSync} from 'node:zlib';
import {mkdtemp,writeFile,readFile,rm,symlink} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {spawnSync} from 'node:child_process';
import {HISTORICAL_PAIR,PAIR_REVISION,FOCUS_CANDIDATE,FOCUS_PROFILE,FOCUS_SEQUENCE,FOCUS_CAPTURES,assertPairedProvenance,
  pairedProvenanceNegativeControls,expectedRuntimeFiles,validateFocusVisibleEvents,
  validateFocusVisibleEvidence,validateFocusVisiblePixels,loadFocusVisibleEvidence,compareFocusVisibleBehavior,assertCurrentFocusVisibleBuild,validateFocusVisibleRelations}
  from './focus-visible-pair-comparator.mjs';
import {focusVisibleNegativeControls} from './focus-visible-comparator.mjs';

// SYNTHETIC FIXTURES ONLY. No browser/runtime/oracle evidence is generated here.
// Artificial geometric ink tests sensitivity, never either renderer's text.
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const clone=value=>structuredClone(value);
const ROOT=[243,244,246,255],PANEL=[219,234,254,255],BLUE=[37,99,235,255],HOVER=[29,78,216,255],
  YELLOW=[251,191,36,255],GREEN=[16,185,129,255];
const blob='c5b3d5dfec3a189d088a621baff55eb55a121b6c',source='crates/gpui/examples/focus_visible.rs';
const rect=(image,x,y,w,h,color)=>{for(let yy=y;yy<y+h;yy++)for(let xx=x;xx<x+w;xx++)image.data.set(color,4*(yy*image.width+xx));};
function syntheticImage({focus,modality,hover},message,variant=0) {
  const image={width:800,height:600,data:new Uint8Array(800*600*4)};
  rect(image,0,0,800,600,ROOT);rect(image,32,95,736,58,PANEL);
  const ink=(x,y,w,color)=>{for(let dx=0;dx<w;dx+=7)rect(image,x+dx,y,3,9,color);};
  ink(32+variant,43,245,[17,24,39,255]);ink(48,116,140+message*21,[30,58,138,255]);
  for(const [index,y] of [208,319,430].entries()) {
    const n=index+1,fill=hover===n&&modality==='mouse'?HOVER:BLUE;
    ink(32,y-23,250+index*35,[55,65,81,255]);rect(image,32,y,736,64,fill);
    const ring=focus!==n?null:n===1?YELLOW:n===2?(modality==='keyboard'?GREEN:null):modality==='keyboard'?GREEN:YELLOW;
    if(ring){rect(image,32,y,736,4,ring);rect(image,32,y+60,736,4,ring);rect(image,32,y,4,64,ring);rect(image,764,y,4,64,ring);}
    ink(190,y+27,340,[255,255,255,255]);
  }
  return image;
}
const MESSAGE={initial:0,tab1:4,tab2:4,tab3:4,wrap1:4,reverse3:5,reverse2:5,reverse1:5,reverse_wrap3:5,
  click1:1,click2:2,click3:3,down2:3,outside_up2:3,key2:3,mouse_hover2:3,hover_suppressed2:3,keyboard_wheel2:3,
  keyboard_release2:3,move2:3,modifier_only2:3,next_after_move3:4,root_reset:4,root_tab1:4,enter_down1:1,enter_up1:1,
  space_before2:4,space_down2:4,space_up2:2,activation_before3:4,activation3:3,stale_key_reset:3,
  stale_key_before:4,stale_key_after:4,stale_focus_before:4,stale_focus_root:4,stale_focus_return2:4,
  stale_focus_after:4,focus_generation_next3:4,mixed_activation_reset:4,mixed_activation_before1:4,
  mixed_activation_up1:1,mixed_activation_cleanup1:1};
const bytesFor=label=>Buffer.from('SYNTHETIC TEST ARTIFACT ONLY: '+label);
function provenance() {
  const build={upstream:{repository:'zed-industries/zed',revision:'5a5fbe79917971a4d52a96b6ddb04da198a5012e'},moonbit:clone(FOCUS_CANDIDATE),
    lab_revision:'b'.repeat(40),lab_tracked_dirty:false,rust_bundled:true,implemented:['focus_visible'],rust_implemented:['focus_visible'],
    implemented_sources:{focus_visible:{source,source_blob:blob}},runtime_sha256_by_example:{focus_visible:sha(bytesFor('moonbit/focus_visible.mjs'))},
    rust:{source_modified:false,packaging:{upstream_files_modified:false},files:Object.fromEntries(['focus_visible.js','focus_visible_bg.wasm','host.mjs'].map(f=>[f,sha(bytesFor('rust/'+f))]))},
    moonbit_host_files_sha256:Object.fromEntries(['moonbit/host.mjs','moonbit/render.mjs','moonbit/focus-visible-host.mjs','load-timing.mjs'].map(f=>[f,sha(bytesFor(f))])),
    font_sha256_by_file:Object.fromEntries(['IBMPlexSans-Regular.ttf','IBMPlexSans-SemiBold.ttf'].map(f=>[f,sha(bytesFor('moonbit/'+f))]))};
  const catalog={upstream:clone(build.upstream),moonbit:clone(build.moonbit),examples:[{id:'focus_visible',moonbit:'implemented',source,source_blob:blob,width:800,height:600}]};
  return {build,catalog};
}
// Minimal lossless PNG encoder for fixture bytes only; production independently
// decodes real browser PNGs using Pillow, rather than trusting this encoder.
const crcTable=Array.from({length:256},(_,n)=>{for(let k=0;k<8;k++)n=n&1?0xedb88320^(n>>>1):n>>>1;return n>>>0;});
function chunk(type,data) {const label=Buffer.from(type),body=Buffer.concat([label,data]),out=Buffer.alloc(data.length+12);out.writeUInt32BE(data.length);body.copy(out,4);
  let crc=0xffffffff;for(const b of body)crc=crcTable[(crc^b)&255]^(crc>>>8);out.writeUInt32BE((crc^0xffffffff)>>>0,out.length-4);return out;}
function png(image) {
  const header=Buffer.alloc(13);header.writeUInt32BE(image.width);header.writeUInt32BE(image.height,4);header[8]=8;header[9]=6;
  const rows=Buffer.alloc((image.width*4+1)*image.height);
  for(let y=0;y<image.height;y++)Buffer.from(image.data.buffer,image.data.byteOffset+y*image.width*4,image.width*4).copy(rows,y*(image.width*4+1)+1);
  return Buffer.concat([Buffer.from('89504e470d0a1a0a','hex'),chunk('IHDR',header),chunk('IDAT',deflateSync(rows)),chunk('IEND',Buffer.alloc(0))]);
}
let shared;
function fixtures() {
  if(shared)return shared;
  const sides={},retained={};
  for(const [runtime,variant] of [['rust',0],['moonbit',1]]) {
    const {build,catalog}=provenance(),manifest_bytes=Buffer.from(JSON.stringify(build)),catalog_bytes=Buffer.from(JSON.stringify(catalog));
    const report={runtime,status:'SYNTHETIC TEST FIXTURE ONLY',candidate:'implemented',comparison:'not_run',errors:[],console:[],
      profile_revision:PAIR_REVISION,profile:clone(FOCUS_PROFILE),canvas:{bounds:{x:0,y:0,width:800,height:600},backing:{width:800,height:600}},build,catalog,
      source:assertPairedProvenance(build,catalog),provenance_negative_controls:pairedProvenanceNegativeControls(build,catalog),
      build_manifest_file:`focus-visible-${runtime}-build-manifest.json`,build_manifest_sha256:sha(manifest_bytes),
      catalog_file:`focus-visible-${runtime}-catalog.json`,catalog_sha256:sha(catalog_bytes),
      initial_transport:{active_tag:'TEXTAREA',canvas_tab_index:-1,textarea:{readOnly:false,disabled:false,isContentEditable:false,
        inline_style:{position:'fixed',left:'0px',top:'0px',width:'1px',height:'1px',opacity:'0',fontSize:'16px'},
        style:{position:'fixed',opacity:'0'},bounds:{x:0,y:0,width:3,height:3}}},
      startup_events:[],operation_start:0,environment:{browser:'SYNTHETIC-NO-BROWSER',platform:'test',node:process.version},captures:{},checks:{fabricated:'ignored'},requests:[],served_requests:[],runtime_responses:[],operations:[],events:[]};
    let time=0;
    for(const expected of FOCUS_SEQUENCE.operations) {
      const events=expected.expected.map(event=>({...event,trusted:true,target:event.type.startsWith('key')||event.type==='beforeinput'?'TEXTAREA':'CANVAS',
        pointerType:'mouse',deltaMode:0,defaultPrevented:event.defaultPrevented??true,time:time++}));
      report.operations.push({...clone(expected),events,post_delivery_animation_frames:2});report.events.push(...events);
    }
    const images={},stableImages={},pngs={},assets={},cache=new Map();
    for(const [name,spec] of Object.entries(FOCUS_SEQUENCE.captures)) {
      assert(Object.hasOwn(MESSAGE,name),'Fixture must independently specify message identity');
      const key=JSON.stringify([spec.state,MESSAGE[name]]);
      let cached=cache.get(key);if(!cached){const image=syntheticImage(spec.state,MESSAGE[name],variant);cached={image,bytes:png(image)};cache.set(key,cached);}
      const {image,bytes}=cached;images[name]=image;stableImages[name]=image;
      const file=`focus-visible-${runtime}-${name}-dpr1.png`,stability_file=`focus-visible-${runtime}-${name}-stable-first-dpr1.png`;
      pngs[file]=bytes;pngs[stability_file]=bytes;
      report.captures[name]={file,stability_file,png_sha256:sha(bytes),rgba_sha256:sha(image.data),stability_png_sha256:sha(bytes),
        stability_rgba_sha256:sha(image.data),width:800,height:600,after_operation:spec.after_operation,
        measurement:{state:'Fabricated status/checks have no authority'},stable:false};
    }
    report.negative_controls=focusVisibleNegativeControls(images,report.operations);
    report.negative_controls_capture_sha256=Object.fromEntries(FOCUS_CAPTURES.map(name=>[name,sha(images[name].data)]));
    for(const [path,digest] of Object.entries(expectedRuntimeFiles(build,runtime))) {
      const url='http://127.0.0.1:10000/gpui-conformance/'+path,file=`focus-visible-${runtime}-asset-${path.replaceAll('/','_')}.bin`;
      report.requests.push({url,status:200});report.served_requests.push({url:'/gpui-conformance/'+path,status:200,sha256:digest});
      report.runtime_responses.push({url,status:200,sha256:digest,file});assets[file]=bytesFor(path);
    }
    sides[runtime]=report;retained[runtime]={images,stableImages,pngs,assets,manifest_bytes,catalog_bytes};
  }
  return shared={sides,retained};
}
async function persist(directory,report,evidence) {
  await writeFile(join(directory,report.build_manifest_file),evidence.manifest_bytes);await writeFile(join(directory,report.catalog_file),evidence.catalog_bytes);
  for(const [name,bytes] of Object.entries({...evidence.assets,...evidence.pngs}))await writeFile(join(directory,name),bytes);
  await writeFile(join(directory,`focus-visible-${report.runtime}-result-dpr1.json`),JSON.stringify(report));
}

test('fixed profile preserves all 43 captures, 74 operations, mixed activation, ABA and modifier-only checks',()=>{
  assert.equal(FOCUS_CAPTURES.length,43);assert.equal(FOCUS_SEQUENCE.operations.length,74);
  assert.deepEqual(Object.keys(MESSAGE),FOCUS_CAPTURES);
  assert.equal(FOCUS_SEQUENCE.captures.stale_focus_after.state.focus,2);
  assert.equal(FOCUS_SEQUENCE.captures.modifier_only2.state.modality,'mouse');
  assert(FOCUS_SEQUENCE.same.some(pair=>pair.join('/')==='click1/mixed_activation_up1'));
  assert(FOCUS_SEQUENCE.unchanged.some(pair=>pair.join('/')==='mixed_activation_up1/mixed_activation_cleanup1'));
});
for(const [name,mutate] of [
  ['wrong source blob',(b,c)=>{c.examples[0].source_blob='0'.repeat(40);}],
  ['wrong built source',b=>{b.implemented_sources.focus_visible.source_blob='0'.repeat(40);}],
  ['wrong candidate engine pin',b=>{b.moonbit.revision='0'.repeat(40);}],
  ['wrong candidate tree',b=>{b.moonbit.tree='0'.repeat(40);}],
  ['dirty lab',b=>{b.lab_tracked_dirty=true;}],['uncommitted lab',b=>{b.lab_revision='dirty';}],
  ['missing candidate',b=>{b.implemented=[];}],['missing Rust',b=>{b.rust_implemented=[];}],
  ['changed Rust',b=>{b.rust.source_modified=true;}],['missing host',b=>{delete b.moonbit_host_files_sha256['moonbit/render.mjs'];}],
  ['missing font',b=>{delete b.font_sha256_by_file['IBMPlexSans-SemiBold.ttf'];}],
])test(`paired provenance rejects ${name}`,()=>{const {build,catalog}=provenance();mutate(build,catalog);assert.throws(()=>assertPairedProvenance(build,catalog));});

test('all paired provenance controls are recomputed against a valid unchanged fixture',()=>{
  const {build,catalog}=provenance(),before=clone({build,catalog});const controls=pairedProvenanceNegativeControls(build,catalog);
  assert.equal(controls.length,11);assert(controls.every(c=>c.rejected));assert.deepEqual({build,catalog},before);
});

test('independent retained metadata validates while fabricated status/check measurements have no authority',()=>{
  const {sides}=fixtures();for(const runtime of ['rust','moonbit'])assert.equal(validateFocusVisibleEvidence(sides[runtime],runtime).capture_count,43);
});
for(const [name,mutate] of [
  ['wrong runtime',r=>{r.runtime='moonbit';}],['historical source relabel',r=>{r.candidate='not_implemented';}],
  ['failed runtime',r=>{r.failure='runtime failed';}],['runtime console errors',r=>{r.console.push({type:'error',text:'bad'});}],
  ['missing transport',r=>{delete r.initial_transport;}],['missing textarea',r=>{r.initial_transport.textarea=null;}],
  ['readonly textarea',r=>{r.initial_transport.textarea.readOnly=true;}],['disabled textarea',r=>{r.initial_transport.textarea.disabled=true;}],
  ['visible transport',r=>{r.initial_transport.textarea.style.opacity='1';}],
  ['oversized transport',r=>{r.initial_transport.textarea.bounds.width=800;}],['wrong inline transport',r=>{r.initial_transport.textarea.inline_style.width='800px';}],
  ['wrong active transport',r=>{r.initial_transport.active_tag='BODY';}],['DOM tab-stop canvas',r=>{r.initial_transport.canvas_tab_index=0;}],
  ['wrong viewport',r=>{r.profile.width=801;}],['scaled canvas',r=>{r.canvas.bounds.width=799;}],
  ['missing capture',r=>{delete r.captures.modifier_only2;}],['wrong capture operation prefix',r=>{r.captures.tab1.after_operation++;}],
  ['wrong filename',r=>{r.captures.initial.file='../escape.png';}],['missing stable sample',r=>{delete r.captures.initial.stability_file;}],
  ['served runtime hash',r=>{r.served_requests[0].sha256='0'.repeat(64);}],
  ['wrong actual runtime',r=>{r.runtime_responses[0].sha256='0'.repeat(64);}],
  ['missing runtime response',r=>{r.runtime_responses.shift();}],['wrong source record',r=>{r.source.source_blob='0'.repeat(40);}],
  ['fabricated negative controls',r=>{r.provenance_negative_controls[0].rejected=false;}],
])test(`paired metadata rejects ${name}`,()=>{const r=clone(fixtures().sides.rust);mutate(r);assert.throws(()=>validateFocusVisibleEvidence(r,'rust'));});

for(const [name,mutate] of [
  ['wrong event order',r=>{r.operations.reverse();}],['missing operation',r=>{r.operations.pop();}],
  ['missing delivery',r=>{r.operations[0].events=[];}],['untrusted delivery',r=>{r.operations[0].events[0].trusted=false;}],
  ['wrong pointer type',r=>{r.operations[0].events[0].pointerType='pen';}],
  ['wrong event type',r=>{r.operations[0].events[0].type='pointerdown';}],
  ['wrong pointer modifier',r=>{r.operations[0].events[0].ctrlKey=true;}],
  ['wrong key modifier',r=>{r.operations[1].events[0].altKey=true;}],
  ['wrong key label',r=>{r.operations[1].events[0].key='Enter';}],
  ['wrong key code',r=>{r.operations[1].events[0].code='Enter';}],
  ['repeat key',r=>{r.operations[1].events[0].repeat=true;}],
  ['wrong keyboard transport',r=>{r.operations[1].events[0].target='CANVAS';}],
  ['wrong pointer button',r=>{r.operations.find(o=>o.name==='click1_down').events[0].button=2;}],
  ['wrong button state',r=>{r.operations.find(o=>o.name==='outside_up2_move').events[0].buttons=0;}],
  ['wrong wheel mode',r=>{r.operations.find(o=>o.name==='keyboard_wheel').events[0].deltaMode=1;}],
  ['unprevented wheel',r=>{r.operations.find(o=>o.name==='keyboard_wheel').events[0].defaultPrevented=false;}],
  ['wrong wheel modifier',r=>{r.operations.find(o=>o.name==='keyboard_wheel').events[0].metaKey=true;}],
  ['missing full event log',r=>{r.events.pop();}],['rewritten expected events',r=>{r.operations[1].expected[0].key='Enter';}],
])test(`fixed event oracle rejects ${name}`,()=>{const r=clone(fixtures().sides.rust);mutate(r);assert.throws(()=>validateFocusVisibleEvents(r,'rust'));});


for(const [name,change] of [
  ['wrong input intent',{inputType:'insertText'}],['composing Enter',{isComposing:true}],
  ['untrusted beforeinput',{trusted:false}],['unprevented beforeinput',{defaultPrevented:false}],
  ['noncancelable beforeinput',{cancelable:false}],['unexpected beforeinput data',{data:'x'}],
  ['wrong beforeinput target',{target:'CANVAS'}],
])test(`trusted Enter beforeinput rejects ${name}`,()=>{
  const r=clone(fixtures().sides.rust),event=r.operations.find(op=>op.name==='enter_down1_event').events[1];
  Object.assign(event,change);assert.throws(()=>validateFocusVisibleEvents(r,'rust'));
});


test('startup Chromium pointer evidence is retained as a bounded prefix, never discarded or treated as a profile operation',()=>{
  const r=clone(fixtures().sides.rust);
  const event={type:'pointermove',trusted:true,target:'BODY',time:0,defaultPrevented:false,x:0,y:0,button:-1,buttons:0,pointerType:'mouse',
    shiftKey:false,ctrlKey:false,altKey:false,metaKey:false};
  r.startup_events=[event];r.operation_start=1;r.events.unshift(event);
  assert.equal(validateFocusVisibleEvents(r).startup_event_count,1);
  for(const change of [{type:'pointerdown'},{trusted:false},{target:'IFRAME'},{x:8},{buttons:1},{ctrlKey:true},{time:-1}]) {
    const bad=clone(r);Object.assign(bad.startup_events[0],change);assert.throws(()=>validateFocusVisibleEvents(bad));
  }
  for(const mutate of [v=>{v.operation_start=0;},v=>{v.events.shift();},v=>{delete v.startup_events;},
    v=>{v.startup_events.push(clone(event));v.operation_start=2;v.events.unshift(clone(event));}]) {
    const bad=clone(r);mutate(bad);assert.throws(()=>validateFocusVisibleEvents(bad));
  }
});

test('report-only fabricated pass cannot establish any pair without independent decoded images',()=>{
  const {sides}=fixtures();const r=clone(sides.rust);r.status='passed';r.checks={status:'passed'};
  assert.throws(()=>compareFocusVisibleBehavior(r,sides.moonbit));
  for(const runtime of ['rust','moonbit']) {
    const evidence={...fixtures().retained};delete evidence[runtime];
    assert.throws(()=>compareFocusVisibleBehavior(r,sides.moonbit,evidence));
  }
  assert.throws(()=>validateFocusVisiblePixels(r,{},{}));
});

test('altered decoded bytes and invalid actual decoded dimensions fail before claimed measurements',()=>{
  const {sides,retained}=fixtures(),r=clone(sides.rust),e=retained.rust;
  const corrupted={...e.images,initial:{...e.images.initial,data:e.images.initial.data.slice()}};corrupted.initial.data[0]^=1;
  assert.throws(()=>validateFocusVisiblePixels(r,corrupted,e.stableImages),/RGBA digest/);
  const wrongSize={...e.images,initial:{...e.images.initial,width:799}};
  assert.throws(()=>validateFocusVisiblePixels(r,wrongSize,e.stableImages),/width/);
  const badStable={...e.stableImages,initial:{...e.images.initial,data:e.images.initial.data.slice()}};badStable.initial.data[0]^=1;
  assert.throws(()=>validateFocusVisiblePixels(r,e.images,badStable),/RGBA digest/);
});


test('current clean checkout pins reject historic reports even with matching fabricated paired statuses',()=>{
  const {sides,retained}=fixtures(),r=sides.rust;
  const current={revision:r.build.lab_revision,trackedDirty:false,catalogBytes:retained.rust.catalog_bytes};
  assert.doesNotThrow(()=>assertCurrentFocusVisibleBuild(r,current));
  for(const change of [{revision:'0'.repeat(40)},{trackedDirty:true},{catalogBytes:Buffer.from('{}')}])
    assert.throws(()=>assertCurrentFocusVisibleBuild(r,{...current,...change}));
});

test('rehashed wrong geometry and first-stable-only changes cannot hide behind fabricated measurements',()=>{
  const {sides,retained}=fixtures(),r=clone(sides.rust),e=retained.rust;
  const wrong={...e.images,initial:{...e.images.initial,data:e.images.initial.data.slice()}};
  wrong.initial.data.set(BLUE,4*(208*800+31));r.captures.initial.rgba_sha256=sha(wrong.initial.data);
  assert.throws(()=>validateFocusVisiblePixels(r,wrong,e.stableImages),/geometry/);
  const report=clone(sides.rust),stable={...e.stableImages,initial:{...e.images.initial,data:e.images.initial.data.slice()}};
  stable.initial.data.set([15,20,30,255],4*(43*800+32));report.captures.initial.stability_rgba_sha256=sha(stable.initial.data);
  assert.throws(()=>validateFocusVisiblePixels(report,e.images,stable),/unchanged/);
});

for(const kind of ['same','different','unchanged'])for(const [before,after] of FOCUS_SEQUENCE[kind])
  test(`independent within-renderer ${kind} relation rejects fabricated ${before}/${after} effect`,()=>{
    const original=fixtures().retained.rust.images;
    const changed={...original,[after]:{...original[after],data:original[after].data.slice()}};
    if(kind==='different') {
      for(let y=95;y<153;y++)changed[after].data.set(original[before].data.subarray(4*(y*800+32),4*(y*800+768)),4*(y*800+32));
    } else {
      for(let x=500;x<530;x++)changed[after].data.set([0,0,0,255],4*(120*800+x));
    }
    assert.throws(()=>validateFocusVisibleRelations(changed));
  });

test('actual PNG bytes are independently decoded for both complete stable samples; bounded pair allows measured raster differences',async()=>{
  const {sides,retained}=fixtures(),directory=await mkdtemp(join(tmpdir(),'focus-SYNTHETIC-pair-'));
  try {
    const loaded={};for(const runtime of ['rust','moonbit']){await persist(directory,sides[runtime],retained[runtime]);loaded[runtime]=await loadFocusVisibleEvidence(directory,sides[runtime]);}
    const result=compareFocusVisibleBehavior(sides.rust,sides.moonbit,loaded);
    assert.equal(result.status,'passed');assert.equal(result.comparison,'independently_decoded_bounded_focus_behavior');
    assert.equal(result.profile_revision,PAIR_REVISION);
    assert.equal(result.decoded_pixel_validation.rust.capture_count,43);assert.equal(result.decoded_pixel_validation.moonbit.samples_per_capture,2);
    assert.equal(result.cross_renderer_image_observations.verdict,'not_a_parity_check');
    assert(result.cross_renderer_image_observations.captures.every(c=>c.different_pixels>0));
    assert.equal(result.keyboard_transport.rust,'Hidden TEXTAREA');
  } finally {await rm(directory,{recursive:true,force:true});}
});

test('retained reads reject altered PNG/runtime bytes, false dimensions, path traversal and symlink escape',async()=>{
  const {sides,retained}=fixtures(),directory=await mkdtemp(join(tmpdir(),'focus-SYNTHETIC-tamper-'));
  const r=clone(sides.rust),e=retained.rust;
  try {
    await persist(directory,r,e);
    const file=r.captures.initial.file,original=e.pngs[file];
    await writeFile(join(directory,file),Buffer.from('not a PNG'));
    await assert.rejects(loadFocusVisibleEvidence(directory,r),/retained bytes hash/);await writeFile(join(directory,file),original);
    const small=png({width:1,height:1,data:Uint8Array.from(ROOT)});await writeFile(join(directory,file),small);r.captures.initial.png_sha256=sha(small);
    await assert.rejects(loadFocusVisibleEvidence(directory,r),/Decoded dimensions/);await writeFile(join(directory,file),original);r.captures.initial.png_sha256=sha(original);
    r.captures.initial.file='../escape.png';await assert.rejects(loadFocusVisibleEvidence(directory,r),/Local retained filename/);r.captures.initial.file=file;
    await rm(join(directory,file));await symlink('/etc/hosts',join(directory,file));await assert.rejects(loadFocusVisibleEvidence(directory,r),/escape evidence/);
    await rm(join(directory,file));await writeFile(join(directory,file),original);
    const asset=r.runtime_responses[0].file;await writeFile(join(directory,asset),Buffer.from('tampered runtime'));
    await assert.rejects(loadFocusVisibleEvidence(directory,r),/retained bytes hash/);
  } finally {await rm(directory,{recursive:true,force:true});}
});

test('paired CLI fails closed and writes diagnostic JSON when either renderer is missing',async()=>{
  const directory=await mkdtemp(join(tmpdir(),'focus-SYNTHETIC-missing-'));
  try {
    const child=spawnSync(process.execPath,[resolve('web/tests/compare-focus-visible-results.mjs'),directory],{encoding:'utf8'});
    assert.equal(child.status,1);const result=JSON.parse(await readFile(join(directory,'focus-visible-pair-result-dpr1.json'),'utf8'));
    assert.equal(result.status,'failed');assert.match(result.failure,/ENOENT/);assert.deepEqual(result.inputs,{});
  } finally {await rm(directory,{recursive:true,force:true});}
});


test('current paired profile requires new exact identity and rejects unversioned or historical reuse',()=>{
  assert.equal(PAIR_REVISION,'focus_visible_paired_v1_popover_pin');
  assert.deepEqual(FOCUS_CANDIDATE,{repository:'gpui-mbt/gpui.mbt',
    revision:'e160f5ec7bf0c6f43738d0bdcf837098299d5569',tree:'96d62ea12a6824ee20d04cb913191bc23a424522'});
  assert.deepEqual(HISTORICAL_PAIR,{revision:null,candidate:{repository:'gpui-mbt/gpui.mbt',
    revision:'89108ad966c2d37b0cb44909b1aac3ecfa8e3c4a',tree:'dd5612a412d251b468c358a25baa0b0dd592c807'}});
  assert(Object.isFrozen(HISTORICAL_PAIR));assert(Object.isFrozen(HISTORICAL_PAIR.candidate));
  for(const runtime of ['rust','moonbit']) {
    const current=fixtures().sides[runtime];validateFocusVisibleEvidence(current,runtime);
    for(const revision of [undefined,HISTORICAL_PAIR.revision,'focus_visible_paired_other']) {
      const old=clone(current);
      if(revision===undefined)delete old.profile_revision;else old.profile_revision=revision;
      assert.throws(()=>validateFocusVisibleEvidence(old,runtime),/Exact current paired profile revision/);
    }
    for(const candidate of [HISTORICAL_PAIR.candidate,
      {...FOCUS_CANDIDATE,revision:HISTORICAL_PAIR.candidate.revision},
      {...FOCUS_CANDIDATE,tree:HISTORICAL_PAIR.candidate.tree}]) {
      const old=clone(current);old.build.moonbit=clone(candidate);old.catalog.moonbit=clone(candidate);
      assert.throws(()=>assertPairedProvenance(old.build,old.catalog),/Exact public candidate engine/);
      assert.throws(()=>validateFocusVisibleEvidence(old,runtime),'New labels cannot qualify historical or mixed core pins');
      delete old.profile_revision;
      assert.throws(()=>validateFocusVisibleEvidence(old,runtime),'Historical evidence remains historical');
    }
  }
});

test('capture harness emits the explicit profile identity only for implemented paired captures',async()=>{
  const harness=await readFile(new URL('./focus-visible-oracle-browser.mjs',import.meta.url),'utf8');
  assert.match(harness,/import \{PAIR_REVISION,assertPairedProvenance/);
  assert(harness.includes("if(paired){result.candidate='implemented';result.profile_revision=PAIR_REVISION;}"));
});
