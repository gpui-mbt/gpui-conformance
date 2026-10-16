import test from 'node:test';
import assert from 'node:assert/strict';
import {createInputHost} from '../moonbit/site/input-host.mjs';

function fixture(t) {
  const previous={document:globalThis.document,window:globalThis.window};
  const calls=[];
  let selecting=false;
  class Element extends EventTarget {
    style={}; dataset={}; captures=new Set();
    setAttribute() {}
    focus() { document.activeElement=this; }
    getBoundingClientRect() { return {left:10,top:20,width:600,height:600}; }
    setPointerCapture(id) { this.captures.add(id); }
    hasPointerCapture(id) { return this.captures.has(id); }
    releasePointerCapture(id) { this.captures.delete(id); }
  }
  globalThis.document={createElement:()=>new Element()};
  globalThis.window=new EventTarget();
  t.after(()=>{globalThis.document=previous.document;globalThis.window=previous.window;});
  const canvas=new Element();
  canvas.parentElement={append() {}};
  const runtime={
    input_text:()=>'', input_anchor:()=>0, input_head:()=>0,
    input_marked_start:()=>-1,input_marked_end:()=>-1,input_composing:()=>false,
    input_can_undo:()=>false,input_can_redo:()=>false,input_scroll_offset:()=>0,
    input_selecting:()=>selecting,
    input_reset:()=>{selecting=false;},
    input_pointer:(x,y,shift)=>{calls.push(['down',x,y,shift]);selecting=y>=34&&y<=72;return selecting;},
    input_pointer_move:(x,y)=>{calls.push(['move',x,y]);return selecting;},
    input_pointer_end:()=>{calls.push(['end']);selecting=false;},
  };
  const host=createInputHost({runtime,canvas,render(){},onError:error=>{throw error;}});
  const send=(type,extra={})=>{
    const event=new Event(type,{cancelable:true});
    Object.assign(event,{button:0,buttons:1,isPrimary:true,pointerId:7,clientX:58,clientY:120,shiftKey:false,...extra});
    canvas.dispatchEvent(event);
    return event;
  };
  return {canvas,host,calls,send};
}

test('pointer transport cancels mouse focus and maps scaled coordinates',t=>{
  const {canvas,host,calls,send}=fixture(t);
  const down=send('pointerdown');
  assert.equal(down.defaultPrevented,true);
  assert.equal(document.activeElement,host.editor);
  assert.equal(canvas.hasPointerCapture(7),true);
  assert.deepEqual(calls,[['down',24,50,false]]);
  send('pointermove',{clientX:106});
  send('pointerup',{clientX:130,buttons:0});
  assert.deepEqual(calls,[['down',24,50,false],['move',48,50],['move',60,50],['end']]);
  assert.equal(host.readState().selecting,false);
  assert.equal(canvas.hasPointerCapture(7),false);
  send('pointermove',{clientX:500});
  assert.equal(calls.length,4);
});

test('secondary and unrelated pointers cannot steal or finish a gesture',t=>{
  const {host,calls,send}=fixture(t);
  send('pointerdown',{button:2});
  send('pointerdown',{isPrimary:false});
  assert.equal(calls.length,0);
  send('pointerdown');
  send('pointerdown',{pointerId:8});
  send('pointermove',{pointerId:8});
  send('pointerup',{pointerId:8});
  send('pointercancel',{pointerId:8});
  assert.equal(calls.length,1);
  assert.equal(host.readState().selecting,true);
  send('pointercancel');
  assert.deepEqual(calls.at(-1),['end']);
});

test('capture failure, missing buttons, blur, reset and pagehide clear ownership',t=>{
  const {canvas,host,send}=fixture(t);
  const capture=canvas.setPointerCapture;
  canvas.setPointerCapture=()=>{throw new Error('inactive pointer');};
  send('pointerdown');
  assert.equal(host.readState().selecting,false);
  canvas.setPointerCapture=capture;
  for (const stop of [()=>send('pointermove',{buttons:0}),
    ()=>host.editor.dispatchEvent(new Event('blur')),()=>host.reset(),
    ()=>window.dispatchEvent(new Event('blur')),()=>window.dispatchEvent(new Event('pagehide')),
    ()=>send('lostpointercapture'),
    ()=>host.editor.dispatchEvent(new Event('compositionstart'))]) {
    send('pointerdown');
    assert.equal(host.readState().selecting,true);
    stop();
    assert.equal(host.readState().selecting,false);
    assert.equal(canvas.hasPointerCapture(7),false);
  }
});

test('invalid coordinates, empty canvas bounds and clicks outside the field do not capture',t=>{
  const {canvas,calls,send}=fixture(t);
  assert.equal(send('pointerdown',{clientX:NaN}).defaultPrevented,false);
  assert.equal(calls.length,0);
  assert.equal(send('pointerdown',{clientY:220}).defaultPrevented,false);
  assert.equal(canvas.hasPointerCapture(7),false);
  canvas.getBoundingClientRect=()=>({left:0,top:0,width:0,height:0});
  send('pointerdown');
  assert.equal(calls.length,1);
});

test('Reset cancels native focus without starting a selection gesture',t=>{
  const {canvas,host,calls,send}=fixture(t);
  const event=send('pointerdown',{clientX:550,clientY:50});
  assert.equal(event.defaultPrevented,true);
  assert.equal(document.activeElement,host.editor);
  assert.equal(canvas.hasPointerCapture(7),false);
  assert.equal(host.readState().selecting,false);
  assert.deepEqual(calls,[]);
});
