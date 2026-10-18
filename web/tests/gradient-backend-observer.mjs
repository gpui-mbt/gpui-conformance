// Observation-only wrappers: forward original receiver/arguments/result untouched.
// Bind observations to the final visible canvas, not discarded context history.
export function installBackendObserver() {
 globalThis.gradientBackendEvents=[];const ids=new WeakMap();let nextId=1;
 const id=canvas=>{if(!canvas||typeof canvas!=='object')return null;if(!ids.has(canvas))ids.set(canvas,nextId++);return ids.get(canvas);};
 const record=entry=>gradientBackendEvents.push({...entry,time:performance.now()});
 globalThis.gradientBackendSnapshot=()=>({events:gradientBackendEvents.slice(),visible_canvases:Array.from(document.querySelectorAll('canvas')).filter(c=>{const b=c.getBoundingClientRect();return c.isConnected&&b.width>0&&b.height>0;}).map(c=>({canvas_id:id(c),width:c.width,height:c.height}))});
 const proto=globalThis.HTMLCanvasElement?.prototype;
 if(proto){const original=proto.getContext;proto.getContext=function(...args){const result=Reflect.apply(original,this,args);const entry={kind:'getContext',requested:String(args[0]),returned:!!result,canvas_id:id(this)};
  if(result&&['webgl','webgl2','experimental-webgl'].includes(args[0]))try{entry.version=result.getParameter(result.VERSION);entry.renderer=result.getParameter(result.RENDERER);const ext=result.getExtension('WEBGL_debug_renderer_info');if(ext)entry.unmasked_renderer=result.getParameter(ext.UNMASKED_RENDERER_WEBGL);}catch(e){entry.observation_error=String(e);}
  record(entry);return result;};}
 if(globalThis.GPUCanvasContext){const original=GPUCanvasContext.prototype.configure;GPUCanvasContext.prototype.configure=function(...args){const result=Reflect.apply(original,this,args);const c=args[0];record({kind:'webgpu.configure',canvas_id:id(this.canvas),format:c.format,alphaMode:c.alphaMode||'opaque',colorSpace:c.colorSpace||'srgb',usage:c.usage??null});return result;};}
 if(globalThis.GPU){const original=GPU.prototype.requestAdapter;GPU.prototype.requestAdapter=function(...args){const promise=Reflect.apply(original,this,args);promise.then(adapter=>{const info=adapter?.info;record({kind:'requestAdapter.resolved',returned:!!adapter,info:info?{vendor:info.vendor,architecture:info.architecture,device:info.device,description:info.description}:null});},error=>record({kind:'requestAdapter.rejected',error:String(error)}));return promise;};}
}
export function classifyBackend(snapshot) {
 const events=Array.isArray(snapshot)?snapshot:snapshot.events,visible=Array.isArray(snapshot)?[]:snapshot.visible_canvases;
 const ids=new Set(visible.map(c=>c.canvas_id));const bound=events.filter(e=>ids.has(e.canvas_id));
 const webgpu=bound.filter(e=>e.kind==='webgpu.configure');
 const gl=bound.filter(e=>e.kind==='getContext'&&e.returned&&['webgl','webgl2','experimental-webgl'].includes(e.requested));
 const observed=visible.length!==1?'pending_visible_canvas_not_unique':webgpu.length&&gl.length?'pending_ambiguous_context_history':webgpu.length?'webgpu_visible_canvas_configured':gl.length?'webgl_visible_canvas_context_returned':'pending_not_observed';
 return {observed,formats:[...new Set(webgpu.map(e=>e.format))],visible_canvases:visible,
  qualification:'Browser API observations bound to the final visible canvas. No native/Metal equivalence; missing format or worker-only configuration stays pending.',events};
}
