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

export const ANCHOR=Object.freeze({width:750,height:600,widths:[750,480],dpr:1,
  revision:'5a5fbe79917971a4d52a96b6ddb04da198a5012e',tree:'990fb995914d51a546b20e5cf0382dafc105c299',
  source:'crates/gpui/examples/anchor.rs',sourceBlob:'b4b280b714a61cea2cd3f3a8ffd82a8f0000eb6b',
  sourceSha256:'5be423ce91b36db94857a8f7758f7f5967d0103b77941fa7bc7c5a64e3c4fe72'});
// Frozen metadata is independent of future candidate registrations.
export const ENGINE=Object.freeze({repository:'gpui-mbt/gpui.mbt',
  revision:'aafa754affa049c1eaf69c75c1d04c5d895d3677',tree:'a6d5e8a048b6b4bc4a9f30912d8edf93581a8bd9'});
export const PROFILE_REVISION='unchanged_anchor_hover_local_snap_shadow_composite_v2';
// Source-permitted fill envelope, not an empirical color tolerance or an
// exact-opacity/shadow-kernel assertion. Black drop shadows paint before fill.
// Four Gaussian midpoint samples have spacing <=1.5 sigma; their positive sum
// is bounded by the infinite Gaussian lattice:1+2q/(1-q)<1.00031,
// q=exp(-2*pi*pi/1.5^2).1.001 also accommodates f32 arithmetic. Each x integral
// lies in[0,1]. Apply the two alpha0.1 shadows, then alpha0.75 fill, allowing
// downward8-bit rounding at each layer:floor(floor(floor(255*.8999)*.8999)*.25)=51.
export const POPUP_COMPOSITING=Object.freeze({
  shadow_alphas:Object.freeze([0.1,0.1]),popup_alpha:0.75,shadow_coverage_upper:1.001,
  minimum_gray:51,maximum_gray:64,qualification:'source_permitted_interval_not_exact_decorative_compositing_parity',
  source_inputs:Object.freeze([
    Object.freeze({path:'crates/gpui_macros/src/styles.rs',lines:'428-438',blob:'4a1bb5c98a3efbb8da8ab3274b8d8ef1e34a08d4',sha256:'5fbd5dac9b7cdc954860a018f6b6925e49c82b4dcfe29424ecea828d47a3ff40'}),
    Object.freeze({path:'crates/gpui/src/style.rs',lines:'691-740',blob:'9150fdded91b817305454f18beb0a0b7d6c5966a',sha256:'b4a0e838fc7050cef25f71aae623cf86010c2ec361600479d24ce1aaff91bdc1'}),
    Object.freeze({path:'crates/gpui/src/window.rs',lines:'4572-4605',blob:'33fa14bfea6ebad50743d6d4014955d1055ef772',sha256:'d85123a09e45761a3a60e196157caa5ceee0e61a9b4adfde484052a31eb4b64a'}),
    Object.freeze({path:'crates/gpui_wgpu/src/shaders.wgsl',lines:'320-341,391-395,1000-1045',blob:'718cb7595d86f73cd91a65bcbf42682004dbba4d',sha256:'1d91f2c8a1958a241f1b659a4137c160592c8076b9be09049db4c9fb9a344529'}),
    Object.freeze({path:'crates/gpui_wgpu/src/wgpu_renderer.rs',lines:'383-392,708-718',blob:'ff4af7d26e1e6706bdd02e0079fea46ace274086',sha256:'3d1f48b13e27ef2b9fff7c77d0046894f9904426900d44a1460aef021a7f6cc2'}),
  ]),
});
export const SOURCE_CONSTRAINTS=Object.freeze([
  'anchor.rs:22-43:120x65 button resolved positions; eight anchor corners and inert unlabeled center',
  'anchor.rs:102-179:fixed512 grid,3 columns,gap24,relative wrappers,hover black/white,deferred Local anchored popup,snap_to_window',
  'anchored.rs:121-221:child-union size,Local origin plus authored position,window clamp,right then left,bottom then top,logical-pixel rounded translation',
  'deferred.rs:50-79:child layout preserved; original element offset deferred after ordinary ancestor paint',
  'Source static block origin after65px preceding child is an explicit hypothesis checked against all eight measured alignments, not runtime-instrumented state',
  'shadow_sm:two black alpha0.1 drop shadows before75%-black fill; achromatic51..64 source-permitted compositing envelope, not exact opacity/shadow parity',
  'Two original complete PNGs per state; measured components supply pointer targets and visible bounds; source expectations are separate',
]);
const HISTORICAL_CATALOG=readFileSync(new URL('./fixtures/anchor-rust-only-catalog-a20e5888.json',import.meta.url));
assert.equal(sha256(HISTORICAL_CATALOG),'2bf21a873708712eeb43cfb028138b15f8859ae6660c73407b7e83b4ae9adae8','Immutable source-only catalog snapshot');
const HASH=/^[0-9a-f]{64}$/;
export function assertProvenance(build,catalog) {
  assert.deepEqual(catalog,JSON.parse(HISTORICAL_CATALOG),'Exact immutable source-only catalog; new candidates require a separate profile');
  assert.equal(build.upstream?.repository,'zed-industries/zed');
  assert.equal(build.upstream?.revision,ANCHOR.revision);
  assert.deepEqual(build.moonbit,ENGINE,'Baseline must preserve the existing engine pin');
  assert.deepEqual(catalog.upstream,build.upstream);assert.deepEqual(catalog.moonbit,build.moonbit);
  assert.equal(build.lab_tracked_dirty,false);assert.match(build.lab_revision||'',/^[0-9a-f]{40}$/);assert.match(build.lab_tree||'',/^[0-9a-f]{40}$/);
  assert.equal(build.rust?.source_revision,ANCHOR.revision);assert.equal(build.rust?.source_tree,ANCHOR.tree);
  assert.equal(build.rust_bundled,true);assert.equal(build.rust?.source_modified,false);
  assert.equal(build.site_kind,'anchor_rust_oracle_only');assert.deepEqual(build.implemented,[]);
  assert.equal(build.moonbit_execution,'not_run','Catalog core pin is metadata only, never a candidate execution');assert.equal(build.comparison_status,'not_run');
  assert.equal(build.rust?.oracle_only,true);assert.equal(build.rust?.packaging?.upstream_files_modified,false);
  assert.deepEqual(build.rust_implemented,['anchor'],'This independent job must build only the explicit oracle');
  assert(!build.implemented?.includes('anchor'),'No MoonBit counterpart may be claimed');
  assert.equal(catalog.examples.filter(entry=>entry.id==='anchor').length,0,'Source-only baseline must not invent a matched catalog route');
  assert.equal(build.rust.implemented_subset,null);
  assert.equal(build.rust_oracle_only.length,1,'Exactly one isolated oracle record');
  assert.deepEqual(build.rust_subset_sources||[],[]);
  const records=build.rust_oracle_only.filter(entry=>entry.id==='anchor');assert.equal(records.length,1);
  for(const [key,value] of Object.entries({source:ANCHOR.source,source_blob:ANCHOR.sourceBlob,
    source_sha256:ANCHOR.sourceSha256,upstream_revision:ANCHOR.revision,upstream_tree:ANCHOR.tree,
    status:'rust_oracle_only',candidate:'not_implemented',width:750,height:600,dpr:1}))assert.equal(records[0][key],value);
  assert.deepEqual(records[0].widths,[750,480]);
  assert(Number.isFinite(Date.parse(build.rust.build_completed_at_utc||'')),'Actual build completion timestamp required');
  assert.match(build.rust.toolchain||'',/^rustc 1\./);assert.match(build.rust.bindings||'',/^wasm-bindgen 0\.2\.129$/);
  assert.deepEqual(build.rust.packaging.additional_bins,[{name:'anchor',source:ANCHOR.source}]);
  for(const file of ['anchor.js','anchor_bg.wasm','host.mjs','unchanged-source/anchor.rs','packaging-Cargo.toml'])
    assert.match(build.rust.files?.[file]||'',HASH,`Pinned Rust file ${file}`);
  assert.equal(build.rust.files['unchanged-source/anchor.rs'],ANCHOR.sourceSha256);
  assert.equal(build.rust.files['index.html'],'8f6806a2ae5f935a8212171af3890fb1460c5ab30a357032bf541222b2bd6669');
  assert.equal(build.rust.files['Cargo.lock'],'d60bd2d8e87639d33f67b740796a06078c2c2e3df9593dcbd699c4abc37919da');
  assert.equal(build.rust.files['packaging-Cargo.toml'],build.rust.packaging.manifest_sha256,'Retained relocated Cargo manifest hash');
  const fonts=Object.values(build.rust.embedded_fonts||{});assert.equal(fonts.length,8,'All eight upstream embedded font inputs required');
  assert.deepEqual(Object.fromEntries(Object.entries(build.rust.embedded_fonts).map(([path,font])=>[path,font.sha256])),EMBEDDED_FONTS,'Exact upstream embedded-font bytes');
  for(const font of fonts) {assert.match(font.sha256||'',HASH);assert.equal(build.rust.files[font.file],font.sha256);}
  assert(build.rust.command.includes('+nightly-2026-10-14'));assert(build.rust.command.includes('--locked'));
  assert.deepEqual(build.rust.command.filter((_argument,index,array)=>array[index-1]==='--bin'),['anchor']);
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
    ['candidate_claim',b=>{b.implemented.push('anchor');}],
    ['wrong_engine',b=>{b.moonbit.revision='0'.repeat(40);}],
    ['missing_wasm',b=>{delete b.rust.files['anchor_bg.wasm'];}],
    ['wrong_html',b=>{b.rust.files['index.html']='0'.repeat(64);}],
    ['wrong_worker_lock',b=>{b.rust.files['Cargo.lock']='0'.repeat(64);}],
    ['candidate_execution_claim',b=>{b.moonbit_execution='passed';}],
    ['missing_font',b=>{delete b.rust.embedded_fonts[Object.keys(b.rust.embedded_fonts)[0]];}],
  ].map(([name,mutate])=>{const copy=structuredClone(build);mutate(copy);
    assert.throws(()=>assertProvenance(copy,catalog),name);return {name,rejected:true};});
}


