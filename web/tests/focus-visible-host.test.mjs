import test from 'node:test';
import assert from 'node:assert/strict';
import {createFocusVisibleHost} from '../moonbit/site/focus-visible-host.mjs';

function setup(options={}) {
  const calls=[],listeners=new Map(),errors=[],renders=[],focus=[],children=[];
  const add=(name,handler)=>listeners.set(name,handler);
  const remove=(name,handler)=>{if(listeners.get(name)===handler)listeners.delete(name);};
  const input={style:{},attributes:{},readOnly:true,spellcheck:true,
    setAttribute(name,value){this.attributes[name]=value;},
    addEventListener:add,removeEventListener:remove,
    focus:args=>focus.push(args),remove(){const index=children.indexOf(this);if(index>=0)children.splice(index,1);},
  };
  const document={body:{appendChild:node=>children.push(node)},createElement:tag=>{assert.equal(tag,'textarea');return input;}};
  const runtime=Object.fromEntries(['pointer','leave','key','wheel'].map(name=>[
    `focus_visible_${name}`,(...args)=>{calls.push([name,...args]);return options.accepted!==false;},
  ]));
  const canvas={tabIndex:0,ownerDocument:document,
    getBoundingClientRect:()=>options.bounds||{left:10,top:20,width:400,height:300},
    addEventListener:add,removeEventListener:remove,
    focus:()=>{throw new Error('Canvas must not own keyboard transport');},
  };
  const host=createFocusVisibleHost({runtime,canvas,render:()=>renders.push(true),onError:error=>errors.push(error.message)});
  const emit=(type,properties={})=>{
    const event={isTrusted:true,pointerType:'mouse',clientX:110,clientY:120,button:0,
      key:'a',shiftKey:false,ctrlKey:false,altKey:false,metaKey:false,repeat:false,
      deltaMode:0,deltaX:0,deltaY:0,defaultPrevented:false,
      preventDefault(){this.defaultPrevented=true;},...properties};
    listeners.get(type)?.(event);return event;
  };
  return {host,canvas,input,children,calls,listeners,errors,renders,focus,emit};
}

test('host translates pointer coordinates and forwards all decisions to MoonBit',()=>{
  const s=setup();
  assert.equal(s.canvas.tabIndex,-1);
  assert.deepEqual(s.children,[s.input]);
  assert.equal(s.input.readOnly,false);assert.equal(s.input.spellcheck,false);
  assert.deepEqual(s.input.attributes,{autocomplete:'off',autocorrect:'off',autocapitalize:'off'});
  assert.deepEqual(s.input.style,{position:'fixed',top:'0',left:'0',width:'1px',height:'1px',opacity:'0',fontSize:'16px'});
  assert.deepEqual(s.focus,[{preventScroll:true}]);
  s.emit('pointermove',{button:-1});
  const down=s.emit('pointerdown',{button:2,shiftKey:true,metaKey:true});
  s.emit('pointerup',{clientX:-10,clientY:15,button:1});
  s.emit('pointerleave');
  assert.deepEqual(s.calls,[
    ['pointer','move',200,200,-1,false,false,false,false],
    ['pointer','down',200,200,2,true,false,false,true],
    ['pointer','up',-40,-10,1,false,false,false,false],['leave'],
  ]);
  assert.equal(down.defaultPrevented,true);assert.equal(s.focus.length,2);
  assert.equal(s.renders.length,4);assert.deepEqual(s.errors,[]);
  assert(!s.listeners.has('click'),'No host click or tab-state emulation');
  assert(!s.listeners.has('blur'),'No invented focus clearing on DOM blur');
});

test('modifier-only DOM events never become core key input or trigger repaint',()=>{
  const s=setup();
  for(const key of ['Control','Alt','Shift','Meta','CapsLock','Compose','Process']) {
    s.emit('keydown',{key});s.emit('keyup',{key});
  }
  assert.deepEqual(s.calls,[]);assert.deepEqual(s.renders,[]);
  assert(s.host.events.every(event=>event.filtered==='modifier_only'));
  // These are not in upstream's modifier-only filter.
  s.emit('keydown',{key:'AltGraph'});s.emit('keyup',{key:'Fn'});
  assert.deepEqual(s.calls.map(call=>call[1]),['AltGraph','Fn']);
});

test('raw keys, direction, modifiers and repeat reach core without JS traversal',()=>{
  const s=setup();
  const tab=s.emit('keydown',{key:'Tab',shiftKey:true,repeat:true});
  const up=s.emit('keyup',{key:'Tab',shiftKey:true});
  s.emit('keydown',{key:'Enter',ctrlKey:true,altKey:true,metaKey:true});
  assert.deepEqual(s.calls,[
    ['key','Tab',true,true,false,false,false,true],
    ['key','Tab',false,true,false,false,false,false],
    ['key','Enter',true,false,true,true,true,false],
  ]);
  assert.equal(tab.defaultPrevented,true);assert.equal(up.defaultPrevented,false);
});

