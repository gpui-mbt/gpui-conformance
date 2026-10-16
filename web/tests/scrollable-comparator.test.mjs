import test from 'node:test';
import assert from 'node:assert/strict';
import {SCROLLABLE,inspectInitial,assertTranslation,assertUnchanged,assertClipping,assertHover,
  assertSameFill,assertHorizontalEnd,assertVerticalEnd,assertWheelDelivery,scrollableNegativeControls}
  from './scrollable-comparator.mjs';

// Deliberately small synthetic comparator fixtures, NOT browser/Rust evidence.
// The foreground pattern is artificial ink, not an emulation of text shaping.
function fixture({dx=0,dy=0,hover=false,dpr=1,leak=false}={}) {
  const width=500*dpr,height=500*dpr,data=new Uint8Array(width*height*4);
  const root={x:0,y:0,width:500,height:500};
  function rect(x,y,w,h,color,clip=root) {
    const left=Math.max(0,x,clip.x)*dpr,top=Math.max(0,y,clip.y)*dpr;
    const right=Math.min(500,x+w,clip.x+clip.width)*dpr,bottom=Math.min(500,y+h,clip.y+clip.height)*dpr;
    for(let yy=top;yy<bottom;yy++)for(let xx=left;xx<right;xx++)data.set(color,4*(yy*width+xx));
  }
  function box(x,y,w,h,color,border,clip=root) {
    rect(x,y,w,h,color,clip);rect(x,y,w,1,border,clip);rect(x,y+h-1,w,1,border,clip);
    rect(x,y,1,h,border,clip);rect(x+w-1,y,1,h,border,clip);
  }
  function ink(x,y,w,clip=root) {
    for(let offset=0;offset<w;offset+=6){rect(x+offset,y,3,8,[0,0,0,255],clip);rect(x+offset+3,y+3,2,2,[0,0,0,255],clip);}
  }
  rect(0,0,500,500,[255,255,255,255]);
  box(16,42+dy,468,5000,[242,242,255,255],[0,0,255,255]);
  const inner=leak?root:{x:33,y:59+dy,width:434,height:150};
  box(33+dx,59+dy,2000,150,hover?[194,219,204,255]:[218,231,230,255],[0,128,0,255],inner);
  ink(16,22+dy,240);ink(50+dx,80+dy,90,inner);ink(33,235+dy,80);
  return {width,height,data};
}

test('contract pins the untouched upstream source',()=>{
  assert.equal(SCROLLABLE.sourceBlob,'c81795618875aecf06e06043bd1709c48630b58f');
  assert.equal(SCROLLABLE.width,500);assert.equal(SCROLLABLE.step,12);
});

for(const dpr of [1,2]) {
  test(`DPR ${dpr}: derive exact border and ink translations from full pixels`,()=>{
    const a=fixture({hover:true,dpr}),initial=inspectInitial(a,dpr);
    assert.deepEqual(initial.geometry.green,{x:33,y:59,width:434,height:150});
    const x=fixture({dx:-12,hover:true,dpr}),y=fixture({dx:-12,dy:-12,hover:true,dpr});
    const horizontal=assertTranslation(a,x,initial,{afterX:-12},dpr);
    assert.deepEqual([horizontal.deltas.horizontal.dx,horizontal.deltas.heading.dx],[-12,0]);
    const vertical=assertTranslation(x,y,initial,{beforeX:-12,afterX:-12,afterY:-12},dpr);
    assert(Object.values(vertical.deltas).every(d=>d.dy===-12&&d.dx===0));
    assert.throws(()=>assertTranslation(a,a,initial,{afterX:-12},dpr),/translation/);
    assert.throws(()=>assertTranslation(a,x,initial,{afterY:-12},dpr),/translation/);
  });
  test(`DPR ${dpr}: clipping and hover require independent retained pixel changes`,()=>{
    const initialImage=fixture({dpr}),initial=inspectInitial(initialImage,dpr);
    const shifted=fixture({dx:-12,dpr}),hover=fixture({dx:-12,hover:true,dpr});
    assert.equal(assertClipping(initialImage,shifted,initial,dpr).checked_outside_pixels,2240*dpr*dpr);
    assert.equal(assertSameFill(initialImage,shifted,initial,dpr).status,'passed');
    assert.equal(assertHover(shifted,hover,initial,dpr).status,'passed');
    assert.throws(()=>assertHover(shifted,shifted,initial,dpr),/Hover/);
    assert.throws(()=>assertSameFill(initialImage,hover,initial,dpr),/unhovered/);
    assert.throws(()=>assertClipping(initialImage,fixture({dx:-12,dpr,leak:true}),initial,dpr),/Clipped/);
  });
  test(`DPR ${dpr}: endpoints require visible borders and padding, not blank unchanged frames`,()=>{
    const initial=inspectInitial(fixture({dpr}),dpr);
    assert.equal(assertHorizontalEnd(fixture({dx:-1566,dpr}),initial,dpr).right_border_x,466);
    assert.equal(assertVerticalEnd(fixture({dy:-4558,dpr}),dpr).bottom_border_y,483);
    assert.throws(()=>assertHorizontalEnd(fixture({dx:-100000,dpr}),initial,dpr),/endpoint/);
    assert.throws(()=>assertVerticalEnd(fixture({dy:-100000,dpr}),dpr),/endpoint/);
    assert.throws(()=>assertVerticalEnd(fixture({dy:-4557,dpr}),dpr),/endpoint/);
  });
  test(`DPR ${dpr}: full-image equality catches a single changed physical pixel`,()=>{
    const a=fixture({dpr}),b=fixture({dpr});assert.equal(assertUnchanged(a,b,dpr).status,'passed');
    b.data[0]^=1;assert.throws(()=>assertUnchanged(a,b,dpr),/unchanged/);
  });
  test(`DPR ${dpr}: every intentionally bad evidence control is rejected`,()=>{
    const captures={initial_unhover:fixture({dpr}),initial_hover:fixture({hover:true,dpr}),
      x12:fixture({dx:-12,hover:true,dpr}),x12_unhover:fixture({dx:-12,dpr}),
      y12:fixture({dx:-12,dy:-12,hover:true,dpr})};
    const controls=scrollableNegativeControls(captures,inspectInitial(captures.initial_unhover,dpr),dpr);
    assert.equal(controls.length,9);assert(controls.every(c=>c.rejected));
  });
}

test('reject truncated, rescaled, empty or wrong palette screenshots',()=>{
  const good=fixture();
  assert.throws(()=>inspectInitial({...good,width:499}),/Full/);
  assert.throws(()=>inspectInitial({...good,data:good.data.slice(0,-4)}),/Complete/);
  const blank={...good,data:new Uint8Array(good.data.length)};
  assert.throws(()=>inspectInitial(blank),/borders/);
});

test('wheel evidence must be trusted, delivered to canvas, prevented, pixel-mode and exact',()=>{
  const expected={x:100,y:134,deltaX:12,deltaY:0};
  const event={...expected,trusted:true,target:'CANVAS',deltaMode:0,defaultPrevented:true};
  assert.equal(assertWheelDelivery([event],expected).status,'passed');
  for(const change of [{trusted:false},{target:'BODY'},{deltaMode:1},{defaultPrevented:false},{deltaX:0},{x:99}])
    assert.throws(()=>assertWheelDelivery([{...event,...change}],expected));
  assert.throws(()=>assertWheelDelivery([],expected),/delivered/);
  assert.equal(assertWheelDelivery([{...event,deltaX:5},{...event,deltaX:7}],expected).status,'passed');
});
