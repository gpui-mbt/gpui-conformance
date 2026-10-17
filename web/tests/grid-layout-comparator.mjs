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

export const GRID_LAYOUT=Object.freeze({width:500,height:500,widths:[399,400,401,500],dpr:1,
  revision:'5a5fbe79917971a4d52a96b6ddb04da198a5012e',tree:'990fb995914d51a546b20e5cf0382dafc105c299',
  source:'crates/gpui/examples/grid_layout.rs',sourceBlob:'51f9b13e41fb7913c653d716da3e8ce05a96109d',
  sourceSha256:'c82663a8c48340464f70f96dfa60135f4cd3b48670882b7bc23a9ca787fb261e'});
// Frozen metadata is independent of future candidate registrations.
export const ENGINE=Object.freeze({repository:'gpui-mbt/gpui.mbt',
  revision:'b9916950350b7d433ecca0d6fa88e39c957b8b6b',tree:'be95df375c707bd6cf961ef7959e93772b34a966'});
export const PROFILE_REVISION='unchanged_grid_layout_resize_v1';
export const SOURCE_CONSTRAINTS=Object.freeze([
  'grid_layout.rs:25-65: measured container width <400 selects flex column; width>=400 selects five-column five-row grid',
  'Source block colors white/red/green/blue/black, full size, 1px white dashed border, medium radius',
  'Source gap_1=4px at default rem16; narrow header/footer h_12=48px, TOC/ad h_20=80px, remaining content flex1',
  'Wide header/footer span all five columns; content spans three columns and three rows; ad spans three rows; TOC h_56=224px',
  'Original PNG connected solid-color regions supply measured bounds; source formulas are checked separately with a bounded raster-edge tolerance',
  'Real Playwright viewport changes and trusted resize events; same-document cycle restores original measured solid-color regions',
]);
const HISTORICAL_CATALOG=readFileSync(new URL('./fixtures/grid-layout-rust-only-catalog-b0781104.json',import.meta.url));
assert.equal(sha256(HISTORICAL_CATALOG),'c9879cb868de5f0ad5cc21cb427401bca2bc7e6f3d344196fd625449c0e8b753','Immutable source-only catalog snapshot');
const HASH=/^[0-9a-f]{64}$/;
export function assertProvenance(build,catalog) {
  assert.deepEqual(catalog,JSON.parse(HISTORICAL_CATALOG),'Exact immutable source-only catalog; new candidates require a separate profile');
  assert.equal(build.upstream?.repository,'zed-industries/zed');
  assert.equal(build.upstream?.revision,GRID_LAYOUT.revision);
  assert.deepEqual(build.moonbit,ENGINE,'Baseline must preserve the existing engine pin');
  assert.deepEqual(catalog.upstream,build.upstream);assert.deepEqual(catalog.moonbit,build.moonbit);
  assert.equal(build.lab_tracked_dirty,false);assert.match(build.lab_revision||'',/^[0-9a-f]{40}$/);assert.match(build.lab_tree||'',/^[0-9a-f]{40}$/);
  assert.equal(build.rust?.source_revision,GRID_LAYOUT.revision);assert.equal(build.rust?.source_tree,GRID_LAYOUT.tree);
  assert.equal(build.rust_bundled,true);assert.equal(build.rust?.source_modified,false);
  assert.equal(build.site_kind,'grid_layout_rust_oracle_only');assert.deepEqual(build.implemented,[]);
  assert.equal(build.moonbit_execution,'not_run','Catalog core pin is metadata only, never a candidate execution');assert.equal(build.comparison_status,'not_run');
  assert.equal(build.rust?.oracle_only,true);assert.equal(build.rust?.packaging?.upstream_files_modified,false);
  assert.deepEqual(build.rust_implemented,['grid_layout'],'This independent job must build only the explicit oracle');
  assert(!build.implemented?.includes('grid_layout'),'No MoonBit counterpart may be claimed');
  assert.equal(catalog.examples.filter(entry=>entry.id==='grid_layout').length,0,'Source-only baseline must not invent a matched catalog route');
  assert.equal(build.rust.implemented_subset,null);
  assert.equal(build.rust_oracle_only.length,1,'Exactly one isolated oracle record');
  assert.deepEqual(build.rust_subset_sources||[],[]);
  const records=build.rust_oracle_only.filter(entry=>entry.id==='grid_layout');assert.equal(records.length,1);
  for(const [key,value] of Object.entries({source:GRID_LAYOUT.source,source_blob:GRID_LAYOUT.sourceBlob,
    source_sha256:GRID_LAYOUT.sourceSha256,upstream_revision:GRID_LAYOUT.revision,upstream_tree:GRID_LAYOUT.tree,
    status:'rust_oracle_only',candidate:'not_implemented',width:500,height:500,dpr:1}))assert.equal(records[0][key],value);
  assert.deepEqual(records[0].widths,[399,400,401,500]);
  assert(Number.isFinite(Date.parse(build.rust.build_completed_at_utc||'')),'Actual build completion timestamp required');
  assert.match(build.rust.toolchain||'',/^rustc 1\./);assert.match(build.rust.bindings||'',/^wasm-bindgen 0\.2\.129$/);
  assert.deepEqual(build.rust.packaging.additional_bins,[{name:'grid_layout',source:GRID_LAYOUT.source}]);
  for(const file of ['grid_layout.js','grid_layout_bg.wasm','host.mjs','unchanged-source/grid_layout.rs','packaging-Cargo.toml'])
    assert.match(build.rust.files?.[file]||'',HASH,`Pinned Rust file ${file}`);
  assert.equal(build.rust.files['unchanged-source/grid_layout.rs'],GRID_LAYOUT.sourceSha256);
  assert.equal(build.rust.files['index.html'],'8f6806a2ae5f935a8212171af3890fb1460c5ab30a357032bf541222b2bd6669');
  assert.equal(build.rust.files['Cargo.lock'],'d60bd2d8e87639d33f67b740796a06078c2c2e3df9593dcbd699c4abc37919da');
  assert.equal(build.rust.files['packaging-Cargo.toml'],build.rust.packaging.manifest_sha256,'Retained relocated Cargo manifest hash');
  const fonts=Object.values(build.rust.embedded_fonts||{});assert.equal(fonts.length,8,'All eight upstream embedded font inputs required');
  assert.deepEqual(Object.fromEntries(Object.entries(build.rust.embedded_fonts).map(([path,font])=>[path,font.sha256])),EMBEDDED_FONTS,'Exact upstream embedded-font bytes');
  for(const font of fonts) {assert.match(font.sha256||'',HASH);assert.equal(build.rust.files[font.file],font.sha256);}
  assert(build.rust.command.includes('+nightly-2026-10-14'));assert(build.rust.command.includes('--locked'));
  assert.deepEqual(build.rust.command.filter((_argument,index,array)=>array[index-1]==='--bin'),['grid_layout']);
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
    ['candidate_claim',b=>{b.implemented.push('grid_layout');}],
    ['wrong_engine',b=>{b.moonbit.revision='0'.repeat(40);}],
    ['missing_wasm',b=>{delete b.rust.files['grid_layout_bg.wasm'];}],
    ['wrong_html',b=>{b.rust.files['index.html']='0'.repeat(64);}],
    ['wrong_worker_lock',b=>{b.rust.files['Cargo.lock']='0'.repeat(64);}],
    ['candidate_execution_claim',b=>{b.moonbit_execution='passed';}],
    ['missing_font',b=>{delete b.rust.embedded_fonts[Object.keys(b.rust.embedded_fonts)[0]];}],
  ].map(([name,mutate])=>{const copy=structuredClone(build);mutate(copy);
    assert.throws(()=>assertProvenance(copy,catalog),name);return {name,rejected:true};});
}


