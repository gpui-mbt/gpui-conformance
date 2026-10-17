// Synthetic source-math tests. These do not execute Rust, a shader or a browser.
import test from 'node:test';
import assert from 'node:assert/strict';
import {gradientT,gradientColor,SOURCE_GRADIENTS,VIEWPORT_SEQUENCE,sourceStructure,buttonTarget} from './gradient-comparator.mjs';
import {classifyBackend} from './gradient-backend-observer.mjs';
const bounds={origin:[0,0],size:[200,100]};
test('source angles retain aspect ratio, raw stops and 360',()=>{
 assert.equal(gradientT(90,[0,1],bounds,[50,50]).normalized,.25);
 assert(Math.abs(gradientT(0,[0,1],bounds,[100,25]).normalized-.75)<1e-12);
 assert(Math.abs(gradientT(360,[0,1],bounds,[100,25]).normalized-.75)<1e-12);
 assert.equal(gradientT(90,[1,0],bounds,[50,50]).normalized,.75);
 assert.equal(gradientT(90,[-1,2],bounds,[100,50]).normalized,.5);
 assert.equal(gradientT(90,[.5,.5],bounds,[100,50]).normalized,null);
 assert.notEqual(gradientT(45,[0,1],bounds,[50,25]).normalized,gradientT(45,[0,1],{origin:[0,0],size:[100,100]},[25,25]).normalized);
});
test('exact half-green and float alpha survive source math',()=>{
 const green=[0,.5,0,.1234];const c=gradientColor(green,[1,0,0,.8766],0,'sRGB');
 assert(Math.abs(c[1]-.5)<1e-12);assert.equal(c[3],.1234);
 assert.notEqual(c[1],127/255);assert.notEqual(c[1],1);
 assert(Math.abs(gradientColor(green,[1,0,0,.8766],.5,'Oklab')[3]-.5)<1e-12);
 assert.equal(SOURCE_GRADIENTS.length,13);assert.equal(SOURCE_GRADIENTS[10][3],.5);assert.equal(SOURCE_GRADIENTS[10][4],.5);
});
test('known source transfer prediction differs from CSS-byte lerp',()=>{
 const c=gradientColor([1,0,0,1],[0,0,1,1],.5,'sRGB');assert(Math.abs(c[0]-.21404114048223255)<1e-12);assert.equal(c[1],0);
 assert.notDeepEqual(c,gradientColor([1,0,0,1],[0,0,1,1],.5,'Oklab'));
});
test('profile has both host sizes and genuine restoration operations',()=>{
 assert.deepEqual(VIEWPORT_SEQUENCE.map(s=>s.space),['sRGB','Oklab','sRGB','sRGB','Oklab','sRGB','sRGB']);
 assert.equal(VIEWPORT_SEQUENCE.filter(s=>s.action==='click').length,4);assert.equal(VIEWPORT_SEQUENCE.filter(s=>s.action==='resize').length,2);
});
test('renderer observations require final visible canvas identity',()=>{
 const snapshot=events=>({events,visible_canvases:[{canvas_id:1,width:960,height:600}]});
 assert.equal(classifyBackend(snapshot([])).observed,'pending_not_observed');
 assert.equal(classifyBackend(snapshot([{kind:'requestAdapter.resolved',returned:true}])).observed,'pending_not_observed');
 assert.equal(classifyBackend(snapshot([{kind:'getContext',requested:'webgl2',returned:true,canvas_id:1}])).observed,'webgl_visible_canvas_context_returned');
 assert.deepEqual(classifyBackend(snapshot([{kind:'webgpu.configure',format:'rgba8unorm',canvas_id:1}])).formats,['rgba8unorm']);
 assert.equal(classifyBackend(snapshot([{kind:'webgpu.configure',format:'rgba8unorm',canvas_id:2}])).observed,'pending_not_observed');
 assert.equal(classifyBackend(snapshot([{kind:'webgpu.configure',format:'rgba8unorm',canvas_id:1},{kind:'getContext',requested:'webgl2',returned:true,canvas_id:1}])).observed,'pending_ambiguous_context_history');
});
test('synthetic whole-image discovery distinguishes 15 source shapes and button',()=>{
 const image={width:960,height:600,data:new Uint8Array(960*600*4).fill(255)};
 const fill=(x,y,w,h,color)=>{for(let j=y;j<y+h;j++)for(let i=x;i<x+w;i++)image.data.set([...color,255],(j*960+i)*4);};
 fill(880,16,64,28,[0,0,0]);
 let y=60;for(const count of [2,4,4,1,1,2,1]){const w=Math.floor((928-12*(count-1))/count);for(let i=0;i<count;i++)fill(16+i*(w+12),y,w,40,[255,0,0]);y+=60;}
 assert.equal(sourceStructure(image).colored.length,15);assert.deepEqual(buttonTarget(image),{x:912,y:30});
 fill(16,60,458,40,[255,255,255]);assert.throws(()=>sourceStructure(image));
});
