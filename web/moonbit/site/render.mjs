export function validateFrame(frame) {
  if (!frame?.ok || frame.conformance !== 'unverified') throw new Error(frame?.error || 'Invalid example frame');
  const snapshot = frame.snapshot;
  if (snapshot?.schema_version !== 1 || !Array.isArray(snapshot.items) || !Array.isArray(frame.decorations)) throw new Error('Expected SceneSnapshot v1 and explicit host decorations');
  for (const item of snapshot.items) {
    if (!['quad', 'text', 'text_run'].includes(item.kind)) throw new Error(`Unsupported scene item ${item.kind}`);
    const b = item.bounds;
    if (!b || ![b.x,b.y,b.width,b.height].every(Number.isFinite) || b.width < 0 || b.height < 0) throw new Error('Invalid scene bounds');
    const c = item.color;
    if (!c || ![c.red,c.green,c.blue,c.alpha].every(n => Number.isInteger(n) && n >= 0 && n <= 255)) throw new Error('Invalid scene color');
    if (item.opacity !== undefined && (!Number.isFinite(item.opacity) || item.opacity < 0 || item.opacity > 1)) throw new Error('Invalid scene opacity');
    if ((item.kind === 'text' || item.kind === 'text_run') && (typeof item.text !== 'string' || !Number.isFinite(item.font_size) || item.font_size <= 0)) throw new Error('Invalid text item');
  }
  if (frame.scroll) {
    const s = frame.scroll;
    if (![s.first_id,s.top,s.height,s.y,s.max].every(Number.isFinite) ||
        !Number.isInteger(s.first_id) || s.first_id < 2 || s.top < 0 ||
        s.height <= 0 || s.y < 0 || s.y > s.max || s.max > 100000)
      throw new Error('Invalid scroll extension');
  }
  if (frame.font_button && !['x','y','width','height'].every(key =>
      Number.isFinite(frame.font_button[key]) && frame.font_button[key] >= 0))
    throw new Error('Invalid font button extension');
  const clips = new Map((snapshot.clip_chains || []).map(clip => [clip.id, clip.rects]));
  for (const rects of clips.values()) {
    if (!Array.isArray(rects) || rects.some(b => ![b.x,b.y,b.width,b.height].every(Number.isFinite) || b.width < 0 || b.height < 0)) throw new Error('Invalid scene clip');
  }
  for (const item of snapshot.items) if (item.clip_chain_id != null && !clips.has(item.clip_chain_id)) throw new Error('Unknown scene clip');
  const texts = new Set(snapshot.items.filter(i => i.kind === 'text' || i.kind === 'text_run').map(i => i.id));
  for (const item of snapshot.items.filter(i => i.kind === 'text_run')) {
    const o = item.text_origin, t = item.transform;
    if (!o || !t || ![o.x,o.y,t.a,t.b,t.c,t.d,t.tx,t.ty].every(Number.isFinite)) throw new Error('Invalid text run geometry');
    if (t.a !== 1 || t.b !== 0 || t.c !== 0 || t.d !== 1) throw new Error('Unsupported text run transform');
  }
  for (const style of frame.text_styles || []) {
    if (!texts.has(style.id) || ![400,700,800].includes(style.weight) || !['normal','italic'].includes(style.style) || !['none','underline','line_through'].includes(style.decoration)) throw new Error('Invalid host text style');
  }
  const quads = new Map(snapshot.items.filter(i => i.kind === 'quad').map(i => [i.id, i]));
  for (const rounded of frame.rounded_fills || []) {
    const b = quads.get(rounded.id)?.bounds;
    if (!b || !Number.isFinite(rounded.radius) || rounded.radius < 0 || rounded.radius > Math.min(b.width,b.height)/2) throw new Error('Invalid rounded fill');
  }
  for (const d of frame.decorations) {
    const b = quads.get(d.id)?.bounds;
    // Source focus ports need 3px/4px solid borders. Wider dashed strokes
    // remain unsupported; this is an explicit Canvas host boundary, not a
    // rounded-border addition to the portable SceneSnapshot contract.
    if (!b || !Number.isFinite(d.radius) || d.radius < 0 || d.radius > Math.min(b.width, b.height) / 2 || ![1,3,4].includes(d.border_width) || !/^#[0-9a-f]{6}$/i.test(d.border) || !['solid', 'dashed'].includes(d.border_style) || (d.border_style === 'dashed' && (d.border_width !== 1 || d.radius <= d.border_width / 2)) || (d.border_width > 1 && Math.min(b.width,b.height) < 2*d.border_width)) throw new Error('Invalid host decoration');
  }
  if (frame.shadows !== undefined && !Array.isArray(frame.shadows)) throw new Error('Invalid shadow extension');
  const shadowIds = new Set();
  for (const shadow of frame.shadows || []) {
    const b = quads.get(shadow?.id)?.bounds;
    if (!b || shadow.kind !== 'shadow_sm' || Object.keys(shadow).some(key => !['id','kind'].includes(key)) || shadowIds.has(shadow.id) || Math.min(b.width,b.height) <= 2 || frame.decorations.some(style => style.id === shadow.id && style.shadow)) throw new Error('Invalid shadow extension');
    shadowIds.add(shadow.id);
  }
  return frame;
}

export function roundedDashSegments(b, radius, width) {
  // A Canvas centerline dash pattern cannot preserve GPUI's outer-radius dash space.
  // Pinned gpui_wgpu/shaders.wgsl lays out 2w dashes from the top-left tangent,
  // then expands only the gaps to fit floor(outer perimeter / 3w) whole periods.
  if (!(width > 0 && radius > width / 2 && radius <= Math.min(b.width, b.height) / 2)) throw new Error('Unsupported rounded dash geometry');
  const inset = width / 2, r = radius - inset;
  const horizontal = b.width - 2 * radius, vertical = b.height - 2 * radius;
  const arc = radius * Math.PI / 2;
  const perimeter = 2 * horizontal + 2 * vertical + 4 * arc;
  const count = Math.floor(perimeter / (3 * width));
  if (!count) throw new Error('Rounded perimeter too short for a dash');
  const period = perimeter / count;
  const x = b.x, y = b.y, right = x + b.width, bottom = y + b.height;
  const segments = [
    {length: horizontal, from: [x + radius, y + inset], to: [right - radius, y + inset]},
    {length: arc, center: [right - radius, y + radius], angle: -Math.PI / 2},
    {length: vertical, from: [right - inset, y + radius], to: [right - inset, bottom - radius]},
    {length: arc, center: [right - radius, bottom - radius], angle: 0},
    {length: horizontal, from: [right - radius, bottom - inset], to: [x + radius, bottom - inset]},
    {length: arc, center: [x + radius, bottom - radius], angle: Math.PI / 2},
    {length: vertical, from: [x + inset, bottom - radius], to: [x + inset, y + radius]},
    {length: arc, center: [x + radius, y + radius], angle: Math.PI},
  ];
  const dashes = [];
  for (let i = 0; i < count; i++) {
    const start = i * period, end = start + 2 * width;
    let offset = 0;
    const commands = [];
    for (const segment of segments) {
      const a = Math.max(start, offset), z = Math.min(end, offset + segment.length);
      if (z > a) {
        const t0 = (a - offset) / segment.length, t1 = (z - offset) / segment.length;
        if (segment.center) {
          const angle0 = segment.angle + t0 * Math.PI / 2, angle1 = segment.angle + t1 * Math.PI / 2;
          const [cx, cy] = segment.center;
          if (!commands.length) commands.push(['moveTo', cx + r * Math.cos(angle0), cy + r * Math.sin(angle0)]);
          commands.push(['arc', cx, cy, r, angle0, angle1]);
        } else {
          const point = t => segment.from.map((v, j) => v + t * (segment.to[j] - v));
          if (!commands.length) commands.push(['moveTo', ...point(t0)]);
          commands.push(['lineTo', ...point(t1)]);
        }
      }
      offset += segment.length;
    }
    dashes.push(commands);
  }
  return {perimeter, count, period, dash_length: 2 * width, dashes};
}

export function drawFrame(context, frame, metadata, scale) {
  validateFrame(frame);
  if (!Number.isFinite(scale) || scale <= 0 || scale > 4) throw new Error('Invalid device scale');
  const styles = new Map(frame.decorations.map(style => [style.id, style]));
  const roundedFills = new Map((frame.rounded_fills || []).map(style => [style.id, style.radius]));
  const shadows = new Set((frame.shadows || []).map(style => style.id));
  const textStyles = new Map((frame.text_styles || []).map(style => [style.id, style]));
  const clips = new Map((frame.snapshot.clip_chains || []).map(clip => [clip.id, clip.rects]));
  context.save();
  try {
    context.setTransform(scale, 0, 0, scale, 0, 0);
    context.clearRect(0, 0, metadata.width, metadata.height);
    context.beginPath(); context.rect(0, 0, metadata.width, metadata.height); context.clip();
    for (const item of frame.snapshot.items) {
      context.save();
      try {
        if (frame.scroll && item.id >= frame.scroll.first_id) {
          // Do not pretend GPUI scroll clipping is a native SceneSnapshot API.
          context.beginPath();
          context.rect(0, frame.scroll.top, metadata.width, frame.scroll.height);
          context.clip();
          context.translate(0, -frame.scroll.y);
        }
        const b = item.bounds;
        const c = item.color;
        context.globalAlpha = item.opacity ?? 1;
        const style = styles.get(item.id);
        for (const rect of clips.get(item.clip_chain_id) || []) {
          context.beginPath(); context.rect(rect.x, rect.y, rect.width, rect.height); context.clip();
        }
        context.fillStyle = `rgba(${c.red},${c.green},${c.blue},${c.alpha / 255})`;
        if (item.kind === 'text' || item.kind === 'text_run') {
          const textStyle = textStyles.get(item.id);
          context.font = `${textStyle?.style || 'normal'} ${textStyle?.weight || 400} ${item.font_size}px "${metadata.font_family}"${metadata.font_fallback ? `, "${metadata.font_fallback}"` : ''}`;
          context.textAlign = 'left'; context.textBaseline = 'alphabetic';
          const metrics = context.measureText(item.text);
          const ascent = metrics.fontBoundingBoxAscent ?? metrics.actualBoundingBoxAscent;
          const descent = metrics.fontBoundingBoxDescent ?? metrics.actualBoundingBoxDescent;
          const baseline = (b.height - ascent - descent) / 2 + ascent;
          if (item.kind === 'text_run') {
            context.fillText(item.text, item.transform.tx + item.text_origin.x,
              item.transform.ty + item.text_origin.y + baseline);
          } else {
            context.fillText(item.text, b.x, b.y + baseline);
          }
          if (textStyle && textStyle.decoration !== 'none') {
            // Geometry follows pinned text_system/line.rs; Canvas font metrics and
            // rasterization remain explicit host extensions, not a conformance pass.
            const y = textStyle.decoration === 'underline'
              ? baseline + descent * 0.618 : ((ascent * 0.5) + baseline) * 0.5;
            context.fillRect(b.x, b.y + y, metrics.width, 1);
          }
        } else {
          if (shadows.has(item.id)) {
            // Source shadow_sm is two layers, not the legacy preview shadow.
            // Canvas blur is an explicit approximation of the GPU kernel.
            // Cast from offscreen and offset back so the opaque caster itself
            // never darkens the fill. Spread -1 shrinks its box by 1px per edge.
            for (const [blur,spread] of [[3,0],[2,-1]]) {
              context.save();
              try {
                context.fillStyle = '#000000';
                context.shadowColor = 'rgba(0,0,0,.1)';
                // Shadow lengths are device pixels in Canvas, unlike the path.
                context.shadowBlur = blur*scale;
                context.shadowOffsetX = 4096*scale;
                context.shadowOffsetY = scale;
                context.beginPath();
                context.roundRect(b.x-spread-4096,b.y-spread,b.width+2*spread,b.height+2*spread,
                  Math.max(0,(style?.radius || roundedFills.get(item.id) || 0)+spread));
                context.fill();
              } finally { context.restore(); }
            }
          }
          context.beginPath(); context.roundRect(b.x, b.y, b.width, b.height, style?.radius || roundedFills.get(item.id) || 0);
          if (style?.shadow) {
            // Canvas blur is not the GPUI GPU shadow kernel; never turn this preview into a pixel pass.
            context.shadowColor = 'rgba(0,0,0,.1)'; context.shadowBlur = 15; context.shadowOffsetY = 10;
          }
          context.fill(); context.shadowColor = 'transparent'; context.shadowBlur = 0; context.shadowOffsetY = 0;
          if (style) {
            context.lineWidth = style.border_width; context.strokeStyle = style.border;
            context.setLineDash([]); context.lineCap = 'butt';
            const inset = style.border_width / 2;
            if (style.border_style === 'dashed') {
              const {dashes} = roundedDashSegments(b, style.radius, style.border_width);
              context.beginPath();
              for (const commands of dashes) for (const [command, ...args] of commands) context[command](...args);
              context.stroke();
            } else {
              context.beginPath(); context.roundRect(b.x + inset, b.y + inset, b.width - 2 * inset, b.height - 2 * inset, Math.max(0, style.radius - inset)); context.stroke();
            }
          }
        }
      } finally { context.restore(); }
    }
  } finally { context.restore(); }
}
