// Actual Chromium live-use regression only. This neither compares Rust nor
// extends the frozen 750/480x600 DPR1 comparison profile or its expectations.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {validateFrame} from '../moonbit/site/render.mjs';

assert.equal(process.argv.length,3,'Usage: anchor-live-browser.mjs candidate-site');
assert(process.env.PLAYWRIGHT_ROOT,'PLAYWRIGHT_ROOT is required');
const site=resolve(process.argv[2]);
const out=resolve(process.env.BROWSER_EVIDENCE||'_build/anchor-live-evidence');
const require=createRequire(join(process.env.PLAYWRIGHT_ROOT,'package.json'));
const {chromium}=require('playwright');
assert.equal(require('playwright/package.json').version,'1.56.1');
const types={'.html':'text/html','.mjs':'text/javascript','.js':'text/javascript','.ttf':'font/ttf'};
const server=createServer(async(req,res)=>{
  try {
    const url=new URL(req.url,'http://localhost');
    if(url.pathname==='/favicon.ico') {res.writeHead(204);res.end();return;}
    if(url.pathname==='/away') {
      res.writeHead(200,{'content-type':'text/html'});
      res.end('<!doctype html><title>Away</title>Navigation lifecycle probe');return;
    }
    if(url.pathname==='/live-embed') {
      res.writeHead(200,{'content-type':'text/html'});
      res.end('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body{margin:0;width:100%;height:100%;overflow:hidden}iframe{width:100%;height:100%;border:0;display:block}</style><iframe title="Live anchor candidate" src="/moonbit/?example=anchor"></iframe>');return;
    }
    let relative=decodeURIComponent(url.pathname).slice(1);
    if(relative.endsWith('/'))relative+='index.html';
    const file=resolve(site,relative);assert(file.startsWith(site+sep));
    res.writeHead(200,{'content-type':types[extname(file)]||'application/octet-stream'});
    res.end(await readFile(file));
  }catch {res.writeHead(404);res.end('Not found');}
});
const report={status:'failed',conformance:'not_claimed',kind:'live_embedded_candidate_regression',
  comparison_profile:'unchanged: 750/480x600 DPR1; no parity claim from this test',states:[],inputs:[]};
const errors=[];
let browser,page,frame,context,cdp,attempted;
const q=(state,id)=>state.frame.snapshot.items.find(item=>item.id===id);
const metrics=(width,height,scale)=>({width,height,scale});
const profileMatch=({width,height,scale})=>[750,480].includes(width)&&height===600&&scale===1;
const originals=new Map();
await mkdir(out,{recursive:true});

async function observe() {
  return frame.evaluate(()=>{
    const canvas=document.querySelector('canvas'),error=document.getElementById('error');
    const notice=document.getElementById('anchor-live-notice');
    const example=globalThis.gpuiExample;
    const rect=canvas.getBoundingClientRect();
    return {width:innerWidth,height:innerHeight,scale:devicePixelRatio,status:document.documentElement.dataset.runtimeStatus,
      canvas:[canvas.width,canvas.height],canvasBounds:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},canvasHidden:canvas.hidden,
      errorHidden:error.hidden,error:error.textContent,noticeHidden:notice?.hidden,notice:notice?.textContent,
      metadata:example?.metadata,frame:example?.frame,hostScale:example?.scale,
      document_id:globalThis.anchorLiveProbe.document_id,lifecycle:globalThis.anchorLiveProbe.lifecycle};
  });
}

async function waitReady(expected) {
  await frame.waitForFunction(expected=>{
    const e=globalThis.gpuiExample;
    return document.documentElement.dataset.runtimeStatus==='ready'&&
      e?.metadata.width===innerWidth&&e?.metadata.height===innerHeight&&e?.scale===devicePixelRatio&&
      (!expected||(innerWidth===expected.width&&innerHeight===expected.height&&devicePixelRatio===expected.scale));
  },expected,{timeout:30000});
  const state=await observe();assertReady(state,expected);return state;
}

