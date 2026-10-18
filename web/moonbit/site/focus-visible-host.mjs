// Transport only: the compiled MoonBit session owns focus, tab order, modality,
// hover, click arming and messages. DOM focus merely delivers keyboard events.
const modifierOnly=new Set(['control','alt','shift','meta','capslock','compose','process']);

export function createFocusVisibleHost({runtime,canvas,render,width=800,height=600,
  onError=error=>console.error(error)}) {
  if(![width,height].every(value=>Number.isFinite(value)&&value>0))
    throw new Error('Invalid focus-visible viewport');
  // Match the pinned desktop gpui_web IME conduit. It stays editable even
  // though this example has no text-input handler, so native Chromium Enter
  // can produce beforeinput. This is transport, never DOM button focus.
  const document=canvas.ownerDocument;
  if(!document?.body||typeof document.createElement!=='function')
    throw new Error('Focus-visible transport requires a document');
  const input=document.createElement('textarea');
  Object.assign(input.style,{position:'fixed',top:'0',left:'0',width:'1px',
    height:'1px',opacity:'0',fontSize:'16px'});
  input.spellcheck=false;
  for(const name of ['autocomplete','autocorrect','autocapitalize'])input.setAttribute(name,'off');
  input.readOnly=false;
  document.body.appendChild(input);
  const events=[];
  let stopped=false;
  const record=entry=>{events.push(entry);if(events.length>200)events.shift();};
  const modifiers=event=>[!!event.shiftKey,!!event.ctrlKey,!!event.altKey,!!event.metaKey];
  const point=event=>{
    const b=canvas.getBoundingClientRect();
    if(![b.left,b.top,b.width,b.height].every(Number.isFinite)||b.width<=0||b.height<=0)
      throw new Error('Invalid canvas coordinates');
    const x=(event.clientX-b.left)*width/b.width,y=(event.clientY-b.top)*height/b.height;
    if(![x,y].every(Number.isFinite))throw new Error('Invalid pointer coordinates');
    return [x,y];
  };
  const dispatch=(type,event,operation)=>{
    if(stopped)return;
    try {
      const accepted=operation()!==false;
      record({type,trusted:event.isTrusted,accepted});
      if(accepted)render();
    }catch(error){record({type,trusted:event.isTrusted,accepted:false,error:error.message});onError(error);}
  };
  const pointer=kind=>event=>dispatch(kind,event,()=>{
    if(event.pointerType!=='mouse')throw new Error('Focus-visible profile requires mouse pointer input');
    const [x,y]=point(event);
    event.preventDefault();
    const accepted=runtime.focus_visible_pointer(kind,x,y,event.button,...modifiers(event));
    if(kind==='down')input.focus({preventScroll:true});
    return accepted;
  });
  const move=pointer('move'),down=pointer('down'),up=pointer('up');
  const leave=event=>dispatch('leave',event,()=>runtime.focus_visible_leave());
  const contextmenu=event=>{if(!stopped)event.preventDefault();};
  const key=down=>event=>{
    if(stopped)return;
    if(typeof event.key!=='string'||!event.key) {
      dispatch(down?'keydown':'keyup',event,()=>{throw new Error('Invalid keyboard label');});return;
    }
    // Mirror upstream's modifier-only transport filter. These DOM events do
    // not become GPUI KeyDown/KeyUp and must not change core modality/arming.
    if(modifierOnly.has(event.key.toLowerCase())) {
      record({type:down?'keydown':'keyup',trusted:event.isTrusted,accepted:false,filtered:'modifier_only'});
      return;
    }
    dispatch(down?'keydown':'keyup',event,()=>{
      // This bounded Linux/Chromium profile mirrors the upstream byte-length
      // key_char rule and AltGr exception. Enter has no key_char and must keep
      // its browser default: beforeinput below supplies the actual edit intent.
      const altGr=event.ctrlKey&&event.altKey;
      const textModifiers=(!event.ctrlKey&&!event.altKey&&!event.metaKey)||altGr;
      const keyChar=event.key===' '||new TextEncoder().encode(event.key).length===1;
      if(down&&((event.key==='Tab'&&!event.ctrlKey&&!event.altKey&&!event.metaKey)||
          (textModifiers&&keyChar)))event.preventDefault();
      return runtime.focus_visible_key(event.key,down,...modifiers(event),!!event.repeat);
    });
  };
  const keydown=key(true),keyup=key(false);
  const beforeinput=event=>{
    if(stopped||event.isComposing||
        !['insertLineBreak','insertParagraph'].includes(event.inputType))return;
    // events.rs::register_before_input dispatches a full synthetic *core*
    // keystroke with default modifiers. Do not synthesize DOM events, infer an
    // activation here, or duplicate this on physical keydown/keyup.
    event.preventDefault();
    dispatch('beforeinput',event,()=>{
      const down=runtime.focus_visible_key('Enter',true,false,false,false,false,false);
      const up=runtime.focus_visible_key('Enter',false,false,false,false,false,false);
      return down!==false&&up!==false;
    });
  };
  const wheel=event=>dispatch('wheel',event,()=>{
    event.preventDefault();
    if(event.deltaMode!==0||![event.deltaX,event.deltaY].every(Number.isFinite))
      throw new Error('Focus-visible profile requires finite pixel wheel deltas');
    return runtime.focus_visible_wheel(...point(event),event.deltaX,event.deltaY);
  });
  const listeners=[[canvas,'pointermove',move],[canvas,'pointerdown',down],[canvas,'pointerup',up],
    [canvas,'pointerleave',leave],[canvas,'contextmenu',contextmenu],
    [input,'keydown',keydown],[input,'keyup',keyup],
    [input,'beforeinput',beforeinput],[canvas,'wheel',wheel]];
  canvas.tabIndex=-1;
  for(const [target,name,handler] of listeners)target.addEventListener(name,handler,name==='wheel'?{passive:false}:undefined);
  input.focus({preventScroll:true});
  return {events,stop(){
    stopped=true;
    for(const [target,name,handler] of listeners)target.removeEventListener(name,handler);
    input.remove();
  }};
}
