// Execute each actual runtime independently. The verifier rereads original bytes afterward.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {randomUUID} from 'node:crypto';
import {createServer} from 'node:http';
import {readFile,mkdir,readdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {SOURCE_CONSTRAINTS,PROFILE_REVISION,VIEWPORT_SEQUENCE,UNVERIFIED,sha256,decodePng,discoverGeometry,inspectLayout,makeProfile,assertResizeDelivery,assertViewport,assertProvenance,provenanceNegativeControls} from './grid-layout-comparator.mjs';
import {SUITE_INPUTS,GRAPHICS_ARGS,captureBinding,inputEvidence,validateRuntimeResponses,assertExecutedBytes,runtimeResponsePath,requiresRuntimeRetention} from './grid-layout-runtime-evidence.mjs';
import {evidenceFilename} from './grid-layout-worker-evidence.mjs';
assert(process.argv.length<=3,'Only a site path is accepted; 399/400/401/500x500 DPR1 unchanged Rust-only profile');
const runtime='rust';
const site=resolve(process.argv[2]||'_build/grid-layout-browser-lab');
const evidence=resolve(process.env.BROWSER_EVIDENCE||'_build/grid-layout-oracle-evidence');
const result={status:'failed',runtime,candidate:'not_implemented',capture_session:randomUUID(),comparison:'not_run',
  conformance:'not_claimed',mode:'source_only_profile_capture',profile_revision:PROFILE_REVISION,profile:{widths:[399,400,401,500],height:500,dpr:1},
  source_constraints:SOURCE_CONSTRAINTS,captures:{},operations:[],requests:[],served_requests:[],runtime_responses:[],
  support_files:[],suite_inputs:[],console:[],errors:[],decoder:{name:'Pillow',version:'12.0.0',transport:'Bounded local dimensions + raw RGBA; original PNG bytes unchanged'},
  unverified:UNVERIFIED};
await mkdir(evidence,{recursive:true});
assert(!(await readdir(evidence)).some(name=>name.startsWith(`grid-layout-${runtime}-`)),'Choose a fresh evidence directory; original runtime evidence is never overwritten');
let browser,server,page;
const images={},responseTasks=[],retained={assets:{},responses:{}};let responseId=0;
try {
  const manifestBytes=await readFile(join(site,'build-manifest.json')),catalogBytes=await readFile(join(site,'examples.json'));
  result.build=JSON.parse(manifestBytes);result.catalog=JSON.parse(catalogBytes);
  result.source=assertProvenance(result.build,result.catalog);
  result.provenance_negative_controls=provenanceNegativeControls(result.build,result.catalog);
  for(const [name,bytes] of [['build-manifest.json',manifestBytes],['catalog.json',catalogBytes]]) {
    const file=`grid-layout-${runtime}-${name}`;await writeFile(join(evidence,file),bytes);
    result[name==='catalog.json'?'catalog_evidence':'build_evidence']={file,sha256:sha256(bytes)};
  }
  const decoder=await readFile(new URL('../scripts/decode_grid_layout_png.py',import.meta.url));
  await writeFile(join(evidence,`grid-layout-${runtime}-png-decoder.py`),decoder);result.decoder.sha256=sha256(decoder);
  for(const path of SUITE_INPUTS) {
    const bytes=await readFile(new URL('../../'+path,import.meta.url)),file=evidenceFilename(runtime,'suite',path);
    await writeFile(join(evidence,file),bytes);result.suite_inputs.push({path,file,sha256:sha256(bytes),bytes:bytes.length});
  }
  for(const path of ['rust/unchanged-source/grid_layout.rs','rust/packaging-Cargo.toml','rust/Cargo.lock',...Object.values(result.build.rust.embedded_fonts).map(font=>'rust/'+font.file)]) {
    const bytes=await readFile(join(site,path));assert.equal(sha256(bytes),result.build.rust.files[path.slice(5)]);
    const file=evidenceFilename(runtime,'input',path);await writeFile(join(evidence,file),bytes);
    result.support_files.push({path,file,sha256:sha256(bytes),bytes:bytes.length,purpose:path.endsWith('.rs')?'Unchanged source input':path.endsWith('.toml')?'Relocated standalone package manifest':path.endsWith('Cargo.lock')?'Pinned Rust dependency lock':'Font bytes embedded in the compiled Rust WASM; not a separate browser font request'});
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
  const context=await browser.newContext({viewport:{width:500,height:500},deviceScaleFactor:1,serviceWorkers:'block'});page=await context.newPage();
  result.environment={playwright:playwrightVersion,browser:await browser.version(),node:process.version,platform:process.platform,arch:process.arch,
    graphics_requested:GRAPHICS_ARGS};
  const browserCdp=await browser.newBrowserCDPSession();
  result.graphics_actual=await browserCdp.send('SystemInfo.getInfo');await browserCdp.detach();
  const graphicsBytes=Buffer.from(JSON.stringify(result.graphics_actual,null,2)+'\n'),graphicsFile=`grid-layout-${runtime}-graphics.json`;
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
  await page.addInitScript(()=>{
    globalThis.gridLayoutOracleDocument=crypto.randomUUID();
    globalThis.gridLayoutOracleEvents=[];
    addEventListener('resize',event=>{
      globalThis.gridLayoutOracleEvents.push({type:event.type,trusted:event.isTrusted,target:event.target===window?'WINDOW':'OTHER',
        time:performance.now(),width:innerWidth,height:innerHeight,dpr:devicePixelRatio});
    });
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/gpui-conformance/${runtime}/?example=grid_layout`);
  await page.locator(`html[data-runtime-status="initialized"]`).waitFor({timeout:60000});
  assert.equal(await page.evaluate(()=>crossOriginIsolated),true);
  result.document_id=await page.evaluate(()=>gridLayoutOracleDocument);
  const canvas=page.locator('canvas');
  async function viewportObservation() {
    return {inner:await page.evaluate(()=>({width:innerWidth,height:innerHeight})),dpr:await page.evaluate(()=>devicePixelRatio),
      canvas:{bounds:await canvas.boundingBox(),backing:await canvas.evaluate(element=>({width:element.width,height:element.height}))}};
  }
  result.initial_viewport=await viewportObservation();assertViewport(result.initial_viewport,500);
  result.transport=await page.evaluate(()=>({active_tag:document.activeElement?.tagName,canvas_tab_index:document.querySelector('canvas')?.tabIndex,
    note:'Transport observation only, never application-focus evidence'}));
  const frames=()=>page.evaluate(()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done))));
  async function capture(name) {
    const state=VIEWPORT_SEQUENCE.find(state=>state.name===name),viewport=await viewportObservation();assertViewport(viewport,state.width);
    const attempts=[];result.captures[name]={attempts,viewport,after_operation:result.operations.length,binding:captureBinding(result,name,result.operations.length-1)};let previous;
    const deadline=Date.now()+30000;
    do {
      const bytes=await page.screenshot({animations:'disabled',scale:'device'});
      const file=`grid-layout-${runtime}-${name}-sample-${attempts.length+1}-dpr1.png`;
      await writeFile(join(evidence,file),bytes);
      const attempt={file,png_sha256:sha256(bytes),bytes:bytes.length,binding:result.captures[name].binding,request_ordinal:attempts.length+1,method:'Playwright.page.screenshot'};attempts.push(attempt);
      // The PNG has already been retained if decoding fails.
      const image=decodePng(bytes);Object.assign(attempt,{rgba_sha256:sha256(image.data),width:image.width,height:image.height});
      {
        try{attempt.observed_geometry=discoverGeometry(image);inspectLayout(image);}catch(error){attempt.layout_validation_error=error.message;previous=undefined;await frames();await page.waitForTimeout(100);continue;}
      }
      if(previous?.rgba_sha256===attempt.rgba_sha256) {
        Object.assign(result.captures[name],{file,stability_file:previous.file,stable:true,png_sha256:attempt.png_sha256,
          stability_png_sha256:previous.png_sha256,rgba_sha256:attempt.rgba_sha256,stability_rgba_sha256:previous.rgba_sha256,
          width:state.width,height:500,
          method:'Two independently requested original full-viewport PNGs with identical pinned-Pillow decoded RGBA; no crop/resample/substitution'});
        images[name]=image;return;
      }
      previous=attempt;await page.waitForTimeout(100);
    }while(Date.now()<deadline);
    throw new Error(`${name}: two identical decoded-RGBA samples were not observed`);
  }
  async function perform(operation) {
    const record={...operation,input_method:'Playwright.page.setViewportSize',status:'pending_delivery',before:await viewportObservation()};result.operations.push(record);
    const start=await page.evaluate(()=>gridLayoutOracleEvents.length),action=operation.action;
    await page.setViewportSize({width:action.width,height:action.height});record.input_acknowledged=true;
    await page.waitForFunction(start=>gridLayoutOracleEvents.length>start,start);
    await page.waitForTimeout(100);await frames();
    await page.waitForFunction(width=>{const canvas=document.querySelector('canvas');return innerWidth===width&&innerHeight===500&&canvas.width===width&&canvas.height===500;},action.width);
    record.events=await page.evaluate(start=>gridLayoutOracleEvents.slice(start),start);assertResizeDelivery(record.events,action);
    record.after=await viewportObservation();assertViewport(record.after,action.width);
    record.document_id=await page.evaluate(()=>gridLayoutOracleDocument);assert.equal(record.document_id,result.document_id);
    record.status='delivered';record.post_delivery_animation_frames=2;
  }
  await frames();await page.waitForTimeout(100);
  result.startup_events=await page.evaluate(()=>gridLayoutOracleEvents.slice());result.operation_start=result.startup_events.length;
  await capture('initial');
  for(const operation of makeProfile().operations){await perform(operation);await capture(operation.name);}
  await Promise.all(responseTasks);
  validateRuntimeResponses(result);assertExecutedBytes(result,retained);
  assert.deepEqual(result.errors,[],'Runtime/console/network errors fail discovery');
  result.status=`${runtime}_profile_captured`;
  console.log(`CAPTURED: actual ${runtime} grid_layout viewport resize profile and original stable PNGs. Independent source-only verification still required.`);
}catch(error){result.failure=error.stack;throw error;}
finally {
  if(page) {
    try{result.events=await page.evaluate(()=>gridLayoutOracleEvents.slice());}catch(error){result.final_event_read_error=error.message;}
    if(result.status==='failed')try {
      const bytes=await page.screenshot({animations:'disabled',scale:'device'}),file=`grid-layout-${runtime}-failure-full-dpr1.png`;
      await writeFile(join(evidence,file),bytes);result.failure_screenshot={file,png_sha256:sha256(bytes)};
    }catch(error){result.failure_screenshot_error=error.message;}
  }
  await Promise.all(responseTasks);
  const inputBytes=Buffer.from(JSON.stringify(inputEvidence(result),null,2)+'\n'),inputFile=`grid-layout-${runtime}-trusted-input.json`;
  await writeFile(join(evidence,inputFile),inputBytes);result.input_evidence={file:inputFile,sha256:sha256(inputBytes)};
  await writeFile(join(evidence,`grid-layout-${runtime}-result-dpr1.json`),JSON.stringify(result,null,2)+'\n');
  if(browser)await browser.close();if(server)await new Promise(done=>server.close(done));
}
