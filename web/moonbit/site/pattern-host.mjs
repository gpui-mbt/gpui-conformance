import {watchGridDeviceScale} from './grid-layout-host.mjs';
// Font measurements and canonical raster transport only; never shader arithmetic.
export function assertPatternInkDisjoint(context,frame,metadata) {
  const items=frame?.snapshot?.items;
  if(!Array.isArray(items)||frame.pattern?.text_order!=='disjoint_ink_checked_labels_last')throw new Error('Missing pattern paint-order proof');
  const labels=items.filter(item=>item.kind==='text_run');
  if(labels.length!==2||labels[0].id!==100||labels[1].id!==101)throw new Error('Missing source pattern labels');
  const inks=[];
  for(const label of labels) {
    context.font=`normal 400 ${label.font_size}px "${metadata.font_family}"`;
    context.textAlign='left';context.textBaseline='alphabetic';
    const m=context.measureText(label.text),b=label.bounds;
    const ascent=m.fontBoundingBoxAscent??m.actualBoundingBoxAscent;
    const descent=m.fontBoundingBoxDescent??m.actualBoundingBoxDescent;
    const baseline=(b.height-ascent-descent)/2+ascent;
    const ink={x:label.text_origin.x-m.actualBoundingBoxLeft-1,y:label.text_origin.y+baseline-m.actualBoundingBoxAscent-1,
      width:m.actualBoundingBoxLeft+m.actualBoundingBoxRight+2,height:m.actualBoundingBoxAscent+m.actualBoundingBoxDescent+2};
    if(!Object.values(ink).every(Number.isFinite)||ink.width<=0||ink.height<=0)throw new Error('Actual pattern glyph ink is unavailable');
    // A one-physical-pixel AA margin bounds the actual Canvas glyphs, not merely
    // advances or line boxes. Ancestor backgrounds precede the label in source.
    for(const item of items) {
      if(item.kind==='text_run'||item.id===1||(label.id===101&&item.id===11))continue;
      // Only source-later paint can invalidate labels-last normalization.
      if(label.id===101&&(item.id===10||(item.id>=20&&item.id<=23)||(item.id>=1040&&item.id<=1047)))continue;
      const p=item.bounds??item.shape?.bounds;
      if(!p)throw new Error('Pattern paint geometry is unavailable');
      if(ink.x<p.x+p.width&&ink.x+ink.width>p.x&&ink.y<p.y+p.height&&ink.y+ink.height>p.y)throw new Error('Pattern glyph ink overlaps later source paint');
    }
    inks.push({id:label.id,...ink});
  }
  return inks;
}

export function readPatternFrame(runtime,context,windowObject,metadata) {
  const width=windowObject.innerWidth,height=windowObject.innerHeight,scale=windowObject.devicePixelRatio;
  if(width!==600||height!==600||scale!==1)throw new Error('Pattern comparison requires 600×600 at DPR1');
  if(metadata.source_blob!=='7d2e98d16e24dc23dc307296a3b35c18e624d9e3'||metadata.runs?.length!==2)throw new Error('Invalid pattern source metadata');
  const widths=metadata.runs.map(run=>{context.font=`normal 400 ${run.font_size}px "${metadata.font_family}"`;return context.measureText(run.text).width;});
  const frame=JSON.parse(runtime.pattern_frame_at_scale(width,height,widths,scale,scale));
  if(!frame.ok)throw new Error(frame.error||'Invalid core pattern frame');
  const glyphInk=assertPatternInkDisjoint(context,frame,metadata);
  return {frame,width,height,scale,widths,glyphInk};
}

// DPR-only changes do not necessarily dispatch resize. A restored document must
// revalidate its source-sized profile before exposing any retained frame.
export function createPatternLifecycle(windowObject,onChange,onSuspend) {
  let stopped=false,suspended=false;
  let stopWatch=watchGridDeviceScale(windowObject,changed);
  function changed(){if(!stopped&&!suspended)onChange();}
  function hide(){
    if(stopped)return;
    suspended=true;stopWatch?.();stopWatch=null;onSuspend();
  }
  function show(){
    if(stopped)return;
    suspended=false;
    if(!stopWatch)stopWatch=watchGridDeviceScale(windowObject,changed);
    onChange();
  }
  windowObject.addEventListener('pagehide',hide);
  windowObject.addEventListener('pageshow',show);
  return {get suspended(){return suspended;},stop(){
    if(stopped)return;stopped=true;stopWatch?.();stopWatch=null;
    windowObject.removeEventListener('pagehide',hide);
    windowObject.removeEventListener('pageshow',show);
  }};
}
