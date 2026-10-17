import assert from 'node:assert/strict';

// Test-harness transport only; this does not drive or synthesize application events.
export async function prepareHistoryDprProbe({frame,page,context,cdp,restored,onAttempt}) {
  // Navigation may restore the browser context's initial device metrics rather
  // than the preceding CDP override. First verify the actual returned viewport.
  await frame.waitForFunction(()=>document.documentElement.dataset.runtimeStatus==='ready'&&globalThis.gpuiExample?.metadata.width===innerWidth&&globalThis.gpuiExample?.metadata.height===innerHeight&&globalThis.gpuiExample?.scale===devicePixelRatio);
  const history=await frame.evaluate(()=>({bfcache_restored:globalThis.liveGridHistoryMarker===true,returned:{width:innerWidth,height:innerHeight,scale:devicePixelRatio,canvas:[document.querySelector('canvas').width,document.querySelector('canvas').height],canvasHidden:document.querySelector('canvas').hidden,errorHidden:document.getElementById('error').hidden,query:globalThis.gpuiExample.frame.grid_layout.query_size,conformance:globalThis.gpuiExample.frame.conformance}}));
  const returned=history.returned;
  assert.deepEqual(returned.canvas,[Math.round(returned.width*returned.scale),Math.round(returned.height*returned.scale)]);
  assert.equal(returned.canvasHidden,false);assert.equal(returned.errorHidden,true);
  assert.equal(returned.conformance,'unverified');
  // Bind a fresh CDP session to the returned page and explicitly declare the
  // next baseline. This changes browser metrics; it never dispatches resize.
  await cdp.detach();cdp=await context.newCDPSession(page);
  onAttempt({operation:'history_return_baseline',width:500,height:500,scale:1});
  await cdp.send('Emulation.setDeviceMetricsOverride',{width:500,height:500,deviceScaleFactor:1,mobile:false});
  await frame.waitForFunction(()=>innerWidth===500&&innerHeight===500&&devicePixelRatio===1&&globalThis.gpuiExample?.metadata.width===500&&globalThis.gpuiExample?.metadata.height===500&&globalThis.gpuiExample?.scale===1);
  assert.deepEqual(await frame.evaluate(()=>globalThis.gpuiExample.frame),restored);
  return {cdp,history};
}
