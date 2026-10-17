// Execute each actual runtime independently. The verifier rereads original bytes afterward.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {randomUUID} from 'node:crypto';
import {createServer} from 'node:http';
import {readFile,mkdir,readdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {ORACLE,PROFILE_REVISION,VIEWPORT_SEQUENCE,GRAPHICS_ARGS,sha256,decodePng,buttonTarget,assertViewport,assertProvenance,validateOperations} from './gradient-comparator.mjs';
import {SUITE_INPUTS,captureBinding,inputEvidence,validateReport,runtimeResponsePath,requiresRuntimeRetention} from './gradient-runtime-evidence.mjs';
import {installBackendObserver,classifyBackend} from './gradient-backend-observer.mjs';
import {evidenceFilename} from './gradient-worker-evidence.mjs';
assert(process.argv.length<=3,'Only a site path is accepted; 960x600/600x960 DPR1 unchanged Rust-only profile');
const runtime='rust';
const site=resolve(process.argv[2]||'_build/gradient-browser-lab');
const evidence=resolve(process.env.BROWSER_EVIDENCE||'_build/gradient-oracle-evidence');
const result={status:'failed',runtime,candidate:'not_implemented',capture_session:randomUUID(),comparison:'not_run',
 conformance:'not_claimed',profile_revision:PROFILE_REVISION,profile:VIEWPORT_SEQUENCE,captures:{},operations:[],requests:[],served_requests:[],runtime_responses:[],
 support_files:[],suite_inputs:[],console:[],errors:[],unverified:ORACLE.unverified};
await mkdir(evidence,{recursive:true});
assert(!(await readdir(evidence)).some(name=>name.startsWith(`gradient-${runtime}-`)),'Choose a fresh evidence directory; original runtime evidence is never overwritten');
let browser,server,page;
const images={},responseTasks=[],retained={assets:{},responses:{}};let responseId=0;
try {
  const manifestBytes=await readFile(join(site,'build-manifest.json')),catalogBytes=await readFile(join(site,'examples.json'));
  result.build=JSON.parse(manifestBytes);result.catalog=JSON.parse(catalogBytes);
  result.source=assertProvenance(result.build,result.catalog);
  for(const [name,bytes] of [['build-manifest.json',manifestBytes],['catalog.json',catalogBytes]]) {
    const file=`gradient-${runtime}-${name}`;await writeFile(join(evidence,file),bytes);
    result[name==='catalog.json'?'catalog_evidence':'build_evidence']={file,sha256:sha256(bytes)};
  }
  for(const path of SUITE_INPUTS) {
    const bytes=await readFile(new URL('../../'+path,import.meta.url)),file=evidenceFilename(runtime,'suite',path);
    await writeFile(join(evidence,file),bytes);result.suite_inputs.push({path,file,sha256:sha256(bytes),bytes:bytes.length});
  }
  for(const path of Object.keys(result.build.rust.files).filter(p=>p.startsWith('support-source/')||p.startsWith('unchanged-source/')||p.startsWith('embedded-font-inputs/')||['Cargo.lock','packaging-Cargo.toml'].includes(p)).map(p=>'rust/'+p)) {
    const bytes=await readFile(join(site,path));assert.equal(sha256(bytes),result.build.rust.files[path.slice(5)]);
    const file=evidenceFilename(runtime,'input',path);await writeFile(join(evidence,file),bytes);
    result.support_files.push({path,file,sha256:sha256(bytes),bytes:bytes.length});
  }
  const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.wasm':'application/wasm','.ttf':'font/ttf'};
  server=createServer(async(request,response)=>{
    const record={method:request.method,url:request.url};result.served_requests.push(record);
    try {
      const url=new URL(request.url,'http://localhost');
      if(url.pathname==='/favicon.ico'){Object.assign(record,{status:204,bytes:0});response.writeHead(204);response.end();return;}
      if(!url.pathname.startsWith('/gpui-conformance/'))throw new Error('Outside site');
      let relative=decodeURIComponent(url.pathname.slice('/gpui-conformance/'.length));if(!relative||relative.endsWith('/'))relative+='index.html';
      const path=resolve(site,relative);if(!path.startsWith(site+sep))throw new Error('Outside site');
      const bytes=await readFile(path);Object.assign(record,{status:200,bytes:bytes.length,sha256:sha256(bytes)});
      response.writeHead(200,{'content-type':types[extname(path)]||'application/octet-stream','cache-control':'no-store',
        'Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp','Cross-Origin-Resource-Policy':'same-origin'});response.end(bytes);
    }catch(error){Object.assign(record,{status:404,error:error.message});response.writeHead(404);response.end('Not found');}
  });
  await new Promise(done=>server.listen(0,'127.0.0.1',done));
  assert(process.env.PLAYWRIGHT_ROOT,'PLAYWRIGHT_ROOT must identify pinned Playwright installation');
  if(process.env.BROWSERS_PATH&&!process.env.PLAYWRIGHT_BROWSERS_PATH)process.env.PLAYWRIGHT_BROWSERS_PATH=process.env.BROWSERS_PATH;
  const require=createRequire(join(process.env.PLAYWRIGHT_ROOT,'package.json'));const {chromium}=require('playwright');
  const playwrightVersion=require('playwright/package.json').version;assert.equal(playwrightVersion,'1.56.1','Pinned browser transport package required');
  browser=await chromium.launch({headless:true,args:GRAPHICS_ARGS});
  const context=await browser.newContext({viewport:{width:960,height:600},deviceScaleFactor:1,serviceWorkers:'block'});page=await context.newPage();
  result.environment={playwright:playwrightVersion,browser:await browser.version(),node:process.version,platform:process.platform,arch:process.arch,
    graphics_requested:GRAPHICS_ARGS};
  const browserCdp=await browser.newBrowserCDPSession();
  result.graphics_actual=await browserCdp.send('SystemInfo.getInfo');await browserCdp.detach();
  const graphicsBytes=Buffer.from(JSON.stringify(result.graphics_actual,null,2)+'\n'),graphicsFile=`gradient-${runtime}-graphics.json`;
  await writeFile(join(evidence,graphicsFile),graphicsBytes);result.graphics_evidence={file:graphicsFile,sha256:sha256(graphicsBytes)};
  page.on('pageerror',error=>result.errors.push({kind:'pageerror',message:error.message}));
  page.on('console',message=>{result.console.push({type:message.type(),text:message.text()});
    if(message.type()==='error')result.errors.push({kind:'console',message:message.text()});});
  page.on('requestfailed',request=>result.errors.push({kind:'requestfailed',url:request.url(),failure:request.failure()}));
  page.on('response',response=>{
    const response_id=++responseId;
    const resource_type=response.request().resourceType();
    result.requests.push({url:response.url(),status:response.status(),response_id,resource_type});
    const path=runtimeResponsePath(response.url());
    if(requiresRuntimeRetention(response.url(),resource_type))responseTasks.push((async()=>{
      try {
        const bytes=await response.body(),file=evidenceFilename(runtime,'asset',response.url(),response_id);
        // Retain even unexpected/failed executable responses before checking pins.
        await writeFile(join(evidence,file),bytes);result.runtime_responses.push({path,url:response.url(),status:response.status(),response_id,resource_type,file,sha256:sha256(bytes),bytes:bytes.length,binding:{runtime,session:result.capture_session}});
        retained.assets[path]=bytes;retained.responses[response_id]=bytes;
      }catch(error){result.errors.push({kind:'runtime_response',url:response.url(),message:error.message});}
    })());
  });
  result.navigation_count=0;
  page.on('framenavigated',frame=>{if(frame===page.mainFrame())result.navigation_count++;});
  await page.addInitScript(installBackendObserver);
  await page.addInitScript(()=>{
    globalThis.gradientOracleDocument=crypto.randomUUID();
    globalThis.gradientOracleEvents=[];
    for(const type of ['resize','pointermove','pointerdown','pointerup','mousedown','mouseup','click'])addEventListener(type,event=>{
      const record={type:event.type,trusted:event.isTrusted,target:event.target===window?'WINDOW':event.target?.tagName||'OTHER',time:performance.now()};
      if(type==='resize')Object.assign(record,{width:innerWidth,height:innerHeight,dpr:devicePixelRatio});
      else Object.assign(record,{x:event.clientX,y:event.clientY,button:event.button,buttons:event.buttons,...(type==='pointermove'?{pointerType:event.pointerType}:{})});
      globalThis.gradientOracleEvents.push(record);
    },true);
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/gpui-conformance/${runtime}/?example=gradient`);
  await page.locator(`html[data-runtime-status="initialized"]`).waitFor({timeout:60000});
  assert.equal(await page.evaluate(()=>crossOriginIsolated),true);
  result.document_id=await page.evaluate(()=>gradientOracleDocument);
  const canvas=page.locator('canvas');
  async function viewportObservation() {
    return {inner:await page.evaluate(()=>({width:innerWidth,height:innerHeight})),dpr:await page.evaluate(()=>devicePixelRatio),
      canvas:{bounds:await canvas.boundingBox(),backing:await canvas.evaluate(element=>({width:element.width,height:element.height}))}};
  }
  result.initial_viewport=await viewportObservation();assertViewport(result.initial_viewport,VIEWPORT_SEQUENCE[0]);
  result.transport=await page.evaluate(()=>({active_tag:document.activeElement?.tagName,canvas_tab_index:document.querySelector('canvas')?.tabIndex,
    note:'Transport observation only, never application-focus evidence'}));
  const frames=()=>page.evaluate(()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done))));
  async function capture(state) {
    const name=state.name,viewport=await viewportObservation();assertViewport(viewport,state);
    const attempts=[];result.captures[name]={attempts,viewport,binding:captureBinding(result,state)};let previous;
    const deadline=Date.now()+30000;
    do {
      const bytes=await page.screenshot({animations:'disabled',scale:'device'});
      const file=`gradient-rust-${name}-sample-${attempts.length+1}-dpr1.png`;await writeFile(join(evidence,file),bytes);
      const attempt={file,png_sha256:sha256(bytes),bytes:bytes.length,binding:result.captures[name].binding,request_ordinal:attempts.length+1,method:'Playwright.page.screenshot'};attempts.push(attempt);
      const image=decodePng(bytes);Object.assign(attempt,{rgba_sha256:sha256(image.data),width:image.width,height:image.height});
      if(previous?.rgba_sha256===attempt.rgba_sha256){Object.assign(result.captures[name],{file,stability_file:previous.file,stable:true,rgba_sha256:attempt.rgba_sha256});images[name]=image;return;}
      previous=attempt;await page.waitForTimeout(100);await frames();
    }while(Date.now()<deadline);
    throw new Error(`${name}: original full-frame RGBA did not stabilize; every attempt retained`);
  }
  async function perform(state) {
    const record={name:state.name,action:state.action,input_method:state.action==='resize'?'Playwright.page.setViewportSize':'Playwright.page.mouse.click',status:'pending_delivery',before:await viewportObservation()};result.operations.push(record);
    record.event_start=await page.evaluate(()=>gradientOracleEvents.length);
    if(state.action==='resize')await page.setViewportSize({width:state.width,height:state.height});
    else {record.target=buttonTarget(images[VIEWPORT_SEQUENCE[state.after_operation-1].name]);await page.mouse.click(record.target.x,record.target.y);await page.mouse.move(0,0);}
    record.input_acknowledged=true;
    await page.waitForFunction(start=>gradientOracleEvents.length>start,record.event_start);await page.waitForTimeout(100);await frames();
    await page.waitForFunction(({width,height})=>{const c=document.querySelector('canvas');return innerWidth===width&&innerHeight===height&&c.width===width&&c.height===height;},state);
    record.event_end=await page.evaluate(()=>gradientOracleEvents.length);record.events=await page.evaluate(({a,b})=>gradientOracleEvents.slice(a,b),{a:record.event_start,b:record.event_end});
    record.after=await viewportObservation();assertViewport(record.after,state);record.document_id=await page.evaluate(()=>gradientOracleDocument);assert.equal(record.document_id,result.document_id);record.status='delivered';
  }
  await frames();await page.waitForTimeout(100);
  result.startup_events=await page.evaluate(()=>gradientOracleEvents.slice());result.operation_start=result.startup_events.length;
  await capture(VIEWPORT_SEQUENCE[0]);
  for(const state of VIEWPORT_SEQUENCE.slice(1)){await perform(state);await capture(state);}
  await Promise.all(responseTasks);
  result.events=await page.evaluate(()=>gradientOracleEvents.slice());
  result.backend=classifyBackend(await page.evaluate(()=>gradientBackendSnapshot()));
  assert.deepEqual(result.errors,[],'Runtime/console/network errors fail discovery');
  result.status='rust_profile_captured';validateReport(result);
  console.log('CAPTURED unchanged gradient original PNGs and trusted real clicks/resizes. Independent verification pending.');
}catch(error){result.status="failed";result.failure=error.stack;throw error;}
finally {
  if(page) {
    try{result.events=await page.evaluate(()=>gradientOracleEvents.slice());}catch(error){result.final_event_read_error=error.message;}
    if(result.status==='failed')try {
      const bytes=await page.screenshot({animations:'disabled',scale:'device'}),file=`gradient-${runtime}-failure-full-dpr1.png`;
      await writeFile(join(evidence,file),bytes);result.failure_screenshot={file,png_sha256:sha256(bytes)};
    }catch(error){result.failure_screenshot_error=error.message;}
  }
  await Promise.all(responseTasks);
  const inputBytes=Buffer.from(JSON.stringify(inputEvidence(result),null,2)+'\n'),inputFile=`gradient-${runtime}-trusted-input.json`;
  await writeFile(join(evidence,inputFile),inputBytes);result.input_evidence={file:inputFile,sha256:sha256(inputBytes)};
  await writeFile(join(evidence,`gradient-${runtime}-result-dpr1.json`),JSON.stringify(result,null,2)+'\n');
  if(browser)await browser.close();if(server)await new Promise(done=>server.close(done));
}
