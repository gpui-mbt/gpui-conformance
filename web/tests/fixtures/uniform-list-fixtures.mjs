// SYNTHETIC UNIT INPUTS ONLY. No compiler, browser, PNG capture or Rust evidence.
import {readFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {EMBEDDED_FONTS,ENGINE,PROFILE_REVISION,SOURCE_CONSTRAINTS,UNIFORM_LIST,sha256,discoverGeometry,makeProfile,assertProvenance,provenanceNegativeControls} from '../uniform-list-comparator.mjs';
import {SUITE_INPUTS,GRAPHICS_ARGS,HTML_ENTRYPOINTS,captureBinding,inputEvidence} from '../uniform-list-runtime-evidence.mjs';
import {RUST_WORKER,deriveRustWorkerBytes,evidenceFilename} from '../uniform-list-worker-evidence.mjs';
export function frame(offset=0,pitch=26) {
  const image={width:300,height:300,data:new Uint8Array(300*300*4)};image.data.fill(255);
  for(let y=0;y<300;y++) {
    const contentY=offset+y,index=Math.floor(contentY/pitch),line=contentY%pitch;
    if(index>=50||line<6||line>=19)continue;
    for(let x=9;x<61;x++)if(x<12||(x>=18&&x<24)||((index+1)&(1<<Math.floor((x-25)/5)))&&x>=25&&x<55) {
      const o=(y*300+x)*4;image.data[o]=image.data[o+1]=image.data[o+2]=0;
    }
  }
  return image;
}
export function pixels(pitch=26) {
  const geometry=discoverGeometry(frame(0,pitch)),profile=makeProfile(geometry),images={},stableImages={};
  for(const [name,state] of Object.entries(profile.captures)) {
    images[name]=frame(state.offset,pitch);stableImages[name]=frame(state.offset,pitch);
  }
  return {geometry,profile,images,stableImages};
}
export function provenance() {
  const catalog=JSON.parse(readFileSync(new URL('./uniform-list-rust-only-catalog-4b4a7047.json',import.meta.url)));
  const record=JSON.parse(readFileSync(new URL('../../oracles/uniform_list.json',import.meta.url)));
  const fonts=Object.fromEntries(Object.entries(EMBEDDED_FONTS).map(([path,sha256])=>[path,{file:'embedded-font-inputs/'+path.split('/').at(-1),sha256}]));
  const files=Object.fromEntries(['uniform_list.js','uniform_list_bg.wasm','host.mjs','packaging-Cargo.toml'].map(path=>[path,'a'.repeat(64)]));
  Object.assign(files,{'unchanged-source/uniform_list.rs':UNIFORM_LIST.sourceSha256,'index.html':HTML_ENTRYPOINTS.rust.sha256,'Cargo.lock':RUST_WORKER.lock_sha256});
  for(const font of Object.values(fonts))files[font.file]=font.sha256;
  const build={upstream:catalog.upstream,moonbit:ENGINE,lab_revision:'1'.repeat(40),lab_tree:'2'.repeat(40),lab_tracked_dirty:false,
    site_kind:'uniform_list_rust_oracle_only',moonbit_execution:'not_run',comparison_status:'not_run',
    implemented:[],rust_bundled:true,rust_implemented:['uniform_list'],rust_oracle_only:[record],rust_subset_sources:[],
    moonbit_host_files_sha256:{'load-timing.mjs':'b'.repeat(64)},
    rust:{source_revision:UNIFORM_LIST.revision,source_tree:UNIFORM_LIST.tree,source_modified:false,oracle_only:true,implemented_subset:null,
      build_completed_at_utc:'2026-10-16T20:00:00.000Z',toolchain:'rustc 1.94.0-nightly (synthetic test)',bindings:'wasm-bindgen 0.2.129',
      packaging:{upstream_files_modified:false,additional_bins:[{name:'uniform_list',source:UNIFORM_LIST.source}],manifest_sha256:files['packaging-Cargo.toml']},
      embedded_fonts:fonts,files,command:['cargo','+nightly-2026-10-14','build','--locked','--release','--bin','uniform_list']}};
  return {build,catalog};
}
export function fixture(pitch=26) {
  const {images,stableImages,geometry,profile}=pixels(pitch),{build,catalog}=provenance();
  const report={status:'rust_profile_captured',runtime:'rust',candidate:'not_implemented',comparison:'not_run',conformance:'not_claimed',
    mode:'source_only_profile_capture',profile_revision:PROFILE_REVISION,capture_session:randomUUID(),build,catalog,
    profile:{width:300,height:300,dpr:1},source_constraints:SOURCE_CONSTRAINTS,
    canvas:{bounds:{x:0,y:0,width:300,height:300},backing:{width:300,height:300}},transport:{canvas_tab_index:-1},
    captures:{},operations:[],events:[],startup_events:[],operation_start:0,
    errors:[],console:[],decoder:{name:'Pillow',version:'12.0.0',sha256:'c'.repeat(64)},
    environment:{browser:'142.0.0.0',node:'v22.0.0',playwright:'1.56.1',platform:'linux',arch:'x64',graphics_requested:GRAPHICS_ARGS},
    graphics_actual:{gpu:{auxAttributes:{glRenderer:'synthetic SwiftShader'}}},graphics_evidence:{file:'uniform-list-rust-graphics.json',sha256:'c'.repeat(64)},
    build_evidence:{file:'uniform-list-rust-build-manifest.json',sha256:'c'.repeat(64)},catalog_evidence:{file:'uniform-list-rust-catalog.json',sha256:'c'.repeat(64)},
    requests:[],served_requests:[],runtime_responses:[],suite_inputs:[]};
  for(const [index,operation] of profile.operations.entries()) {
    const a=operation.action,event={type:'wheel',trusted:true,target:'CANVAS',time:index+1,defaultPrevented:true,x:a.x,y:a.y,
      deltaX:a.deltaX,deltaY:a.deltaY,deltaZ:0,deltaMode:0,shiftKey:false,ctrlKey:false,altKey:false,metaKey:false};
    report.operations.push({...operation,input_method:'CDP.Input.dispatchMouseEvent',input_acknowledged:true,status:'delivered',post_delivery_animation_frames:2,events:[event]});
    report.events.push(event);
  }
  for(const [name,state] of Object.entries(profile.captures)) {
    const binding=captureBinding(report,name,state.after_operation-1),digest=sha256(images[name].data),attempts=[1,2].map(n=>({
      file:`uniform-list-rust-${name}-sample-${n}-dpr1.png`,binding,request_ordinal:n,method:'Playwright.page.screenshot',rgba_sha256:digest,width:300,height:300}));
    report.captures[name]={after_operation:state.after_operation,binding,attempts,stable:true,file:attempts[1].file,stability_file:attempts[0].file,rgba_sha256:digest,stability_rgba_sha256:digest};
  }
  for(const path of SUITE_INPUTS) {
    const bytes=readFileSync(new URL('../../../'+path,import.meta.url));report.suite_inputs.push({path,file:evidenceFilename('rust','suite',path),sha256:sha256(bytes),bytes:bytes.length});
  }
  const assets={},responses={},origin='http://127.0.0.1:12345',loaderURL=origin+'/gpui-conformance/rust/uniform_list.js';
  const paths=['rust/index.html','rust/host.mjs','load-timing.mjs','rust/uniform_list.js','rust/uniform_list_bg.wasm'];
  const template=readFileSync(new URL('../../../'+RUST_WORKER.template_path,import.meta.url));
  for(const path of paths) {
    const bytes=path.endsWith('index.html')?readFileSync(new URL('../../rust/index.html',import.meta.url)):
      path.endsWith('.wasm')?Buffer.concat([Buffer.from('synthetic test wasm'),template]):Buffer.from('synthetic test '+path);
    if(path==='load-timing.mjs')build.moonbit_host_files_sha256[path]=sha256(bytes);else build.rust.files[path.slice(5)]=sha256(bytes);
    const url=origin+'/gpui-conformance/'+(path==='rust/index.html'?'rust/?example=uniform_list':path);
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
  report.input_evidence={file:'uniform-list-rust-trusted-input.json',sha256:sha256(inputBytes)};
  report.source=assertProvenance(build,catalog);report.provenance_negative_controls=provenanceNegativeControls(build,catalog);
  return {report,retained:{images,stableImages,assets,responses,inputBytes},geometry,profile};
}
