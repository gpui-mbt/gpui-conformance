// Actual paired viewport plumbing. Does not qualify cross-runtime pixel parity.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
const site=resolve(process.argv[2]);
const out=resolve(process.argv[3]);await mkdir(out,{recursive:true});
const require=createRequire(join(process.env.PLAYWRIGHT_ROOT,'package.json'));
assert.equal(require('playwright/package.json').version,'1.56.1');const {chromium}=require('playwright');
const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.ttf':'font/ttf','.wasm':'application/wasm'};
const server=createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://localhost');const file=resolve(site,'.'+decodeURIComponent(url.pathname)+(url.pathname.endsWith('/')?'index.html':''));assert(file.startsWith(site+sep));
 res.writeHead(200,{'content-type':mime[extname(file)]||'application/octet-stream','Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp'});res.end(await readFile(file));
}catch{res.writeHead(404);res.end();}});
await new Promise(done=>server.listen(0,'127.0.0.1',done));
const report={status:'failed',scope:'actual_paired_viewport_resize_only',parity:'unverified',states:[],errors:[],build:JSON.parse(await readFile(join(site,'build-manifest.json'),'utf8'))};let browser;
try{
 assert(report.build.rust_bundled);
 for(const dpr of [1,2]){
  browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist',`--force-device-scale-factor=${dpr}`]});
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:dpr});page.on('pageerror',e=>report.errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/?example=grid_layout`);
  let urls;
  for(const [width,height] of [[1440,1000],[390,844],[844,390],[1280,900]]){
   await page.setViewportSize({width,height});
   await page.waitForFunction(dpr=>{
    const frames=['rust','moon'].map(s=>document.getElementById(s+'-frame'));
    const panes=document.querySelector('.panes'),style=getComputedStyle(panes),stacked=innerWidth<=720;
    const headers=[...panes.querySelectorAll('.pane-head')].map(n=>n.getBoundingClientRect().height+2);
    const expectedWidth=Math.max(16,Math.floor(Math.min(...frames.map(f=>f.parentElement.clientWidth))));
    const expectedHeight=Math.max(160,Math.floor((innerHeight-Math.max(0,panes.getBoundingClientRect().top)-parseFloat(style.paddingTop)-parseFloat(style.paddingBottom)-(stacked?headers.reduce((a,b)=>a+b,0):Math.max(...headers))-(stacked?parseFloat(style.rowGap):0))/(stacked?2:1)));
    return frames.every(f=>parseInt(f.style.width)===expectedWidth&&parseInt(f.style.height)===expectedHeight)&&frames.every(f=>{const w=f.contentWindow,c=f.contentDocument?.querySelector('canvas');return w&&w.location.href===f.src&&w.innerWidth===parseInt(f.style.width)&&w.innerHeight===parseInt(f.style.height)&&w.devicePixelRatio===dpr&&c&&c.width===Math.round(w.innerWidth*dpr)&&c.height===Math.round(w.innerHeight*dpr);})&&frames[0].contentDocument.documentElement.dataset.runtimeStatus==='initialized'&&frames[1].contentDocument.documentElement.dataset.runtimeStatus==='ready'&&frames[1].contentWindow.gpuiExample?.metadata.width===frames[1].contentWindow.innerWidth&&frames[1].contentWindow.gpuiExample?.metadata.height===frames[1].contentWindow.innerHeight;
   },dpr,{timeout:90000});
   const state=await page.evaluate(()=>({parent:[innerWidth,innerHeight],overflow:document.documentElement.scrollWidth>innerWidth,panes:['rust','moon'].map(s=>{const f=document.getElementById(s+'-frame'),w=f.contentWindow,c=f.contentDocument.querySelector('canvas');return {src:f.src,timeOrigin:w.performance.timeOrigin,containerWidth:f.parentElement.clientWidth,width:w.innerWidth,height:w.innerHeight,dpr:w.devicePixelRatio,backing:[c.width,c.height],x:f.getBoundingClientRect().x,y:f.getBoundingClientRect().y};}),candidate:document.getElementById('moon-frame').contentWindow.gpuiExample.frame}));
   const [r,m]=state.panes;assert.deepEqual([r.width,r.height,r.dpr],[m.width,m.height,m.dpr]);assert(!state.overflow);
   if(width<=720){assert.equal(r.x,m.x);assert(m.y>r.y);assert(r.width<400,'narrow parent must reach the grid stack breakpoint');}else {assert(r.x<m.x);assert.equal(r.y,m.y);}
   assert.equal(state.candidate.grid_layout.mode,r.width<400?'stack':'grid');assert.equal(state.candidate.conformance,'unverified');
   assert.equal(r.width,Math.floor(Math.min(r.containerWidth,m.containerWidth)));
   const next=state.panes.map(p=>[p.src,p.timeOrigin]);if(urls)assert.deepEqual(next,urls,'resize must not reload either runtime');else urls=next;
   report.states.push({dpr,width,height,...state});await page.screenshot({path:join(out,`${width}-${height}-dpr${dpr}.png`),fullPage:true});
  }
  // Leaving the responsive example restores the original fixed-size contract.
  await page.selectOption('#fixture','hello_world');
  await page.waitForFunction(()=>!document.body.classList.contains('live-grid')&&['rust','moon'].every(s=>{const f=document.getElementById(s+'-frame');return f.style.width==='500px'&&f.style.height==='500px';}));
  await browser.close();browser=null;
 }
 assert.deepEqual(report.errors,[]);report.status='passed';
}finally{await writeFile(join(out,'result.json'),JSON.stringify(report,null,2));await browser?.close();await new Promise(done=>server.close(done));}
