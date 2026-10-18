import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {drawFrame,validateFrame} from '../moonbit/site/render.mjs';
import {metadata,blue,clear,quad,label,previewFrame,adjacentPreviews,borderedPreview,isShadow,recorder} from './fixtures/drag-drop-render-fixture.mjs';

function paint(frame=previewFrame(),scale=1,draw=drawFrame) {
  const result=recorder();draw(result.context,frame,metadata,scale);return result;
}
function checkLayers(states,scale=1,opacity=1) {
  const shadows=states.filter(isShadow);
  assert.equal(shadows.length,2,'source shadow_md requires both layers');
  assert.deepEqual(shadows.map(s=>[s.shadowColor,s.shadowBlur,s.shadowOffsetX,s.shadowOffsetY,s.globalAlpha]),[
    ['rgba(0,0,0,.1)',6*scale,4096*scale,4*scale,opacity],
    ['rgba(0,0,0,.1)',4*scale,4096*scale,2*scale,opacity],
  ]);
  assert.deepEqual(shadows.map(s=>s.path),[
    [['roundRect',201-4096,201,118,48,0]],
    [['roundRect',202-4096,202,116,46,0]],
  ]);
}
function checkAdjacentOrder(states) {
  assert.deepEqual(states.filter(isShadow).map(s=>[s.path[0][2],s.shadowBlur]),[[201,6],[251,6],[202,4],[252,4]]);
  const firstBody=states.findIndex(s=>s.kind==='fill'&&!isShadow(s)&&s.path[0]?.[2]===200);
  for(const [index,state] of states.entries())if(isShadow(state)&&state.path[0][2]>=250)
    assert(index<firstBody,'later unblurred nonintersecting shadow must precede the first body');
}
function checkOverlayOrder(states) {
  const border=states.findIndex(s=>s.kind==='stroke');
  assert(border>=0);
  const text=states.findIndex(s=>s.kind==='fillText'&&s.args[0]==='Drop items here');
  assert(text>=0&&text<border,'the source border continuation follows its child text');
  for(const [index,state] of states.entries())if(isShadow(state))
    assert(index>border,'intersecting preview shadows must remain above the earlier full-bounds border quad');
  assert.equal(states.filter(s=>s.kind==='stroke').length,1,'no border repaint workaround');
}

test('shadow_md emits the two pinned source layers in declaration order',()=>{
  const r=paint();checkLayers(r.states);
  assert.deepEqual(r.states.map(s=>s.kind),['fill','fill','fill','fillText']);
  assert.deepEqual(r.states[2].path,[['roundRect',200,200,120,50,0]]);
});

test('source preview fill0.5, white text1 and both shadow element opacities1 stay independent',()=>{
  const r=paint();checkLayers(r.states);
  const body=r.states.find(s=>s.kind==='fill'&&!isShadow(s)),text=r.states.find(s=>s.kind==='fillText');
  assert.equal(body.fillStyle,'rgba(0,0,255,1)');assert.equal(body.globalAlpha,.5);
  assert.notEqual(body.globalAlpha,128/255,'source0.5 must not be byte-alpha quantized');
  assert.equal(text.fillStyle,'rgba(255,255,255,1)');assert.equal(text.globalAlpha,1);
  for(const shadow of r.states.filter(isShadow))assert.equal(.1*shadow.globalAlpha,.1);
});

test('shadow_md explicitly accepts independent finite endpoint and fractional element opacity',()=>{
  for(const opacity of [0,.25,1]) {
    const f=previewFrame();f.shadows[0].element_opacity=opacity;
    const r=paint(f);checkLayers(r.states,1,opacity);
    assert.equal(r.states.find(s=>s.kind==='fill'&&!isShadow(s)).globalAlpha,.5);
    assert.equal(r.states.find(s=>s.kind==='fillText').globalAlpha,1);
  }
});

test('shadow_md device lengths scale but spread caster paths stay logical',()=>{
  for(const scale of [1,1.5,2,4]) {
    const r=paint(previewFrame(),scale);checkLayers(r.states,scale);
    assert.deepEqual(r.calls.find(c=>c[0]==='setTransform'),['setTransform',scale,0,0,scale,0,0]);
  }
});

