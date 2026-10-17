import assert from 'node:assert/strict';
import {readFile,realpath,lstat} from 'node:fs/promises';
import {readFileSync,readdirSync} from 'node:fs';
import {resolve,join,basename,sep} from 'node:path';
import {spawnSync} from 'node:child_process';
import {sha256,decodePng,buttonTarget,ORACLE,SOURCES,assertViewport,validateOperations,VIEWPORT_SEQUENCE} from './gradient-comparator.mjs';
import {runtimeResponsePath,requiresRuntimeRetention,verifyBehavior} from './gradient-runtime-evidence.mjs';
import {GRAPHICS_ARGS} from './gradient-comparator.mjs';
import {assertUploadSafeFilename,assertLocalRuntimeURL,evidenceFilename} from './gradient-worker-evidence.mjs';
import {PAIR_PROFILE,TOLERANCES,COLOR_BUDGET,NOT_CLAIMED,comparePairImages} from './gradient-pair-comparator.mjs';
export {runtimeResponsePath,requiresRuntimeRetention,evidenceFilename};
export {GRAPHICS_ARGS} from './gradient-comparator.mjs';
import {POLICY_PROFILE,POLICY_SEQUENCE,verifyPolicyImage} from './gradient-policy-contract.mjs';
export const sequenceFor=r=>r.profile_revision===POLICY_PROFILE?POLICY_SEQUENCE:VIEWPORT_SEQUENCE;
export function captureBinding(report,state){return {runtime:'moonbit',session:report.capture_session,state:state.name,after_operation:state.after_operation,route:report.profile_revision===POLICY_PROFILE?'/moonbit/?example=gradient&policy=1':'/moonbit/?example=gradient',document_id:report.document_id,viewport:{width:state.width,height:state.height,dpr:1}};}
export function inputEvidence(r){return {capture_session:r.capture_session,document_id:r.document_id,navigation_count:r.navigation_count,operations:r.operations,events:r.events,backend:r.backend,initial_viewport:r.initial_viewport};}
export const PAIR_SUITE_INPUTS=Object.freeze([
  'web/tests/gradient-policy-contract.mjs','web/pairs/gradient-mutation-revisions.json','web/pairs/gradient.json','web/scripts/build_gradient_pair.py','web/tests/gradient-pair-browser.mjs',
  'web/tests/gradient-pair-evidence.mjs','web/tests/gradient-pair-comparator.mjs',
  'web/tests/verify-gradient-pair.mjs','web/scripts/decode_gradient_png.py',
  'web/load-timing.mjs','.github/workflows/gradient-browser-pair.yml',
  'web/scripts/build_moonbit.py','web/tests/gradient-comparator.mjs',
  'web/tests/gradient-runtime-evidence.mjs','web/tests/gradient-worker-evidence.mjs',
  'web/scripts/run_gradient_pair_controls.py',
  ...readdirSync(new URL('../moonbit/site/',import.meta.url)).filter(name=>name.endsWith('.mjs')||name==='index.html').sort().map(name=>'web/moonbit/site/'+name),
  ...readdirSync(new URL('../moonbit/gradient/',import.meta.url)).sort().map(name=>'web/moonbit/gradient/'+name),
]);
const SHA=/^[0-9a-f]{64}$/;
export function candidateProvenance(build,profile=JSON.parse(readFileSync(new URL('../pairs/gradient.json',import.meta.url))),expectedControl=null) {
  assert(build&&typeof build==='object'&&!Array.isArray(build));
  assert.deepEqual(Object.keys(build).sort(),['schema','site_kind','profile','qualification','candidate','candidate_tracked_or_untracked_dirty','lab_revision','lab_tree','lab_tracked_dirty','compiler','completed_at_utc','commands','unit_tests','executed_control','mutation','control_source','implemented','font_contract','core_source_sha256','compiled_core_source_sha256','files','comparison','conformance'].sort(),'Exact build manifest schema');
  assert.match(build.lab_revision||'',/^[0-9a-f]{40}$/);assert.match(build.lab_tree||'',/^[0-9a-f]{40}$/);
  assert.equal(build.schema,1);assert.equal(build.site_kind,'gradient_compiled_candidate');
  assert.equal(build.qualification,'pinned_clean_source','Local overrides are never qualified');
  assert.equal(build.candidate_tracked_or_untracked_dirty,false);assert.equal(build.lab_tracked_dirty,false);
  assert.match(profile.candidate.revision||'',/^[0-9a-f]{40}$/,'Exact published core pin required');
  assert.match(profile.candidate.tree||'',/^[0-9a-f]{40}$/,'Exact published core tree required');
  assert.deepEqual(build.profile,profile);assert.equal(profile.profile,PAIR_PROFILE);
  assert.deepEqual(profile.tolerances_physical_pixels,TOLERANCES);assert.deepEqual(profile.tolerances_unorm8,COLOR_BUDGET);
  assert.deepEqual(profile.sequence,VIEWPORT_SEQUENCE.map(state=>state.name));
  assert.deepEqual(profile.viewport,{sizes:[[960,600],[600,960]],dpr:1});
  assert.deepEqual(build.candidate,profile.candidate);assert.deepEqual(build.implemented,['gradient']);
  assert.equal(profile.upstream.repository,'zed-industries/zed');assert.equal(profile.upstream.source,ORACLE.source);
  assert.equal(profile.upstream.revision,ORACLE.upstream_revision);assert.equal(profile.upstream.tree,ORACLE.upstream_tree);
  assert.equal(profile.upstream.source_blob,ORACLE.source_blob);assert.equal(profile.upstream.source_sha256,ORACLE.source_sha256);
  assert.equal(build.files['inputs/gradient.rs'],ORACLE.source_sha256);
  assert.equal(build.files['moonbit/IBMPlexSans-Regular.ttf'],SOURCES.fonts['assets/fonts/ibm-plex-sans/IBMPlexSans-Regular.ttf']);
  assert.equal(build.files['inputs/profile.json'],sha256(readFileSync(new URL('../pairs/gradient.json',import.meta.url))),'Canonical profile bytes');
  for(const path of ['moonbit/gradient.mjs','moonbit/host.mjs','moonbit/render.mjs','inputs/gradient.mbt','inputs/gradient_wbtest.mbt','inputs/moon.pkg','inputs/build-log.json','inputs/current-catalog.json'])assert.match(build.files[path]||'',SHA,path);
  assert.match(build.compiler||'',/moon/);
  assert.equal(build.executed_control,expectedControl,'Executed faults never qualify as an ordinary candidate');
  assert.equal(build.unit_tests,expectedControl?'not_run_for_executed_mutant':'passed');
  assert.deepEqual(build.mutation,expectedControl?profile.executed_controls[expectedControl]:null);
  if(expectedControl) {
    assert(Object.hasOwn(profile.executed_controls,expectedControl));
    assert.equal(build.control_source.path,build.mutation.path);
    assert.equal(build.control_source.original_sha256,build.core_source_sha256[build.mutation.path]);
    assert.equal(build.control_source.mutated_sha256,build.compiled_core_source_sha256[build.mutation.path]);
    assert.equal(build.files['inputs/mutation-original.mbt'],build.control_source.original_sha256);
    assert.equal(build.files['inputs/mutation-compiled.mbt'],build.control_source.mutated_sha256);
    assert.equal(build.control_source.patch_file,'inputs/source-mutation.patch');
    assert.match(build.control_source.patch_sha256,SHA);
    assert.equal(build.files['inputs/source-mutation.patch'],build.control_source.patch_sha256);
  }else assert.equal(build.control_source,null);
  assert(Number.isFinite(Date.parse(build.completed_at_utc||'')));
  assert.equal(build.comparison,'not_run');assert.equal(build.conformance,'not_claimed');
  const commands=[['moon','test','examples/conformance_gradient','--target','js','--deny-warn'],
    ['moon','build','examples/conformance_gradient','--target','js','--release','--deny-warn']];
  assert.deepEqual(build.commands,expectedControl?commands.slice(1):commands);
  return {candidate:build.candidate,upstream:profile.upstream,qualification:build.qualification};
}
export function assertCandidateRuntime(report,assets,responses) {
  const required=['moonbit/index.html','moonbit/host.mjs','moonbit/gradient.mjs','moonbit/render.mjs',
    'moonbit/gradient-host.mjs','moonbit/IBMPlexSans-Regular.ttf','load-timing.mjs'];
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
      assert.equal(record.resource_type,'document');assert.equal(url.pathname,'/gpui-conformance/moonbit/');assert.equal(url.search,report.profile_revision===POLICY_PROFILE?'?example=gradient&policy=1':'?example=gradient');
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
  assert.equal(report.runtime,'moonbit');assert([PAIR_PROFILE,POLICY_PROFILE].includes(report.profile_revision));const sequence=sequenceFor(report);
  assert.equal(report.decoder.name,'Pillow');assert.equal(report.decoder.version,'12.0.0');
  assert.equal(report.mode,'actual_compiled_candidate_capture');assert.equal(report.status,'moonbit_profile_captured');
  assert.equal(report.failure,undefined);assert.equal(report.conformance,'not_claimed');assert.equal(report.comparison,'not_run');
  candidateProvenance(report.build,undefined,expectedControl);assert.deepEqual(report.source,candidateProvenance(report.build,undefined,expectedControl));assert.deepEqual(report.errors,[]);assert(report.console.every(x=>x.type!=='error'));
  assert.deepEqual(report.profile,report.profile_revision===POLICY_PROFILE?{sizes:[[960,600]],dpr:1}:{sizes:[[960,600],[600,960]],dpr:1});
  assert.equal(report.transport?.canvas_tab_index,-1);assertCandidateBackend(report.backend);
  assert.deepEqual(report.unverified,NOT_CLAIMED);
  assertViewport(report.initial_viewport,sequence[0]);assert.equal(report.navigation_count,1);assert.match(report.document_id||'',/^[0-9a-f-]{36}$/);
  assert.deepEqual(Object.keys(report.captures),sequence.map(state=>state.name));

  assert.equal(report.environment.playwright,'1.56.1');assert.equal(report.environment.platform,'linux');assert.equal(report.environment.arch,'x64');
  assert.match(report.environment.browser,/^\d+\.\d+\.\d+\.\d+$/);assert.deepEqual(report.environment.graphics_requested,GRAPHICS_ARGS);
  assert.match(report.graphics_actual?.gpu?.auxAttributes?.glRenderer||'',/swiftshader/i);
  assert.match(report.capture_session,/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/);
  assert.deepEqual(report.suite_inputs.map(x=>x.path),PAIR_SUITE_INPUTS);
  for(const entry of report.suite_inputs)assert.equal(entry.file,evidenceFilename('moonbit','suite',entry.path));
  assert.equal(report.build_evidence.file,'gradient-moonbit-build-manifest.json');
  assert.equal(report.graphics_evidence.file,'gradient-moonbit-graphics.json');
  assert.equal(report.input_evidence.file,'gradient-moonbit-trusted-input.json');
  for(const [index,[name,capture]] of Object.entries(report.captures).entries()) {
    assertViewport(capture.viewport,sequence[index]);
    assert.deepEqual(capture.binding,captureBinding(report,sequence[index]));assert.equal(capture.binding.after_operation,index);
    assert(capture.stable&&capture.attempts.length>=2);assert.equal(capture.file,capture.attempts.at(-1).file);
    assert.equal(capture.stability_file,capture.attempts.at(-2).file);
    assert.equal(capture.scene.file,`gradient-moonbit-${name}-scene.json`);
    for(const [i,attempt] of capture.attempts.entries()) {
      assert.equal(attempt.file,`gradient-moonbit-${name}-sample-${i+1}-dpr1.png`);
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
  validateCandidateReport(report,expectedControl);const sequence=sequenceFor(report);const local=await strictLocalReader(directory);
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
    if(/^inputs\/(gradient(?:_wbtest)?\.mbt|moon\.pkg)$/.test(entry.path)) {
      let current=await readFile(new URL('../moonbit/gradient/'+entry.path.slice('inputs/'.length),import.meta.url));
      
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
    const current=entry.path==='load-timing.mjs'?'web/load-timing.mjs':entry.path==='moonbit/gradient.mjs'||entry.path.endsWith('.ttf')?null:'web/moonbit/site/'+entry.path.slice('moonbit/'.length);
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
      assert.equal(sha256(image.data),attempt.rgba_sha256);assert.equal(attempt.width,sequence.find(state=>state.name===name).width);assert.equal(attempt.height,sequence.find(state=>state.name===name).height);
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
    assert.equal(scene.observation.metadata.source_blob,ORACLE.source_blob);

    assert.equal(scene.observation.scale,1);assert.equal(scene.observation.frame.ok,true);
    // Telemetry is retained for diagnostics, never substituted for measured PNGs.
    assert(['sRGB','Oklab'].includes(scene.observation.frame.gradient.color_space));
    assert(Array.isArray(scene.observation.gradientEvents));
  }
  if(report.profile_revision===POLICY_PROFILE){assert.deepEqual(report.operations,[]);assert.equal(report.navigation_count,1);assert.equal(scenes.policy.observation.frame.gradient.authored_policy_probe,true);assert.deepEqual(scenes.policy.observation.frame.snapshot.items.map(i=>i.id),[1,2,3,4,6]);assert.deepEqual(scenes.policy.observation.frame.operations,[{kind:'rgba_run',index:0,count:5,x:0,y:0,width:960,height:600}]);}else {validateOperations(report);for(const op of report.operations.filter(o=>o.action==='click')){const i=sequence.findIndex(s=>s.name===op.name);assert.deepEqual(op.target,buttonTarget(images[sequence[i-1].name]));assert.deepEqual(op.target,buttonTarget(stableImages[sequence[i-1].name]));}}
  if(expectedControl) {
    const original=support['inputs/mutation-original.mbt'],compiled=support['inputs/mutation-compiled.mbt'];
    assert.deepEqual(compiled,mutatedSource(original,report.build.mutation),'Exact compiled core mutant bytes');
    const diff=spawnSync('python3',['-c',
      'import difflib,json,sys; a,b,p=json.load(sys.stdin);sys.stdout.write("".join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile="original/"+p,tofile="compiled-control/"+p)))'],
      {input:JSON.stringify([original.toString(),compiled.toString(),report.build.mutation.path]),maxBuffer:1024*1024});
    assert.equal(diff.status,0);assert.deepEqual(support['inputs/source-mutation.patch'],diff.stdout,'Exact retained core source diff');
  }
  assert.equal(sha256(support['inputs/gradient.rs']),ORACLE.source_sha256);
  assert.equal(sha256(support['inputs/profile.json']),sha256(readFileSync(new URL('../pairs/gradient.json',import.meta.url))));
  return {images,stableImages,scenes,assets,responses,support};
}
export function mutatedSource(bytes,mutation) {
  const source=Buffer.from(bytes).toString('utf8');
  assert.equal(source.split(mutation.find).length-1,mutation.occurrences,'Pinned exact mutation gradients');
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
  assert.deepEqual(Object.keys(report.build.core_source_sha256).sort(),paths,'Complete exact production dependency source set');assert.deepEqual(Object.keys(report.build.compiled_core_source_sha256).sort(),paths);
  for(const path of paths) {
    const p=spawnSync('git',['show',`HEAD:${path}`],{cwd:coreDirectory,maxBuffer:16*1024*1024});assert.equal(p.status,0);
    assert.equal(sha256(p.stdout),report.build.core_source_sha256[path]);assert.deepEqual(retained.support['inputs/core/'+path],p.stdout);
    const expected=report.build.executed_control&&report.build.mutation.path===path?mutatedSource(p.stdout,report.build.mutation):p.stdout;
    assert.equal(sha256(expected),report.build.compiled_core_source_sha256[path]);assert.deepEqual(retained.support['inputs/compiled-core/'+path],expected);
  }
  return {revision:report.build.candidate.revision,tree:report.build.candidate.tree,files:paths.length};
}

// A fault is meaningful only relative to a successful exact ordinary pair.
// Summary checks are necessary, never sufficient: original evidence is reopened
// and its pair predicate is recomputed below before any rejection can qualify.
export function assertSuccessfulBaselineSummary(summary,report,reportBytes,rustBytes,checkout) {
  assert.equal(summary.status,'bounded_gradient_sample_pair_verified','Successful ordinary pair baseline required');
  assert.equal(summary.comparison,'bounded_original_gradient_sample_pair');
  assert.equal(summary.expected_control,null,'A control cannot qualify another control');
  assert.equal(summary.failure,undefined);assert.equal(summary.conformance,'not_claimed');
  candidateProvenance(report.build);assert.equal(report.build.executed_control,null);
  assert.equal(summary.inputs.moonbit.file,'gradient-moonbit-result-dpr1.json');
  assert.equal(summary.inputs.moonbit.sha256,sha256(reportBytes),'Exact successful ordinary candidate report');
  assert.equal(summary.inputs.rust.file,'gradient-rust-result-dpr1.json');
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
  candidateSourceBehavior({runtime:'moonbit',operations:[]},{images:ordinaryFiles.images});candidateSourceBehavior({runtime:'moonbit',operations:[]},{images:ordinaryFiles.stableImages});
  assert.deepEqual(comparePairImages(rustFiles.stableImages,ordinaryFiles.stableImages),pair,
    'Successful ordinary pair must hold for both original independent sample sets');
  assert.deepEqual(summary.pair,pair,'Retained successful summary must match fresh original-byte comparison');
  return pair;
}
export async function loadQualifiedOrdinaryBaseline(directory,{rust,rustBytes,rustFiles,coreDirectory,checkout,controlReport}) {
  assert(typeof directory==='string'&&directory.length>0,'Ordinary candidate evidence directory is mandatory for controls');
  const local=await strictLocalReader(directory);
  const reportFile='gradient-moonbit-result-dpr1.json',summaryFile='gradient-pair-verification.json';
  for(const file of [reportFile,summaryFile]) {
    const info=await lstat(join(directory,file));assert(info.isFile()&&!info.isSymbolicLink()&&info.nlink===1&&info.size>0&&info.size<=64*1024*1024);
  }
  const reportBytes=await readFile(join(directory,reportFile)),summaryBytes=await readFile(join(directory,summaryFile));
  await local(reportFile,sha256(reportBytes));await local(summaryFile,sha256(summaryBytes));
  const ordinary=JSON.parse(reportBytes),summary=JSON.parse(summaryBytes);
  assertSuccessfulBaselineSummary(summary,ordinary,reportBytes,rustBytes,checkout);
  assert.equal(ordinary.rust_input.capture_session,rust.capture_session);
  assert.equal(ordinary.rust_input.initial_png_sha256,rust.captures.wideSrgb.attempts.at(-1).png_sha256);
  assert.notEqual(ordinary.capture_session,rust.capture_session);
  assert.notEqual(ordinary.document_id,rust.document_id);
  assert.notEqual(ordinary.capture_session,controlReport.capture_session,'Independent ordinary/control sessions');
  assert.notEqual(ordinary.document_id,controlReport.document_id,'Independent ordinary/control documents');
  assert.equal(ordinary.environment.browser,rust.environment.browser);
  assert.equal(ordinary.environment.browser,controlReport.environment.browser);
  assert.deepEqual(ordinary.build.profile,controlReport.build.profile,'Same exact ordinary/control source profile');
  assert.deepEqual(ordinary.build.candidate,controlReport.build.candidate,'Same exact ordinary/control production core');
  assert.equal(ordinary.build.compiler,controlReport.build.compiler,'Same ordinary/control MoonBit toolchain');
  const files=await loadCandidateEvidence(directory,ordinary);
  const core=verifyCoreSource(ordinary,files,coreDirectory);
  assert.deepEqual(summary.core,core);
  const pair=recomputeOrdinaryBaseline(rustFiles,files,summary);
  const policy=await loadPolicyEvidence(join(directory,'policy'),ordinary);
  const policyCheck=verifyPolicyImage(policy.files.images.policy);assert.deepEqual(verifyPolicyImage(policy.files.stableImages.policy),policyCheck);assert.deepEqual(summary.policy,policyCheck);assert.deepEqual(summary.policy_input,policy.binding);
  assert.equal(sha256(files.support['inputs/core/'+controlReport.build.mutation.path]),controlReport.build.control_source.original_sha256,
    'Core source mutation starts at the successful ordinary production core bytes');
  assert.notEqual(sha256(files.assets['moonbit/gradient.mjs']),controlReport.build.files['moonbit/gradient.mjs'],
    'Executed control must load a different compiled module from the successful ordinary runtime');
  return {status:pair.status,report:{file:reportFile,sha256:sha256(reportBytes)},
    verification:{file:summaryFile,sha256:sha256(summaryBytes)},capture_session:ordinary.capture_session,
    source_sha256:sha256(files.support['inputs/core/'+controlReport.build.mutation.path]),runtime_sha256:sha256(files.assets['moonbit/gradient.mjs']),
    rust_report_sha256:sha256(rustBytes),core,profile:ordinary.build.profile.profile,current_checkout:summary.current_checkout,
    qualification:'Reopened original ordinary source/runtime/font/input/PNG evidence and recomputed both stable sample sets'};
}

export async function loadPolicyEvidence(directory,mainReport,expectedControl=null) {
  const bytes=await readFile(join(directory,'gradient-moonbit-result-dpr1.json'));
  await (await strictLocalReader(directory))('gradient-moonbit-result-dpr1.json',sha256(bytes));
  const report=JSON.parse(bytes);assert.equal(report.profile_revision,POLICY_PROFILE);
  assert.notEqual(report.capture_session,mainReport.capture_session);assert.notEqual(report.document_id,mainReport.document_id);
  assert.deepEqual(report.build,mainReport.build);assert.deepEqual(report.rust_input,mainReport.rust_input);assert.equal(report.environment.browser,mainReport.environment.browser);
  const files=await loadCandidateEvidence(directory,report,expectedControl);
  return {report,files,binding:{sha256:sha256(bytes),capture_session:report.capture_session,document_id:report.document_id}};
}

export function candidateSourceBehavior(report,files){assert.equal(report.runtime,'moonbit','Typed candidate-only source predicate adapter');return verifyBehavior({...report,backend:{observed:'candidate_canvas2d_core_rgba_transport'}},files);}
export function assertCandidateBackend(backend){assert.equal(backend.kind,'candidate_canvas2d_core_rgba_transport');assert.equal(backend.visible_canvases.length,1);const id=backend.visible_canvases[0].canvas_id;const events=backend.events.filter(e=>e.canvas_id===id);assert(events.some(e=>e.kind==='getContext'&&e.requested==='2d'&&e.returned));assert(!events.some(e=>e.kind==='webgpu.configure'||(e.kind==='getContext'&&e.returned&&['webgl','webgl2','experimental-webgl'].includes(e.requested))));return backend;}
