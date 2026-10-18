import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile,realpath} from 'node:fs/promises';
import {resolve,join,basename,sep} from 'node:path';
import {spawnSync} from 'node:child_process';
import {FOCUS_VISIBLE,GEOMETRY,inspectState,assertImage,assertDelivery,assertPanelSame,
  assertPanelDifferent,assertUnchanged,focusVisibleNegativeControls} from './focus-visible-comparator.mjs';

// No private renderer state, claimed check status, or cross-renderer text/image
// equality is an oracle. The profile below is fixed independently of reports.
// Retained reports had no profile revision; this descriptor is never an active alternative.
export const HISTORICAL_PAIR=Object.freeze({revision:null,
  candidate:Object.freeze({repository:'gpui-mbt/gpui.mbt',
    revision:'89108ad966c2d37b0cb44909b1aac3ecfa8e3c4a',tree:'dd5612a412d251b468c358a25baa0b0dd592c807'})});
// Retired popover profile is provenance only, never an accepted current alternative.
export const POPOVER_PAIR=Object.freeze({revision:'focus_visible_paired_v1_popover_pin',
  candidate:Object.freeze({repository:'gpui-mbt/gpui.mbt',
    revision:'e160f5ec7bf0c6f43738d0bdcf837098299d5569',tree:'96d62ea12a6824ee20d04cb913191bc23a424522'})});
// Current source qualification requires fresh independent captures and byte verification.
export const PAIR_REVISION='focus_visible_paired_v2_pattern_pin';
export const FOCUS_CANDIDATE=Object.freeze({repository:'gpui-mbt/gpui.mbt',
  revision:'3bea4fea2dd54768a3859c7c881dda2a60fa5bbd',tree:'25b0647f974d8b6ffd46c1a15c7eeb5ef7e4fe85'});
export const FOCUS_PROFILE=Object.freeze({width:800,height:600,dpr:1,input:'Trusted Chromium mouse, keyboard and pixel wheel'});
const sha=data=>createHash('sha256').update(data).digest('hex');
const HASH=/^[0-9a-f]{64}$/;
const object=(value,label)=>assert(value&&typeof value==='object'&&!Array.isArray(value),`${label}: object required`);
const sameKeys=(value,keys,label)=>assert.deepEqual(Object.keys(value).sort(),[...keys].sort(),`${label}: exact named evidence required`);
const hash=(value,label)=>assert(typeof value==='string'&&HASH.test(value),`${label}: SHA256 required`);
const clone=value=>structuredClone(value);

