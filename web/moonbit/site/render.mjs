import {validateImageResources, resolveImageResources} from './image-resources.mjs';
// Pinned gpui_macros/styles.rs presets only, not a caller-configurable shadow API.
const sourceShadowLayers = {
  shadow_sm: [
    {offset_x:0,offset_y:1,blur:3,spread:0},
    {offset_x:0,offset_y:1,blur:2,spread:-1},
  ],
  shadow_lg: [
    {offset_x:0,offset_y:10,blur:15,spread:-3},
    {offset_x:0,offset_y:4,blur:6,spread:-4},
  ],
  shadow_md: [
    {offset_x:0,offset_y:4,blur:6,spread:-1},
    {offset_x:0,offset_y:2,blur:4,spread:-2},
  ],
};

export function validateFrame(frame) {
  if (!frame?.ok || frame.conformance !== 'unverified') throw new Error(frame?.error || 'Invalid example frame');
  const snapshot = frame.snapshot;
  if (snapshot?.schema_version !== 1 || !Array.isArray(snapshot.items) || !Array.isArray(frame.decorations)) throw new Error('Expected SceneSnapshot v1 and explicit host decorations');
  for (const item of snapshot.items) {
    if (!['quad', 'text', 'text_run', 'image'].includes(item.kind)) throw new Error(`Unsupported scene item ${item.kind}`);
    const b = item.bounds;
    if (!b || ![b.x,b.y,b.width,b.height].every(Number.isFinite) || b.width < 0 || b.height < 0) throw new Error('Invalid scene bounds');
    const c = item.color;
    if (item.kind !== 'image' && (!c || ![c.red,c.green,c.blue,c.alpha].every(n => Number.isInteger(n) && n >= 0 && n <= 255))) throw new Error('Invalid scene color');
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
    // Explicit source marker admits only the authored 1px device-snapped
    // popover border. Generic callers retain the legacy integer-width contract.
    const sourceScale = snapshot.scale;
    const sourceBorder = d.border_source === 'device_snapped_1px' &&
      d.border_style === 'solid' && Number.isFinite(sourceScale) &&
      sourceScale >= 0.25 && sourceScale <= 4 && Number.isFinite(d.border_width) &&
      Math.abs(d.border_width - Math.max(1, Math.ceil(sourceScale - 0.5)) / sourceScale) <= 1e-9;
    const validWidth = d.border_source === undefined
      ? [1,2,3,4].includes(d.border_width) : sourceBorder;
    // Source drag/focus ports need 2px/3px/4px solid borders. Wider dashed strokes
    // remain unsupported; this is an explicit Canvas host boundary, not a
    // rounded-border addition to the portable SceneSnapshot contract.
    if (!b || !Number.isFinite(d.radius) || d.radius < 0 || d.radius > Math.min(b.width, b.height) / 2 || !validWidth || !/^#[0-9a-f]{6}$/i.test(d.border) || (d.border_opacity !== undefined && (!Number.isFinite(d.border_opacity) || d.border_opacity < 0 || d.border_opacity > 1)) || !['solid', 'dashed'].includes(d.border_style) || (d.border_style === 'dashed' && (d.border_width !== 1 || d.radius <= d.border_width / 2)) || (d.border_width > 1 && Math.min(b.width,b.height) < 2*d.border_width)) throw new Error('Invalid host decoration');
  }
  if (frame.shadows !== undefined && !Array.isArray(frame.shadows)) throw new Error('Invalid shadow extension');
  const shadowIds = new Set();
  for (const shadow of frame.shadows || []) {
    const b = quads.get(shadow?.id)?.bounds;
    const keys = shadow?.kind === 'shadow_md' ? ['id','kind','element_opacity'] : ['id','kind'];
    if (!b || !['shadow_sm','shadow_md','shadow_lg'].includes(shadow.kind) ||
        Object.keys(shadow).length !== keys.length || keys.some(key => !Object.hasOwn(shadow,key)) ||
        (shadow.kind === 'shadow_md' && (!Number.isFinite(shadow.element_opacity) || shadow.element_opacity < 0 || shadow.element_opacity > 1)) ||
        shadowIds.has(shadow.id) || sourceShadowLayers[shadow.kind].some(({spread}) =>
          ![b.width+2*spread,b.height+2*spread].every(size => Number.isFinite(size) && size > 0)) ||
        frame.decorations.some(style => style.id === shadow.id && style.shadow)) throw new Error('Invalid shadow extension');
    shadowIds.add(shadow.id);
  }
  if (shadowIds.size) {
    // This extension lowers an axis-aligned source example, not arbitrary
    // retained GPUI layers/transforms or the legacy preview shadow model.
    if (frame.scroll || frame.decorations.some(style => style.shadow) ||
        new Set(snapshot.items.map(item => item.id)).size !== snapshot.items.length ||
        snapshot.items.some(item => item.transform &&
          !['a','b','c','d','tx','ty'].every((key, index) => item.transform[key] === [1,0,0,1,0,0][index])))
      throw new Error('Unsupported source shadow paint geometry');
  }
  if (snapshot.items.some(item => item.kind === 'image') && (frame.shadows?.length || frame.scroll)) throw new Error('Unsupported mixed image paint extension');
  validateImageResources(snapshot);
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

// Bound the explicit shadow_sm/shadow_md/shadow_lg extensions by pinned GPUI scene ordering.
// window.rs inserts offset/spread shadow bounds WITHOUT the blur tail;
// bounds_tree.rs assigns 1 + the maximum strictly intersecting order;
// scene.rs batches equal-order Shadow before Quad, retaining insertion ties.
// Canvas still approximates the GPU blur kernel. Existing item paints remain
// composite host operations; this does not reconstruct arbitrary GPUI layers,
// parent-border continuations, border strips, or text atlas batches.
function sourceShadowPaintCommands(frame, metadata, scale) {
  const shadowStyles = new Map((frame.shadows || []).map(style => [style.id,style]));
  if (!shadowStyles.size) return frame.snapshot.items.map(item => ({item}));
  const clips = new Map((frame.snapshot.clip_chains || []).map(clip => [clip.id, clip.rects]));
  const commands = [], inserted = [];
  const edges = b => ({left:b.x,top:b.y,right:b.x+b.width,bottom:b.y+b.height});
  const intersect = (a,b) => ({left:Math.max(a.left,b.left),top:Math.max(a.top,b.top),
    right:Math.min(a.right,b.right),bottom:Math.min(a.bottom,b.bottom)});
  const cover = b => ({left:Math.floor(b.left*scale), top:Math.floor(b.top*scale),
    right:Math.ceil(b.right*scale), bottom:Math.ceil(b.bottom*scale)});
  const overlaps = (a,b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
  for (const item of frame.snapshot.items) {
    const b = item.bounds;
    const shadowStyle = shadowStyles.get(item.id);
    const shadowOpacity = shadowStyle?.kind === 'shadow_md' ? shadowStyle.element_opacity : item.opacity ?? 1;
    for (const shadow of shadowStyle ? [...sourceShadowLayers[shadowStyle.kind],null] : [null]) {
      const spread = shadow?.spread || 0;
      const primitive = edges(shadow ? {x:b.x+shadow.offset_x-spread,y:b.y+shadow.offset_y-spread,width:b.width+2*spread,height:b.height+2*spread} : b);
      // Intersect inherited logical masks before covering the combined mask,
      // as Window::with_content_mask/snapped_content_mask do. Covering each
      // mask separately can manufacture an overlap across a fractional gap.
      let mask = edges({x:0,y:0,width:metadata.width,height:metadata.height});
      for (const clip of clips.get(item.clip_chain_id) || []) mask = intersect(mask,edges(clip));
      if (![...Object.values(primitive),...Object.values(mask)].every(Number.isFinite)) throw new Error('Invalid source shadow paint bounds');
      if (mask.left >= mask.right || mask.top >= mask.bottom) continue;
      const bounds = intersect(cover(primitive),cover(mask));
      if (!Object.values(bounds).every(Number.isFinite)) throw new Error('Invalid source shadow paint bounds');
      if (bounds.left >= bounds.right || bounds.top >= bounds.bottom) continue;
      const order = 1 + inserted.reduce((max, entry) => overlaps(bounds,entry.bounds) ? Math.max(max,entry.order) : max,0);
      // Source Shadow < Quad ties also apply to full-bounds border quads.
      // Text retains its later GPUI primitive-kind precedence.
      const kind = shadow ? 0 : item.kind === 'quad' ? 1 : 4;
      inserted.push({bounds,order});
      commands.push({item,shadow,shadowOpacity,order,kind,index:commands.length});
    }
  }
  return commands.sort((a,b) => a.order-b.order || a.kind-b.kind || a.index-b.index);
}

export function drawFrame(context, frame, metadata, scale, imageResources) {
  return drawFrameInternal(context, frame, metadata, scale, true, imageResources);
}

function drawFrameInternal(context, frame, metadata, scale, clear, imageResources) {
  validateFrame(frame);
  const images = resolveImageResources(frame.snapshot, imageResources);
  if (!Number.isFinite(scale) || scale <= 0 || scale > 4) throw new Error('Invalid device scale');
  const styles = new Map(frame.decorations.map(style => [style.id, style]));
  const roundedFills = new Map((frame.rounded_fills || []).map(style => [style.id, style.radius]));
  const textStyles = new Map((frame.text_styles || []).map(style => [style.id, style]));
  const clips = new Map((frame.snapshot.clip_chains || []).map(clip => [clip.id, clip.rects]));
  const commands = sourceShadowPaintCommands(frame, metadata, scale);
  context.save();
  try {
    context.setTransform(scale, 0, 0, scale, 0, 0);
    if (clear) context.clearRect(0, 0, metadata.width, metadata.height);
    context.beginPath(); context.rect(0, 0, metadata.width, metadata.height); context.clip();
    for (const {item,shadow,shadowOpacity} of commands) {
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
        context.globalAlpha = shadow ? shadowOpacity : item.opacity ?? 1;
        const style = styles.get(item.id);
        for (const rect of clips.get(item.clip_chain_id) || []) {
          context.beginPath(); context.rect(rect.x, rect.y, rect.width, rect.height); context.clip();
        }
        if (c) context.fillStyle = `rgba(${c.red},${c.green},${c.blue},${c.alpha / 255})`;
        if (shadow) {
          const {offset_x,offset_y,blur,spread} = shadow;
          // Keep both source layers, opacity and clip. The offscreen caster
          // prevents its opaque fill from appearing in the viewport.
          context.fillStyle = '#000000';
          context.shadowColor = 'rgba(0,0,0,.1)';
          // Shadow lengths are device pixels in Canvas, unlike the path.
          context.shadowBlur = blur*scale;
          context.shadowOffsetX = (4096+offset_x)*scale;
          context.shadowOffsetY = offset_y*scale;
          context.beginPath();
          context.roundRect(b.x-spread-4096,b.y-spread,b.width+2*spread,b.height+2*spread,
            Math.max(0,(style?.radius || roundedFills.get(item.id) || 0)+spread));
          context.fill();
        } else if (item.kind === 'image') {
          const crop = item.image_bounds;
          context.beginPath(); context.rect(crop.x,crop.y,crop.width,crop.height); context.clip();
          images(context,item);
        } else if (item.kind === 'text' || item.kind === 'text_run') {
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
          context.beginPath(); context.roundRect(b.x, b.y, b.width, b.height, style?.radius || roundedFills.get(item.id) || 0);
          if (style?.shadow) {
            // Canvas blur is not the GPUI GPU shadow kernel; never turn this preview into a pixel pass.
            context.shadowColor = 'rgba(0,0,0,.1)'; context.shadowBlur = 15; context.shadowOffsetY = 10;
          }
          context.fill(); context.shadowColor = 'transparent'; context.shadowBlur = 0; context.shadowOffsetY = 0;
          if (style) {
            context.lineWidth = style.border_width; context.strokeStyle = style.border;
            if (style.border_opacity !== undefined)
              context.globalAlpha = (item.opacity ?? 1) * style.border_opacity;
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

// Ordered presentation only. Core already resolved physical geometry, coverage,
// clips, transforms, alpha and shader-output channels. No gradient arithmetic.
export function validateCoreRasterFrame(frame,metadata,scale) {
  if(!frame?.ok||frame.conformance!=='unverified'||frame.raster_transport!=='ordered_core_webgl2_linear_straight_v1')throw new Error('Invalid core raster transport');
  if(!Number.isFinite(scale)||scale<.25||scale>4||![metadata.width,metadata.height].every(v=>Number.isFinite(v)&&v>0))throw new Error('Invalid core raster viewport');
  const width=Math.ceil(metadata.width*scale),height=Math.ceil(metadata.height*scale);
  if(width<1||height<1||width>2048||height>2048||width*height>1048576)throw new Error('Core raster viewport exceeds resource cap');
  const snapshot=frame.snapshot;
  if (snapshot?.resources !== undefined && (!Array.isArray(snapshot.resources) || snapshot.resources.length)) throw new Error('Image resources unsupported in core raster transport');
  if(snapshot?.schema_version!==1||!Array.isArray(snapshot.items)||snapshot.items.length>128||!Array.isArray(frame.operations)||frame.operations.length>snapshot.items.length||frame.decorations?.length!==0)throw new Error('Invalid ordered core raster scene');
  const viewport=snapshot.viewport;
  if(!viewport||viewport.x!==0||viewport.y!==0||viewport.width!==metadata.width||viewport.height!==metadata.height||snapshot.scale!==scale)throw new Error('Core snapshot/viewport mismatch');
  if(frame.shadows?.length||frame.rounded_fills?.length||frame.text_styles?.length||frame.scroll)throw new Error('Unsupported mixed raster decoration');
  // Keep the legacy validator intact, applied to the exact legacy scene items.
  validateFrame({...frame,snapshot:{...snapshot,items:snapshot.items.filter(i=>i.kind!=='paint')}});
  let total=0,cursor=0;const seen=new Set();
  for(let index=0;index<frame.operations.length;index++) {
    const op=frame.operations[index],item=snapshot.items[cursor];
    if(!op||seen.has(op)||op.index!==cursor||!['legacy','rgba','rgba_run','skip'].includes(op.kind)||!['paint','quad','text','text_run'].includes(item?.kind))throw new Error('Malformed ordered core operation');seen.add(op);
    const count=op.kind==='rgba_run'?op.count:1;
    if(!Number.isSafeInteger(count)||count<1||cursor+count>snapshot.items.length)throw new Error('Invalid core run membership');
    if(op.kind==='rgba_run'&&snapshot.items.slice(cursor,cursor+count).some(i=>!['paint','quad'].includes(i.kind)))throw new Error('Core run crosses legacy text');
    cursor+=count;
    if(op.kind==='legacy') {
      if(!['quad','text','text_run'].includes(item.kind)||Object.keys(op).sort().join(',')!=='index,kind')throw new Error('Invalid legacy operation');
    } else if(op.kind==='skip') {
      if(!['quad','paint'].includes(item.kind)||Object.keys(op).sort().join(',')!=='index,kind')throw new Error('Invalid skipped operation');
    } else {
      if(!['quad','paint'].includes(item.kind)||Object.keys(op).sort().join(',')!==(op.kind==='rgba_run'?'count,height,index,kind,rgba,width,x,y':'height,index,kind,rgba,width,x,y'))throw new Error('Invalid raster operation');
      if(![op.x,op.y,op.width,op.height].every(Number.isSafeInteger)||op.x<0||op.y<0||op.width<1||op.height<1||op.width>2048||op.height>2048||op.x+op.width>width||op.y+op.height>height)throw new Error('Invalid physical core tile bounds');
      const count=op.width*op.height;total+=count;
      if(count>1048576||total>4194304||!Array.isArray(op.rgba)||seen.has(op.rgba)||op.rgba.length!==4*count||!op.rgba.every(v=>Number.isInteger(v)&&v>=0&&v<=255))throw new Error('Invalid, aliased or oversized core tile bytes');seen.add(op.rgba);
      if(op.kind==='rgba_run'&&op.rgba.some((v,i)=>i%4===3&&v!==255))throw new Error('Canonical paint run must be opaque after core compositing');
    }
  }
  if(cursor!==snapshot.items.length)throw new Error('Incomplete core operation stream');
  return {width,height};
}

export function drawCoreRasterFrame(context,frame,metadata,scale,makeSurface=(w,h)=>new OffscreenCanvas(w,h)) {
  const {width,height}=validateCoreRasterFrame(frame,metadata,scale);
  // Allocate/upload every tile before touching the destination, so malformed
  // later buffers or allocation failures cannot partially present the frame.
  const surfaces=new Map();
  for(const op of frame.operations)if(op.kind==='rgba'||op.kind==='rgba_run') {
    const surface=makeSurface(op.width,op.height),tile=surface.getContext('2d');
    if(!tile)throw new Error('Core tile Canvas2D unavailable');
    const image=tile.createImageData(op.width,op.height);image.data.set(op.rgba);tile.putImageData(image,0,0);surfaces.set(op.index,surface);
  }
  context.save();
  try {
    context.setTransform(1,0,0,1,0,0);context.globalAlpha=1;context.globalCompositeOperation='source-over';
    context.clearRect(0,0,width,height);
    for(const op of frame.operations) {
      if(op.kind==='skip')continue;
      if(op.kind==='rgba'||op.kind==='rgba_run') {
        context.save();try{context.setTransform(1,0,0,1,0,0);context.globalAlpha=1;context.globalCompositeOperation='source-over';context.drawImage(surfaces.get(op.index),op.x,op.y);}finally{context.restore();}
      } else {
        // One canonical item, in its original position. No backing resize/clear.
        drawFrameInternal(context,{ok:true,conformance:'unverified',decorations:[],snapshot:{...frame.snapshot,items:[frame.snapshot.items[op.index]]}},metadata,scale,false);
      }
    }
  } finally {context.restore();}
}


