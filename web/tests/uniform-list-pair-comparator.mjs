// Original images establish each runtime's progression separately. No candidate
// telemetry may become an expected Rust pixel, measured pitch or source fact.
import assert from 'node:assert/strict';
import {discoverGeometry,makeProfile,validateProfile,inspectInk,sha256} from './uniform-list-comparator.mjs';
export const PAIR_PROFILE='uniform_list_actual_browser_pair_v1';

function atlas(images,geometry) {
  const rows=new Map();
  for(const [name,state] of Object.entries(makeProfile(geometry).captures))
    for(let y=0;y<300;y++)rows.set(state.offset+y,images[name].data.slice(y*1200,(y+1)*1200));
  return rows;
}
function envelope(rows,index,pitch) {
  let left=300,right=-1,top=pitch,bottom=-1,ink=0;
  for(let y=0;y<pitch;y++)for(let x=0;x<300;x++) {
    const row=rows.get(index*pitch+y),o=x*4;
    if(Math.min(row[o],row[o+1],row[o+2])<250) {
      left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);ink++;
    }
  }
  assert(ink>0,'Every observed row must contain real glyph ink');
  return {left,right_exclusive:right+1,top,bottom_exclusive:bottom+1};
}
export function describeImageDifference(rust,moon) {
  let different=0,absolute=0,max=0;
  for(let i=0;i<rust.data.length;i+=4) {
    let changed=false;
    for(let c=0;c<3;c++) {
      const delta=Math.abs(rust.data[i+c]-moon.data[i+c]);absolute+=delta;max=Math.max(max,delta);changed ||= delta!==0;
    }
    if(changed)different++;
  }
  return {different_pixels:different,total_pixels:90000,mean_absolute_channel_difference:absolute/270000,max_channel_difference:max,
    rust_rgba_sha256:sha256(rust.data),moonbit_rgba_sha256:sha256(moon.data),claim:'Descriptive only; not a full-image or antialiasing pass criterion'};
}
export function describePairPlacement(rustImages,moonImages) {
  const rustGeometry=discoverGeometry(rustImages.initial),moonGeometry=discoverGeometry(moonImages.initial);
  if(rustGeometry.pitch!==moonGeometry.pitch)return {rust_geometry:rustGeometry,moonbit_geometry:moonGeometry,rows:null,
    diagnosis:'Different measured pitch; same-row glyph-envelope comparison is undefined'};
  const rustAtlas=atlas(rustImages,rustGeometry),moonAtlas=atlas(moonImages,moonGeometry),rows=[];
  for(let index=0;index<50;index++) {
    const rust=envelope(rustAtlas,index,rustGeometry.pitch),moonbit=envelope(moonAtlas,index,moonGeometry.pitch);
    rows.push({index,rust,moonbit,difference:Object.fromEntries(Object.keys(rust).map(key=>[key,moonbit[key]-rust[key]]))});
  }
  return {rust_geometry:rustGeometry,moonbit_geometry:moonGeometry,rows,
    differing_rows:rows.filter(row=>Object.values(row.difference).some(delta=>delta!==0)).map(row=>row.index),
    claim:'Descriptive actual raster support; no OCR identity or permission to relax the predicate'};
}
export function comparePairImages(rustImages,moonImages) {
  const rustGeometry=discoverGeometry(rustImages.initial),moonGeometry=discoverGeometry(moonImages.initial);
  // Exact envelopes are intentionally fail-closed. A rasterizer disagreement is
  // retained for diagnosis; never turn an observed failure into a looser bound.
  for(const key of ['pitch','ink_top','ink_bottom','left'])
    assert.equal(moonGeometry[key],rustGeometry[key],`Cross-runtime measured ${key}; retain and diagnose mismatches`);
  const rustPaint=validateProfile(rustImages,rustGeometry),moonPaint=validateProfile(moonImages,moonGeometry);
  assert.equal(rustPaint.observed_content_scanlines,moonPaint.observed_content_scanlines);
  assert.equal(rustPaint.endpoint_offset_from_bounded_wheel_and_overlap,moonPaint.endpoint_offset_from_bounded_wheel_and_overlap);
  const rustAtlas=atlas(rustImages,rustGeometry),moonAtlas=atlas(moonImages,moonGeometry),rows=[];
  for(let index=0;index<50;index++) {
    const rust=envelope(rustAtlas,index,rustGeometry.pitch),moonbit=envelope(moonAtlas,index,moonGeometry.pitch);
    assert.deepEqual(moonbit,rust,`Original full-content row${index}: exact glyph envelope; not OCR identity`);
    rows.push({index,rust,moonbit});
  }
  return {status:'bounded_browser_pair_verified',rust_geometry:rustGeometry,moonbit_geometry:moonGeometry,
    rust_paint:rustPaint,moonbit_paint:moonPaint,row_envelopes:rows,
    raster_differences:Object.fromEntries(Object.keys(rustImages).map(name=>[name,describeImageDifference(rustImages[name],moonImages[name])])),
    claims:['Independent original-raster progression for50 distinct rows in each runtime','Equal measured pitch, 50-row extent and endpoint',
      'Exact measured glyph envelopes and horizontal text origin','Partial glyph ink at actual drawing-surface edges'],
    not_claimed:['Full-image/antialiasing equality','OCR label identity','Rust callback/laziness/click IDs','Internal-mask versus surface clipping','Native or other viewport/browser/GPU parity']};
}
// Separately named bounded result. The original strict predicate above is
// unchanged and must also run, with its result retained, on every actual pair.
export function compareBoundedPlacement(rustImages,moonImages) {
  const placement=describePairPlacement(rustImages,moonImages);
  const rustGeometry=placement.rust_geometry,moonGeometry=placement.moonbit_geometry;
  for(const key of ['pitch','ink_top','ink_bottom','left'])
    assert.equal(moonGeometry[key],rustGeometry[key],`Exact bounded cross-runtime ${key}`);
  const rustPaint=validateProfile(rustImages,rustGeometry),moonPaint=validateProfile(moonImages,moonGeometry);
  for(const row of placement.rows)for(const key of ['left','top','bottom_exclusive'])
    assert.equal(row.moonbit[key],row.rust[key],`Row${row.index}: exact bounded ${key}`);
  assert.equal(rustPaint.observed_content_scanlines,moonPaint.observed_content_scanlines);
  assert.equal(rustPaint.endpoint_offset_from_bounded_wheel_and_overlap,moonPaint.endpoint_offset_from_bounded_wheel_and_overlap);
  return {status:placement.differing_rows.length?'bounded_placement_scroll_clip_verified_with_typography_mismatch':'bounded_placement_scroll_clip_verified',
    profile:'uniform_list_bounded_placement_scroll_clip_v1',rust_geometry:rustGeometry,moonbit_geometry:moonGeometry,
    rust_paint:rustPaint,moonbit_paint:moonPaint,glyph_placement:placement,
    typography:{exact_envelopes:placement.differing_rows.length?'mismatch':'matched',
      right_edge_differences:placement.rows.map(row=>({index:row.index,rust_right_exclusive:row.rust.right_exclusive,
        moonbit_right_exclusive:row.moonbit.right_exclusive,delta:row.difference.right_exclusive})),
      claim:'Horizontal glyph support and antialiasing are reported without a passing tolerance'},
    raster_differences:Object.fromEntries(Object.keys(rustImages).map(name=>[name,describeImageDifference(rustImages[name],moonImages[name])])),
    claims:['Each runtime independently covers50 distinct complete row rasters through original overlap-linked wheel progression',
      'Exact measured pitch, vertical ink bands and row ink-left support in every row','Equal measured complete extent and endpoint',
      'Actual partial surface-edge ink, both axis rules and endpoint/top restoration'],
    not_claimed:['Exact horizontal glyph envelope equality','Full-image or antialiasing equality','OCR label identity',
      'Rust factory/callback/click or internal-mask behavior','General complex-text shaping','Native/other browser/viewport/GPU parity']};
}
export function boundedNegativeControls(rust,moon) {
  compareBoundedPlacement(rust,moon);
  const rejected=[],check=(name,images)=>{assert.throws(()=>compareBoundedPlacement(rust,images),name);
    rejected.push({name,rejected:true,kind:'corrupted_evidence_sensitivity_not_executed_mutant'});};
  for(const [name,state,replacement] of [['bounded_moon_no_scroll','before_row_boundary','initial'],
    ['bounded_moon_wrong_endpoint','bottom_clamp','initial'],['bounded_moon_lost_restore','top_return','bottom_clamp'],
    ['bounded_moon_x_ignored','x_only_partial','initial'],['bounded_moon_mixed_wrong_axis','mixed_y_partial','at_row_boundary']])
    check(name,{...moon,[state]:moon[replacement]});
  const shifted={...moon.initial,data:moon.initial.data.slice()};
  for(let y=0;y<300;y++){const row=moon.initial.data.slice(y*1200,(y+1)*1200);shifted.data.fill(255,y*1200,(y+1)*1200);shifted.data.set(row.subarray(0,1196),y*1200+4);}
  check('bounded_moon_left_origin_shift',{...moon,initial:shifted});
  const erased={...moon.top_edge_partial,data:moon.top_edge_partial.data.slice()};erased.data.fill(255,0,1200);
  check('bounded_moon_missing_partial_edge',{...moon,top_edge_partial:erased});
  return rejected;
}
export function assertCandidateScene(frame,geometry,offset,metrics) {
  assert.equal(frame?.ok,true);assert.equal(frame.conformance,'unverified');assert.equal(frame.cursor,'pointer');
  assert.deepEqual(frame.decorations,[]);assert.equal(frame.scroll,undefined,'No host scroll substitute');
  const scene=frame.snapshot,list=frame.uniform_list;
  assert.equal(scene.schema_version,1);assert.equal(scene.scale,1);
  assert.deepEqual(scene.viewport,{x:0,y:0,width:300,height:300});
  assert.equal(list.measured_height,geometry.pitch,'Candidate measured geometry agrees with its own original pixels');
  assert.equal(list.offset,offset);assert.equal(list.content_height,50*geometry.pitch);
  assert.equal(list.max_offset,50*geometry.pitch-300);
  assert.deepEqual(list.bounds,{x:0,y:0,width:300,height:300});
  const first=Math.floor(offset/geometry.pitch),end=Math.min(50,Math.ceil((offset+300)/geometry.pitch));
  assert.deepEqual(list.range,[first,end]);assert.equal(list.rows.length,end-first);
  const background=scene.items[0];assert.equal(background.kind,'quad');assert.equal(background.id,1);
  assert.deepEqual(background.bounds,{x:0,y:0,width:300,height:300});assert.deepEqual(background.color,{red:255,green:255,blue:255,alpha:255});
  assert.deepEqual(scene.clip_chains,[{id:0,rects:[{x:0,y:0,width:300,height:300}]}]);
  assert(metrics&&Array.isArray(metrics.widths)&&metrics.widths.length===50,'Retained real shaping inputs required');
  assert.equal(metrics.shaping_mode,'geometricPrecision');assert.equal(metrics.raster_mode,'auto');assert.equal(metrics.kerning,'normal');
  let cursor=1;
  for(let i=first;i<end;i++) {
    const row=list.rows[i-first];
    assert.equal(row.index,i);assert.equal(row.id,100+i*2);
    assert.deepEqual(row.bounds,{x:0,y:i*geometry.pitch-offset,width:300,height:geometry.pitch});
    assert.equal(row.text_anchor_id,row.id+1);
    const characters=Array.from(`Item ${i+1}`),prefixes=metrics.prefixes[i],advances=metrics.advances[i];
    assert.equal(prefixes.length,characters.length+1);assert.equal(advances.length,characters.length);
    assert.equal(prefixes[0],0);assert.equal(prefixes.at(-1),metrics.widths[i]);
    for(const [slot,character] of characters.entries()) {
      const text=scene.items[cursor++];assert(text,'Every source character produces one compiled run');
      assert.equal(text.kind,'text_run');assert.equal(text.id,row.text_anchor_id*10+slot);assert.equal(text.text,character);
      assert.deepEqual(text.bounds,{x:8,y:row.bounds.y,width:284,height:geometry.pitch});
      assert.deepEqual(text.text_origin,{x:Math.ceil((8+(prefixes[slot+1]-advances[slot]))*4-0.5)/4,y:row.bounds.y});
      assert.equal(text.clip_chain_id,0);assert.equal(text.font_size,16);assert.equal(text.opacity,1);
      assert.deepEqual(text.color,{red:0,green:0,blue:0,alpha:255});
      assert.deepEqual(text.transform,{a:1,b:0,c:0,d:1,tx:0,ty:0});
    }
  }
  assert.equal(cursor,scene.items.length,'No omitted, duplicated or extra compiled glyphs');
  // This validates actual candidate callback traces only, not Rust observability.
  assert.deepEqual(list.factory_calls,[{start:0,end:1,created_ids:[100]},{start:0,end:1,created_ids:[100]},
    {start:first,end,created_ids:list.rows.map(row=>row.id)}]);
  return {live_rows:list.rows.length,prototype_calls:2,observed_candidate_only:true};
}
export function pairNegativeControls(rust,moon) {
  comparePairImages(rust,moon);
  const rejected=[],check=(name,images)=>{assert.throws(()=>comparePairImages(rust,images),name);
    rejected.push({name,rejected:true,kind:'corrupted_evidence_sensitivity_not_executed_mutant'});};
  for(const [name,state,replacement] of [['moon_no_scroll','before_row_boundary','initial'],
    ['moon_wrong_endpoint','bottom_clamp','initial'],['moon_lost_restore','top_return','bottom_clamp'],
    ['moon_x_ignored','x_only_partial','initial'],['moon_mixed_wrong_axis','mixed_y_partial','at_row_boundary']])
    check(name,{...moon,[state]:moon[replacement]});
  const shifted={...moon.initial,data:moon.initial.data.slice()};
  for(let y=0;y<300;y++){const row=moon.initial.data.slice(y*1200,(y+1)*1200);shifted.data.fill(255,y*1200,(y+1)*1200);shifted.data.set(row.subarray(0,1196),y*1200+4);}
  check('moon_glyph_x_plus_one',{...moon,initial:shifted});
  const erased={...moon.top_edge_partial,data:moon.top_edge_partial.data.slice()};erased.data.fill(255,0,1200);
  check('moon_missing_partial_edge',{...moon,top_edge_partial:erased});
  return rejected;
}