function assertReady(state,expected) {
  if(expected)for(const name of ['width','height','scale'])assert.equal(state[name],expected[name],name);
  assert.equal(state.status,'ready');assert.equal(state.canvasHidden,false);assert.equal(state.errorHidden,true);
  assert.deepEqual(state.canvas,[Math.round(state.width*state.scale),Math.round(state.height*state.scale)]);
  assert.deepEqual(state.canvasBounds,{x:0,y:0,width:state.width,height:state.height});
  assert.equal(state.metadata.width,state.width);assert.equal(state.metadata.height,state.height);assert.equal(state.hostScale,state.scale);
  validateFrame(state.frame);
  // Core layout snaps the viewport to physical pixels (including its own
  // half-pixel rule); the CSS viewport and rounded backing store stay actual.
  const viewport=state.frame.snapshot.viewport;
  assert.equal(viewport.x,0);assert.equal(viewport.y,0);
  for(const name of ['width','height']) {
    assert(Math.abs(viewport[name]-state[name])<=1/state.scale+1e-6);
    assert(Math.abs(viewport[name]*state.scale-Math.round(viewport[name]*state.scale))<1e-6);
  }
  assert.equal(state.frame.snapshot.scale,state.scale,'The actual core snapshot must carry live DPR');
  assert.equal(state.frame.anchor.comparison_profile_match,profileMatch(state));
  assert.equal(state.noticeHidden,profileMatch(state));
  if(!profileMatch(state))assert.match(state.notice,/unverified/i);
  assert.equal(state.frame.conformance,'unverified');
  assert.equal(state.frame.decorations.length,8);assert.equal(q(state,104),undefined,'Center has no label or hover behavior');
}

async function setMetrics(expected,label) {
  attempted={operation:label,...expected};
  await cdp.send('Emulation.setDeviceMetricsOverride',{
    width:expected.width,height:expected.height,deviceScaleFactor:expected.scale,mobile:false,
  });
  const state=await waitReady(expected);
  report.states.push({operation:label,...state});return state;
}

async function clearPointer() {
  // Real browser input outside the iframe triggers pointerleave. Never call
  // runtime exports, dispatchEvent, or synthetic resize/pointer handlers here.
  await page.mouse.move(-10,-10);
  await frame.waitForFunction(()=>globalThis.gpuiExample?.frame.anchor.hovered===-1);
  const state=await waitReady();
  assert.equal(q(state,200),undefined);assert.equal(state.frame.anchor.layout_passes,1);
  return state;
}

function visibleBounds(state,item) {
  let left=Math.max(0,item.bounds.x),top=Math.max(0,item.bounds.y);
  let right=Math.min(state.width,item.bounds.x+item.bounds.width),bottom=Math.min(state.height,item.bounds.y+item.bounds.height);
  const chain=state.frame.snapshot.clip_chains.find(clip=>clip.id===item.clip_chain_id);
  for(const clip of chain?.rects||[]) {
    left=Math.max(left,clip.x);top=Math.max(top,clip.y);
    right=Math.min(right,clip.x+clip.width);bottom=Math.min(bottom,clip.y+clip.height);
  }
  return {x:left,y:top,width:Math.max(0,right-left),height:Math.max(0,bottom-top)};
}

