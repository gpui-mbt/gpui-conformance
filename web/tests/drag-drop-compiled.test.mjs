import test from 'node:test';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {createDragDropHost} from '../moonbit/site/drag-drop-host.mjs';
const path=process.env.DRAG_DROP_RUNTIME;
const runtime=path?await import(pathToFileURL(path).href):null;
const widths=[115,54,54,54,110,33,33,33];
const frame=()=>JSON.parse(runtime.drag_drop_frame(widths,1));
const pointer=(kind,x,y,button=0)=>JSON.parse(runtime.drag_drop_pointer(kind,x,y,button,false,false,false,false));
test('compiled exports retain authentic typed model state through all colors and duplicate release',{skip:!runtime},()=>{
  runtime.drag_drop_reset();let f=frame();assert.equal(f.ok,true);
  assert.equal(JSON.parse(runtime.drag_drop_metadata()).runs.length,8);
  assert.equal(f.drag_drop.session.phase,'idle');
  for(let ix=0;ix<3;ix++) {
    const border=f.snapshot.items.find(item=>item.id===1010+ix).bounds;
    const x=border.x+64,y=border.y+64;
    assert.equal(pointer('down',x,y).outcome,'admitted');
    assert.equal(pointer('move',x+2,y,-1).outcome,'unchanged');
    assert.equal(pointer('move',x+3,y,-1).outcome,'activated');
    f=frame();assert.equal(f.drag_drop.session.phase,'active');
    assert.deepEqual(f.drag_drop.session.payload.position,{x:0,y:0});
    assert.deepEqual(f.drag_drop.preview_value.position,{x:67,y:64});
    assert.deepEqual(f.shadows,[{id:90,kind:'shadow_md',element_opacity:1}]);
    const target=f.snapshot.items.find(item=>item.id===1030).bounds;
    const tx=target.x+target.width/2,ty=target.y+target.height/2;
    pointer('move',tx,ty,-1);assert.equal(JSON.parse(runtime.drag_drop_state()).drop_count,ix);
    assert.equal(pointer('up',tx,ty).outcome,'dropped');
    assert.equal(pointer('up',tx,ty).outcome,'unchanged');
    f=frame();assert.equal(f.drag_drop.drop_count,ix+1);assert.equal(f.drag_drop.drop_on.ix,ix);
    assert.deepEqual(f.drag_drop.drop_on.position,{x:0,y:0});
    assert.equal(f.snapshot.items.find(i=>i.id===30).opacity,0.5);
    assert.equal(f.snapshot.items.some(i=>i.id===90),false);
  }
});
test('real compiled runtime receives raw transport while host owns no drag decisions',{skip:!runtime},()=>{
  runtime.drag_drop_reset();frame();const handlers=new Map();let last;
  const canvas={style:{},getBoundingClientRect:()=>({left:0,top:0,width:800,height:600}),
    addEventListener:(name,handler)=>handlers.set(name,handler),removeEventListener:name=>handlers.delete(name)};
  const host=createDragDropHost({runtime,canvas,render:()=>{last=frame();},onError:error=>{throw error;}});
  const emit=(type,x,y,button=0)=>handlers.get(type)({pointerType:'mouse',clientX:x,clientY:y,button,isTrusted:false,preventDefault(){}});
  emit('pointerdown',256,232);emit('pointermove',258,232,-1);
  assert.equal(last.drag_drop.session.phase,'pending');
  emit('pointermove',259,232,-1);emit('pointermove',400,420,-1);
  assert.equal(last.drag_drop.session.phase,'active');assert.equal(last.drag_drop.drop_count,0);
  emit('pointerup',400,420);assert.equal(last.drag_drop.drop_count,1);
  assert(host.events.every(event=>event.trusted===false));host.stop();
  assert.equal(JSON.parse(runtime.drag_drop_state()).session.phase,'idle');
});
