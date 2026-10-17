import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,symlink,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {candidateProvenance,mutatedSource,strictLocalReader,assertSuccessfulBaselineSummary} from './gradient-pair-evidence.mjs';
import {sha256} from './gradient-comparator.mjs';
test('unqualified/absent core pin can never qualify a build',()=>{for(const b of [{},{schema:1,qualification:'unqualified_local_override'},{executed_control:'wrong_geometry'}])assert.throws(()=>candidateProvenance(b));});
test('exact core mutation requires anchored count and modifies compiled bytes',()=>{const m={find:'let green = 0.5',replace:'let green = 1.0',occurrences:1};assert.equal(mutatedSource(Buffer.from('let green = 0.5\n'),m).toString(),'let green = 1.0\n');assert.throws(()=>mutatedSource(Buffer.from('no anchor'),m));assert.throws(()=>mutatedSource(Buffer.from('let green = 0.5; let green = 0.5'),m));});
test('forged ordinary success and a control baseline never qualify controls',()=>{for(const summary of [{status:'passed'},{status:'bounded_gradient_sample_pair_verified',comparison:'bounded_original_gradient_sample_pair',expected_control:'wrong_geometry'}])assert.throws(()=>assertSuccessfulBaselineSummary(summary,{},Buffer.from('{}'),Buffer.from('{}'),{}));});
test('strict evidence reader rejects bytes, links and alias reuse',async()=>{const dir=await mkdtemp(join(tmpdir(),'gradient-pair-reader-'));try{const bytes=Buffer.from('actual evidence');await writeFile(join(dir,'a'),bytes);const reader=await strictLocalReader(dir);await reader('a',sha256(bytes));await assert.rejects(()=>reader('a',sha256(bytes)));await symlink(join(dir,'a'),join(dir,'link'));await assert.rejects(()=>(async()=>{const r=await strictLocalReader(dir);return r('link',sha256(bytes));})());await assert.rejects(()=>(async()=>{const r=await strictLocalReader(dir);return r('a','0'.repeat(64));})());await assert.rejects(()=>reader('../a',sha256(bytes)));}finally{await rm(dir,{recursive:true,force:true});}});

// Positive synthetic state images exercise the end-to-end comparator adapter,
// not just malformed-report early exits. These are not runtime evidence.
import {candidateSourceBehavior,recomputeOrdinaryBaseline} from './gradient-pair-evidence.mjs';
import {comparePairImages} from './gradient-pair-comparator.mjs';
import {rasterSourcePolygon} from './gradient-candidate-polygon-fixture.mjs';
function syntheticStates(){
 const make=(width,height,changed)=>{const image={width,height,data:new Uint8Array(width*height*4).fill(255)};
  const fill=(x,y,w,h,c)=>{for(let j=y;j<y+h;j++)for(let i=x;i<x+w;i++)image.data.set(c,(j*width+i)*4);};
  fill(width-80,16,64,28,[0,0,0,255]);let y=60,index=0;
  for(const count of [2,4,4,1,1,2]){const w=Math.floor((width-32-12*(count-1))/count);for(let i=0;i<count;i++){fill(16+i*(w+12),y,w,40,index===0?[255,0,0,255]:index===1?[0,0,255,255]:changed?[0,0,255,255]:[255,0,0,255]);index++;}y+=60;}
  const polygon=rasterSourcePolygon(width,height).image;for(let i=0;i<polygon.data.length;i+=4)if(polygon.data[i+1]===0)image.data.set(changed?[0,0,255,255]:[255,0,0,255],i);return image;
 };
 const wide=make(960,600,false),tall=make(600,960,false);
 return {wideSrgb:wide,wideOklab:make(960,600,true),wideRestored:wide,tallSrgb:tall,tallOklab:make(600,960,true),tallRestored:tall,wideAgain:wide};
}
test('valid synthetic seven-state baseline traverses candidate behavior and ordinary recomputation',()=>{const images=syntheticStates(),files={images,stableImages:images};const behavior=candidateSourceBehavior({runtime:'moonbit',operations:[]},files);assert.equal(behavior.backend,'candidate_canvas2d_core_rgba_transport');const pair=comparePairImages(images,images);assert.deepEqual(recomputeOrdinaryBaseline(files,files,{pair}),pair);});

import {assertCandidateBackend} from './gradient-pair-evidence.mjs';
import {validateReport as validateRustReport} from './gradient-runtime-evidence.mjs';
test('candidate Canvas facts cannot qualify unchanged Rust backend/oracle',()=>{const backend={kind:'candidate_canvas2d_core_rgba_transport',visible_canvases:[{canvas_id:1}],events:[{kind:'getContext',canvas_id:1,requested:'2d',returned:true}]};assertCandidateBackend(backend);assert.throws(()=>validateRustReport({runtime:'moonbit',status:'moonbit_profile_captured',backend}));assert.throws(()=>assertCandidateBackend({...backend,kind:'webgl_visible_canvas_context_returned'}));assert.throws(()=>assertCandidateBackend({...backend,events:[{kind:'getContext',canvas_id:1,requested:'webgl2',returned:true}]}));assert.throws(()=>candidateSourceBehavior({runtime:'rust',operations:[]},{images:{}}));});

import {readFileSync} from 'node:fs';
import {PAIR_SUITE_INPUTS,assertCandidateSuiteInputInventory,evidenceFilename} from './gradient-pair-evidence.mjs';
test('candidate geometry adapter is mandatory and tamper-evident in retained suite inputs',()=>{
 const path='web/tests/gradient-candidate-behavior.mjs';assert(PAIR_SUITE_INPUTS.includes(path));
 const entries=PAIR_SUITE_INPUTS.map(path=>({path,file:evidenceFilename('moonbit','suite',path),sha256:sha256(readFileSync(new URL('../../'+path,import.meta.url)))}));
 assert.doesNotThrow(()=>assertCandidateSuiteInputInventory(entries));
 assert.throws(()=>assertCandidateSuiteInputInventory(entries.filter(e=>e.path!==path)),/mandatory candidate suite input/);
 const tampered=structuredClone(entries);tampered.find(e=>e.path===path).sha256=sha256(Buffer.from('changed candidate geometry predicate'));
 assert.throws(()=>assertCandidateSuiteInputInventory(tampered),/Current candidate suite bytes/);
});
