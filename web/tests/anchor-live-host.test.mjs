import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {readAnchorFrame,createAnchorHost} from '../moonbit/site/anchor-host.mjs';
import {watchGridDeviceScale} from '../moonbit/site/grid-layout-host.mjs';
// Synthetic lifecycle tests verify the real shared host wiring and transport;
// separate compiled and Chromium tests establish actual candidate execution.
async function route(width=800) {
  const events=new Map(),listeners=new Map(),queries=[],calls=[],draws=[];let hovered=false,resets=0;
  const runtime={anchor_metadata:()=>JSON.stringify({id:'anchor',width:750,height:600,font_family:'IBM Plex Sans',runs:[{text:'A',font_size:16}]}),
    anchor_pointer:(_x,_y,inside)=>{hovered=inside;},anchor_reset:()=>{hovered=false;resets++;},
    anchor_frame:(w,h,widths,d)=>{calls.push([w,h,widths,d]);return JSON.stringify({ok:true,conformance:'unverified',anchor:{hovered:hovered?0:-1,comparison_profile_match:[750,480].includes(w)&&h===600&&d===1}});}};
  const context={measureText:()=>({width:80})};
  const canvas={style:{},setAttribute(){},getContext:()=>context,getBoundingClientRect:()=>({left:0,top:0}),
    addEventListener:(n,f)=>{assert(!listeners.has(n));listeners.set(n,f);},removeEventListener:(n,f)=>{assert.equal(listeners.get(n),f);listeners.delete(n);}};
  const error={hidden:true},notice={style:{},hidden:true,setAttribute(){}};
  const document={createElement:()=>notice,body:{append(){}},getElementById:id=>id==='canvas'?canvas:error,documentElement:{dataset:{}},fonts:{add(){},ready:Promise.resolve()}};
  const window={innerWidth:width,innerHeight:600,devicePixelRatio:2,
    matchMedia:media=>{const q={media,listeners:new Set(),addEventListener:(_n,f)=>q.listeners.add(f),removeEventListener:(_n,f)=>q.listeners.delete(f)};queries.push(q);return q;},
    addEventListener:(n,f)=>{if(!events.has(n))events.set(n,[]);events.get(n).push(f);}};
  const sandbox={URL,location:{href:'http://localhost/moonbit/?example=anchor'},window,document,FontFace:class{async load(){return this;}},
    readAnchorFrame,createAnchorHost,watchGridDeviceScale,drawFrame:(_c,f,m,s)=>draws.push({f,m:{...m},s}),load:async()=>runtime,
    createHostTiming:()=>({complete(){},fail(){}})};
  const source=readFileSync(new URL('../moonbit/site/host.mjs',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace('await import(modules[example])','await load(modules[example])');
  await vm.runInNewContext(`(async()=>{${source}})()`,sandbox);
  return {window,canvas,error,notice,queries,calls,draws,sandbox,listeners,resets:()=>resets,fire:n=>{for(const f of events.get(n)||[])f();},move:()=>listeners.get('pointermove')({isTrusted:true,pointerType:'mouse',clientX:80,clientY:80})};
}
test('actual anchor host wiring transports live size, fractional rounded backing and honest profile notice',async()=>{
  const f=await route();
  for(const [w,h,d] of [[800,600,2],[801.25,600.5,1.25],[4,4,.25],[750,600,1],[480,600,1]]) {
    Object.assign(f.window,{innerWidth:w,innerHeight:h,devicePixelRatio:d});f.fire('resize');
    assert.equal(f.canvas.width,Math.round(w*d));assert.equal(f.canvas.height,Math.round(h*d));
    assert.equal(f.canvas.style.width,`${w}px`);assert.equal(f.sandbox.gpuiExample.scale,d);
    assert.equal(f.notice.hidden,[750,480].includes(w)&&h===600&&d===1);assert.match(f.notice.textContent,/unverified/);
  }
});
test('invalid live inputs clear hover and stale success before measurement, and recover in the same document',async()=>{
  for(const initial of [800,0]) {
    const f=await route(initial);Object.assign(f.window,{innerWidth:800});f.fire('resize');f.move();
    assert.equal(f.sandbox.gpuiExample.frame.anchor.hovered,0);
    for(const [w,h,d] of [[4097,600,1],[800,3,1],[800,600,NaN],[800,600,0],[800,600,Infinity],[4,4097,4],[4096,8192.5,1]]) {
      const count=f.calls.length;Object.assign(f.window,{innerWidth:w,innerHeight:h,devicePixelRatio:d});f.fire('resize');
      assert.equal(f.calls.length,count);assert.equal(f.canvas.hidden,true);assert.equal(f.error.hidden,false);assert.equal(f.sandbox.gpuiExample,undefined);assert.equal(f.notice.hidden,true);
      Object.assign(f.window,{innerWidth:800,innerHeight:600,devicePixelRatio:2});f.fire('resize');
      assert.equal(f.canvas.hidden,false);assert.equal(f.error.hidden,true);assert.equal(f.sandbox.gpuiExample.frame.anchor.hovered,-1);
    }
  }
});
test('DPR-only observer rearms and pagehide/pageshow releases and restores hover transport exactly once',async()=>{
  const f=await route();f.move();
  for(const d of [1.25,4,4.1,2]) {
    const old=f.queries.at(-1);assert.equal(old.listeners.size,1);f.window.devicePixelRatio=d;
    for(const fn of [...old.listeners])fn();assert.equal(old.listeners.size,0);
    assert.equal(f.queries.at(-1).media,`(resolution: ${d}dppx)`);
    if(d>4)assert.equal(f.sandbox.gpuiExample,undefined);else assert.equal(f.sandbox.gpuiExample.scale,d);
  }
  for(let i=0;i<2;i++) {
    f.move();assert.equal(f.sandbox.gpuiExample.frame.anchor.hovered,0);
    f.fire('pagehide');assert.equal(f.listeners.size,0);assert.equal(f.queries.at(-1).listeners.size,0);
    f.window.devicePixelRatio=1.25;f.fire('pageshow');assert.equal(f.listeners.size,2);assert.equal(f.queries.at(-1).listeners.size,1);
    assert.equal(f.sandbox.gpuiExample.frame.anchor.hovered,-1);assert.equal(f.canvas.width,1000);
    const count=f.queries.length;f.fire('pageshow');assert.equal(f.queries.length,count);
  }
  assert(f.resets()>0);
});
