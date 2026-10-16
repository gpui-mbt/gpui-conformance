import test from 'node:test';
import assert from 'node:assert/strict';
import {createScrollableHost} from '../moonbit/site/scrollable-host.mjs';

function fixture() {
  const canvas = new EventTarget(), calls = [], errors = [];
  let renders = 0, accepted = true;
  canvas.getBoundingClientRect = () => ({left:20,top:40,width:250,height:250});
  const runtime = Object.fromEntries(['pointer','leave','wheel'].map(type =>
    [`scrollable_${type}`, (...args) => { calls.push({type,args}); return accepted; }]));
  const host = createScrollableHost({runtime,canvas,render:() => renders++,onError:error => errors.push(error.message)});
  const fire = (type, values = {}) => {
    const event = new Event(type,{cancelable:true});
    Object.assign(event,{clientX:70,clientY:90,deltaMode:0,deltaX:0,deltaY:0,...values});
    canvas.dispatchEvent(event); return event;
  };
  return {canvas,calls,errors,host,fire,get renders(){return renders;},reject(){accepted=false;}};
}

test('pointer and leave transport call MoonBit using canvas-relative logical coordinates', () => {
  const f=fixture(); f.fire('pointermove'); f.fire('pointerleave');
  assert.deepEqual(f.calls,[{type:'pointer',args:[100,100]},{type:'leave',args:[]}]);
  assert.equal(f.renders,2);
});
test('pixel wheel forwards both signed axes unchanged for core dominant-axis routing', () => {
  const f=fixture(); const event=f.fire('wheel',{deltaX:-12,deltaY:7,shiftKey:true});
  assert(event.defaultPrevented);
  assert.deepEqual(f.calls,[{type:'wheel',args:[100,100,-12,7]}]);
  assert.equal(f.renders,1);
});
test('repeated wheel forwarding does not accumulate, clamp or invent scroll state in JS', () => {
  const f=fixture(); for(let i=0;i<4;i++)f.fire('wheel',{deltaX:100000,deltaY:0});
  assert.equal(f.calls.length,4);
  assert(f.calls.every(call => JSON.stringify(call.args)==='[100,100,100000,0]'));
  assert.deepEqual(Object.keys(f.host).sort(),['events','stop']);
});
test('nonpixel and nonfinite deltas fail explicitly without a candidate mutation', () => {
  const f=fixture(); for(const values of [{deltaMode:1},{deltaMode:2},{deltaX:NaN},{deltaY:Infinity}]) {
    assert(f.fire('wheel',values).defaultPrevented);
  }
  assert.equal(f.errors.length,4); assert.deepEqual(f.calls,[]); assert.equal(f.renders,0);
});
test('invalid canvas geometry and pointer coordinates cannot reach MoonBit', () => {
  const f=fixture(); f.fire('pointermove',{clientX:NaN});
  f.canvas.getBoundingClientRect=()=>({left:0,top:0,width:0,height:500}); f.fire('wheel',{deltaY:12});
  assert.equal(f.errors.length,2); assert.deepEqual(f.calls,[]);
});
test('core rejection does not render and stop removes every transport listener', () => {
  const f=fixture(); f.reject(); f.fire('wheel',{deltaY:12});
  assert.equal(f.renders,0); assert.equal(f.host.events[0].accepted,false);
  f.host.stop(); f.fire('wheel',{deltaY:12}); f.fire('pointermove'); f.fire('pointerleave');
  assert.equal(f.calls.length,1);
});
test('transport diagnostics are bounded and are not authoritative scroll state', () => {
  const f=fixture(); for(let i=0;i<210;i++)f.fire('pointermove');
  assert.equal(f.host.events.length,200); assert.equal(f.calls.length,210);
  assert(f.host.events.every(entry => !('offset' in entry) && !('bounds' in entry)));
});
