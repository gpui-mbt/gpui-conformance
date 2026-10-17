// Synthetic unit inputs only; no executed browser or fault qualification.
import test from 'node:test';
import assert from 'node:assert/strict';
import {pixels} from './fixtures/anchor-fixtures.mjs';
import {VIEWPORT_SEQUENCE} from './anchor-comparator.mjs';
import {comparePairImages,pairNegativeControls,TOLERANCES,NOT_CLAIMED} from './anchor-pair-comparator.mjs';
test('41-state pair independently checks source predicates, bound geometry and exact restoration',()=>{
 const result=comparePairImages(pixels().images,pixels().images);
 assert.equal(result.status,'bounded_color_component_pair_verified');assert.equal(VIEWPORT_SEQUENCE.length,41);
 assert.deepEqual(Object.keys(result.states),VIEWPORT_SEQUENCE.map(s=>s.name));assert.deepEqual(TOLERANCES,{fill_edge:2});
 assert.deepEqual(result.not_claimed,NOT_CLAIMED);assert.equal(result.conformance,'not_claimed');
 for(const state of Object.values(result.states))for(const region of Object.values(state.components))assert.deepEqual(region.edge_deltas,{left:0,right:0,top:0,bottom:0});
});
test('popup paint corruption fails source compositing before any claimed geometry parity',()=>{
 const rust=pixels().images,moon=pixels().images,image={...moon.wideTopLeft,data:moon.wideTopLeft.data.slice()};
 for(let p=0;p<image.width*image.height;p++)if(image.data[p*4]===64)image.data.set([128,0,128,255],p*4);
 assert.throws(()=>comparePairImages(rust,{...moon,wideTopLeft:image}),/source-permitted51..64/);
});
test('synthetic corruption is labeled separately from actual compiled controls',()=>{
 const controls=pairNegativeControls(pixels().images,pixels().images);assert.equal(controls.length,3);
 assert(controls.every(x=>x.rejected&&x.kind==='synthetic_raster_corruption_not_executed_mutant'));
});
