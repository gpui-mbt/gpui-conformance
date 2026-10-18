import assert from 'node:assert/strict';
import {readFile,realpath,stat} from 'node:fs/promises';
import {resolve,join,basename,sep} from 'node:path';
import {createHash} from 'node:crypto';
import {TAB_STOP,EMBEDDED_FONTS,STOPS,sha256,decodePng,frameGeometry,sourceGeometry,validateTraversal,validateClicks,
  validateOperations,traversalNegativeControls,makeProfile,assertCurrentTabStopBuild} from './tab-stop-comparator.mjs';

// Historical identity is retained for provenance, never accepted by the current verifier.
export const HISTORICAL_PAIR=Object.freeze({revision:'tab_stop_paired_state_specific_v3_uniform_list_pin',
  candidate:Object.freeze({repository:'gpui-mbt/gpui.mbt',
    revision:'89108ad966c2d37b0cb44909b1aac3ecfa8e3c4a',tree:'dd5612a412d251b468c358a25baa0b0dd592c807'})});
// Retired popover profile is provenance only, never an accepted current alternative.
export const POPOVER_PAIR=Object.freeze({revision:'tab_stop_paired_state_specific_v4_popover_pin',
  candidate:Object.freeze({repository:'gpui-mbt/gpui.mbt',
    revision:'e160f5ec7bf0c6f43738d0bdcf837098299d5569',tree:'96d62ea12a6824ee20d04cb913191bc23a424522'})});
// This new source profile requires fresh independent captures and byte verification.
export const TAB_CANDIDATE=Object.freeze({repository:'gpui-mbt/gpui.mbt',
  revision:'3bea4fea2dd54768a3859c7c881dda2a60fa5bbd',tree:'25b0647f974d8b6ffd46c1a15c7eeb5ef7e4fe85'});
