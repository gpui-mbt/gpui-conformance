// Independently reopen original runtime/source/font/input/PNG files. Failure is
// retained verbatim; no tolerance adaptation, screenshot substitution or pass flag inference.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {sha256,discoverGeometry,VIEWPORT_SEQUENCE} from './gradient-comparator.mjs';
import {assertCurrentBuild} from './gradient-comparator.mjs';
import {SUITE_INPUTS,validateReport,loadEvidence,verifyBehavior} from './gradient-runtime-evidence.mjs';
import {PAIR_SUITE_INPUTS,strictLocalReader,candidateProvenance,loadCandidateEvidence,verifyCoreSource,loadQualifiedOrdinaryBaseline,loadPolicyEvidence,candidateSourceBehavior} from './gradient-pair-evidence.mjs';
import {comparePairImages,pairNegativeControls,TOLERANCES,NOT_CLAIMED} from './gradient-pair-comparator.mjs';
import {verifyPolicyImage} from './gradient-policy-contract.mjs';
const directory=resolve(process.argv[2]||'_build/gradient-pair-evidence');
const rustDirectory=resolve(process.argv[3]||'_build/gradient-oracle-evidence');
const coreDirectory=resolve(process.argv[4]||'_sources/core');
const expectedControl=process.argv[5]||null;
const ordinaryDirectory=process.argv[6]?resolve(process.argv[6]):null;
await mkdir(directory,{recursive:true});
const verification={status:'failed',conformance:'not_claimed',comparison:'not_run',expected_control:expectedControl,
  tolerances_physical_pixels:TOLERANCES,not_claimed:NOT_CLAIMED};
