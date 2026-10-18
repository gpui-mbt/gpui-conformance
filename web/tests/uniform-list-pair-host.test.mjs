import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createUniformListHost} from '../moonbit/site/uniform-list-host.mjs';
function fixture(){
  const canvas=new EventTarget(),calls=[],errors=[];let renders=0,accepted=true;
  canvas.getBoundingClientRect=()=>({left:20,top:40,width:150,height:150});
  const runtime={uniform_list_wheel(...args){calls.push(['wheel',...args]);return accepted;},
    uniform_list_pointer(...args){calls.push(['pointer',...args]);return accepted;}};
  const host=createUniformListHost({runtime,canvas,render:()=>renders++,onError:error=>errors.push(error.message)});
  const fire=(kind,values={})=>{const event=new Event(kind,{cancelable:true});
    Object.assign(event,{clientX:70,clientY:90,deltaMode:0,deltaX:0,deltaY:0,button:0,...values});canvas.dispatchEvent(event);return event;};
  return {canvas,calls,errors,host,fire,get renders(){return renders;},reject(){accepted=false;}};
}
test('both raw signed wheel axes reach compiled core unchanged',()=>{
  const f=fixture();assert(f.fire('wheel',{deltaX:130,deltaY:25}).defaultPrevented);
  f.fire('wheel',{deltaX:25,deltaY:0});f.fire('wheel',{deltaY:-100000});
  assert.deepEqual(f.calls,[['wheel',100,100,130,25],['wheel',100,100,25,0],['wheel',100,100,0,-100000]]);
});
test('pointer delivery transports coordinates/button and never selects a row',()=>{
  const f=fixture();f.fire('pointerdown');f.fire('pointerup',{button:2});
  assert.deepEqual(f.calls,[['pointer','down',100,100,0],['pointer','up',100,100,2]]);
});
test('nonpixel/invalid geometry rejected and core rejection does not render',()=>{
  const f=fixture();f.fire('wheel',{deltaMode:1});f.fire('wheel',{deltaY:Infinity});f.fire('pointerdown',{clientX:NaN});
  assert.equal(f.errors.length,3);assert.equal(f.calls.length,0);f.reject();f.fire('wheel',{deltaY:1});assert.equal(f.renders,0);
  f.host.stop();f.fire('wheel',{deltaY:1});assert.equal(f.calls.length,1);
});
test('shared host registers candidate while retaining historical modules and dispatch',()=>{
  const source=readFileSync(new URL('../moonbit/site/host.mjs',import.meta.url),'utf8');
  assert(source.includes("uniform_list: './uniform_list.mjs'"));
  for(const name of ['drag_drop','tab_stop','focus_visible','scrollable','tree','text_layout','text_wrapper','hello_web','input','dynamic_fonts'])
    assert(source.includes(`${name}: './${name}.mjs'`));
  assert(source.includes('runtime[example + \'_frame\'](width, scale)'));
  const host=readFileSync(new URL('../moonbit/site/uniform-list-host.mjs',import.meta.url),'utf8');
  assert(!/Math\.(floor|ceil|min|max)|scrollY|offset\s*=|range\s*=/.test(host));
});