test('separate full-bounds solid2 and solid3 border quads follow text with opaque strokes',()=>{
  const f=previewFrame();f.snapshot.items=[];f.shadows=[];
  for(const [id,width,opacity,y] of [[1,2,.2,100],[4,3,.5,300]]) {
    const b={x:100,y,width:128,height:128};
    f.snapshot.items.push(quad(id,b,blue,opacity),label(id+1,{x:130,y:y+51,width:68,height:26},'Item (0)',blue,16),quad(id+2,b,clear));
    f.decorations.push({id:id+2,radius:0,border:'#0000ff',border_width:width,border_style:'solid'});
  }
  const r=paint(f);
  assert.deepEqual(r.states.map(s=>s.kind),['fill','fillText','fill','stroke','fill','fillText','fill','stroke']);
  assert.deepEqual(r.states.filter(s=>s.kind==='stroke').map(s=>[s.lineWidth,s.globalAlpha,s.strokeStyle,s.path]),[
    [2,1,'#0000ff',[['roundRect',101,101,126,126,0]]],
    [3,1,'#0000ff',[['roundRect',101.5,301.5,125,125,0]]],
  ]);
  assert.deepEqual(r.states.filter(s=>s.kind==='fill').map(s=>[s.fillStyle,s.globalAlpha,s.path[0].slice(1)]),[
    ['rgba(0,0,255,1)',.2,[100,100,128,128,0]],['rgba(0,0,0,0)',1,[100,100,128,128,0]],
    ['rgba(0,0,255,1)',.5,[100,300,128,128,0]],['rgba(0,0,0,0)',1,[100,300,128,128,0]],
  ]);
  for(const s of r.states.filter(s=>s.kind==='fillText'))assert.equal(s.globalAlpha,1);
});

test('solid2 retains finite width, radius and4px minimum extent guards; dashed remains1px only',()=>{
  const f=previewFrame();f.shadows=[];f.snapshot.items=[quad(1,{x:0,y:0,width:4,height:4})];
  f.decorations=[{id:1,radius:2,border:'#0000ff',border_width:2,border_style:'solid'}];
  assert.doesNotThrow(()=>validateFrame(f));
  for(const mutate of [
    g=>g.snapshot.items[0].bounds.width=3.99,g=>g.snapshot.items[0].bounds.height=3.99,
    g=>g.decorations[0].border_style='dashed',g=>g.decorations[0].radius=-1,
    g=>g.decorations[0].radius=2.01,g=>g.decorations[0].radius=NaN,g=>g.decorations[0].radius=Infinity,
    ...[0,.5,1.5,2.5,5,-1,NaN,Infinity,'2',null].map(width=>g=>g.decorations[0].border_width=width),
  ]) {
    const bad=structuredClone(f);mutate(bad);const r=recorder();
    assert.throws(()=>drawFrame(r.context,bad,metadata,1));assert.equal(r.calls.length,0);
  }
});

test('shadow_md rejects missing/extra fields, non-quads, duplicate IDs and nonpositive spread extents before Canvas calls',()=>{
  const mutations=[
    f=>f.shadows=null,f=>f.shadows={},f=>f.shadows=[null],f=>f.shadows=[[]],f=>f.shadows=[1],
    f=>delete f.shadows[0].id,f=>delete f.shadows[0].kind,f=>delete f.shadows[0].element_opacity,
    f=>f.shadows[0].kind='shadow_xl',f=>f.shadows[0].id=101,f=>f.shadows[0].id=999,
    ...['blur','spread','offset_x','offset_y','opacity','color','extra'].map(key=>f=>f.shadows[0][key]=1),
    ...[undefined,null,NaN,Infinity,-Infinity,-.01,1.01,'1',true].map(value=>f=>f.shadows[0].element_opacity=value),
    f=>f.shadows.push({...f.shadows[0]}),f=>f.shadows.push({id:100,kind:'shadow_sm'}),
    f=>f.snapshot.items.push({...f.snapshot.items[0]}),
    ...[0,2,3.99,4].flatMap(size=>['width','height'].map(axis=>f=>f.snapshot.items[0].bounds[axis]=size)),
    f=>f.scroll={first_id:100,top:0,height:600,y:0,max:0},
    f=>f.snapshot.items[0].transform={a:1,b:0,c:0,d:1,tx:1,ty:0},
    f=>f.snapshot.items[1].transform={a:1,b:1,c:0,d:1,tx:0,ty:0},
    f=>f.decorations.push({id:100,radius:0,border:'#0000ff',border_width:2,border_style:'solid',shadow:true}),
    f=>{f.snapshot.items.push(quad(20,{x:0,y:0,width:12,height:12}));f.decorations.push({id:20,radius:0,border:'#0000ff',border_width:2,border_style:'solid',shadow:true});},
    f=>{f.snapshot.items[0].bounds.x=Number.MAX_VALUE;f.snapshot.items[0].bounds.width=Number.MAX_VALUE;},
  ];
  for(const mutate of mutations) {
    const f=previewFrame();mutate(f);const r=recorder();
    assert.throws(()=>drawFrame(r.context,f,metadata,1));assert.equal(r.calls.length,0);
  }
  const small=previewFrame();small.snapshot.items[0].bounds.width=4.01;
  assert.doesNotThrow(()=>validateFrame(small));
});