export const ANCHORS=Object.freeze(['TopLeft','TopCenter','TopRight','LeftCenter','RightCenter','BottomLeft','BottomCenter','BottomRight']);
const indices=[0,1,2,3,5,6,7,8];
const states=[{name:'initial',width:750,hover:null,phase:'wide',action:null}];
for(const [phase,width] of [['wide',750],['narrow',480]]) {
  if(phase==='narrow')states.push({name:'narrowIdle',width,hover:null,phase,action:{kind:'viewport_resize',width,height:600}});
  for(const anchor of [...ANCHORS,'Center']) {
    states.push({name:phase+anchor,width,hover:anchor==='Center'?null:anchor,phase,action:{kind:'pointer_move',target:anchor}});
    states.push({name:phase+anchor+'Exit',width,hover:null,phase,action:{kind:'pointer_move',target:'safe'}});
  }
}
states.push({name:'restoredIdle',width:750,hover:null,phase:'wide',action:{kind:'viewport_resize',width:750,height:600}},
  {name:'repeatTopLeft',width:750,hover:'TopLeft',phase:'wide',action:{kind:'pointer_move',target:'TopLeft'}},
  {name:'repeatTopLeftExit',width:750,hover:null,phase:'wide',action:{kind:'pointer_move',target:'safe'}});
