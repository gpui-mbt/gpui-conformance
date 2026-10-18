// Current-checkout verification of both independent raw runtime captures.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {sha256} from './tab-stop-comparator.mjs';
import {validateReport,loadEvidence,compareBehavior,assertCurrentTabStopBuild} from './tab-stop-pair-comparator.mjs';
const directory=resolve(process.argv[2]||'_build/tab-stop-pair-evidence');await mkdir(directory,{recursive:true});
const verification={status:'failed',comparison:'not_established',conformance:'not_claimed',inputs:{}};
try {
  assert(process.argv.length<=3,'Only an evidence directory is accepted; fixed800x600 DPR1');
  const git=args=>{const result=spawnSync('git',args,{encoding:'utf8',timeout:10000,maxBuffer:1024*1024});
    if(result.error)throw result.error;assert.equal(result.status,0,`Actual current Git context: ${result.stderr?.slice(0,2048)}`);return result.stdout.trim();};
  const checkout={revision:git(['rev-parse','HEAD']),tree:git(['rev-parse','HEAD^{tree}']),
    trackedDirty:git(['status','--porcelain','--untracked-files=no'])!=='',catalogBytes:await readFile(resolve('web/examples.json'))};
  const reports={},retained={};
  for(const runtime of ['rust','moonbit']) {
    const file=`tab-stop-${runtime}-result-dpr1.json`,bytes=await readFile(join(directory,file));
    reports[runtime]=JSON.parse(bytes);verification.inputs[runtime]={file,sha256:sha256(bytes)};
    validateReport(reports[runtime],runtime);verification.current_checkout=assertCurrentTabStopBuild(reports[runtime],checkout);
    retained[runtime]=await loadEvidence(directory,reports[runtime]);
  }
  Object.assign(verification,compareBehavior(reports.rust,reports.moonbit,retained));
  console.log('PASS: independently decoded actual Rust/MoonBit tab-stop geometry, traversal, messages, paint and moving-edge behavior agree within the fixed source profile. Text/full-image/native parity unverified.');
}catch(error){verification.failure=error.stack;process.exitCode=1;console.error(`FAIL: tab-stop pair: ${error.message}`);}
finally {await writeFile(join(directory,'tab-stop-pair-result-dpr1.json'),JSON.stringify(verification,null,2)+'\n');}