test('shadow_sm keeps its original two-key descriptor and inherited opacity alongside md',()=>{
  const f=previewFrame();f.snapshot.items.push(quad(200,{x:400,y:200,width:120,height:50},blue,.4));
  f.shadows.push({id:200,kind:'shadow_sm'});
  const states=paint(f).states.filter(isShadow);
  assert.deepEqual(states.map(s=>[s.shadowBlur,s.shadowOffsetY,s.globalAlpha]),[[6,4,1],[3,1,.4],[4,2,1],[2,1,.4]]);
  for(const extra of ['element_opacity','blur']) {
    const bad=structuredClone(f);bad.shadows[1][extra]=1;const r=recorder();
    assert.throws(()=>drawFrame(r.context,bad,metadata,1));assert.equal(r.calls.length,0);
  }
});

test('shadow_md retains viewport and inherited clips for actual blur tails and restores context',()=>{
  const f=previewFrame();f.snapshot.clip_chains=[{id:7,rects:[{x:190,y:195,width:100,height:50},{x:210,y:210,width:40,height:20}]}];
  for(const item of f.snapshot.items){item.clip_chain_id=7;item.transform={a:1,b:0,c:0,d:1,tx:0,ty:0};}
  const r=paint(f,2);checkLayers(r.states,2);
  for(const state of r.states)assert.deepEqual(state.clips,[['rect',0,0,800,600],['rect',190,195,100,50],['rect',210,210,40,20]]);
  for(const state of r.states.filter(s=>!isShadow(s))) {
    assert.equal(state.shadowBlur,0);assert.equal(state.shadowOffsetX,0);assert.equal(state.shadowOffsetY,0);
    assert.equal(state.shadowColor,'transparent');
  }
  assert.deepEqual(r.state,r.initial);assert.equal(r.stack.length,0);
  const failed=recorder({failFill:true});
  assert.throws(()=>drawFrame(failed.context,f,metadata,2),/Synthetic Canvas paint failure/);
  assert.deepEqual(failed.state,failed.initial);assert.equal(failed.stack.length,0);
});

test('shadow_md emits no blur-only commands through fully clipped or disjoint fractional masks',()=>{
  for(const rects of [
    [{x:0,y:0,width:800,height:199}],
    [{x:200,y:200,width:120,height:.2},{x:200,y:200.3,width:120,height:.2}],
  ]) {
    const f=previewFrame();f.snapshot.clip_chains=[{id:7,rects}];
    for(const item of f.snapshot.items)item.clip_chain_id=7;
    const r=paint(f,2);assert.equal(r.states.length,0);
  }
});

test('adjacent md previews preserve strict unblurred ordering and stable layer/source ties',()=>{
  const r=paint(adjacentPreviews());checkAdjacentOrder(r.states);
});

test('overlapping md preview shadows follow earlier full-bounds transparent border quads',()=>{
  const r=paint(borderedPreview());checkOverlayOrder(r.states);
});

test('md scheduling uses offset/spread bounds without blur tails and Shadow-before-Quad ties',()=>{
  const f=previewFrame();f.snapshot.items[0].bounds={x:0,y:0,width:120,height:50};
  f.snapshot.items[1].bounds={x:42,y:15,width:36,height:19};
  f.snapshot.items.unshift(quad(1,{x:0,y:0,width:120,height:4},{red:255,green:0,blue:0,alpha:255}));
  const states=paint(f).states;
  assert.deepEqual(states.map(s=>isShadow(s)?`shadow${s.shadowBlur}`:s.kind==='fill'?s.fillStyle:'text'),[
    'shadow6','rgba(255,0,0,1)','shadow4','rgba(0,0,255,1)','text',
  ]);
});

