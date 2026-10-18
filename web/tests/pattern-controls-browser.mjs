// Require specific rejection of separately compiled faults, never a generic crash.
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
assert.equal(process.argv.length,6,'Usage: rust-site baseline-moonbit-site compiled-controls-directory fresh-evidence-directory');
const [rust,baseline,controls,out]=process.argv.slice(2).map(p=>resolve(p));await mkdir(out,{recursive:false});
const checks=[];
for(const id of ['wrong_interval','wrong_phase','wrong_color','missing_row','missing_runtime']){
 const evidence=join(out,id),site=id==='missing_runtime'?baseline:join(controls,id);
 const env={...process.env,...(id==='missing_runtime'?{PATTERN_BLOCK_RUNTIME:'1'}:{PATTERN_EXPECT_CONTROL:id})};
 const run=spawnSync(process.execPath,[new URL('./pattern-pair-browser.mjs',import.meta.url).pathname,rust,site,evidence],{env,encoding:'utf8'});
 await writeFile(join(out,`${id}.log`),(run.stdout||'')+(run.stderr||''));assert.notEqual(run.status,0,`${id}: fault unexpectedly passed`);
 const report=JSON.parse(await readFile(join(evidence,'pattern-pair-result.json')));
 assert.equal(report.status,'failed');
 if(id==='missing_runtime'){
  assert.equal(report.stage,'moonbit_capture');
  assert(report.captures.moonbit.errors.some(e=>/pattern\.mjs.*ERR_FAILED/.test(e)),'missing runtime must fail its actual executable request');
 }else{
  assert.equal(report.stage,'comparison',`${id}: setup/runtime failure is not a qualified visual negative control`);
  const reason={wrong_interval:'red4',wrong_phase:'red1',wrong_color:'large_green',missing_row:'short_yellow'}[id];
  assert(report.failure.includes(`${reason}: RGB/alpha/interval/phase mismatch`),`${id}: expected named source-region visual rejection`);
 }
 checks.push({id,status:'expected_rejection',stage:report.stage});
}
await writeFile(join(out,'pattern-controls-result.json'),JSON.stringify({status:'all_expected_rejections',checks},null,2)+'\n');
console.log(JSON.stringify(checks,null,2));
