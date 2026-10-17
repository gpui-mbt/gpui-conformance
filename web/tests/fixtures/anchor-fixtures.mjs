// SYNTHETIC UNIT INPUTS ONLY. No compiler, browser, PNG capture or Rust evidence.
import {readFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {EMBEDDED_FONTS,ENGINE,PROFILE_REVISION,SOURCE_CONSTRAINTS,ANCHOR,sha256,VIEWPORT_SEQUENCE,ANCHORS,sourcePopupExpectation,pointerTarget,discoverButtons,makeProfile,assertProvenance,provenanceNegativeControls} from '../anchor-comparator.mjs';
import {SUITE_INPUTS,GRAPHICS_ARGS,HTML_ENTRYPOINTS,captureBinding,inputEvidence} from '../anchor-runtime-evidence.mjs';
import {RUST_WORKER,deriveRustWorkerBytes,evidenceFilename} from '../anchor-worker-evidence.mjs';
const indices=[0,1,2,3,5,6,7,8];
export function frame(width=750,hover=null) {
  const image={width,height:600,data:new Uint8Array(width*600*4)};image.data.fill(255);
  const rect=(b,color,outline=false)=>{for(let y=b.top;y<b.bottom;y++)for(let x=b.left;x<b.right;x++)if(x>=0&&x<width&&y>=0&&y<600&&(!outline||y===b.top||y===b.bottom-1||x===b.left||x===b.right-1))image.data.set(color,4*(y*width+x));};
  const boxes={};for(const [i,anchor] of ANCHORS.entries()) {
    const index=indices[i],left=Math.round((width-512)/2+(index%3)*178.6666666667),top=100+Math.floor(index/3)*170;
    boxes[anchor]={left,right:left+120,top,bottom:top+65,width:120,height:65};rect(boxes[anchor],[0,0,0,255],anchor!==hover);
  }
  if(hover){const expected=sourcePopupExpectation(boxes[hover],{width:100,height:24},hover,width),left=Math.round(expected.snapped.left),top=Math.round(expected.snapped.top);rect({left,top,right:left+100,bottom:top+24},[64,64,64,255]);}
  return image;
}
export function viewport(width) {return {inner:{width,height:600},dpr:1,canvas:{bounds:{x:0,y:0,width,height:600},backing:{width,height:600}}};}
export function pixels() {
  const profile=makeProfile(),images={},stableImages={},cache={};
  for(const state of VIEWPORT_SEQUENCE){const key=state.width+':'+state.hover;cache[key]??=frame(state.width,state.hover);images[state.name]=cache[key];stableImages[state.name]=cache[key];}
  return {profile,images,stableImages};
}
export function provenance() {
  const catalog=JSON.parse(readFileSync(new URL('./anchor-rust-only-catalog-a20e5888.json',import.meta.url)));
  const record=JSON.parse(readFileSync(new URL('../../oracles/anchor.json',import.meta.url)));
  const fonts=Object.fromEntries(Object.entries(EMBEDDED_FONTS).map(([path,sha256])=>[path,{file:'embedded-font-inputs/'+path.split('/').at(-1),sha256}]));
  const files=Object.fromEntries(['anchor.js','anchor_bg.wasm','host.mjs','packaging-Cargo.toml'].map(path=>[path,'a'.repeat(64)]));
  Object.assign(files,{'unchanged-source/anchor.rs':ANCHOR.sourceSha256,'index.html':HTML_ENTRYPOINTS.rust.sha256,'Cargo.lock':RUST_WORKER.lock_sha256});
  for(const font of Object.values(fonts))files[font.file]=font.sha256;
  const build={upstream:catalog.upstream,moonbit:ENGINE,lab_revision:'1'.repeat(40),lab_tree:'2'.repeat(40),lab_tracked_dirty:false,
    site_kind:'anchor_rust_oracle_only',moonbit_execution:'not_run',comparison_status:'not_run',
    implemented:[],rust_bundled:true,rust_implemented:['anchor'],rust_oracle_only:[record],rust_subset_sources:[],
    moonbit_host_files_sha256:{'load-timing.mjs':'b'.repeat(64)},
    rust:{source_revision:ANCHOR.revision,source_tree:ANCHOR.tree,source_modified:false,oracle_only:true,implemented_subset:null,
      build_completed_at_utc:'2026-10-16T20:00:00.000Z',toolchain:'rustc 1.94.0-nightly (synthetic test)',bindings:'wasm-bindgen 0.2.129',
      packaging:{upstream_files_modified:false,additional_bins:[{name:'anchor',source:ANCHOR.source}],manifest_sha256:files['packaging-Cargo.toml']},
      embedded_fonts:fonts,files,command:['cargo','+nightly-2026-10-14','build','--locked','--release','--bin','anchor']}};
  return {build,catalog};
}
export function fixture() {
  const {images,stableImages,profile}=pixels(),{build,catalog}=provenance();
  const report={status:'rust_profile_captured',runtime:'rust',candidate:'not_implemented',comparison:'not_run',conformance:'not_claimed',
    mode:'source_only_profile_capture',profile_revision:PROFILE_REVISION,capture_session:randomUUID(),build,catalog,
    profile:{widths:[750,480],height:600,dpr:1},source_constraints:SOURCE_CONSTRAINTS,
    document_id:randomUUID(),navigation_count:1,initial_viewport:viewport(750),transport:{canvas_tab_index:-1},
    captures:{},operations:[],events:[],startup_events:[],operation_start:0,
    errors:[],console:[],decoder:{name:'Pillow',version:'12.0.0',sha256:'c'.repeat(64)},
    environment:{browser:'142.0.0.0',node:'v22.0.0',playwright:'1.56.1',platform:'linux',arch:'x64',graphics_requested:GRAPHICS_ARGS},
    graphics_actual:{gpu:{auxAttributes:{glRenderer:'synthetic SwiftShader'}}},graphics_evidence:{file:'anchor-rust-graphics.json',sha256:'c'.repeat(64)},
    build_evidence:{file:'anchor-rust-build-manifest.json',sha256:'c'.repeat(64)},catalog_evidence:{file:'anchor-rust-catalog.json',sha256:'c'.repeat(64)},
    requests:[],served_requests:[],runtime_responses:[],suite_inputs:[]};
  const geometry={wide:discoverButtons(images.initial),narrow:discoverButtons(images.narrowIdle)};let time=1;
  for(const [index,operation] of profile.operations.entries()) {
    const a=operation.action,state=VIEWPORT_SEQUENCE[index+1],target=a.kind==='pointer_move'?pointerTarget(geometry[state.phase],a.target):null;
    const events=a.kind==='viewport_resize'?[{type:'resize',trusted:true,target:'WINDOW',time:time++,width:a.width,height:600,dpr:1}]:['pointermove','mousemove'].map(type=>({type,trusted:true,target:'CANVAS',time:time++,x:target.x,y:target.y,button:type==='pointermove'?-1:0,buttons:0,...(type==='pointermove'?{pointerType:'mouse'}:{})}));
    report.operations.push({...operation,input_method:a.kind==='viewport_resize'?'Playwright.page.setViewportSize':'Playwright.page.mouse.move',input_acknowledged:true,status:'delivered',
      post_delivery_animation_frames:2,events,before:viewport(VIEWPORT_SEQUENCE[index].width),after:viewport(state.width),document_id:report.document_id,...(target?{target}:{})});
    report.events.push(...events);
  }
  for(const [name,state] of Object.entries(profile.captures)) {
    const binding=captureBinding(report,name,state.after_operation-1),digest=sha256(images[name].data),attempts=[1,2].map(n=>({
      file:`anchor-rust-${name}-sample-${n}-dpr1.png`,binding,request_ordinal:n,method:'Playwright.page.screenshot',rgba_sha256:digest,width:state.width,height:600}));
    report.captures[name]={after_operation:state.after_operation,binding,attempts,viewport:viewport(state.width),stable:true,file:attempts[1].file,stability_file:attempts[0].file,rgba_sha256:digest,stability_rgba_sha256:digest};
  }
  for(const path of SUITE_INPUTS) {
    const bytes=readFileSync(new URL('../../../'+path,import.meta.url));report.suite_inputs.push({path,file:evidenceFilename('rust','suite',path),sha256:sha256(bytes),bytes:bytes.length});
  }
  const assets={},responses={},origin='http://127.0.0.1:12345',loaderURL=origin+'/gpui-conformance/rust/anchor.js';
  const paths=['rust/index.html','rust/host.mjs','load-timing.mjs','rust/anchor.js','rust/anchor_bg.wasm'];
  const template=readFileSync(new URL('../../../'+RUST_WORKER.template_path,import.meta.url));
  for(const path of paths) {
    const bytes=path.endsWith('index.html')?readFileSync(new URL('../../rust/index.html',import.meta.url)):
      path.endsWith('.wasm')?Buffer.concat([Buffer.from('synthetic test wasm'),template]):Buffer.from('synthetic test '+path);
    if(path==='load-timing.mjs')build.moonbit_host_files_sha256[path]=sha256(bytes);else build.rust.files[path.slice(5)]=sha256(bytes);
    const url=origin+'/gpui-conformance/'+(path==='rust/index.html'?'rust/?example=anchor':path);
    const id=report.requests.length+1,type=path.endsWith('index.html')?'document':path.endsWith('.wasm')?'fetch':'script';
    assets[path]=bytes;responses[id]=bytes;
    const response={path,url,status:200,response_id:id,resource_type:type,file:evidenceFilename('rust','asset',url,id),sha256:sha256(bytes),bytes:bytes.length,binding:{runtime:'rust',session:report.capture_session}};
    report.runtime_responses.push(response);report.requests.push({url,status:200,response_id:id,resource_type:type});
    report.served_requests.push({url:new URL(url).pathname+new URL(url).search,status:200,sha256:sha256(bytes)});
  }
  const workerURL='blob:'+origin+'/'+randomUUID(),worker=deriveRustWorkerBytes(loaderURL),id=6;
  assets[workerURL]=worker;responses[id]=worker;
  report.runtime_responses.push({path:workerURL,url:workerURL,status:200,response_id:id,resource_type:'script',file:evidenceFilename('rust','asset',workerURL,id),sha256:sha256(worker),bytes:worker.length,binding:{runtime:'rust',session:report.capture_session}});
  report.requests.push({url:workerURL,status:200,response_id:id,resource_type:'script'});
  const inputBytes=Buffer.from(JSON.stringify(inputEvidence(report)));
  report.input_evidence={file:'anchor-rust-trusted-input.json',sha256:sha256(inputBytes)};
  report.source=assertProvenance(build,catalog);report.provenance_negative_controls=provenanceNegativeControls(build,catalog);
  return {report,retained:{images,stableImages,assets,responses,inputBytes},profile};
}