export const VIEWPORT_SEQUENCE=Object.freeze([
  {name:'initial',width:500},{name:'narrow399',width:399},{name:'threshold400',width:400},
  {name:'wide401',width:401},{name:'restore500',width:500},{name:'return399',width:399},
  {name:'return400',width:400},{name:'final500',width:500},
].map(state=>Object.freeze({...state,height:500,dpr:1})));
export const UNVERIFIED=Object.freeze(['MoonBit counterpart/comparison','Text content, shaping or exact glyph pixels',
  'Dashed border, rounded corner or shadow raster fidelity','Exact full-image or native parity',
  'Internal container-query callback count, nested assigned-size isolation, layout internals or hidden offscreen work',
  'Other browsers/GPUs/viewports/DPRs']);
export function decodePng(bytes) {
  assert(Buffer.isBuffer(bytes)&&bytes.length>0&&bytes.length<=8*1024*1024,'Bounded original PNG bytes required');
  const result=spawnSync('python3',[fileURLToPath(new URL('../scripts/decode_grid_layout_png.py',import.meta.url))],
    {input:bytes,timeout:10000,maxBuffer:500*500*4+4096});
  if(result.error)throw result.error;
  assert.equal(result.status,0,`Strict PNG decoder: ${result.stderr?.toString().slice(0,2048)}`);
  const width=result.stdout.readUInt32BE(0),height=result.stdout.readUInt32BE(4);
  assert(GRID_LAYOUT.widths.includes(width));assert.equal(height,500);assert.equal(result.stdout.length,8+width*height*4);
  return {width,height,data:new Uint8Array(result.stdout.subarray(8))};
}
export const COLORS=Object.freeze({header:[255,255,255,255],toc:[255,0,0,255],content:[0,128,0,255],ad:[0,0,255,255],footer:[0,0,0,255]});
const BACKGROUND=[80,80,80,255];
const equalColor=(data,index,color)=>color.every((value,channel)=>data[4*index+channel]===value);
function checkImage(image) {
  assert(GRID_LAYOUT.widths.includes(image?.width),'Exact requested original image width');assert.equal(image?.height,500);
  assert.equal(image?.data?.length,image.width*image.height*4,'Complete original RGBA');
  for(let i=3;i<image.data.length;i+=4)assert.equal(image.data[i],255,'Opaque original viewport');
}
// Discover components before consulting any layout formula. Connected solid fill
// tolerates text holes and excludes detached glyph/border fragments. These bounds
// describe observed fill pixels, not an inferred exact curved/bordered box edge.
export function discoverGeometry(image) {
  checkImage(image);const {width,height,data}=image,count=width*height;
  const labels=new Int8Array(count);labels.fill(-1);const colors=Object.values(COLORS),names=Object.keys(COLORS);
  for(let p=0;p<count;p++)for(let c=0;c<colors.length;c++)if(equalColor(data,p,colors[c])){labels[p]=c;break;}
  const visited=new Uint8Array(count),queue=new Int32Array(count),components=names.map(()=>[]);
  for(let p=0;p<count;p++) {
    const label=labels[p];if(label<0||visited[p])continue;
    let start=0,end=1,left=width,right=0,top=height,bottom=0;queue[0]=p;visited[p]=1;
    while(start<end) {
      const current=queue[start++],x=current%width,y=Math.floor(current/width);
      left=Math.min(left,x);right=Math.max(right,x+1);top=Math.min(top,y);bottom=Math.max(bottom,y+1);
      for(const next of [x>0?current-1:-1,x+1<width?current+1:-1,y>0?current-width:-1,y+1<height?current+width:-1])
        if(next>=0&&!visited[next]&&labels[next]===label){visited[next]=1;queue[end++]=next;}
    }
    components[label].push({left,right,top,bottom,width:right-left,height:bottom-top,pixels:end});
  }
  const regions={};
  for(const [index,name] of names.entries()) {
    components[index].sort((a,b)=>b.pixels-a.pixels);const region=components[index][0];
    assert(region&&region.pixels>=1000,`${name}: substantial connected original solid fill required`);
    assert(region.pixels/(region.width*region.height)>=0.75,`${name}: solid fill density, no disconnected outline or thin surrogate`);
    assert(!components[index][1]||components[index][1].pixels<region.pixels*0.15,`${name}: unique dominant fill region`);
    regions[name]={...region,rgba:COLORS[name],coverage:region.pixels/(region.width*region.height)};
  }
  return {width,height,regions,derivation:'Largest connected exact-color components in complete original PNG; no DOM/scene geometry, fabricated image, crop or expected-coordinate search'};
}
// Source constants are independent expectations, never inputs to the component
// discovery. minmax(0,1fr) keeps TOC h56 from enlarging a grid row.
export function sourceExpectations(width) {
  const rem=16,gap=rem/4,height=500,box=(left,top,width,height)=>({left,top,right:left+width,bottom:top+height,width,height});
  if(width<400) {
    const heights={header:3*rem,toc:5*rem,content:height-2*3*rem-2*5*rem-4*gap,ad:5*rem,footer:3*rem},regions={};
    let top=0;
    for(const [name,blockHeight] of Object.entries(heights)){regions[name]=box(0,top,width,blockHeight);top+=blockHeight+gap;}
    return {mode:'stack',source_default_rem:rem,gap,regions};
  }
  const column=(width-4*gap)/5,row=(height-4*gap)/5;
  return {mode:'grid',source_default_rem:rem,gap,column_track:column,row_track:row,regions:{
    header:box(0,0,width,row),toc:box(0,row+gap,column,14*rem),content:box(column+gap,row+gap,3*column+2*gap,3*row+2*gap),
    ad:box(4*(column+gap),row+gap,column,3*row+2*gap),footer:box(0,4*(row+gap),width,row)}};
}
function close(actual,wanted,label,tolerance=2) {
  assert(Math.abs(actual-wanted)<=tolerance,`${label}: measured ${actual}, source expectation ${wanted}, max raster-edge uncertainty ${tolerance}px`);
}
function backgroundLine(image,axis,fixed,start,end,label) {
  let checked=0;
  for(let moving=Math.ceil(start);moving<Math.floor(end);moving++) {
    const x=axis==='horizontal'?moving:Math.floor(fixed),y=axis==='horizontal'?Math.floor(fixed):moving;
    assert(equalColor(image.data,y*image.width+x,BACKGROUND),`${label}: original gray gap/vacancy at (${x},${y})`);checked++;
  }
  assert(checked>10);return checked;
}
function measuredGrayGap(image,axis,between,cross,label) {
  const limit=axis==='horizontal'?image.width:image.height;
  const isGray=position=>equalColor(image.data,axis==='horizontal'?Math.floor(cross)*image.width+position:position*image.width+Math.floor(cross),BACKGROUND);
  const middle=Math.floor(between);assert(isGray(middle),`${label}: measured gap midpoint must be original gray`);
  let start=middle,end=middle+1;
  while(start>0&&isGray(start-1))start--;
  while(end<limit&&isGray(end))end++;
  // Unlike fill-to-fill separation, this measures the exposed gray itself.
  // At fractional edges one physical sample can be blended with a border.
  close(end-start,4,label,1);
  return {axis,cross:Math.floor(cross),start,end,pixels:end-start};
}
export function inspectLayout(image) {
  const geometry=discoverGeometry(image),expected=sourceExpectations(image.width),regions=geometry.regions;
  for(const [name,region] of Object.entries(regions))for(const edge of ['left','right','top','bottom'])
    close(region[edge],expected.regions[name][edge],`${name} ${edge}`);
  let gapPixels=0;const measuredGaps=[];
  if(expected.mode==='stack') {
    const order=['header','toc','content','ad','footer'];
    for(let i=1;i<order.length;i++) {
      const previous=regions[order[i-1]],next=regions[order[i]];
      assert(next.top>previous.bottom,'Measured single-column source order');
      close(next.top-previous.bottom,expected.gap,`${order[i]} measured fill separation`,4);
      measuredGaps.push(measuredGrayGap(image,'vertical',(previous.bottom+next.top)/2,image.width/2,`${order[i]} exposed gap`));
      gapPixels+=backgroundLine(image,'horizontal',(expected.regions[order[i-1]].bottom+expected.regions[order[i]].top)/2,8,image.width-8,'Stack gap');
    }
  } else {
    assert(regions.toc.right<regions.content.left&&regions.content.right<regions.ad.left,'Measured TOC/content/ad source order');
    assert(regions.toc.bottom>regions.toc.top+2*expected.row_track,'Fixed-height TOC overhangs its single zero-min grid row');
    assert(regions.toc.bottom<regions.content.bottom-20,'TOC does not stretch to the three-row content span');
    for(const [left,right] of [['toc','content'],['content','ad']]) {
      close(regions[right].left-regions[left].right,expected.gap,`${left}/${right} measured fill separation`,4);
      measuredGaps.push(measuredGrayGap(image,'horizontal',(regions[left].right+regions[right].left)/2,regions.content.top+64,`${left}/${right} exposed gap`));
      gapPixels+=backgroundLine(image,'vertical',(expected.regions[left].right+expected.regions[right].left)/2,expected.regions.content.top+32,expected.regions.content.bottom-8,'Grid column gap');
    }
    for(const y of [(regions.header.bottom+regions.content.top)/2,(regions.content.bottom+regions.footer.top)/2]) {
      measuredGaps.push(measuredGrayGap(image,'vertical',y,image.width/2,'Grid exposed row gap'));
      gapPixels+=backgroundLine(image,'horizontal',y,8,image.width-8,'Grid row gap');
    }
    gapPixels+=backgroundLine(image,'horizontal',(expected.regions.toc.bottom+expected.regions.footer.top)/2,8,expected.regions.toc.right-8,'Unoccupied lower-left grid area');
  }
  return {geometry,source_expectations:expected,measured_exposed_gaps:measuredGaps,checked_gap_or_vacancy_pixels:gapPixels,
    edge_tolerance_physical_pixels:2,exposed_gap_tolerance_physical_pixels:1,fill_separation_tolerance_physical_pixels:4,
    single_pixel_geometry_regression_detection:'not_guaranteed',claim:'Measured dominant solid fills, source order/gap/track/span/threshold constraints only'};
}
export function makeProfile() {
  return {captures:Object.fromEntries(VIEWPORT_SEQUENCE.map((state,index)=>[state.name,{...state,after_operation:index}])),
    operations:VIEWPORT_SEQUENCE.slice(1).map(state=>({name:state.name,action:{kind:'viewport_resize',width:state.width,height:state.height}}))};
}
export function assertViewport(observation,width) {
  assert.deepEqual(observation,{inner:{width,height:500},dpr:1,canvas:{bounds:{x:0,y:0,width,height:500},backing:{width,height:500}}},'Actual browser inner size and complete canvas backing/bounds');
}
export function assertResizeDelivery(events,action) {
  assert(events.length>=1&&events.length<=4,'Bounded actual trusted resize event(s)');
  for(const event of events) {
    assert.equal(event.type,'resize');assert.equal(event.trusted,true);assert.equal(event.target,'WINDOW');
    assert.equal(event.width,action.width);assert.equal(event.height,action.height);assert.equal(event.dpr,1);
    assert(Number.isFinite(event.time)&&event.time>=0);
  }
}
export function validateOperations(report) {
  const profile=makeProfile();assert.deepEqual(Object.keys(report.captures),Object.keys(profile.captures));
  assert.equal(report.operations.length,profile.operations.length);assert.equal(report.operation_start,report.startup_events.length);
  assertViewport(report.initial_viewport,500);
  const delivered=[];
  for(const [index,expected] of profile.operations.entries()) {
    const actual=report.operations[index];assert.equal(actual.name,expected.name);assert.deepEqual(actual.action,expected.action);
    assert.equal(actual.input_method,'Playwright.page.setViewportSize');assert.equal(actual.input_acknowledged,true);
    assert.equal(actual.status,'delivered');assert.equal(actual.post_delivery_animation_frames,2);
    assert.deepEqual(actual.before,index?report.operations[index-1].after:report.initial_viewport);
    assertViewport(actual.after,expected.action.width);assertResizeDelivery(actual.events,expected.action);delivered.push(...actual.events);
    assert.equal(actual.document_id,report.document_id,'Resize must not navigate/recreate the example');
  }
  assert.match(report.document_id||'',/^[0-9a-f-]{36}$/);assert.equal(report.navigation_count,1,'One original document, no reload at breakpoint');
  assert.deepEqual(report.events,[...report.startup_events,...delivered],'Complete original resize stream');
  for(let i=1;i<report.events.length;i++)assert(report.events[i].time>report.events[i-1].time,'Strict resize chronology');
  for(const state of VIEWPORT_SEQUENCE)assertViewport(report.captures[state.name].viewport,state.width);
  return {viewport_changes:delivered.length,requested_resizes:profile.operations.length,one_document:true};
}
function sameRegions(left,right,label) {
  assert.deepEqual(left.geometry.regions,right.geometry.regions,label);
}
export function validateProfile(images) {
  assert.deepEqual(Object.keys(images),VIEWPORT_SEQUENCE.map(state=>state.name));
  const observations={};
  for(const state of VIEWPORT_SEQUENCE) {
    assert.equal(images[state.name].width,state.width);observations[state.name]=inspectLayout(images[state.name]);
  }
  for(const state of ['restore500','final500'])sameRegions(observations.initial,observations[state],'Original500 solid-color geometry and counts restore');
  sameRegions(observations.narrow399,observations.return399,'Original399 solid-color geometry and counts restore');
  sameRegions(observations.threshold400,observations.return400,'Original400 solid-color geometry and counts restore');
  return {observations,restoration:'All independently measured solid-color component bounds and counts match on repeated viewport widths',
    threshold:'399 stacks;400/401/500 use grid',full_image_restoration:'not_claimed'};
}
export function profileNegativeControls(images,report) {
  validateProfile(images);validateOperations(report);
  const controls=[],check=(name,run)=>{assert.throws(run,name);controls.push({name,rejected:true,kind:'corrupted_evidence_sensitivity_not_executed_mutant'});};
  for(const [name,state,replacement] of [['ignored_resize','narrow399','initial'],['threshold_off_by_one','threshold400','narrow399'],['failed_restore','restore500','wide401']])
    check(name,()=>validateProfile({...images,[state]:images[replacement]}));
  const copy=name=>({...images[name],data:images[name].data.slice()});
  const swapped=copy('initial');for(let p=0;p<swapped.width*swapped.height;p++) {
    if(equalColor(swapped.data,p,COLORS.toc))swapped.data.set(COLORS.ad,4*p);
    else if(equalColor(swapped.data,p,COLORS.ad))swapped.data.set(COLORS.toc,4*p);
  }
  check('swapped_toc_ad_order',()=>validateProfile({...images,initial:swapped}));
  // Pad a corrupted copy of the actual399 image to400; dimensions alone must
  // not be what rejects a strict-threshold branch error. Original PNGs stay intact.
  const wrongBranch={width:400,height:500,data:new Uint8Array(400*500*4)};
  for(let y=0;y<500;y++) {
    wrongBranch.data.set(images.narrow399.data.subarray(y*399*4,(y+1)*399*4),y*400*4);
    wrongBranch.data.set(BACKGROUND,4*(y*400+399));
  }
  check('stack_branch_at_exact400_same_dimensions',()=>validateProfile({...images,threshold400:wrongBranch}));
  const restored=copy('restore500');
  for(let p=0;p<restored.width*restored.height;p++)if(equalColor(restored.data,p,COLORS.toc)){restored.data.set(BACKGROUND,4*p);break;}
  check('restoration_lost_original_fill_pixel',()=>validateProfile({...images,restore500:restored}));

  const erased=copy('initial'),geometry=discoverGeometry(erased),content=geometry.regions.content;
  for(let y=content.top;y<content.bottom;y++)for(let x=Math.floor((content.left+content.right)/2);x<content.right;x++)erased.data.set(BACKGROUND,4*(y*erased.width+x));
  check('shortened_content_span',()=>validateProfile({...images,initial:erased}));
  for(const [name,region,edge] of [['toc_lost_fixed_height','toc','bottom'],['header_not_full_span','header','right'],['incorrect_row_expansion','header','bottom']]) {
    const changed=copy('initial'),bounds=discoverGeometry(changed).regions[region];
    for(let y=bounds.top;y<bounds.bottom;y++)for(let x=bounds.left;x<bounds.right;x++)
      if((edge==='bottom'&&y>=bounds.bottom-20)||(edge==='right'&&x>=bounds.right-20))changed.data.set(BACKGROUND,4*(y*changed.width+x));
    check(name,()=>validateProfile({...images,initial:changed}));
  }

  const missing=copy('initial');for(let p=0;p<missing.width*missing.height;p++)if(equalColor(missing.data,p,COLORS.footer))missing.data.set(BACKGROUND,4*p);
  check('missing_footer',()=>validateProfile({...images,initial:missing}));
  const gap=copy('narrow399');for(let x=8;x<gap.width-8;x++)gap.data.set(COLORS.ad,4*(50*gap.width+x));
  check('corrupted_gap',()=>validateProfile({...images,narrow399:gap}));
  for(const [name,mutate] of [['missing_resize',r=>{r.operations[0].events=[];}],['untrusted_resize',r=>{r.operations[0].events[0].trusted=false;}],
    ['wrong_viewport',r=>{r.operations[0].after.inner.width++;}],['wrong_backing',r=>{r.captures.narrow399.viewport.canvas.backing.width++;}],
    ['reordered_resizes',r=>{[r.operations[0],r.operations[1]]=[r.operations[1],r.operations[0]];}],['reloaded_example',r=>{r.navigation_count++;}],
    ['different_document',r=>{r.operations[0].document_id='0'.repeat(36);}]] ) {
    const changed=structuredClone(report);mutate(changed);check(name,()=>validateOperations(changed));
  }
  return controls;
}
