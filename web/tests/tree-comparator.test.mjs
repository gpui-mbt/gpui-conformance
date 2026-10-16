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
  assert.deepEqual(rings[0].bounds,{x:0,y:0,width:300,height:204});
  assert.deepEqual(rings[50].bounds,{x:100,y:100,width:100,height:4});
  assert.deepEqual(rings.slice(0,4).map(r=>r.rgba),[[0,128,0,255],[0,0,255,255],[255,0,0,255],[255,255,0,255]]);
  assert.equal(rings.reduce((sum,r)=>sum+r.visible_pixels,0),61200);
  assert.equal(assertTreeScene(fixture()).nodes,51);
});

for(const dpr of [1,2]) {
  test(`DPR ${dpr}: count every ring and every unused white pixel without masks`,()=>{
    const image=treeReferenceImage(dpr),result=compareTreeImages(image,image,dpr);
    assert.equal(result.status,'passed');assert.equal(result.different_pixels,0);
    assert.equal(result.checked_pixels,90000*dpr*dpr);
    assert.equal(result.rust.background.matching_pixels,28800*dpr*dpr);
    assert(result.rust.rings.every(r=>r.matching_pixels===r.expected_pixels));
    assert.equal(Object.keys(result.rust.palette_counts).length,5);
  });
  test(`DPR ${dpr}: reject shifted layout, reordered paint, missing nodes, and isolated pixel recolors`,()=>{
    const negatives=treeNegativeControls(fixture(dpr),treeReferenceImage(dpr),dpr);
    assert.equal(negatives.length,5);assert(negatives.every(n=>n.pixel_rejected&&n.different_pixels>0));
    assert(negatives.slice(0,3).every(n=>n.scene_rejected));
  });
}

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