try {
  assert(expectedControl?process.argv.length===7:process.argv.length===5,
    'Usage: candidate-evidence rust-evidence exact-core-source [frozen-control-name ordinary-candidate-evidence]; controls require a successful ordinary baseline');
  assert(expectedControl===null||Object.hasOwn(JSON.parse(await readFile('web/pairs/gradient.json')), 'executed_controls') && Object.hasOwn(JSON.parse(await readFile('web/pairs/gradient.json')).executed_controls,expectedControl));
  const git=args=>{const p=spawnSync('git',args,{encoding:'utf8',timeout:10000,maxBuffer:8*1024*1024});assert.equal(p.status,0,p.stderr);return p.stdout.trim();};
  const checkout={revision:git(['rev-parse','HEAD']),tree:git(['rev-parse','HEAD^{tree}']),
    trackedDirty:git(['status','--porcelain','--untracked-files=no'])!=='',catalogBytes:await readFile(resolve('web/examples.json'))};
  for(const path of new Set([...SUITE_INPUTS,...PAIR_SUITE_INPUTS])) {
    const p=spawnSync('git',['show','HEAD:'+path],{timeout:10000,maxBuffer:8*1024*1024});assert.equal(p.status,0,`${path}: committed source required`);
    assert.deepEqual(await readFile(resolve(path)),p.stdout,`${path}: actual current source equals clean committed HEAD`);
  }
  verification.suite_inputs_verified_against_head=true;
  const rustBytes=await readFile(join(rustDirectory,'gradient-rust-result-dpr1.json'));
  const moonBytes=await readFile(join(directory,'gradient-moonbit-result-dpr1.json'));
  await (await strictLocalReader(rustDirectory))('gradient-rust-result-dpr1.json',sha256(rustBytes));
  await (await strictLocalReader(directory))('gradient-moonbit-result-dpr1.json',sha256(moonBytes));
  const rust=JSON.parse(rustBytes),moon=JSON.parse(moonBytes);
  verification.inputs={rust:{file:'gradient-rust-result-dpr1.json',sha256:sha256(rustBytes)},
    moonbit:{file:'gradient-moonbit-result-dpr1.json',sha256:sha256(moonBytes)}};
  validateReport(rust,'rust');assertCurrentBuild(rust,{...checkout,catalogBytes:await readFile(resolve('web/tests/fixtures/gradient-rust-only-catalog.json'))});
  assert.equal(moon.build.lab_revision,checkout.revision);assert.equal(moon.build.lab_tree,checkout.tree);assert.equal(checkout.trackedDirty,false);
  assert.equal(moon.build.files['inputs/current-catalog.json'],sha256(checkout.catalogBytes));
  candidateProvenance(moon.build,undefined,expectedControl);
  assert.notEqual(moon.capture_session,rust.capture_session,'Independent runtime sessions');
  assert.notEqual(moon.document_id,rust.document_id,'Independent runtime documents');
  assert.equal(moon.rust_input.report_sha256,sha256(rustBytes));assert.equal(moon.rust_input.capture_session,rust.capture_session);
  assert.equal(moon.rust_input.initial_png_sha256,rust.captures.wideSrgb.attempts.at(-1).png_sha256);
  assert.equal(moon.environment.browser,rust.environment.browser,'Same measured browser version');
  assert.deepEqual(moon.environment.graphics_requested,rust.environment.graphics_requested);
  const rustFiles=await loadEvidence(rustDirectory,rust);verification.rust=verifyBehavior(rust,rustFiles);
  assert.equal(rust.backend.observed,'webgl_visible_canvas_context_returned');
  const visible=new Set(rust.backend.visible_canvases.map(c=>c.canvas_id));
  const selected=rust.backend.events.filter(e=>visible.has(e.canvas_id)&&e.kind==='getContext'&&e.returned&&e.requested==='webgl2');
  assert.equal(selected.length,1,'Exactly observed visible WebGL2 context required');assert.match(selected[0].unmasked_renderer,/SwiftShader/i);assert.equal(rust.backend.formats.length,0,'No inferred WebGPU format');
  const moonFiles=await loadCandidateEvidence(directory,moon,expectedControl);
  verification.core=verifyCoreSource(moon,moonFiles,coreDirectory);
  const policy=await loadPolicyEvidence(join(directory,'policy'),moon,expectedControl);verifyCoreSource(policy.report,policy.files,coreDirectory);verification.policy_input=policy.binding;
  verification.measurements={};
  for(const {name} of VIEWPORT_SEQUENCE) {
    const measurement=verification.measurements[name]={};
    for(const [runtime,files] of [['rust',rustFiles],['moonbit',moonFiles]]) {
      try{measurement[runtime]=discoverGeometry(files.images[name]);}
      catch(error){measurement[runtime]={discovery_failure:error.message};}
    }
  }
  verification.current_checkout={revision:checkout.revision,tree:checkout.tree,tracked_dirty:false,catalog_sha256:sha256(checkout.catalogBytes)};
  verification.candidate=moon.build.candidate;verification.upstream=moon.build.profile.upstream;
  if(expectedControl) {
    verification.ordinary_baseline=await loadQualifiedOrdinaryBaseline(ordinaryDirectory,{rust,rustBytes,rustFiles,coreDirectory,checkout,controlReport:moon});
    const failures=[];
    for(const [a,b] of [[rustFiles.images,moonFiles.images],[rustFiles.stableImages,moonFiles.stableImages]]) {
      let failure;try{comparePairImages(a,b);candidateSourceBehavior(moon,{images:b});verifyPolicyImage(a===rustFiles.images?policy.files.images.policy:policy.files.stableImages.policy);}catch(error){failure=error;}
      assert(failure,'The executed fault must be rejected by the actual raster comparison');
      assert.match(failure.message,/policy |RGB code delta|component .* delta|Exact authored candidate solid|Source|source|colored|gradient|restoration|Gradient|polygon|opaque alpha/,
        'Rejection must concern the executed fault, not provenance/startup/missing files');
      failures.push({message:failure.message,stack:failure.stack});
    }
    verification.executed_control={name:expectedControl,kind:moon.build.mutation.kind,
      status:'executed_fault_rejected',actual_compiled_runtime_sha256:moon.build.files['moonbit/gradient.mjs'],
      actual_compiled_source_sha256:moon.build.files['inputs/mutation-compiled.mbt'],
      actual_capture_count:Object.keys(moon.captures).length,source_diff:moon.build.control_source,mutation:moon.build.mutation,original_comparison_failures:failures};
    verification.status='executed_fault_rejected';verification.comparison='actual_compiled_fault_sensitivity';
  } else {
    const pair=comparePairImages(rustFiles.images,moonFiles.images);
    assert.deepEqual(comparePairImages(rustFiles.stableImages,moonFiles.stableImages),pair,'Both independent original stable sample sets');
    verification.candidate_source_behavior=candidateSourceBehavior(moon,moonFiles);verification.pair=pair;verification.policy=verifyPolicyImage(policy.files.images.policy);assert.deepEqual(verifyPolicyImage(policy.files.stableImages.policy),verification.policy);verification.negative_controls=pairNegativeControls(rustFiles.images,moonFiles.images);
    const reject=(name,run)=>{assert.throws(run,name);verification.negative_controls.push({name,rejected:true,kind:'corrupted_report_sensitivity_not_executed_mutant'});};
    for(const [name,mutate] of [['local_override',x=>x.qualification='unqualified_local_override'],
      ['wrong_core_pin',x=>x.candidate.revision='0'.repeat(40)],['dirty_core',x=>x.candidate_tracked_or_untracked_dirty=true],
      ['wrong_font',x=>x.files['moonbit/IBMPlexSans-Regular.ttf']='0'.repeat(64)],['hidden_control',x=>x.executed_control='wrong_geometry']]) {
      const changed=structuredClone(moon.build);mutate(changed);reject(name,()=>candidateProvenance(changed));
    }
    verification.status=pair.status;verification.comparison='bounded_original_gradient_sample_pair';
  }
  console.log(`VERIFIED: gradient ${verification.status}; no full-image, text, decoration or native parity claim.`);
}catch(error){verification.failure=error.stack;process.exitCode=1;console.error(`FAIL: gradient actual browser pair: ${error.message}`);}
finally {
  const bytes=JSON.stringify(verification,null,2)+'\n';
  try{await writeFile(join(directory,'gradient-pair-verification.json'),bytes,{flag:'wx'});}
  catch(error){if(error.code!=='EEXIST')throw error;await writeFile(join(directory,`gradient-pair-verification-recheck-${Date.now()}.json`),bytes,{flag:'wx'});}
}
