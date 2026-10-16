import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createDragDropHost} from '../moonbit/site/drag-drop-host.mjs';
function setup({response,rect}={}) {
  const calls=[],listeners=new Map(),errors=[],renders=[];
  const canvas={style:{},getBoundingClientRect:()=>rect??({left:10,top:20,width:400,height:300}),
    addEventListener:(n,h)=>listeners.set(n,h),removeEventListener:n=>listeners.delete(n)};
  const runtime={drag_drop_pointer(...args){calls.push(['pointer',...args]);return response??JSON.stringify({ok:true,changed:false,stopped:false,outcome:'unchanged',cursor:'move'});},
    drag_drop_leave(){calls.push(['leave']);return JSON.stringify({ok:true,changed:true,stopped:false,outcome:'leave',cursor:'default'});},
    drag_drop_reset(){calls.push(['reset']);}};
  const host=createDragDropHost({runtime,canvas,render:()=>renders.push(true),onError:error=>errors.push(error.message)});
  const emit=(type,props={})=>listeners.get(type)?.({isTrusted:true,pointerType:'mouse',clientX:210,clientY:170,
    button:0,shiftKey:false,ctrlKey:false,altKey:false,metaKey:false,preventDefault(){},...props});
  return {host,runtime,canvas,calls,listeners,errors,renders,emit};
}
test('raw mouse and modifiers reach compiled exports in order with no host policy',()=>{
  const s=setup();
  s.emit('pointermove',{button:-1});s.emit('pointerdown',{shiftKey:true,ctrlKey:true});
  s.emit('pointerup',{clientX:338,clientY:198,button:2,altKey:true,metaKey:true});s.emit('pointerleave');
  assert.deepEqual(s.calls,[['pointer','move',400,300,-1,false,false,false,false],
    ['pointer','down',400,300,0,true,true,false,false],
    ['pointer','up',656,356,2,false,false,true,true],['leave']]);
  assert.equal(s.renders.length,4);assert.equal(s.canvas.style.cursor,'default');
  assert.equal(s.errors.length,0);assert(s.host.events.every(event=>event.trusted&&event.accepted));
  assert.deepEqual([...s.listeners.keys()],['pointermove','pointerdown','pointerup','pointerleave','contextmenu']);
  assert.deepEqual(Object.keys(s.host).sort(),['events','stop']);
});
test('unchanged core drag result still repaints model-owned hover and accepts model cursor',()=>{
  const s=setup();s.emit('pointermove',{button:-1});
  assert.equal(s.renders.length,1);assert.equal(s.canvas.style.cursor,'move');
  assert.deepEqual(s.host.events[0],{type:'move',trusted:true,accepted:true,outcome:'unchanged',error:null});
});
test('explicit core error is observable and renders explicit application cancellation',()=>{
  const s=setup({response:JSON.stringify({ok:false,error:'unknown_target_binding:999',cancelled:true,cursor:'default'})});
  s.emit('pointerup');assert.equal(s.renders.length,1);
  assert.deepEqual(s.errors,['MoonBit drag-drop: unknown_target_binding:999']);
  assert.equal(s.host.events[0].accepted,false);assert.equal(s.host.events[0].error,'unknown_target_binding:999');
});
test('host neither fabricates drag activation nor translates leave into cancellation',()=>{
  const s=setup();s.emit('pointerdown');s.emit('pointerleave');
  assert.deepEqual(s.calls.map(c=>c[0]),['pointer','leave']);
  s.host.stop();s.host.stop();
  assert.deepEqual(s.calls.map(c=>c[0]),['pointer','leave','reset']);
  assert.equal(s.listeners.size,0);assert.equal(s.canvas.style.cursor,'default');
  s.emit('pointerup');assert.equal(s.calls.length,3);
});
test('unqualified pointer types and malformed geometry fail before dispatch',()=>{
  const s=setup();for(const pointerType of ['touch','pen',''])s.emit('pointerdown',{pointerType});
  s.emit('pointerup',{clientX:NaN});assert.equal(s.calls.length,0);assert.equal(s.errors.length,4);
  const b=setup({rect:{left:0,top:0,width:0,height:600}});b.emit('pointerdown');
  assert.equal(b.calls.length,0);assert.match(b.errors[0],/Invalid canvas coordinates/);
});
test('malformed compiled result is never silently converted to successful transport',()=>{
  for(const response of ['not json','false','{}','{"ok":true,"cursor":"copy"}']) {
    const s=setup({response});s.emit('pointerdown');assert.equal(s.renders.length,0);
    assert.equal(s.errors.length,1);assert.equal(s.host.events.at(-1).accepted,false);
  }
});
test('all exports and viewport are verified before listeners attach',()=>{
  assert.throws(()=>createDragDropHost({runtime:{}}),/Missing drag-drop transport method/);
  const runtime=Object.fromEntries(['pointer','leave','reset'].map(n=>[`drag_drop_${n}`,()=>{}]));
  for(const width of [NaN,Infinity,0,-1])assert.throws(()=>createDragDropHost({runtime,width}),/Invalid drag-drop viewport/);
});
test('transport trace is bounded and untrusted status is retained rather than upgraded',()=>{
  const s=setup();for(let i=0;i<230;i++)s.emit('pointermove',{isTrusted:false,button:-1});
  assert.equal(s.host.events.length,200);assert(s.host.events.every(e=>e.trusted===false));
  assert.equal(s.calls.length,230);
});
test('source contract excludes host payload state geometry hit testing and synthetic input',async()=>{
  const source=await readFile(new URL('../moonbit/site/drag-drop-host.mjs',import.meta.url),'utf8');
  for(const forbidden of [/Math\.hypot/,/dispatchEvent\(/,/new PointerEvent/,/setPointerCapture/,
    /releasePointerCapture/,/\.drop_on\s*=/,/payload\s*=/,/sourceId\s*=/,/targetId\s*=/,/kind\s*===?\s*['"]drag/])
    assert.doesNotMatch(source,forbidden);
  const host=await readFile(new URL('../moonbit/site/host.mjs',import.meta.url),'utf8');
  assert.match(host,/drag_drop:\s*'\.\/drag_drop\.mjs'/);
  assert.match(host,/createDragDropHost\(\{runtime,canvas,render\}\)/);
});
