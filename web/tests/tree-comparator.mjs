import assert from 'node:assert/strict';

// This contract is derived from pinned tree.rs and GPUI's window-root semantics.
// DEPTH is 50 wrapping operations around one padded red block: 51 paint items.
// gpui/src/window.rs:3710-3724 calls stretch_auto_size_to_fill before layout;
// gpui/src/taffy.rs:109-136 replaces auto ROOT dimensions with viewport lengths.
// Consequently only the outermost block is 300x300; descendants stay auto-sized.
export const TREE = Object.freeze({width:300, height:300, wraps:50, nodes:51, padding:2,
  sourceBlob:'891be4790a59ae258da3380d2ef54fba26979346'});
const palette = [[255,0,0,255], [0,0,255,255], [0,128,0,255], [255,255,0,255]];
const white = [255,255,255,255];
const rgba = c => [c.red,c.green,c.blue,c.alpha];
const colorKey = c => c.join(',');

export function expectedTreeRings() {
  return Array.from({length:TREE.nodes}, (_, ordinal) => {
    const bounds = {x:2*ordinal,y:2*ordinal,width:300-4*ordinal,height:ordinal===0?300:204-4*ordinal};
    const next=ordinal+1;
    const innerArea = ordinal < TREE.wraps ? (300-4*next)*(204-4*next) : 0;
    return {ordinal, source_index:TREE.wraps-ordinal, bounds,
      rgba:[...palette[(TREE.wraps-ordinal)%4]], visible_pixels:bounds.width*bounds.height-innerArea};
  });
}

export function assertTreeScene(example, dpr=1) {
  assert.equal(example.metadata.id,'tree');
  for (const [key,value] of Object.entries({width:300,height:300,depth:50,node_count:51,padding:2})) {
    assert.equal(example.metadata[key],value,`tree metadata ${key}`);
  }
  const frame = example.frame;
  assert.equal(frame.ok,true);
  assert.equal(frame.conformance,'unverified','A runtime must not self-certify parity');
  assert.deepEqual(frame.decorations,[]);
  assert.deepEqual(frame.host_extensions,[]);
  const snapshot = frame.snapshot;
  assert.equal(snapshot.schema_version,1);
  assert.deepEqual(snapshot.viewport,{x:0,y:0,width:300,height:300});
  assert.equal(snapshot.scale,dpr);
  assert.deepEqual(snapshot.resources,[]);
  assert.deepEqual(snapshot.clip_chains,[]);
  assert.equal(snapshot.items.length,TREE.nodes,'tree must retain all 51 colored nodes');
  assert.equal(new Set(snapshot.items.map(item => item.id)).size,TREE.nodes,'tree node IDs must be unique');
  const rings = expectedTreeRings();
  for (const [ordinal,item] of snapshot.items.entries()) {
    assert.equal(item.kind,'quad',`ring ${ordinal}: only an actual scene quad is expected`);
    assert.deepEqual(item.bounds,rings[ordinal].bounds,`ring ${ordinal}: bounds/outer-to-inner paint order`);
    assert.deepEqual(rgba(item.color),rings[ordinal].rgba,`ring ${ordinal}: pinned palette`);
    assert.deepEqual(item.transform,{a:1,b:0,c:0,d:1,tx:0,ty:0},`ring ${ordinal}: transform`);
    assert.equal(item.opacity,1,`ring ${ordinal}: opacity`);
    assert.equal(item.clip_chain_id,null,`ring ${ordinal}: unexpected clip`);
  }
  return {nodes:TREE.nodes,wrapping_operations:TREE.wraps,padding:TREE.padding,
    root_sizing:'auto window root stretched to full 300x300 viewport before layout',
    paint_order:'outer-to-inner',rings};
}

function assertImage(image,dpr) {
  assert([1,2].includes(dpr),'This comparator is scoped to DPR 1 or 2');
  assert.equal(image.width,TREE.width*dpr,'full image width; no resizing or cropping');
  assert.equal(image.height,TREE.height*dpr,'full image height; no resizing or cropping');
  assert.equal(image.data.length,image.width*image.height*4,'complete RGBA image required');
}

function reference(dpr) {
  const width=TREE.width*dpr,height=TREE.height*dpr;
  const data=new Uint8Array(width*height*4);
  const regions=new Int16Array(width*height); regions.fill(-1);
  for(let p=0;p<width*height;p++) data.set(white,4*p);
  for(const ring of expectedTreeRings()) {
    const b=ring.bounds;
    for(let y=b.y*dpr;y<(b.y+b.height)*dpr;y++) {
      for(let x=b.x*dpr;x<(b.x+b.width)*dpr;x++) {
        const p=y*width+x; regions[p]=ring.ordinal; data.set(ring.rgba,4*p);
      }
    }
  }
  return {width,height,data,regions};
}

// Synthetic fixture only. Success evidence must always come from real browser captures.
export function treeReferenceImage(dpr=1) {
  const {regions,...image}=reference(dpr); return image;
}