async function hover(state,index,label) {
  const button=q(state,index+10),visible=visibleBounds(state,button);
  assert(visible.width>2&&visible.height>2,`${label}: requested button must actually be visible`);
  const target={x:visible.x+visible.width/2,y:visible.y+visible.height/2};
  const start=await frame.evaluate(()=>globalThis.anchorLiveProbe.pointer_events.length);
  attempted={operation:label,index,target,width:state.width,height:state.height,scale:state.scale};
  await page.mouse.move(target.x,target.y);
  await frame.waitForFunction(({start,index})=>globalThis.anchorLiveProbe.pointer_events.length>start&&
    globalThis.gpuiExample?.frame.anchor.hovered===(index===4?-1:index),{start,index});
  const events=await frame.evaluate(start=>globalThis.anchorLiveProbe.pointer_events.slice(start),start);
  const delivered=events.findLast(event=>event.type==='pointermove');
  assert(delivered?.trusted&&delivered.target==='CANVAS'&&delivered.pointerType==='mouse');
  assert(Math.abs(delivered.x-target.x)<0.01&&Math.abs(delivered.y-target.y)<0.01);
  const result=await waitReady(metrics(state.width,state.height,state.scale));
  assert.deepEqual(q(result,index+10).bounds,button.bounds,'Hover cannot move its core-laid-out button');
  const popup=q(result,200);
  if(index===4) {
    assert.equal(popup,undefined);assert.equal(result.frame.anchor.layout_passes,1);
  }else {
    assert.equal(result.frame.anchor.layout_passes,2);
    assert.deepEqual(q(result,index+10).color,{red:0,green:0,blue:0,alpha:255});
    assert(popup,'Trusted hover must create the actual deferred popup');
    assert.equal(popup.color.alpha,191);
    assert.equal(q(result,201).text,result.metadata.runs[index+1].text);
    assert.deepEqual(result.frame.shadows,[{id:200,kind:'shadow_sm'}]);
    assert(result.frame.snapshot.items.indexOf(popup)>result.frame.snapshot.items.findIndex(item=>item.id===108));
    // Standard live sizes can contain the measured popup. Tiny viewports may
    // legitimately clip it, so containment is conditional on its actual size.
    if(popup.bounds.width<=state.width&&popup.bounds.height<=state.height) {
      const b=popup.bounds,tolerance=1/state.scale+1e-6;
      assert(b.x>=-tolerance&&b.y>=-tolerance&&b.x+b.width<=state.width+tolerance&&b.y+b.height<=state.height+tolerance);
    }
    assert(visibleBounds(result,popup).width>0&&visibleBounds(result,popup).height>0);
  }
  report.inputs.push({operation:label,index,target,events,button:button.bounds,visible,popup:popup?.bounds,frame:result.frame});
  return result;
}

async function exerciseVisibleButtons(state,label,{requireClipped=false}={}) {
  const idle=await clearPointer();let hovered=0,clipped=0;
  for(const index of [0,1,2,3,4,5,6,7,8]) {
    const button=q(idle,index+10),visible=visibleBounds(idle,button);
    if(visible.width<=2||visible.height<=2)continue;
    const wasClipped=visible.width<button.bounds.width-1e-6||visible.height<button.bounds.height-1e-6;
    await hover(idle,index,`${label}: button ${index}`);
    if(index!==4){hovered++;if(wasClipped)clipped++;}
    assert.deepEqual((await clearPointer()).frame,idle.frame,'Trusted pointerleave restores the same core idle frame');
  }
  assert(hovered>0,`${label}: must exercise a real visible button`);
  if(requireClipped)assert(clipped>0,`${label}: must exercise a viewport-clipped button`);
  report.states.push({operation:`${label}: hover coverage`,hovered,clipped});return idle;
}

async function rejectAndRecover(invalid,label) {
  const previous=await waitReady();attempted={operation:label,...invalid};
  await cdp.send('Emulation.setDeviceMetricsOverride',{width:invalid.width,height:invalid.height,deviceScaleFactor:invalid.scale,mobile:false});
  await frame.waitForFunction(expected=>innerWidth===expected.width&&innerHeight===expected.height&&Math.abs(devicePixelRatio-expected.scale)<1e-6&&
    document.documentElement.dataset.runtimeStatus==='failed',invalid);
  const rejected=await observe();
  assert.equal(rejected.canvasHidden,true);assert.equal(rejected.errorHidden,false);assert.equal(rejected.noticeHidden,true);
  assert.equal(rejected.frame,undefined);assert.equal(rejected.metadata,undefined);
  assert.match(rejected.error,/invalid_live_viewport/);
  assert.deepEqual(rejected.canvas,previous.canvas,'Invalid resource request must be rejected before allocating a new backing store');
  assert.equal(rejected.document_id,previous.document_id);
  report.states.push({operation:label,...rejected,status:'deliberately_rejected',runtime_status:rejected.status});
  const recovered=await setMetrics(metrics(800,600,1),`${label}: recover in same document`);
  assert.equal(recovered.document_id,previous.document_id);
  await exerciseVisibleButtons(recovered,`${label}: recovered hover`);
}

