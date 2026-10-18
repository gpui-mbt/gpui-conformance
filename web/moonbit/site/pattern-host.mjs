import {watchGridDeviceScale} from './grid-layout-host.mjs';
// Font measurements and canonical raster transport only; never shader arithmetic.
export function assertPatternInkDisjoint(context,frame,metadata,scale=1) {
  const items=frame?.snapshot?.items;
  if(!Array.isArray(items)||frame.pattern?.text_order!=='disjoint_ink_checked_labels_last')throw new Error('Missing pattern paint-order proof');
  const labels=items.filter(item=>item.kind==='text_run');
  if(labels.length!==2||labels[0].id!==100||labels[1].id!==101)throw new Error('Missing source pattern labels');
  const background=items.find(item=>item.id===0);
  if(background){
    const b=background.bounds,v=frame.snapshot.viewport,c=background.color,t=background.transform;
    if(items[0]!==background||background.kind!=='quad'||!v||!b||b.x!==0||b.y!==0||b.width!==v.width||b.height!==v.height||c?.red!==255||c?.green!==255||c?.blue!==255||c?.alpha!==255||background.opacity!==1||background.clip_chain_id!=null||!t||t.a!==1||t.b!==0||t.c!==0||t.d!==1||t.tx!==0||t.ty!==0)throw new Error('Invalid live pattern canvas background');
  }
  const inks=[];
  for(const label of labels) {
    context.font=`normal 400 ${label.font_size}px "${metadata.font_family}"`;
    context.textAlign='left';context.textBaseline='alphabetic';
    const m=context.measureText(label.text),b=label.bounds;
    const ascent=m.fontBoundingBoxAscent??m.actualBoundingBoxAscent;
    const descent=m.fontBoundingBoxDescent??m.actualBoundingBoxDescent;
    const baseline=(b.height-ascent-descent)/2+ascent;
    const margin=1/scale;
    const ink={x:label.text_origin.x-m.actualBoundingBoxLeft-margin,y:label.text_origin.y+baseline-m.actualBoundingBoxAscent-margin,
      width:m.actualBoundingBoxLeft+m.actualBoundingBoxRight+2*margin,height:m.actualBoundingBoxAscent+m.actualBoundingBoxDescent+2*margin};
    if(!Object.values(ink).every(Number.isFinite)||ink.width<=0||ink.height<=0)throw new Error('Actual pattern glyph ink is unavailable');
    // A one-physical-pixel AA margin bounds the actual Canvas glyphs, not merely
    // advances or line boxes. Ancestor backgrounds precede the label in source.
    for(const item of items) {
      if(item.kind==='text_run'||item.id===0||item.id===1||(label.id===101&&item.id===11))continue;
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

// Bound the physical raster without changing the authored 600px content geometry.
// A reduced backing scale is disclosed and never qualifies a comparison profile.
export function patternRenderScale(width,height,actualDeviceScale) {
  if(![width,height,actualDeviceScale].every(Number.isFinite)||width<1||width>2048||height<1||height>2048||actualDeviceScale<.25||actualDeviceScale>64)throw new Error('Invalid live pattern viewport/device scale');
  const fits=s=>Math.ceil(width*s)<=2048&&Math.ceil(height*s)<=2048&&Math.ceil(width*s)*Math.ceil(height*s)<=1048576;
  let scale=Math.min(actualDeviceScale,4);
  if(!fits(scale)){let low=.25,high=scale;for(let i=0;i<64;i++){const mid=(low+high)/2;if(fits(mid))low=mid;else high=mid;}scale=low;}
  // Division back to logical units must preserve the integer physical footprint.
  // Rare floating roundtrip expansion falls back to an exact binary scale.
  const stable=n=>Math.ceil(Math.ceil(n*scale)/scale*scale)===Math.ceil(n*scale);
  if(!stable(width)||!stable(height))scale=2**Math.floor(Math.log2(scale));
  return {actualDeviceScale,effectiveRenderScale:scale,backingWidth:Math.ceil(width*scale),backingHeight:Math.ceil(height*scale),renderScaleReduced:scale!==actualDeviceScale};
}
export function readPatternFrame(runtime,context,windowObject,metadata) {
  const width=windowObject.innerWidth,height=windowObject.innerHeight,deviceScale=windowObject.devicePixelRatio;
  const transport=patternRenderScale(width,height,deviceScale),scale=transport.effectiveRenderScale;
  if(metadata.source_blob!=='7d2e98d16e24dc23dc307296a3b35c18e624d9e3'||metadata.runs?.length!==2)throw new Error('Invalid pattern source metadata');
  const widths=metadata.runs.map(run=>{context.font=`normal 400 ${run.font_size}px "${metadata.font_family}"`;return context.measureText(run.text).width;});
  const frame=JSON.parse(runtime.pattern_frame_at_scale(width,height,widths,deviceScale,scale));
  if(!frame.ok)throw new Error(frame.error||'Invalid core pattern frame');
  const comparisonProfileMatch=width===600&&height===600&&deviceScale===1&&scale===1;
  if(frame.pattern?.comparison_profile_match!==comparisonProfileMatch)throw new Error('Pattern comparison profile metadata mismatch');
  const glyphInk=assertPatternInkDisjoint(context,frame,metadata,scale);
  return {frame,width,height,scale,widths,glyphInk,rasterWidth:transport.backingWidth/scale,rasterHeight:transport.backingHeight/scale,...transport};
}

// DPR-only changes do not necessarily dispatch resize. A restored document must
// revalidate its live viewport before exposing any retained frame.
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
