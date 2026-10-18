import test from 'node:test';
import assert from 'node:assert/strict';
import {drawFrame,validateFrame} from '../moonbit/site/render.mjs';

// Recorder tests of the explicit Canvas approximation, not a pixel comparison.
function frame() {
  return {ok:true,conformance:'unverified',snapshot:{schema_version:1,items:[
    {id:2,kind:'quad',bounds:{x:20,y:20,width:400,height:500},color:{red:80,green:80,blue:80,alpha:255},opacity:.8},
    {id:10,kind:'quad',bounds:{x:20,y:20,width:400,height:97},color:{red:255,green:255,blue:255,alpha:255}},
    {id:1000,kind:'text_run',bounds:{x:21,y:21,width:398,height:26},text_origin:{x:21,y:21},transform:{a:1,b:0,c:0,d:1,tx:0,ty:0},
      color:{red:0,green:0,blue:0,alpha:255},font_size:16,text:'Header — 400px'},
  ]},decorations:[{id:10,radius:6,border:'#ffffff',border_width:1,border_style:'dashed'}],shadows:[{id:2,kind:'shadow_lg'}]};
}
function recorder() {
  const calls=[],paints=[],stack=[],state={shadowColor:'transparent',shadowBlur:0,shadowOffsetX:0,shadowOffsetY:0};
  const context=new Proxy(state,{
    get:(object,key)=>key==='save'?()=>stack.push({...object}):key==='restore'?()=>{
      const previous=stack.pop();for(const name of Object.keys(object))delete object[name];Object.assign(object,previous);
    }:key==='measureText'?()=>({fontBoundingBoxAscent:16,fontBoundingBoxDescent:4}):(...args)=>{
      calls.push([key,...args]);
      if(key==='roundRect')object.rectangle=args;
      if(key==='rect')object.mask=args;
      if(['fill','stroke','fillText'].includes(key))paints.push({kind:key,args,...object});
    },
    set:(object,key,value)=>{object[key]=value;return true;},
  });return {context,calls,paints};
}
const metadata={width:500,height:600,font_family:'IBM Plex Sans'};

test('shadow_lg retains both pinned source layers, signed spread and black alpha .1',()=>{
  const f=frame(),r=recorder();drawFrame(r.context,f,metadata,1);
  const shadows=r.paints.filter(paint=>paint.kind==='fill'&&paint.shadowBlur>0);
  assert.deepEqual(shadows.map(paint=>[paint.shadowColor,paint.shadowOffsetX,paint.shadowOffsetY,paint.shadowBlur,paint.globalAlpha]),[
    ['rgba(0,0,0,.1)',4096,10,15,.8],['rgba(0,0,0,.1)',4096,4,6,.8],
  ]);
  assert.deepEqual(shadows.map(paint=>paint.rectangle),[[23-4096,23,394,494,0],[24-4096,24,392,492,0]]);
  assert(r.paints.indexOf(shadows[1])<r.paints.findIndex(paint=>paint.fillStyle==='rgba(80,80,80,1)'&&paint.shadowBlur===0));
  for(const paint of r.paints.filter(paint=>paint.shadowBlur===0)) {
    assert.equal(paint.shadowOffsetX,0);assert.equal(paint.shadowOffsetY,0);
  }
});

test('source layer lengths scale independently of caster paths and retain viewport mask',()=>{
  const r=recorder();drawFrame(r.context,frame(),metadata,2);
  const shadows=r.paints.filter(paint=>paint.kind==='fill'&&paint.shadowBlur>0);
  assert.deepEqual(shadows.map(paint=>[paint.shadowOffsetX,paint.shadowOffsetY,paint.shadowBlur]),[[8192,20,30],[8192,8,12]]);
  assert.deepEqual(shadows.map(paint=>paint.rectangle),[[23-4096,23,394,494,0],[24-4096,24,392,492,0]]);
  assert.deepEqual(r.calls.find(call=>call[0]==='rect'),['rect',0,0,500,600]);
});

test('Block label uses provided top-left border inset with normal line-height baseline',()=>{
  const r=recorder();drawFrame(r.context,frame(),metadata,1);
  const text=r.paints.find(paint=>paint.kind==='fillText');
  assert.deepEqual(text.args,['Header — 400px',21,40]);
  assert.equal(text.textAlign,'left');assert.equal(text.textBaseline,'alphabetic');
  assert.equal(text.shadowBlur,0);assert.equal(text.globalAlpha,1);
  assert(r.calls.some(call=>call[0]==='arc'),'Source dashed rounded border remains explicit');
});

test('new preset rejects unsupported shape opacity options and degenerate casters atomically',()=>{
  for(const mutate of [
    f=>{f.shadows[0].kind='shadow_xl';},f=>{f.shadows[0].blur=15;},
    f=>{f.shadows[0].element_opacity=.8;},f=>{f.shadows[0].id=1000;},
    f=>{f.shadows.push({...f.shadows[0]});},f=>{f.snapshot.items[0].bounds.width=8;},
    f=>{f.snapshot.items[0].bounds.height=7;},f=>{f.conformance='pass';},
  ]) {
    const f=frame(),r=recorder();mutate(f);
    assert.throws(()=>drawFrame(r.context,f,metadata,1));assert.equal(r.calls.length,0);
  }
  const f=frame();f.snapshot.items[0].bounds.width=9;assert.doesNotThrow(()=>validateFrame(f));
});