test('transport keeps Enter default for actual beforeinput while matching byte-based text prevention',()=>{
  const s=setup();
  for(const key of ['Tab',' ','a'])assert.equal(s.emit('keydown',{key}).defaultPrevented,true);
  for(const key of ['Enter','😀','é'])assert.equal(s.emit('keydown',{key}).defaultPrevented,false);
  assert.equal(s.emit('keydown',{key:'a',ctrlKey:true,altKey:true}).defaultPrevented,true);
  assert.equal(s.emit('keydown',{key:'q',metaKey:true}).defaultPrevented,false);
  assert.equal(s.emit('keydown',{key:'a',ctrlKey:true}).defaultPrevented,false);
});

test('finite pixel wheels are forwarded and never converted into offsets in JS',()=>{
  const s=setup();const event=s.emit('wheel',{deltaX:-2.5,deltaY:10});
  assert.equal(event.defaultPrevented,true);
  assert.deepEqual(s.calls,[['wheel',200,200,-2.5,10]]);
  for(const properties of [{deltaMode:1},{deltaMode:2},{deltaX:Infinity},{deltaY:NaN}])s.emit('wheel',properties);
  assert.equal(s.calls.length,1);assert.equal(s.errors.length,4);assert.equal(s.renders.length,1);
});

test('invalid coordinates, unsupported pointers and malformed keys fail before core dispatch',()=>{
  const s=setup();
  s.emit('pointermove',{clientX:NaN});s.emit('pointerdown',{clientY:Infinity});
  s.emit('pointermove',{pointerType:'touch'});s.emit('pointerdown',{pointerType:'pen'});
  s.emit('keydown',{key:''});s.emit('keyup',{key:null});
  assert.equal(s.errors.length,6);assert.deepEqual(s.calls,[]);assert.deepEqual(s.renders,[]);
  assert.equal(s.focus.length,1,'Invalid input must not focus the transport again');
  for(const bounds of [{left:0,top:0,width:0,height:10},{left:NaN,top:0,width:10,height:10}]) {
    const bad=setup({bounds});bad.emit('pointermove');assert.equal(bad.calls.length,0);assert.equal(bad.errors.length,1);
  }
});

test('core rejection prevents repaint and diagnostics never supply replacement state',()=>{
  const s=setup({accepted:false});s.emit('keydown',{key:'Tab'});s.emit('pointerdown');
  assert.equal(s.calls.length,2);assert.equal(s.renders.length,0);
  assert(s.host.events.every(event=>event.accepted===false));
  assert.deepEqual(Object.keys(s.host).sort(),['events','stop']);
});

test('transport log is bounded and stop removes every listener without touching core focus',()=>{
  const s=setup();for(let n=0;n<220;n++)s.emit('pointermove');
  assert.equal(s.host.events.length,200);assert.equal(s.calls.length,220);
  s.host.stop();s.host.stop();assert.equal(s.listeners.size,0);assert.deepEqual(s.children,[]);
  s.emit('keydown',{key:'Tab'});s.emit('pointerdown');assert.equal(s.calls.length,220);
});

test('invalid viewport cannot initialize transport',()=>{
  for(const width of [0,-1,Infinity,NaN])assert.throws(()=>createFocusVisibleHost({width,height:600}),/viewport/);
});


test('trusted beforeinput forwards one default-modifier core down/up pair independently of physical key identity',()=>{
  const s=setup();
  const down=s.emit('keydown',{key:'Enter',shiftKey:true});
  assert.equal(down.defaultPrevented,false);
  const intent=s.emit('beforeinput',{inputType:'insertLineBreak',isComposing:false});
  const up=s.emit('keyup',{key:'Enter',shiftKey:true});
  assert.equal(intent.defaultPrevented,true);assert.equal(up.defaultPrevented,false);
  assert.deepEqual(s.calls,[
    ['key','Enter',true,true,false,false,false,false],
    ['key','Enter',true,false,false,false,false,false],
    ['key','Enter',false,false,false,false,false,false],
    ['key','Enter',false,true,false,false,false,false],
  ]);
  assert.equal(s.host.events.filter(event=>event.type==='beforeinput').length,1);
  assert.equal(s.renders.length,3);
});

test('beforeinput paragraph works without hardware keys, composition and unrelated edit intents do not synthesize activation',()=>{
  const s=setup();
  for(const inputType of ['insertText','deleteContentBackward','insertFromPaste'])
    assert.equal(s.emit('beforeinput',{inputType,isComposing:false}).defaultPrevented,false);
  for(const inputType of ['insertParagraph','insertLineBreak'])
    assert.equal(s.emit('beforeinput',{inputType,isComposing:true}).defaultPrevented,false);
  assert.deepEqual(s.calls,[]);
  assert.equal(s.emit('beforeinput',{inputType:'insertParagraph',isComposing:false}).defaultPrevented,true);
  assert.deepEqual(s.calls,[
    ['key','Enter',true,false,false,false,false,false],
    ['key','Enter',false,false,false,false,false,false],
  ]);
  s.host.stop();s.emit('beforeinput',{inputType:'insertParagraph'});assert.equal(s.calls.length,2);
});


test('secondary focus keeps browser context menus from consuming later key input',()=>{
  const s=setup();
  const event=s.emit('contextmenu',{button:2});
  assert.equal(event.defaultPrevented,true);
  assert.deepEqual(s.calls,[]);assert.deepEqual(s.renders,[]);
});
