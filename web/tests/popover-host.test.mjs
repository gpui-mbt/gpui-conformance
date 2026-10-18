// Transport/metrics unit contracts with synthetic runtime and Canvas objects.
// These are not compiled MoonBit, Rust or browser conformance evidence.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {popoverRuns,loadPopoverFont,measurePopoverInputs} from '../moonbit/site/popover-text.mjs';
import {createPopoverHost,readPopoverFrame} from '../moonbit/site/popover-host.mjs';
import {validateFrame,drawFrame} from '../moonbit/site/render.mjs';
const metadata=()=>({id:'popover',font_family:'IBM Plex Sans',runs:popoverRuns.map(([text,font_size])=>({text,font_size}))});
const context=()=>({font:'',textRendering:'auto',fontKerning:'auto',save(){this.saved=[this.font,this.textRendering,this.fontKerning];},restore(){[this.font,this.textRendering,this.fontKerning]=this.saved;},measureText(text){return {width:text.length*(this.font.includes('14px')?7:8)};}});
const frame=()=>({ok:true,conformance:'unverified',snapshot:{schema_version:1,items:[]},decorations:[],popover:{comparison_profile_match:false}});
class Target {
  listeners=new Map();innerWidth=800;innerHeight=600;devicePixelRatio=1;
  addEventListener(k,f){if(!this.listeners.has(k))this.listeners.set(k,new Set());this.listeners.get(k).add(f);}
  removeEventListener(k,f){this.listeners.get(k)?.delete(f);}
  emit(k,e={}){for(const f of this.listeners.get(k)||[])f(e);}
  getBoundingClientRect(){return {left:10,top:20,width:this.innerWidth/2,height:this.innerHeight/2};}
}
const event=(values={})=>({isTrusted:true,pointerType:'mouse',isPrimary:true,pointerId:1,clientX:30,clientY:40,button:0,...values});
test('bundled face load and font readiness precede admission; failed fonts reject',async()=>{
  const calls=[];let face;
  class Font {constructor(...args){calls.push(args);face=this;}async load(){calls.push('load');this.status='loaded';return this;}}
  const fonts={add:f=>{assert.equal(f,face);calls.push('add');},ready:Promise.resolve(),check:spec=>{calls.push(spec);return true;}};
  assert.equal(await loadPopoverFont({FontFaceType:Font,fonts}),face);
  assert.deepEqual(calls,[['IBM Plex Sans','url(./IBMPlexSans-Regular.ttf)'],'load','add','16px "IBM Plex Sans"','14px "IBM Plex Sans"']);
  await assert.rejects(loadPopoverFont({FontFaceType:Font,fonts:{...fonts,check:()=>false}}),/unavailable/);
  class Failed {async load(){throw Error('network');}}
  await assert.rejects(loadPopoverFont({FontFaceType:Failed,fonts}),/network/);
});
test('seven exact source styles flatten into eight LF-separated prefix arrays',()=>{
  const c=context(),values=measurePopoverInputs(c,metadata());
  assert.equal(values.length,8);assert.equal(values[0].length,'Opened Popover'.length+1);
  assert.equal(values[0].at(-1),'Opened Popover'.length*8);
  assert.equal(values[6].at(-1),'Click outside to close.'.length*7);
  assert.equal(c.font,'');assert.equal(c.textRendering,'auto');
  const wrong=metadata();wrong.runs[3].font_size=16;assert.throws(()=>measurePopoverInputs(c,wrong),/source/);
  for(const value of [NaN,Infinity,-1,0,16385])assert.throws(()=>measurePopoverInputs({...context(),measureText:()=>({width:value})},metadata()),/metric/);
});
test('frame transport uses current viewport and rejects invalid inputs before model dispatch',()=>{
  let calls=0;const runtime={popover_frame(...args){calls++;assert.deepEqual(args.slice(0,3),[800,600,2]);assert.equal(args[3].length,8);return JSON.stringify(frame());}};
  assert.equal(readPopoverFrame(runtime,context(),{innerWidth:800,innerHeight:600,devicePixelRatio:2},metadata()).backingWidth,1600);
  for(const v of [[0,600,1],[800,600,NaN],[800,600,8],[8192,8192,4]])assert.throws(()=>readPopoverFrame(runtime,context(),{innerWidth:v[0],innerHeight:v[1],devicePixelRatio:v[2]},metadata()),/viewport/);
  assert.equal(calls,1);
  assert.throws(()=>readPopoverFrame({popover_frame:()=>JSON.stringify({ok:false,error:'invalid_metrics_or_viewport'})},context(),new Target(),metadata()),/invalid_metrics/);
});
test('trusted primary mouse transport refreshes before dispatch, passes current coordinates, cancels interrupted input and stops cleanly',()=>{
  const canvas=new Target(),windowTarget=new Target(),calls=[];let valid=true;
  const runtime={popover_pointer(...args){calls.push(args);return true;},popover_cancel(){calls.push('cancel');}};
  const host=createPopoverHost({runtime,canvas,windowTarget,render(){calls.push('render');return valid;}});
  canvas.emit('pointerdown',event({isTrusted:false}));canvas.emit('pointerdown',event({pointerType:'touch'}));canvas.emit('pointerdown',event({isPrimary:false}));assert.equal(calls.length,0);
  canvas.emit('pointerdown',event());assert.deepEqual(calls,['render',['down',40,40,0],'render']);
  windowTarget.innerWidth=400;windowTarget.emit('pointerup',event());assert.deepEqual(calls.slice(-3),['render',['up',20,40,0],'render']);
  windowTarget.emit('pointerup',event());assert.equal(calls.length,6);
  canvas.emit('pointerdown',event());windowTarget.emit('blur');windowTarget.emit('pointerup',event());assert.equal(calls.at(-1),'cancel');
  canvas.emit('pointerdown',event({button:2}));assert.deepEqual(calls.at(-2),['down',20,40,2]);
  windowTarget.emit('pointercancel',event());assert.equal(calls.at(-1),'cancel');
  valid=false;canvas.emit('pointerdown',event());assert.equal(calls.at(-1),'cancel');
  host.stop();host.stop();const count=calls.length;canvas.emit('pointerdown',event());windowTarget.emit('pointerup',event());assert.equal(calls.length,count);
  assert(host.events.every(e=>e.trusted));
});
test('solid snapped border and opacity validate without relaxing dashed contracts',()=>{
  const f=frame();f.snapshot.scale=1.25;f.snapshot.items=[{id:1,kind:'quad',bounds:{x:0,y:0,width:100,height:50},color:{red:255,green:255,blue:255,alpha:255}}];
  f.decorations=[{id:1,radius:6,border_width:0.8,border_source:'device_snapped_1px',border:'#000000',border_style:'solid',border_opacity:0.1}];
  validateFrame(f);
  const original=f.decorations[0].border_width;
  for(const width of [0.7,1.25,2,NaN]){f.decorations[0].border_width=width;assert.throws(()=>validateFrame(f),/decoration/);}
  f.decorations[0].border_width=original;
  delete f.decorations[0].border_source;assert.throws(()=>validateFrame(f),/decoration/);
  f.decorations[0].border_source='unknown';assert.throws(()=>validateFrame(f),/decoration/);
  f.decorations[0].border_source='device_snapped_1px';
  for(const opacity of [NaN,-1,1.01]){f.decorations[0].border_opacity=opacity;assert.throws(()=>validateFrame(f),/decoration/);}
  f.decorations[0].border_opacity=0.1;f.decorations[0].border_style='dashed';assert.throws(()=>validateFrame(f),/decoration/);
  f.decorations[0].border_style='solid';const alpha=[];const c=new Proxy({globalAlpha:1,save(){},restore(){},stroke(){alpha.push(this.globalAlpha);}}, {get(t,k){return k in t?t[k]:(()=>{});}});
  drawFrame(c,f,{width:100,height:50},1);assert.deepEqual(alpha,[0.1]);
  f.snapshot.items[0].opacity=0.5;
  const writes=[];
  const setterOnly=new Proxy({}, {get:()=>()=>{},set(target,key,value){if(key==='globalAlpha')writes.push(value);return true;}});
  drawFrame(setterOnly,f,{width:100,height:50},1.25);
  assert.deepEqual(writes,[0.5,0.05]);
});
test('Rust popover route is wired but only claims canvas initialization',async()=>{
  const source=readFileSync(new URL('../rust/host.mjs',import.meta.url),'utf8').replace("import { createHostTiming } from '../load-timing.mjs';",'').replace('await import(modules[example])','await load(modules[example])');
  const imports=[],document={documentElement:{dataset:{}},querySelector:()=>({}),getElementById:()=>({})};
  await vm.runInNewContext(`(async()=>{${source}})()`,{URL,location:{href:'https://example.test/?example=popover'},crossOriginIsolated:true,document,createHostTiming:()=>({complete(){},fail(){}}),load:async path=>{imports.push(path);return {default:async()=>{}};},performance:{now:()=>0},console});
  assert.deepEqual(imports,['./popover.js']);assert.equal(document.documentElement.dataset.runtimeStatus,'initialized');
});
test('shared MoonBit host fails closed and reconnects once after BFCache restoration',async()=>{
  const source=readFileSync(new URL('../moonbit/site/host.mjs',import.meta.url),'utf8')
    .replace(/^import .*;\n/gm,'').replace('await import(modules[example])','await load(modules[example])');
  const canvas=new Target();canvas.style={};canvas.setAttribute=()=>{};canvas.getContext=()=>context();
  const windowTarget=new Target(),error={hidden:true,textContent:''},document={documentElement:{dataset:{}},getElementById:id=>id==='canvas'?canvas:error,fonts:{}};
  let valid=true,reads=0,draws=0,reset=0,starts=0,stops=0,watches=0,unwatches=0,fontReady=false;
  const runtime={popover_metadata:()=>JSON.stringify({...metadata(),width:800,height:600}),popover_reset:()=>reset++};
  const sandbox={URL,location:{href:'https://example.test/?example=popover'},document,window:windowTarget,FontFace:class{},
    load:async()=>runtime,createHostTiming:()=>({complete(){},fail(){}}),
    loadPopoverFont:async()=>{fontReady=true;},readPopoverFrame:()=>{
      assert(fontReady);reads++;if(!valid)throw Error('bad metrics');
      return {frame:frame(),width:800,height:600,scale:1,prefixes:[],backingWidth:800,backingHeight:600};
    },drawFrame:()=>draws++,createPopoverHost:()=>{starts++;return {events:[],stop:()=>stops++};},
    watchGridDeviceScale:()=>{watches++;return ()=>unwatches++;},console};
  await vm.runInNewContext(`(async()=>{${source}})()`,sandbox);
  assert.equal(document.documentElement.dataset.runtimeStatus,'ready');assert.equal(starts,1);assert.equal(draws,1);
  valid=false;windowTarget.emit('resize');assert.equal(document.documentElement.dataset.runtimeStatus,'failed');assert(canvas.hidden);assert.equal(sandbox.gpuiExample,undefined);assert.equal(reset,1);
  valid=true;windowTarget.emit('resize');assert.equal(document.documentElement.dataset.runtimeStatus,'ready');assert(!canvas.hidden);
  windowTarget.emit('pagehide');assert.equal(stops,1);assert.equal(unwatches,1);assert.equal(sandbox.gpuiExample,undefined);
  const before=reads;windowTarget.emit('resize');assert.equal(reads,before);
  windowTarget.emit('pageshow');assert.equal(starts,2);assert.equal(watches,2);assert.equal(reads,before+1);
  windowTarget.emit('pageshow');assert.equal(starts,2);assert.equal(reads,before+1);
});
