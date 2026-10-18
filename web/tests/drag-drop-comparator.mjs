import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {EMBEDDED_FONTS,sha256} from './tab-stop-comparator.mjs';
export {EMBEDDED_FONTS,sha256};
export const DRAG_DROP=Object.freeze({width:800,height:600,dpr:1,
  revision:'5a5fbe79917971a4d52a96b6ddb04da198a5012e',tree:'990fb995914d51a546b20e5cf0382dafc105c299',
  source:'crates/gpui/examples/drag_drop.rs',sourceBlob:'8f038ef3308fee9b097e7289665c9fa47cd6945b',
  sourceSha256:'4011afde7c64fac2559b78918e6fdabdc563fe9f7591c74425d72da906dcc47a'});
export const ENGINE=Object.freeze({repository:'gpui-mbt/gpui.mbt',
  revision:'eb968228bbea56aff13721dc427875c2dacffc14',tree:'ae9072d350ef6d1546e408226218ec08efc96552'});
export const PROFILE_REVISION='unchanged_drag_drop_pointer_v1';
export const SOURCE_CONSTRAINTS=Object.freeze([
  'drag_drop.rs:70-111: white centered flex column, source blue/red/green 128px squares, border2, gap4=16px, hover alpha0.2',
  'drag_drop.rs:113-130: target512x128 border3, no drag-over style, accepted DragInfo sets color border and half-alpha fill',
  'div.rs:52,2974-3012: activation only on Bubble MouseMove, distance strictly greater than2, pending left down consumed once',
  'div.rs:2987: activation grip is move position minus source origin, not original down position',
  'window.rs:3744-3751 + drag_drop.rs:38-57: view origin pointer minus grip and child padding grip minus60,25 cancel; visible preview120x50 centered at pointer',
  'div.rs:3437-3474: source hover styles suppressed while active drag exists',
  'div.rs:2903-2931 + window.rs:6010-6015: typed hovered target consumes accepted drag on Bubble up; any remaining active drag clears after up',
  'No rejecting predicate, foreign payload, nested target, native/global capture, touch or OS drag is present in this bounded source example',
]);
const HASH=/^[0-9a-f]{64}$/;
export function assertProvenance(build,catalog) {
  assert.equal(build.upstream?.repository,'zed-industries/zed');
  assert.equal(build.upstream?.revision,DRAG_DROP.revision);
  assert.deepEqual(build.moonbit,ENGINE,'Baseline must preserve the existing engine pin');
  assert.deepEqual(catalog.upstream,build.upstream);assert.deepEqual(catalog.moonbit,build.moonbit);
  assert.equal(build.lab_tracked_dirty,false);assert.match(build.lab_revision||'',/^[0-9a-f]{40}$/);assert.match(build.lab_tree||'',/^[0-9a-f]{40}$/);
  assert.equal(build.rust?.source_revision,DRAG_DROP.revision);assert.equal(build.rust?.source_tree,DRAG_DROP.tree);
  assert.equal(build.rust_bundled,true);assert.equal(build.rust?.source_modified,false);
  assert.equal(build.rust?.oracle_only,true);assert.equal(build.rust?.packaging?.upstream_files_modified,false);
  assert.deepEqual(build.rust_implemented,['drag_drop'],'This independent job must build only the explicit oracle');
  assert(!build.implemented?.includes('drag_drop'),'No MoonBit counterpart may be claimed');
  assert.equal(catalog.examples.filter(entry=>entry.id==='drag_drop').length,0,'Source-only baseline must not invent a matched catalog route');
  assert.equal(build.rust.implemented_subset,null);
  assert.equal(build.rust_oracle_only.length,1,'Exactly one isolated oracle record');
  assert.deepEqual(build.rust_subset_sources||[],[]);
  const records=build.rust_oracle_only.filter(entry=>entry.id==='drag_drop');assert.equal(records.length,1);
  for(const [key,value] of Object.entries({source:DRAG_DROP.source,source_blob:DRAG_DROP.sourceBlob,
    source_sha256:DRAG_DROP.sourceSha256,upstream_revision:DRAG_DROP.revision,
    status:'rust_oracle_only',candidate:'not_implemented',width:800,height:600,dpr:1}))assert.equal(records[0][key],value);
  assert(Number.isFinite(Date.parse(build.rust.build_completed_at_utc||'')),'Actual build completion timestamp required');
  assert.match(build.rust.toolchain||'',/^rustc 1\./);assert.match(build.rust.bindings||'',/^wasm-bindgen 0\.2\.129$/);
  assert.deepEqual(build.rust.packaging.additional_bins,[{name:'drag_drop',source:DRAG_DROP.source}]);
  for(const file of ['drag_drop.js','drag_drop_bg.wasm','host.mjs','unchanged-source/drag_drop.rs','packaging-Cargo.toml'])
    assert.match(build.rust.files?.[file]||'',HASH,`Pinned Rust file ${file}`);
  assert.equal(build.rust.files['unchanged-source/drag_drop.rs'],DRAG_DROP.sourceSha256);
  assert.equal(build.rust.files['packaging-Cargo.toml'],build.rust.packaging.manifest_sha256,'Retained relocated Cargo manifest hash');
  const fonts=Object.values(build.rust.embedded_fonts||{});assert.equal(fonts.length,8,'All eight upstream embedded font inputs required');
  assert.deepEqual(Object.fromEntries(Object.entries(build.rust.embedded_fonts).map(([path,font])=>[path,font.sha256])),EMBEDDED_FONTS,'Exact upstream embedded-font bytes');
  for(const font of fonts) {assert.match(font.sha256||'',HASH);assert.equal(build.rust.files[font.file],font.sha256);}
  assert(build.rust.command.includes('+nightly-2026-10-14'));assert(build.rust.command.includes('--locked'));
  assert.deepEqual(build.rust.command.filter((_argument,index,array)=>array[index-1]==='--bin'),['drag_drop']);
  assert.match(build.moonbit_host_files_sha256?.['load-timing.mjs']||'',HASH);
  return records[0];
}
export function assertCurrentBuild(report,checkout) {
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
    ['wrong_source_tree',b=>{b.rust.source_tree='0'.repeat(40);}],
    ['extra_oracle',b=>{b.rust_oracle_only.push({...b.rust_oracle_only[0],id:'other'});}],
    ['modified_archive',b=>{b.rust.packaging.upstream_files_modified=true;}],
    ['dirty_lab',b=>{b.lab_tracked_dirty=true;}],
    ['candidate_claim',b=>{b.implemented.push('drag_drop');}],
    ['wrong_engine',b=>{b.moonbit.revision='0'.repeat(40);}],
    ['missing_wasm',b=>{delete b.rust.files['drag_drop_bg.wasm'];}],
    ['missing_font',b=>{delete b.rust.embedded_fonts[Object.keys(b.rust.embedded_fonts)[0]];}],
  ].map(([name,mutate])=>{const copy=structuredClone(build);mutate(copy);
    assert.throws(()=>assertProvenance(copy,catalog),name);return {name,rejected:true};});
}

