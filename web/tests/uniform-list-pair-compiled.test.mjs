import test from 'node:test';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {assertCandidateScene} from './uniform-list-pair-comparator.mjs';
const path=process.env.UNIFORM_LIST_RUNTIME;
test('actual compiled candidate lifecycle, scroll, stable labels, clip and extent', {skip:!path}, async()=>{
  const runtime=await import(pathToFileURL(path));const widths=Array.from({length:50},(_,i)=>42+i%4);
  const metrics={widths,prefixes:widths.map((w,i)=>Array.from({length:`Item ${i+1}`.length+1},(_,j)=>j*w/`Item ${i+1}`.length)),
    advances:widths.map((w,i)=>Array(`Item ${i+1}`.length).fill(w/`Item ${i+1}`.length)),shaping_mode:'geometricPrecision',raster_mode:'auto',kerning:'normal'};
  runtime.uniform_list_reset();const render=()=>JSON.parse(runtime.uniform_list_frame(widths,metrics.prefixes,metrics.advances,1));
  const first=render();assertCandidateScene(first,{pitch:26},0,metrics);
  for(const [dx,dy,offset] of [[0,25,25],[0,1,26],[0,1,27],[0,-27,0],[25,0,25],
    [0,-25,0],[130,25,25],[0,100000,1000],[0,100000,1000],[0,-1,999],[0,1,1000],[0,-100000,0]]) {
    assert.equal(runtime.uniform_list_wheel(150,150,dx,dy),true);
    const frame=render();assertCandidateScene(frame,{pitch:26},offset,metrics);
  }
  assert.equal(runtime.uniform_list_wheel(300,150,0,1),false);
  assert.equal(runtime.uniform_list_wheel(150,300,0,1),false);
  assert.deepEqual(render(),first);
  assert.equal(runtime.uniform_list_frame([1],[],[],1),'{"ok":false,"error":"invalid_metrics"}');
  assert.equal(runtime.uniform_list_wheel(150,150,Infinity,0),false);
});
