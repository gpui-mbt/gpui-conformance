// Authored probe document, distinct from the unchanged gradient.rs example.
// Predicates declared before candidate execution, from reviewed original
// SwiftShader WebGL2 observations. Exact failures remain failures.
import assert from 'node:assert/strict';
import {pixel} from './gradient-comparator.mjs';
export const POLICY_PROFILE='gradient_explicit_policy_probe_v1';
export const POLICY_SEQUENCE=Object.freeze([{name:'policy',width:960,height:600,space:'sRGB',action:null,dpr:1,after_operation:0}]);
export const POLICY_SOURCE=Object.freeze({
 viewport:[960,600],equal_stop:{rect:[20,20,161,20],angle:90,stops:[.5,.5],start:[1,0,0,1],end:[0,0,1,1],sample_y:30},
 green:{rect:[20,60,161,20],rgba:[0,.5,0,1],sample:[100,70],expected:[0,128,0,255]},
 alpha_green:{rect:[20,100,161,20],rgba:[0,.5,0,.5],background:[1,1,1,1],sample:[100,110],expected:[128,191,128,255]},
 polygon:{points:[[20,220],[100,170],[180,170],[260,220]],clip:[0,185,300,35],angle:180,stops:[0,1],start:[1,0,0,1],end:[0,0,1,1],sample:[140,195],expected:[114,0,19,255]},
});
export function verifyPolicyImage(image) {
 assert.equal(image.width,960);assert.equal(image.height,600);const samples=[];
 for(let x=0;x<161;x++){const actual=pixel(image,20+x,30),expected=x<=80?[255,0,0,255]:[0,0,255,255];assert.deepEqual(actual,expected,`policy equal-stop161 exact boundary x=${x}`);samples.push({position:[20+x,30],actual,expected});}
 for(const name of ['green','alpha_green','polygon']){const p=POLICY_SOURCE[name],actual=pixel(image,...p.sample);assert.deepEqual(actual,p.expected,`policy ${name} exact observed bytes`);samples.push({name,position:p.sample,actual,expected:p.expected});}
 assert.deepEqual(pixel(image,140,180),[255,255,255,255],'policy polygon clip excludes y180');
 return {status:'explicit_policy_probe_verified',profile:POLICY_PROFILE,samples,qualification:'Separately authored core policy probes match reviewed software-WebGL2 observations; no universal GPU or unchanged-example attribution'};
}
