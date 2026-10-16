import test from 'node:test';
import assert from 'node:assert/strict';
import {drawFrame,validateFrame} from '../moonbit/site/render.mjs';
const frame=()=>({ok:true,conformance:'unverified',snapshot:{schema_version:1,items:[
  {id:20,kind:'quad',bounds:{x:16,y:280,width:380,height:40},color:{red:0,green:0,blue:0,alpha:255},opacity:1},
  {id:60,kind:'text',bounds:{x:170,y:287,width:70,height:26},font_size:16,text:'Button 1',color:{red:255,green:255,blue:255,alpha:255},opacity:1},
]},decorations:[{id:20,radius:0,border:'#0000ff',border_width:3,border_style:'solid'}],shadows:[{id:20,kind:'shadow_sm'}]});
function recorder() {
  const calls=[],states=[],stack=[];
  let path=[];
  const state={shadowColor:'transparent',shadowBlur:0,shadowOffsetX:0,shadowOffsetY:0};
  const context=new Proxy(state,{
    get:(object,key)=>key==='save'?()=>stack.push({...object}):key==='restore'?()=>{const old=stack.pop();for(const name of Object.keys(object))delete object[name];Object.assign(object,old);}:
      key==='measureText'?()=>({actualBoundingBoxAscent:12,actualBoundingBoxDescent:4}):
      (...args)=>{
        calls.push([key,...args]);
        if(key==='beginPath')path=[];
        if(['rect','roundRect'].includes(key))path.push([key,...args]);
        if(key==='clip')object.clips=[...(object.clips||[]),...path];
        if(['fill','stroke','fillText'].includes(key))states.push({kind:key,...object,path:path.map(part=>[...part])});
      },
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
    f=>f.decorations[0].border_width=2.5,f=>f.decorations[0].border_style='dashed',f=>f.snapshot.items[0].bounds.height=5,f=>f.decorations[0].shadow=true]) {
    const f=frame();mutation(f);let calls=0;
    assert.throws(()=>drawFrame(new Proxy({}, {get:()=>()=>calls++}),f,{width:800,height:600},1));assert.equal(calls,0);
  }
});
test('solid3px requires6px extent while existing1px dashed and4px solid stay accepted',()=>{
  const f=frame();f.shadows=[];f.snapshot.items[0].bounds.height=6;assert.doesNotThrow(()=>validateFrame(f));
  // Solid2px is now explicitly supported for drag_drop; fractional widths are not.
  for(const width of [1,2,4]){const old=frame();old.shadows=[];old.decorations[0].border_width=width;old.decorations[0].radius=6;old.decorations[0].border_style=width===1?'dashed':'solid';assert.doesNotThrow(()=>validateFrame(old));}
  for(const width of [0,2.5,5,-1,NaN,Infinity,'3',null]){const bad=frame();bad.decorations[0].border_width=width;assert.throws(()=>validateFrame(bad));}
});

// Real source groups have zero-gap opaque siblings. The shadow's blur tail
// overlaps a prior sibling although its ordering rectangle does not.
function siblings({gap=0, overlap=0, clipped=false}={}) {
  const f=frame();
  f.snapshot.items.unshift({id:1,kind:'quad',bounds:{x:0,y:0,width:800,height:600},color:{red:255,green:255,blue:255,alpha:255}});
  f.snapshot.items[1].bounds={x:16,y:332,width:768,height:40};
  f.snapshot.items[2].bounds={x:350,y:339,width:100,height:26};
  f.snapshot.items.push({id:21,kind:'quad',bounds:{x:16,y:372+gap-overlap,width:768,height:40},color:{red:0,green:0,blue:0,alpha:255},opacity:.7});
  f.decorations.push({id:21,radius:0,border:'#000000',border_width:1,border_style:'solid'});
  f.shadows.push({id:21,kind:'shadow_sm'});
  if(clipped) {
    f.snapshot.clip_chains=[{id:9,rects:[{x:16,y:372,width:768,height:40}]}];
    f.snapshot.items.at(-1).clip_chain_id=9;
  }
  return f;
}
const metadata={width:800,height:600,font_family:'IBM Plex Sans'};
const isShadow=state=>state.kind==='fill'&&state.shadowBlur>0;
const focusedStroke=states=>states.findIndex(state=>state.kind==='stroke'&&state.strokeStyle==='#0000ff');
const secondShadows=(states,y)=>states.map((state,index)=>({state,index})).filter(({state})=>
  isShadow(state)&&state.path[0]?.[2]>=y&&state.path[0]?.[2]<=y+1);

