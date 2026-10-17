// Font/viewport and trusted-event transport only. Core routes the click and owns
// layout, canonical paint order, coverage, gradient sampling and raster bytes.
export function gradientRenderScale(width,height,actualDeviceScale) {
  if(![width,height,actualDeviceScale].every(Number.isFinite)||width<240||width>2048||height<300||height>2048||actualDeviceScale<.25||actualDeviceScale>64)throw new Error('Invalid live gradient viewport/device scale');
  const fits=s=>Math.ceil(width*s)<=2048&&Math.ceil(height*s)<=2048&&Math.ceil(width*s)*Math.ceil(height*s)<=1048576;
  let scale=Math.min(actualDeviceScale,4);
  if(!fits(scale)){let low=.25,high=scale;for(let i=0;i<64;i++){const mid=(low+high)/2;if(fits(mid))low=mid;else high=mid;}scale=low;}
  return {actualDeviceScale,effectiveRenderScale:scale,backingWidth:Math.ceil(width*scale),backingHeight:Math.ceil(height*scale),renderScaleReduced:scale!==actualDeviceScale};
}
export function readGradientFrame(runtime,context,windowObject,metadata,policy=false) {
  const width=windowObject.innerWidth,height=windowObject.innerHeight,deviceScale=windowObject.devicePixelRatio;
  if(policy&&(width!==960||height!==600||deviceScale!==1))throw new Error('Policy probe requires its frozen viewport');
  const transport=gradientRenderScale(width,height,deviceScale),scale=transport.effectiveRenderScale;
  const widths=metadata.runs.map(run=>{context.font=`normal 400 ${run.font_size}px "IBM Plex Sans"`;return context.measureText(run.text).width;});
  const frame=JSON.parse(policy?runtime.gradient_policy_frame():runtime.gradient_frame_at_scale(width,height,widths,deviceScale,scale));
  if(!frame.ok)throw new Error(frame.error||'Invalid core gradient frame');
  return {frame,width,height,scale,widths,...transport};
}
export function createGradientHost({runtime,canvas,render}) {
  const events=[];let stopped=false;
  function click(event) {
    if(!event.isTrusted||event.button!==0)return;
    const b=canvas.getBoundingClientRect(),x=event.clientX-b.left,y=event.clientY-b.top;
    if(!Number.isFinite(x)||!Number.isFinite(y))return;
    runtime.gradient_click(x,y);events.push({type:'click',x,y,button:event.button,trusted:true});render();
  }
  canvas.addEventListener('click',click);
  return {events,stop(){if(stopped)return;stopped=true;canvas.removeEventListener('click',click);runtime.gradient_reset();}};
}
