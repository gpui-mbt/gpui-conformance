// Two independent browser processes consume the actual compiled-core output.
// Host assertions do not fabricate scene geometry or inherited opacity.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {readFile,mkdir,writeFile,readdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
assert.equal(process.argv.length,5,'Usage: capture.mjs suite-root actual-core-output.json fresh-output');
const [root,input,out]=process.argv.slice(2).map(p=>resolve(p));
const inputBytes=await readFile(input), core=JSON.parse(inputBytes);
assert.equal(core.backend,'actual-moonbit-core');assert(core.run_token);
assert.deepEqual(core.cases.map(c=>c.case),['original_png_nested','original_png_clipped','portrait_contain','painter_order']);
await mkdir(out,{recursive:true});assert.equal((await readdir(out)).length,0);
const sha=b=>createHash('sha256').update(b).digest('hex');
assert(process.env.PLAYWRIGHT_ROOT,'PLAYWRIGHT_ROOT required');
const require=createRequire(join(resolve(process.env.PLAYWRIGHT_ROOT),'package.json'));
assert.equal(require('playwright/package.json').version,'1.56.1');
const {chromium}=require('playwright');
const files=new Map();
for(const [url,path,mime] of [['/render.mjs','web/moonbit/site/render.mjs','text/javascript'],['/image-resources.mjs','web/moonbit/site/image-resources.mjs','text/javascript'],['/icon.png','assets/app-icon.png','image/png'],['/portrait.png','assets/portrait.png','image/png']]) {
 const bytes=await readFile(join(root,path));files.set(url,{bytes,mime});
 await writeFile(join(out,path.replaceAll('/','-')),bytes);
}
files.set('/frames.json',{bytes:inputBytes,mime:'application/json'});
const html=`<!doctype html><meta charset="utf-8"><canvas width="160" height="120"></canvas><script type="module">
import {drawFrame} from '/render.mjs';import {prepareImageResources} from '/image-resources.mjs';
window.captureCase=async(index,control)=>{
 const source=await(await fetch('/frames.json')).json(),frame=source.cases[index].frame;
 const encoded=new Map();for(const r of frame.snapshot.resources)encoded.set(r.id,new Uint8Array(await(await fetch(r.id===1?'/icon.png':'/portrait.png')).arrayBuffer()));
 if(control==='wrong_resource')encoded.set(frame.snapshot.resources[0].id,new Uint8Array(await(await fetch('/portrait.png')).arrayBuffer()));
 const prepared=await prepareImageResources(frame.snapshot.resources,encoded);
 if(control==='omit')frame.snapshot.items=frame.snapshot.items.filter(i=>i.kind!=='image');
 if(control==='double_alpha')for(const i of frame.snapshot.items)if(i.kind==='image')i.opacity*=i.opacity;
 if(control==='ignore_alpha')for(const i of frame.snapshot.items)if(i.kind==='image')i.opacity=1;
 if(control==='stretch')for(const i of frame.snapshot.items)if(i.kind==='image')i.bounds={...i.image_bounds};
 if(control==='missing_resource'){frame.snapshot.resources=[];frame.snapshot.items.unshift({kind:'quad',id:999,bounds:{x:0,y:0,width:160,height:120},color:{red:255,green:0,blue:0,alpha:255},opacity:1});}
 const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');
 ctx.fillStyle='#ca3197';ctx.fillRect(0,0,160,120);const before=[...ctx.getImageData(0,0,160,120).data];
 const destinationCalls=[];const destination=new Proxy(ctx,{get:(target,key)=>{const value=Reflect.get(target,key,target);return typeof value==='function'?(...args)=>{destinationCalls.push(String(key));return value.apply(target,args);}:value;},set:(target,key,value)=>Reflect.set(target,key,value,target)});
 try {drawFrame(destination,frame,{width:160,height:120},1,prepared);}catch(error){const after=ctx.getImageData(0,0,160,120).data;return {error:String(error),destination_calls:destinationCalls,unchanged:before.every((v,i)=>v===after[i])};}
 return {pixels:[...ctx.getImageData(0,0,160,120).data],frame,run_token:source.run_token,device_scale:window.devicePixelRatio};
};window.ready=true;
</script>`;
files.set('/',{bytes:Buffer.from(html),mime:'text/html'});
const server=createServer((req,res)=>{const f=files.get(req.url);if(!f){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',f.mime);res.end(f.bytes);});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const origin=`http://127.0.0.1:${server.address().port}`;
const alpha=(p,x,y)=>p[(y*160+x)*4+3];
function check(result,index) {
 assert(!result.error);assert.equal(result.device_scale,1);const p=result.pixels;assert.equal(p.length,160*120*4);
 if(index===3){
   assert.deepEqual(result.frame.snapshot.items.map(i=>i.kind),['quad','image','quad','image']);
   const at=(x,c)=>p[(16*160+x)*4+c];
   assert(Math.abs(at(16,3)-159)<=1);assert.equal(at(48,3),255);
   for(let c=0;c<3;c++)assert(Math.abs(at(16,c)-(at(48,c)*.4+(c===0?153:0)))<=2,'ordered source-over compositing');
 } else if(index===2){assert.equal(alpha(p,24,50),0);assert.equal(alpha(p,25,50),255);assert.equal(alpha(p,74,50),255);assert.equal(alpha(p,75,50),0);}
 else {
   const x=index===0?32:20;
   let opaque=0;
   for(let yy=0;yy<32;yy++)for(let xx=0;xx<(index===0?32:20);xx++) {
    const a=alpha(p,xx,yy),b=alpha(p,xx+x,yy);
    assert(Math.abs(a-b*.25)<=1,'inherited alpha is applied exactly once');
    if(b>200)opaque++;
   }
   assert(opaque>10,'original PNG is visibly present');
   assert.equal(alpha(p,x,0),0,'original PNG transparent corner preserved');
   assert.equal(alpha(p,x+31,31),0,'original PNG opposite transparent corner preserved');
   let partial=0;for(let yy=0;yy<32;yy++)for(let xx=0;xx<32;xx++){const a=alpha(p,x+xx,yy);if(a>0&&a<255)partial++;}
   assert(partial>0,'original PNG partial intrinsic alpha preserved');
   result.intrinsic_alpha={opaque_samples:opaque,partial_samples:partial,transparent_corners:2};
   assert.equal(alpha(p,x+32,16),0,'sibling extent');
 }
}
const report={status:'running',input_sha256:sha(inputBytes),core_run_token:core.run_token,captures:[],controls:[]};
try {
 for(let run=0;run<2;run++) {
  const browser=await chromium.launch({headless:true});
  try {
   const page=await browser.newPage({viewport:{width:160,height:120},deviceScaleFactor:1});await page.goto(origin);await page.waitForFunction(()=>window.ready);
   const token=randomUUID();
   for(let index=0;index<4;index++) {
    const actual=await page.evaluate(i=>window.captureCase(i),index);check(actual,index);
    const stem=`run-${run}-${core.cases[index].case}`;
    await writeFile(join(out,stem+'.json'),JSON.stringify(actual));await page.locator('canvas').screenshot({path:join(out,stem+'.png')});
    report.captures.push({run,case:core.cases[index].case,token,browser:browser.version(),device_scale:actual.device_scale,intrinsic_alpha:actual.intrinsic_alpha,pixels_sha256:sha(Buffer.from(actual.pixels)),png:stem+'.png'});
   }
   if(run===0)for(const [control,index] of [['omit',0],['double_alpha',0],['ignore_alpha',0],['stretch',2],['missing_resource',0],['wrong_resource',0]]) {
    let actual,error;try{actual=await page.evaluate(([i,c])=>window.captureCase(i,c),[index,control]);}catch(e){error=String(e);}
    if(control==='wrong_resource')assert(error&&/dimensions|identity/.test(error));
    else if(control==='missing_resource'){assert(actual.error);assert.equal(actual.unchanged,true);assert.deepEqual(actual.destination_calls,[]);}
    else assert.throws(()=>check(actual,index));
    report.controls.push({control,index,rejected:true,destination_calls:actual?.destination_calls,unchanged:actual?.unchanged,error:error||actual?.error||'pixel acceptance rejected'});
   }
  } finally {await browser.close();}
 }
 report.status='passed-bounded-browser-image-proof';
} finally {await writeFile(join(out,'report.json'),JSON.stringify(report,null,2));await new Promise(r=>server.close(r));}
