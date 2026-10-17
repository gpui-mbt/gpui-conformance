import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {verifyCanvasCapture,exportLiveCanvas,captureIdentity} from './anchor-live-capture.mjs';
function png(width,height,color) {
  const result=spawnSync('python3',['-c','import io,sys;from PIL import Image;im=Image.new("RGBA",tuple(map(int,sys.argv[1:3])),tuple(map(int,sys.argv[3:])));im.save(sys.stdout.buffer,format="PNG")',width,height,...color].map(String));
  assert.equal(result.status,0,String(result.stderr));return result.stdout;
}
function fixture(color=[0,0,0,255]) {
  const before={width:4,height:4,scale:1,status:'ready',canvas:[4,4],canvasBounds:{x:0,y:0,width:4,height:4},canvasHidden:false,errorHidden:true,noticeHidden:false,
    metadata:{width:4,height:4},hostScale:1,frame:{snapshot:{scale:1},anchor:{hovered:2}},document_id:'same-document'};
  const rgba=Buffer.from(Array(16).fill(color).flat());
  return {before,after:structuredClone(before),expected:structuredClone(before),rgba,png:png(4,4,color),samples:[{kind:'hover',x:1,y:1,rgba:color}]};
}
test('Canvas PNG export is independently decoded and compared with the complete separate live RGBA buffer',()=>{
  const f=fixture(),result=verifyCanvasCapture(f);assert.equal(result.kind,'canvas_export');assert.equal(result.composited_page_screenshot,false);assert.equal(result.rgba_bytes,64);
});
test('same-sized stale image, a single changed pixel, wrong decoded dimensions and false pixel probes fail',()=>{
  const f=fixture(),stale=png(4,4,[255,255,255,255]);
  assert.throws(()=>verifyCanvasCapture({...f,png:stale}),/stale same-size capture/);
  assert.throws(()=>verifyCanvasCapture({...f,png:stale,rgba:Buffer.alloc(64,255)}),/Decoded PNG sample/,
    'Even a matching stale PNG+RGBA pair cannot claim the retained hover pixel');
  const altered=Buffer.from(f.rgba);altered[altered.length-3]=123;
  assert.throws(()=>verifyCanvasCapture({...f,rgba:altered}),/stale same-size capture/);
  assert.throws(()=>verifyCanvasCapture({...f,png:png(5,4,[0,0,0,255])}),/dimensions/);
  assert.throws(()=>verifyCanvasCapture({...f,samples:[{kind:'wrong',x:1,y:1,rgba:[255,255,255,255]}]}),/Decoded PNG sample/);
});
test('same-sized stale frame, viewport/DPR changes, changed hover/document and missing backing pixels fail',()=>{
  const f=fixture();
  for(const mutate of [s=>s.width=5,s=>s.scale=2,s=>s.frame.anchor.hovered=-1,s=>s.document_id='new-document',s=>s.noticeHidden=true]) {
    const after=structuredClone(f.after);mutate(after);assert.throws(()=>verifyCanvasCapture({...f,after}),/changed during capture/);
    const expected=structuredClone(f.expected);mutate(expected);assert.throws(()=>verifyCanvasCapture({...f,expected}),/stale relative/);
  }
  assert.throws(()=>verifyCanvasCapture({...f,rgba:f.rgba.subarray(4)}),/buffer length/);
});
test('actual live harness uses synchronous Canvas export, never Playwright screenshot, and preserves strict capture sources',()=>{
  const source=readFileSync(new URL('./anchor-live-browser.mjs',import.meta.url),'utf8');
  assert(!source.includes('page.screenshot'));assert(source.includes('frame.evaluate(exportLiveCanvas)'));
  const helper=exportLiveCanvas.toString();assert(helper.includes("toDataURL('image/png')"));assert(helper.includes('getImageData(0,0,canvas.width,canvas.height)'));assert(!helper.includes('await'));
  const state=fixture().before;assert.deepEqual(captureIdentity({...state,lifecycle:['irrelevant']}),state);
});

test('atomic browser exporter preserves separate PNG and RGBA reads and exposes a changed hover',async()=>{
  const {default:vm}=await import('node:vm');
  const f=fixture();
  let current=structuredClone(f.before),mutate=false;
  const canvas={width:4,height:4,hidden:false,getBoundingClientRect:()=>({x:0,y:0,width:4,height:4}),
    toDataURL:()=>{if(mutate)current.frame.anchor.hovered=-1;return `data:image/png;base64,${f.png.toString('base64')}`;},
    getContext:()=>({getImageData:()=>({data:new Uint8ClampedArray(f.rgba)})})};
  const sandbox={structuredClone,innerWidth:4,innerHeight:4,devicePixelRatio:1,btoa:s=>Buffer.from(s,'binary').toString('base64'),
    document:{querySelector:()=>canvas,getElementById:id=>({hidden:id==='error'}),documentElement:{dataset:{runtimeStatus:'ready'}}},
    anchorLiveProbe:{document_id:'same-document'},get gpuiExample(){return {metadata:current.metadata,frame:current.frame,scale:1};}};
  const capture=()=>vm.runInNewContext(`(${exportLiveCanvas.toString()})()`,sandbox);
  let actual=capture();verifyCanvasCapture({...actual,expected:f.expected,png:Buffer.from(actual.png.split(',')[1],'base64'),rgba:Buffer.from(actual.rgba,'base64')});
  mutate=true;actual=capture();assert.throws(()=>verifyCanvasCapture({...actual,expected:f.expected,png:f.png,rgba:f.rgba}),/changed during capture/);
});

