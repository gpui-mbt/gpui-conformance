import assert from 'node:assert/strict';
import {readFile,realpath,lstat} from 'node:fs/promises';
import {readFileSync,readdirSync} from 'node:fs';
import {resolve,join,basename,sep} from 'node:path';
import {spawnSync} from 'node:child_process';
import {sha256,decodePng,EMBEDDED_FONTS,ANCHOR,SOURCE_CONSTRAINTS,assertViewport,validateOperations,VIEWPORT_SEQUENCE} from './anchor-comparator.mjs';
import {GRAPHICS_ARGS,runtimeResponsePath,requiresRuntimeRetention,captureBinding,inputEvidence} from './anchor-runtime-evidence.mjs';
import {assertUploadSafeFilename,assertLocalRuntimeURL,evidenceFilename} from './anchor-worker-evidence.mjs';
import {PAIR_PROFILE,TOLERANCES,NOT_CLAIMED,comparePairImages} from './anchor-pair-comparator.mjs';
export {GRAPHICS_ARGS,runtimeResponsePath,requiresRuntimeRetention,captureBinding,inputEvidence,evidenceFilename};
export const PAIR_SUITE_INPUTS=Object.freeze([
  'web/pairs/anchor.json','web/scripts/build_anchor_pair.py','web/tests/anchor-pair-browser.mjs',
  'web/tests/anchor-pair-evidence.mjs','web/tests/anchor-pair-comparator.mjs',
  'web/tests/verify-anchor-pair.mjs','web/scripts/decode_anchor_png.py',
  'web/load-timing.mjs','.github/workflows/anchor-browser-pair.yml',
  'web/scripts/build_moonbit.py','web/tests/anchor-comparator.mjs',
  'web/tests/anchor-runtime-evidence.mjs','web/tests/anchor-worker-evidence.mjs',
  'web/scripts/run_anchor_pair_controls.py',
  ...readdirSync(new URL('../moonbit/site/',import.meta.url)).filter(name=>name.endsWith('.mjs')||name==='index.html').sort().map(name=>'web/moonbit/site/'+name),
  ...readdirSync(new URL('../moonbit/anchor/',import.meta.url)).sort().map(name=>'web/moonbit/anchor/'+name),
]);
const SHA=/^[0-9a-f]{64}$/;
export function candidateProvenance(build,profile=JSON.parse(readFileSync(new URL('../pairs/anchor.json',import.meta.url))),expectedControl=null) {
  assert(build&&typeof build==='object'&&!Array.isArray(build));
  assert.deepEqual(Object.keys(build).sort(),['schema','site_kind','profile','qualification','candidate','candidate_tracked_or_untracked_dirty','lab_revision','lab_tree','lab_tracked_dirty','compiler','completed_at_utc','commands','unit_tests','executed_control','mutation','control_source','implemented','font_contract','core_source_sha256','files','comparison','conformance'].sort(),'Exact build manifest schema');
  assert.match(build.lab_revision||'',/^[0-9a-f]{40}$/);assert.match(build.lab_tree||'',/^[0-9a-f]{40}$/);
  assert.equal(build.schema,1);assert.equal(build.site_kind,'anchor_compiled_candidate');
  assert.equal(build.qualification,'pinned_clean_source','Local overrides are never qualified');
  assert.equal(build.candidate_tracked_or_untracked_dirty,false);assert.equal(build.lab_tracked_dirty,false);
  assert.match(profile.candidate.revision||'',/^[0-9a-f]{40}$/,'Exact published core pin required');
  assert.match(profile.candidate.tree||'',/^[0-9a-f]{40}$/,'Exact published core tree required');
  assert.deepEqual(build.profile,profile);assert.equal(profile.profile,PAIR_PROFILE);
  assert.deepEqual(profile.tolerances_physical_pixels,TOLERANCES);
  assert.deepEqual(profile.sequence,VIEWPORT_SEQUENCE.map(state=>state.name));
  assert.deepEqual(profile.viewport,{widths:[750,480],height:600,dpr:1});
  assert.deepEqual(build.candidate,profile.candidate);assert.deepEqual(build.implemented,['anchor']);
  assert.equal(profile.upstream.repository,'zed-industries/zed');assert.equal(profile.upstream.source,ANCHOR.source);
  assert.equal(profile.upstream.revision,ANCHOR.revision);assert.equal(profile.upstream.tree,ANCHOR.tree);
  assert.equal(profile.upstream.source_blob,ANCHOR.sourceBlob);assert.equal(profile.upstream.source_sha256,ANCHOR.sourceSha256);
  assert.equal(build.files['inputs/anchor.rs'],ANCHOR.sourceSha256);
  assert.equal(build.files['moonbit/IBMPlexSans-Regular.ttf'],EMBEDDED_FONTS['assets/fonts/ibm-plex-sans/IBMPlexSans-Regular.ttf']);
  assert.equal(build.files['inputs/profile.json'],sha256(readFileSync(new URL('../pairs/anchor.json',import.meta.url))),'Canonical profile bytes');
  for(const path of ['moonbit/anchor.mjs','moonbit/host.mjs','moonbit/render.mjs','inputs/anchor.mbt','inputs/anchor_wbtest.mbt','inputs/moon.pkg','inputs/build-log.json','inputs/current-catalog.json'])assert.match(build.files[path]||'',SHA,path);
  assert.match(build.compiler||'',/moon/);
  assert.equal(build.executed_control,expectedControl,'Executed faults never qualify as an ordinary candidate');
  assert.equal(build.unit_tests,expectedControl?'not_run_for_executed_mutant':'passed');
  assert.deepEqual(build.mutation,expectedControl?profile.executed_controls[expectedControl]:null);
  if(expectedControl) {
    assert(Object.hasOwn(profile.executed_controls,expectedControl));
    const original=readFileSync(new URL('../moonbit/anchor/anchor.mbt',import.meta.url));
    assert.equal(build.control_source.original_sha256,sha256(original));
    assert.equal(build.control_source.mutated_sha256,sha256(mutatedSource(original,build.mutation)));
    assert.equal(build.files['inputs/anchor.mbt'],build.control_source.mutated_sha256);
    assert.equal(build.files['inputs/unmutated-anchor.mbt'],build.control_source.original_sha256);
    assert.equal(build.control_source.patch_file,'inputs/source-mutation.patch');
    assert.match(build.control_source.patch_sha256,SHA);
    assert.equal(build.files['inputs/source-mutation.patch'],build.control_source.patch_sha256);
  }else assert.equal(build.control_source,null);
  assert(Number.isFinite(Date.parse(build.completed_at_utc||'')));
  assert.equal(build.comparison,'not_run');assert.equal(build.conformance,'not_claimed');
  const commands=[['moon','test','examples/conformance_anchor','--target','js','--deny-warn'],
    ['moon','build','examples/conformance_anchor','--target','js','--release','--deny-warn']];
  assert.deepEqual(build.commands,expectedControl?commands.slice(1):commands);
  return {candidate:build.candidate,upstream:profile.upstream,qualification:build.qualification};
}
export function assertCandidateRuntime(report,assets,responses) {
  const required=['moonbit/index.html','moonbit/host.mjs','moonbit/anchor.mjs','moonbit/render.mjs',
    'moonbit/anchor-host.mjs','moonbit/IBMPlexSans-Regular.ttf','load-timing.mjs'];
  const ids=new Set(),seen=new Set(),doc=report.runtime_responses.find(r=>r.path==='moonbit/index.html');
  assert(doc,'Actual candidate document response');const origin=assertLocalRuntimeURL(doc.url).origin;
  for(const record of report.runtime_responses) {
    assert(Number.isSafeInteger(record.response_id)&&record.response_id>0&&!ids.has(record.response_id));ids.add(record.response_id);
    assert.deepEqual(record.binding,{runtime:'moonbit',session:report.capture_session});
    const url=assertLocalRuntimeURL(record.url);assert.equal(url.origin,origin,'No external/blob/data candidate executable response');
    assert.equal(record.path,runtimeResponsePath(record.url));assert.equal(record.status,200);
    assert.equal(record.sha256,report.build.files[record.path],'Executed dependency must be pinned');
    assert.equal(record.file,evidenceFilename('moonbit','asset',record.url,record.response_id));
    if(record.path==='moonbit/index.html') {
      assert.equal(record.resource_type,'document');assert.equal(url.pathname,'/gpui-conformance/moonbit/');assert.equal(url.search,'?example=anchor');
    }else assert.equal(record.url,origin+'/gpui-conformance/'+record.path);
    assert(report.served_requests.some(r=>r.url===url.pathname+url.search&&r.status===200&&r.sha256===record.sha256));
    assert(report.requests.some(r=>r.response_id===record.response_id&&r.url===record.url&&r.status===200&&r.resource_type===record.resource_type));
    assert.equal(sha256(responses[record.response_id]),record.sha256);assert.equal(responses[record.response_id].length,record.bytes);
    assert.equal(sha256(assets[record.path]),record.sha256);seen.add(record.path);
  }
  for(const path of required)assert(seen.has(path),`Required actual response ${path}`);
  const requestIds=new Set();
  for(const request of report.requests) {
    assert(!requestIds.has(request.response_id));requestIds.add(request.response_id);
    if(requiresRuntimeRetention(request.url,request.resource_type))assert(ids.has(request.response_id),'Every actual executable/font response retained');
  }
}
export function validateCandidateReport(report,expectedControl=null) {
  assert.equal(report.runtime,'moonbit');assert.equal(report.profile_revision,PAIR_PROFILE);
  assert.equal(report.decoder.name,'Pillow');assert.equal(report.decoder.version,'12.0.0');
  assert.equal(report.mode,'actual_compiled_candidate_capture');assert.equal(report.status,'moonbit_profile_captured');
  assert.equal(report.failure,undefined);assert.equal(report.conformance,'not_claimed');assert.equal(report.comparison,'not_run');
  candidateProvenance(report.build,undefined,expectedControl);assert.deepEqual(report.source,candidateProvenance(report.build,undefined,expectedControl));assert.deepEqual(report.errors,[]);assert(report.console.every(x=>x.type!=='error'));
  assert.deepEqual(report.profile,{widths:[750,480],height:600,dpr:1});
  assert.equal(report.transport?.canvas_tab_index,-1);
  assert.deepEqual(report.source_constraints,SOURCE_CONSTRAINTS);assert.deepEqual(report.unverified,NOT_CLAIMED);
  assert.equal(report.navigation_count,1);assert.match(report.document_id||'',/^[0-9a-f-]{36}$/);
  assert.deepEqual(Object.keys(report.captures),VIEWPORT_SEQUENCE.map(state=>state.name));

  assert.equal(report.environment.playwright,'1.56.1');assert.equal(report.environment.platform,'linux');assert.equal(report.environment.arch,'x64');
  assert.match(report.environment.browser,/^\d+\.\d+\.\d+\.\d+$/);assert.deepEqual(report.environment.graphics_requested,GRAPHICS_ARGS);
  assert.match(report.graphics_actual?.gpu?.auxAttributes?.glRenderer||'',/swiftshader/i);
  assert.match(report.capture_session,/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/);
  assert.deepEqual(report.suite_inputs.map(x=>x.path),PAIR_SUITE_INPUTS);
  for(const entry of report.suite_inputs)assert.equal(entry.file,evidenceFilename('moonbit','suite',entry.path));
  assert.equal(report.build_evidence.file,'anchor-moonbit-build-manifest.json');
  assert.equal(report.graphics_evidence.file,'anchor-moonbit-graphics.json');
  assert.equal(report.input_evidence.file,'anchor-moonbit-trusted-input.json');
  for(const [index,[name,capture]] of Object.entries(report.captures).entries()) {
    assertViewport(capture.viewport,VIEWPORT_SEQUENCE[index].width);
    assert.deepEqual(capture.binding,captureBinding(report,name,index-1));assert.equal(capture.after_operation,index);
    assert(capture.stable&&capture.attempts.length>=2);assert.equal(capture.file,capture.attempts.at(-1).file);
    assert.equal(capture.stability_file,capture.attempts.at(-2).file);
    assert.equal(capture.scene.file,`anchor-moonbit-${name}-scene.json`);
    for(const [i,attempt] of capture.attempts.entries()) {
      assert.equal(attempt.file,`anchor-moonbit-${name}-sample-${i+1}-dpr1.png`);
      assert.deepEqual(attempt.binding,capture.binding);assert.equal(attempt.request_ordinal,i+1);
      assert.equal(attempt.method,'Playwright.page.screenshot');
    }
  }
}
export async function strictLocalReader(directory) {
  const root=await realpath(resolve(directory));const inodes=new Set();
  return async(file,digest,max=64*1024*1024)=>{
    assertUploadSafeFilename(file);assert.equal(file,basename(file));assert(!file.includes('\\'));
    const path=join(root,file),actual=await realpath(path);assert.equal(actual,path);assert(actual.startsWith(root+sep));
    const info=await lstat(path);assert(info.isFile()&&!info.isSymbolicLink()&&info.nlink===1&&info.size>0&&info.size<=max);
    const key=`${info.dev}:${info.ino}`;assert(!inodes.has(key),'Each evidence record must have its own physical file');inodes.add(key);
    const bytes=await readFile(path);assert.equal(sha256(bytes),digest,`${file}: retained byte digest`);return bytes;
  };
}
export async function loadCandidateEvidence(directory,report,expectedControl=null) {
  validateCandidateReport(report,expectedControl);const local=await strictLocalReader(directory);
  const manifest=await local(report.build_evidence.file,report.build_evidence.sha256);assert.deepEqual(JSON.parse(manifest),report.build);
  const graphics=await local(report.graphics_evidence.file,report.graphics_evidence.sha256);assert.deepEqual(JSON.parse(graphics),report.graphics_actual);
  const input=await local(report.input_evidence.file,report.input_evidence.sha256);assert.deepEqual(JSON.parse(input),inputEvidence(report));

  for(const entry of report.suite_inputs) {
    const bytes=await local(entry.file,entry.sha256);assert.equal(bytes.length,entry.bytes);
    assert.deepEqual(bytes,await readFile(new URL('../../'+entry.path,import.meta.url)),'Exact current pair/host/source bytes');
  }
  const support={};
  assert.deepEqual(report.support_files.map(x=>x.path).sort(),Object.keys(report.build.files).filter(x=>x.startsWith('inputs/')).sort());
  for(const entry of report.support_files) {
    assert.equal(entry.file,evidenceFilename('moonbit','input',entry.path));
    const bytes=await local(entry.file,entry.sha256);assert.equal(bytes.length,entry.bytes);
    assert.equal(entry.sha256,report.build.files[entry.path]);support[entry.path]=bytes;
    if(/^inputs\/(anchor(?:_wbtest)?\.mbt|moon\.pkg)$/.test(entry.path)) {
      let current=await readFile(new URL('../moonbit/anchor/'+entry.path.slice('inputs/'.length),import.meta.url));
      if(expectedControl&&entry.path==='inputs/anchor.mbt')current=mutatedSource(current,report.build.mutation);
      assert.deepEqual(bytes,current,'Exact original source or explicitly authorized compiled fault');
    }
    if(entry.path==='inputs/profile.json')assert.deepEqual(JSON.parse(bytes),report.build.profile);
    if(entry.path==='inputs/build-log.json') {
      const logs=JSON.parse(bytes);assert.deepEqual(logs.map(log=>log.command),report.build.commands);
      assert(logs.every(log=>log.returncode===0&&typeof log.output==='string'&&log.output.length>0));
    }
  }
  const assets={},responses={};
  for(const entry of report.runtime_responses) {
    const bytes=await local(entry.file,entry.sha256);assets[entry.path]=bytes;responses[entry.response_id]=bytes;
    const current=entry.path==='load-timing.mjs'?'web/load-timing.mjs':entry.path==='moonbit/anchor.mjs'||entry.path.endsWith('.ttf')?null:'web/moonbit/site/'+entry.path.slice('moonbit/'.length);
    if(current)assert.deepEqual(bytes,await readFile(new URL('../../'+current,import.meta.url)));
  }
  assertCandidateRuntime(report,assets,responses);
  const images={},stableImages={},scenes={};
  for(const [name,capture] of Object.entries(report.captures)) {
    const sceneBytes=await local(capture.scene.file,capture.scene.sha256);scenes[name]=JSON.parse(sceneBytes);
    assert.deepEqual(scenes[name].binding,capture.binding);
    for(const attempt of capture.attempts) {
      const bytes=await local(attempt.file,attempt.png_sha256,8*1024*1024);assert.equal(bytes.length,attempt.bytes);
      const image=decodePng(bytes);
      assert.equal(sha256(image.data),attempt.rgba_sha256);assert.equal(attempt.width,VIEWPORT_SEQUENCE.find(state=>state.name===name).width);assert.equal(attempt.height,600);
      assert.equal(image.width,attempt.width);assert.equal(image.height,attempt.height);
      if(attempt.file===capture.file)images[name]=image;if(attempt.file===capture.stability_file)stableImages[name]=image;
    }
    assert.equal(sha256(images[name].data),capture.rgba_sha256);assert.equal(sha256(stableImages[name].data),capture.stability_rgba_sha256);
    assert.equal(capture.rgba_sha256,capture.stability_rgba_sha256);
    assert.equal(capture.png_sha256,capture.attempts.at(-1).png_sha256);
    assert.equal(capture.stability_png_sha256,capture.attempts.at(-2).png_sha256);
  }
  for(const [name,scene] of Object.entries(scenes)) {
    assert.deepEqual(scene.raster_state,{font_loaded:true,runtime_status:'ready'});
    assert.equal(scene.observation.metadata.source_blob,ANCHOR.sourceBlob);

    assert.equal(scene.observation.scale,1);assert.equal(scene.observation.frame.ok,true);
    // Telemetry is retained for diagnostics, never substituted for measured PNGs.
    assert(Number.isInteger(scene.observation.frame.anchor.hovered));
    assert(Array.isArray(scene.observation.anchorEvents));
  }
  validateOperations(report,images);
  validateOperations(report,stableImages);
  if(expectedControl) {
    assert.deepEqual(support['inputs/unmutated-anchor.mbt'],readFileSync(new URL('../moonbit/anchor/anchor.mbt',import.meta.url)));
    const diff=spawnSync('python3',['-c',
      'import difflib,json,sys; a,b=json.load(sys.stdin);sys.stdout.write("".join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile="original/anchor.mbt",tofile="compiled-control/anchor.mbt")))'],
      {input:JSON.stringify([support['inputs/unmutated-anchor.mbt'].toString(),support['inputs/anchor.mbt'].toString()]),maxBuffer:1024*1024});
    assert.equal(diff.status,0);assert.deepEqual(support['inputs/source-mutation.patch'],diff.stdout,'Exact retained source diff, not a synthetic report substitution');
  }
  assert.equal(sha256(support['inputs/anchor.rs']),ANCHOR.sourceSha256);
  assert.equal(sha256(support['inputs/profile.json']),sha256(readFileSync(new URL('../pairs/anchor.json',import.meta.url))));
  return {images,stableImages,scenes,assets,responses,support};
}
export function mutatedSource(bytes,mutation) {
  const source=Buffer.from(bytes).toString('utf8');
  assert.equal(source.split(mutation.find).length-1,mutation.occurrences,'Pinned exact mutation anchors');
  return Buffer.from(source.replaceAll(mutation.find,mutation.replace));
}