export const PAIR_REVISION='tab_stop_paired_state_specific_v5_pattern_pin';
export const REQUIRED_HOSTS=['moonbit/host.mjs','moonbit/render.mjs','moonbit/tab-stop-host.mjs','moonbit/focus-visible-host.mjs','load-timing.mjs'];
const HASH=/^[0-9a-f]{64}$/;
const hash=(value,label)=>assert.match(value||'',HASH,label);
const sameKeys=(value,keys,label)=>assert.deepEqual(Object.keys(value).sort(),[...keys].sort(),label);
export function assertPairedProvenance(build,catalog) {
  assert.equal(build.upstream?.repository,'zed-industries/zed');assert.equal(build.upstream?.revision,TAB_STOP.revision);
  assert.deepEqual(build.moonbit,TAB_CANDIDATE,'Exact reviewed candidate core commit/tree');
  assert.deepEqual(catalog.upstream,build.upstream);assert.deepEqual(catalog.moonbit,build.moonbit);
  assert.equal(build.lab_tracked_dirty,false);assert.match(build.lab_revision||'',/^[0-9a-f]{40}$/);assert.match(build.lab_tree||'',/^[0-9a-f]{40}$/);
  assert.equal(build.rust_bundled,true);assert.equal(build.rust?.source_modified,false);assert.equal(build.rust.packaging?.upstream_files_modified,false);
  assert.equal(build.rust.oracle_only,false);assert.deepEqual(build.rust.implemented_subset,['tab_stop']);
  assert.deepEqual(build.rust_implemented,['tab_stop']);assert.deepEqual(build.rust_oracle_only,[],'Historical extra-oracle records cannot certify an implemented pair');
  assert(build.implemented.includes('tab_stop'));assert.deepEqual(build.implemented_sources?.tab_stop,{source:TAB_STOP.source,source_blob:TAB_STOP.sourceBlob});
  const entries=catalog.examples.filter(entry=>entry.id==='tab_stop');assert.equal(entries.length,1);
  for(const [key,value] of Object.entries({moonbit:'implemented',source:TAB_STOP.source,source_blob:TAB_STOP.sourceBlob,
    candidate_source:'web/moonbit/tab_stop/tab_stop.mbt',width:800,height:600}))assert.equal(entries[0][key],value);
  assert.notEqual(entries[0].rust,'oracle_only');
  assert.deepEqual(build.rust_subset_sources,[{id:'tab_stop',source:TAB_STOP.source,source_blob:TAB_STOP.sourceBlob,
    source_sha256:TAB_STOP.sourceSha256,upstream_revision:TAB_STOP.revision,status:'implemented_subset',candidate:'implemented'}]);
  assert.deepEqual(build.rust.packaging.additional_bins,[{name:'tab_stop',source:TAB_STOP.source}]);
  assert(build.rust.command.includes('+nightly-2026-10-14'));assert(build.rust.command.includes('--locked'));
  assert.deepEqual(build.rust.command.filter((_value,index,array)=>array[index-1]==='--bin'),['tab_stop']);
  assert.match(build.rust.toolchain||'',/^rustc 1\./);assert.equal(build.rust.bindings,'wasm-bindgen 0.2.129');
  assert(Number.isFinite(Date.parse(build.rust.build_completed_at_utc||'')));
  for(const file of ['tab_stop.js','tab_stop_bg.wasm','host.mjs','packaging-Cargo.toml'])hash(build.rust.files?.[file],file);
  assert.equal(build.rust.files['unchanged-source/tab_stop.rs'],TAB_STOP.sourceSha256);
  assert.equal(build.rust.files['packaging-Cargo.toml'],build.rust.packaging.manifest_sha256);
  assert.deepEqual(Object.fromEntries(Object.entries(build.rust.embedded_fonts||{}).map(([path,font])=>[path,font.sha256])),EMBEDDED_FONTS);
  for(const font of Object.values(build.rust.embedded_fonts))assert.equal(build.rust.files[font.file],font.sha256);
  assert.match(build.compiler||'',/^moon \S+[^\n]*\nmoonc \S+/,'Measured MoonBit CLI and compiler versions');
  assert.equal(build.moonbit_unit_tests,'passed');assert.equal(build.comparison_status,'unverified');
  hash(build.runtime_sha256_by_example?.tab_stop,'Actual compiled candidate');
  for(const file of REQUIRED_HOSTS)hash(build.moonbit_host_files_sha256?.[file],file);
  assert.deepEqual(build.font_sha256_by_file,Object.fromEntries(['IBMPlexSans-Regular.ttf','IBMPlexSans-Italic.ttf','IBMPlexSans-SemiBold.ttf'].map(name=>[name,EMBEDDED_FONTS['assets/fonts/ibm-plex-sans/'+name]])));
  assert.equal(build.font_sha256,build.font_sha256_by_file['IBMPlexSans-Regular.ttf']);
  return {id:'tab_stop',source:TAB_STOP.source,source_blob:TAB_STOP.sourceBlob,source_sha256:TAB_STOP.sourceSha256,
    upstream_revision:TAB_STOP.revision,width:800,height:600,dpr:1,status:'paired_profile',candidate:'implemented'};
}
export function pairedProvenanceNegativeControls(build,catalog) {
  assertPairedProvenance(build,catalog);
  return [['previous_uniform_list_baseline_core',b=>{b.moonbit={repository:'gpui-mbt/gpui.mbt',revision:'fc53cb382c66f68bfc1b3e1cc72d01056cd3c625',tree:'c9ec59c5fbdbd84548b7d6ffe2c99b8403509db9'};}],
    ['dirty_lab',b=>{b.lab_tracked_dirty=true;}],['wrong_core_commit',b=>{b.moonbit.revision='0'.repeat(40);}],
    ['wrong_core_tree',b=>{b.moonbit.tree='0'.repeat(40);}],['modified_source',b=>{b.rust.source_modified=true;}],
    ['wrong_source_blob',b=>{b.rust_subset_sources[0].source_blob='0'.repeat(40);}],
    ['historical_oracle_claim',b=>{b.rust.oracle_only=true;}],['missing_subset',b=>{b.rust.implemented_subset=null;}],
    ['missing_wasm_hash',b=>{delete b.rust.files['tab_stop_bg.wasm'];}],
    ['missing_candidate_hash',b=>{delete b.runtime_sha256_by_example.tab_stop;}],
    ['missing_host_hash',b=>{delete b.moonbit_host_files_sha256['moonbit/tab-stop-host.mjs'];}],
    ['missing_compiler',b=>{delete b.compiler;}],['wrong_font',b=>{b.font_sha256_by_file['IBMPlexSans-Regular.ttf']='0'.repeat(64);}]]
    .map(([name,mutate])=>{const copy=structuredClone(build);mutate(copy);assert.throws(()=>assertPairedProvenance(copy,catalog),name);return {name,rejected:true};});
}
export function expectedRuntimeFiles(build,runtime) {
  if(runtime==='rust')return {...Object.fromEntries(Object.entries(build.rust.files).map(([file,digest])=>['rust/'+file,digest])),
    'load-timing.mjs':build.moonbit_host_files_sha256['load-timing.mjs']};
  assert.equal(runtime,'moonbit');
  return {...build.moonbit_host_files_sha256,'moonbit/tab_stop.mjs':build.runtime_sha256_by_example.tab_stop,
    ...Object.fromEntries(Object.entries(build.font_sha256_by_file).map(([file,digest])=>['moonbit/'+file,digest]))};
}
export function requiredRuntimeFiles(runtime) {
  return runtime==='rust'?['rust/host.mjs','rust/tab_stop.js','rust/tab_stop_bg.wasm','load-timing.mjs']:
    ['moonbit/tab_stop.mjs',...REQUIRED_HOSTS,'moonbit/IBMPlexSans-Regular.ttf'];
}
export function validateReport(report,runtime) {
  assert.equal(report.runtime,runtime);assert(['rust','moonbit'].includes(runtime));
  assert.equal(report.status,`${runtime}_profile_captured`);assert.equal(report.mode,'paired_profile_capture');
  assert.equal(report.profile_revision,PAIR_REVISION);assert.equal(report.candidate,'implemented');
  assert.equal(report.comparison,'not_run');assert.equal(report.conformance,'not_claimed');assert.equal(report.failure,undefined);
  assert(report.environment&&typeof report.environment==='object','Actual independent runtime environment');
  assert.match(report.environment.browser||'',/^\d+\.\d+\.\d+\.\d+$/);assert.match(report.environment.node||'',/^v\d+\.\d+\.\d+$/);
  assert.equal(report.environment.platform,'linux');assert.equal(report.environment.arch,'x64');
  assert.deepEqual(report.errors,[]);assert(report.console.every(entry=>entry.type!=='error'));
  assert.deepEqual(report.profile,{width:800,height:600,dpr:1});
  assert.deepEqual(report.canvas,{bounds:{x:0,y:0,width:800,height:600},backing:{width:800,height:600}});
  assert.equal(report.transport?.active_tag,'TEXTAREA','Hidden textarea is keyboard transport only');
  assert.equal(report.transport?.canvas_tab_index,-1,'Canvas is not a DOM tab stop');
  assert.deepEqual(report.source,assertPairedProvenance(report.build,report.catalog));
  assert.deepEqual(report.provenance_negative_controls,pairedProvenanceNegativeControls(report.build,report.catalog));
  for(const key of ['build_evidence','catalog_evidence']){assert.equal(report[key].file,`tab-stop-${runtime}-${key==='build_evidence'?'build-manifest':'catalog'}.json`);hash(report[key].sha256,key);}
  assert.equal(report.decoder.name,'Pillow');assert.equal(report.decoder.version,'12.0.0');hash(report.decoder.sha256,'Decoder source');
  const files=expectedRuntimeFiles(report.build,runtime),seen=new Set();
  for(const response of report.runtime_responses) {
    assert(Object.hasOwn(files,response.path),'All executed dependencies must be pinned');assert.equal(response.status,200);
    assert.equal(new URL(response.url).pathname,'/gpui-conformance/'+response.path);assert.equal(response.sha256,files[response.path]);
    assert.equal(response.file,`tab-stop-${runtime}-asset-${response.path.replaceAll('/','_')}.bin`);
    assert(report.requests.some(entry=>entry.url===response.url&&entry.status===200),'Browser request observation');
    assert(report.served_requests.some(entry=>entry.url==='/gpui-conformance/'+response.path&&entry.status===200&&entry.sha256===response.sha256),'Server byte observation');seen.add(response.path);
  }
  for(const path of requiredRuntimeFiles(runtime))assert(seen.has(path),`Actual required runtime dependency: ${path}`);
  for(const request of report.requests)if(/\.(mjs|js|wasm|ttf)$/.test(new URL(request.url).pathname))
    assert(report.runtime_responses.some(response=>response.url===request.url),'Every code/font request must retain actual response bytes');
  return {status:'passed',runtime,loaded_dependencies:seen.size};
}
export async function loadEvidence(directory,report) {
  const root=await realpath(resolve(directory));
  const local=async(file,digest,max=64*1024*1024)=>{
    assert(typeof file==='string'&&file===basename(file)&&file!=='.'&&file!=='..'&&!file.includes('\\'),'Direct local evidence filename');
    const path=await realpath(join(root,file));assert(path.startsWith(root+sep));const info=await stat(path);
    assert(info.isFile()&&info.size>0&&info.size<=max,'Bounded nonempty retained file');const bytes=await readFile(path);assert.equal(sha256(bytes),digest,`${file}: raw bytes hash`);return bytes;
  };
  const manifestBytes=await local(report.build_evidence.file,report.build_evidence.sha256),catalogBytes=await local(report.catalog_evidence.file,report.catalog_evidence.sha256);
  assert.deepEqual(JSON.parse(manifestBytes),report.build);assert.deepEqual(JSON.parse(catalogBytes),report.catalog);
  const decoder=await local(`tab-stop-${report.runtime}-png-decoder.py`,report.decoder.sha256);
  assert.equal(sha256(decoder),sha256(await readFile(new URL('../scripts/decode_oracle_png.py',import.meta.url))));
  const assets={};for(const entry of report.runtime_responses)assets[entry.path]=await local(entry.file,entry.sha256);
  const support={};
  const expectedSupport=['rust/unchanged-source/tab_stop.rs','rust/packaging-Cargo.toml',...Object.values(report.build.rust.embedded_fonts).map(font=>'rust/'+font.file)];
  assert.deepEqual(report.support_files.map(entry=>entry.path).sort(),expectedSupport.sort());
  for(const entry of report.support_files) {
    assert.equal(entry.sha256,report.build.rust.files[entry.path.slice(5)]);support[entry.path]=await local(entry.file,entry.sha256);
    if(entry.path.endsWith('.rs'))assert.equal(createHash('sha1').update(Buffer.from(`blob ${support[entry.path].length}\0`)).update(support[entry.path]).digest('hex'),TAB_STOP.sourceBlob);
  }
  const images={},stableImages={},used=new Set();
  for(const [name,capture] of Object.entries(report.captures)) {
    assert(capture.stable&&capture.file!==capture.stability_file);assert(capture.attempts.length>=2);
    assert.equal(capture.attempts.at(-1).file,capture.file);assert.equal(capture.attempts.at(-2).file,capture.stability_file);
    for(let index=0;index<capture.attempts.length;index++) {
      const attempt=capture.attempts[index];assert.equal(attempt.file,`tab-stop-${report.runtime}-${name}-sample-${index+1}-dpr1.png`);
      assert(!used.has(attempt.file));used.add(attempt.file);const image=decodePng(await local(attempt.file,attempt.png_sha256,8*1024*1024));
      assert.equal(sha256(image.data),attempt.rgba_sha256);assert.equal(attempt.width,800);assert.equal(attempt.height,600);
      if(attempt.file===capture.file)images[name]=image;if(attempt.file===capture.stability_file)stableImages[name]=image;
    }
    assert.equal(sha256(images[name].data),capture.rgba_sha256);assert.equal(sha256(stableImages[name].data),capture.stability_rgba_sha256);
    assert.equal(sha256(images[name].data),sha256(stableImages[name].data),'Two original independently decoded stable samples');
    await local(capture.file,capture.png_sha256);await local(capture.stability_file,capture.stability_png_sha256);
  }
  return {manifestBytes,catalogBytes,assets,support,images,stableImages};
}
function transportAt(profile,count) {
  let pointer={x:0,y:0},modality='mouse';
  for(const operation of profile.operations.slice(0,count))for(const event of operation.expected) {
    if(event.type==='pointermove'){pointer={x:event.x,y:event.y};modality='mouse';}
    if(event.type==='pointerdown')modality='mouse';if(event.type==='keydown'&&event.key!=='Shift')modality='keyboard';
  }
  return {pointer,modality};
}
export function inspectPaint(image,frame,transport) {
  const sample=(x,y)=>Array.from(image.data.subarray(4*(y*800+x),4*(y*800+x)+4));
  const patch=(rect,color,label)=>{for(let y=rect.y;y<rect.y+3;y++)for(let x=rect.x;x<rect.x+3;x++)assert.deepEqual(sample(x,y),color,label);};
  patch({x:4,y:4},[255,255,255,255],'Source white root');
  const hovered=[];
  for(let index=0;index<5;index++) {
    const name='item'+index,rect=frame.controls[name],{x,y}=transport.pointer;
    const hover=index!==3&&transport.modality==='mouse'&&x>=rect.x&&x<rect.x+rect.width&&y>=rect.y&&y<rect.y+rect.height;
    const point={x:rect.x+8,y:rect.y+8},color=sample(point.x,point.y);
    if(hover){assert([[229,229,229,255],[230,230,230,255]].some(expected=>expected.every((value,i)=>value===color[i])),'Source black alpha0.1 hover over white');hovered.push(name);}
    else assert.deepEqual(color,[255,255,255,255],'Non-hover/disabled source card fill');
    patch(point,color,'Uniform source card fill patch');
  }
  for(const name of STOPS.slice(4)){const rect=frame.controls[name];patch({x:rect.x+8,y:rect.y+8},[0,0,0,255],'Black source button fill');}
  // Exact gray border1px / blue3px and source paint order are checked independently by frameGeometry.
  return {hovered_cards:hovered,disabled_card_opacity:'black at0.4 over white gives153',buttons:'opaque black',root:'opaque white'};
}
export function validatePixels(report,retained) {
  const geometry=sourceGeometry(retained.images),profile=makeProfile(geometry.frames);assert(profile.complete);
  sameKeys(retained.images,Object.keys(profile.captures),'Complete independently decoded current-frame profile');
  sameKeys(retained.stableImages,Object.keys(profile.captures),'Complete independent stable sample set');
  validateTraversal(retained.images,geometry);validateClicks(retained.images,geometry);validateOperations(report,geometry);
  for(let index=0;index<report.events.length;index++) {
    const event=report.events[index];assert(Number.isFinite(event.time));if(index)assert(event.time>=report.events[index-1].time,'Trusted delivery chronology');
    if(event.type.startsWith('key'))assert.equal(event.target,'TEXTAREA');
  }
  for(const [name,capture] of Object.entries(report.captures)) {
    assert.equal(sha256(retained.images[name].data),capture.rgba_sha256);
    assert.equal(sha256(retained.stableImages[name].data),capture.stability_rgba_sha256);
  }
  const stableGeometry=sourceGeometry(retained.stableImages);assert.deepEqual(stableGeometry,geometry);
  validateTraversal(retained.stableImages,stableGeometry);validateClicks(retained.stableImages,stableGeometry);
  const paint={};for(const [name,spec] of Object.entries(profile.captures)) {
    const transport=transportAt(profile,spec.after_operation);paint[name]=inspectPaint(retained.images[name],geometry.frames[name],transport);
    assert.deepEqual(inspectPaint(retained.stableImages[name],stableGeometry.frames[name],transport),paint[name]);
  }
  return {geometry,paint,profile,negative_controls:traversalNegativeControls(retained.images,geometry)};
}
export function pixelNegativeControls(report,retained,measured) {
  const rejected=[],check=(name,run)=>{assert.throws(run,name);rejected.push({name,rejected:true});};
  const changed=name=>({...retained.images[name],data:retained.images[name].data.slice()});
  const set=(image,x,y,color)=>image.data.set(color,4*(y*800+x));
  const moved=changed('forward_item0'),card=measured.geometry.frames.forward_item0.controls.item0;
  // A missing original blue edge cannot be rescued by matching report geometry.
  set(moved,card.x,card.y+5,[255,255,255,255]);
  check('moved_or_incomplete_blue_border',()=>frameGeometry(moved));
  const opacity=changed('initial'),disabled=measured.geometry.frames.initial.controls.item3;
  set(opacity,disabled.x,disabled.y+5,[0,0,0,255]);
  check('wrong_nonstop_opacity',()=>frameGeometry(opacity));
  const hover=changed('edge_card_hover'),hoverCard=measured.geometry.frames.edge_card_hover.controls.item0;
  set(hover,hoverCard.x+8,hoverCard.y+8,[255,255,255,255]);
  check('missing_current_card_hover',()=>inspectPaint(hover,measured.geometry.frames.edge_card_hover,
    transportAt(measured.profile,measured.profile.captures.edge_card_hover.after_operation)));
  for(const name of ['edge_card_move','edge_el1_move','edge_el2_move']) {
    const stale=structuredClone(report),operation=stale.operations.find(entry=>entry.name===name);
    // Mutate the trusted plan and delivered event together; source-derived current geometry must still reject it.
    operation.expected[0][name==='edge_card_move'?'y':'x']-=3;
    operation.events[0][name==='edge_card_move'?'y':'x']-=3;
    check(name+'_stale_coordinate',()=>validateOperations(stale,measured.geometry));
  }
  return rejected;
}
export function compareMeasurements(rust,moonbit) {
  for(const name of Object.keys(rust.profile.captures)) {
    assert.deepEqual(moonbit.geometry.frames[name].controls,rust.geometry.frames[name].controls,`${name}: actual cross-renderer source geometry`);
    assert.equal(moonbit.geometry.frames[name].observed_focus,rust.geometry.frames[name].observed_focus);
    assert.deepEqual(moonbit.paint[name],rust.paint[name],`${name}: source paint/hover/opacity relations`);
  }
  assert.deepEqual(moonbit.profile,rust.profile,'Independently derived trusted operation coordinates/order must agree');
  return {status:'source_measurements_agree',captures:Object.keys(rust.profile.captures).length};
}
export function compareBehavior(rust,moonbit,retained) {
  validateReport(rust,'rust');validateReport(moonbit,'moonbit');assert(retained.rust&&retained.moonbit);
  assert.deepEqual(rust.build,moonbit.build);assert.deepEqual(rust.catalog,moonbit.catalog);assert.deepEqual(rust.environment,moonbit.environment);
  assert.equal(rust.build_evidence.sha256,moonbit.build_evidence.sha256);assert.equal(rust.catalog_evidence.sha256,moonbit.catalog_evidence.sha256);
  const checked={};
  for(const [runtime,report] of [['rust',rust],['moonbit',moonbit]]) {
    const files=retained[runtime];assert.equal(sha256(files.manifestBytes),report.build_evidence.sha256);assert.equal(sha256(files.catalogBytes),report.catalog_evidence.sha256);
    for(const entry of report.runtime_responses)assert.equal(sha256(files.assets[entry.path]),entry.sha256,'Actual retained executed runtime bytes required');
    const supportPaths=['rust/unchanged-source/tab_stop.rs','rust/packaging-Cargo.toml',...Object.values(report.build.rust.embedded_fonts).map(font=>'rust/'+font.file)];
    assert.deepEqual(report.support_files.map(entry=>entry.path).sort(),supportPaths.sort(),'All pinned source/font inputs required');
    sameKeys(files.support,report.support_files.map(entry=>entry.path),'Actual retained source/font inputs');
    for(const entry of report.support_files) {
      assert.equal(sha256(files.support[entry.path]),entry.sha256,'Actual retained source/font bytes required');
      assert.equal(entry.sha256,report.build.rust.files[entry.path.slice(5)]);
    }
    checked[runtime]=validatePixels(report,files);
    checked[runtime].pixel_negative_controls=pixelNegativeControls(report,files,checked[runtime]);
  }
  const wasm=retained.rust.assets['rust/tab_stop_bg.wasm'];
  for(const [path,bytes] of Object.entries(retained.rust.support)) {
    assert.deepEqual(bytes,retained.moonbit.support[path],'Both independently retained support inputs must be identical');
    if(path.endsWith('.ttf'))assert(wasm.includes(bytes),'Actual served Rust WASM embeds each complete pinned font');
  }
  const agreement=compareMeasurements(checked.rust,checked.moonbit);
  return {status:'passed',comparison:'independently_decoded_tab_stop_source_behavior',conformance:'bounded_source_profile_only',
    scope:'Actual unchanged Rust WASM and compiled MoonBit; independent128-operation/72-capture source profile at800x600 DPR1',
    source:rust.source,build:{lab_revision:rust.build.lab_revision,lab_tree:rust.build.lab_tree,moonbit:rust.build.moonbit,upstream:rust.build.upstream},
    agreement,geometry:checked.rust.geometry,paint:checked.rust.paint,negative_controls:{rust:[...checked.rust.negative_controls,...checked.rust.pixel_negative_controls],moonbit:[...checked.moonbit.negative_controls,...checked.moonbit.pixel_negative_controls]},
    unverified:['Exact text/OCR, glyph/antialiasing or full-image equality','Shadow rasterization equality','Native parity','Direct group-container focus anchors','Other browsers/GPUs/viewports/DPRs','Touch/IME']};
}
export {assertCurrentTabStopBuild};