test('independent report verifier reopens all required states and rejects stale same-size raster and corrupted bindings',async()=>{
  const {verifyLiveCaptures}=await import('./verify-anchor-live-captures.mjs');
  const specs=[['ordinary-iframe-dpr2',800,600,2,-1,'ordinary iframe startup'],['fractional-dpr-clipped',322,713,1.25,-1,'fractional DPR and rounded backing store'],
    ['maximum-width-popup',4096,600,1,2,'maximum live width'],['restored-750-dpr1-3',750,600,1,-1,'restore original comparison profile'],
    ['restored-480-dpr1-4',480,600,1,-1,'restore original comparison profile'],['restored-750-dpr1-5',750,600,1,-1,'restore original comparison profile']];
  const report={status:'passed',image_kind:'canvas_export',composited_page_screenshots:false,states:[],inputs:[],captures:[]},files=new Map();
  for(const [name,width,height,scale,hovered,operation] of specs) {
    const dimensions=[Math.round(width*scale),Math.round(height*scale)],button={x:200,y:100,width:120,height:65},popup={x:300,y:200,width:100,height:27};
    const state={...fixture().before,width,height,scale,canvas:dimensions,canvasBounds:{x:0,y:0,width,height},metadata:{width,height},hostScale:scale,
      frame:{snapshot:{scale,items:[{id:12,bounds:button}]},anchor:{hovered:-1}}};
    report.states.push({operation,...structuredClone(state)});
    let samples=[];
    if(hovered===2) {
      state.frame.anchor.hovered=2;state.frame.snapshot.items.push({id:200,bounds:popup});report.inputs.push({operation:'maximum-width rightmost popup',frame:state.frame});
      samples=[{kind:'blank8',x:8,y:213.5,rgba:[255,255,255,255]},{kind:'blank64',x:64,y:213.5,rgba:[255,255,255,255]},
        {kind:'button',x:212,y:112,rgba:[0,0,0,255]},{kind:'popup',x:303,y:203,rgba:[53,53,53,255]}];
      report.shadow_probe={width,height,scale,samples};
    }
    const generated=spawnSync('python3',['-c','import io,json,sys,struct;from PIL import Image;w,h,points=json.load(sys.stdin);im=Image.new("RGBA",(w,h),(255,255,255,255));[(im.putpixel((int(p["x"]),int(p["y"])),tuple(p["rgba"]))) for p in points];out=io.BytesIO();im.save(out,format="PNG");b=out.getvalue();sys.stdout.buffer.write(struct.pack(">I",len(b))+b+im.tobytes())'],{input:JSON.stringify([...dimensions,samples]),maxBuffer:20*1024*1024});
    assert.equal(generated.status,0,String(generated.stderr));const length=generated.stdout.readUInt32BE(0),image=generated.stdout.subarray(4,4+length),raw=generated.stdout.subarray(4+length);
    const file=`${name}.canvas.png`,rawFile=`${name}.canvas.rgba`;files.set(file,image);files.set(rawFile,raw);
    report.captures.push({file,raw:rawFile,before:state,after:structuredClone(state),...verifyCanvasCapture({before:state,after:state,expected:state,png:image,rgba:raw,samples})});
  }
  assert.equal(verifyLiveCaptures(report,p=>files.get(p)).length,6);
  const wrong=structuredClone(report);wrong.captures[2].before=structuredClone(wrong.captures[2].before);wrong.captures[2].before.frame.anchor.hovered=-1;
  assert.throws(()=>verifyLiveCaptures(wrong,p=>files.get(p)),/differs from recorded/);
  const stale=png(4096,600,[255,255,255,255]);
  assert.throws(()=>verifyLiveCaptures(report,p=>p==='maximum-width-popup.canvas.png'?stale:files.get(p)),/stale same-size/);
  const renamed=structuredClone(report);renamed.captures[1].file=renamed.captures[0].file;
  assert.throws(()=>verifyLiveCaptures(renamed,p=>files.get(p)));
  const badSample=structuredClone(report);badSample.shadow_probe.samples[2].x=1;
  assert.throws(()=>verifyLiveCaptures(badSample,p=>files.get(p)));
});
