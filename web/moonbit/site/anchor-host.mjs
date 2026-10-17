// Browser input, viewport and text-measurement transport only. No button,
// anchor, popup, snapping, hover selection or deferred-order geometry here.
export function readAnchorFrame(runtime, context, windowObject, metadata) {
  const width = windowObject.innerWidth, height = windowObject.innerHeight;
  const scale = windowObject.devicePixelRatio || 1;
  const widths = metadata.runs.map(run => {
    context.font = `normal 400 ${run.font_size}px "IBM Plex Sans"`;
    return context.measureText(run.text).width;
  });
  const frame = JSON.parse(runtime.anchor_frame(width,height,widths,scale));
  if (!frame.ok) throw new Error(frame.error || 'Invalid anchor frame');
  return {frame,width,height,scale,widths};
}

export function createAnchorHost({runtime,canvas,render}) {
  const events = [];
  function move(event) {
    if (!event.isTrusted || event.pointerType !== 'mouse') return;
    const rect = canvas.getBoundingClientRect();
    // Logical viewport canvas is 1:1 with CSS pixels in the bounded DPR1 profile.
    const x = event.clientX - rect.left, y = event.clientY - rect.top;
    runtime.anchor_pointer(x,y,true);
    events.push({type:'pointermove',x,y,trusted:event.isTrusted});
    render();
  }
  function leave(event) {
    if (!event.isTrusted || event.pointerType !== 'mouse') return;
    runtime.anchor_pointer(0,0,false);
    events.push({type:'pointerleave',trusted:event.isTrusted});
    render();
  }
  canvas.addEventListener('pointermove',move);
  canvas.addEventListener('pointerleave',leave);
  return {events,stop() {
    canvas.removeEventListener('pointermove',move);
    canvas.removeEventListener('pointerleave',leave);
  }};
}
