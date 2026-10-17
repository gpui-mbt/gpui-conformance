// Pair observations are derived only from complete original raster bytes.
// Frozen Rust-only geometry/source predicates remain separate and unchanged.
import assert from 'node:assert/strict';
import {VIEWPORT_SEQUENCE,COLORS,validateProfile,discoverGeometry} from './grid-layout-comparator.mjs';
export const PAIR_PROFILE='grid_layout_actual_browser_pair_v1';
export const TOLERANCES=Object.freeze({fill_edge:2,exposed_gray_gap:1,fill_separation:4});
export const NOT_CLAIMED=Object.freeze(['Full-image/antialiasing equality','Text content/shaping/glyph pixels/typography parity',
  'Dashed border/radius/shadow fidelity','Native parity','Rust callback counts/layout internals/offscreen work','Other viewports/DPRs/browsers/GPUs']);
function bounded(delta,tolerance,label) {
  assert(Math.abs(delta)<=tolerance,`${label}: measured candidate minus Rust ${delta}px exceeds unchanged ±${tolerance}px bound`);
}
function separations(geometry) {
  const r=geometry.regions;
  return geometry.width===399
    ? ['toc','content','ad','footer'].map((name,i)=>({name,axis:'vertical',pixels:r[name].top-r[['header','toc','content','ad'][i]].bottom}))
    : [{name:'toc/content',axis:'horizontal',pixels:r.content.left-r.toc.right},
       {name:'content/ad',axis:'horizontal',pixels:r.ad.left-r.content.right},
       {name:'header/content',axis:'vertical',pixels:r.content.top-r.header.bottom},
       {name:'content/footer',axis:'vertical',pixels:r.footer.top-r.content.bottom}];
}
export function describePairComponents(rustImages,moonImages) {
  return Object.fromEntries(VIEWPORT_SEQUENCE.map(({name})=>[name,{
    rust:discoverGeometry(rustImages[name]),moonbit:discoverGeometry(moonImages[name])}]));
}
export function comparePairImages(rustImages,moonImages) {
  // Each runtime must independently satisfy every original source predicate,
  // including source ±2 fill edges, ±1 gray gaps, ±4 separation and restoration.
  const rust=validateProfile(rustImages),moonbit=validateProfile(moonImages),states={};
  for(const {name,width} of VIEWPORT_SEQUENCE) {
    const a=rust.observations[name],b=moonbit.observations[name],components={};
    assert.equal(a.geometry.width,width);assert.equal(b.geometry.width,width);
    for(const region of Object.keys(COLORS)) {
      const x=a.geometry.regions[region],y=b.geometry.regions[region];
      assert.deepEqual(x.rgba,y.rgba,'Same exact source fill color in independently discovered components');
      const deltas={};
      for(const edge of ['left','right','top','bottom']) {
        deltas[edge]=y[edge]-x[edge];bounded(deltas[edge],TOLERANCES.fill_edge,`${name}/${region}/${edge}`);
      }
      components[region]={rust:x,moonbit:y,edge_deltas:deltas,pixel_count_delta:y.pixels-x.pixels,
        pixel_count_comparison:'descriptive only; text/border/AA pixels are not compared across runtimes'};
    }
    assert.equal(a.measured_exposed_gaps.length,b.measured_exposed_gaps.length);
    const gaps=a.measured_exposed_gaps.map((gap,i)=>{
      const other=b.measured_exposed_gaps[i];assert.equal(gap.axis,other.axis);
      const delta=other.pixels-gap.pixels;bounded(delta,TOLERANCES.exposed_gray_gap,`${name}/exposed-gap-${i}`);
      return {rust:gap,moonbit:other,delta};
    });
    const aSeparations=separations(a.geometry),bSeparations=separations(b.geometry);
    const fillSeparations=aSeparations.map((value,i)=>{
      const other=bSeparations[i];assert.equal(value.name,other.name);assert.equal(value.axis,other.axis);
      const delta=other.pixels-value.pixels;bounded(delta,TOLERANCES.fill_separation,`${name}/${value.name}/fill-separation`);
      return {rust:value,moonbit:other,delta};
    });
    states[name]={width,height:500,components,exposed_gaps:gaps,fill_separations:fillSeparations};
  }
  return {status:'bounded_color_component_pair_verified',profile:PAIR_PROFILE,tolerances_physical_pixels:TOLERANCES,
    states,restoration:{rust:rust.restoration,moonbit:moonbit.restoration},
    threshold:'Both original runtime rasters stack at399 and use grid at400/401/500',
    single_pixel_geometry_regression_detection:'not_guaranteed',conformance:'not_claimed',not_claimed:NOT_CLAIMED};
}
export function pairNegativeControls(rust,moon) {
  comparePairImages(rust,moon);
  const controls=[],reject=(name,run)=>{assert.throws(run,name);controls.push({name,rejected:true,kind:'synthetic_raster_corruption_not_executed_mutant'});};
  reject('borrowed_wrong_width_capture',()=>comparePairImages(rust,{...moon,narrow399:moon.initial}));
  const changed={...moon.initial,data:moon.initial.data.slice()};
  for(let p=0;p<changed.width*changed.height;p++)if(COLORS.content.every((v,i)=>changed.data[p*4+i]===v))changed.data.set([128,0,128,255],p*4);
  reject('synthetic_wrong_fill_color',()=>comparePairImages(rust,{...moon,initial:changed}));
  const restored={...moon.restore500,data:moon.restore500.data.slice()};
  for(let p=0;p<restored.width*restored.height;p++)if(COLORS.toc.every((v,i)=>restored.data[p*4+i]===v)){restored.data.set([80,80,80,255],p*4);break;}
  reject('synthetic_restoration_pixel_loss',()=>comparePairImages(rust,{...moon,restore500:restored}));
  return controls;
}