export function assertPairedProvenance(build,catalog) {
  assert.equal(build.upstream?.repository,'zed-industries/zed','Pinned upstream repository');
  assert.equal(build.upstream?.revision,FOCUS_VISIBLE.revision,'Pinned unchanged upstream revision');
  assert.deepEqual(build.moonbit,FOCUS_CANDIDATE,'Exact public candidate engine revision and tree required');
  assert.equal(build.lab_tracked_dirty,false,'Clean lab build required');
  assert.match(build.lab_revision||'',/^[0-9a-f]{40}$/,'Committed lab revision required');
  assert.equal(build.rust_bundled,true,'Real Rust WASM bundle required');
  assert.equal(build.rust?.source_modified,false,'Unchanged Rust source required');
  assert.equal(build.rust?.packaging?.upstream_files_modified,false,'Unmodified upstream archive required');
  assert.deepEqual(catalog.upstream,build.upstream,'Catalog/build upstream pin');
  assert.deepEqual(catalog.moonbit,build.moonbit,'Catalog/build candidate pin');
  const entries=catalog.examples.filter(entry=>entry.id==='focus_visible');
  assert.equal(entries.length,1,'Exactly one implemented catalog identity required');
  const entry=entries[0];
  for(const [key,value] of Object.entries({moonbit:'implemented',source:FOCUS_VISIBLE.source,
    source_blob:FOCUS_VISIBLE.sourceBlob,width:800,height:600}))assert.equal(entry[key],value,`Current catalog ${key}`);
  assert(build.implemented?.includes('focus_visible'),'Compiled MoonBit example required');
  assert(build.rust_implemented?.includes('focus_visible'),'Compiled Rust example required');
  assert.deepEqual(build.implemented_sources?.focus_visible,{source:FOCUS_VISIBLE.source,source_blob:FOCUS_VISIBLE.sourceBlob},'Built current source/blob identity');
  hash(build.runtime_sha256_by_example?.focus_visible,'Compiled MoonBit module');
  for(const file of ['focus_visible.js','focus_visible_bg.wasm','host.mjs'])hash(build.rust.files?.[file],`Rust ${file}`);
  for(const file of ['moonbit/host.mjs','moonbit/render.mjs','moonbit/focus-visible-host.mjs','load-timing.mjs'])
    hash(build.moonbit_host_files_sha256?.[file],`Candidate transport dependency ${file}`);
  for(const file of ['IBMPlexSans-Regular.ttf','IBMPlexSans-SemiBold.ttf'])hash(build.font_sha256_by_file?.[file],`Font ${file}`);
  return {id:'focus_visible',source:FOCUS_VISIBLE.source,source_blob:FOCUS_VISIBLE.sourceBlob,
    upstream_revision:FOCUS_VISIBLE.revision,width:800,height:600,dpr:1,status:'paired_profile',candidate:'implemented'};
}
export function pairedProvenanceNegativeControls(build,catalog) {
  assertPairedProvenance(build,catalog);
  return [
    ['previous_uniform_list_baseline_core',b=>{b.moonbit={repository:'gpui-mbt/gpui.mbt',revision:'fc53cb382c66f68bfc1b3e1cc72d01056cd3c625',tree:'c9ec59c5fbdbd84548b7d6ffe2c99b8403509db9'};}],
    ['dirty_lab',b=>{b.lab_tracked_dirty=true;}],['wrong_upstream',b=>{b.upstream.revision='0'.repeat(40);}],
    ['modified_source',b=>{b.rust.source_modified=true;}],['modified_archive',b=>{b.rust.packaging.upstream_files_modified=true;}],
    ['wrong_example_blob',(_b,c)=>{c.examples.find(e=>e.id==='focus_visible').source_blob='0'.repeat(40);}],
    ['missing_runtime_hash',b=>{delete b.rust.files['focus_visible_bg.wasm'];}],
    ['missing_candidate',b=>{b.implemented=b.implemented.filter(id=>id!=='focus_visible');}],
    ['wrong_engine_pin',b=>{b.moonbit.revision='0'.repeat(40);}],['wrong_engine_tree',b=>{b.moonbit.tree='0'.repeat(40);}],
    ['missing_host_hash',b=>{delete b.moonbit_host_files_sha256['moonbit/focus-visible-host.mjs'];}],
  ].map(([name,mutate])=>{const b=clone(build),c=clone(catalog);mutate(b,c);
    assert.throws(()=>assertPairedProvenance(b,c),`${name}: negative control survived`);
    return {name,rejected:true,input:'Intentionally corrupted copy of retained current paired build provenance'};});
}

export function expectedRuntimeFiles(build,runtime) {
  if(runtime==='rust')return Object.fromEntries([
    ...Object.entries(build.rust.files).map(([file,digest])=>['rust/'+file,digest]),
    ['load-timing.mjs',build.moonbit_host_files_sha256['load-timing.mjs']]]);
  assert.equal(runtime,'moonbit','Recognized independent runtime');
  return {...build.moonbit_host_files_sha256,'moonbit/focus_visible.mjs':build.runtime_sha256_by_example.focus_visible,
    ...Object.fromEntries(['IBMPlexSans-Regular.ttf','IBMPlexSans-SemiBold.ttf'].map(file=>['moonbit/'+file,build.font_sha256_by_file[file]]))};
}

