import test from 'node:test';
import assert from 'node:assert/strict';
import {createInputHost} from '../moonbit/site/input-host.mjs';

// The adapter receives DOM events; this stub models only calls into the
// authoritative TextField, not the browser textarea as another document.
function fixture(t) {
  const previous={document:globalThis.document,window:globalThis.window};
  class Element extends EventTarget {
    style={}; dataset={}; value='';
    setAttribute() {}
    focus() { document.activeElement=this; }
  }
  globalThis.document={createElement:()=>new Element()};
  globalThis.window=new EventTarget();
  t.after(()=>{globalThis.document=previous.document;globalThis.window=previous.window;});
  const canvas=new Element();
  canvas.parentElement={append() {}};
  const calls=[];
  let text='',composing=false;
  const runtime={
    input_text:()=>text,input_anchor:()=>text.length,input_head:()=>text.length,
    input_marked_start:()=>-1,input_marked_end:()=>-1,
    input_composing:()=>composing,input_selecting:()=>false,
    input_can_undo:()=>false,input_can_redo:()=>false,input_scroll_offset:()=>0,
    input_pointer_end:()=>{},
    input_reset:()=>{text='';composing=false;},
    input_preedit:(value,start,end)=>{calls.push(['preedit',value,start,end]);composing=true;return true;},
    input_finish:(value,committed)=>{
      calls.push(['finish',value,committed]);
      composing=false;
      if (committed) text+=value;
      return true;
    },
    input_insert:value=>{calls.push(['insert',value]);text+=value;return true;},
  };
  const host=createInputHost({runtime,canvas,render(){},onError:error=>{throw error;}});
  const dispatch=(type,options={})=>{
    const {cancelable=true,...properties}=options;
    const event=new Event(type,{cancelable,bubbles:true});
    Object.assign(event,properties);
    host.editor.dispatchEvent(event);
    return event;
  };
  const compose=(preedit='にほん',final='日本')=>{
    dispatch('compositionstart',{data:''});
    dispatch('compositionupdate',{data:preedit});
    dispatch('compositionend',{data:final});
  };
  const before=(data,{cancelable=true,inputType='insertText'}={})=>
    dispatch('beforeinput',{data,inputType,cancelable,isComposing:false});
  const nativeInput=(value,{inputType='insertText'}={})=>{
    host.editor.value=value;
    dispatch('input',{data:value,inputType,isComposing:false});
  };
  return {host,calls,dispatch,compose,before,nativeInput,get text(){return text;}};
}

test('normal composition commits once without relying on the textarea',t=>{
  const f=fixture(t);
  f.compose();
  assert.equal(f.text,'日本');
  assert.equal(f.host.editor.value,'');
  assert.deepEqual(f.calls.slice(-1),[['finish','日本',true]]);
  assert.equal(f.host.readState().composing,false);
});

test('cancelable final beforeinput is prevented and the next identical edit is accepted',t=>{
  const f=fixture(t);
  f.compose();
  const replay=f.before('日本',{inputType:'insertFromComposition'});
  assert.equal(replay.defaultPrevented,true);
  assert.equal(f.text,'日本');
  // No input event follows a successfully canceled beforeinput.
  const next=f.before('日本');
  assert.equal(next.defaultPrevented,true);
  assert.equal(f.text,'日本日本');
  assert.deepEqual(f.calls.filter(call=>call[0]==='insert'),[['insert','日本']]);
});

test('non-cancelable IME beforeinput followed by input cannot duplicate the committed text',t=>{
  const f=fixture(t);
  f.compose();
  const replay=f.before('日本',{cancelable:false,inputType:'insertText'});
  assert.equal(replay.cancelable,false);
  assert.equal(replay.defaultPrevented,false);
  // A non-cancelable event must be followed by the browser's native DOM edit.
  f.nativeInput('日本');
  assert.equal(f.text,'日本');
  assert.equal(f.host.editor.value,'');
  assert.deepEqual(f.calls.filter(call=>call[0]==='insert'),[]);
  f.before('!');
  assert.equal(f.text,'日本!');
});

test('input fallback without beforeinput also consumes the duplicate exactly once',t=>{
  const f=fixture(t);
  f.compose();
  f.nativeInput('日本',{inputType:'insertFromComposition'});
  assert.equal(f.text,'日本');
  f.before('!');
  assert.equal(f.text,'日本!');
});

test('Escape and ambiguous empty finalization cancel; ordinary typing still works',t=>{
  const f=fixture(t);
  f.dispatch('compositionstart',{data:''});
  f.dispatch('compositionupdate',{data:'かな'});
  f.dispatch('keydown',{key:'Escape',keyCode:27,isComposing:true});
  f.dispatch('compositionend',{data:'かな'});
  assert.equal(f.text,'');
  assert.deepEqual(f.calls.slice(-1),[['finish','かな',false]]);
  f.dispatch('compositionstart',{data:''});
  f.dispatch('compositionupdate',{data:'未'});
  f.dispatch('compositionend',{data:''});
  assert.equal(f.text,'');
  f.before('Z');
  assert.equal(f.text,'Z');
});

test('the next ordinary character is not swallowed, with or without a keydown',t=>{
  const f=fixture(t);
  f.compose();
  f.before('!');
  assert.equal(f.text,'日本!');
  f.host.reset();
  f.compose();
  f.dispatch('keydown',{key:'!',keyCode:49,isComposing:false});
  f.before('!');
  assert.equal(f.text,'日本!');
});

test('a non-cancelable ordinary beforeinput is inserted by input fallback, not twice',t=>{
  const f=fixture(t);
  f.compose();
  const next=f.before('!',{cancelable:false});
  assert.equal(next.defaultPrevented,false);
  f.nativeInput('!');
  assert.equal(f.text,'日本!');
  assert.deepEqual(f.calls.filter(call=>call[0]==='insert'),[['insert','!']]);
});
