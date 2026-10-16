// Browser transport only. The compiled MoonBit ElementTree owns scroll offsets,
// limits, clipping, hit testing and hover; this adapter owns none of that state.
export function createScrollableHost({runtime, canvas, render, width = 500, height = 500,
  onError = error => console.error(error)}) {
  if (![width,height].every(value => Number.isFinite(value) && value > 0))
    throw new Error('Invalid scrollable viewport');
  const events = [];
  let stopped = false;
  const record = entry => { events.push(entry); if (events.length > 200) events.shift(); };
  const point = event => {
    const bounds = canvas.getBoundingClientRect();
    if (![bounds.left,bounds.top,bounds.width,bounds.height].every(Number.isFinite) ||
        bounds.width <= 0 || bounds.height <= 0) throw new Error('Invalid canvas coordinates');
    const x = (event.clientX - bounds.left) * width / bounds.width;
    const y = (event.clientY - bounds.top) * height / bounds.height;
    if (![x,y].every(Number.isFinite)) throw new Error('Invalid pointer coordinates');
    return {x,y};
  };
  const dispatch = (type, operation, detail = {}) => {
    if (stopped) return;
    try {
      const accepted = operation() !== false;
      record({type,...detail,accepted});
      if (accepted) render();
    } catch (error) {
      record({type,...detail,accepted:false,error:error.message});
      onError(error);
    }
  };
  const move = event => dispatch('pointer', () => {
    const {x,y} = point(event);
    return runtime.scrollable_pointer(x,y);
  }, {trusted:event.isTrusted});
  const leave = event => dispatch('leave', () => runtime.scrollable_leave(), {trusted:event.isTrusted});
  const wheel = event => {
    if (stopped) return;
    event.preventDefault();
    dispatch('wheel', () => {
      // The measured profile is trusted pixel wheel input. Do not silently
      // apply typography's line/page conversion to a different GPUI example.
      if (event.deltaMode !== 0 || ![event.deltaX,event.deltaY].every(Number.isFinite))
        throw new Error('Scrollable profile requires finite pixel wheel deltas');
      const {x,y} = point(event);
      return runtime.scrollable_wheel(x,y,event.deltaX,event.deltaY);
    }, {trusted:event.isTrusted,deltaMode:event.deltaMode,deltaX:event.deltaX,deltaY:event.deltaY});
  };
  canvas.addEventListener('pointermove', move);
  canvas.addEventListener('pointerleave', leave);
  canvas.addEventListener('wheel', wheel, {passive:false});
  return {events, stop() {
    stopped = true;
    canvas.removeEventListener('pointermove', move);
    canvas.removeEventListener('pointerleave', leave);
    canvas.removeEventListener('wheel', wheel);
  }};
}
