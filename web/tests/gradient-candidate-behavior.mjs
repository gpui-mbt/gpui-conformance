// Candidate-only source geometry adapter v2. Original Rust predicates stay frozen.
import assert from 'node:assert/strict';
import {sourceStructure,colorObservations,buttonTarget,VIEWPORT_SEQUENCE,ORACLE} from './gradient-comparator.mjs';

export function expectedBinaryPolygonBounds(width,height) {
 assert(Number.isSafeInteger(width)&&Number.isSafeInteger(height)&&width>=240&&height>=300,'Integer source viewport required');
 // Authored canvas: root inset16, allocation96. Polygon top offset30,
 // bottom80; horizontal slant80 over vertical extent50. Its final sampled
 // row is0.5 above the bottom, moving each slant inward80/50*0.5=0.8.
 // Source left is0.1*(width-32), right0.9*(width-32), omitting canvas X.
 // Scale rational coordinates by20 before pixel-center ceil/floor. This
 // preserves exact boundary inclusion without a fitted floating epsilon.
 const canvasWidth=width-2*16,units=20,halfPixel=units/2;
 const inset=80/50*halfPixel,left=canvasWidth*2,right=canvasWidth*18;
 const x=Math.ceil((left+inset-halfPixel)/units);
 const lastX=Math.floor((right-inset-halfPixel)/units);
 const canvasTop=height-16-96,top=canvasTop+30,bottom=canvasTop+80;
 const y=Math.ceil(top-.5),lastY=Math.floor(bottom-.5);
 return {x,y,width:lastX-x+1,height:lastY-y+1};
}
export function assertCandidatePolygonCoverage(polygon,width,height) {
 const actual=Object.fromEntries(['x','y','width','height'].map(k=>[k,polygon[k]]));
 assert.deepEqual(actual,expectedBinaryPolygonBounds(width,height),'Candidate source polygon pixel-center binary coverage, omitted canvas origin and authored width');
}
function verifyCandidateSet(r,files) {
 const geometry={},observations={};
 for(const state of VIEWPORT_SEQUENCE){const image=files.images[state.name];const g=sourceStructure(image);geometry[state.name]=g;observations[state.name]=colorObservations(image,state.space,g);
  assertCandidatePolygonCoverage(g.colored.at(-1),state.width,state.height);

 }
 for(const op of r.operations.filter(o=>o.action==='click')){const index=VIEWPORT_SEQUENCE.findIndex(s=>s.name===op.name);assert.deepEqual(op.target,buttonTarget(files.images[VIEWPORT_SEQUENCE[index-1].name]),'Target derived from prior original PNG');}
 for(const phase of ['wide','tall']) {
  assert.deepEqual(files.images[phase+'Srgb'].data,files.images[phase+'Restored'].data,'Complete sRGB restoration');
  assert.notDeepEqual(files.images[phase+'Srgb'].data,files.images[phase+'Oklab'].data,'Actual toggle changes original render');
  for(const index of [0,1]){const box=geometry[phase+'Srgb'].colored[index];for(let y=box.y;y<box.y+box.height;y++)for(let x=box.x;x<box.x+box.width;x++){const p=(y*files.images[phase+'Srgb'].width+x)*4;assert.deepEqual(files.images[phase+'Srgb'].data.slice(p,p+4),files.images[phase+'Oklab'].data.slice(p,p+4),'Source solid does not change with color-space toggle');}}
  // Exclude label-only changes: at least one original interior gradient pixel changes.
  let changed=false;for(const box of geometry[phase+'Srgb'].colored.slice(2,-1)){for(let y=box.y+4;y<box.y+box.height-4;y++)for(let x=box.x+4;x<box.x+box.width-4;x++){const p=(y*files.images[phase+'Srgb'].width+x)*4;if(!Buffer.from(files.images[phase+'Srgb'].data.slice(p,p+4)).equals(Buffer.from(files.images[phase+'Oklab'].data.slice(p,p+4))))changed=true;}}
  assert(changed,'Gradient interior changed after real click');
 }
 assert.deepEqual(files.images.wideSrgb.data,files.images.wideAgain.data,'Real viewport round trip restores full original frame');
 return {status:'verified_bounded_structure_interaction_restoration',geometry,color_observations:observations,color_equivalence:'pending_source_and_original_artifact_review_no_tolerance_fitted',backend:'candidate_canvas2d_core_rgba_transport',unverified:ORACLE.unverified};
}
export function verifyCandidateSourceBehavior(report,files) {
 assert.equal(report.runtime,'moonbit','Typed candidate-only source predicate adapter');
 assert(files?.images&&files?.stableImages,'Both independent candidate stable sets required');
 const first=verifyCandidateSet(report,{images:files.images});
 const second=verifyCandidateSet(report,{images:files.stableImages});
 assert.deepEqual(second,first,'Both candidate source-behavior sample sets');
 return {...first,adapter_revision:'authored_binary_polygon_pixel_centers_v2',original_rust_predicates:'unchanged; independently required before the paired gate'};
}
