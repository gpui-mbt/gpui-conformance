import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdtemp,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {TAB_STOP,EMBEDDED_FONTS,sha256,sourceGeometry} from './tab-stop-comparator.mjs';
import {TAB_CANDIDATE,PAIR_REVISION,REQUIRED_HOSTS,assertPairedProvenance,pairedProvenanceNegativeControls,expectedRuntimeFiles,
  requiredRuntimeFiles,validateReport,loadEvidence,validatePixels,compareMeasurements,compareBehavior,pixelNegativeControls} from './tab-stop-pair-comparator.mjs';
import {syntheticPixels,fixtureFrame} from './tab-stop-pair-fixtures.mjs';
// Synthetic metadata and pixels only test rejection sensitivity; they cannot
// replace actual served bytes, original PNGs, or unchanged pinned font/source inputs.
function metadata(runtime='rust') {
  const upstream={repository:'zed-industries/zed',revision:TAB_STOP.revision};
  const files=Object.fromEntries(['host.mjs','tab_stop.js','tab_stop_bg.wasm','packaging-Cargo.toml'].map(file=>[file,'a'.repeat(64)]));
  files['unchanged-source/tab_stop.rs']=TAB_STOP.sourceSha256;
  const embedded_fonts=Object.fromEntries(Object.entries(EMBEDDED_FONTS).map(([path,sha256])=>{
    const file='embedded-font-inputs/'+path.split('/').at(-1);files[file]=sha256;return [path,{file,sha256}];}));
  const build={upstream,moonbit:TAB_CANDIDATE,lab_revision:'b'.repeat(40),lab_tree:'c'.repeat(40),lab_tracked_dirty:false,rust_bundled:true,
    compiler:'moon 0.1.synthetic\nmoonc v0.1.synthetic',moonbit_unit_tests:'passed',comparison_status:'unverified',font_sha256:EMBEDDED_FONTS['assets/fonts/ibm-plex-sans/IBMPlexSans-Regular.ttf'],
    implemented:['hello_world','tab_stop'],implemented_sources:{tab_stop:{source:TAB_STOP.source,source_blob:TAB_STOP.sourceBlob}},
    runtime_sha256_by_example:{tab_stop:'d'.repeat(64)},font_sha256_by_file:Object.fromEntries(['IBMPlexSans-Regular.ttf','IBMPlexSans-Italic.ttf','IBMPlexSans-SemiBold.ttf'].map(name=>[name,EMBEDDED_FONTS['assets/fonts/ibm-plex-sans/'+name]])),
    moonbit_host_files_sha256:Object.fromEntries([...REQUIRED_HOSTS,'moonbit/another-static-import.mjs'].map(file=>[file,'e'.repeat(64)])),
    rust_implemented:['tab_stop'],rust_oracle_only:[],rust_subset_sources:[{id:'tab_stop',source:TAB_STOP.source,source_blob:TAB_STOP.sourceBlob,
      source_sha256:TAB_STOP.sourceSha256,upstream_revision:TAB_STOP.revision,status:'implemented_subset',candidate:'implemented'}],
    rust:{source_modified:false,oracle_only:false,implemented_subset:['tab_stop'],toolchain:'rustc 1.93.0-nightly (synthetic)',bindings:'wasm-bindgen 0.2.129',
      build_completed_at_utc:'2026-10-16T00:00:00Z',command:['cargo','+nightly-2026-10-14','build','--locked','--bin','tab_stop'],embedded_fonts,files,
      packaging:{upstream_files_modified:false,manifest_sha256:'a'.repeat(64),additional_bins:[{name:'tab_stop',source:TAB_STOP.source}]}}};
  const catalog={upstream,moonbit:TAB_CANDIDATE,examples:[{id:'tab_stop',moonbit:'implemented',source:TAB_STOP.source,source_blob:TAB_STOP.sourceBlob,
    candidate_source:'web/moonbit/tab_stop/tab_stop.mbt',width:800,height:600}]};
  const manifestBytes=Buffer.from(JSON.stringify(build)),catalogBytes=Buffer.from(JSON.stringify(catalog));
  const paths=requiredRuntimeFiles(runtime),hashes=expectedRuntimeFiles(build,runtime);
  const runtime_responses=paths.map(path=>({path,url:'http://localhost/gpui-conformance/'+path,status:200,sha256:hashes[path],file:`tab-stop-${runtime}-asset-${path.replaceAll('/','_')}.bin`}));
  const report={runtime,status:`${runtime}_profile_captured`,mode:'paired_profile_capture',profile_revision:PAIR_REVISION,candidate:'implemented',comparison:'not_run',conformance:'not_claimed',
    environment:{browser:'141.0.0.0',node:'v22.0.0',platform:'linux',arch:'x64',graphics:'Synthetic metadata only'},
    errors:[],console:[],profile:{width:800,height:600,dpr:1},canvas:{bounds:{x:0,y:0,width:800,height:600},backing:{width:800,height:600}},
    transport:{active_tag:'TEXTAREA',canvas_tab_index:-1},build,catalog,source:assertPairedProvenance(build,catalog),provenance_negative_controls:pairedProvenanceNegativeControls(build,catalog),
    build_evidence:{file:`tab-stop-${runtime}-build-manifest.json`,sha256:sha256(manifestBytes)},catalog_evidence:{file:`tab-stop-${runtime}-catalog.json`,sha256:sha256(catalogBytes)},
    decoder:{name:'Pillow',version:'12.0.0',sha256:'f'.repeat(64)},runtime_responses,
    requests:runtime_responses.map(entry=>({url:entry.url,status:200})),served_requests:runtime_responses.map(entry=>({url:new URL(entry.url).pathname,status:200,sha256:entry.sha256}))};
  return {report,manifestBytes,catalogBytes};
}
const synthetic=syntheticPixels();
test('paired source and core pins are exact and historical oracle claims are rejected',()=>{
  const {report}=metadata();assert.equal(TAB_CANDIDATE.revision,'eb968228bbea56aff13721dc427875c2dacffc14');
  assert.equal(TAB_CANDIDATE.tree,'ae9072d350ef6d1546e408226218ec08efc96552');assert.equal(assertPairedProvenance(report.build,report.catalog).candidate,'implemented');
  assert.equal(pairedProvenanceNegativeControls(report.build,report.catalog).length,12);
  const changed=structuredClone(report.catalog);changed.examples[0].moonbit='not_implemented';assert.throws(()=>assertPairedProvenance(report.build,changed));
});
test('both actual runtime reports require pinned dependencies, transport and immutable current paired labels',()=>{
  for(const runtime of ['rust','moonbit']) {
    const {report}=metadata(runtime);assert.equal(validateReport(report,runtime).status,'passed');
    const missing=structuredClone(report);missing.runtime_responses.pop();assert.throws(()=>validateReport(missing,runtime));
    const old=structuredClone(report);old.status='rust_discovery_captured';assert.throws(()=>validateReport(old,runtime));
    const unpinned=structuredClone(report);unpinned.requests.push({url:'http://localhost/gpui-conformance/extra.mjs',status:200});assert.throws(()=>validateReport(unpinned,runtime));
    const bad=structuredClone(report);bad.transport.active_tag='CANVAS';assert.throws(()=>validateReport(bad,runtime));
  }
  assert(Object.hasOwn(expectedRuntimeFiles(metadata('moonbit').report.build,'moonbit'),'moonbit/another-static-import.mjs'));
});
test('synthetic complete current-frame source measurements pass before pairing and do not certify runtime execution',()=>{
  const measured=validatePixels(synthetic.report,synthetic.retained);
  assert.equal(measured.profile.operations.length,128);assert.equal(Object.keys(measured.paint).length,72);
  assert.deepEqual(measured.paint.click_item1.hovered_cards,['item1']);assert.deepEqual(measured.paint.after_click_item1.hovered_cards,[]);
  assert.deepEqual(measured.paint.edge_card_down.hovered_cards,['item0']);
  assert.equal(compareMeasurements(measured,measured).status,'source_measurements_agree');
  assert.equal(pixelNegativeControls(synthetic.report,synthetic.retained,measured).length,6);
});
test('paired geometry and source order cannot be blessed by equal-looking report metadata',()=>{
  const measured=validatePixels(synthetic.report,synthetic.retained),wrong=structuredClone(measured);
  wrong.geometry.frames.forward_item1.controls.item1.y++;assert.throws(()=>compareMeasurements(measured,wrong));
  const focus=structuredClone(measured);focus.geometry.frames.forward_item1.observed_focus='item4';assert.throws(()=>compareMeasurements(measured,focus));
  const order=structuredClone(synthetic.report);order.operations[2].name='invented_order';assert.throws(()=>validatePixels(order,synthetic.retained));
  const stale=structuredClone(synthetic.report),operation=stale.operations.find(entry=>entry.name==='edge_el1_move');operation.expected[0].x=393;operation.events[0].x=393;
  assert.throws(()=>validatePixels(stale,synthetic.retained),/redefine/);
});
test('missing hover, changed opacity, stale paint and changed focus fail source paint/frame predicates',()=>{
  const missing={...synthetic.retained,images:{...synthetic.retained.images,edge_card_hover:fixtureFrame('item0','forward',false)}};
  const report=structuredClone(synthetic.report);report.captures.edge_card_hover.rgba_sha256=sha256(missing.images.edge_card_hover.data);
  assert.throws(()=>validatePixels(report,missing));
  const opacity={...synthetic.retained,images:{...synthetic.retained.images,initial:fixtureFrame()}};
  const initial=opacity.images.initial;initial.data.set([0,0,0,255],4*(190*800+16));assert.throws(()=>sourceGeometry(opacity.images));
  const mismatch={...synthetic.retained,stableImages:{...synthetic.retained.stableImages,edge_card_down:fixtureFrame(null,'forward')}};
  assert.throws(()=>validatePixels(synthetic.report,mismatch));
});
test('retained loader refuses forged manifest bytes before any report can self-certify original PNGs',async()=>{
  const directory=await mkdtemp(join(tmpdir(),'tab-stop-pair-unit-'));
  try {
    const {report}=metadata();await writeFile(join(directory,report.build_evidence.file),'forged');
    await assert.rejects(()=>loadEvidence(directory,report),/raw bytes hash/);
  }finally{await rm(directory,{recursive:true,force:true});}
});
test('metadata plus matching synthetic images cannot self-certify actual paired execution without real retained bytes',()=>{
  const reports={},retained={};
  for(const runtime of ['rust','moonbit']) {
    const data=metadata(runtime);reports[runtime]={...data.report,...synthetic.report,support_files:[]};
    retained[runtime]={...synthetic.retained,manifestBytes:data.manifestBytes,catalogBytes:data.catalogBytes,support:{},
      assets:Object.fromEntries(data.report.runtime_responses.map(entry=>[entry.path,Buffer.from('synthetic asset, not actual execution')]))};
  }
  assert.throws(()=>compareBehavior(reports.rust,reports.moonbit,retained),/Actual retained executed runtime bytes/);
});
test('dedicated pair workflow keeps the complete profile out of the matched job and retains independent failures',async()=>{
  const pair=await readFile(new URL('../../.github/workflows/tab-stop-oracle.yml',import.meta.url),'utf8');
  const matched=await readFile(new URL('../../.github/workflows/browser-examples.yml',import.meta.url),'utf8');
  assert(pair.includes('timeout-minutes: 75'));assert(pair.includes('--implemented-example tab_stop'));
  assert(pair.includes('tab-stop-pair-browser.mjs _build/tab-stop-browser-lab --candidate'));assert(pair.includes('compare-tab-stop-results.mjs'));
  assert(pair.includes('if: always()'));assert(!matched.includes('tab-stop-pair-browser'));
});
