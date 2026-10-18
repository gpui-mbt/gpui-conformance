import test from 'node:test';
import assert from 'node:assert/strict';
import {assertPatternInkDisjoint,readPatternFrame,createPatternLifecycle,patternRenderScale} from '../moonbit/site/pattern-host.mjs';
const metadata={font_family:'IBM Plex Sans',source_blob:'7d2e98d16e24dc23dc307296a3b35c18e624d9e3',runs:[{text:'Pattern Example',font_size:20},{text:'Elements the same height should align',font_size:20}]};
const context={measureText:()=>({width:100,fontBoundingBoxAscent:20,fontBoundingBoxDescent:5,actualBoundingBoxLeft:0,actualBoundingBoxRight:100,actualBoundingBoxAscent:18,actualBoundingBoxDescent:4})};
function fixture(){return {ok:true,pattern:{comparison_profile_match:true,text_order:'disjoint_ink_checked_labels_last'},snapshot:{items:[{kind:'paint',id:30,shape:{bounds:{x:0,y:100,width:256,height:56}}},...([100,101].map((id,i)=>({kind:'text_run',id,font_size:20,text:'label',text_origin:{x:0,y:i*40},bounds:{x:0,y:i*40,width:100,height:33}})))]}};}
test('actual glyph ink is checked separately from advance and source line bounds',()=>{
 const f=fixture();assert.equal(assertPatternInkDisjoint(context,f,metadata).length,2);
 const overflow={measureText:()=>({...context.measureText(),actualBoundingBoxDescent:100})};
 assert.throws(()=>assertPatternInkDisjoint(overflow,f,metadata),/overlaps/);
});
test('missing ink metrics, labels and paint geometry fail closed',()=>{
 assert.throws(()=>assertPatternInkDisjoint({measureText:()=>({width:100})},fixture(),metadata),/ink/);
 const f=fixture();f.snapshot.items.pop();assert.throws(()=>assertPatternInkDisjoint(context,f,metadata),/labels/);
 const g=fixture();delete g.snapshot.items[0].shape;assert.throws(()=>assertPatternInkDisjoint(context,g,metadata),/geometry/);
});
test('profile and source identity checked before invoking runtime',()=>{
 let calls=0;const runtime={pattern_frame_at_scale(){calls++;return JSON.stringify(fixture());}};
 assert.throws(()=>readPatternFrame(runtime,context,{innerWidth:600,innerHeight:600,devicePixelRatio:0},metadata),/viewport/);
 assert.throws(()=>readPatternFrame(runtime,context,{innerWidth:600,innerHeight:600,devicePixelRatio:1},{...metadata,source_blob:'wrong'}),/metadata/);
 assert.equal(calls,0);
 const result=readPatternFrame(runtime,context,{innerWidth:600,innerHeight:600,devicePixelRatio:1},metadata);
 assert.equal(calls,1);assert.deepEqual(result.widths,[100,100]);assert.equal(result.glyphInk.length,2);
});