export const VIEWPORT_SEQUENCE=Object.freeze(states.map((s,i)=>Object.freeze({...s,height:600,dpr:1,after_operation:i})));
export const UNVERIFIED=Object.freeze(JSON.parse(readFileSync(new URL('../oracles/anchor.json',import.meta.url))).unverified);
export function makeProfile(){return {captures:Object.fromEntries(VIEWPORT_SEQUENCE.map(s=>[s.name,s])),operations:VIEWPORT_SEQUENCE.slice(1).map(s=>({name:s.name,action:s.action}))};}
export function decodePng(bytes) {
  assert(Buffer.isBuffer(bytes)&&bytes.length>0&&bytes.length<=8*1024*1024,'Bounded original PNG bytes required');
  const r=spawnSync('python3',[fileURLToPath(new URL('../scripts/decode_anchor_png.py',import.meta.url))],{input:bytes,timeout:10000,maxBuffer:750*600*4+4096});
  if(r.error)throw r.error;assert.equal(r.status,0,`Strict PNG decoder: ${r.stderr?.toString().slice(0,2048)}`);
  const width=r.stdout.readUInt32BE(0),height=r.stdout.readUInt32BE(4);
  assert(ANCHOR.widths.includes(width));assert.equal(height,600);assert.equal(r.stdout.length,8+width*height*4);
  return {width,height,data:new Uint8Array(r.stdout.subarray(8))};
}
function checkImage(image) {
  assert(ANCHOR.widths.includes(image?.width));assert.equal(image?.height,600);assert.equal(image.data?.length,image.width*image.height*4);
  for(let i=3;i<image.data.length;i+=4)assert.equal(image.data[i],255,'Complete opaque viewport');
}
const close=(actual,wanted,label,tolerance=2)=>assert(Math.abs(actual-wanted)<=tolerance,`${label}: observed ${actual}, hypothesis ${wanted}, max raster uncertainty ${tolerance}px`);
// Exhaustive whole-original-image connected components. No source coordinates,
// expected rectangles, report geometry, DOM scene or candidate state enter here.
function components(image,predicate,diagonals=false) {
  checkImage(image);const {width:w,height:h,data}=image,n=w*h,mask=new Uint8Array(n),seen=new Uint8Array(n),queue=new Int32Array(n),found=[];
  for(let p=0;p<n;p++)mask[p]=predicate(data,p*4)?1:0;
  for(let p=0;p<n;p++)if(mask[p]&&!seen[p]) {
    let a=0,b=1,left=w,right=0,top=h,bottom=0;queue[0]=p;seen[p]=1;
    while(a<b) {
      const q=queue[a++],x=q%w,y=Math.floor(q/w);left=Math.min(left,x);right=Math.max(right,x+1);top=Math.min(top,y);bottom=Math.max(bottom,y+1);
      for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++)if((dx||dy)&&(diagonals||!dx||!dy)) {
        const xx=x+dx,yy=y+dy,z=yy*w+xx;
        if(xx>=0&&xx<w&&yy>=0&&yy<h&&mask[z]&&!seen[z]){seen[z]=1;queue[b++]=z;}
      }
    }
    found.push({left,right,top,bottom,width:right-left,height:bottom-top,pixels:b,coverage:b/((right-left)*(bottom-top))});
  }
  return found.sort((a,b)=>b.pixels-a.pixels);
}
const dark=(d,p)=>d[p]<=220&&d[p]===d[p+1]&&d[p]===d[p+2];
const black=(d,p)=>d[p]===0&&d[p+1]===0&&d[p+2]===0;
const gray=(d,p)=>d[p]>=POPUP_COMPOSITING.minimum_gray&&d[p]<=POPUP_COMPOSITING.maximum_gray&&d[p]===d[p+1]&&d[p]===d[p+2];
export function discoverButtons(image) {
  const outlines=components(image,dark,true).filter(b=>b.width>=80&&b.width<=122&&b.height>=63&&b.height<=67&&b.pixels>=180&&b.pixels<=650&&b.coverage<0.12);
  assert.equal(outlines.length,8,'Exactly eight independently discovered complete/clipped outline components');
  const ordered=outlines.sort((a,b)=>a.top-b.top||a.left-b.left),rows=[];
  for(const b of ordered){let row=rows.at(-1);if(!row||Math.abs(row[0].top-b.top)>2){row=[];rows.push(row);}row.push(b);}
  assert.deepEqual(rows.map(r=>r.length),[3,2,3],'Source three-row order and inert center vacancy');
  for(const row of rows)row.sort((a,b)=>a.left-b.left);
  const buttons={};rows.flat().forEach((b,i)=>{buttons[ANCHORS[i]]={...b,index:indices[i],visible_bounds_only:true};});
  const center={x:(buttons.TopCenter.left+buttons.TopCenter.right)/2,y:(buttons.LeftCenter.top+buttons.LeftCenter.bottom)/2};
  const safe={x:10,y:10};
  for(const p of [safe,center])for(let y=Math.floor(p.y)-3;y<=Math.floor(p.y)+3;y++)for(let x=Math.floor(p.x)-3;x<=Math.floor(p.x)+3;x++)
    assert.deepEqual([...image.data.subarray(4*(y*image.width+x),4*(y*image.width+x)+4)],[255,255,255,255],'Observed blank interior safe/center patch');
  return {width:image.width,height:image.height,buttons,center,safe,derivation:'Exhaustive original-PNG dark achromatic 8-connected outline discovery; row/column source order labels only after discovery; center is source-inferred inert lattice point, never an observed center box'};
}
export function discoverPopup(image) {
  const candidates=components(image,gray).filter(b=>b.width>=95&&b.width<=180&&b.height>=15&&b.height<=40&&b.pixels>=1000&&b.coverage>=0.70);
  assert.equal(candidates.length,1,'One independently measured substantial source-permitted51..64-gray popup fill, text holes permitted; no thin/surrogate component');
  return {...candidates[0],visible_fill_bounds_only:true,rgba_predicate:'Opaque achromatic51..64;75%-black over two preceding alpha0.1 shadow_sm layers on white; not exact-opacity/shadow parity'};
}
export function discoverGeometry(image){return {black_fills:components(image,black).filter(b=>b.pixels>=1000&&b.coverage>=0.70),popup_fills:components(image,gray).filter(b=>b.pixels>=1000&&b.coverage>=0.70)};}
export function inspectIdle(image) {
  const geometry=discoverButtons(image);assert.equal(discoverGeometry(image).black_fills.length,0,'No hover fill at idle');
  assert.equal(discoverGeometry(image).popup_fills.length,0,'No popover at idle/center');
  for(const [name,b] of Object.entries(geometry.buttons)) {
    close(b.height,65,`${name} source button height`);close(b.width,image.width===480&&[0,3,6].includes(b.index)?104:120,`${name} visible source width`);
    const column=b.index%3,sourceLeft=(image.width-512)/2+column*((512-48)/3+24);
    close(b.left,Math.max(0,sourceLeft),`${name} visible source grid left`);
  }
  const b=geometry.buttons;
  close(b.TopCenter.left-b.TopLeft.left,178.6666667-(image.width===480?16:0),'Visible first-column spacing');
  close(b.TopRight.left-b.TopCenter.left,178.6666667,'Full right-column spacing');
  close(b.BottomLeft.top-b.LeftCenter.top,b.LeftCenter.top-b.TopLeft.top,'Equal measured grid row spacing');
  return geometry;
}
export function sourceButtonBounds(wide,narrow,anchor) {
  const original=wide.buttons[anchor];if(!narrow)return {...original};
  const shifts=ANCHORS.filter(a=>wide.buttons[a].index%3!==0).map(a=>({x:narrow.buttons[a].left-wide.buttons[a].left,y:narrow.buttons[a].top-wide.buttons[a].top}));
  for(const delta of shifts){close(delta.x,-135,'Measured full-column recentering delta',1);close(delta.y,0,'Width-only resize preserves measured row y',1);}
  const dx=shifts.reduce((n,d)=>n+d.x,0)/shifts.length,dy=shifts.reduce((n,d)=>n+d.y,0)/shifts.length;
  const predicted={left:original.left+dx,right:original.right+dx,top:original.top+dy,bottom:original.bottom+dy,width:original.width,height:original.height};
  const visible=narrow.buttons[anchor];for(const edge of ['left','right','top','bottom'])close(visible[edge],edge==='left'?Math.max(0,predicted[edge]):predicted[edge],`${anchor} clipped/translated visible ${edge}`);
  return {...predicted,derivation:'Unclipped hypothesis from original750 measured button and independently measured fully visible-column translation; not claimed as directly observed clipped layout origin'};
}
export function sourcePopupExpectation(button,popup,anchor,width) {
  const refs={TopLeft:[0,65,0,0],TopCenter:[60,65,.5,0],TopRight:[120,65,1,0],LeftCenter:[120,32.5,0,.5],RightCenter:[0,32.5,1,.5],BottomLeft:[0,0,0,1],BottomCenter:[60,0,.5,1],BottomRight:[120,0,1,1]};
  assert(refs[anchor]);const [x,y,ax,ay]=refs[anchor],desired={left:button.left+x-ax*popup.width,top:button.top+y-ay*popup.height};
  const snapped={left:Math.max(0,Math.min(width-popup.width,desired.left)),top:Math.max(0,Math.min(600-popup.height,desired.top))};
  return {desired,snapped,anchor_reference:{x:button.left+x,y:button.top+y},derivation:'Source Local block static-origin-after65 hypothesis plus resolved_position, anchor corner subtraction, viewport clamp; independently measured popup size'};
}
export function inspectHover(image,idle,wide,anchor,widePopup=null) {
  const geometry=discoverGeometry(image);assert.equal(geometry.black_fills.length,1,'One hovered opaque black source button fill');
  const fill=geometry.black_fills[0],visible=idle.buttons[anchor];
  for(const edge of ['left','right','top','bottom'])close(fill[edge],visible[edge],`${anchor} hovered button ${edge}`);
  assert(fill.coverage>=.85,'Substantial solid hover fill');
  const popup=discoverPopup(image);
  if(widePopup){close(popup.width,widePopup.width,`${anchor} full popup width survives resize`,1);close(popup.height,widePopup.height,`${anchor} popup height survives resize`,1);}
  const button=sourceButtonBounds(wide,image.width===480?idle:null,anchor),expected=sourcePopupExpectation(button,widePopup||popup,anchor,image.width);
  close(popup.left,expected.snapped.left,`${anchor} Local/snapped popup left`);close(popup.top,expected.snapped.top,`${anchor} Local/snapped popup top`);
  assert(popup.left>=0&&popup.top>=0&&popup.right<=image.width&&popup.bottom<=600,'Measured popup fill stays inside actual viewport');
  return {hover_fill:fill,popup,button_hypothesis:button,source_expectation:expected,snap_x_observed:expected.desired.left< -2&&popup.left===0&&!!widePopup};
}
export function assertViewport(observation,width) {
  assert.deepEqual(observation,{inner:{width,height:600},dpr:1,canvas:{bounds:{x:0,y:0,width,height:600},backing:{width,height:600}}},'Actual full browser viewport and canvas backing');
}
export function assertResizeDelivery(events,action) {
  assert(events.length>=1&&events.length<=4);for(const e of events){assert.equal(e.type,'resize');assert.equal(e.trusted,true);assert.equal(e.target,'WINDOW');assert.equal(e.width,action.width);assert.equal(e.height,600);assert.equal(e.dpr,1);assert(Number.isFinite(e.time)&&e.time>=0);}
}
export function pointerTarget(geometry,target) {
  if(target==='safe')return geometry.safe;if(target==='Center')return geometry.center;
  const b=geometry.buttons[target];assert(b);return {x:(b.left+b.right)/2,y:(b.top+b.bottom)/2};
}
export function assertPointerDelivery(events,target) {
  assert(events.length>=2&&events.length<=8,'Actual pointer/mouse event pair');
  assert(events.some(e=>e.type==='pointermove'));assert(events.some(e=>e.type==='mousemove'));
  for(const e of events){assert(['pointermove','mousemove'].includes(e.type));assert.equal(e.trusted,true);assert.equal(e.target,'CANVAS');close(e.x,target.x,'Trusted pointer x',1);close(e.y,target.y,'Trusted pointer y',1);assert.equal(e.buttons,0);assert.equal(e.button,e.type==='pointermove'?-1:0);assert(Number.isFinite(e.time)&&e.time>=0);if(e.type==='pointermove')assert.equal(e.pointerType,'mouse');}
}
export function validateOperations(report,images) {
  const profile=makeProfile();assert.deepEqual(Object.keys(report.captures),Object.keys(profile.captures));assert.equal(report.operations.length,profile.operations.length);
  assert.equal(report.operation_start,report.startup_events.length);assertViewport(report.initial_viewport,750);
  const geometry={wide:inspectIdle(images.initial),narrow:inspectIdle(images.narrowIdle)},delivered=[];
  for(const [i,expected] of profile.operations.entries()) {
    const actual=report.operations[i],state=VIEWPORT_SEQUENCE[i+1];assert.equal(actual.name,expected.name);assert.deepEqual(actual.action,expected.action);
    assert.equal(actual.input_acknowledged,true);assert.equal(actual.status,'delivered');assert.equal(actual.post_delivery_animation_frames,2);
    assert.deepEqual(actual.before,i?report.operations[i-1].after:report.initial_viewport);assertViewport(actual.after,state.width);
    if(expected.action.kind==='viewport_resize'){assert.equal(actual.input_method,'Playwright.page.setViewportSize');assertResizeDelivery(actual.events,expected.action);assert.equal(actual.target,undefined);}
    else {assert.equal(actual.input_method,'Playwright.page.mouse.move');const target=pointerTarget(geometry[state.phase],expected.action.target);assert.deepEqual(actual.target,target,'Pointer target independently recomputed from retained original idle PNG');assertPointerDelivery(actual.events,target);}
    assert.equal(actual.document_id,report.document_id);delivered.push(...actual.events);
  }
  assert.match(report.document_id||'',/^[0-9a-f-]{36}$/);assert.equal(report.navigation_count,1);assert.deepEqual(report.events,[...report.startup_events,...delivered],'Complete chronological transport stream');
  for(let i=1;i<report.events.length;i++)assert(report.events[i].time>=report.events[i-1].time,'Nondecreasing browser event timestamps');
  for(const s of VIEWPORT_SEQUENCE)assertViewport(report.captures[s.name].viewport,s.width);
  return {pointer_moves:report.operations.filter(o=>o.action.kind==='pointer_move').length,viewport_resizes:2,one_document:true,targets:'Original-PNG visible button interiors and observed blank safe patch; inferred center lattice interior'};
}
export function validateProfile(images) {
  assert.deepEqual(Object.keys(images),VIEWPORT_SEQUENCE.map(s=>s.name));const wide=inspectIdle(images.initial),narrow=inspectIdle(images.narrowIdle),observations={},snaps=[];
  for(const state of VIEWPORT_SEQUENCE) {
    const image=images[state.name];assert.equal(image.width,state.width);const idle=state.phase==='wide'?wide:narrow;
    if(state.hover) {
      const ref=state.phase==='narrow'?observations['wide'+state.hover].popup:null;
      const o=inspectHover(image,idle,wide,state.hover,ref);observations[state.name]=o;if(o.snap_x_observed)snaps.push(state.name);
    } else {
      observations[state.name]={idle:inspectIdle(image)};
      const baseline=state.phase==='wide'?images.initial:images.narrowIdle;
      assert.equal(sha256(image.data),sha256(baseline.data),`${state.name}: complete original RGBA idle/inert/exit restoration`);
    }
  }
  assert.deepEqual(observations.repeatTopLeft,observations.wideTopLeft,'Repeat hover restores independently observed popup/button geometry');
  assert.deepEqual(snaps,['narrowTopLeft','narrowBottomLeft'],'Both left-column corner popovers preserve original full size at measured x0 after source-derived negative unclipped origin');
  return {observations,snapping:{observed:snaps,claim:'Only the two measured left-edge snaps; clipped button origin is source-derived from measured full columns'},hovered_anchors:ANCHORS,center:'Original RGBA unchanged at inferred source center and after exit',restoration:'Complete original RGBA identical after each hover exit, inert center and750 viewport restoration',full_image_cross_runtime_parity:'not_claimed'};
}
export function profileNegativeControls(images,report) {
  validateProfile(images);validateOperations(report,images);const controls=[],check=(name,f)=>{assert.throws(f,name);controls.push({name,rejected:true,kind:'corrupted_evidence_sensitivity_not_executed_mutant'});};
  const changed=(name,mutate)=>{const image={...images[name],data:images[name].data.slice()};mutate(image);return {...images,[name]:image};};
  for(const [name,state,replacement] of [['missing_popup_and_hover','wideTopLeft','initial'],['wrong_anchor_popup','wideTopCenter','wideTopRight'],['stale_hover_after_exit','wideTopLeftExit','wideTopLeft'],['active_inert_center','wideCenter','wideLeftCenter'],['failed_viewport_restore','restoredIdle','narrowIdle']])check(name,()=>validateProfile({...images,[state]:images[replacement]}));
  for(const [name,mutate] of [['missing_popup',image=>{for(let p=0;p<image.width*image.height;p++)if(gray(image.data,p*4))image.data.set([255,255,255,255],p*4);}],['lost_hover_fill',image=>{for(let p=0;p<image.width*image.height;p++)if(black(image.data,p*4))image.data.set([255,255,255,255],p*4);} ]])check(name,()=>validateProfile(changed('wideTopLeft',mutate)));
  const displaced=changed('wideTopLeft',image=>{const b=discoverPopup(image),copy=image.data.slice();for(let y=b.top;y<b.bottom;y++)for(let x=b.left;x<b.right+8;x++)image.data.set([255,255,255,255],4*(y*image.width+x));for(let y=b.top;y<b.bottom;y++)for(let x=b.left;x<b.right;x++)image.data.set(copy.subarray(4*(y*image.width+x),4*(y*image.width+x)+4),4*(y*image.width+x+8));});
  check('wrong_local_popup_offset',()=>validateProfile(displaced));
  const unsnapped=changed('narrowTopLeft',image=>{const b=discoverPopup(image),copy=image.data.slice();for(let y=b.top;y<b.bottom;y++)for(let x=b.left;x<b.right;x++)image.data.set([255,255,255,255],4*(y*image.width+x));for(let y=b.top;y<b.bottom;y++)for(let x=b.left+16;x<b.right;x++)image.data.set(copy.subarray(4*(y*image.width+x),4*(y*image.width+x)+4),4*(y*image.width+x-16));});
  check('clipped_unsnapped_popup_same_viewport',()=>validateProfile(unsnapped));
  check('restoration_pixel_changed',()=>validateProfile(changed('wideTopLeftExit',image=>{image.data[0]=254;})));
  for(const [name,mutate] of [['untrusted_pointer',r=>{r.operations[0].events[0].trusted=false;}],['missing_pointer',r=>{r.operations[0].events=[];}],['wrong_pointer_target',r=>{r.operations[0].target.x+=10;}],['input_outside_button',r=>{r.operations[0].events.forEach(e=>e.x+=100);}],['missing_resize',r=>{r.operations.find(o=>o.action.kind==='viewport_resize').events=[];}],['wrong_backing',r=>{r.captures.narrowIdle.viewport.canvas.backing.width++;}],['reloaded_document',r=>{r.navigation_count++;}],['different_document',r=>{r.operations[0].document_id='0'.repeat(36);}]] ) {const r=structuredClone(report);mutate(r);check(name,()=>validateOperations(r,images));}
  return controls;
}
