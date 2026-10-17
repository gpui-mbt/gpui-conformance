// SYNTHETIC CONTRACT TESTS ONLY. No Rust execution or browser observation.
import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {ANCHOR,ANCHORS,POPUP_COMPOSITING,assertProvenance,provenanceNegativeControls,discoverButtons,discoverPopup,inspectIdle,validateProfile,validateOperations,profileNegativeControls,assertCurrentBuild,sha256} from './anchor-comparator.mjs';
import {validateReport,verifyBehavior,validateCaptureBindings,validateRuntimeResponses,assertExecutedBytes,evidenceNegativeControls,inputEvidence,validateInputEvidence,assertRetainedSupport} from './anchor-runtime-evidence.mjs';
import {deriveRustWorkerBytes,evidenceFilename} from './anchor-worker-evidence.mjs';
import {frame,pixels,provenance,fixture} from './fixtures/anchor-fixtures.mjs';
test('synthetic provenance preserves unchanged source, unused engine pin, frozen catalog and eight fonts',()=>{
  const {build,catalog}=provenance();assert.equal(assertProvenance(build,catalog).source_blob,ANCHOR.sourceBlob);assert(provenanceNegativeControls(build,catalog).every(c=>c.rejected));
  for(const change of [b=>{b.rust.files['index.html']='0'.repeat(64);},b=>{b.rust_oracle_only[0].width=800;},b=>{b.rust.files['Cargo.lock']='0'.repeat(64);},b=>{b.rust.command.push('--bin','hello_world');}]){const b=structuredClone(build);change(b);assert.throws(()=>assertProvenance(b,catalog));}
});
test('whole original synthetic pixels discover eight outlines, observed white points and clipped visible bounds',()=>{
  const wide=discoverButtons(frame()),narrow=discoverButtons(frame(480));assert.deepEqual(Object.keys(wide.buttons),ANCHORS);
  assert.equal(wide.buttons.TopLeft.left,119);assert.equal(narrow.buttons.TopLeft.left,0);assert.equal(narrow.buttons.TopLeft.width,104);
  assert.equal(discoverPopup(frame(750,'TopLeft')).width,100);inspectIdle(frame(480));
  const shifted=frame();shifted.data.copyWithin(750*4,0,599*750*4);assert.equal(discoverButtons(shifted).buttons.TopLeft.top,wide.buttons.TopLeft.top+1);
  const blank=frame();blank.data.fill(255);assert.throws(()=>discoverButtons(blank));const alpha=frame();alpha.data[3]=254;assert.throws(()=>discoverButtons(alpha));
});
test('synthetic complete profile checks every anchor, inferred inert center, Local geometry and two measured left snaps',()=>{
  const {report,retained}=fixture();const result=validateProfile(retained.images);assert.deepEqual(result.snapping.observed,['narrowTopLeft','narrowBottomLeft']);
  assert.equal(validateOperations(report,retained.images).pointer_moves,38);assert.equal(result.hovered_anchors.length,8);
  report.reported_geometry={left:999};report.passed=true;assert.equal(verifyBehavior(report,retained).status,'rust_source_profile_verified');
});
test('corrupted pixel/input controls reject wrong anchor, missing popup, stale hover, active center, lost snap and untrusted input',()=>{
  const {report,retained}=fixture(),controls=profileNegativeControls(retained.images,report);assert(controls.length>=18);assert(controls.every(c=>c.rejected));
});
test('runtime response and capture bindings require exact HTML/worker bytes and original raw input',()=>{
  const {report,retained}=fixture();validateReport(report,'rust');validateCaptureBindings(report);assertExecutedBytes(report,retained);assert(evidenceNegativeControls(report,retained).every(c=>c.rejected));
  for(const path of ['rust/index.html','rust/anchor.js','rust/anchor_bg.wasm']){const r=structuredClone(report);r.runtime_responses=r.runtime_responses.filter(e=>e.path!==path);assert.throws(()=>validateRuntimeResponses(r));}
  const r=structuredClone(report);r.operations[0].events[0].x++;assert.throws(()=>validateInputEvidence(r,JSON.parse(retained.inputBytes)));assert.deepEqual(inputEvidence(report),JSON.parse(retained.inputBytes));
  const swapped=structuredClone(report);[swapped.captures.wideTopLeft,swapped.captures.wideTopRight]=[swapped.captures.wideTopRight,swapped.captures.wideTopLeft];assert.throws(()=>validateCaptureBindings(swapped));
  for(const url of ['data:text/javascript,alert(1)','https://example.com/external.js','blob:http://127.0.0.1:12345/not-an-id']){const r=structuredClone(report);r.runtime_responses.at(-1).url=url;assert.throws(()=>validateRuntimeResponses(r));}
});
test('worker derivation and historical provenance cannot borrow other routes or checkout revisions',()=>{
  assert(deriveRustWorkerBytes('http://127.0.0.1:12345/gpui-conformance/rust/anchor.js').includes(Buffer.from('/rust/anchor.js')));
  assert.throws(()=>deriveRustWorkerBytes('http://127.0.0.1:12345/gpui-conformance/rust/grid_layout.js'));assert.notEqual(evidenceFilename('rust','asset','a/b',1),evidenceFilename('rust','asset','a_b',1));
  const {report}=fixture(),catalogBytes=readFileSync(new URL('./fixtures/anchor-rust-only-catalog-a20e5888.json',import.meta.url));report.catalog_evidence.sha256=sha256(catalogBytes);
  const checkout={revision:report.build.lab_revision,tree:report.build.lab_tree,trackedDirty:false,catalogBytes};assertCurrentBuild(report,checkout);for(const changed of [{revision:'0'.repeat(40)},{tree:'0'.repeat(40)},{trackedDirty:true},{catalogBytes:Buffer.from('{}')}])assert.throws(()=>assertCurrentBuild(report,{...checkout,...changed}));
});
test('source/font input corruption and missing embedding fail independently',()=>{
  const bytes=Buffer.from('synthetic font'),path='rust/embedded-font-inputs/test.ttf',entry={path,bytes:bytes.length,sha256:sha256(bytes)},build={rust:{files:{[path.slice(5)]:sha256(bytes)}}};
  assertRetainedSupport(entry,bytes,build,bytes);assert.throws(()=>assertRetainedSupport(entry,Buffer.from('changed'),build,bytes));assert.throws(()=>assertRetainedSupport(entry,bytes,build,Buffer.from('no font')));
});

