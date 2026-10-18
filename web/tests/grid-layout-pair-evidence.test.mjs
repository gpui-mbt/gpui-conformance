// All runtime records here are synthetic contract fixtures. No actual browser,
// compiler or GPU is executed, and these tests never establish pair conformance.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {mkdtemp,writeFile,symlink,link,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomUUID} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fixture,pixels,frame} from './fixtures/grid-layout-fixtures.mjs';
import {GRID_LAYOUT,EMBEDDED_FONTS,sha256,VIEWPORT_SEQUENCE,COLORS} from './grid-layout-comparator.mjs';
import {PAIR_PROFILE,TOLERANCES,comparePairImages} from './grid-layout-pair-comparator.mjs';
import {PAIR_SUITE_INPUTS,candidateProvenance,validateCandidateReport,assertCandidateRuntime,
  mutatedSource,strictLocalReader,captureBinding,evidenceFilename,assertSuccessfulBaselineSummary,recomputeOrdinaryBaseline,loadQualifiedOrdinaryBaseline} from './grid-layout-pair-evidence.mjs';
const read=path=>readFileSync(new URL('../../'+path,import.meta.url));
const profile=JSON.parse(read('web/pairs/grid_layout.json'));
function build(control=null) {
  const files={};
  for(const path of ['moonbit/grid_layout.mjs','moonbit/host.mjs','moonbit/render.mjs','inputs/grid_layout.mbt','inputs/grid_layout_wbtest.mbt','inputs/moon.pkg','inputs/build-log.json','inputs/current-catalog.json'])files[path]='a'.repeat(64);
  files['inputs/grid_layout.rs']=GRID_LAYOUT.sourceSha256;
  files['inputs/profile.json']=sha256(read('web/pairs/grid_layout.json'));
  files['moonbit/IBMPlexSans-Regular.ttf']=EMBEDDED_FONTS['assets/fonts/ibm-plex-sans/IBMPlexSans-Regular.ttf'];
  const source=read('web/moonbit/grid_layout/grid_layout.mbt');
  const controlSource=control?{original_sha256:sha256(source),mutated_sha256:sha256(mutatedSource(source,profile.executed_controls[control])),
    patch_file:'inputs/source-mutation.patch',patch_sha256:'b'.repeat(64)}:null;
  if(control) {
    files['inputs/grid_layout.mbt']=controlSource.mutated_sha256;
    files['inputs/unmutated-grid_layout.mbt']=controlSource.original_sha256;
    files['inputs/source-mutation.patch']=controlSource.patch_sha256;
  }
  const commands=[['moon','test','examples/conformance_grid_layout','--target','js','--deny-warn'],['moon','build','examples/conformance_grid_layout','--target','js','--release','--deny-warn']];
  return {schema:1,site_kind:'grid_layout_compiled_candidate',qualification:'pinned_clean_source',
    profile:structuredClone(profile),candidate:structuredClone(profile.candidate),candidate_tracked_or_untracked_dirty:false,lab_tracked_dirty:false,
    files,implemented:['grid_layout'],compiler:'moon synthetic fixture',unit_tests:control?'not_run_for_executed_mutant':'passed',
    completed_at_utc:'2026-10-17T00:00:00Z',comparison:'not_run',conformance:'not_claimed',executed_control:control,
    mutation:control?profile.executed_controls[control]:null,control_source:controlSource,commands:control?commands.slice(1):commands};
}
function reportFixture() {
  const {report}=fixture();report.runtime='moonbit';report.profile_revision=PAIR_PROFILE;
  report.mode='actual_compiled_candidate_capture';report.status='moonbit_profile_captured';report.build=build();
  report.source=candidateProvenance(report.build);report.capture_session=randomUUID();
  report.build_evidence.file='grid-layout-moonbit-build-manifest.json';
  report.input_evidence.file='grid-layout-moonbit-trusted-input.json';report.graphics_evidence.file='grid-layout-moonbit-graphics.json';
  report.suite_inputs=PAIR_SUITE_INPUTS.map(path=>({path,file:evidenceFilename('moonbit','suite',path),sha256:sha256(read(path)),bytes:read(path).length}));
  for(const [index,[name,capture]] of Object.entries(report.captures).entries()) {
    capture.binding=captureBinding(report,name,index-1);
    for(const [i,attempt] of capture.attempts.entries()) {
      attempt.file=`grid-layout-moonbit-${name}-sample-${i+1}-dpr1.png`;attempt.binding=capture.binding;
    }
    capture.file=capture.attempts[1].file;capture.stability_file=capture.attempts[0].file;
    capture.scene={file:`grid-layout-moonbit-${name}-scene.json`,sha256:'a'.repeat(64)};
  }
  return report;
}
function runtimeFixture() {
  const report=reportFixture(),assets={},responses={};report.requests=[];report.runtime_responses=[];report.served_requests=[];
  const paths=['moonbit/index.html','moonbit/host.mjs','moonbit/grid_layout.mjs','moonbit/render.mjs','moonbit/grid-layout-host.mjs','moonbit/IBMPlexSans-Regular.ttf','load-timing.mjs'];
  for(const [i,path] of paths.entries()) {
    const bytes=Buffer.from('synthetic executed asset '+path),id=i+1;
    const url='http://127.0.0.1:12345/gpui-conformance/'+(i===0?'moonbit/?example=grid_layout':path);
    const type=i===0?'document':path.endsWith('.ttf')?'font':'script';
    report.build.files[path]=sha256(bytes);assets[path]=bytes;responses[id]=bytes;
    report.runtime_responses.push({path,url,status:200,response_id:id,resource_type:type,file:evidenceFilename('moonbit','asset',url,id),sha256:sha256(bytes),bytes:bytes.length,binding:{runtime:'moonbit',session:report.capture_session}});
    report.requests.push({url,status:200,response_id:id,resource_type:type});
    report.served_requests.push({url:new URL(url).pathname+new URL(url).search,status:200,sha256:sha256(bytes)});
  }
  return {report,assets,responses};
}
test('separate clean source profile binds exact source/core/font and disallows hidden executed faults',()=>{
  assert.equal(candidateProvenance(build()).upstream.source_sha256,GRID_LAYOUT.sourceSha256);
  for(const change of [b=>b.candidate.revision='0'.repeat(40),b=>b.qualification='unqualified_local_override',
    b=>b.files['moonbit/IBMPlexSans-Regular.ttf']='0'.repeat(64),b=>b.candidate_tracked_or_untracked_dirty=true,
    b=>b.executed_control='wrong_gap',b=>delete b.files['inputs/build-log.json']]) {
    const b=build();change(b);assert.throws(()=>candidateProvenance(b));
  }
});
test('explicit compiled controls bind their exact source mutations and cannot count as ordinary pair evidence',()=>{
  const source=read('web/moonbit/grid_layout/grid_layout.mbt');
  for(const name of ['wrong_gap','wrong_color']) {
    const b=build(name);candidateProvenance(b,undefined,name);assert.throws(()=>candidateProvenance(b));
    const changed=mutatedSource(source,b.mutation);assert.notEqual(sha256(changed),sha256(source));
    assert.equal(changed.toString().split(b.mutation.replace).length-1,b.mutation.occurrences);
    assert.throws(()=>mutatedSource(Buffer.from('missing anchors'),b.mutation));
  }
});
test('eight candidate captures require trusted same-document resize restoration and separate original requests',()=>{
  const report=reportFixture();validateCandidateReport(report);
  for(const change of [r=>r.operations[0].events[0].trusted=false,r=>r.navigation_count++,
    r=>r.captures.narrow399.binding.runtime='rust',r=>r.captures.initial.stability_file=r.captures.initial.file,
    r=>r.captures.return400.scene.file='borrowed.json',r=>r.captures.initial.attempts[1].request_ordinal=1,
    r=>r.captures.wide401.viewport.canvas.backing.width++,r=>delete r.captures.final500]) {
    const copy=structuredClone(report);change(copy);assert.throws(()=>validateCandidateReport(copy));
  }
});
test('runtime retention checks actual per-response bytes, font, source route and server records',()=>{
  const {report,assets,responses}=runtimeFixture();assertCandidateRuntime(report,assets,responses);
  for(const path of Object.keys(assets))assert.throws(()=>assertCandidateRuntime(report,{...assets,[path]:Buffer.from('changed')},responses));
  for(const id of Object.keys(responses))assert.throws(()=>assertCandidateRuntime(report,assets,{...responses,[id]:Buffer.from('changed')}));
  for(const change of [r=>r.runtime_responses.pop(),r=>r.runtime_responses[0].binding.session=randomUUID(),
    r=>r.runtime_responses[0].url=r.runtime_responses[0].url.replace('grid_layout','uniform_list'),
    r=>r.served_requests=[],r=>r.runtime_responses[1].url='https://example.com/host.mjs',
    r=>r.runtime_responses[1].response_id=1,r=>r.requests.push({...r.requests[1],response_id:99})]) {
    const changed=structuredClone(report);change(changed);assert.throws(()=>assertCandidateRuntime(changed,assets,responses));
  }
});
test('strict reader rejects hash changes, duplicate files, symlinks and hardlinks',async()=>{
  const directory=await mkdtemp(join(tmpdir(),'grid-pair-contract-'));
  try {
    const bytes=Buffer.from('original'),digest=sha256(bytes);await writeFile(join(directory,'file.json'),bytes);
    const local=await strictLocalReader(directory);assert.deepEqual(await local('file.json',digest),bytes);
    await assert.rejects(()=>local('file.json',digest));
    await assert.rejects(async()=>{const fresh=await strictLocalReader(directory);await fresh('file.json','0'.repeat(64));});
    await symlink(join(directory,'file.json'),join(directory,'alias.json'));
    await assert.rejects(async()=>{const fresh=await strictLocalReader(directory);await fresh('alias.json',digest);});
    await link(join(directory,'file.json'),join(directory,'hard.json'));
    await assert.rejects(async()=>{const fresh=await strictLocalReader(directory);await fresh('hard.json',digest);});
  }finally{await rm(directory,{recursive:true,force:true});}
});

