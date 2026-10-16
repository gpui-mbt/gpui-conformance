import test from 'node:test';
import assert from 'node:assert/strict';
import {drawFrame,validateFrame} from '../moonbit/site/render.mjs';
const frame=()=>({ok:true,conformance:'unverified',snapshot:{schema_version:1,items:[
  {id:20,kind:'quad',bounds:{x:16,y:280,width:380,height:40},color:{red:0,green:0,blue:0,alpha:255},opacity:1},
  {id:60,kind:'text',bounds:{x:170,y:287,width:70,height:26},font_size:16,text:'Button 1',color:{red:255,green:255,blue:255,alpha:255},opacity:1},
]},decorations:[{id:20,radius:0,border:'#0000ff',border_width:3,border_style:'solid'}],shadows:[{id:20,kind:'shadow_sm'}]});
function recorder() {
  const calls=[],states=[],stack=[];
  const state={shadowColor:'transparent',shadowBlur:0,shadowOffsetX:0,shadowOffsetY:0};
  const context=new Proxy(state,{
    get:(object,key)=>key==='save'?()=>stack.push({...object}):key==='restore'?()=>{const old=stack.pop();for(const name of Object.keys(object))delete object[name];Object.assign(object,old);}:
      key==='measureText'?()=>({actualBoundingBoxAscent:12,actualBoundingBoxDescent:4}):
      (...args)=>{calls.push([key,...args]);if(['fill','stroke','fillText'].includes(key))states.push({kind:key,...object});},
    set:(object,key,value)=>{object[key]=value;return true;},
  });
  return {context,calls,states};
}
test('source square3px border validates and strokes its inset1.5px centerline',()=>{
  const f=frame();assert.doesNotThrow(()=>validateFrame(f));
  const r=recorder();drawFrame(r.context,f,{width:800,height:600,font_family:'IBM Plex Sans'},1);
  assert.deepEqual(r.calls.filter(c=>c[0]==='roundRect').at(-1),['roundRect',17.5,281.5,377,37,0]);
  assert.equal(r.states.find(s=>s.kind==='stroke').lineWidth,3);
  assert.equal(r.states.find(s=>s.kind==='stroke').strokeStyle,'#0000ff');
});
test('source shadow_sm emits exact two declared Canvas approximation layers before fill',()=>{
  const r=recorder();drawFrame(r.context,frame(),{width:800,height:600,font_family:'IBM Plex Sans'},1);
  const fills=r.states.filter(s=>s.kind==='fill');assert.equal(fills.length,3);
  assert.deepEqual(fills.slice(0,2).map(s=>[s.shadowColor,s.shadowBlur,s.shadowOffsetX,s.shadowOffsetY]),[
    ['rgba(0,0,0,.1)',3,4096,1],['rgba(0,0,0,.1)',2,4096,1],
  ]);
  assert.deepEqual(r.calls.filter(c=>c[0]==='roundRect').slice(0,3),[
    ['roundRect',16-4096,280,380,40,0],['roundRect',17-4096,281,378,38,0],['roundRect',16,280,380,40,0],
  ]);
  for(const s of r.states.filter(s=>s.kind==='stroke'||s.kind==='fillText'||s===fills[2])) {
    assert.equal(s.shadowBlur,0);assert.equal(s.shadowOffsetX,0);assert.equal(s.shadowOffsetY,0);
  }
});
test('opacity applies to fill border and shadow layers without leaking to later text',()=>{
  const f=frame();f.snapshot.items[0].opacity=.4;
  const r=recorder();drawFrame(r.context,f,{width:800,height:600,font_family:'IBM Plex Sans'},1);
  for(const state of r.states.filter(s=>s.kind==='fill'||s.kind==='stroke'))assert.equal(state.globalAlpha,.4);
  assert.equal(r.states.find(s=>s.kind==='fillText').globalAlpha,1);
});
test('shadow lengths follow device scale independently from transformed caster paths',()=>{
  const r=recorder();drawFrame(r.context,frame(),{width:800,height:600,font_family:'IBM Plex Sans'},2);
  assert.deepEqual(r.states.filter(s=>s.kind==='fill').slice(0,2).map(s=>[s.shadowBlur,s.shadowOffsetX,s.shadowOffsetY]),[[6,8192,2],[4,8192,2]]);
});
test('new preset rejects unsupported shape and values before any draw call',()=>{
  for(const mutation of [f=>f.shadows=null,f=>f.shadows={},f=>f.shadows=[null],f=>f.shadows[0].kind='shadow_lg',
    f=>f.shadows[0].id=60,f=>f.shadows[0].blur=3,f=>f.shadows.push({...f.shadows[0]}),f=>f.snapshot.items[0].bounds.height=2,
    f=>f.decorations[0].border_width=2,f=>f.decorations[0].border_style='dashed',f=>f.snapshot.items[0].bounds.height=5,f=>f.decorations[0].shadow=true]) {
    const f=frame();mutation(f);let calls=0;
    assert.throws(()=>drawFrame(new Proxy({}, {get:()=>()=>calls++}),f,{width:800,height:600},1));assert.equal(calls,0);
  }
});
test('solid3px requires6px extent while existing1px dashed and4px solid stay accepted',()=>{
  const f=frame();f.shadows=[];f.snapshot.items[0].bounds.height=6;assert.doesNotThrow(()=>validateFrame(f));
  for(const width of [1,4]){const old=frame();old.shadows=[];old.decorations[0].border_width=width;old.decorations[0].radius=6;old.decorations[0].border_style=width===1?'dashed':'solid';assert.doesNotThrow(()=>validateFrame(old));}
  for(const width of [0,2,5,-1,NaN,Infinity,'3',null]){const bad=frame();bad.decorations[0].border_width=width;assert.throws(()=>validateFrame(bad));}
});
