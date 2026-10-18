// Current-checkout verification of both independent raw runtime captures.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {sha256} from './drag-drop-comparator.mjs';
import {validateReport,loadEvidence,compareBehavior,assertCurrentBuild} from './drag-drop-pair-comparator.mjs';
const directory=resolve(process.argv[2]||'_build/drag-drop-pair-evidence');await mkdir(directory,{recursive:true});
const verification={status:'failed',comparison:'not_established',conformance:'not_claimed',inputs:{},checkout_negative_controls:[]};
try {
  assert(process.argv.length<=3,'Only an evidence directory is accepted; fixed800x600 DPR1');
  const git=args=>{const result=spawnSync('git',args,{encoding:'utf8',timeout:10000,maxBuffer:1024*1024});
    if(result.error)throw result.error;assert.equal(result.status,0,`Actual current Git context: ${result.stderr?.slice(0,2048)}`);return result.stdout.trim();};
  const checkout={revision:git(['rev-parse','HEAD']),tree:git(['rev-parse','HEAD^{tree}']),
    trackedDirty:git(['status','--porcelain','--untracked-files=no'])!=='',catalogBytes:await readFile(resolve('web/examples.json'))};
  const reports={},retained={};
  for(const runtime of ['rust','moonbit']) {
    const file=`drag-drop-${runtime}-result-dpr1.json`,bytes=await readFile(join(directory,file));
    reports[runtime]=JSON.parse(bytes);verification.inputs[runtime]={file,sha256:sha256(bytes)};
    validateReport(reports[runtime],runtime);verification.current_checkout=assertCurrentBuild(reports[runtime],checkout);
    for(const [name,change] of [['mismatched_historical_revision',{revision:'0'.repeat(40)}],
      ['mismatched_historical_tree',{tree:'0'.repeat(40)}],['dirty_current_checkout',{trackedDirty:true}],
      ['wrong_current_catalog_bytes',{catalogBytes:Buffer.from('{}')}]]) {
      assert.throws(()=>assertCurrentBuild(reports[runtime],{...checkout,...change}),name);
      verification.checkout_negative_controls.push({runtime,name,rejected:true});
    }
    retained[runtime]=await loadEvidence(directory,reports[runtime]);
  }
  Object.assign(verification,compareBehavior(reports.rust,reports.moonbit,retained));
  console.log('PASS: independently decoded actual Rust/MoonBit drag-drop geometry, move-only activation, drag/drop, preview, paint and trusted delivery agree within the fixed source profile. Text/full-image/native parity unverified.');
}catch(error){verification.failure=error.stack;process.exitCode=1;console.error(`FAIL: drag-drop pair: ${error.message}`);}
finally {
  const bytes=JSON.stringify(verification,null,2)+'\n';
  try{await writeFile(join(directory,'drag-drop-pair-result-dpr1.json'),bytes,{flag:'wx'});}
  catch(error){if(error.code!=='EEXIST')throw error;await writeFile(join(directory,`drag-drop-pair-recheck-${Date.now()}.json`),bytes,{flag:'wx'});}
}
