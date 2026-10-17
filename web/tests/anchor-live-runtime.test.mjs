import test from 'node:test';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {validateFrame,drawFrame} from '../moonbit/site/render.mjs';
const runtimePath=process.env.GPUI_ANCHOR_RUNTIME;
function painter() {
  const state={},stack=[],casters=[];
  const context=new Proxy(state,{get:(o,k)=>k==='save'?()=>stack.push({...o}):k==='restore'?()=>{
    for(const key of Object.keys(o))delete o[key];Object.assign(o,stack.pop());
  }:k==='measureText'?()=>({fontBoundingBoxAscent:14,fontBoundingBoxDescent:4}):k==='roundRect'?(...args)=>{
    if(o.shadowOffsetX>1000)casters.push(args);
  }:()=>{},set:(o,k,v)=>(o[k]=v,true)});
  return {context,casters};
}
const q=(f,id)=>f.snapshot.items.find(i=>i.id===id);
test('actual compiled anchor uses actual DPR layout, line boxes, paint snapshots, and safe clipped live bounds',{skip:!runtimePath},async()=>{
  const r=await import(pathToFileURL(runtimePath)),metadata=JSON.parse(r.anchor_metadata());
  const read=(w,h,d,metric=80)=>JSON.parse(r.anchor_frame(w,h,Array(19).fill(metric),d));
  r.anchor_reset();const initial=read(750,600,1);
  for(const [w,h,d] of [[800,600,2],[801.25,601.5,1.25],[320,200,1.5],[4,4,.25],[4.001,4.001,.25],[4096,512,4],[4095.999,600,1.25],[4096,600,1],[4,16384,1],[4,4096.124,4],[4096,8192.49,1],[4096,8192,1],[750,600,1],[480,600,1]]) {
    for(const metric of [1,80,1000]) {
      r.anchor_reset();const idle=read(w,h,d,metric);assert.equal(idle.ok,true);validateFrame(idle);
      assert.equal(idle.snapshot.scale,d);assert.equal(idle.conformance,'unverified');
      assert.equal(idle.anchor.comparison_profile_match,(w===750||w===480)&&h===600&&d===1);
      // This expectation follows pinned text.rs Window.pixel_snap, not a DPR1 box.
      const line=(size)=>Math.ceil(size*1.618033988749895*d-.5)/d;
      assert(Math.abs(q(idle,2).bounds.height-line(16))<1e-8);
      const p=painter();drawFrame(p.context,idle,{...metadata,width:w,height:h},d);
      for(const index of [0,1,2,3,5,6,7,8]) {
        const b=q(idle,index+10).bounds;
        const left=Math.max(0,b.x),right=Math.min(w,b.x+b.width),top=Math.max(0,b.y),bottom=Math.min(h,b.y+b.height);
        if(right<=left||bottom<=top)continue;
        r.anchor_pointer((left+right)/2,(top+bottom)/2,true);const hover=read(w,h,d,metric);
        assert.equal(hover.anchor.hovered,index);validateFrame(hover);
        assert.equal(hover.snapshot.scale,d);
        // Core snaps origin and extent separately, so a fractional far edge may
        // differ from its unsnapped constraint by one device pixel.
        assert(Math.abs(q(hover,201).bounds.height-line(14))<1e-8);
        const popup=q(hover,200).bounds;
        if(w>=popup.width)assert(popup.x>=-1e-8);
        if(h>=popup.height)assert(popup.y>=-1e-8);
        if(w>=popup.width)assert(popup.x+popup.width<=w+1/d+1e-8);
        if(h>=popup.height)assert(popup.y+popup.height<=h+1/d+1e-8);
        drawFrame(p.context,hover,{...metadata,width:w,height:h},d);
        r.anchor_reset();assert.deepEqual(read(w,h,d,metric),idle);
      }
      // These are actual drawFrame caster paths with real Canvas save/restore
      // state semantics, not a second implementation of anchor geometry.
      assert(p.casters.every(([x,_y,width])=>x+width<=0),JSON.stringify({w,h,d,metric,casters:p.casters}));
    }
  }
  r.anchor_reset();assert.deepEqual(read(750,600,1),initial);
});

test('actual exports reject nonfinite/oversized resources, clear stale hover, and recover',{skip:!runtimePath},async()=>{
  const r=await import(pathToFileURL(runtimePath));const read=(w=750,h=600,d=1,metrics=Array(19).fill(80))=>JSON.parse(r.anchor_frame(w,h,metrics,d));
  r.anchor_reset();const idle=read();const b=q(idle,10).bounds;
  for(const values of [[NaN,600,1],[Infinity,600,1],[750,Infinity,1],[750,600,NaN],[750,600,Infinity],[3.999,600,1],[4096.001,600,1],[750,3.999,1],[4,16384.001,1],[750,600,.24999],[750,600,4.0001],[4,4096.125,4],[4096,8192.5,1],[4096,513,4]]) {
    r.anchor_pointer(b.x+60,b.y+32,true);assert.equal(read().anchor.hovered,0);
    assert.equal(read(...values).error,'invalid_live_viewport');assert.deepEqual(read(),idle);
  }
  for(const metric of [0,-1,1000.001,NaN,Infinity]) {
    r.anchor_pointer(b.x+60,b.y+32,true);assert.equal(read(750,600,1,Array(19).fill(metric)).error,'invalid_metrics');assert.deepEqual(read(),idle);
  }
  for(const [x,y] of [[-1,100],[800,100],[100,-1],[100,700],[NaN,1],[Infinity,1]]) {
    r.anchor_pointer(x,y,true);assert.deepEqual(read(),idle);
  }
});