export function verifyCoreSource(report,retained,coreDirectory) {
  const git=args=>{const p=spawnSync('git',args,{cwd:coreDirectory,encoding:'utf8',maxBuffer:16*1024*1024});
    assert.equal(p.status,0,p.stderr);return p.stdout.trim();};
  assert.equal(git(['rev-parse','HEAD']),report.build.candidate.revision);
  assert.equal(git(['rev-parse','HEAD^{tree}']),report.build.candidate.tree);
  assert.equal(git(['status','--porcelain','--untracked-files=all']),'');
  const paths=git(['ls-tree','-r','--name-only','HEAD']).split('\n').filter(path=>path==='moon.mod'||path==='script/macos_text_prebuild.py'||
    /^(element|layout|primitives|scene)\/.+\.mbt$/.test(path)||/^(element|layout|primitives|scene)\/moon\.pkg$/.test(path)).sort();
  assert.deepEqual(Object.keys(report.build.core_source_sha256).sort(),paths,'Complete exact production dependency source set');
  for(const path of paths) {
    const p=spawnSync('git',['show',`HEAD:${path}`],{cwd:coreDirectory,maxBuffer:16*1024*1024});assert.equal(p.status,0);
    assert.equal(sha256(p.stdout),report.build.core_source_sha256[path]);assert.deepEqual(retained.support['inputs/core/'+path],p.stdout);
  }
  return {revision:report.build.candidate.revision,tree:report.build.candidate.tree,files:paths.length};
}

