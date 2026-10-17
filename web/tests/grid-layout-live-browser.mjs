// Live-use regression only. No Rust comparison or parity claim outside the frozen profile.
import assert from 'node:assert/strict';
import {prepareHistoryDprProbe} from './grid-layout-live-history.mjs';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
assert(process.argv[2], 'Usage: grid-layout-live-browser.mjs candidate-site');
assert(process.env.PLAYWRIGHT_ROOT, 'PLAYWRIGHT_ROOT is required');
const site=resolve(process.argv[2]);
const out=resolve(process.env.BROWSER_EVIDENCE||'_build/grid-layout-live-evidence');
const require=createRequire(join(process.env.PLAYWRIGHT_ROOT,'package.json'));
const {chromium}=require('playwright');
assert.equal(require('playwright/package.json').version,'1.56.1');
const types={'.html':'text/html','.mjs':'text/javascript','.js':'text/javascript','.ttf':'font/ttf'};
const server=createServer(async(req,res)=>{
  try {
    const url=new URL(req.url,'http://localhost');
    if(url.pathname==='/away') { res.writeHead(200,{'content-type':'text/html'});res.end('<!doctype html><title>Away</title>Navigation lifecycle probe');return; }
    if(url.pathname==='/live-embed') {
      res.writeHead(200,{'content-type':'text/html'});
      res.end('<!doctype html><style>html,body{margin:0;width:100%;height:100%;overflow:hidden}iframe{width:100%;height:100%;border:0;display:block}</style><iframe src="/moonbit/?example=grid_layout"></iframe>');return;
    }
    let relative=decodeURIComponent(url.pathname).slice(1);if(relative.endsWith('/'))relative+='index.html';
    const file=resolve(site,relative);assert(file.startsWith(site+sep));
    const bytes=await readFile(file);res.writeHead(200,{'content-type':types[extname(file)]||'application/octet-stream'});res.end(bytes);
  }catch {res.writeHead(404);res.end('Not found');}
});
let browser, page, frame, attempted;
const errors=[];
const report={status:'failed',conformance:'not_claimed',kind:'live_embedded_candidate_regression',states:[]};
try {
  await mkdir(out,{recursive:true});
  await new Promise(done=>server.listen(0,'127.0.0.1',done));
  browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:800,height:600},deviceScaleFactor:2});
  page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/live-embed`);
  const iframe=await page.waitForSelector('iframe');frame=await iframe.contentFrame();
  let cdp=await context.newCDPSession(page);
  let restored;
  for(const [width,height,scale] of [[800,600,2],[320,713,1.25],[500,500,1],[399,500,1],[400,500,1],[800,600,2],[800,600,4],[800,600,5],[800,600,1],[8,32,1],[500,500,1]]) {
    attempted={width,height,scale};
    await cdp.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:scale,mobile:false});
    if(width<16 || scale>4) {
      await frame.waitForFunction(({width,height,scale})=>innerWidth===width&&innerHeight===height&&devicePixelRatio===scale&&document.documentElement.dataset.runtimeStatus==='failed',{width,height,scale});
      assert(await frame.evaluate(()=>document.querySelector('canvas').hidden && !document.getElementById('error').hidden && !globalThis.gpuiExample));
      report.states.push({width,height,scale,status:'deliberately_rejected'});continue;
    }
    await frame.waitForFunction(({width,height,scale})=>globalThis.gpuiExample?.metadata.width===width&&globalThis.gpuiExample?.metadata.height===height&&globalThis.gpuiExample?.scale===scale,{width,height,scale});
    const state=await frame.evaluate(()=>({width:innerWidth,height:innerHeight,scale:devicePixelRatio,status:document.documentElement.dataset.runtimeStatus,canvas:[document.querySelector('canvas').width,document.querySelector('canvas').height],hidden:document.querySelector('canvas').hidden,noticeHidden:document.getElementById('grid-live-notice').hidden,frame:globalThis.gpuiExample.frame}));
    assert.equal(state.status,'ready');assert.equal(state.hidden,false);
    assert.deepEqual(state.canvas,[Math.round(width*scale),Math.round(height*scale)]);
    const match=[399,400,401,500].includes(width)&&height===500&&scale===1;
    assert.equal(state.frame.grid_layout.comparison_profile_match,match);assert.equal(state.noticeHidden,match);
    assert.equal(state.frame.conformance,'unverified');
    assert.equal(state.frame.grid_layout.mode,width<400?'stack':'grid');
    if(width===500&&height===500&&scale===1) {
      assert.deepEqual(state.frame.grid_layout.blocks.map(b=>Object.values(b.bounds)),[[0,0,500,97],[0,101,97,224],[101,101,298,298],[403,101,97,298],[0,403,500,97]]);
      if(restored)assert.deepEqual(state.frame,restored);else restored=state.frame;
    }
    report.states.push(state);
  }
  await page.screenshot({path:join(out,'restored-original-profile.png')});
  // Real history navigation may restore BFCache or reload, depending on Chromium
  // policy. Record which happened; neither path may lose DPR observation.
  await frame.evaluate(()=>{globalThis.liveGridHistoryMarker=true;});
  attempted={operation:'observe_history_return'};
  await page.goto(`http://127.0.0.1:${server.address().port}/away`);
  await page.goBack();
  frame=await (await page.waitForSelector('iframe')).contentFrame();
  const historyProbe=await prepareHistoryDprProbe({frame,page,context,cdp,restored,onAttempt:state=>{attempted=state;}});
  cdp=historyProbe.cdp;report.history=historyProbe.history;
  attempted={operation:'history_return_same_size_dpr',width:500,height:500,scale:2};
  await cdp.send('Emulation.setDeviceMetricsOverride',{width:500,height:500,deviceScaleFactor:2,mobile:false});
  await frame.waitForFunction(()=>globalThis.gpuiExample?.metadata.width===500&&globalThis.gpuiExample?.scale===2);
  assert(await frame.evaluate(()=>document.documentElement.dataset.runtimeStatus==='ready'&&document.querySelector('canvas').width===1000&&!document.querySelector('canvas').hidden));
  report.history.same_size_dpr_after_return='passed';
  assert.deepEqual(errors,[]);report.status='passed';report.browser=await browser.version();
} catch (error) {
  report.failure={attempted,error:{name:error.name,message:error.message},page_errors:errors};
  if(frame) {
    try {
      report.failure.observed=await frame.evaluate(()=>({width:innerWidth,height:innerHeight,scale:devicePixelRatio,status:document.documentElement.dataset.runtimeStatus,error:document.getElementById('error')?.textContent,errorHidden:document.getElementById('error')?.hidden,canvasHidden:document.querySelector('canvas')?.hidden,example:globalThis.gpuiExample||null}));
    } catch (captureError) {report.failure.observation_error=captureError.message;}
  }
  throw error;
} finally {
  await writeFile(join(out,'live-regression.json'),JSON.stringify(report,null,2)+'\n');
  await browser?.close();await new Promise(done=>server.close(done));
}
console.log('Live embedded grid resize/DPR regression passed; no parity claim.');
