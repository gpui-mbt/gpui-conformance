// Reopen original Canvas PNG + separately sampled RGBA sidecars, never rewritten
// or composited screenshots. Independent of the frozen Rust pair comparators.
import assert from 'node:assert/strict';
import {readFileSync,lstatSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {verifyCanvasCapture,captureIdentity} from './anchor-live-capture.mjs';
export function verifyLiveCaptures(report,read) {
  assert.equal(report.status,'passed');assert.equal(report.image_kind,'canvas_export');assert.equal(report.composited_page_screenshots,false);
  assert.equal(report.captures?.length,6,'Six state-bound Canvas exports are required');
  const expected=[['ordinary-iframe-dpr2',800,600,2,-1,'ordinary iframe startup'],
    ['fractional-dpr-clipped',322,713,1.25,-1,'fractional DPR and rounded backing store'],
    ['maximum-width-popup',4096,600,1,2,'maximum live width'],
    ['restored-750-dpr1-3',750,600,1,-1,'restore original comparison profile'],
    ['restored-480-dpr1-4',480,600,1,-1,'restore original comparison profile'],
    ['restored-750-dpr1-5',750,600,1,-1,'restore original comparison profile']];
  return report.captures.map((capture,index)=>{
    const [name,width,height,scale,hovered,operation]=expected[index];
    assert.equal(capture.file,`${name}.canvas.png`);assert.equal(capture.raw,`${name}.canvas.rgba`);
    assert.equal(capture.kind,'canvas_export');assert.equal(capture.composited_page_screenshot,false);
    const state=structuredClone(report.states.find(s=>s.operation===operation&&s.width===width&&s.height===height&&s.scale===scale));
    assert(state,'Capture must bind to an independently recorded live state');
    let samples=[];
    if(hovered===2) {
      state.frame=report.inputs.find(i=>i.operation==='maximum-width rightmost popup')?.frame;
      assert(state.frame);samples=report.shadow_probe.samples;
      assert.deepEqual({width:report.shadow_probe.width,height:report.shadow_probe.height,scale:report.shadow_probe.scale},{width,height,scale});
      const popup=state.frame.snapshot.items.find(item=>item.id===200).bounds;
      const button=state.frame.snapshot.items.find(item=>item.id===12).bounds;
      assert.deepEqual(samples.map(({kind,x,y})=>({kind,x,y})),[
        {kind:'blank8',x:8,y:popup.y+popup.height/2},{kind:'blank64',x:64,y:popup.y+popup.height/2},
        {kind:'button',x:button.x+12,y:button.y+12},{kind:'popup',x:popup.x+3,y:popup.y+3}]);
      assert.deepEqual(samples[0].rgba,[255,255,255,255]);assert.deepEqual(samples[1].rgba,[255,255,255,255]);
      assert.deepEqual(samples[2].rgba,[0,0,0,255]);assert.equal(samples[3].rgba[3],255);assert(samples[3].rgba.slice(0,3).every(v=>v<=90));
    }
    assert.equal(state.frame.anchor.hovered,hovered);
    assert.deepEqual(captureIdentity(capture.before),captureIdentity(state),'Capture before-state differs from recorded viewport/hover state');
    const checked=verifyCanvasCapture({before:capture.before,after:capture.after,expected:state,
      png:read(capture.file),rgba:read(capture.raw),samples});
    for(const [key,value] of Object.entries(checked))assert.deepEqual(capture[key],value,`Recomputed capture field ${key}`);
    return {file:capture.file,...checked};
  });
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href) {
  assert.equal(process.argv.length,3,'Usage: verify-anchor-live-captures.mjs live-evidence-directory');
  const root=resolve(process.argv[2]);
  const read=name=>{assert(/^[a-z0-9-]+\.canvas\.(png|rgba)$/.test(name));const p=join(root,name),stat=lstatSync(p);
    assert(stat.isFile()&&!stat.isSymbolicLink()&&stat.nlink===1&&stat.size>0&&stat.size<=33554432*4,'Original bounded regular capture file required');return readFileSync(p);};
  const report=JSON.parse(readFileSync(join(root,'live-regression.json')));
  console.log(JSON.stringify({status:'verified_canvas_exports',captures:verifyLiveCaptures(report,read)},null,2));
}
