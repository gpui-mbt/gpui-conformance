// Input transport only. No offset/range/clamp/row IDs or text placement here.
export function createUniformListHost({runtime,canvas,render,onError=error=>console.error(error)}) {
  const events=[];
  let stopped=false;
  const point=event=>{
    const b=canvas.getBoundingClientRect();
    if(![b.left,b.top,b.width,b.height].every(Number.isFinite)||b.width<=0||b.height<=0)
      throw new Error('Invalid canvas coordinates');
    return [(event.clientX-b.left)*300/b.width,(event.clientY-b.top)*300/b.height];
  };
  const dispatch=(event,kind)=>{
    if(stopped)return;
    try {
      const [x,y]=point(event);
      if(![x,y].every(Number.isFinite))throw new Error('Invalid input coordinates');
      let accepted;
      if(kind==='wheel') {
        event.preventDefault();
        if(event.deltaMode!==0||![event.deltaX,event.deltaY].every(Number.isFinite))
          throw new Error('Uniform-list profile requires finite pixel wheel deltas');
        accepted=runtime.uniform_list_wheel(x,y,event.deltaX,event.deltaY);
      }else accepted=runtime.uniform_list_pointer(kind,x,y,event.button);
      events.push({kind,x,y,trusted:event.isTrusted,accepted,
        ...(kind==='wheel'?{deltaX:event.deltaX,deltaY:event.deltaY,deltaMode:event.deltaMode}:{button:event.button})});
      if(accepted)render();
    }catch(error){events.push({kind,error:error.message});onError(error);}
  };
  const wheel=event=>dispatch(event,'wheel'),down=event=>dispatch(event,'down'),up=event=>dispatch(event,'up');
  canvas.addEventListener('wheel',wheel,{passive:false});
  canvas.addEventListener('pointerdown',down);canvas.addEventListener('pointerup',up);
  return {events,stop(){stopped=true;canvas.removeEventListener('wheel',wheel);
    canvas.removeEventListener('pointerdown',down);canvas.removeEventListener('pointerup',up);}};
}