test('source-permitted popup compositing envelope covers two shadow layers without fitting geometry or claiming exact opacity',()=>{
  const profile=POPUP_COMPOSITING,q=Math.exp(-2*Math.PI*Math.PI/(1.5*1.5));
  assert(1+2*q/(1-q)<profile.shadow_coverage_upper);
  let lower=255;for(const alpha of profile.shadow_alphas)lower=Math.floor(lower*(1-alpha*profile.shadow_coverage_upper));
  assert.equal(Math.floor(lower*(1-profile.popup_alpha)),profile.minimum_gray);assert.equal(Math.ceil(255*(1-profile.popup_alpha)),profile.maximum_gray);
  const recolor=(colorAt)=>{const image=frame(750,'TopLeft'),bounds=discoverPopup(image);for(let y=bounds.top;y<bounds.bottom;y++)for(let x=bounds.left;x<bounds.right;x++)image.data.set(colorAt(x-bounds.left,y-bounds.top),4*(y*image.width+x));return image;};
  for(const value of [51,64])assert.equal(discoverPopup(recolor(()=>[value,value,value,255])).width,100);
  // Forward compositing fixtures: coverage varies independently through[0,1],
  // then the authored fill paints over both source shadows on white.
  const gradient=recolor((x,y)=>{const c1=(x%11)/10,c2=(y%11)/10,value=Math.round(255*(1-.1*c1)*(1-.1*c2)*.25);return [value,value,value,255];});
  assert.equal(discoverPopup(gradient).width,100);assert.equal(discoverPopup(gradient).height,24);
  for(const [label,color] of [['below_source_envelope',[50,50,50,255]],['above_source_envelope',[65,65,65,255]],['shadow_only',[207,207,207,255]],['non_achromatic_fill',[52,53,52,255]],['selected_wrong_opacity_half',[103,103,103,255]],['selected_wrong_opacity_nine_tenths',[21,21,21,255]]])assert.throws(()=>discoverPopup(recolor(()=>color)),label);
  // Another opacity can land inside the interval. Accepting its pixels is an
  // explicit claim boundary, not evidence that the original alpha was measured.
  assert.equal(discoverPopup(recolor(()=>[56,56,56,255])).width,100);
});
