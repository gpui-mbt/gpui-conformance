import test from 'node:test';
import assert from 'node:assert/strict';
import {drawFrame,validateFrame} from '../moonbit/site/render.mjs';
const item = (id,opacity) => ({id,kind:'quad',bounds:{x:0,y:0,width:20,height:20},
  color:{red:0,green:128,blue:0,alpha:255},opacity});
const frame = items => ({ok:true,conformance:'unverified',snapshot:{schema_version:1,items},decorations:[]});

test('the host applies precise scene opacity independently for every primitive', () => {
  const assignments=[],fills=[],target={globalAlpha:1};
  const context=new Proxy(target,{
    get:(object,key) => key==='fill' ? () => fills.push(object.globalAlpha) : () => {},
    set:(object,key,value) => {object[key]=value;if(key==='globalAlpha')assignments.push(value);return true;},
  });
  drawFrame(context,frame([item(1,.05),item(2,.1),item(3,.2),item(4,1),item(5,0),item(6,undefined)]),{width:500,height:500},1);
  assert.deepEqual(assignments,[.05,.1,.2,1,0,1]);
  assert.deepEqual(fills,[.05,.1,.2,1,0,1]);
});
test('invalid scene opacity is rejected before drawing, including null and numeric strings', () => {
  for(const opacity of [-.1,1.1,NaN,Infinity,null,'0.1']) {
    assert.throws(() => validateFrame(frame([item(1,opacity)])),/opacity/);
    let calls=0;
    assert.throws(() => drawFrame(new Proxy({}, {get:()=>()=>calls++}),frame([item(1,opacity)]),{width:500,height:500},1));
    assert.equal(calls,0);
  }
});
