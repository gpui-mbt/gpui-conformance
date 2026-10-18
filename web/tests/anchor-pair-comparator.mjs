// Independent complete original raster measurements; frozen source predicates.
import assert from 'node:assert/strict';
import {VIEWPORT_SEQUENCE,validateProfile} from './anchor-comparator.mjs';
export const PAIR_PROFILE='anchor_actual_browser_pair_v1';
export const TOLERANCES=Object.freeze({fill_edge:2});
export const NOT_CLAIMED=Object.freeze(['Full-image equality','Text/shaping/glyph/typography parity','Exact shadow kernel or opacity parity','Native parity','Callback counts','Other viewports/DPRs/browsers/GPUs']);
export function comparePairImages(rustImages,moonImages) {
  const rust=validateProfile(rustImages),moonbit=validateProfile(moonImages),states={};
  for(const state of VIEWPORT_SEQUENCE) {
    const a=rust.observations[state.name],b=moonbit.observations[state.name];
    const regions=state.hover?['hover_fill','popup']:Object.keys(a.idle.buttons);
    const components={};
    for(const region of regions) {
      const x=state.hover?a[region]:a.idle.buttons[region],y=state.hover?b[region]:b.idle.buttons[region],deltas={};
      for(const edge of ['left','right','top','bottom']) {
        deltas[edge]=y[edge]-x[edge];
        assert(Math.abs(deltas[edge])<=2,`${state.name}/${region}/${edge}: measured candidate minus Rust ${deltas[edge]}px exceeds unchanged ±2px bound`);
      }
      components[region]={rust:x,moonbit:y,edge_deltas:deltas,pixel_count_delta:y.pixels-x.pixels,pixel_count_comparison:'descriptive only; glyph holes/AA/decorative compositing differ'};
    }
    states[state.name]={width:state.width,height:600,components};
  }
  return {status:'bounded_color_component_pair_verified',profile:PAIR_PROFILE,tolerances_physical_pixels:TOLERANCES,states,
    restoration:{rust:rust.restoration,moonbit:moonbit.restoration},snapping:{rust:rust.snapping,moonbit:moonbit.snapping},
    source_color:'Opaque black hover fill; achromatic 51..64 popup source compositing envelope, not exact shadow/opacity parity',
    single_pixel_geometry_regression_detection:'not_guaranteed',conformance:'not_claimed',not_claimed:NOT_CLAIMED};
}
export function pairNegativeControls(rust,moon) {
  comparePairImages(rust,moon);const controls=[];
  for(const [name,state,replacement] of [['wrong_viewport','narrowIdle','initial'],['missing_popup','wideTopLeft','initial'],['stale_hover_after_exit','wideTopLeftExit','wideTopLeft']]) {
    assert.throws(()=>comparePairImages(rust,{...moon,[state]:moon[replacement]}));
    controls.push({name,rejected:true,kind:'synthetic_raster_corruption_not_executed_mutant'});
  }
  return controls;
}
