import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
export const sha256=bytes=>createHash('sha256').update(bytes).digest('hex');
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

export const UNIFORM_LIST=Object.freeze({width:300,height:300,dpr:1,count:50,
  revision:'5a5fbe79917971a4d52a96b6ddb04da198a5012e',tree:'990fb995914d51a546b20e5cf0382dafc105c299',
  source:'crates/gpui/examples/uniform_list.rs',sourceBlob:'4a2c4788b192d802ee3d51714c250e7c5a82db76',
  sourceSha256:'939b065c2db96ce38400c0ea79a0dd74803aa27793698bb5d00f6652a58f4e3a'});
// Existing catalog identity is frozen for this new source-only profile. It is not a list candidate.
export const ENGINE=Object.freeze({repository:'gpui-mbt/gpui.mbt',
  revision:'fc53cb382c66f68bfc1b3e1cc72d01056cd3c625',tree:'c9ec59c5fbdbd84548b7d6ffe2c99b8403509db9'});
export const PROFILE_REVISION='unchanged_uniform_list_wheel_v1';
export const SOURCE_CONSTRAINTS=Object.freeze([
  'uniform_list.rs:16-42: white full-size root, 50 source rows, stable id(ix), px_2 padding, Item 1 through Item 50',
  'uniform_list.rs:50: requested300x300; browser canvas size is explicitly300x300 DPR1',
  'elements/uniform_list.rs:278-310,344-379: measured prototype height and complete count-times-height content extent',
  'elements/uniform_list.rs:473-513: visible half-open range and f64 per-row offset under content mask',
  'div.rs:2450-2500: offset clamped against full extent; div.rs:3331-3385: X-only maps to Y, nonzero Y wins',
  'Source-derived26px pitch is a hypothesis only; first original PNG independently supplies measured row pitch',
  'Only original paint, trusted wheel delivery, raster translation and drawing-surface-edge output are observable here',
]);
const HISTORICAL_CATALOG=readFileSync(new URL('./fixtures/uniform-list-rust-only-catalog-4b4a7047.json',import.meta.url));
assert.equal(sha256(HISTORICAL_CATALOG),'f44de111e586b8597831e1317f6c9114637879ba4d3fe516ecfe2c7900e8b39b','Immutable source-only catalog snapshot');
const HASH=/^[0-9a-f]{64}$/;
export function assertProvenance(build,catalog) {
  assert.deepEqual(catalog,JSON.parse(HISTORICAL_CATALOG),'Exact immutable source-only catalog; new candidates require a separate profile');
  assert.equal(build.upstream?.repository,'zed-industries/zed');
  assert.equal(build.upstream?.revision,UNIFORM_LIST.revision);
  assert.deepEqual(build.moonbit,ENGINE,'Baseline must preserve the existing engine pin');
  assert.deepEqual(catalog.upstream,build.upstream);assert.deepEqual(catalog.moonbit,build.moonbit);
  assert.equal(build.lab_tracked_dirty,false);assert.match(build.lab_revision||'',/^[0-9a-f]{40}$/);assert.match(build.lab_tree||'',/^[0-9a-f]{40}$/);
  assert.equal(build.rust?.source_revision,UNIFORM_LIST.revision);assert.equal(build.rust?.source_tree,UNIFORM_LIST.tree);
  assert.equal(build.rust_bundled,true);assert.equal(build.rust?.source_modified,false);
  assert.equal(build.site_kind,'uniform_list_rust_oracle_only');assert.deepEqual(build.implemented,[]);
  assert.equal(build.moonbit_execution,'not_run','Catalog core pin is metadata only, never a candidate execution');assert.equal(build.comparison_status,'not_run');
  assert.equal(build.rust?.oracle_only,true);assert.equal(build.rust?.packaging?.upstream_files_modified,false);
  assert.deepEqual(build.rust_implemented,['uniform_list'],'This independent job must build only the explicit oracle');
  assert(!build.implemented?.includes('uniform_list'),'No MoonBit counterpart may be claimed');
  assert.equal(catalog.examples.filter(entry=>entry.id==='uniform_list').length,0,'Source-only baseline must not invent a matched catalog route');
  assert.equal(build.rust.implemented_subset,null);
  assert.equal(build.rust_oracle_only.length,1,'Exactly one isolated oracle record');
  assert.deepEqual(build.rust_subset_sources||[],[]);
  const records=build.rust_oracle_only.filter(entry=>entry.id==='uniform_list');assert.equal(records.length,1);
  for(const [key,value] of Object.entries({source:UNIFORM_LIST.source,source_blob:UNIFORM_LIST.sourceBlob,
    source_sha256:UNIFORM_LIST.sourceSha256,upstream_revision:UNIFORM_LIST.revision,upstream_tree:UNIFORM_LIST.tree,
    status:'rust_oracle_only',candidate:'not_implemented',width:300,height:300,dpr:1}))assert.equal(records[0][key],value);
  assert(Number.isFinite(Date.parse(build.rust.build_completed_at_utc||'')),'Actual build completion timestamp required');
  assert.match(build.rust.toolchain||'',/^rustc 1\./);assert.match(build.rust.bindings||'',/^wasm-bindgen 0\.2\.129$/);
  assert.deepEqual(build.rust.packaging.additional_bins,[{name:'uniform_list',source:UNIFORM_LIST.source}]);
  for(const file of ['uniform_list.js','uniform_list_bg.wasm','host.mjs','unchanged-source/uniform_list.rs','packaging-Cargo.toml'])
    assert.match(build.rust.files?.[file]||'',HASH,`Pinned Rust file ${file}`);
  assert.equal(build.rust.files['unchanged-source/uniform_list.rs'],UNIFORM_LIST.sourceSha256);
  assert.equal(build.rust.files['index.html'],'8f6806a2ae5f935a8212171af3890fb1460c5ab30a357032bf541222b2bd6669');
  assert.equal(build.rust.files['Cargo.lock'],'d60bd2d8e87639d33f67b740796a06078c2c2e3df9593dcbd699c4abc37919da');
  assert.equal(build.rust.files['packaging-Cargo.toml'],build.rust.packaging.manifest_sha256,'Retained relocated Cargo manifest hash');
  const fonts=Object.values(build.rust.embedded_fonts||{});assert.equal(fonts.length,8,'All eight upstream embedded font inputs required');
  assert.deepEqual(Object.fromEntries(Object.entries(build.rust.embedded_fonts).map(([path,font])=>[path,font.sha256])),EMBEDDED_FONTS,'Exact upstream embedded-font bytes');
  for(const font of fonts) {assert.match(font.sha256||'',HASH);assert.equal(build.rust.files[font.file],font.sha256);}
  assert(build.rust.command.includes('+nightly-2026-10-14'));assert(build.rust.command.includes('--locked'));
  assert.deepEqual(build.rust.command.filter((_argument,index,array)=>array[index-1]==='--bin'),['uniform_list']);
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
    ['candidate_claim',b=>{b.implemented.push('uniform_list');}],
    ['wrong_engine',b=>{b.moonbit.revision='0'.repeat(40);}],
    ['missing_wasm',b=>{delete b.rust.files['uniform_list_bg.wasm'];}],
    ['wrong_html',b=>{b.rust.files['index.html']='0'.repeat(64);}],
    ['wrong_worker_lock',b=>{b.rust.files['Cargo.lock']='0'.repeat(64);}],
    ['candidate_execution_claim',b=>{b.moonbit_execution='passed';}],
    ['missing_font',b=>{delete b.rust.embedded_fonts[Object.keys(b.rust.embedded_fonts)[0]];}],
  ].map(([name,mutate])=>{const copy=structuredClone(build);mutate(copy);
    assert.throws(()=>assertProvenance(copy,catalog),name);return {name,rejected:true};});
}