test('md ordering outward-covers offset/spread boxes before strict device-pixel intersection',()=>{
  const f=previewFrame();f.snapshot.items[0].bounds.x=19.3;
  f.snapshot.items.unshift(quad(1,{x:0,y:200,width:20.2,height:50},{red:255,green:0,blue:0,alpha:255}));
  for(const scale of [1,2]) {
    const states=paint(f,scale).states;
    const prior=states.findIndex(s=>s.kind==='fill'&&s.fillStyle==='rgba(255,0,0,1)');
    const firstShadow=states.findIndex(s=>isShadow(s)&&s.shadowBlur===6*scale);
    assert(prior<firstShadow,'the fractional logical gap closes under outward device coverage');
  }
});

// Deliberate in-memory renderer substitutions are command-recorder controls.
// They neither generate nor relabel original screenshots or browser evidence.
const source=await readFile(new URL('../moonbit/site/render.mjs',import.meta.url),'utf8');
async function mutatedDraw(before,after) {
  assert(source.includes(before),'negative-control mutation anchor must remain present');
  const mutated=source.replace(before,after);
  assert.notEqual(mutated,source);
  return (await import(`data:text/javascript;base64,${Buffer.from(mutated).toString('base64')}`)).drawFrame;
}

for(const blur of [6,4])test(`negative control: inheriting fill0.5 fails the md blur${blur} layer opacity check`,async()=>{
  const draw=await mutatedDraw("shadowStyle?.kind === 'shadow_md' ? shadowStyle.element_opacity : item.opacity ?? 1",'item.opacity ?? 1');
  const layer=paint(previewFrame(),1,draw).states.find(s=>isShadow(s)&&s.shadowBlur===blur);
  assert.equal(layer.globalAlpha,.5);assert.equal(.1*layer.globalAlpha,.05);
  assert.throws(()=>assert.equal(layer.globalAlpha,1),assert.AssertionError);
});

test('negative controls reject either missing md layer and changed source parameters/order',async()=>{
  for(const [before,after] of [
    ['    {offset_x:0,offset_y:4,blur:6,spread:-1},\n',''],
    ['    {offset_x:0,offset_y:2,blur:4,spread:-2},\n',''],
    ['offset_x:0,offset_y:4,blur:6,spread:-1','offset_x:1,offset_y:4,blur:6,spread:-1'],
    ['offset_x:0,offset_y:4,blur:6,spread:-1','offset_x:0,offset_y:3,blur:6,spread:-1'],
    ['offset_x:0,offset_y:2,blur:4,spread:-2','offset_x:0,offset_y:1,blur:4,spread:-2'],
    ['offset_x:0,offset_y:4,blur:6,spread:-1','offset_x:0,offset_y:4,blur:5,spread:-1'],
    ['offset_x:0,offset_y:2,blur:4,spread:-2','offset_x:0,offset_y:2,blur:3,spread:-2'],
    ['offset_x:0,offset_y:4,blur:6,spread:-1','offset_x:0,offset_y:4,blur:6,spread:0'],
    ['offset_x:0,offset_y:2,blur:4,spread:-2','offset_x:0,offset_y:2,blur:4,spread:-1'],
    ['[...sourceShadowLayers[shadowStyle.kind],null]','[...sourceShadowLayers[shadowStyle.kind]].reverse().concat([null])'],
  ]) {
    const draw=await mutatedDraw(before,after);
    assert.throws(()=>checkLayers(paint(previewFrame(),1,draw).states),assert.AssertionError);
  }
});

test('negative control rejects inline source-item shadow paint ordering',async()=>{
  const draw=await mutatedDraw('a.order-b.order || a.kind-b.kind || a.index-b.index','a.index-b.index');
  assert.throws(()=>checkAdjacentOrder(paint(adjacentPreviews(),1,draw).states),assert.AssertionError);
});

test('negative control rejects a global all-shadows prepass',async()=>{
  const draw=await mutatedDraw('a.order-b.order || a.kind-b.kind || a.index-b.index','a.kind-b.kind || a.order-b.order || a.index-b.index');
  assert.throws(()=>checkOverlayOrder(paint(borderedPreview(),1,draw).states),assert.AssertionError);
});

test('negative control rejects the legacy preview-shadow stand-in',()=>{
  const f=previewFrame();f.shadows=[];
  f.decorations=[{id:100,radius:0,border:'#0000ff',border_width:1,border_style:'solid',shadow:true}];
  assert.throws(()=>checkLayers(paint(f).states),assert.AssertionError);
});
