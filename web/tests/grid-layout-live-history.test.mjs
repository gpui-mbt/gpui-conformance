import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {prepareHistoryDprProbe} from './grid-layout-live-history.mjs';

// Synthetic browser transport model only. Actual navigation remains a CI gate.
function fixture(width=800,height=600,scale=2,bfcache=false) {
  const calls=[],canvas={},error={hidden:true},root={dataset:{runtimeStatus:'ready'}};
  const sandbox={innerWidth:width,innerHeight:height,devicePixelRatio:scale,liveGridHistoryMarker:bfcache,
    document:{documentElement:root,querySelector:()=>canvas,getElementById:()=>error}};
  function setMetrics(w,h,d) {
    Object.assign(sandbox,{innerWidth:w,innerHeight:h,devicePixelRatio:d});
    Object.assign(canvas,{width:Math.round(w*d),height:Math.round(h*d),hidden:false});
    sandbox.gpuiExample={metadata:{width:w,height:h},scale:d,frame:{conformance:'unverified',grid_layout:{query_size:{width:w,height:h}},snapshot:{scale:d}}};
  }
  setMetrics(500,500,1);const restored=structuredClone(sandbox.gpuiExample.frame);setMetrics(width,height,scale);
  const evaluate=fn=>vm.runInNewContext(`(${fn.toString()})()`,sandbox);
  const frame={waitForFunction:async fn=>{calls.push('wait');assert.equal(evaluate(fn),true,'Expected browser state must actually be established before waiting');},evaluate:async fn=>structuredClone(evaluate(fn))};
  const page={},replacement={send:async(method,metrics)=>{calls.push(['send',method,metrics]);setMetrics(metrics.width,metrics.height,metrics.deviceScaleFactor);}};
  const cdp={detach:async()=>calls.push('detach')};
  const context={newCDPSession:async p=>{assert.equal(p,page);calls.push('session');return replacement;}};
  return {frame,page,context,cdp,restored,replacement,calls,canvas,sandbox,onAttempt:state=>calls.push(['attempt',state])};
}

test('history return may restore initial context metrics before explicit probe baseline',async()=>{
  for(const [width,height,scale,bfcache] of [[800,600,2,false],[800,600,2,true],[500,500,1,true]]) {
    const f=fixture(width,height,scale,bfcache);
    const result=await prepareHistoryDprProbe(f);
    assert.equal(result.history.bfcache_restored,bfcache);
    assert.deepEqual(result.history.returned.canvas,[width*scale,height*scale]);
    assert.equal(result.history.returned.width,width);assert.equal(result.history.returned.scale,scale);
    assert.equal(result.cdp,f.replacement);
    assert.deepEqual(f.calls.map(c=>Array.isArray(c)?c[0]:c),['wait','detach','session','attempt','send','wait']);
    assert.deepEqual(f.calls.find(c=>c[0]==='send'),['send','Emulation.setDeviceMetricsOverride',{width:500,height:500,deviceScaleFactor:1,mobile:false}]);
    assert.deepEqual(f.sandbox.gpuiExample.frame,f.restored);
  }
});

test('history probe rejects incoherent returned output instead of resetting past a real failure',async()=>{
  for(const corrupt of [f=>{f.sandbox.gpuiExample.scale=1;},f=>{f.canvas.width=500;}]) {
    const f=fixture();corrupt(f);
    await assert.rejects(prepareHistoryDprProbe(f));
    assert(!f.calls.includes('detach'),'Must validate restored output before replacing device metrics');
  }
});