// A fault is meaningful only relative to a successful exact ordinary pair.
// Summary checks are necessary, never sufficient: original evidence is reopened
// and its pair predicate is recomputed below before any rejection can qualify.
export function assertSuccessfulBaselineSummary(summary,report,reportBytes,rustBytes,checkout) {
  assert.equal(summary.status,'bounded_color_component_pair_verified','Successful ordinary pair baseline required');
  assert.equal(summary.comparison,'bounded_original_color_component_pair');
  assert.equal(summary.expected_control,null,'A control cannot qualify another control');
  assert.equal(summary.failure,undefined);assert.equal(summary.conformance,'not_claimed');
  candidateProvenance(report.build);assert.equal(report.build.executed_control,null);
  assert.equal(summary.inputs.moonbit.file,'anchor-moonbit-result-dpr1.json');
  assert.equal(summary.inputs.moonbit.sha256,sha256(reportBytes),'Exact successful ordinary candidate report');
  assert.equal(summary.inputs.rust.file,'anchor-rust-result-dpr1.json');
  assert.equal(summary.inputs.rust.sha256,sha256(rustBytes),'Same independently verified Rust report');
  assert.equal(report.rust_input.report_sha256,sha256(rustBytes));
  assert.equal(report.build.lab_revision,checkout.revision);assert.equal(report.build.lab_tree,checkout.tree);
  assert.equal(checkout.trackedDirty,false);
  assert.equal(report.build.files['inputs/current-catalog.json'],sha256(checkout.catalogBytes));
  assert.deepEqual(summary.current_checkout,{revision:checkout.revision,tree:checkout.tree,tracked_dirty:false,
    catalog_sha256:sha256(checkout.catalogBytes)});
  assert.deepEqual(summary.candidate,report.build.candidate);
  assert.deepEqual(summary.upstream,report.build.profile.upstream);
  assert.equal(summary.core.revision,report.build.candidate.revision);assert.equal(summary.core.tree,report.build.candidate.tree);
  assert.deepEqual(summary.tolerances_physical_pixels,TOLERANCES);
  return true;
}
export function recomputeOrdinaryBaseline(rustFiles,ordinaryFiles,summary) {
  const pair=comparePairImages(rustFiles.images,ordinaryFiles.images);
  assert.deepEqual(comparePairImages(rustFiles.stableImages,ordinaryFiles.stableImages),pair,
    'Successful ordinary pair must hold for both original independent sample sets');
  assert.deepEqual(summary.pair,pair,'Retained successful summary must match fresh original-byte comparison');
  return pair;
}
export async function loadQualifiedOrdinaryBaseline(directory,{rust,rustBytes,rustFiles,coreDirectory,checkout,controlReport}) {
  assert(typeof directory==='string'&&directory.length>0,'Ordinary candidate evidence directory is mandatory for controls');
  const local=await strictLocalReader(directory);
  const reportFile='anchor-moonbit-result-dpr1.json',summaryFile='anchor-pair-verification.json';
  for(const file of [reportFile,summaryFile]) {
    const info=await lstat(join(directory,file));assert(info.isFile()&&!info.isSymbolicLink()&&info.nlink===1&&info.size>0&&info.size<=64*1024*1024);
  }
  const reportBytes=await readFile(join(directory,reportFile)),summaryBytes=await readFile(join(directory,summaryFile));
  await local(reportFile,sha256(reportBytes));await local(summaryFile,sha256(summaryBytes));
  const ordinary=JSON.parse(reportBytes),summary=JSON.parse(summaryBytes);
  assertSuccessfulBaselineSummary(summary,ordinary,reportBytes,rustBytes,checkout);
  assert.equal(ordinary.rust_input.capture_session,rust.capture_session);
  assert.equal(ordinary.rust_input.initial_png_sha256,rust.captures.initial.png_sha256);
  assert.notEqual(ordinary.capture_session,rust.capture_session);
  assert.notEqual(ordinary.document_id,rust.document_id);
  assert.notEqual(ordinary.capture_session,controlReport.capture_session,'Independent ordinary/control sessions');
  assert.notEqual(ordinary.document_id,controlReport.document_id,'Independent ordinary/control documents');
  assert.equal(ordinary.environment.browser,rust.environment.browser);
  assert.equal(ordinary.environment.browser,controlReport.environment.browser);
  assert.deepEqual(ordinary.build.profile,controlReport.build.profile,'Same exact ordinary/control source profile');
  assert.deepEqual(ordinary.build.candidate,controlReport.build.candidate,'Same exact ordinary/control production core');
  const files=await loadCandidateEvidence(directory,ordinary);
  const core=verifyCoreSource(ordinary,files,coreDirectory);
  assert.deepEqual(summary.core,core);
  const pair=recomputeOrdinaryBaseline(rustFiles,files,summary);
  assert.equal(sha256(files.support['inputs/anchor.mbt']),controlReport.build.control_source.original_sha256,
    'Control source mutation starts at the successful ordinary example bytes');
  assert.notEqual(sha256(files.assets['moonbit/anchor.mjs']),controlReport.build.files['moonbit/anchor.mjs'],
    'Executed control must load a different compiled module from the successful ordinary runtime');
  return {status:pair.status,report:{file:reportFile,sha256:sha256(reportBytes)},
    verification:{file:summaryFile,sha256:sha256(summaryBytes)},capture_session:ordinary.capture_session,
    source_sha256:sha256(files.support['inputs/anchor.mbt']),runtime_sha256:sha256(files.assets['moonbit/anchor.mjs']),
    rust_report_sha256:sha256(rustBytes),core,profile:ordinary.build.profile.profile,current_checkout:summary.current_checkout,
    qualification:'Reopened original ordinary source/runtime/font/input/PNG evidence and recomputed both stable sample sets'};
}
