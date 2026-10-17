// Browser input, viewport and text-measurement transport only. No button,
// anchor, popup, snapping, hover selection or deferred-order geometry here.
export function readAnchorFrame(runtime, context, windowObject, metadata) {
  const width = windowObject.innerWidth, height = windowObject.innerHeight;
  const scale = windowObject.devicePixelRatio;
  const pixelsW = Math.round(width * scale), pixelsH = Math.round(height * scale);
  if (![width,height,scale].every(Number.isFinite) || width < 4 || width > 4096 ||
      height < 4 || height > 16384 || scale < 0.25 || scale > 4 ||
      pixelsW < 1 || pixelsW > 16384 || pixelsH < 1 || pixelsH > 16384 || pixelsW * pixelsH > 33554432) {
    runtime.anchor_reset();
    throw new Error('invalid_live_viewport');
  }
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
    // The live logical viewport canvas remains 1:1 with CSS pixels at any DPR.
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
  let stopped=false;
  canvas.addEventListener('pointermove',move);
  canvas.addEventListener('pointerleave',leave);
  return {events,stop() {
    if (stopped) return;
    stopped=true;
    runtime.anchor_reset();
    canvas.removeEventListener('pointermove',move);
    canvas.removeEventListener('pointerleave',leave);
  }};
}
