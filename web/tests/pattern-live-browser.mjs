// Candidate-only live rendering regression; never a Rust parity qualification.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {readFile,mkdir,writeFile,readdir} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {createHash} from 'node:crypto';
assert.equal(process.argv.length,4,'Usage: node pattern-live-browser.mjs built-site fresh-evidence-directory');
const [site,out]=process.argv.slice(2).map(p=>resolve(p));
await mkdir(out,{recursive:true});assert.equal((await readdir(out)).length,0);
const hash=b=>createHash('sha256').update(b).digest('hex');
const require=createRequire(join(resolve(process.env.PLAYWRIGHT_ROOT),'package.json'));
assert.equal(require('playwright/package.json').version,'1.56.1');
const {chromium}=require('playwright');
const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.ttf':'font/ttf'};
const server=createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://localhost');if(url.pathname==='/favicon.ico'){res.writeHead(204);res.end();return;}
 const path=resolve(site,'.'+decodeURIComponent(url.pathname)+(url.pathname.endsWith('/')?'index.html':''));assert(path.startsWith(site+sep));
 res.writeHead(200,{'content-type':mime[extname(path)]||'application/octet-stream','cache-control':'no-store','Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp'});res.end(await readFile(path));
}catch{res.writeHead(404);res.end();}});
await new Promise(done=>server.listen(0,'127.0.0.1',done));
const report={status:'failed',scope:'candidate_live_rendering_only',parity:'unverified',stages:[],errors:[]};let browser;
try{
 const build=await readFile(join(site,'build-manifest.json'));await writeFile(join(out,'build-manifest.json'),build);report.build_sha256=hash(build);
 browser=await chromium.launch({headless:true});report.browser=await browser.version();
 const context=await browser.newContext({viewport:{width:801,height:700},deviceScaleFactor:1.25});const page=await context.newPage();
 page.on('pageerror',e=>report.errors.push(e.message));
 await page.goto(`http://127.0.0.1:${server.address().port}/moonbit/?example=pattern`);
 const cdp=await context.newCDPSession(page);
 async function capture(name,w,h,dpr){
  await page.waitForFunction(({w,h,dpr})=>document.documentElement.dataset.runtimeStatus==='ready'&&globalThis.gpuiExample?.metadata.width===w&&gpuiExample.metadata.height===h&&gpuiExample.actualDeviceScale===dpr,{w,h,dpr},{timeout:60000});
  const state=await page.evaluate(()=>{
   const e=gpuiExample,c=document.querySelector('canvas'),pixels=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
   let colored=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i+3]>0&&(pixels[i]!==pixels[i+1]||pixels[i+1]!==pixels[i+2]))colored++;
   return {width:innerWidth,height:innerHeight,dpr:devicePixelRatio,backing:[c.width,c.height],scale:e.scale,actualDeviceScale:e.actualDeviceScale,reduced:e.renderScaleReduced,qualified:e.frame.pattern.comparison_profile_match,conformance:e.frame.conformance,root:e.frame.snapshot.items.find(i=>i.id===1)?.bounds,colored,noticeHidden:document.querySelector('#pattern-live-notice').hidden,hidden:c.hidden,errorHidden:document.querySelector('#error').hidden};
  });
  assert.equal(state.width,w);assert.equal(state.height,h);assert.equal(state.dpr,dpr);
  assert.deepEqual(state.backing,[Math.ceil(w*state.scale),Math.ceil(h*state.scale)]);
  assert(state.backing[0]*state.backing[1]<=1048576);assert(state.backing.every(n=>n<=2048));
  assert.equal(state.qualified,w===600&&h===600&&dpr===1);assert.equal(state.conformance,'unverified');assert.equal(state.noticeHidden,state.qualified);
  assert.equal(state.hidden,false);assert(state.errorHidden);assert(state.colored>50,'actual colored candidate pixels required');
  assert.equal(state.root.width,600);assert.equal(state.root.height,600);
  const file=`${name}.png`,bytes=await page.screenshot();await writeFile(join(out,file),bytes);report.stages.push({name,state,file,sha256:hash(bytes)});
 }
 await capture('embedded-fractional',801,700,1.25);
 await page.setViewportSize({width:321,height:479});await capture('narrow-clipped',321,479,1.25);
 await cdp.send('Emulation.setDeviceMetricsOverride',{width:321,height:479,deviceScaleFactor:2,mobile:false});await capture('dpr-only',321,479,2);
 await cdp.send('Emulation.setDeviceMetricsOverride',{width:801,height:701,deviceScaleFactor:2,mobile:false});await capture('fractional-root-boundary',801,701,2);
 await cdp.send('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:3,mobile:false});await capture('budget-reduced',1280,900,3);assert(report.stages.at(-1).state.reduced);
 await cdp.send('Emulation.setDeviceMetricsOverride',{width:2049,height:700,deviceScaleFactor:1,mobile:false});
 await page.waitForFunction(()=>document.documentElement.dataset.runtimeStatus==='failed'&&!globalThis.gpuiExample&&document.querySelector('canvas').hidden);
 report.unsafeRejected=true;
 await cdp.send('Emulation.setDeviceMetricsOverride',{width:600,height:600,deviceScaleFactor:1,mobile:false});await capture('qualified-recovery',600,600,1);
 // Synthetic lifecycle events test invalidation only, not actual browser BFCache.
 await page.evaluate(()=>dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true})));
 assert(await page.evaluate(()=>!globalThis.gpuiExample&&document.querySelector('canvas').hidden));
 await page.evaluate(()=>dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));await capture('synthetic-pageshow-recovery',600,600,1);
 assert.deepEqual(report.errors,[]);report.status='pass';
}finally{await writeFile(join(out,'result.json'),JSON.stringify(report,null,2));await browser?.close();await new Promise(done=>server.close(done));}
