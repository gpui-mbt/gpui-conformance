import test from 'node:test';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {readAnchorFrame} from '../moonbit/site/anchor-host.mjs';
import {validateFrame,drawFrame} from '../moonbit/site/render.mjs';
const runtimePath=process.env.GPUI_ANCHOR_RUNTIME;
test('compiled anchor uses all eight core local/deferred placements and restores across actual viewport inputs', {skip:!runtimePath}, async()=>{
  const r=await import(pathToFileURL(runtimePath));
  const m=JSON.parse(r.anchor_metadata());
  assert.equal(m.runs.length,19);
  const context={measureText:text=>({width:text.length*7})};
  const read=width=>readAnchorFrame(r,context,{innerWidth:width,innerHeight:600,devicePixelRatio:1},m).frame;
  const q=(f,id)=>f.snapshot.items.find(i=>i.id===id);
  r.anchor_reset();const initial=read(750);
  for(const width of [750,480,750]) {
    r.anchor_pointer(0,0,false);const idle=read(width);validateFrame(idle);
    assert.equal(idle.anchor.hovered,-1);assert.equal(idle.decorations.length,8);
    assert.equal(q(idle,104),undefined);assert.equal(q(idle,200),undefined);
    for(const index of [0,1,2,3,5,6,7,8]) {
      const b=q(idle,index+10).bounds;
      // Candidate-only test targets its actual layout, not screenshot oracle locations.
      r.anchor_pointer(Math.max(1,b.x+60),b.y+32,true);
      const hover=read(width);validateFrame(hover);
      assert.equal(hover.anchor.hovered,index);assert.equal(hover.anchor.layout_passes,2);
      const popup=q(hover,200).bounds;
      assert.deepEqual(q(hover,index+10).color,{red:0,green:0,blue:0,alpha:255});
      assert.equal(q(hover,201).text,m.runs[index+1].text);
      assert.equal(q(hover,200).color.alpha,191);
      assert.equal(popup.height,27);assert(popup.width>=100);
      const localX=[0,60,120,120,0,0,0,60,120][index];
      const localY=[0,0,0,-32.5,0,-32.5,-65,-65,-65][index];
      const ax=[0,.5,1,0,0,1,0,.5,1][index];
      const ay=[0,0,0,.5,0,.5,1,1,1][index];
      assert.equal(popup.x,Math.round(Math.max(0,Math.min(width-popup.width,b.x+localX-popup.width*ax))));
      assert.equal(popup.y,Math.round(Math.max(0,Math.min(600-popup.height,b.y+65+localY-popup.height*ay))));
      assert(popup.x>=0&&popup.y>=0&&popup.x+popup.width<=width&&popup.y+popup.height<=600);
      assert.deepEqual(hover.shadows,[{id:200,kind:'shadow_sm'}]);
      assert(q(hover,201).bounds.x===popup.x+8&&q(hover,201).bounds.y===popup.y+2);
      assert(hover.snapshot.items.findIndex(i=>i.id===200)>hover.snapshot.items.findIndex(i=>i.id===108));
      const painter=new Proxy({}, {get:(_o,key)=>key==='measureText'?()=>({fontBoundingBoxAscent:14,fontBoundingBoxDescent:4}):()=>{}});
      drawFrame(painter,hover,{...m,width,height:600},1);
      r.anchor_pointer(0,0,false);assert.deepEqual(read(width),idle);
    }
    const center=q(idle,14).bounds;r.anchor_pointer(center.x+60,center.y+32,true);
    assert.deepEqual(read(width),idle);
  }
  r.anchor_reset();assert.deepEqual(read(750),initial);
  for(const [w,h,d] of [[3,600,1],[480,3,1],[750,600,5]])
    assert.equal(JSON.parse(r.anchor_frame(w,h,[],d)).error,'invalid_live_viewport');
  assert.equal(JSON.parse(r.anchor_frame(750,600,[],1)).error,'invalid_metrics');
});
