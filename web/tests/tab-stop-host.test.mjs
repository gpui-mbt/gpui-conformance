import test from 'node:test';
import assert from 'node:assert/strict';
import {createTabStopHost} from '../moonbit/site/tab-stop-host.mjs';
function setup() {
  const calls=[],listeners=new Map(),children=[],renders=[];
  const input={style:{},setAttribute(){},addEventListener:(n,h)=>listeners.set(n,h),removeEventListener:n=>listeners.delete(n),focus(){},remove(){children.pop();}};
  const canvas={ownerDocument:{body:{appendChild:n=>children.push(n)},createElement:()=>input},getBoundingClientRect:()=>({left:0,top:0,width:800,height:600}),addEventListener:(n,h)=>listeners.set(n,h),removeEventListener:n=>listeners.delete(n)};
  const runtime=Object.fromEntries(['pointer','leave','key','wheel'].map(name=>[`tab_stop_${name}`,(...args)=>{calls.push([name,...args]);return true;}]));
  const host=createTabStopHost({runtime,canvas,render:()=>renders.push(true)});
  const emit=(type,props={})=>listeners.get(type)?.({isTrusted:true,pointerType:'mouse',clientX:395,clientY:300,button:0,key:'Tab',shiftKey:false,ctrlKey:false,altKey:false,metaKey:false,repeat:false,deltaMode:0,deltaX:0,deltaY:10,preventDefault(){},...props});
  return {host,calls,listeners,children,renders,emit};
}
test('tab-stop adapter forwards unchanged shared input transport into compiled exports',()=>{
  const s=setup();s.emit('pointerdown');s.emit('pointerup');s.emit('keydown',{shiftKey:true});s.emit('pointerleave');s.emit('wheel');
  assert.deepEqual(s.calls,[['pointer','down',395,300,0,false,false,false,false],['pointer','up',395,300,0,false,false,false,false],['key','Tab',true,true,false,false,false,false],['leave'],['wheel',395,300,0,10]]);
  assert.deepEqual(Object.keys(s.host).sort(),['events','stop']);assert(!s.listeners.has('click'));assert(!s.listeners.has('blur'));assert.equal(s.renders.length,5);
  s.host.stop();assert.equal(s.listeners.size,0);assert.equal(s.children.length,0);
});
test('actual beforeinput carries its own core Enter pair without host activation or geometry state',()=>{
  const s=setup();s.emit('keydown',{key:'Enter',shiftKey:true});s.emit('beforeinput',{inputType:'insertLineBreak',isComposing:false});s.emit('keyup',{key:'Enter',shiftKey:true});
  assert.deepEqual(s.calls,[['key','Enter',true,true,false,false,false,false],['key','Enter',true,false,false,false,false,false],['key','Enter',false,false,false,false,false,false],['key','Enter',false,true,false,false,false,false]]);
  s.emit('keydown',{key:'Shift'});assert.equal(s.calls.length,4);
});
test('missing compiled exports fail before creating browser transport',()=>{
  assert.throws(()=>createTabStopHost({runtime:{}}),/Missing tab-stop transport method/);
});