function makeProfile() {
  const operations=[],captures={},same=[],different=[],unchanged=[];
  let pointer={x:0,y:0},buttons=0;
  const mods={shiftKey:false,ctrlKey:false,altKey:false,metaKey:false};
  const op=(name,expected)=>operations.push({name,expected});
  const move=(name,x,y)=>{op(name,[{type:'pointermove',x,y,...mods,button:-1,buttons}]);pointer={x,y};};
  const mouse=(name,type,secondary=false)=>{buttons=type==='down'?(secondary?2:1):0;
    op(name,[{type:type==='down'?'pointerdown':'pointerup',...pointer,button:secondary?2:0,buttons,...mods}]);};
  const key=(name,label,type='press',shift=false)=>op(name,(type==='press'?['keydown','keyup']:[type==='down'?'keydown':'keyup'])
    .flatMap(type=>[ {type,key:label==='Space'?' ':label,code:label==='Space'?'Space':label==='Shift'?'ShiftLeft':label.length===1?'Key'+label.toUpperCase():label,...mods,shiftKey:shift,repeat:false,
      ...(label==='Enter'&&type==='keydown'?{defaultPrevented:false}:{})},
      ...(label==='Enter'&&type==='keydown'?[{type:'beforeinput',inputType:'insertLineBreak',data:null,isComposing:false,cancelable:true,defaultPrevented:true}]:[]) ]));
  const capture=(name,focus,modality='keyboard',hover=0)=>{captures[name]={state:{focus,modality,hover},after_operation:operations.length};};
  const tab=(name,focus,reverse=false)=>{
    if(reverse)key(name+'_shift_down','Shift','down',true);
    key(name+'_tab','Tab','press',reverse);if(reverse)key(name+'_shift_up','Shift','up');
    capture(name,focus,'keyboard',pointer.x>=32&&pointer.x<768?([208,319,430].findIndex(y=>pointer.y>=y&&pointer.y<y+64)+1):0);};
  const click=(name,button,secondary=false)=>{move(name+'_move',100,[240,351,462][button-1]);
    mouse(name+'_down','down',secondary);mouse(name+'_up','up',secondary);capture(name,button,'mouse',button);};
  const reset=(name='root_reset')=>{move(name+'_move',8,550);mouse(name+'_down','down');mouse(name+'_up','up');capture(name,0,'mouse');};
  move('initial_pointer',8,8);capture('initial',0,'mouse');
  for(const [name,focus] of [['tab1',1],['tab2',2],['tab3',3],['wrap1',1]])tab(name,focus);
  for(const [name,focus] of [['reverse3',3],['reverse2',2],['reverse1',1],['reverse_wrap3',3]])tab(name,focus,true);
  different.push(['initial','tab1'],['tab1','reverse3']);
  for(const name of ['tab2','tab3','wrap1'])same.push(['tab1',name]);
  for(const name of ['reverse2','reverse1','reverse_wrap3'])same.push(['reverse3',name]);
  for(const button of [1,2,3])click('click'+button,button);
  different.push(['click1','click2'],['click2','click3'],['click1','click3']);
  move('down2_move',100,351);mouse('down2_event','down');capture('down2',2,'mouse',2);same.push(['click3','down2']);
  move('outside_up2_move',8,550);mouse('outside_up2_event','up');capture('outside_up2',2,'mouse');same.push(['down2','outside_up2']);
  key('unrelated_key_reenables_ring','x');capture('key2',2);same.push(['click3','key2']);
  move('mouse_hover2_move',100,351);capture('mouse_hover2',2,'mouse',2);
  key('resting_pointer_key','x');capture('hover_suppressed2',2,'keyboard',2);unchanged.push(['key2','hover_suppressed2']);
  op('keyboard_wheel',[{type:'wheel',x:100,y:351,deltaX:0,deltaY:1,...mods}]);
  capture('keyboard_wheel2',2,'keyboard',2);unchanged.push(['hover_suppressed2','keyboard_wheel2']);
  key('unmatched_release_preserves_modality','z','up');capture('keyboard_release2',2,'keyboard',2);unchanged.push(['hover_suppressed2','keyboard_release2']);
  move('move2_event',101,351);capture('move2',2,'mouse',2);same.push(['hover_suppressed2','move2']);
  key('modifier_only_shift_down','Shift','down',true);key('modifier_only_shift_up','Shift','up');
  capture('modifier_only2',2,'mouse',2);unchanged.push(['move2','modifier_only2']);
  tab('next_after_move3',3);reset();same.push(['next_after_move3','root_reset']);tab('root_tab1',1);
  key('enter_down1_event','Enter','down');capture('enter_down1',1);same.push(['click1','enter_down1']);different.push(['root_tab1','enter_down1']);
  key('enter_up1_event','Enter','up');capture('enter_up1',1);same.push(['click1','enter_up1']);unchanged.push(['enter_down1','enter_up1']);
  tab('space_before2',2);key('space_down2_event','Space','down');capture('space_down2',2);same.push(['space_before2','space_down2']);
  key('space_up2_event','Space','up');capture('space_up2',2);same.push(['click2','space_up2']);different.push(['space_down2','space_up2']);
  tab('activation_before3',3);key('activation3_enter','Enter');capture('activation3',3);same.push(['click3','activation3']);
  reset('stale_key_reset');tab('stale_key_before',1);key('stale_key_space_down','Space','down');key('stale_key_interruption','x');key('stale_key_space_up','Space','up');
  capture('stale_key_after',1);same.push(['stale_key_before','stale_key_after']);
  tab('stale_focus_before',2);key('stale_focus_space_down','Space','down');
  move('stale_focus_root_move',8,550);mouse('stale_focus_root_down','down',true);mouse('stale_focus_root_up','up',true);
  capture('stale_focus_root',0,'mouse');same.push(['stale_focus_before','stale_focus_root']);
  click('stale_focus_return2',2,true);same.push(['stale_focus_before','stale_focus_return2']);
  key('stale_focus_space_up','Space','up');capture('stale_focus_after',2,'mouse',2);same.push(['stale_focus_before','stale_focus_after']);
  tab('focus_generation_next3',3);reset('mixed_activation_reset');tab('mixed_activation_before1',1);
  key('mixed_space_down','Space','down');key('mixed_enter_up','Enter','up');capture('mixed_activation_up1',1);
  same.push(['click1','mixed_activation_up1']);different.push(['mixed_activation_before1','mixed_activation_up1']);
  key('mixed_space_cleanup','Space','up');capture('mixed_activation_cleanup1',1);unchanged.push(['mixed_activation_up1','mixed_activation_cleanup1']);
  return {operations,captures,same,different,unchanged};
}
export const FOCUS_SEQUENCE=makeProfile();
export const FOCUS_CAPTURES=Object.freeze(Object.keys(FOCUS_SEQUENCE.captures));