export function decodePng(bytes) {
  assert(Buffer.isBuffer(bytes)&&bytes.length>0&&bytes.length<=8*1024*1024,'Bounded original PNG bytes required');
  const decoder=fileURLToPath(new URL('../scripts/decode_drag_drop_png.py',import.meta.url));
  const decoded=spawnSync('python3',[decoder],{input:bytes,timeout:10000,maxBuffer:800*600*4+4096});
  if(decoded.error)throw decoded.error;
  assert.equal(decoded.status,0,`Strict PNG decoder: ${decoded.stderr?.toString().slice(0,2048)}`);
  assert.equal(decoded.stdout.length,8+800*600*4);assert.equal(decoded.stdout.readUInt32BE(0),800);assert.equal(decoded.stdout.readUInt32BE(4),600);
  return {width:800,height:600,data:new Uint8Array(decoded.stdout.subarray(8))};
}

const WHITE=[255,255,255,255],BLACK=[0,0,0,255];
export const COLORS=Object.freeze([[0,0,255,255],[255,0,0,255],[0,128,0,255]]);
const primary=[2,0,1];
function imageCheck(image) {assert.equal(image.width,800);assert.equal(image.height,600);assert.equal(image.data.length,800*600*4);}
const pixel=(image,x,y)=>Array.from(image.data.subarray(4*(y*800+x),4*(y*800+x)+4));
const equal=(a,b,tolerance=0)=>a.every((value,index)=>Math.abs(value-b[index])<=tolerance);
const inside=(p,r)=>p.x>=r.x&&p.x<r.x+r.width&&p.y>=r.y&&p.y<r.y+r.height;
const near=(p,q,dx,dy)=>Math.abs(p.x-q.x)<=dx&&Math.abs(p.y-q.y)<=dy;
export const center=r=>({x:r.x+r.width/2,y:r.y+r.height/2});
function bounds(image,color) {
  let left=800,right=-1,top=600,bottom=-1;
  for(let y=0;y<600;y++)for(let x=0;x<800;x++)if(equal(pixel(image,x,y),color)) {
    left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);
  }
  assert(right>=left,'Source solid border color required');
  return {x:left,y:top,width:right-left+1,height:bottom-top+1};
}
export function discoverGeometry(image) {
  imageCheck(image);const sources=COLORS.map(color=>bounds(image,color)),target=bounds(image,BLACK);
  for(const source of sources) {assert.equal(source.width,128);assert.equal(source.height,128);assert.equal(source.y,sources[0].y);}
  for(let index=1;index<3;index++)assert.equal(sources[index].x-sources[index-1].x-128,16,'Source gap4');
  assert.equal(sources[0].x+sources[2].x+128,800,'Centered source row');
  assert.equal(target.width,512);assert.equal(target.height,128);assert.equal(2*target.x+target.width,800,'Centered target');
  assert.equal(target.y-sources[0].y-128,60,'Source mb10 plus root gap5 separates target');
  const geometry={sources,target};assertPaint(image,geometry,{pointer:{x:10,y:10},active:null,target:null});return geometry;
}
function baseColor(p,geometry,state) {
  for(let index=0;index<3;index++) {
    const r=geometry.sources[index];if(!inside(p,r))continue;
    if(p.x<r.x+2||p.x>=r.x+r.width-2||p.y<r.y+2||p.y>=r.y+r.height-2)return COLORS[index];
    return state.active===null&&inside(state.pointer,r)?COLORS[index].map((value,i)=>i===3?255:Math.round(value*.2+255*.8)):WHITE;
  }
  const r=geometry.target;
  if(inside(p,r)) {
    if(p.x<r.x+3||p.x>=r.x+r.width-3||p.y<r.y+3||p.y>=r.y+r.height-3)return state.target===null?BLACK:COLORS[state.target];
    return state.target===null?WHITE:COLORS[state.target].map((value,i)=>i===3?255:Math.round(value*.5+255*.5));
  }
  return WHITE;
}
function textRegion(p,g) {
  // Text is excluded from color/geometry assertions, never OCR-substituted.
  if(p.y<g.sources[0].y-16&&p.x>250&&p.x<550)return true;
  return [...g.sources,g.target].some(r=>near(p,center(r),90,15));
}
export function assertPaint(image,geometry,state) {
  imageCheck(image);let checked=0;
  for(let y=0;y<600;y++)for(let x=0;x<800;x++) {
    const p={x,y};if(textRegion(p,geometry))continue;
    if(state.active!==null&&near(p,state.pointer,100,65))continue;
    assert(equal(pixel(image,x,y),baseColor(p,geometry,state),1),`Source border/fill/hover or cleanup mismatch ${x},${y}`);checked++;
  }
  assert(checked>350000,'Bounded preview/text exclusions must retain broad independent source paint coverage');
  return {checked_pixels:checked};
}
function previewAlpha(image,p,geometry,state) {
  const base=baseColor(p,geometry,state),paint=pixel(image,p.x,p.y),channel=primary[state.active];
  const other=[0,1,2].filter(index=>index!==channel).sort((a,b)=>base[b]-base[a])[0];
  if(base[other]<100)return null;
  // A neutral shadow scales the underlying base. Eliminating that factor lets
  // the source-color contribution independently expose its half alpha.
  return (paint[channel]-paint[other]/base[other]*base[channel])/COLORS[state.active][channel];
}
export function assertPreview(image,geometry,state,precise=false) {
  assert.notEqual(state.active,null);const p=state.pointer,y=p.y-16;let checked=0;
  for(let x=p.x-52;x<=p.x+52;x+=4) {
    const q={x,y};if(textRegion(q,geometry))continue;
    const alpha=previewAlpha(image,q,geometry,state);if(alpha===null)continue;
    assert(Math.abs(alpha-.5)<=.02,`Source half-alpha preview contribution at ${x},${y}: ${alpha}`);checked++;
  }
  assert(checked>=10,'Preview must remain independently observable away from text');
  if(precise) {
    const rows=[p.y-20,p.y-16,p.y+16,p.y+20];
    for(const row of rows) {
      const selected=[];
      for(let x=p.x-70;x<=p.x+70;x++) {
        const alpha=previewAlpha(image,{x,y:row},geometry,state);
        if(alpha!==null&&Math.abs(alpha-.5)<=.02)selected.push(x);
      }
      assert.equal(selected.length,120,'Source floating preview width120 on independent nontext scanline');
      assert.equal(selected[0],p.x-60,'Actual visible grab geometry is pointer-centered');
      assert.equal(selected.at(-1),p.x+59);
    }
    for(const dy of [-26,25])assert(Math.abs(previewAlpha(image,{x:p.x-35,y:p.y+dy},geometry,state))<.02,'Outside source preview height50 has only neutral shadow');
    for(const dy of [-25,24])assert(Math.abs(previewAlpha(image,{x:p.x-35,y:p.y+dy},geometry,state)-.5)<.02,'Source preview height50 edges');
  }
  return {checked_samples:checked,precise_geometry:precise};
}
export function makeProfile(geometry=null) {
  const operations=[],captures={};let pointer={x:10,y:10},down=false,active=null,target=null;
  const add=(name,action,update={},precise=false)=>{
    const before={...pointer};if(action.kind==='move'||action.kind==='releaseAt')pointer={x:action.x,y:action.y};
    const type=action.kind==='move'?'pointermove':action.kind==='down'?'pointerdown':'pointerup';
    const duplicate=action.kind==='duplicateUp';if(action.kind==='down')down=true;else if(type==='pointerup')down=false;
    if(Object.hasOwn(update,'active'))active=update.active;if(Object.hasOwn(update,'target'))target=update.target;
    const expected={type,x:pointer.x,y:pointer.y,button:type==='pointermove'?-1:0,buttons:down?1:0,pointerType:'mouse'};
    operations.push({name,action,expected:duplicate?[]:[expected],duplicate,mouse_expected:{type:type.replace('pointer','mouse'),x:pointer.x,y:pointer.y,button:0,buttons:down?1:0},prior_pointer:before});
    captures[name]={after_operation:operations.length,pointer:{...pointer},active,target,precise_preview:precise};
  };
  add('initial',{kind:'move',...pointer});if(!geometry)return {operations,captures,complete:false};
  const source=index=>center(geometry.sources[index]),stage={x:100,y:60},t=center(geometry.target);
  const move=(name,p,update={},precise=false)=>add(name,{kind:'move',...p},update,precise);
  const press=(name)=>add(name,{kind:'down'}),up=(name,update={})=>add(name,{kind:'up'},update);
  move('no_move_hover',source(0));press('no_move_down');up('no_move_up');
  press('threshold_down');move('exact_two',{x:source(0).x+2,y:source(0).y});
  move('over_two',{x:source(0).x+3,y:source(0).y},{active:0});move('return_toward_origin',{x:source(0).x+1,y:source(0).y});
  move('threshold_stage',stage,{},true);up('threshold_outside_up',{active:null});
  add('duplicate_up',{kind:'duplicateUp'});
  // CDP release coordinates are independent of its last mouseMoved. The pointer stream and any compatibility mouse events
  // must prove there was no intervening move; otherwise this run fails.
  move('far_release_hover',source(1));press('far_release_down');
  add('far_release_only',{kind:'releaseAt',...t},{active:null});
  move('after_far_release',stage);
  for(let color=0;color<3;color++) {
    move(`color${color}_hover`,source(color));press(`color${color}_down`);
    move(`color${color}_activate`,{x:source(color).x+3,y:source(color).y},{active:color});
    move(`color${color}_stage`,stage,{},true);move(`color${color}_target`,t);
    up(`color${color}_accepted`,{active:null,target:color});move(`color${color}_park`,stage);
  }
  // Off-center down/activation are intentionally independent of the source's
  // center. The visible preview still centers at pointer by source algebra.
  const r=geometry.sources[0],grip={x:r.x+92,y:r.y+105};
  move('offcenter_hover',grip);press('offcenter_down');move('offcenter_activate',{x:grip.x+3,y:grip.y},{active:0});
  move('offcenter_stage',{x:110,y:70},{},true);
  const right=geometry.target.x+geometry.target.width;
  move('outside_target_active',{x:right+1,y:t.y});up('outside_target_rejected',{active:null});
  move('repeat_hover',source(1));press('repeat_down');move('repeat_activate',{x:source(1).x+3,y:source(1).y},{active:1});
  move('inside_target_border',{x:right-1,y:t.y});up('inside_target_accepted',{active:null,target:1});
  move('exclusive_edge_hover',source(2));press('exclusive_edge_down');move('exclusive_edge_activate',{x:source(2).x+3,y:source(2).y},{active:2});
  move('exclusive_target_edge',{x:right,y:t.y});up('exclusive_target_rejected',{active:null});
  move('final_park',stage);add('final_duplicate_up',{kind:'duplicateUp'});
  return {operations,captures,complete:true};
}
export function assertPointerDelivery(events,expected,{duplicate=false}={}) {
  if(duplicate)assert(events.length<=1,'Duplicate up may be browser-suppressed; never fabricate delivery');
  else assert.equal(events.length,expected.length,'Exact delivered pointer count');
  for(let index=0;index<events.length;index++) {
    const event=events[index],wanted=duplicate?{type:'pointerup',...expected[0]}:expected[index];
    assert.equal(event.trusted,true);assert.equal(event.target,'CANVAS');assert.equal(event.pointerType,'mouse');
    for(const [key,value] of Object.entries(wanted))assert.equal(event[key],value,`Trusted pointer ${index} ${key}`);
  }
  return {pointer_events:events.length,browser_suppressed:duplicate&&events.length===0};
}
export function validateOperations(result,geometry) {
  const profile=makeProfile(geometry);assert.equal(result.operations.length,profile.operations.length);
  assert.deepEqual(Object.keys(result.captures),Object.keys(profile.captures),'Exact fixed source capture profile');
  const pointers=[],mice=[],duplicates=[];
  for(let index=0;index<profile.operations.length;index++) {
    const actual=result.operations[index],wanted=profile.operations[index];assert.equal(actual.name,wanted.name);assert.deepEqual(actual.action,wanted.action);
    assert.equal(actual.status,'delivered');assert.equal(actual.input_method,'CDP.Input.dispatchMouseEvent');assert.equal(actual.input_acknowledged,true);assert.equal(actual.post_delivery_animation_frames,2);
    assert.deepEqual(actual.expected,wanted.expected);assert.equal(actual.duplicate,wanted.duplicate);
    const pointerExpected=wanted.duplicate?[{x:wanted.mouse_expected.x,y:wanted.mouse_expected.y,button:0,buttons:0,pointerType:'mouse'}]:wanted.expected;
    const delivery=assertPointerDelivery(actual.events,pointerExpected,{duplicate:wanted.duplicate});
    if(wanted.duplicate)duplicates.push({name:wanted.name,...delivery});
    assert(actual.mouse_events.length<=1,'Compatibility mouse delivery may be suppressed by canvas pointer preventDefault; no extra events permitted');
    for(const mouse of actual.mouse_events) {assert.equal(mouse.trusted,true);assert.equal(mouse.target,'CANVAS');
      for(const [key,value] of Object.entries(wanted.mouse_expected))assert.equal(mouse[key],value,`Independent mouse transport ${wanted.name} ${key}`);}
    if(wanted.duplicate)duplicates.at(-1).mouse_events=actual.mouse_events.length;
    pointers.push(...actual.events);mice.push(...actual.mouse_events);
    assert.equal(result.captures[wanted.name].after_operation,index+1);
  }
  assert.deepEqual(result.events.slice(result.operation_start),pointers,'Entire pointer stream partitions into exact operation log');
  assert.deepEqual(result.mouse_events.slice(result.mouse_operation_start),mice,'Entire mouse stream partitions into exact operation log');
  assert(result.events.every(event=>event.trusted));assert(result.mouse_events.every(event=>event.trusted));
  return {operations:profile.operations.length,duplicate_releases:duplicates,far_coordinate_release_only:'trusted coordinate-changing pointerup without intervening move; any delivered compatibility mouseup independently checked'};
}
export function validateProfile(images,geometry) {
  const profile=makeProfile(geometry),checks={};assert.deepEqual(Object.keys(images),Object.keys(profile.captures));
  for(const [name,state] of Object.entries(profile.captures)) {
    checks[name]={paint:assertPaint(images[name],geometry,state)};
    if(state.active!==null)checks[name].preview=assertPreview(images[name],geometry,state,state.precise_preview);
  }
  return checks;
}
export function profileNegativeControls(images,geometry,result) {
  if(result)validateOperations(result,geometry);
  const controls=[],reject=(name,run)=>{assert.throws(run,name);controls.push({name,rejected:true});};
  const changed=(name,mutate)=>{const copy={...images,[name]:{...images[name],data:new Uint8Array(images[name].data)}};mutate(copy[name]);return copy;};
  const paint=(image,p,color)=>image.data.set(color,4*(p.y*800+p.x));
  const states=makeProfile(geometry).captures;
  const inspect=(name,image)=>{assertPaint(image,geometry,states[name]);if(states[name].active!==null)assertPreview(image,geometry,states[name],states[name].precise_preview);};
  reject('activation_at_exact_two',()=>inspect('exact_two',images.over_two));
  reject('deactivation_return_toward_origin',()=>inspect('return_toward_origin',images.no_move_down));
  reject('wrong_accepted_color',()=>inspect('color1_accepted',images.color0_accepted));
  reject('excluded_edge_accepts_drop',()=>inspect('exclusive_target_rejected',images.color2_accepted));
  reject('outside_release_mutates_target',()=>inspect('outside_target_rejected',images.inside_target_accepted));
  reject('preview_survives_release',()=>inspect('threshold_outside_up',images.threshold_stage));
  reject('half_alpha_preview_missing',()=>inspect('threshold_stage',images.threshold_outside_up));
  reject('source_hover_leaks_into_active',()=>inspect('threshold_stage',changed('threshold_stage',image=>paint(image,{x:geometry.sources[0].x+5,y:geometry.sources[0].y+5},[204,204,255,255])).threshold_stage));
  reject('target_border_width',()=>inspect('initial',changed('initial',image=>paint(image,{x:geometry.target.x+3,y:geometry.target.y+10},BLACK)).initial));
  reject('source_gap',()=>discoverGeometry(changed('initial',image=>paint(image,{x:geometry.sources[0].x-1,y:geometry.sources[0].y},COLORS[0])).initial));
  if(result) {
    for(const [name,mutate] of [
      ['untrusted_delivery',r=>{r.operations[1].events[0].trusted=false;}],
      ['missing_delivery',r=>{r.operations[1].events=[];}],
      ['release_only_has_move',r=>{r.operations.find(o=>o.name==='far_release_only').events.unshift(r.operations[1].events[0]);}],
      ['wrong_release_coordinates',r=>{r.operations.find(o=>o.name==='far_release_only').events[0].x=10;}],
      ['reordered_operations',r=>{[r.operations[1],r.operations[2]]=[r.operations[2],r.operations[1]];}],
    ]) {const copy=structuredClone(result);mutate(copy);reject(name,()=>validateOperations(copy,geometry));}
  }
  return controls;
}
