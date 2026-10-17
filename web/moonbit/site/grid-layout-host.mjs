// Transport and shaping only. Responsive selection, tracks, spans, block bounds,
// text wrapping and declaration order are owned by the compiled MoonBit port.
export function readGridViewport(windowObject) {
  const width = windowObject.innerWidth, height = windowObject.innerHeight;
  if (![width,height].every(Number.isFinite) || width <= 0 || height <= 0)
    throw new Error('Invalid grid viewport dimensions');
  return {width,height};
}

export function measureGridInputs(runtime, context, width, height, scale) {
  const content = JSON.parse(runtime.grid_layout_content(width,height,scale));
  if (!content.ok || !Array.isArray(content.runs) || content.runs.length !== 5)
    throw new Error(content.error || 'Invalid grid text content');
  const prefixes = content.runs.map(run => {
    if (typeof run.text !== 'string' || run.font_size !== 16) throw new Error('Invalid grid text run');
    context.font = 'normal 400 16px "IBM Plex Sans"';
    const widths = [0]; let prefix = '';
    for (const character of run.text) { prefix += character; widths.push(context.measureText(prefix).width); }
    return widths;
  });
  return {content,prefixes};
}

export function readGridFrame(runtime, context, windowObject, scale) {
  const {width,height} = readGridViewport(windowObject);
  // Validate before measurement/allocation; mirror the candidate resource guard.
  const pixelsW = Math.round(width * scale), pixelsH = Math.round(height * scale);
  if (!Number.isFinite(scale) || width < 16 || height < 32 || width > 16384 || height > 16384 || scale < 0.25 || scale > 8 ||
      pixelsW < 1 || pixelsW > 16384 || pixelsH < 1 || pixelsH > 16384 || pixelsW * pixelsH > 33554432)
    throw new Error('invalid_live_viewport');
  const {content,prefixes} = measureGridInputs(runtime, context, width, height, scale);
  const frame = JSON.parse(runtime.grid_layout_frame(width,height,prefixes,scale));
  if (!frame.ok) throw new Error(frame.error || 'Invalid grid frame');
  if (content.layout_passes !== 1 || frame.grid_layout?.frame_layout_passes !== 1)
    throw new Error('Invalid grid layout-pass diagnostics');
  // Both numbers describe actual calls above, not Rust callback observations.
  frame.grid_layout.host_layout_passes = content.layout_passes + frame.grid_layout.frame_layout_passes;
  return {frame,content,prefixes,width,height};
}
