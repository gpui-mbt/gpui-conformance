export function validateFrame(frame) {
  if (!frame?.ok || frame.conformance !== 'unverified') throw new Error(frame?.error || 'Invalid example frame');
  const snapshot = frame.snapshot;
  if (snapshot?.schema_version !== 1 || !Array.isArray(snapshot.items) || !Array.isArray(frame.decorations)) throw new Error('Expected SceneSnapshot v1 and explicit host decorations');
  for (const item of snapshot.items) {
    if (!['quad', 'text'].includes(item.kind)) throw new Error(`Unsupported scene item ${item.kind}`);
    const b = item.bounds;
    if (!b || ![b.x,b.y,b.width,b.height].every(Number.isFinite) || b.width < 0 || b.height < 0) throw new Error('Invalid scene bounds');
    const c = item.color;
    if (!c || ![c.red,c.green,c.blue,c.alpha].every(n => Number.isInteger(n) && n >= 0 && n <= 255)) throw new Error('Invalid scene color');
    if (item.kind === 'text' && (typeof item.text !== 'string' || !Number.isFinite(item.font_size) || item.font_size <= 0)) throw new Error('Invalid text item');
  }
  const ids = new Set(snapshot.items.filter(i => i.kind === 'quad').map(i => i.id));
  for (const d of frame.decorations) {
    if (!ids.has(d.id) || !Number.isFinite(d.radius) || d.radius < 0 || d.border_width !== 1 || !/^#[0-9a-f]{6}$/i.test(d.border) || !Array.isArray(d.dash) || !d.dash.every(n => Number.isFinite(n) && n > 0)) throw new Error('Invalid host decoration');
  }
  return frame;
}

export function drawFrame(context, frame, metadata, scale) {
  validateFrame(frame);
  if (!Number.isFinite(scale) || scale <= 0 || scale > 4) throw new Error('Invalid device scale');
  const styles = new Map(frame.decorations.map(style => [style.id, style]));
  context.save();
  try {
    context.setTransform(scale, 0, 0, scale, 0, 0);
    context.clearRect(0, 0, metadata.width, metadata.height);
    context.beginPath(); context.rect(0, 0, metadata.width, metadata.height); context.clip();
    for (const item of frame.snapshot.items) {
      context.save();
      try {
        const b = item.bounds;
        const c = item.color;
        const style = styles.get(item.id);
        context.fillStyle = `rgba(${c.red},${c.green},${c.blue},${c.alpha / 255})`;
        if (item.kind === 'text') {
          context.font = `${item.font_size}px "${metadata.font_family}"`;
          context.textAlign = 'left'; context.textBaseline = 'alphabetic';
          const metrics = context.measureText(item.text);
          const ascent = metrics.fontBoundingBoxAscent ?? metrics.actualBoundingBoxAscent;
          const descent = metrics.fontBoundingBoxDescent ?? metrics.actualBoundingBoxDescent;
          context.fillText(item.text, b.x, b.y + (b.height - ascent - descent) / 2 + ascent);
        } else {
          context.beginPath(); context.roundRect(b.x, b.y, b.width, b.height, style?.radius || 0);
          if (style?.shadow) {
            // Canvas blur is not the GPUI GPU shadow kernel; never turn this preview into a pixel pass.
            context.shadowColor = 'rgba(0,0,0,.1)'; context.shadowBlur = 15; context.shadowOffsetY = 10;
          }
          context.fill(); context.shadowColor = 'transparent'; context.shadowBlur = 0; context.shadowOffsetY = 0;
          if (style) {
            context.lineWidth = style.border_width; context.strokeStyle = style.border; context.setLineDash(style.dash);
            const inset = style.border_width / 2;
            context.beginPath(); context.roundRect(b.x + inset, b.y + inset, b.width - 2 * inset, b.height - 2 * inset, Math.max(0, style.radius - inset)); context.stroke();
          }
        }
      } finally { context.restore(); }
    }
  } finally { context.restore(); }
}
