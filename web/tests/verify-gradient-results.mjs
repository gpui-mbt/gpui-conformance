// Re-read every retained original artifact against this exact committed suite.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {sha256,assertCurrentBuild} from './gradient-comparator.mjs';
import {SUITE_INPUTS,validateReport,loadEvidence,verifyBehavior,negativeControls} from './gradient-runtime-evidence.mjs';
const directory=resolve(process.argv[2]||'_build/gradient-oracle-evidence');await mkdir(directory,{recursive:true});
const verification={status:'failed',runtime:'rust',candidate:'not_implemented',comparison:'not_run',conformance:'not_claimed'};
try {
 assert(process.argv.length<=3,'Only original evidence directory accepted');
 const git=args=>{const r=spawnSync('git',args,{encoding:'utf8',timeout:10000,maxBuffer:1024*1024});if(r.error)throw r.error;assert.equal(r.status,0,r.stderr);return r.stdout.trim();};
 const checkout={revision:git(['rev-parse','HEAD']),tree:git(['rev-parse','HEAD^{tree}']),trackedDirty:git(['status','--porcelain','--untracked-files=no'])!=='',catalogBytes:await readFile(resolve('web/tests/fixtures/gradient-rust-only-catalog.json'))};
 for(const path of SUITE_INPUTS){const r=spawnSync('git',['show','HEAD:'+path],{timeout:10000,maxBuffer:8*1024*1024});if(r.error)throw r.error;assert.equal(r.status,0,`${path} must be committed at HEAD`);assert.deepEqual(await readFile(resolve(path)),r.stdout);}
 const file='gradient-rust-result-dpr1.json',bytes=await readFile(join(directory,file)),report=JSON.parse(bytes);
 verification.input={file,sha256:sha256(bytes)};validateReport(report);verification.checkout=assertCurrentBuild(report,checkout);
 verification.checkout_negative_controls=[];
 for(const [name,change] of [['revision',{revision:'0'.repeat(40)}],['tree',{tree:'0'.repeat(40)}],['dirty',{trackedDirty:true}],['catalog',{catalogBytes:Buffer.from('{}')}]]){assert.throws(()=>assertCurrentBuild(report,{...checkout,...change}));verification.checkout_negative_controls.push({name,rejected:true,kind:'synthetic_corrupted_evidence'});}
 const retained=await loadEvidence(directory,report);Object.assign(verification,verifyBehavior(report,retained));verification.evidence_negative_controls=negativeControls(report,retained);
 // Exercise the strict original-PNG decoder on actual retained corruption.
 const png=await readFile(join(directory,report.captures.wideSrgb.file));const corrupt=Buffer.from(png);corrupt[Math.floor(corrupt.length/2)]^=1;
 const {decodePng}=await import('./gradient-comparator.mjs');assert.throws(()=>decodePng(corrupt));verification.original_png_corruption_rejected=true;
 console.log('VERIFIED bounded unchanged gradient structure and real-input restoration. Color residuals remain observations; no MoonBit, native or exact-color parity claim.');
}catch(error){verification.failure=error.stack;process.exitCode=1;console.error(`FAIL: gradient original evidence: ${error.message}`);}
finally{try{await writeFile(join(directory,'gradient-rust-verification-dpr1.json'),JSON.stringify(verification,null,2)+'\n',{flag:'wx'});}catch(error){if(error.code!=='EEXIST')throw error;await writeFile(join(directory,`gradient-rust-verification-recheck-${Date.now()}.json`),JSON.stringify(verification,null,2)+'\n',{flag:'wx'});}}