export function decodePng(bytes) {
  assert(Buffer.isBuffer(bytes)&&bytes.length>0&&bytes.length<=8*1024*1024,'Bounded original PNG bytes required');
  const decoder=fileURLToPath(new URL('../scripts/decode_uniform_list_png.py',import.meta.url));
  const result=spawnSync('python3',[decoder],{input:bytes,timeout:10000,maxBuffer:300*300*4+4096});
  if(result.error)throw result.error;
  assert.equal(result.status,0,`Strict PNG decoder: ${result.stderr?.toString().slice(0,2048)}`);
  assert.equal(result.stdout.length,8+300*300*4);assert.equal(result.stdout.readUInt32BE(0),300);assert.equal(result.stdout.readUInt32BE(4),300);
  return {width:300,height:300,data:new Uint8Array(result.stdout.subarray(8))};
}
const rowBytes=1200;
function imageCheck(image) {
  assert.equal(image?.width,300);assert.equal(image?.height,300);assert.equal(image?.data?.length,300*300*4);
}
// Neutral glyph pixels are observations, never OCR, DOM text, canvas readback or supplied telemetry.
export function inspectInk(image) {
  imageCheck(image);const rows=[];let left=300,right=-1,count=0,black=0;
  for(let y=0;y<300;y++) {
    let ink=0;
    for(let x=0;x<300;x++) {
      const o=(y*300+x)*4,[r,g,b,a]=image.data.subarray(o,o+4);
      assert.equal(a,255,'Opaque source white root');assert(Math.max(r,g,b)-Math.min(r,g,b)<=2,'Bounded neutral text ink only');
      if(Math.min(r,g,b)<250) {
        assert(x>=8&&x<120,'Stationary source px_2 text corridor; no shifted horizontal content');
        left=Math.min(left,x);right=Math.max(right,x);count++;ink++;if(Math.max(r,g,b)<80)black++;
      }
      if(x<8||x>=120)assert(r===255&&g===255&&b===255,'White source root outside text');
    }
    rows.push(ink);
  }
  assert(count>300&&count<15000&&black>100,'Actual bounded black text ink required');
  return {rows,left,right,count};
}
export function discoverGeometry(image) {
  const ink=inspectInk(image),bands=[];
  for(let y=0;y<300;y++)if(ink.rows[y]) {
    if(!bands.length||bands.at(-1).bottom!==y)bands.push({top:y,bottom:y+1});else bands.at(-1).bottom++;
  }
  assert(bands.length>=5,'Repeated original row ink bands');
  const pitch=bands[1].top-bands[0].top;
  assert(Number.isSafeInteger(pitch)&&pitch>=16&&pitch<=48,'Bounded observed integral row pitch');
  const top=bands[0].top,bottom=bands[0].bottom;
  assert(top>0&&bottom<pitch&&bottom-top>=6,'Observed full first text row with white line padding');
  for(let i=0;i<bands.length;i++) {
    assert.equal(bands[i].top,top+i*pitch,'Repeated measured row pitch');
    assert.equal(bands[i].bottom,Math.min(300,bottom+i*pitch),'Repeated ink height or actual surface-clipped tail');
  }
  assert.equal(bands.length,Math.ceil((300-top)/pitch),'No omitted visible row ink bands');
  assert(ink.left>=8&&ink.left<=16,'Source padding plus measured font bearing');
  return {pitch,ink_top:top,ink_bottom:bottom,left:ink.left,right:ink.right,
    derivation:'Original initial PNG ink scanlines; no source26px assumption or runtime range telemetry'};
}
export function makeProfile(geometry) {
  const operations=[],captures={initial:{after_operation:0,offset:0}};
  if(!geometry)return {operations,captures};
  const h=geometry.pitch,max=50*h-300;let offset=0;
  assert(Number.isSafeInteger(h)&&h>=16&&h<=48&&max>0);
  const wheel=(name,deltaX,deltaY)=>{
    const action={kind:'wheel',x:150,y:150,deltaX,deltaY};
    // Source constraint only; actual translation must be established from original PNG overlap.
    offset=Math.max(0,Math.min(max,offset+(deltaY!==0?deltaY:deltaX)));
    operations.push({name,action});captures[name]={after_operation:operations.length,offset};
  };
  wheel('before_row_boundary',0,h-1);wheel('at_row_boundary',0,1);wheel('after_row_boundary',0,1);
  wheel('top_after_small',0,-h-1);
  wheel('x_only_partial',h-1,0);wheel('top_after_x',0,-h+1);
  wheel('mixed_y_partial',5*h,h-1);wheel('top_after_mixed',0,-h+1);
  wheel('top_edge_partial',0,geometry.ink_top+1);wheel('top_after_top_edge',0,-geometry.ink_top-1);
  const bottomDelta=(geometry.ink_top+1-(299%h)+h)%h||h;
  wheel('bottom_edge_partial',0,bottomDelta);wheel('top_after_bottom_edge',0,-bottomDelta);
  const stride=Math.floor(208/h)*h;
  for(let i=1;offset<max;i++)wheel(`sweep_${i}`,0,stride);
  wheel('bottom_clamp',0,100000);wheel('bottom_clamp_repeat',0,100000);
  wheel('bottom_reverse',0,-1);wheel('bottom_return',0,1);
  wheel('top_return',0,-100000);wheel('top_clamp_repeat',0,-100000);
  return {operations,captures};
}
export function assertWheelDelivery(events,action) {
  assert.equal(events.length,1,'Exactly one separately requested trusted pixel wheel');
  const event=events[0];
  for(const [key,value] of Object.entries({type:'wheel',trusted:true,target:'CANVAS',x:action.x,y:action.y,
    deltaX:action.deltaX,deltaY:action.deltaY,deltaZ:0,deltaMode:0,shiftKey:false,ctrlKey:false,altKey:false,metaKey:false}))
    assert.equal(event[key],value,`Actual wheel ${key}`);
  assert(Number.isFinite(event.time)&&event.time>=0);assert.equal(event.defaultPrevented,true,'Actual upstream nonpassive wheel prevention');
}
export function validateOperations(report,geometry) {
  const profile=makeProfile(geometry);assert.equal(report.operations.length,profile.operations.length);
  assert.deepEqual(Object.keys(report.captures),Object.keys(profile.captures),'Complete ordered state set');
  assert.equal(report.operation_start,report.startup_events.length);assert.deepEqual(report.startup_events,[],'No unplanned wheel before baseline');
  const delivered=[];
  for(let i=0;i<profile.operations.length;i++) {
    const expected=profile.operations[i],actual=report.operations[i];assert.equal(actual.name,expected.name);assert.deepEqual(actual.action,expected.action);
    assert.equal(actual.input_method,'CDP.Input.dispatchMouseEvent');assert.equal(actual.input_acknowledged,true);
    assert.equal(actual.status,'delivered');assert.equal(actual.post_delivery_animation_frames,2);
    assertWheelDelivery(actual.events,expected.action);delivered.push(...actual.events);
  }
  assert.deepEqual(report.events,delivered,'Complete original wheel stream in exact operation order');
  for(let i=1;i<delivered.length;i++)assert(delivered[i].time>delivered[i-1].time,'Strict wheel chronology');
  for(const [name,state] of Object.entries(profile.captures))assert.equal(report.captures[name].after_operation,state.after_operation);
  return {operations:delivered.length,pixel_wheels:delivered.length};
}
export function validateProfile(images,geometry=discoverGeometry(images.initial)) {
  assert.deepEqual(discoverGeometry(images.initial),geometry,'Independent original initial measurement');
  const profile=makeProfile(geometry),atlas=new Map(),h=geometry.pitch;
  assert.deepEqual(Object.keys(images),Object.keys(profile.captures),'Exact ordered independently captured original PNG states');
  const observations={};let overlaps=0;
  for(const [name,state] of Object.entries(profile.captures)) {
    const image=images[name],ink=inspectInk(image);assert.equal(ink.left,geometry.left,'Stable horizontal ink origin');
    let common=0,newRows=0;
    for(let y=0;y<300;y++) {
      const contentY=state.offset+y,row=image.data.subarray(y*rowBytes,(y+1)*rowBytes);
      const residue=contentY%h;
      assert.equal(ink.rows[y]>0,residue>=geometry.ink_top&&residue<geometry.ink_bottom,'Original repeated ink bands and partial edge output');
      if(atlas.has(contentY)) {
        assert.deepEqual(row,atlas.get(contentY),`${name}: actual original overlapping raster translation at surface y${y}`);common++;
      }else {atlas.set(contentY,row.slice());newRows++;}
    }
    if(name!=='initial'){assert(common>=92,'Overlapping original scanlines prevent disconnected invented endpoint evidence');overlaps+=common;}
    observations[name]={offset_from_source_wheel_constraint:state.offset,matched_original_scanlines:common,new_original_scanlines:newRows,
      original_rgba_sha256:sha256(image.data)};
  }
  assert.equal(atlas.size,50*h,'Source count50 complete paint extent covered through overlapping original frames');
  const row_rasters=[];
  for(let index=0;index<50;index++) {
    const bytes=Buffer.concat(Array.from({length:h},(_,line)=>Buffer.from(atlas.get(index*h+line))));
    row_rasters.push({source_position:index,sha256:sha256(bytes)});
  }
  assert.equal(new Set(row_rasters.map(row=>row.sha256)).size,50,'Fifty distinct observed complete row rasters; no OCR label identity claim');
  assert(inspectInk(images.top_edge_partial).rows[0]>0,'Actual partially clipped top ink');
  assert(inspectInk(images.bottom_edge_partial).rows[299]>0,'Actual partially clipped bottom ink');
  return {measured_pitch:h,source_pitch_hypothesis:26,hypothesis_matches_observation:h===26,
    observed_content_scanlines:atlas.size,endpoint_offset_from_bounded_wheel_and_overlap:50*h-300,
    matched_original_scanlines:overlaps,row_rasters,observations,
    claim:'Bounded original paint/scroll/surface-edge output only; no factory, callback, internal-mask, OCR or native evidence'};
}
export function profileNegativeControls(images,geometry,report) {
  validateProfile(images,geometry);validateOperations(report,geometry);
  const rejected=[],check=(name,run)=>{assert.throws(run,name);rejected.push({name,rejected:true,kind:'corrupted_evidence_sensitivity_not_executed_mutant'});};
  for(const [name,state,replacement] of [
    ['no_scroll_pixels','before_row_boundary','initial'],['wrong_direction','before_row_boundary','after_row_boundary'],
    ['wrong_endpoint','bottom_clamp','initial'],['failed_top_restore','top_return','bottom_clamp'],
    ['horizontal_only_ignored','x_only_partial','initial'],['mixed_axis_wrong','mixed_y_partial','at_row_boundary']])
    check(name,()=>validateProfile({...images,[state]:images[replacement]},geometry));
  const copy=name=>({...images[name],data:images[name].data.slice()});
  const swapped=copy('at_row_boundary'),h=geometry.pitch,a=0,b=h*rowBytes,first=swapped.data.slice(a,b),second=swapped.data.slice(b,b*2);
  assert.notEqual(sha256(first),sha256(second),'Control must swap different original row rasters');swapped.data.set(second,a);swapped.data.set(first,b);
  check('swapped_distinct_row_rasters',()=>validateProfile({...images,at_row_boundary:swapped},geometry));
  for(const [state,y] of [['top_edge_partial',0],['bottom_edge_partial',299]]) {
    const changed=copy(state);changed.data.fill(255,y*rowBytes,(y+1)*rowBytes);
    check(`erased_${state}_ink`,()=>validateProfile({...images,[state]:changed},geometry));
  }
  const changed=copy('before_row_boundary');changed.data.copyWithin(rowBytes,0,299*rowBytes);
  check('wrong_row_pitch_or_translation',()=>validateProfile({...images,before_row_boundary:changed},geometry));
  for(const [name,mutate] of [
    ['missing_wheel',r=>{r.operations[0].events=[];}],['untrusted_wheel',r=>{r.operations[0].events[0].trusted=false;}],
    ['wrong_wheel_coordinate',r=>{r.operations[0].events[0].x++;}],['wrong_wheel_delta',r=>{r.operations[0].events[0].deltaY++;}],
    ['reordered_wheels',r=>{[r.operations[0],r.operations[1]]=[r.operations[1],r.operations[0]];}],
    ['wrong_wheel_units',r=>{r.operations[0].events[0].deltaMode=1;}],
    ['fabricated_x_fallback',r=>{r.operations[4].events[0].deltaY=1;}],
  ]) {const clone=structuredClone(report);mutate(clone);check(name,()=>validateOperations(clone,geometry));}
  return rejected;
}
