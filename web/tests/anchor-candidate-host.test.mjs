import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createAnchorHost,readAnchorFrame} from '../moonbit/site/anchor-host.mjs';
test('anchor host only transports trusted mouse and measures text; teardown removes listeners',()=>{
  const listeners=new Map(),calls=[];
  const canvas={getBoundingClientRect:()=>({left:10,top:20}),addEventListener:(n,f)=>listeners.set(n,f),removeEventListener:(n,f)=>{assert.equal(listeners.get(n),f);listeners.delete(n);}};
  const h=createAnchorHost({runtime:{anchor_pointer:(...a)=>calls.push(a)},canvas,render:()=>calls.push('render')});
  listeners.get('pointermove')({isTrusted:false,pointerType:'mouse',clientX:50,clientY:60});
  listeners.get('pointermove')({isTrusted:true,pointerType:'touch',clientX:50,clientY:60});assert.equal(calls.length,0);
  listeners.get('pointermove')({isTrusted:true,pointerType:'mouse',clientX:50,clientY:60});
  listeners.get('pointerleave')({isTrusted:true,pointerType:'mouse'});
  assert.deepEqual(calls,[[40,40,true],'render',[0,0,false],'render']);assert.equal(h.events.length,2);h.stop();assert.equal(listeners.size,0);
  let input;const result=readAnchorFrame({anchor_frame:(...a)=>{input=a;return '{"ok":true}';}},{measureText:t=>({width:t.length})},{innerWidth:480,innerHeight:600,devicePixelRatio:1},{runs:[{text:'A',font_size:14}]});
  assert.deepEqual(input,[480,600,[1],1]);assert.equal(result.width,480);
  assert.throws(()=>readAnchorFrame({anchor_frame:()=>'{"ok":false,"error":"unsupported_viewport_profile"}'},{},{innerWidth:4,innerHeight:3},{runs:[]}),/unsupported_viewport_profile/);
});
test('anchor source delegates placement and routing to production core',async()=>{
  const source=await readFile(new URL('../moonbit/anchor/anchor.mbt',import.meta.url),'utf8');
  for(const required of ['Element::anchored_after','@element.Local','.deferred()','.hit_test(point)','.with_grid_children_style','.request_layout_with_device_scale','.prepaint()','.paint_snapshot(1)'])assert(source.includes(required),required);
  const host=await readFile(new URL('../moonbit/site/anchor-host.mjs',import.meta.url),'utf8');
  for(const forbidden of ['Math.min','Math.max','TopLeft','BottomRight','getImageData'])assert(!host.includes(forbidden),forbidden);
});
