import test from 'node:test';
import assert from 'node:assert/strict';
import {verifyPolicyImage,POLICY_SOURCE} from './gradient-policy-contract.mjs';
function fixture(){const image={width:960,height:600,data:new Uint8Array(960*600*4).fill(255)};const set=(x,y,c)=>image.data.set(c,(y*960+x)*4);for(let x=0;x<161;x++)set(20+x,30,x<=80?[255,0,0,255]:[0,0,255,255]);for(const name of ['green','alpha_green','polygon']){const p=POLICY_SOURCE[name];set(...p.sample,p.expected);}return image;}
test('synthetic policy fixture meets frozen exact predicates',()=>assert.equal(verifyPolicyImage(fixture()).status,'explicit_policy_probe_verified'));
test('early green or alpha quantization cannot hide in2-code main budget',()=>{for(const [name,wrong] of [['alpha_green',[128,192,128,255]],['alpha_green',[127,191,127,255]],['green',[0,127,0,255]],['polygon',[52,0,57,255]]]){const image=fixture(),[x,y]=POLICY_SOURCE[name].sample;image.data.set(wrong,(y*960+x)*4);assert.throws(()=>verifyPolicyImage(image));}});
