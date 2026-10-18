import {measurePopoverInputs} from './popover-text.mjs';
import {validateFrame} from './render.mjs';

// Resource bounds protect Canvas allocation, independently of model bounds.
export function readPopoverFrame(runtime,context,viewport,metadata) {
  const width=viewport.innerWidth,height=viewport.innerHeight,scale=viewport.devicePixelRatio;
  const backingWidth=Math.round(width*scale),backingHeight=Math.round(height*scale);
  if(![width,height,scale].every(Number.isFinite)||width<1||height<1||width>8192||height>8192||
     scale<0.25||scale>4||backingWidth<1||backingHeight<1||backingWidth>16384||backingHeight>16384||
     backingWidth*backingHeight>33554432)throw new Error('Unsupported popover viewport');
  const prefixes=measurePopoverInputs(context,metadata);
  const frame=JSON.parse(runtime.popover_frame(width,height,scale,prefixes));
  validateFrame(frame);
  if(!frame.popover||frame.popover.comparison_profile_match!==false)
    throw new Error('Invalid popover qualification status');
  return {frame,width,height,scale,prefixes,backingWidth,backingHeight};
}

// Trusted primary-mouse transport only: no hits, open flags, or layout decisions.
export function createPopoverHost({runtime,canvas,render,windowTarget=window,onError=error=>console.error(error)}) {
  const events=[];let stopped=false,activePointer=null;
  const record=value=>{events.push(value);if(events.length>256)events.shift();};
  const cancel=()=>{activePointer=null;runtime.popover_cancel();};
  const dispatch=(event,kind)=>{
    if(stopped||event.isTrusted!==true||event.pointerType!=='mouse'||event.isPrimary===false)return;
    if(kind==='up'&&activePointer!==event.pointerId)return;
    if(kind==='down'&&activePointer!==null&&activePointer!==event.pointerId){cancel();return;}
    try {
      // Re-measure and rebuild before every event, including after a resize/DPR
      // change whose asynchronous browser notification has not run yet.
      if(render()===false){cancel();return;}
      const b=canvas.getBoundingClientRect();
      const width=windowTarget.innerWidth,height=windowTarget.innerHeight;
      if(![b.left,b.top,b.width,b.height,width,height,event.clientX,event.clientY].every(Number.isFinite)||
         b.width<=0||b.height<=0)throw new Error('Invalid popover pointer coordinates');
      const x=(event.clientX-b.left)*width/b.width,y=(event.clientY-b.top)*height/b.height;
      if(!Number.isFinite(x)||!Number.isFinite(y))throw new Error('Invalid popover pointer coordinates');
      if(kind==='down')activePointer=event.pointerId;
      if(kind==='up')activePointer=null;
      const accepted=runtime.popover_pointer(kind,x,y,event.button);
      record({kind,x,y,button:event.button,trusted:true,accepted});
      if(accepted)render();
    }catch(error){cancel();record({kind,error:error.message});onError(error);}
  };
  const down=e=>dispatch(e,'down'),up=e=>dispatch(e,'up');
  const pointerCancel=e=>{if(e.isTrusted===true&&(activePointer===null||e.pointerId===activePointer))cancel();};
  canvas.addEventListener('pointerdown',down);
  windowTarget.addEventListener('pointerup',up);
  windowTarget.addEventListener('pointercancel',pointerCancel);
  windowTarget.addEventListener('blur',cancel);
  return {events,stop(){if(stopped)return;stopped=true;cancel();
    canvas.removeEventListener('pointerdown',down);windowTarget.removeEventListener('pointerup',up);
    windowTarget.removeEventListener('pointercancel',pointerCancel);windowTarget.removeEventListener('blur',cancel);
  }};
}
