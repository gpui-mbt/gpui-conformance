// Verify current-checkout provenance and original source-only runtime evidence.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {sha256} from './grid-layout-comparator.mjs';
import {SUITE_INPUTS,validateReport,loadEvidence,verifyBehavior,assertCurrentBuild} from './grid-layout-runtime-evidence.mjs';
const directory=resolve(process.argv[2]||'_build/grid-layout-oracle-evidence');await mkdir(directory,{recursive:true});
const verification={status:'failed',runtime:'rust',candidate:'not_implemented',comparison:'not_run',conformance:'not_claimed',checkout_negative_controls:[]};
try {
  assert(process.argv.length<=3,'Only an evidence directory is accepted; 399/400/401/500x500 DPR1');
  const git=args=>{const result=spawnSync('git',args,{encoding:'utf8',timeout:10000,maxBuffer:1024*1024});
    if(result.error)throw result.error;assert.equal(result.status,0,`Actual current Git context: ${result.stderr?.slice(0,2048)}`);return result.stdout.trim();};
  const checkout={revision:git(['rev-parse','HEAD']),tree:git(['rev-parse','HEAD^{tree}']),
    trackedDirty:git(['status','--porcelain','--untracked-files=no'])!=='',catalogBytes:await readFile(resolve('web/tests/fixtures/grid-layout-rust-only-catalog-b0781104.json'))};
  for(const path of SUITE_INPUTS) {
    const committed=spawnSync('git',['show','HEAD:'+path],{timeout:10000,maxBuffer:8*1024*1024});
    if(committed.error)throw committed.error;
    assert.equal(committed.status,0,`${path}: required input must be committed at HEAD`);
    assert.deepEqual(await readFile(resolve(path)),committed.stdout,`${path}: current source bytes must equal committed HEAD`);
  }
  verification.suite_inputs_verified_against_head=true;
  const file='grid-layout-rust-result-dpr1.json',bytes=await readFile(join(directory,file)),report=JSON.parse(bytes);
  verification.input={file,sha256:sha256(bytes)};validateReport(report,'rust');
  verification.current_checkout=assertCurrentBuild(report,checkout);
  for(const [name,change] of [['mismatched_historical_revision',{revision:'0'.repeat(40)}],
    ['mismatched_historical_tree',{tree:'0'.repeat(40)}],['dirty_current_checkout',{trackedDirty:true}],
    ['wrong_current_catalog_bytes',{catalogBytes:Buffer.from('{}')}]]) {
    assert.throws(()=>assertCurrentBuild(report,{...checkout,...change}),name);
    verification.checkout_negative_controls.push({name,rejected:true,kind:'corrupted_evidence_sensitivity_not_executed_mutant'});
  }
  const retained=await loadEvidence(directory,report);Object.assign(verification,verifyBehavior(report,retained));
  console.log('VERIFIED: unchanged Rust grid_layout original solid-color grid/span/gap/threshold profile and actual same-document viewport resize restoration. No candidate, text, dash, radius, shadow, full-image or native claim.');
}catch(error){verification.failure=error.stack;process.exitCode=1;console.error(`FAIL: grid-layout source profile: ${error.message}`);}
finally {
  const bytes=JSON.stringify(verification,null,2)+'\n';
  try{await writeFile(join(directory,'grid-layout-rust-verification-dpr1.json'),bytes,{flag:'wx'});}
  catch(error){if(error.code!=='EEXIST')throw error;await writeFile(join(directory,`grid-layout-rust-verification-recheck-${Date.now()}.json`),bytes,{flag:'wx'});}
}