export function validateFocusVisibleEvents(report,runtime=report.runtime) {
  assert(['rust','moonbit'].includes(runtime),'Independent renderer identity required');
  assert(Array.isArray(report.startup_events),'Complete observed startup prefix required');
  assert.equal(report.operation_start,report.startup_events.length,'Exact operation-start event index');
  assert(report.startup_events.length<=1,'Only the observed bounded Chromium initial-pointer startup is supported');
  for(const event of report.startup_events) {
    for(const [key,value] of Object.entries({type:'pointermove',trusted:true,x:0,y:0,button:-1,buttons:0,pointerType:'mouse',
      shiftKey:false,ctrlKey:false,altKey:false,metaKey:false}))assert.equal(event[key],value,`Startup pointer ${key}`);
    assert(['HTML','BODY','CANVAS','TEXTAREA'].includes(event.target),'Startup pointer has a known transport DOM target');
    assert.equal(typeof event.defaultPrevented,'boolean','Startup dispatch must be complete');
    assert(Number.isFinite(event.time)&&event.time>=0,'Startup timestamp required');
  }
  const expected=FOCUS_SEQUENCE.operations,delivered=[];
  assert.deepEqual(report.operations.map(op=>op.name),expected.map(op=>op.name),'Complete exact ordered operation profile required');
  for(const [index,wanted] of expected.entries()) {
    const operation=report.operations[index];
    assertDelivery(operation.events,wanted.expected);
    for(const event of operation.events) {
      if(event.type.startsWith('key'))assert.equal(event.target,'TEXTAREA','Explicit renderer keyboard transport target');
      assert(Number.isFinite(event.time)&&event.time>=0,'Retained finite event timestamp required');
      assert.equal(typeof event.defaultPrevented,'boolean','Completed dispatch prevention flag required');
    }
    // Reports may retain expected/delivery diagnostics, but cannot define the oracle.
    for(const [i,event] of wanted.expected.entries())for(const [key,value] of Object.entries(operation.expected[i]||{}))
      assert.equal(value,event[key],`${wanted.name}: reported expected field ${key} cannot contradict fixed profile`);
    assert.equal(operation.expected.length,wanted.expected.length,'Expected event diagnostic count');
    assert.equal(operation.post_delivery_animation_frames,2,'Two frames after complete trusted delivery');
    delivered.push(...operation.events);
  }
  const complete=[...report.startup_events,...delivered];
  assert.deepEqual(report.events,complete,'Complete event log must equal retained startup plus ordered per-operation evidence');
  assert(complete.every((event,i)=>!i||event.time>=complete[i-1].time),'Event delivery chronology');
  return {operation_count:expected.length,event_count:delivered.length,startup_event_count:report.startup_events.length,
    keyboard_transport:'TEXTAREA',focus_oracle:'Rendered rings and following traversal only'};
}

