// Source-derived checks only. No candidate and no fitted pixel tolerances.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
export const sha256=bytes=>createHash('sha256').update(bytes).digest('hex');
export const ORACLE=JSON.parse(readFileSync(new URL('../oracles/gradient.json',import.meta.url)));
export const SOURCES=JSON.parse(readFileSync(new URL('../oracles/gradient-sources.json',import.meta.url)));
export const CATALOG_BYTES=readFileSync(new URL('./fixtures/gradient-rust-only-catalog.json',import.meta.url));
assert.equal(sha256(CATALOG_BYTES),'fcd36a52996bba647a40c8422b4481840a94174602ea1f327d71ad6e474b4b73');
export const PROFILE_REVISION='unchanged_gradient_wide_tall_restore_v1';
export const VIEWPORT_SEQUENCE=Object.freeze([
 {name:'wideSrgb',width:960,height:600,space:'sRGB',action:null},
 {name:'wideOklab',width:960,height:600,space:'Oklab',action:'click'},
 {name:'wideRestored',width:960,height:600,space:'sRGB',action:'click'},
 {name:'tallSrgb',width:600,height:960,space:'sRGB',action:'resize'},
 {name:'tallOklab',width:600,height:960,space:'Oklab',action:'click'},
 {name:'tallRestored',width:600,height:960,space:'sRGB',action:'click'},
 {name:'wideAgain',width:960,height:600,space:'sRGB',action:'resize'},
].map((s,i)=>Object.freeze({...s,dpr:1,after_operation:i})));
export const GRAPHICS_ARGS=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'];
export function assertProvenance(build,catalog) {
 assert.deepEqual(catalog,JSON.parse(CATALOG_BYTES));assert.deepEqual(build.upstream,catalog.upstream);assert.deepEqual(build.moonbit,catalog.moonbit);
 assert.equal(build.site_kind,'gradient_rust_oracle_only');assert.equal(build.lab_tracked_dirty,false);
 assert.match(build.lab_revision||'',/^[0-9a-f]{40}$/);assert.match(build.lab_tree||'',/^[0-9a-f]{40}$/);
 assert.equal(build.rust_bundled,true);assert.deepEqual(build.implemented,[]);assert.equal(build.moonbit_execution,'not_run');assert.equal(build.comparison_status,'not_run');
 assert.deepEqual(build.rust_implemented,['gradient']);assert.deepEqual(build.rust_oracle_only,[ORACLE]);assert.deepEqual(build.rust_subset_sources,[]);
 const rust=build.rust;assert.equal(rust.source_revision,ORACLE.upstream_revision);assert.equal(rust.source_tree,ORACLE.upstream_tree);
 assert.equal(rust.source_modified,false);assert.equal(rust.oracle_only,true);assert.equal(rust.implemented_subset,null);
 assert.equal(rust.packaging.upstream_files_modified,false);assert.deepEqual(rust.packaging.additional_bins,[{name:'gradient',source:ORACLE.source}]);
 assert.equal(rust.files['unchanged-source/gradient.rs'],ORACLE.source_sha256);
 assert.equal(rust.files['Cargo.lock'],'d60bd2d8e87639d33f67b740796a06078c2c2e3df9593dcbd699c4abc37919da');
 assert.equal(rust.files['index.html'],'8f6806a2ae5f935a8212171af3890fb1460c5ab30a357032bf541222b2bd6669');
 assert.equal(rust.files['host.mjs'],sha256(readFileSync(new URL('../gradient/host.mjs',import.meta.url))));
 assert.equal(rust.files['packaging-Cargo.toml'],rust.packaging.manifest_sha256);
 for(const entry of SOURCES.sources)assert.equal(rust.files['support-source/'+entry.path],entry.sha256);
 assert.equal(Object.keys(rust.embedded_fonts).length,8);
 for(const [path,font] of Object.entries(rust.embedded_fonts)) {
  assert.equal(font.sha256,SOURCES.fonts[path]);assert.equal(rust.files[font.file],font.sha256);
 }
 for(const name of ['gradient.js','gradient_bg.wasm'])assert.match(rust.files[name]||'',/^[0-9a-f]{64}$/);
 assert(rust.command.includes('+nightly-2026-10-14')&&rust.command.includes('--locked'));
 assert.deepEqual(rust.command.filter((x,i,a)=>a[i-1]==='--bin'),['gradient']);
 assert.match(rust.bindings,/^wasm-bindgen 0\.2\.129$/);assert.match(rust.toolchain,/^rustc 1\./);assert(Number.isFinite(Date.parse(rust.build_completed_at_utc)));
 return ORACLE;
}
export function assertCurrentBuild(report,checkout) {
 assert.equal(checkout.trackedDirty,false);assert.equal(report.build.lab_revision,checkout.revision);assert.equal(report.build.lab_tree,checkout.tree);
 assert.deepEqual(checkout.catalogBytes,CATALOG_BYTES);assert.equal(report.catalog_evidence.sha256,sha256(CATALOG_BYTES));return {revision:checkout.revision,tree:checkout.tree};
}
export function decodePng(bytes) {
 assert(Buffer.isBuffer(bytes)&&bytes.length>0&&bytes.length<=8*1024*1024);
 const r=spawnSync('python3',[fileURLToPath(new URL('../scripts/decode_gradient_png.py',import.meta.url))],{input:bytes,timeout:10000,maxBuffer:960*600*4+4096});
 if(r.error)throw r.error;assert.equal(r.status,0,`Strict original PNG decoder: ${r.stderr}`);
 const width=r.stdout.readUInt32BE(0),height=r.stdout.readUInt32BE(4);assert([[960,600],[600,960]].some(([w,h])=>w===width&&h===height));assert.equal(r.stdout.length,8+width*height*4);
 return {width,height,data:new Uint8Array(r.stdout.subarray(8))};
}
export function assertViewport(v,state) {
 assert.deepEqual(v.inner,{width:state.width,height:state.height});assert.equal(v.dpr,1);
 assert.deepEqual(v.canvas.backing,{width:state.width,height:state.height});assert.deepEqual(v.canvas.bounds,{x:0,y:0,width:state.width,height:state.height});
}
export const pixel=(image,x,y)=>Array.from(image.data.slice((y*image.width+x)*4,(y*image.width+x)*4+4));
// Discover all colored components without source coordinates or reference pixels.
export function components(image,predicate) {
 const {width:w,height:h,data}=image,n=w*h,seen=new Uint8Array(n),queue=new Int32Array(n),found=[];
 for(let p=0;p<n;p++)if(!seen[p]&&predicate(data,p*4)) {
  let a=0,b=1,left=w,right=0,top=h,bottom=0;queue[0]=p;seen[p]=1;
  while(a<b){const q=queue[a++],x=q%w,y=Math.floor(q/w);left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);
   for(const k of [x>0?q-1:-1,x<w-1?q+1:-1,y>0?q-w:-1,y<h-1?q+w:-1])if(k>=0&&!seen[k]&&predicate(data,k*4)){seen[k]=1;queue[b++]=k;}
  }
  found.push({x:left,y:top,width:right-left+1,height:bottom-top+1,area:b});
 }
 return found.sort((a,b)=>a.y-b.y||a.x-b.x);
}
export function discoverGeometry(image) {
 // 32 pixels removes isolated color-font raster noise; structural minimum only.
 const colored=components(image,(d,i)=>Math.max(d[i],d[i+1],d[i+2])-Math.min(d[i],d[i+1],d[i+2])>0).filter(c=>c.area>=32);
 // Method button is the large solid-black component in the header; text islands
 // are too small. Target is observed from its original PNG, never a DOM locator.
 const buttons=components(image,(d,i)=>d[i]===0&&d[i+1]===0&&d[i+2]===0).filter(c=>c.y<80&&c.width>=35&&c.height>=16&&c.area>=300);
 assert.equal(buttons.length,1,'Unique source method button');
 return {colored,button:buttons[0]};
}
export function sourceStructure(image) {
 const g=discoverGeometry(image);assert.equal(g.colored.length,15,'2 solids, 12 gradient quads, 1 filled polygon');
 const ordered=[];let remainder=[...g.colored];
 for(const count of [2,4,4,1,1,2,1]) {
  const top=Math.min(...remainder.map(c=>c.y));const row=remainder.filter(c=>Math.abs(c.y-top)<=1).sort((a,b)=>a.x-b.x);
  assert.equal(row.length,count,'Source-authored row cardinality');ordered.push(...row);remainder=remainder.filter(c=>!row.includes(c));
 }
 assert.equal(remainder.length,0);return {...g,colored:ordered};
}
export function buttonTarget(image){const b=discoverGeometry(image).button;return {x:Math.floor(b.x+b.width/2),y:Math.floor(b.y+b.height/2)};}
export function validateOperations(report) {
 assert.equal(report.navigation_count,1);assert.match(report.document_id||'',/^[0-9a-f-]{36}$/);
 assert.equal(report.operations.length,6);
 for(const [i,op] of report.operations.entries()) {
  const state=VIEWPORT_SEQUENCE[i+1];assert.equal(op.name,state.name);assert.equal(op.action,state.action);assert.equal(op.status,'delivered');assert.equal(op.document_id,report.document_id);assert.equal(op.input_acknowledged,true);assertViewport(op.after,state);
  assert(Number.isSafeInteger(op.event_start)&&Number.isSafeInteger(op.event_end)&&op.event_end>op.event_start);
  assert.deepEqual(op.events,report.events.slice(op.event_start,op.event_end),'Retained original event slice');
  if(state.action==='resize')assert(op.events.some(e=>e.type==='resize'&&e.trusted&&e.width===state.width&&e.height===state.height&&e.dpr===1));
  else {
   assert.equal(op.input_method,'Playwright.page.mouse.click');
   for(const type of ['pointerdown','pointerup','click'])assert(op.events.some(e=>e.type===type&&e.trusted&&e.target==='CANVAS'&&e.button===0&&e.x===op.target.x&&e.y===op.target.y),type+' original delivery');
  }
 }
}
// Direct double-precision transcription of pinned WGSL, used to expose residuals.
// It does not decide f32 NaN behavior, antialiasing, transfer or native parity.
export function gradientT(angle,stops,bounds,position) {
 const r=(angle%360-90)*Math.PI/180;let x=Math.cos(r),y=Math.sin(r);const [w,h]=bounds.size;
 if(w>h)y*=h/w;else x*=w/h;
 let t=((position[0]-bounds.origin[0]-w/2)*x+(position[1]-bounds.origin[1]-h/2)*y)/Math.hypot(x,y);
 t=Math.abs(x)>Math.abs(y)?(t+w/2)/w:(t+h/2)/h;
 if(stops[0]===stops[1])return {raw:t,normalized:null,reason:'equal_stops_actual_GPU_NaN_or_infinity_semantics_pending'};
 return {raw:t,normalized:Math.max(0,Math.min(1,(t-stops[0])/(stops[1]-stops[0])))};
}
const linearToSrgb=a=>a<0.0031308?12.92*a:1.055*Math.pow(a,1/2.4)-0.055;
const srgbToLinear=a=>a<0.04045?a/12.92:Math.pow((a+0.055)/1.055,2.4);
const mat=(m,v)=>m.map(r=>r.reduce((sum,x,i)=>sum+x*v[i],0));
const lab=c=>mat([[.2104542553,.793617785,-.0040720468],[1.9779984951,-2.428592205,.4505937099],[.0259040371,.7827717662,-.808675766]],mat([[.4122214708,.5363325363,.0514459929],[.2119034982,.6806995451,.1073969566],[.0883024619,.2817188376,.6299787005]],c).map(x=>Math.pow(x,1/3)));
const unlab=c=>mat([[4.0767416621,-3.3077115913,.2309699292],[-1.2684380046,2.6097574011,-.3413193965],[-.0041960863,-.7034186147,1.707614701]],mat([[1,.3963377774,.2158037573],[1,-.1055613458,-.0638541728],[1,-.0894841775,-1.291485548]],c).map(x=>x*x*x));
export function gradientColor(a,b,t,space) {
 assert(t!==null&&Number.isFinite(t));const ca=space==='Oklab'?lab(a):a.slice(0,3).map(linearToSrgb),cb=space==='Oklab'?lab(b):b.slice(0,3).map(linearToSrgb);
 const mixed=ca.map((v,i)=>v+(cb[i]-v)*t);return [...(space==='Oklab'?unlab(mixed):mixed.map(srgbToLinear)),a[3]+(b[3]-a[3])*t];
}
const R=[1,0,0,1],B=[0,0,1,1],G=[0,.5,0,1],Y=[1,1,0,1],W=[1,1,1,1];
export const SOURCE_GRADIENTS=[[45,R,B,0,1],[135,R,G,0,1],[225,G,B,0,1],[315,G,Y,0,1],[0,R,W,0,1],[90,B,W,0,1],[180,G,W,0,1],[360,Y,W,0,1],[0,G,Y,.05,.95],[90,B,R,.05,.95],[90,B,R,.5,.5],[180,G,B,0,.5],[180,R,B,0,1]];
export function colorObservations(image,space,geometry) {
 return geometry.colored.slice(2).map((box,i)=>{
  const [angle,a,b,s0,s1]=SOURCE_GRADIENTS[i];
  const samples=[];
  for(const f of [.25,.5,.75]) {
   const x=Math.floor(box.x+box.width*f),y=Math.floor(box.y+box.height*.5);
   const t=gradientT(angle,[s0,s1],{origin:[box.x,box.y],size:[box.width,box.height]},[x+.5,y+.5]);
   const predicted=t.normalized===null?null:gradientColor(a,b,t.normalized,space);
   samples.push({position:[x,y],actual:pixel(image,x,y),t,predicted_linear_rgba:predicted,
    predicted_unorm8:predicted?.map(v=>Math.round(Math.max(0,Math.min(1,v))*255)),status:'observation_only_no_color_tolerance_or_pass'});
  }
  return {index:i,angle,stops:[s0,s1],endpoints:[a,b],measured_colored_bounds:box,
   bounds_qualification:'Visible colored-component bounds; white endpoints/AA may omit edge pixels. Not instrumented layout bounds.',samples};
 });
}
