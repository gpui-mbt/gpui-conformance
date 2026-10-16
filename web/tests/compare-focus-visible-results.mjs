// Decode and re-evaluate the complete retained profiles from both renderers.
// A failure always retains JSON diagnostics, even for missing/invalid inputs.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {compareFocusVisibleBehavior,loadFocusVisibleEvidence,validateFocusVisibleEvidence,assertCurrentFocusVisibleBuild}
  from './focus-visible-pair-comparator.mjs';
const args=process.argv.slice(2),directory=resolve(args.find(arg=>!arg.startsWith('--'))||'_build/browser-example-evidence');
const report={status:'failed',comparison:'not_established',scope:'Independent retained Rust/MoonBit focus behavior at 800x600 DPR1',inputs:{}};
await mkdir(directory,{recursive:true});
try {
  assert(args.length<=1&&!args.some(arg=>arg.startsWith('--')),'Only an evidence directory and the fixed DPR1 profile are supported');
  const version=spawnSync('python3',['-c','import PIL; print(PIL.__version__)'],{encoding:'utf8'});
  if(version.error)throw version.error;assert.equal(version.status,0,`Pillow required: ${version.stderr}`);
  report.png_decoder={implementation:'Pillow',version:version.stdout.trim(),dimensions:'Actual decoded PNG dimensions'};
  const sides={},retained={};
  for(const runtime of ['rust','moonbit']) {
    const file=`focus-visible-${runtime}-result-dpr1.json`,bytes=await readFile(join(directory,file));
    report.inputs[runtime]={file,sha256:createHash('sha256').update(bytes).digest('hex')};
    sides[runtime]=JSON.parse(bytes);
    report.inputs[runtime].integrity=validateFocusVisibleEvidence(sides[runtime],runtime);
    const git=args=>{const value=spawnSync('git',args,{encoding:'utf8'});if(value.error)throw value.error;
      assert.equal(value.status,0,`Current checkout provenance: ${value.stderr}`);return value.stdout.trim();};
    const checkout={revision:git(['rev-parse','HEAD']),trackedDirty:git(['status','--porcelain','--untracked-files=no'])!=='',
      catalogBytes:await readFile(resolve('web/examples.json'))};
    assertCurrentFocusVisibleBuild(sides[runtime],checkout);
    report.current_checkout={revision:checkout.revision,tracked_dirty:false,catalog_sha256:sides[runtime].catalog_sha256};
    retained[runtime]=await loadFocusVisibleEvidence(directory,sides[runtime]);
    report.inputs[runtime].retained_files='Manifest, catalog, actual runtime responses, and both stable PNG samples independently hashed and decoded';
  }
  Object.assign(report,compareFocusVisibleBehavior(sides.rust,sides.moonbit,retained));
  console.log('PASS: actual Rust/MoonBit focus behavior agrees within the retained fixed profile. Cross-renderer text, full-image, and native parity remain UNVERIFIED.');
} catch(error) {
  report.status='failed';report.failure=error.stack;process.exitCode=1;
  console.error(`FAIL: focus-visible pair: ${error.message}`);
} finally {
  await writeFile(join(directory,'focus-visible-pair-result-dpr1.json'),JSON.stringify(report,null,2)+'\n');
}
