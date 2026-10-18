import test from 'node:test';
import assert from 'node:assert/strict';
import {assertPatternInkDisjoint,readPatternFrame,createPatternLifecycle} from '../moonbit/site/pattern-host.mjs';
const metadata={font_family:'IBM Plex Sans',source_blob:'7d2e98d16e24dc23dc307296a3b35c18e624d9e3',runs:[{text:'Pattern Example',font_size:20},{text:'Elements the same height should align',font_size:20}]};
const context={measureText:()=>({width:100,fontBoundingBoxAscent:20,fontBoundingBoxDescent:5,actualBoundingBoxLeft:0,actualBoundingBoxRight:100,actualBoundingBoxAscent:18,actualBoundingBoxDescent:4})};
function fixture(){return {ok:true,pattern:{text_order:'disjoint_ink_checked_labels_last'},snapshot:{items:[{kind:'paint',id:30,shape:{bounds:{x:0,y:100,width:256,height:56}}},...([100,101].map((id,i)=>({kind:'text_run',id,font_size:20,text:'label',text_origin:{x:0,y:i*40},bounds:{x:0,y:i*40,width:100,height:33}})))]}};}
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
 assert.throws(()=>readPatternFrame(runtime,context,{innerWidth:600,innerHeight:600,devicePixelRatio:2},metadata),/DPR1/);
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
 const runtime={pattern_frame_at_scale(){calls++;return JSON.stringify(fixture());}};
 function render(){try{frame=readPatternFrame(runtime,context,windowObject,metadata);status='ready';}catch{frame=undefined;status='failed';}}
 render();assert.equal(calls,1);assert.equal(status,'ready');
 const lifecycle=createPatternLifecycle(windowObject,render,()=>{frame=undefined;status='suspended';});
 windowObject.devicePixelRatio=2;queries.at(-1).fire();
 assert.equal(status,'failed');assert.equal(frame,undefined);assert.equal(calls,1);
 windowObject.devicePixelRatio=1;queries.at(-1).fire();assert.equal(status,'ready');assert.equal(calls,2);
 listeners.get('pagehide')();assert.equal(status,'suspended');assert.equal(frame,undefined);assert(lifecycle.suspended);
 windowObject.devicePixelRatio=2;listeners.get('pageshow')();
 assert.equal(status,'failed');assert.equal(frame,undefined);assert.equal(calls,2);assert(!lifecycle.suspended);
 windowObject.devicePixelRatio=1;queries.at(-1).fire();assert.equal(status,'ready');assert.equal(calls,3);
 lifecycle.stop();lifecycle.stop();assert.equal(listeners.size,0);assert(queries.every(q=>q.callbacks.size===0));
 windowObject.devicePixelRatio=2;queries.at(-1).fire();assert.equal(calls,3);
});
