// Mouse transport only. Compiled MoonBit owns the typed payload, admission,
// threshold, hit routing, hover, cursor and one-shot target mutation.
export function createDragDropHost({runtime,canvas,render,width=800,height=600,
  onError=error=>console.error(error)}) {
  for(const name of ['pointer','leave','reset']) {
    if(typeof runtime?.[`drag_drop_${name}`]!=='function')
      throw new Error(`Missing drag-drop transport method ${name}`);
  }
  if(![width,height].every(value=>Number.isFinite(value)&&value>0))
    throw new Error('Invalid drag-drop viewport');
  const events=[];
  let stopped=false;
  const record=entry=>{events.push(entry);if(events.length>200)events.shift();};
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
      const result=JSON.parse(operation());
      if(!result||typeof result.ok!=='boolean'||!['default','move'].includes(result.cursor))
        throw new Error('Invalid compiled drag-drop response');
      canvas.style.cursor=result.cursor;
      record({type,trusted:event.isTrusted,accepted:result.ok,outcome:result.outcome??null,
        error:result.error??null});
      // Hover can change without a core drag transition, including idle move.
      // An explicit application cancellation on Err also needs a repaint.
      render();
      if(!result.ok)onError(new Error(`MoonBit drag-drop: ${result.error}`));
    }catch(error){record({type,trusted:event.isTrusted,accepted:false,error:error.message});onError(error);}
  };
  const pointer=kind=>event=>dispatch(kind,event,()=>{
    if(event.pointerType!=='mouse')throw new Error('Drag-drop profile requires mouse pointer input');
    const [x,y]=point(event);
    event.preventDefault();
    return runtime.drag_drop_pointer(kind,x,y,event.button,
      !!event.shiftKey,!!event.ctrlKey,!!event.altKey,!!event.metaKey);
  });
  const leave=event=>dispatch('leave',event,()=>runtime.drag_drop_leave());
  const contextmenu=event=>{if(!stopped)event.preventDefault();};
  const listeners=[['pointermove',pointer('move')],['pointerdown',pointer('down')],
    ['pointerup',pointer('up')],['pointerleave',leave],['contextmenu',contextmenu]];
  for(const [name,handler] of listeners)canvas.addEventListener(name,handler);
  return {events,stop(){
    if(stopped)return;
    stopped=true;
    for(const [name,handler] of listeners)canvas.removeEventListener(name,handler);
    runtime.drag_drop_reset();
    canvas.style.cursor='default';
  }};
}
