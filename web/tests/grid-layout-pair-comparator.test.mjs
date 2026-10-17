// SYNTHETIC UNIT INPUTS ONLY; never Rust/browser evidence or executed faults.
import test from 'node:test';
import assert from 'node:assert/strict';
import {pixels,frame} from './fixtures/grid-layout-fixtures.mjs';
import {VIEWPORT_SEQUENCE,COLORS} from './grid-layout-comparator.mjs';
import {comparePairImages,pairNegativeControls,TOLERANCES,NOT_CLAIMED,describePairComponents} from './grid-layout-pair-comparator.mjs';
test('pair measures independent components in all eight states and preserves explicit baseline bounds',()=>{
  const rust=pixels().images,moon=pixels().images,result=comparePairImages(rust,moon);
  assert.equal(result.status,'bounded_color_component_pair_verified');
  assert.deepEqual(Object.keys(result.states),VIEWPORT_SEQUENCE.map(x=>x.name));
  assert.deepEqual(TOLERANCES,{fill_edge:2,exposed_gray_gap:1,fill_separation:4});
  assert.deepEqual(result.not_claimed,NOT_CLAIMED);
  assert.equal(result.single_pixel_geometry_regression_detection,'not_guaranteed');
  for(const state of Object.values(result.states)) {
    assert.equal(Object.keys(state.components).length,5);
    for(const region of Object.values(state.components))assert.deepEqual(region.edge_deltas,{left:0,right:0,top:0,bottom:0});
  }
  assert.equal(describePairComponents(rust,moon).initial.rust.width,500);
});
test('bounded fill edges permit only documented component differences, without count/full-pixel equality',()=>{
  const rust=pixels().images,moon=Object.fromEntries(VIEWPORT_SEQUENCE.map(s=>[s.name,frame(s.width,0.8)]));
  const result=comparePairImages(rust,moon);assert.equal(result.conformance,'not_claimed');
});
test('wrong exact fill color fails even with unchanged rectangles',()=>{
  const rust=pixels().images,moon=pixels().images,changed=moon.initial;
  for(let p=0;p<changed.width*changed.height;p++)if(COLORS.content.every((v,i)=>changed.data[p*4+i]===v))changed.data.set([128,0,128,255],p*4);
  assert.throws(()=>comparePairImages(rust,moon),/content: substantial/);
});
test('corruption controls stay explicitly separate from actual compiled controls',()=>{
  const controls=pairNegativeControls(pixels().images,pixels().images);assert.equal(controls.length,3);
  assert(controls.every(x=>x.rejected&&x.kind==='synthetic_raster_corruption_not_executed_mutant'));
});
test('threshold swap and restoration loss fail original measured profile',()=>{
  const rust=pixels().images,moon=pixels().images;
  assert.throws(()=>comparePairImages(rust,{...moon,threshold400:moon.narrow399}));
  assert.throws(()=>comparePairImages(rust,{...moon,final500:moon.wide401}));
});