export function validateFocusVisibleEvidence(report,runtime=report?.runtime) {
  object(report,'Runtime report');assert.equal(report.runtime,runtime,'Correct independent runtime required');
  assert(['rust','moonbit'].includes(runtime),'Both recognized renderers required');
  assert.equal(report.profile_revision,PAIR_REVISION,'Exact current paired profile revision required');
  assert.equal(report.candidate,'implemented','Historical Rust-only reports cannot be relabeled as paired');
  assert.equal(report.comparison,'not_run','Raw runtime report cannot self-certify pairing');
  assert.equal(report.failure,undefined,'Failed execution cannot pass');assert.deepEqual(report.errors,[],'Runtime errors fail closed');
  assert(Array.isArray(report.console)&&!report.console.some(entry=>entry.type==='error'),'Retained runtime console must contain no errors');
  assert.deepEqual(report.profile,FOCUS_PROFILE,'Exact fixed input/view profile');
  assert.deepEqual(report.canvas,{bounds:{x:0,y:0,width:800,height:600},backing:{width:800,height:600}},'Unscaled full viewport canvas');
  object(report.initial_transport,'Actual startup transport observation');
  assert.equal(report.initial_transport.active_tag,'TEXTAREA','Focused textarea keyboard delivery conduit required');
  assert.equal(report.initial_transport.canvas_tab_index,-1,'Canvas cannot become a DOM tab stop');
  const input=report.initial_transport.textarea;object(input,'Actual textarea observation');
  for(const key of ['readOnly','disabled','isContentEditable'])assert.equal(input[key],false,`Exact desktop textarea ${key}`);
  assert.deepEqual(input.inline_style,{position:'fixed',left:'0px',top:'0px',width:'1px',height:'1px',opacity:'0',fontSize:'16px'},
    'Source-requested hidden textarea style');
  assert.equal(input.style?.opacity,'0','Transport must be visually hidden');
  assert.equal(input.style?.position,'fixed','Fixed hidden transport required');
  const bounds=input.bounds;object(bounds,'Actual textarea box');
  assert.equal(bounds.x,0);assert.equal(bounds.y,0);
  assert([bounds.width,bounds.height].every(value=>Number.isFinite(value)&&value>0&&value<=16),
    'Actual hidden textarea box must be finite and bounded; UA padding/borders may differ');
  assert.deepEqual(report.source,assertPairedProvenance(report.build,report.catalog),'Current implemented source identity');
  assert.deepEqual(report.provenance_negative_controls,pairedProvenanceNegativeControls(report.build,report.catalog),'Recomputed provenance controls');
  hash(report.build_manifest_sha256,'Retained manifest');hash(report.catalog_sha256,'Retained catalog');
  assert.equal(report.build_manifest_file,`focus-visible-${runtime}-build-manifest.json`,'Renderer-bound manifest filename');
  assert.equal(report.catalog_file,`focus-visible-${runtime}-catalog.json`,'Renderer-bound catalog filename');
  sameKeys(report.captures,FOCUS_CAPTURES,'Complete capture set');
  for(const [name,spec] of Object.entries(FOCUS_SEQUENCE.captures)) {
    const capture=report.captures[name];
    assert.equal(capture.file,`focus-visible-${runtime}-${name}-dpr1.png`,'Renderer-bound screenshot filename');
    assert.equal(capture.stability_file,`focus-visible-${runtime}-${name}-stable-first-dpr1.png`,'Independent stable sample filename');
    for(const key of ['png_sha256','rgba_sha256','stability_png_sha256','stability_rgba_sha256'])hash(capture[key],`${name} ${key}`);
    assert.equal(capture.after_operation,spec.after_operation,`${name}: capture must follow exact operation prefix`);
    assert.equal(capture.width,800);assert.equal(capture.height,600);
  }
  const files=expectedRuntimeFiles(report.build,runtime),seen=new Set();
  assert(Array.isArray(report.runtime_responses)&&report.runtime_responses.length,'Actual loaded runtime bytes required');
  for(const response of report.runtime_responses) {
    const url=new URL(response.url),path=url.pathname.replace(/^\/gpui-conformance\//,'');
    assert(Object.hasOwn(files,path),`Unpinned loaded code/font dependency ${path}`);
    assert.equal(response.status,200,'Successful actual browser response');assert.equal(response.sha256,files[path],`Executed ${path} manifest hash`);
    assert.equal(response.file,`focus-visible-${runtime}-asset-${path.replaceAll('/','_')}.bin`,'Retained executed artifact filename');
    assert(report.requests.some(request=>request.url===response.url&&request.status===200),'Loaded browser request log');
    assert(report.served_requests.some(request=>request.url===url.pathname+url.search&&request.status===200&&request.sha256===response.sha256),'Server byte/hash log');
    seen.add(path);
  }
  const required=runtime==='rust'?['rust/focus_visible.js','rust/focus_visible_bg.wasm','rust/host.mjs','load-timing.mjs']:
    ['moonbit/focus_visible.mjs','moonbit/host.mjs','moonbit/render.mjs','moonbit/focus-visible-host.mjs','load-timing.mjs',
      'moonbit/IBMPlexSans-Regular.ttf','moonbit/IBMPlexSans-SemiBold.ttf'];
  for(const file of required)assert(seen.has(file),`Missing actual runtime dependency ${file}`);
  for(const request of report.requests) {
    const pathname=new URL(request.url).pathname;
    if(/\.(mjs|js|wasm|ttf)$/.test(pathname))assert(report.runtime_responses.some(response=>response.url===request.url),'All actual code/font requests must retain pinned bytes');
  }
  return {runtime,...validateFocusVisibleEvents(report,runtime),capture_count:FOCUS_CAPTURES.length,loaded_assets:seen.size};
}

export function assertCurrentFocusVisibleBuild(report,{revision,trackedDirty,catalogBytes}) {
  assert.match(revision||'',/^[0-9a-f]{40}$/,'Current checkout revision required');
  assert.equal(trackedDirty,false,'Current checkout must be clean');
  assert.equal(report.build.lab_revision,revision,'Historical build cannot be relabeled onto current checkout');
  assert.equal(sha(catalogBytes),report.catalog_sha256,'Actual current catalog bytes must match retained provenance');
  assert.deepEqual(JSON.parse(catalogBytes),report.catalog,'Actual current catalog identity');
}

export function validateFocusVisibleRelations(images) {
  const checks={};
  for(const [kind,predicate] of [['same',assertPanelSame],['different',assertPanelDifferent],['unchanged',assertUnchanged]])
    checks[kind]=FOCUS_SEQUENCE[kind].map(([before,after])=>({before,after,...predicate(images[before],images[after])}));
  return checks;
}

export function validateFocusVisiblePixels(report,images,stableImages) {
  sameKeys(images,FOCUS_CAPTURES,'Decoded full capture set');sameKeys(stableImages,FOCUS_CAPTURES,'Decoded first-stable capture set');
  const measurements={},hashes={};
  for(const [name,spec] of Object.entries(FOCUS_SEQUENCE.captures)) {
    const capture=report.captures[name],image=images[name],stable=stableImages[name];
    for(const [sample,wanted] of [[image,capture.rgba_sha256],[stable,capture.stability_rgba_sha256]]) {
      assert(sample?.data instanceof Uint8Array,`${name}: independently decoded RGBA bytes required`);assertImage(sample);
      assert.equal(sha(sample.data),wanted,`${name}: retained RGBA digest`);
      // Dimensions come from the actual PNG decoder, never report metadata.
      const measured=inspectState(sample,spec.state);
      if(sample===image)measurements[name]=measured;
    }
    assertUnchanged(image,stable);hashes[name]=sha(image.data);

  }
  const checks=validateFocusVisibleRelations(images);
  // Recompute every relation for both independently retained stable samples.
  validateFocusVisibleRelations(stableImages);
  const controls=focusVisibleNegativeControls(images,report.operations);
  assert.deepEqual(report.negative_controls,controls,'Recomputed actual-pixel/event negative controls');
  assert.deepEqual(report.negative_controls_capture_sha256,hashes,'Negative controls bind the full actual capture set');
  return {capture_count:FOCUS_CAPTURES.length,samples_per_capture:2,checked_pixels_per_sample:800*600,
    measurements,checks,negative_controls:controls};
}

// Retained artifact reads reject traversal and symlink escapes. A changed PNG
// hash, valid-header/wrong-dimension PNG, or fabricated report never substitutes
// for independently decoded pixels. Pillow emits its actual decoded dimensions.
export async function loadFocusVisibleEvidence(directory,report) {
  const root=await realpath(resolve(directory));
  const read=async(file,expected)=>{
    assert(typeof file==='string'&&file===basename(file)&&file!=='.'&&file!=='..'&&!file.includes('\\'),'Local retained filename required');
    const path=await realpath(join(root,file));assert(path.startsWith(root+sep),'Retained artifact cannot escape evidence directory');
    const bytes=await readFile(path);assert.equal(sha(bytes),expected,`${file}: retained bytes hash`);return {path,bytes};};
  const manifest=await read(report.build_manifest_file,report.build_manifest_sha256);
  const catalog=await read(report.catalog_file,report.catalog_sha256);
  assert.deepEqual(JSON.parse(manifest.bytes),report.build,'Retained manifest must match report');
  assert.deepEqual(JSON.parse(catalog.bytes),report.catalog,'Retained catalog must match report');
  const assets={};
  for(const response of report.runtime_responses)assets[response.file]=(await read(response.file,response.sha256)).bytes;
  const files=[];
  for(const name of FOCUS_CAPTURES) {
    const capture=report.captures[name];
    for(const [file,digest] of [[capture.file,capture.png_sha256],[capture.stability_file,capture.stability_png_sha256]])
      files.push((await read(file,digest)).path);
  }
  const script='from PIL import Image; import sys,struct,json\nfor p in json.loads(sys.stdin.read()):\n with Image.open(p) as im:\n  assert im.format == "PNG", "PNG required"\n  assert im.size == (800,600), "Decoded dimensions must be 800x600"\n  im.load()\n  assert im.size == (800,600), "Loaded dimensions must be 800x600"\n  sys.stdout.buffer.write(struct.pack(">II",*im.size)); sys.stdout.buffer.write(im.convert("RGBA").tobytes())';
  const decoded=spawnSync('python3',['-c',script],{input:JSON.stringify(files),maxBuffer:files.length*(800*600*4+8)+4096});
  if(decoded.error)throw decoded.error;assert.equal(decoded.status,0,`Independent Pillow PNG decode: ${decoded.stderr?.toString()}`);
  assert.equal(decoded.stdout.length,files.length*(800*600*4+8),'Complete decoder output required');
  const images={},stableImages={};let offset=0;
  for(const name of FOCUS_CAPTURES)for(const target of [images,stableImages]) {
    const width=decoded.stdout.readUInt32BE(offset),height=decoded.stdout.readUInt32BE(offset+4);offset+=8;
    target[name]={width,height,data:new Uint8Array(decoded.stdout.buffer,decoded.stdout.byteOffset+offset,width*height*4)};offset+=width*height*4;
  }
  return {images,stableImages,assets,manifest_bytes:manifest.bytes,catalog_bytes:catalog.bytes};
}

export function compareFocusVisibleBehavior(rust,moonbit,retained) {
  assert(retained?.rust&&retained?.moonbit,'Independent retained pixels from both renderers required');
  const integrity={rust:validateFocusVisibleEvidence(rust,'rust'),moonbit:validateFocusVisibleEvidence(moonbit,'moonbit')};
  assert.deepEqual(rust.build,moonbit.build,'Same current clean committed build manifest required');
  assert.equal(rust.build_manifest_sha256,moonbit.build_manifest_sha256,'Identical retained manifest bytes');
  assert.deepEqual(rust.catalog,moonbit.catalog,'Identical current implemented catalog');
  assert.equal(rust.catalog_sha256,moonbit.catalog_sha256,'Identical retained catalog bytes');
  assert.deepEqual(rust.environment,moonbit.environment,'Same independent browser runtime environment');
  const pixels={};
  for(const [runtime,report] of [['rust',rust],['moonbit',moonbit]]) {
    const evidence=retained[runtime];
    assert.equal(sha(evidence.manifest_bytes),report.build_manifest_sha256,'Actual retained manifest bytes required');
    assert.equal(sha(evidence.catalog_bytes),report.catalog_sha256,'Actual retained catalog bytes required');
    for(const response of report.runtime_responses)assert.equal(sha(evidence.assets?.[response.file]),response.sha256,'Actual loaded runtime bytes required');
    pixels[runtime]=validateFocusVisiblePixels(report,evidence.images,evidence.stableImages);
  }
  const imageDifferences=FOCUS_CAPTURES.map(name=>{
    const a=retained.rust.images[name].data,b=retained.moonbit.images[name].data;let different=0;
    for(let i=0;i<a.length;i+=4)if(a[i]!==b[i]||a[i+1]!==b[i+1]||a[i+2]!==b[i+2]||a[i+3]!==b[i+3])different++;
    return {capture:name,different_pixels:different,total_pixels:800*600,equal:different===0,
      text_ink_population:{rust:clone(pixels.rust.measurements[name].text),moonbit:clone(pixels.moonbit.measurements[name].text)},
      button_label_ink_population:{rust:pixels.rust.measurements[name].buttons.map(button=>button.label_ink_pixels),
        moonbit:pixels.moonbit.measurements[name].buttons.map(button=>button.label_ink_pixels)}};});
  return {status:'passed',comparison:'independently_decoded_bounded_focus_behavior',profile_revision:PAIR_REVISION,source:clone(rust.source),profile:clone(FOCUS_PROFILE),
    scope:'Actual unchanged Rust WASM and compiled MoonBit, trusted fixed mouse/keyboard/wheel sequence, 800x600 DPR1 only',
    build:{lab_revision:rust.build.lab_revision,upstream:clone(rust.build.upstream),moonbit:clone(rust.build.moonbit)},
    geometry:clone(GEOMETRY),integrity,decoded_pixel_validation:pixels,
    cross_renderer_image_observations:{verdict:'not_a_parity_check',captures:imageDifferences,
      meaning:'Observed complete-image differences include text and antialiasing; no text OCR, rasterization or full-image parity verdict'},
    keyboard_transport:{rust:'Hidden TEXTAREA',moonbit:'Hidden TEXTAREA',meaning:'Trusted physical key and beforeinput delivery only; neither DOM target establishes application focus'},
    unverified:['cross-renderer text content/OCR, ink or antialiasing parity','cross-renderer full-image parity','native parity',
      'private Rust focus state','nested tab groups','touch','pointer capture','other browsers/GPUs','other viewports or DPR beyond 1']};
}