export function inspectTreeImage(image,dpr=1) {
  assertImage(image,dpr);
  const expected=reference(dpr);
  const rings=expectedTreeRings().map(r => ({...r,expected_pixels:r.visible_pixels*dpr*dpr,
    pixels:0,matching_pixels:0,mismatched_pixels:0,observed_colors:{}}));
  // This is a diagnostic subset of ring 0, not an extra region or unpainted
  // background. It caught the old transparent-wrapper/shrinkwrapped-root bug.
  const rootOnlyBottom={bounds:{x:0,y:204,width:300,height:96},rgba:[0,128,0,255],
    subset_of_ring:0,
    expected_pixels:28800*dpr*dpr,pixels:0,matching_pixels:0,mismatched_pixels:0,observed_colors:{}};
  const colors={}; let mismatched=0; const first=[];
  for(let p=0;p<image.width*image.height;p++) {
    const actual=Array.from(image.data.subarray(4*p,4*p+4));
    const wanted=Array.from(expected.data.subarray(4*p,4*p+4));
    const key=colorKey(actual); colors[key]=(colors[key]||0)+1;
    const region=rings[expected.regions[p]];
    assert(region,'The full viewport must be covered by the window-root quad');
    region.pixels++;
    region.observed_colors[key]=(region.observed_colors[key]||0)+1;
    const different=actual.some((v,i)=>v!==wanted[i]);
    if(different) {
      mismatched++;region.mismatched_pixels++;
      if(first.length<12) first.push({x:p%image.width,y:Math.floor(p/image.width),expected:wanted,actual,ring:expected.regions[p]});
    } else region.matching_pixels++;
    if(Math.floor(p/image.width)>=204*dpr) {
      rootOnlyBottom.pixels++;
      rootOnlyBottom.observed_colors[key]=(rootOnlyBottom.observed_colors[key]||0)+1;
      if(different)rootOnlyBottom.mismatched_pixels++;else rootOnlyBottom.matching_pixels++;
    }
  }
  return {status:mismatched?'failed':'passed',width:image.width,height:image.height,dpr,
    checked_pixels:image.width*image.height,matching_pixels:image.width*image.height-mismatched,
    mismatched_pixels:mismatched,first_mismatches:first,palette_counts:colors,rings,root_only_bottom:rootOnlyBottom};
}

export function compareTreeImages(rust,moonbit,dpr=1) {
  const rustInspection=inspectTreeImage(rust,dpr),moonInspection=inspectTreeImage(moonbit,dpr);
  let differentPixels=0,differentChannels=0,maxChannelDelta=0;
  for(let p=0;p<rust.width*rust.height;p++) {
    let different=false;
    for(let c=0;c<4;c++) {
      const delta=Math.abs(rust.data[4*p+c]-moonbit.data[4*p+c]);
      if(delta) {different=true;differentChannels++;maxChannelDelta=Math.max(maxChannelDelta,delta);}
    }
    if(different) differentPixels++;
  }
  return {status:!differentPixels&&rustInspection.status==='passed'&&moonInspection.status==='passed'?'passed':'failed',
    scope:`pinned default tree.rs; 300x300 CSS pixels; Chromium DPR ${dpr}; exact full-frame RGBA`,
    checked_pixels:rust.width*rust.height,different_pixels:differentPixels,different_channels:differentChannels,
    max_channel_delta:maxChannelDelta,threshold:0,mask:'none',resampling:'none',rust:rustInspection,moonbit:moonInspection,
    unverified:['native renderer parity','non-default depths','other viewport sizes','other browsers and GPUs']};
}

function renderSyntheticScene(example,dpr) {
  const width=300*dpr,height=300*dpr,data=new Uint8Array(width*height*4);
  for(let p=0;p<width*height;p++) data.set(white,4*p);
  for(const item of example.frame.snapshot.items) {
    const b=item.bounds;
    for(let y=Math.max(0,b.y*dpr);y<Math.min(height,(b.y+b.height)*dpr);y++)
      for(let x=Math.max(0,b.x*dpr);x<Math.min(width,(b.x+b.width)*dpr);x++) data.set(rgba(item.color),4*(y*width+x));
  }
  return {width,height,data};
}

// These intentionally corrupted inputs prove rejection sensitivity. They never
// replace either browser image, nor count as Rust/candidate rendering evidence.
export function treeNegativeControls(example,actualImage,dpr=1) {
  assertTreeScene(example,dpr);
  assert.equal(inspectTreeImage(actualImage,dpr).status,'passed','negative controls need a verified real/synthetic baseline');
  const controls=[];
  for(const [name,mutate] of [
    ['shrinkwrapped_root',e=>{e.frame.snapshot.items[0].bounds.height=204;}],
    ['shifted_layout',e=>{for(const q of e.frame.snapshot.items)q.bounds.x+=1;}],
    ['reordered_paint',e=>{const a=e.frame.snapshot.items;[a[0],a[1]]=[a[1],a[0]];}],
    ['missing_node',e=>{e.frame.snapshot.items.splice(25,1);}],
  ]) {
    const bad=structuredClone(example);mutate(bad);
    let sceneRejected=false;try {assertTreeScene(bad,dpr);} catch {sceneRejected=true;}
    const image=renderSyntheticScene(bad,dpr),comparison=compareTreeImages(actualImage,image,dpr);
    assert(sceneRejected,`${name}: scene negative control must be rejected`);
    assert(comparison.different_pixels>0 && comparison.status==='failed',`${name}: pixel negative control must be rejected`);
    controls.push({name,scene_rejected:sceneRejected,pixel_rejected:true,different_pixels:comparison.different_pixels,
      input:'intentionally mutated scene rendered by test-only rectangle fixture'});
  }
  for(const [name,x,y] of [['recolored_pixel',100,100],['recolored_root_only_bottom',0,299]]) {
    const bad={...actualImage,data:actualImage.data.slice()};
    bad.data[4*((y*dpr)*bad.width+x*dpr)+2]^=1;
    const comparison=compareTreeImages(actualImage,bad,dpr);
    assert.equal(comparison.status,'failed');assert.equal(comparison.different_pixels,1);
    controls.push({name,pixel_rejected:true,different_pixels:1,input:'one physical screenshot pixel intentionally changed'});
  }
  return controls;
}
