import test from 'node:test';
import assert from 'node:assert/strict';
import {TREE,expectedTreeRings,assertTreeScene,treeReferenceImage,inspectTreeImage,compareTreeImages,treeNegativeControls} from './tree-comparator.mjs';

function fixture(dpr=1) {
  return {metadata:{id:'tree',width:300,height:300,depth:50,node_count:51,padding:2},
    frame:{ok:true,conformance:'unverified',decorations:[],host_extensions:[],snapshot:{schema_version:1,
      viewport:{x:0,y:0,width:300,height:300},scale:dpr,resources:[],clip_chains:[],
      items:expectedTreeRings().map(r=>({id:52-r.ordinal,kind:'quad',bounds:r.bounds,
        color:Object.fromEntries(['red','green','blue','alpha'].map((c,i)=>[c,r.rgba[i]])),
        transform:{a:1,b:0,c:0,d:1,tx:0,ty:0},opacity:1,clip_chain_id:null}))}}};
}

test('source-derived contract has 51 blocks, 50 rings, and a four-pixel-high red center',()=>{
  const rings=expectedTreeRings();assert.equal(rings.length,TREE.nodes);
  assert.deepEqual(rings[0].bounds,{x:0,y:0,width:300,height:300});
  assert.deepEqual(rings[1].bounds,{x:2,y:2,width:296,height:200});
  assert.deepEqual(rings[50].bounds,{x:100,y:100,width:100,height:4});
  assert.deepEqual(rings.slice(0,4).map(r=>r.rgba),[[0,128,0,255],[0,0,255,255],[255,0,0,255],[255,255,0,255]]);
  assert.equal(rings[0].visible_pixels,30800);
  assert.equal(rings.reduce((sum,r)=>sum+r.visible_pixels,0),90000);
  assert.equal(assertTreeScene(fixture()).nodes,51);
});

for(const dpr of [1,2]) {
  test(`DPR ${dpr}: count every ring and the root-only bottom region without masks`,()=>{
    const image=treeReferenceImage(dpr),result=compareTreeImages(image,image,dpr);
    assert.equal(result.status,'passed');assert.equal(result.different_pixels,0);
    assert.equal(result.checked_pixels,90000*dpr*dpr);
    assert.equal(result.rust.root_only_bottom.matching_pixels,28800*dpr*dpr);
    assert.equal(result.rust.root_only_bottom.subset_of_ring,0);
    assert.deepEqual(result.rust.root_only_bottom.rgba,[0,128,0,255]);
    assert(result.rust.rings.every(r=>r.matching_pixels===r.expected_pixels));
    assert.deepEqual(result.rust.palette_counts,{'0,128,0,255':44816*dpr*dpr,
      '0,0,255,255':15600*dpr*dpr,'255,0,0,255':15184*dpr*dpr,'255,255,0,255':14400*dpr*dpr});
  });
  test(`DPR ${dpr}: reject shifted layout, reordered paint, missing nodes, and isolated pixel recolors`,()=>{
    const negatives=treeNegativeControls(fixture(dpr),treeReferenceImage(dpr),dpr);
    assert.equal(negatives.length,6);assert(negatives.every(n=>n.pixel_rejected&&n.different_pixels>0));
    assert(negatives.slice(0,4).every(n=>n.scene_rejected));
    assert.equal(negatives.find(n=>n.name==='shrinkwrapped_root').different_pixels,28800*dpr*dpr);
  });
}

test('regression: the old 204px shrinkwrapped root fails even when all inner rings match',()=>{
  const bad=fixture();bad.frame.snapshot.items[0].bounds.height=204;
  assert.throws(()=>assertTreeScene(bad),/ring 0: bounds/);
  const goodImage=treeReferenceImage(),badImage=treeReferenceImage();
  for(let y=204;y<300;y++)for(let x=0;x<300;x++)badImage.data.set([255,255,255,255],4*(y*300+x));
  const comparison=compareTreeImages(goodImage,badImage);
  assert.equal(comparison.status,'failed');assert.equal(comparison.different_pixels,28800);
  assert.equal(comparison.moonbit.root_only_bottom.mismatched_pixels,28800);
  assert(comparison.moonbit.rings.slice(1).every(r=>r.mismatched_pixels===0));
});

test('two identical wrong images cannot certify a wrong tree',()=>{
  const image=treeReferenceImage();image.data[0]=255;
  const result=compareTreeImages(image,image);
  assert.equal(result.different_pixels,0);assert.equal(result.status,'failed');
  assert.equal(result.rust.mismatched_pixels,1);
});

test('reject an alpha-only difference and a truncated capture',()=>{
  const good=treeReferenceImage(),bad=treeReferenceImage();bad.data[3]=254;
  const result=compareTreeImages(good,bad);
  assert.equal(result.status,'failed');assert.equal(result.different_channels,1);
  assert.throws(()=>inspectTreeImage({...good,height:299}),/full image height/);
});

test('scene checks cannot silently discard extra primitives, transforms, clips, or reordered paint',()=>{
  for(const mutate of [e=>e.frame.snapshot.items.reverse(),e=>e.frame.snapshot.items[9].transform.tx=1,
    e=>e.frame.snapshot.items[9].opacity=0.5,e=>e.frame.snapshot.items[9].clip_chain_id=2,
    e=>e.frame.snapshot.items.push({...e.frame.snapshot.items[0],kind:'text'}),
    e=>e.frame.snapshot.items[9].color.green=129]) {
    const f=fixture();mutate(f);assert.throws(()=>assertTreeScene(f));
  }
});
