// Frozen before any candidate execution. This is a deliberately bounded sample
// budget, NOT a proved universal f32 error bound or a whole-image equivalence test.
import assert from 'node:assert/strict';
import {VIEWPORT_SEQUENCE,sourceStructure,pixel,buttonTarget} from './gradient-comparator.mjs';
import {verifyBehavior} from './gradient-runtime-evidence.mjs';
export const PAIR_PROFILE='gradient_actual_browser_pair_v1';
export const TOLERANCES=Object.freeze({component_edge:2});
export const COLOR_BUDGET=Object.freeze({rgb_code:2,opaque_alpha:0});
export const NOT_CLAIMED=Object.freeze(['Full-image equality','Text/shaping/glyph/typography parity','Rounded or polygon antialias-edge parity','Universal equal-stop GPU semantics','Native/Metal or physical GPU parity','Other browsers, GPU backends, viewport/DPR profiles','General gradient conformance']);
export function compareChannels(a,b,label) {
 assert.equal(a.length,4);assert.equal(b.length,4);
 assert.equal(a[3],255,`${label}: original opaque alpha`);assert.equal(b[3],255,`${label}: candidate opaque alpha`);
 const delta=b.map((v,i)=>v-a[i]);
 for(let i=0;i<3;i++)assert(Math.abs(delta[i])<=COLOR_BUDGET.rgb_code,`${label}: RGB code delta ${delta[i]} exceeds predeclared 2-code budget`);
 return {rust:a,moonbit:b,delta,exact:a.every((v,i)=>v===b[i])};
}
export function compareBounds(a,b,label) {
 const edges=r=>({left:r.x,top:r.y,right:r.x+r.width,bottom:r.y+r.height});const x=edges(a),y=edges(b),delta={};
 for(const edge of Object.keys(x)){delta[edge]=y[edge]-x[edge];assert(Math.abs(delta[edge])<=TOLERANCES.component_edge,`${label}: component ${edge} delta ${delta[edge]} exceeds predeclared 2px bound`);}
 return {rust:a,moonbit:b,edge_deltas:delta};
}
export function comparePairImages(rustImages,moonImages) {
 const states={};
 for(const state of VIEWPORT_SEQUENCE) {
  const rust=rustImages[state.name],moon=moonImages[state.name];assert(rust&&moon,'Every source state required');
  assert.equal(rust.width,state.width);assert.equal(rust.height,state.height);assert.equal(moon.width,state.width);assert.equal(moon.height,state.height);
  const a=sourceStructure(rust),b=sourceStructure(moon),components=[];
  for(let i=0;i<15;i++) {
   const geometry=compareBounds(a.colored[i],b.colored[i],`${state.name}/${i}`),samples=[];
   if(i<2) {
    // Away from centered label and corner coverage. Original authored solids
    // are exact, rather than receiving the gradient arithmetic budget.
    const x=Math.max(a.colored[i].x,b.colored[i].x)+Math.floor(Math.min(a.colored[i].width,b.colored[i].width)/4);
    const y=Math.max(a.colored[i].y,b.colored[i].y)+Math.floor(Math.min(a.colored[i].height,b.colored[i].height)/4);
    const expected=i===0?[255,0,0,255]:[0,0,255,255];
    assert.deepEqual(pixel(rust,x,y),expected,'Exact authored original solid');assert.deepEqual(pixel(moon,x,y),expected,'Exact authored candidate solid');samples.push({position:[x,y],expected,exact:true});
   } else {
    const left=Math.max(a.colored[i].x,b.colored[i].x),top=Math.max(a.colored[i].y,b.colored[i].y);
    const right=Math.min(a.colored[i].x+a.colored[i].width,b.colored[i].x+b.colored[i].width),bottom=Math.min(a.colored[i].y+a.colored[i].height,b.colored[i].y+b.colored[i].height);
    assert(right-left>8&&bottom-top>8,'Substantial common interior');
    for(const fy of [.25,.5,.75])for(const fx of [.25,.5,.75]) {
     const x=Math.floor(left+(right-left)*fx),y=Math.floor(top+(bottom-top)*fy);
     // The discontinuity has no finite cross-runtime positional error budget.
     // Its ambiguous central samples are retained as observations, not erased;
     // exact center-start is separately checked in the matched161px diagnostic.
     if(i===12&&fx===.5){samples.push({position:[x,y],rust:pixel(rust,x,y),moonbit:pixel(moon,x,y),status:'equal_stop_center_alignment_unqualified_use_matched161_probe'});continue;}
     samples.push({position:[x,y],...compareChannels(pixel(rust,x,y),pixel(moon,x,y),`${state.name}/${i}/${x},${y}`)});
    }
   }
   components.push({index:i,geometry,samples});
  }
  states[state.name]={components,button:compareBounds(a.button,b.button,state.name+'/button')};
 }
 for(const images of [rustImages,moonImages]) {
  for(const phase of ['wide','tall'])assert.deepEqual(images[phase+'Srgb'].data,images[phase+'Restored'].data,'Exact complete same-runtime restoration');
  assert.deepEqual(images.wideSrgb.data,images.wideAgain.data,'Exact complete viewport round-trip restoration');
 }
 return {status:'bounded_gradient_sample_pair_verified',profile:PAIR_PROFILE,tolerances_physical_pixels:TOLERANCES,tolerances_unorm8:COLOR_BUDGET,states,conformance:'not_claimed',not_claimed:NOT_CLAIMED};
}
export function verifyMatched161Probe(image) {
 assert.equal(image.width,161);assert.equal(image.height,1);
 for(let x=0;x<161;x++)assert.deepEqual(pixel(image,x,0),x<=80?[255,0,0,255]:[0,0,255,255],`Explicit equal-stop start-at-boundary policy x=${x}`);
 return {status:'exact_explicit_core_policy',left:pixel(image,0,0),center:pixel(image,80,0),right:pixel(image,160,0),backend_claim:'Matches observed original SwiftShader WebGL2 diagnostic only; not universal GPU semantics'};
}
export function pairNegativeControls(rust,moon) {
 comparePairImages(rust,moon);const controls=[];
 for(const [name,run] of [['rgb_budget_plus_one',()=>compareChannels([100,100,100,255],[103,100,100,255],'synthetic')],['geometry_budget_plus_one',()=>compareBounds({x:0,y:0,width:10,height:10},{x:3,y:0,width:10,height:10},'synthetic')],['opaque_alpha',()=>compareChannels([100,100,100,255],[100,100,100,254],'synthetic')]]){assert.throws(run);controls.push({name,rejected:true,kind:'synthetic_checker_sensitivity_not_executed_core_fault'});}
 return controls;
}
