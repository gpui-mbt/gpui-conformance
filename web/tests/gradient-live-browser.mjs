// Actual Chromium usability only; separate from frozen pair/policy acceptance.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {createHash} from 'node:crypto';
assert.equal(process.argv.length,3,'Usage: gradient-live-browser.mjs candidate-site');
assert(process.env.PLAYWRIGHT_ROOT);
const site=resolve(process.argv[2]),out=resolve(process.env.BROWSER_EVIDENCE||'_build/gradient-live-evidence');
const require=createRequire(join(process.env.PLAYWRIGHT_ROOT,'package.json')),{chromium}=require('playwright');
assert.equal(require('playwright/package.json').version,'1.56.1');
const hash=b=>createHash('sha256').update(b).digest('hex');
const report={status:'failed',kind:'actual_compiled_live_usability',conformance:'not_claimed',frozen_pair_profile_extended:false,states:[],inputs:[],errors:[]};
const types={'.html':'text/html','.mjs':'text/javascript','.js':'text/javascript','.ttf':'font/ttf'};
const server=createServer(async(req,res)=>{try{const u=new URL(req.url,'http://localhost');if(u.pathname==='/favicon.ico'){res.writeHead(204);res.end();return;}let relative=decodeURIComponent(u.pathname).slice(1);if(relative.endsWith('/'))relative+='index.html';const file=resolve(site,relative);assert(file.startsWith(site+sep));const bytes=await readFile(file);res.writeHead(200,{'content-type':types[extname(file)]||'application/octet-stream','cache-control':'no-store'});res.end(bytes);}catch{res.writeHead(404);res.end('Not found');}});
let browser,page,cdp;
await mkdir(out,{recursive:true});
async function metrics(width,height,deviceScaleFactor){await cdp.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor,mobile:false});}
async function capture(name,width,height,dpr){
 await page.waitForFunction(({width,height,dpr})=>{const e=globalThis.gpuiExample;return document.documentElement.dataset.runtimeStatus==='ready'&&innerWidth===width&&innerHeight===height&&devicePixelRatio===dpr&&e?.actualDeviceScale===dpr&&e.metadata.width===width&&e.metadata.height===height;},{width,height,dpr});
 const s=await page.evaluate(()=>{const e=globalThis.gpuiExample,c=document.querySelector('canvas'),n=document.getElementById('gradient-live-notice');return {width:innerWidth,height:innerHeight,actualDeviceScale:devicePixelRatio,effectiveRenderScale:e.effectiveRenderScale,backingWidth:c.width,backingHeight:c.height,reduced:e.renderScaleReduced,profile:e.frame.gradient.comparison_profile_match,color:e.frame.gradient.color_space,notice:n.textContent,noticeHidden:n.hidden,button:e.frame.snapshot.items.find(i=>i.id===3).shape.bounds,png:c.toDataURL('image/png'),events:e.gradientEvents};});
 assert.equal(s.actualDeviceScale,dpr);assert.ok(s.backingWidth<=2048&&s.backingHeight<=2048&&s.backingWidth*s.backingHeight<=1048576);assert.equal(s.backingWidth,Math.ceil(width*s.effectiveRenderScale));assert.equal(s.backingHeight,Math.ceil(height*s.effectiveRenderScale));assert.equal(s.profile,dpr===1&&((width===960&&height===600)||(width===600&&height===960)));assert.equal(s.noticeHidden,s.profile);if(s.reduced)assert.match(s.notice,/resolution reduced/);
 const png=Buffer.from(s.png.split(',')[1],'base64');delete s.png;const file=name+'.png';await writeFile(join(out,file),png);s.capture={file,sha256:hash(png),bytes:png.length};report.states.push({name,...s});return s;
}
try{
 const bytes=await readFile(join(site,'build-manifest.json'));report.build_manifest_sha256=hash(bytes);await writeFile(join(out,'build-manifest.json'),bytes);
 await new Promise(r=>server.listen(0,'127.0.0.1',r));browser=await chromium.launch({headless:true});report.browser=browser.version();const context=await browser.newContext({viewport:{width:960,height:600},deviceScaleFactor:1});page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));cdp=await context.newCDPSession(page);
 await page.goto(`http://127.0.0.1:${server.address().port}/moonbit/?example=gradient`);await page.evaluate(()=>document.fonts.ready);const first=await capture('paired-before',960,600,1);
 for(const dpr of [2,1.25,4]){await metrics(800,600,dpr);const s=await capture('live-'+dpr,800,600,dpr);await page.mouse.click(s.button.x+2,s.button.y+2);await page.waitForFunction(()=>globalThis.gpuiExample.frame.gradient.color_space==='Oklab');await page.mouse.click(s.button.x+2,s.button.y+2);await page.waitForFunction(()=>globalThis.gpuiExample.frame.gradient.color_space==='sRGB');const restored=await capture('live-restored-'+dpr,800,600,dpr);assert.equal(restored.capture.sha256,s.capture.sha256);assert.ok(restored.events.slice(-2).every(e=>e.trusted));report.inputs.push(...restored.events.slice(-2));}
 await metrics(200,600,2);await page.waitForFunction(()=>document.documentElement.dataset.runtimeStatus==='failed'&&!globalThis.gpuiExample);report.invalid_rejected=true;
 await metrics(960,600,1);const last=await capture('paired-recovered',960,600,1);assert.equal(last.capture.sha256,first.capture.sha256);assert.deepEqual(report.errors,[]);report.status='passed';
}catch(error){report.failure={message:error.message,stack:error.stack};process.exitCode=1;}finally{await writeFile(join(out,'gradient-live-result.json'),JSON.stringify(report,null,2)+'\n');await browser?.close();await new Promise(r=>server.close(r));}
