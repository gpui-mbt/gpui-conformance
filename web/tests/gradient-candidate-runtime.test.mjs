import test from 'node:test';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {drawCoreRasterFrame,validateCoreRasterFrame} from '../moonbit/site/render.mjs';
import {verifyPolicyImage} from './gradient-policy-contract.mjs';
import {gradientRenderScale} from '../moonbit/site/gradient-host.mjs';
const path=process.env.GPUI_GRADIENT_RUNTIME;
const runtime=path?await import(pathToFileURL(path)):null;
const widths=[140,35,40,80];
test('actual compiled candidate uses live source geometry and core click routing',{skip:!runtime},()=>{
 runtime.gradient_reset();const metadata=JSON.parse(runtime.gradient_metadata());assert.equal(metadata.source_blob,'df1398fff58b637abf0c0b31934f6ad523d84a21');
 const frame=JSON.parse(runtime.gradient_frame(960,600,widths,1));validateCoreRasterFrame(frame,{...metadata,width:960,height:600},1);
 assert.equal(frame.gradient.color_space,'sRGB');assert.equal(frame.gradient.comparison_profile_match,true);
 assert.equal(frame.snapshot.items.filter(i=>i.kind==='paint').length,16);
 const button=frame.snapshot.items.find(i=>i.id===3);const b=button.shape.bounds;
 runtime.gradient_click(b.x+2,b.y+2);const toggled=JSON.parse(runtime.gradient_frame(960,600,widths,1));assert.equal(toggled.gradient.color_space,'Oklab');
 runtime.gradient_click(b.x+2,b.y+2);assert.deepEqual(JSON.parse(runtime.gradient_frame(960,600,widths,1)),frame);
 runtime.gradient_click(0,0);assert.equal(JSON.parse(runtime.gradient_frame(733,515,widths,1.25)).gradient.comparison_profile_match,false);
 assert.equal(JSON.parse(runtime.gradient_frame(960,600,widths,4)).ok,false);
 runtime.gradient_reset();assert.equal(JSON.parse(runtime.gradient_frame(600,960,widths,1)).gradient.color_space,'sRGB');
});
test('actual core policy run retains float blending until final byte quantization',{skip:!runtime},()=>{
 const frame=JSON.parse(runtime.gradient_policy_frame());validateCoreRasterFrame(frame,{width:960,height:600,font_family:'IBM Plex Sans'},1);
 assert.deepEqual(frame.snapshot.items.map(i=>i.id),[1,2,3,4,6]);assert.equal(frame.operations.length,1);const op=frame.operations[0];assert.equal(op.kind,'rgba_run');assert.equal(op.count,5);
 verifyPolicyImage({width:960,height:600,data:new Uint8Array(op.rgba)});
});

test('compiled fitted high-DPR frames preserve logical layout and core hit routes',{skip:!runtime},()=>{
 const surface=(w,h)=>({getContext:()=>({createImageData:()=>({data:new Uint8ClampedArray(w*h*4)}),putImageData(){}})});
 for(const d of [2,1.333,4]){runtime.gradient_reset();const fit=gradientRenderScale(800,600,d),scale=fit.effectiveRenderScale;
 const f=JSON.parse(runtime.gradient_frame_at_scale(800,600,widths,d,scale));const low=JSON.parse(runtime.gradient_frame_at_scale(800,600,widths,d,.5));
 assert.deepEqual(f.snapshot.items,low.snapshot.items);assert.deepEqual(f.snapshot.clip_chains,low.snapshot.clip_chains);
 assert.equal(f.gradient.comparison_profile_match,false);const dimensions=validateCoreRasterFrame(f,{width:800,height:600},scale);assert.equal(dimensions.width,fit.backingWidth);assert.equal(dimensions.height,fit.backingHeight);
 let clears=0,draws=0;const ctx=new Proxy({},{get:(_,k)=>k==='measureText'?()=>({fontBoundingBoxAscent:10,fontBoundingBoxDescent:3}):()=>{if(k==='clearRect')clears++;if(k==='drawImage')draws++;},set:()=>true});drawCoreRasterFrame(ctx,f,{width:800,height:600,font_family:'IBM Plex Sans'},scale,surface);assert.equal(clears,1);assert.ok(draws>0);
 const b=f.snapshot.items.find(i=>i.id===3).shape.bounds;runtime.gradient_click(b.x+2,b.y+2);assert.equal(JSON.parse(runtime.gradient_frame_at_scale(800,600,widths,d,scale)).gradient.color_space,'Oklab');
 }runtime.gradient_reset();
 assert.equal(JSON.parse(runtime.gradient_frame_at_scale(800,600,widths,2,1.478)).ok,false);assert.equal(JSON.parse(runtime.gradient_frame_at_scale(1024.1,1024,widths,1,1)).ok,false);assert.equal(JSON.parse(runtime.gradient_frame_at_scale(800,600,widths,NaN,1)).ok,false);assert.equal(JSON.parse(runtime.gradient_frame_at_scale(800,600,widths,2,1)).ok,true);
});
test('paired DPR1 frame remains byte-identical to the pre-fit compiled candidate',{skip:!runtime||!process.env.GPUI_GRADIENT_PRE_FIT_RUNTIME},async()=>{const old=await import(pathToFileURL(process.env.GPUI_GRADIENT_PRE_FIT_RUNTIME));for(const [w,h] of [[960,600],[600,960]]){runtime.gradient_reset();old.gradient_reset();assert.equal(runtime.gradient_frame_at_scale(w,h,widths,1,1),old.gradient_frame(w,h,widths,1));}});
