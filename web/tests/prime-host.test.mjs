import test from 'node:test';
import assert from 'node:assert/strict';
import {createPrimeHost} from '../moonbit/site/prime-host.mjs';
function fixture({throwOnCreate=false}={}) {
  const canvas=new EventTarget(); canvas.getBoundingClientRect=()=>({left:0,top:0,width:640,height:560});
  const lifecycle=new EventTarget(), workers=[], accepted=[], failed=[], actions=[];
  let renders=0;
  const runtime={hello_web_init:n=>assert.equal(n,2), hello_web_click:()=>JSON.stringify(actions.shift()||{action:'none'}),
    hello_web_receive:(...args)=>{accepted.push(args);return true;}, hello_web_fail:id=>failed.push(id)};
  const host=createPrimeHost({runtime,canvas,lifecycle,concurrency:2,now:()=>5,render:()=>renders++,onFailure:()=>{},workerFactory:()=>{
    if(throwOnCreate) throw new Error('Worker blocked');
    const worker={sent:[],stopped:false,postMessage(data){this.sent.push(data);},terminate(){this.stopped=true;}};
    workers.push(worker);return worker;
  }});
  const click=()=>{const e=new Event('click');Object.assign(e,{button:0,clientX:100,clientY:100});canvas.dispatchEvent(e);};
  const start=id=>{actions.push({action:'start',generation:id,chunks:Array.from({length:12},(_,i)=>({index:i,start:i*10,end:(i+1)*10}))});click();};
  const finish=worker=>{const data=worker.sent.at(-1);worker.onmessage({data:{...data,count:2}});};
  return {host,workers,accepted,failed,actions,start,click,finish,lifecycle,get renders(){return renders;}};
}
test('worker pool executes twelve tasks and releases every worker',()=>{
  const f=fixture();f.start(1);
  assert.equal(f.workers.length,2);
  for(let i=0;i<12;i++) f.finish(f.workers[i%2]);
  assert.equal(f.accepted.length,12);
  assert.equal(f.host.diagnostics.active,0);
  assert.equal(f.host.diagnostics.created,f.host.diagnostics.terminated);
  assert(f.workers.every(w=>w.stopped));
  f.start(2);assert.equal(f.workers.length,4);
  f.workers[0].onmessage({data:{generation:1,index:0,start:0,end:10,count:2}});
  assert.equal(f.accepted.length,12);
  f.host.stop();assert.equal(f.host.diagnostics.active,0);
});
test('pagehide terminates active work and queued late responses cannot render or mutate state',()=>{
  const f=fixture();f.start(1);const before=f.renders;
  f.lifecycle.dispatchEvent(new Event('pagehide'));
  f.finish(f.workers[0]);f.click();
  assert.equal(f.accepted.length,0);assert.equal(f.renders,before);
  assert(f.workers.every(w=>w.stopped));
  assert.equal(f.host.diagnostics.active,0);
});
test('unavailable workers and malformed/duplicate responses fail visibly and release the pool',()=>{
  const missing=fixture({throwOnCreate:true});missing.start(1);
  assert.deepEqual(missing.failed,[1]);assert.equal(missing.host.diagnostics.active,0);
  const f=fixture();f.start(1);
  const first=f.workers[0].sent[0];f.finish(f.workers[0]);
  f.workers[0].onmessage({data:{...first,count:2}});
  assert.equal(f.accepted.length,1);assert.deepEqual(f.failed,[1]);
  assert(f.workers.every(w=>w.stopped));assert.equal(f.host.diagnostics.active,0);
});
test('repeated clicks that MoonBit ignores create no additional tasks',()=>{
  const f=fixture();f.start(1);for(let i=0;i<20;i++) f.click();
  assert.equal(f.workers.length,2);assert.equal(f.accepted.length,0);f.host.stop();
});