test('zero-gap source sibling shadows precede the previous exact-blue border without repainting',()=>{
  const r=recorder();drawFrame(r.context,siblings(),metadata,1);
  const later=secondShadows(r.states,372),focus=focusedStroke(r.states);
  assert.equal(later.length,2);
  for(const {index} of later)assert(index<focus,'later sibling shadow must not paint over the earlier focus stroke');
  assert.equal(r.states.filter(state=>state.kind==='stroke'&&state.strokeStyle==='#0000ff').length,1);
  assert.equal(r.states[focus].shadowBlur,0);
  assert.deepEqual(r.states[focus].path,[['roundRect',17.5,333.5,765,37,0]]);
  assert.equal(r.states[focus].strokeStyle,'#0000ff');
});

test('overlapping source shadow rectangles retain later-on-top interleaving',()=>{
  const r=recorder();drawFrame(r.context,siblings({overlap:10}),metadata,1);
  const later=secondShadows(r.states,362),focus=focusedStroke(r.states);
  assert.equal(later.length,2);
  for(const {index} of later)assert(index>focus,'an intersecting later shadow cannot be moved to a global shadow prepass');
});

test('non-adjacent source controls retain both shadow layers and stable source ties',()=>{
  const r=recorder();drawFrame(r.context,siblings({gap:12}),metadata,1);
  assert.deepEqual(r.states.filter(isShadow).map(state=>[state.path[0][2],state.shadowBlur]),[[332,3],[384,3],[333,2],[385,2]]);
  assert.deepEqual(r.states.filter(state=>state.kind==='stroke').map(state=>state.strokeStyle),['#0000ff','#000000']);
});

test('clipped ordering rectangles remove false overlaps while preserving actual Canvas masks',()=>{
  const r=recorder();drawFrame(r.context,siblings({overlap:10,clipped:true}),metadata,2);
  const later=secondShadows(r.states,362),focus=focusedStroke(r.states);
  assert.equal(later.length,2);
  for(const {state,index} of later) {
    assert(index<focus,'the clipped ordering box touches but does not overlap the previous sibling');
    assert.deepEqual(state.clips,[['rect',0,0,800,600],['rect',16,372,768,40]]);
    assert.equal(state.globalAlpha,.7);assert.equal(state.shadowOffsetX,8192);assert.equal(state.shadowOffsetY,2);
  }
});

test('a fully clipped source caster emits no blur-only paint command',()=>{
  const f=frame();f.snapshot.clip_chains=[{id:7,rects:[{x:0,y:0,width:800,height:279}]}];
  for(const item of f.snapshot.items)item.clip_chain_id=7;
  const r=recorder();drawFrame(r.context,f,metadata,1);
  assert.equal(r.states.length,0);
});

test('unsupported source shadow combinations fail atomically',()=>{
  for(const mutate of [
    f=>{f.scroll={first_id:20,top:0,height:600,y:0,max:0};},
    f=>{f.snapshot.items[0].transform={a:1,b:0,c:0,d:1,tx:1,ty:0};},
    f=>{f.snapshot.items[1].transform={a:1,b:1,c:0,d:1,tx:0,ty:0};},
    f=>{f.snapshot.items.push({...f.snapshot.items[1]});},
    f=>{f.decorations.push({id:21,radius:0,border:'#000000',border_width:1,border_style:'solid',shadow:true});},
  ]) {
    const f=siblings();mutate(f);const r=recorder();
    assert.throws(()=>drawFrame(r.context,f,metadata,1));assert.equal(r.calls.length,0);
  }
});

test('absent or empty explicit source shadows preserve the legacy snapshot paint sequence',()=>{
  for(const empty of [false,true]) {
    const f=siblings();if(empty)f.shadows=[];else delete f.shadows;
    const r=recorder();drawFrame(r.context,f,metadata,1);
    assert.equal(r.states.filter(isShadow).length,0);
    assert.deepEqual(r.states.map(state=>state.kind),['fill','fill','stroke','fillText','fill','stroke']);
  }
});

test('strict edge touching and equal-order kind ties keep shadows before opaque quads',()=>{
  const r=recorder();drawFrame(r.context,siblings({overlap:1}),metadata,1);
  const later=secondShadows(r.states,371),focus=focusedStroke(r.states);
  assert.equal(later.length,2);
  for(const {index} of later)assert(index<focus,'touching unblurred boxes do not require an above-border shadow layer');
});

test('disjoint nested fractional masks cannot manufacture an ordering rectangle',()=>{
  const f=frame();f.snapshot.clip_chains=[{id:7,rects:[
    {x:16,y:280,width:380,height:.2},{x:16,y:280.3,width:380,height:.2},
  ]}];
  for(const item of f.snapshot.items)item.clip_chain_id=7;
  const r=recorder();drawFrame(r.context,f,metadata,2);
  assert.equal(r.states.length,0);
});