function baselineFixture() {
  const report=reportFixture(),rustBytes=Buffer.from('synthetic exact Rust report');
  const checkout={revision:'1'.repeat(40),tree:'2'.repeat(40),trackedDirty:false,catalogBytes:Buffer.from('synthetic catalog')};
  report.build.lab_revision=checkout.revision;report.build.lab_tree=checkout.tree;
  report.build.files['inputs/current-catalog.json']=sha256(checkout.catalogBytes);
  report.rust_input={report_sha256:sha256(rustBytes)};
  const reportBytes=Buffer.from(JSON.stringify(report));
  const summary={status:'bounded_color_component_pair_verified',comparison:'bounded_original_color_component_pair',
    expected_control:null,conformance:'not_claimed',candidate:report.build.candidate,upstream:profile.upstream,
    inputs:{moonbit:{file:'grid-layout-moonbit-result-dpr1.json',sha256:sha256(reportBytes)},
      rust:{file:'grid-layout-rust-result-dpr1.json',sha256:sha256(rustBytes)}},
    current_checkout:{revision:checkout.revision,tree:checkout.tree,tracked_dirty:false,catalog_sha256:sha256(checkout.catalogBytes)},
    core:{revision:profile.candidate.revision,tree:profile.candidate.tree},tolerances_physical_pixels:TOLERANCES};
  return {report,reportBytes,rustBytes,checkout,summary};
}
test('control baseline must be successful ordinary evidence bound to exact reports, source, core and current suite',()=>{
  const f=baselineFixture();assertSuccessfulBaselineSummary(f.summary,f.report,f.reportBytes,f.rustBytes,f.checkout);
  for(const mutate of [x=>x.summary.status='failed',x=>delete x.summary.expected_control,
    x=>x.summary.expected_control='wrong_gap',x=>x.summary.inputs.rust.sha256='0'.repeat(64),
    x=>x.summary.inputs.moonbit.sha256='0'.repeat(64),x=>x.summary.current_checkout.revision='0'.repeat(40),
    x=>x.summary.core.tree='0'.repeat(40),x=>x.summary.upstream={...x.summary.upstream,source_sha256:'0'.repeat(64)},
    x=>x.report.build.profile={...x.report.build.profile,profile:'different_source_profile'},
    x=>x.report.build=build('wrong_color'),x=>x.checkout.trackedDirty=true]) {
    const x=baselineFixture();mutate(x);
    assert.throws(()=>assertSuccessfulBaselineSummary(x.summary,x.report,x.reportBytes,x.rustBytes,x.checkout));
  }
});
test('forged success cannot qualify the preserved pre-existing ordinary geometry failure',()=>{
  const rust=pixels(),ordinary={images:Object.fromEntries(VIEWPORT_SEQUENCE.map(({name,width})=>[name,frame(width,3)]))};
  ordinary.stableImages=ordinary.images;
  // This exact error matched a27d's broad wrong-gap rejection gate despite the
  // ordinary candidate already failing. Preserve it as a regression fixture.
  assert.throws(()=>comparePairImages(rust.images,ordinary.images),/header left: measured 3, source expectation 0/);
  assert.throws(()=>recomputeOrdinaryBaseline(rust,ordinary,{status:'bounded_color_component_pair_verified'}),/header left: measured 3/);
  const purple=Object.fromEntries(Object.entries(ordinary.images).map(([name,image])=>[name,{...image,data:image.data.slice()}]));
  for(const image of Object.values(purple))for(let p=0;p<image.width*image.height;p++)
    if(COLORS.content.every((v,i)=>image.data[p*4+i]===v))image.data.set([128,0,128,255],p*4);
  assert.throws(()=>comparePairImages(rust.images,purple),/content: substantial/);
  // Either named fault still needs the ordinary predicate to pass first.
  for(const control of ['wrong_gap','wrong_color'])assert.throws(()=>recomputeOrdinaryBaseline(rust,ordinary,{expected_control:control}));
});
test('a valid ordinary original-raster pair recomputes both stable sets; changed success summary fails',()=>{
  const rust=pixels(),ordinary=pixels(),pair=comparePairImages(rust.images,ordinary.images);
  assert.deepEqual(recomputeOrdinaryBaseline(rust,ordinary,{pair}),pair);
  const changed=structuredClone(pair);changed.status='invented_success';
  assert.throws(()=>recomputeOrdinaryBaseline(rust,ordinary,{pair:changed}));
  assert.throws(()=>recomputeOrdinaryBaseline(rust,{...ordinary,stableImages:{...ordinary.stableImages,narrow399:ordinary.images.initial}},{pair}));
});
test('missing ordinary files and direct control CLI without an ordinary directory fail closed',async()=>{
  const directory=await mkdtemp(join(tmpdir(),'grid-pair-missing-baseline-'));
  try {
    await assert.rejects(()=>loadQualifiedOrdinaryBaseline(directory,{}));
    const result=spawnSync('node',['web/tests/verify-grid-layout-pair.mjs',directory,'missing-rust','missing-core','wrong_gap'],
      {cwd:new URL('../../',import.meta.url),encoding:'utf8'});
    assert.equal(result.status,1);assert.match(result.stderr,/controls require a successful ordinary baseline/);
    const report=JSON.parse(readFileSync(join(directory,'grid-layout-pair-verification.json')));
    assert.equal(report.status,'failed');assert.equal(report.executed_control,undefined);
  }finally{await rm(directory,{recursive:true,force:true});}
});