try {
  await new Promise((done,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',done);});
  browser=await chromium.launch({headless:true});
  context=await browser.newContext({viewport:{width:800,height:600},deviceScaleFactor:2});
  page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{
    globalThis.anchorLiveProbe={document_id:crypto.randomUUID(),pointer_events:[],lifecycle:[]};
    for(const type of ['pageshow','pagehide'])addEventListener(type,event=>{
      globalThis.anchorLiveProbe.lifecycle.push({type,persisted:event.persisted});
    });
    for(const type of ['pointermove','pointerleave'])addEventListener(type,event=>{
      globalThis.anchorLiveProbe.pointer_events.push({type,trusted:event.isTrusted,pointerType:event.pointerType,
        target:event.target?.tagName||'OTHER',x:event.clientX,y:event.clientY});
    },true);
  });
  const origin=`http://127.0.0.1:${server.address().port}`;
  await page.goto(`${origin}/live-embed`);
  frame=await (await page.waitForSelector('iframe')).contentFrame();
  cdp=await context.newCDPSession(page);
  attempted={operation:'ordinary iframe startup',width:800,height:600,scale:2};
  const initial=await waitReady(metrics(800,600,2));
  report.states.push({operation:'ordinary iframe startup',...initial});
  await exerciseVisibleButtons(initial,'ordinary iframe DPR2');
  await page.screenshot({path:join(out,'ordinary-iframe-dpr2.png')});

  // Preserve the actual candidate's original-profile frames before departures.
  // Their independent Rust comparison still belongs exclusively to the pair gate.
  for(const width of [750,480]) {
    const state=await setMetrics(metrics(width,600,1),'original comparison-profile baseline');
    const idle=await exerciseVisibleButtons(state,`original ${width}px baseline`);
    originals.set(width,idle.frame);
  }
  let state=await setMetrics(metrics(322,713,1.25),'fractional DPR and rounded backing store');
  await exerciseVisibleButtons(state,'fractional DPR clipped buttons',{requireClipped:true});
  await page.screenshot({path:join(out,'fractional-dpr-clipped.png')});
  state=await setMetrics(metrics(128,128,1.25),'short clipped viewport');
  await exerciseVisibleButtons(state,'short viewport clipping',{requireClipped:true});
  await setMetrics(metrics(4,4,.25),'minimum live viewport and backing store');

  // The shadow workaround uses an offscreen caster. At the maximum admitted
  // width, verify real Canvas pixels do not contain a stray opaque caster.
  state=await setMetrics(metrics(4096,600,1),'maximum live width');
  await clearPointer();
  const wideHover=await hover(state,2,'maximum-width rightmost popup');
  const popup=q(wideHover,200).bounds,button=q(wideHover,12).bounds;
  const points=[{kind:'blank8',x:8,y:popup.y+popup.height/2},{kind:'blank64',x:64,y:popup.y+popup.height/2},
    {kind:'button',x:button.x+12,y:button.y+12},{kind:'popup',x:popup.x+3,y:popup.y+3}];
  const samples=await frame.evaluate(points=>{
    const canvas=document.querySelector('canvas'),context=canvas.getContext('2d');
    return points.map(point=>({...point,rgba:Array.from(context.getImageData(Math.floor(point.x*devicePixelRatio),Math.floor(point.y*devicePixelRatio),1,1).data)}));
  },points);
  for(const sample of samples.filter(sample=>sample.kind.startsWith('blank')))assert.deepEqual(sample.rgba,[255,255,255,255],`No leaked shadow caster at ${sample.kind}`);
  assert.deepEqual(samples.find(sample=>sample.kind==='button').rgba,[0,0,0,255]);
  const popupPixel=samples.find(sample=>sample.kind==='popup').rgba;
  assert.equal(popupPixel[3],255);assert(popupPixel.slice(0,3).every(value=>value<=90),'Actual popup paint must darken its interior');
  report.shadow_probe={width:4096,height:600,scale:1,samples};
  await page.screenshot({path:join(out,'maximum-width-popup.png')});
  await clearPointer();

  // Change DPR repeatedly without changing logical dimensions. Browser CDP
  // changes real metrics; this harness never dispatches resize/matchMedia events.
  for(const scale of [2,1.25,4,.25,1]) {
    state=await setMetrics(metrics(800,600,scale),'same-size DPR change');
    await clearPointer();await hover(state,2,`same-size DPR ${scale} hover`);await clearPointer();
  }
  for(const [invalid,label] of [
    [metrics(800,600,4.1),'invalid DPR at same logical size'],
    [metrics(4097,600,1),'invalid logical width'],
    [metrics(800,3,1),'invalid logical height'],
    [metrics(128,4097,4),'invalid backing-store side'],
    [metrics(4096,8193,1),'invalid backing-store area'],
  ])await rejectAndRecover(invalid,label);

  for(const width of [750,480,750]) {
    await setMetrics(metrics(width,600,1),'restore original comparison profile');
    const idle=await clearPointer();
    assert.deepEqual(idle.frame,originals.get(width),'Live viewport/DPR departures must restore original candidate output');
    await exerciseVisibleButtons(idle,`restored ${width}px hover`);
    await page.screenshot({path:join(out,`restored-${width}-dpr1.png`)});
  }

  // History may reload or restore BFCache, and Chromium may reset CDP metrics
  // to the context's initial 800x600 DPR2. Validate observed returned metrics
  // coherently BEFORE imposing any expected baseline. Neither lifecycle path
  // is required, and a return alone is never claimed as BFCache restoration.
  const beforeHistory=await observe();
  await frame.evaluate(()=>{globalThis.anchorLiveHistoryMarker=true;});
  attempted={operation:'observe real history return'};
  await page.goto(`${origin}/away`);await page.goBack();
  frame=await (await page.waitForSelector('iframe')).contentFrame();
  const returned=await waitReady();
  const marker=await frame.evaluate(()=>globalThis.anchorLiveHistoryMarker===true);
  const persisted=returned.lifecycle.findLast(event=>event.type==='pageshow')?.persisted===true;
  report.history={returned,same_document:returned.document_id===beforeHistory.document_id,marker_retained:marker,
    pageshow_persisted:persisted,bfcache_restored:marker&&persisted};
  if(persisted)assert(marker&&report.history.same_document,'Persisted pageshow must preserve the original document');
  await cdp.detach();cdp=await context.newCDPSession(page);
  await setMetrics(metrics(750,600,1),'explicit history-return baseline');
  assert.deepEqual((await clearPointer()).frame,originals.get(750));
  for(const scale of [2,1.25,1]) {
    state=await setMetrics(metrics(750,600,scale),'same-size DPR after history return');
    await clearPointer();await hover(state,2,`history-return DPR ${scale} hover`);await clearPointer();
  }
  assert.deepEqual((await waitReady()).frame,originals.get(750));
  report.history.same_size_dpr_and_trusted_hover_after_return='passed';
  assert.deepEqual(errors,[]);report.status='passed';report.browser=await browser.version();
}catch(error) {
  report.failure={attempted,error:{name:error.name,message:error.message,stack:error.stack},page_errors:errors};
  if(frame)try{report.failure.observed=await observe();}catch(captureError){report.failure.observation_error=captureError.message;}
  if(page)try{await page.screenshot({path:join(out,'failure.png')});}catch(captureError){report.failure.screenshot_error=captureError.message;}
  throw error;
}finally {
  await writeFile(join(out,'live-regression.json'),JSON.stringify(report,null,2)+'\n');
  await browser?.close();await new Promise(done=>server.close(done));
}
console.log('Live embedded anchor viewport/DPR, trusted hover, clipping, recovery and history regression passed; no parity claim.');
