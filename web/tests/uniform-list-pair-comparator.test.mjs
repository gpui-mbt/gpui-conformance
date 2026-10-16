import test from 'node:test';
import assert from 'node:assert/strict';
import {pixels} from './fixtures/uniform-list-fixtures.mjs';
import {comparePairImages,pairNegativeControls,describeImageDifference} from './uniform-list-pair-comparator.mjs';

test('synthetic same-source pair verifies independently at26 and31, never browser evidence',()=>{
  for(const pitch of [26,31]) {
    const {images,stableImages}=pixels(pitch),result=comparePairImages(images,stableImages);
    assert.equal(result.status,'bounded_browser_pair_verified');assert.equal(result.row_envelopes.length,50);
    assert.equal(result.moonbit_geometry.pitch,pitch);assert(result.not_claimed.includes('Full-image/antialiasing equality'));
  }
});
test('different antialias intensities remain descriptive without weakening glyph envelopes',()=>{
  const {images}=pixels();
  const moon=Object.fromEntries(Object.entries(images).map(([name,image])=>{
    const data=image.data.slice();for(let i=0;i<data.length;i+=4)if(data[i]===0)data[i]=data[i+1]=data[i+2]=20;
    return [name,{...image,data}];
  }));
  const result=comparePairImages(images,moon);assert(result.raster_differences.initial.different_pixels>0);
  assert(result.raster_differences.initial.mean_absolute_channel_difference>0);
});
test('original-raster sensitivity catches movement, endpoints, axes, padding and partial clips',()=>{
  const {images,stableImages}=pixels();const controls=pairNegativeControls(images,stableImages);
  assert.equal(controls.length,7);assert(controls.every(x=>x.rejected&&x.kind==='corrupted_evidence_sensitivity_not_executed_mutant'));
});
test('cross-runtime row pitch mismatch fails instead of accepting each independent self-report',()=>{
  assert.throws(()=>comparePairImages(pixels(26).images,pixels(31).images),/pitch/);
});
test('descriptive difference has no pass flag',()=>{
  const image=pixels().images.initial;const result=describeImageDifference(image,image);
  assert.equal(result.different_pixels,0);assert.equal(result.status,undefined);
});

test('separately scoped bounded result preserves strict failure and all50 right-edge differences',async()=>{
  const {compareBoundedPlacement,describePairPlacement,boundedNegativeControls}=await import('./uniform-list-pair-comparator.mjs');
  const {images,profile}=pixels();
  const moon=Object.fromEntries(Object.entries(images).map(([name,image])=>{
    const data=image.data.slice(),offset=profile.captures[name].offset;
    for(let y=0;y<300;y++)if((offset+y)%26===10){const at=(y*300+62)*4;data[at]=data[at+1]=data[at+2]=30;}
    return [name,{...image,data}];
  }));
  assert.throws(()=>comparePairImages(images,moon),/glyph envelope/);
  const result=compareBoundedPlacement(images,moon);
  assert.equal(result.status,'bounded_placement_scroll_clip_verified_with_typography_mismatch');
  assert.equal(result.profile,'uniform_list_bounded_placement_scroll_clip_v1');
  assert.equal(result.typography.right_edge_differences.length,50);assert.equal(result.glyph_placement.differing_rows.length,50);
  assert.equal(describePairPlacement(images,moon).rows.length,50);
  assert.equal(boundedNegativeControls(images,moon).length,7);
  assert(result.not_claimed.includes('Exact horizontal glyph envelope equality'));
});
