// Reopen both original evidence sets and exact production source. Never certify
// from pass flags, in-memory screenshots, template workers or candidate telemetry.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {sha256,discoverGeometry,profileNegativeControls} from './uniform-list-comparator.mjs';
import {validateReport,loadEvidence,verifyBehavior,assertCurrentBuild} from './uniform-list-runtime-evidence.mjs';
import {candidateProvenance,loadCandidateEvidence,verifyCoreSource} from './uniform-list-pair-evidence.mjs';
import {comparePairImages,compareBoundedPlacement,boundedNegativeControls,describeImageDifference,describePairPlacement,assertCandidateScene} from './uniform-list-pair-comparator.mjs';
const directory=resolve(process.argv[2]||'_build/uniform-list-pair-evidence');
const rustDirectory=resolve(process.argv[3]||'_build/uniform-list-oracle-evidence');
const coreDirectory=resolve(process.argv[4]||'_sources/core');
await mkdir(directory,{recursive:true});
const verification={status:'failed',conformance:'not_claimed',comparison:'not_run'};
try {
  assert(process.argv.length===5,'Usage: candidate-evidence rust-evidence exact-core-source');
  const git=args=>{const p=spawnSync('git',args,{encoding:'utf8'});assert.equal(p.status,0,p.stderr);return p.stdout.trim();};
  const checkout={revision:git(['rev-parse','HEAD']),tree:git(['rev-parse','HEAD^{tree}']),
    trackedDirty:git(['status','--porcelain','--untracked-files=no'])!=='',catalogBytes:await readFile(resolve('web/examples.json'))};
  const rustBytes=await readFile(join(rustDirectory,'uniform-list-rust-result-dpr1.json'));
  const moonBytes=await readFile(join(directory,'uniform-list-moonbit-result-dpr1.json'));
  const rust=JSON.parse(rustBytes),moon=JSON.parse(moonBytes);
  verification.inputs={rust:{file:'uniform-list-rust-result-dpr1.json',sha256:sha256(rustBytes)},
    moonbit:{file:'uniform-list-moonbit-result-dpr1.json',sha256:sha256(moonBytes)}};
  validateReport(rust,'rust');assertCurrentBuild(rust,{...checkout,catalogBytes:await readFile(resolve('web/tests/fixtures/uniform-list-rust-only-catalog-4b4a7047.json'))});
  assert.equal(moon.build.lab_revision,checkout.revision);assert.equal(moon.build.lab_tree,checkout.tree);assert.equal(checkout.trackedDirty,false);
  assert.equal(moon.build.files['inputs/current-catalog.json'],sha256(checkout.catalogBytes));
  candidateProvenance(moon.build);
  assert.notEqual(moon.capture_session,rust.capture_session,'Independent runtime sessions');
  assert.equal(moon.rust_input.report_sha256,sha256(rustBytes));assert.equal(moon.rust_input.capture_session,rust.capture_session);
  assert.equal(moon.rust_input.initial_png_sha256,rust.captures.initial.png_sha256);
  const rustFiles=await loadEvidence(rustDirectory,rust);verification.rust=verifyBehavior(rust,rustFiles);
  const geometry=discoverGeometry(rustFiles.images.initial);
  const moonFiles=await loadCandidateEvidence(directory,moon,geometry);
  verification.core=verifyCoreSource(moon,moonFiles,coreDirectory);
  verification.measurements={rust:geometry,moonbit:moonFiles.geometry};
  verification.raster_differences=Object.fromEntries(Object.keys(rustFiles.images).map(name=>[name,
    describeImageDifference(rustFiles.images[name],moonFiles.images[name])]));
  verification.glyph_placement=describePairPlacement(rustFiles.images,moonFiles.images);
  // Preserve descriptive discrepancies even when the strict placement predicate fails.
  const strict={profile:'uniform_list_exact_glyph_envelope_v1',status:'failed',conformance:'not_claimed',
    glyph_placement:verification.glyph_placement,raster_differences:verification.raster_differences};
  try {
    strict.result=comparePairImages(rustFiles.images,moonFiles.images);
    assert.deepEqual(comparePairImages(rustFiles.stableImages,moonFiles.stableImages),strict.result);
    strict.status='exact_envelopes_matched';
  } catch(error) {strict.failure=error.stack;}
  // Keep the original strict failure as its own immutable artifact. Its status
  // is never replaced by the separately scoped bounded result below.
  const strictBytes=Buffer.from(JSON.stringify(strict,null,2)+'\n');
  let strictFile='uniform-list-strict-envelope-result.json';
  try{await writeFile(join(directory,strictFile),strictBytes,{flag:'wx'});}
  catch(error){if(error.code!=='EEXIST')throw error;strictFile=`uniform-list-strict-envelope-recheck-${Date.now()}.json`;
    await writeFile(join(directory,strictFile),strictBytes,{flag:'wx'});}
  verification.strict_envelope_comparison={...strict,file:strictFile,sha256:sha256(strictBytes)};
  const pair=compareBoundedPlacement(rustFiles.images,moonFiles.images);
  assert.deepEqual(compareBoundedPlacement(rustFiles.stableImages,moonFiles.stableImages),pair,'Both original independent sample sets');
  verification.bounded_pair=pair;verification.negative_controls=[...boundedNegativeControls(rustFiles.images,moonFiles.images),
    ...profileNegativeControls(moonFiles.images,moonFiles.geometry,moon)];
  const reject=(name,run)=>{assert.throws(run,name);verification.negative_controls.push({name,rejected:true,kind:'corrupted_evidence_sensitivity_not_executed_mutant'});};
  for(const [name,mutate] of [['local_override',x=>x.qualification='unqualified_local_override'],
    ['wrong_core_pin',x=>x.candidate.revision='0'.repeat(40)],['dirty_core',x=>x.candidate_tracked_or_untracked_dirty=true],
    ['wrong_font',x=>x.files['moonbit/IBMPlexSans-Regular.ttf']='0'.repeat(64)]]) {
    const changed=structuredClone(moon.build);mutate(changed);reject(name,()=>candidateProvenance(changed));
  }
  const initial=moonFiles.scenes.initial.observation.frame;
  for(const [name,mutate] of [['missing_candidate_clip',x=>x.snapshot.clip_chains=[]],
    ['candidate_wrong_row_id',x=>x.uniform_list.rows[0].id++],
    ['candidate_wrong_range',x=>x.uniform_list.range[0]++],
    ['candidate_offset_reset',x=>x.uniform_list.offset++],
    ['candidate_wrong_maximum',x=>x.uniform_list.max_offset--],
    ['candidate_wrong_glyph_identity',x=>x.snapshot.items[1].text='Z'],
    ['candidate_wrong_glyph_clip',x=>x.snapshot.items[1].clip_chain_id=null],['candidate_visible_only_extent',x=>x.uniform_list.content_height=300],
    ['candidate_anchor_shift',x=>x.snapshot.items[1].bounds.x++],
    ['candidate_glyph_origin_shift',x=>x.snapshot.items[1].text_origin.x++],
    ['candidate_duplicated_glyph',x=>x.snapshot.items.push(x.snapshot.items[1])],
    ['candidate_missing_glyph',x=>x.snapshot.items.splice(1,1)],
    ['candidate_reordered_glyph',x=>{[x.snapshot.items[1],x.snapshot.items[2]]=[x.snapshot.items[2],x.snapshot.items[1]]}],['candidate_eager_factory_trace',x=>x.uniform_list.factory_calls[2].end=50]]) {
    const changed=structuredClone(initial);mutate(changed);reject(name,()=>assertCandidateScene(changed,moonFiles.geometry,0,moonFiles.scenes.initial.observation.textWidth));
  }
  Object.assign(verification,{status:pair.status,comparison:'bounded_placement_scroll_clip_with_separate_strict_envelope_result',
    candidate:moon.build.candidate,upstream:moon.build.profile.upstream,current_checkout:checkout});
  // Avoid serializing entire current catalog Buffer as an invented observed source.
  verification.current_checkout={revision:checkout.revision,tree:checkout.tree,tracked_dirty:false,catalog_sha256:sha256(checkout.catalogBytes)};
  console.log(`VERIFIED: independent bounded placement/scroll/clip only. Strict glyph-envelope result: ${strict.status}; ${pair.typography.right_edge_differences.filter(row=>row.delta!==0).length} rows have horizontal-support differences. No full-image/AA/OCR/native or Rust laziness/click claim.`);
}catch(error){verification.failure=error.stack;process.exitCode=1;console.error(`FAIL: uniform-list actual browser pair: ${error.message}`);}
finally {
  const bytes=JSON.stringify(verification,null,2)+'\n';
  try{await writeFile(join(directory,'uniform-list-pair-verification.json'),bytes,{flag:'wx'});}
  catch(error){if(error.code!=='EEXIST')throw error;await writeFile(join(directory,`uniform-list-pair-verification-recheck-${Date.now()}.json`),bytes,{flag:'wx'});}
}