test('DPR-only transitions and cached-page restore invalidate and recover the exact profile',()=>{
 const listeners=new Map(),queries=[];
 const windowObject={innerWidth:600,innerHeight:600,devicePixelRatio:1,
   addEventListener(name,fn){listeners.set(name,fn);},removeEventListener(name,fn){if(listeners.get(name)===fn)listeners.delete(name);},
   matchMedia(){const callbacks=new Set();const query={addEventListener(_,fn){callbacks.add(fn);},removeEventListener(_,fn){callbacks.delete(fn);},fire(){for(const fn of [...callbacks])fn();},callbacks};queries.push(query);return query;}};
 let calls=0,status='initial',frame;
 const runtime={pattern_frame_at_scale(w,h,widths,dpr,scale){calls++;const f=fixture();f.pattern.comparison_profile_match=w===600&&h===600&&dpr===1&&scale===1;return JSON.stringify(f);}};
 function render(){try{frame=readPatternFrame(runtime,context,windowObject,metadata);status='ready';}catch{frame=undefined;status='failed';}}
 render();assert.equal(calls,1);assert.equal(status,'ready');
 const lifecycle=createPatternLifecycle(windowObject,render,()=>{frame=undefined;status='suspended';});
 windowObject.devicePixelRatio=2;queries.at(-1).fire();
 assert.equal(status,'ready');assert.equal(frame.frame.pattern.comparison_profile_match,false);assert.equal(calls,2);
 windowObject.devicePixelRatio=1;queries.at(-1).fire();assert.equal(status,'ready');assert.equal(calls,3);
 listeners.get('pagehide')();assert.equal(status,'suspended');assert.equal(frame,undefined);assert(lifecycle.suspended);
 windowObject.devicePixelRatio=2;listeners.get('pageshow')();
 assert.equal(status,'ready');assert.equal(frame.frame.pattern.comparison_profile_match,false);assert.equal(calls,4);assert(!lifecycle.suspended);
 windowObject.devicePixelRatio=1;queries.at(-1).fire();assert.equal(status,'ready');assert.equal(calls,5);
 lifecycle.stop();lifecycle.stop();assert.equal(listeners.size,0);assert(queries.every(q=>q.callbacks.size===0));
 windowObject.devicePixelRatio=2;queries.at(-1).fire();assert.equal(calls,5);
});


test('ordinary viewports and high DPR stay inside the frozen physical resource caps',()=>{
 for(const w of [1,320,600,801,1280,2048])for(const h of [1,480,600,900,2048])for(const dpr of [.25,1,1.25,2,3,4,64]) {
  const p=patternRenderScale(w,h,dpr);
  assert(p.backingWidth<=2048&&p.backingHeight<=2048&&p.backingWidth*p.backingHeight<=1048576);
  assert(p.effectiveRenderScale>=.25&&p.effectiveRenderScale<=4);
  assert.equal(p.renderScaleReduced,p.effectiveRenderScale!==dpr);
  assert.equal(Math.ceil(p.backingWidth/p.effectiveRenderScale*p.effectiveRenderScale),p.backingWidth);
  assert.equal(Math.ceil(p.backingHeight/p.effectiveRenderScale*p.effectiveRenderScale),p.backingHeight);
 }
 assert.deepEqual(patternRenderScale(600,600,1),{actualDeviceScale:1,effectiveRenderScale:1,backingWidth:600,backingHeight:600,renderScaleReduced:false});
 for(const [w,h,dpr] of [[0,600,1],[2049,600,1],[600,Infinity,1],[600,600,NaN],[600,600,65]])assert.throws(()=>patternRenderScale(w,h,dpr),/viewport/);
});
test('classification cannot be forged by reduced scale or stale core metadata',()=>{
 const runtime={pattern_frame_at_scale(){return JSON.stringify(fixture());}};
 assert.throws(()=>readPatternFrame(runtime,context,{innerWidth:600,innerHeight:600,devicePixelRatio:2},metadata),/metadata mismatch/);
});

test('live canvas background is accepted only as the validated first white viewport quad',()=>{
 const f=fixture();f.snapshot.viewport={x:0,y:0,width:600,height:600};
 const background={kind:'quad',id:0,bounds:{x:0,y:0,width:600,height:600},color:{red:255,green:255,blue:255,alpha:255},opacity:1,clip_chain_id:null,transform:{a:1,b:0,c:0,d:1,tx:0,ty:0}};
 f.snapshot.items.unshift(background);assert.equal(assertPatternInkDisjoint(context,f,metadata).length,2);
 background.color.alpha=0;assert.throws(()=>assertPatternInkDisjoint(context,f,metadata),/background/);
 background.color.alpha=255;f.snapshot.items.reverse();assert.throws(()=>assertPatternInkDisjoint(context,f,metadata),/background|labels/);
});
