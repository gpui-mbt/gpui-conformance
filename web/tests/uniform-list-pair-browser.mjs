// Execute each actual runtime independently. The verifier rereads original bytes afterward.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {randomUUID} from 'node:crypto';
import {createServer} from 'node:http';
import {readFile,mkdir,readdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {sha256,decodePng,discoverGeometry,makeProfile,assertWheelDelivery} from './uniform-list-comparator.mjs';
import {PAIR_PROFILE} from './uniform-list-pair-comparator.mjs';
import {PAIR_SUITE_INPUTS,GRAPHICS_ARGS,captureBinding,inputEvidence,candidateProvenance,assertCandidateRuntime,runtimeResponsePath,requiresRuntimeRetention} from './uniform-list-pair-evidence.mjs';
import {validateReport,loadEvidence,verifyBehavior} from './uniform-list-runtime-evidence.mjs';
import {evidenceFilename} from './uniform-list-worker-evidence.mjs';
assert(process.argv.length===4,'Usage: candidate-site rust-evidence; fixed300x300 DPR1');
const runtime='moonbit';
const site=resolve(process.argv[2]);
const rustDirectory=resolve(process.argv[3]);
const evidence=resolve(process.env.BROWSER_EVIDENCE||'_build/uniform-list-pair-evidence');
const result={status:'failed',runtime,capture_session:randomUUID(),comparison:'not_run',
  conformance:'not_claimed',mode:'actual_compiled_candidate_capture',profile_revision:PAIR_PROFILE,profile:{width:300,height:300,dpr:1},
  captures:{},operations:[],requests:[],served_requests:[],runtime_responses:[],
  support_files:[],suite_inputs:[],console:[],errors:[],
  decoder:{name:'Pillow',version:'12.0.0',transport:'Original300x300 PNG bytes; bounded dimensions plus complete RGBA'},
  unverified:['Full-image/AA, OCR or native parity','Rust lazy factories/callback/internal-mask/click claims']};
await mkdir(evidence,{recursive:true});
assert(!(await readdir(evidence)).some(name=>name.startsWith(`uniform-list-${runtime}-`)),'Choose a fresh evidence directory; original runtime evidence is never overwritten');
let browser,server,page;
const images={},responseTasks=[],retained={assets:{},responses:{}};let responseId=0;
try {
  const rustReportBytes=await readFile(join(rustDirectory,'uniform-list-rust-result-dpr1.json'));
  const rustReport=JSON.parse(rustReportBytes);validateReport(rustReport,'rust');
  const rustFiles=await loadEvidence(rustDirectory,rustReport);verifyBehavior(rustReport,rustFiles);
  const rustGeometry=discoverGeometry(rustFiles.images.initial);
  result.rust_input={report_sha256:sha256(rustReportBytes),capture_session:rustReport.capture_session,
    initial_png_sha256:rustReport.captures.initial.png_sha256,geometry_derivation:'Reread original Rust PNG; never candidate metadata'};
  const manifestBytes=await readFile(join(site,'build-manifest.json'));
  result.build=JSON.parse(manifestBytes);result.source=candidateProvenance(result.build);
  const manifestFile='uniform-list-moonbit-build-manifest.json';await writeFile(join(evidence,manifestFile),manifestBytes);
  result.build_evidence={file:manifestFile,sha256:sha256(manifestBytes)};
  for(const path of PAIR_SUITE_INPUTS) {
    const bytes=await readFile(new URL('../../'+path,import.meta.url)),file=evidenceFilename(runtime,'suite',path);
    await writeFile(join(evidence,file),bytes);result.suite_inputs.push({path,file,sha256:sha256(bytes),bytes:bytes.length});
  }
  for(const path of Object.keys(result.build.files).filter(path=>path.startsWith('inputs/')).sort()) {
    const bytes=await readFile(join(site,path));assert.equal(sha256(bytes),result.build.files[path]);
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
  const context=await browser.newContext({viewport:{width:300,height:300},deviceScaleFactor:1,serviceWorkers:'block'});page=await context.newPage();
  result.environment={playwright:playwrightVersion,browser:await browser.version(),node:process.version,platform:process.platform,arch:process.arch,
    graphics_requested:GRAPHICS_ARGS};
  const browserCdp=await browser.newBrowserCDPSession();
  result.graphics_actual=await browserCdp.send('SystemInfo.getInfo');await browserCdp.detach();
  const graphicsBytes=Buffer.from(JSON.stringify(result.graphics_actual,null,2)+'\n'),graphicsFile=`uniform-list-${runtime}-graphics.json`;
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
  await page.addInitScript(()=>{
    globalThis.uniformListOracleEvents=[];
    addEventListener('wheel',event=>{
      const entry={type:event.type,trusted:event.isTrusted,target:event.target.tagName,time:performance.now(),defaultPrevented:null,
        x:event.clientX,y:event.clientY,deltaX:event.deltaX,deltaY:event.deltaY,deltaZ:event.deltaZ,deltaMode:event.deltaMode,
        shiftKey:event.shiftKey,ctrlKey:event.ctrlKey,altKey:event.altKey,metaKey:event.metaKey};
      globalThis.uniformListOracleEvents.push(entry);setTimeout(()=>{entry.defaultPrevented=event.defaultPrevented;},0);
    },{capture:true,passive:true});
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/gpui-conformance/${runtime}/?example=uniform_list`);
  await page.locator(`html[data-runtime-status="ready"]`).waitFor({timeout:60000});
  assert.equal(await page.evaluate(()=>crossOriginIsolated),true);assert.equal(await page.evaluate(()=>devicePixelRatio),1);
  const canvas=page.locator('canvas');result.canvas={bounds:await canvas.boundingBox(),backing:await canvas.evaluate(element=>({width:element.width,height:element.height}))};
  assert.deepEqual(result.canvas,{bounds:{x:0,y:0,width:300,height:300},backing:{width:300,height:300}});
  result.transport=await page.evaluate(()=>({active_tag:document.activeElement?.tagName,canvas_tab_index:document.querySelector('canvas')?.tabIndex,
    note:'Transport observation only, never application-focus evidence'}));
  const frames=()=>page.evaluate(()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done))));
  async function capture(name) {
    const attempts=[];result.captures[name]={attempts,after_operation:result.operations.length,binding:captureBinding(result,name,result.operations.length-1)};let previous;
    const deadline=Date.now()+30000;
    do {
      const bytes=await page.screenshot({animations:'disabled',scale:'device'});
      const file=`uniform-list-${runtime}-${name}-sample-${attempts.length+1}-dpr1.png`;
      await writeFile(join(evidence,file),bytes);
      const attempt={file,png_sha256:sha256(bytes),bytes:bytes.length,binding:result.captures[name].binding,request_ordinal:attempts.length+1,method:'Playwright.page.screenshot'};attempts.push(attempt);
      // The PNG has already been retained if decoding fails.
      const image=decodePng(bytes);Object.assign(attempt,{rgba_sha256:sha256(image.data),width:image.width,height:image.height});
      if(name==='initial') {
        try{discoverGeometry(image);}catch(error){attempt.initial_geometry_error=error.message;previous=undefined;await frames();await page.waitForTimeout(100);continue;}
      }
      if(previous?.rgba_sha256===attempt.rgba_sha256) {
        Object.assign(result.captures[name],{file,stability_file:previous.file,stable:true,png_sha256:attempt.png_sha256,
          stability_png_sha256:previous.png_sha256,rgba_sha256:attempt.rgba_sha256,stability_rgba_sha256:previous.rgba_sha256,
          width:300,height:300,
          method:'Two independently requested original full-viewport PNGs with identical pinned-Pillow decoded RGBA; no crop/resample/substitution'});
        images[name]=image;
        const observation=await page.evaluate(()=>({observation:globalThis.gpuiExample,
          raster_state:{textRendering:document.querySelector('canvas').getContext('2d').textRendering,
            font_loaded:document.fonts.check('16px "IBM Plex Sans"')},
          font_metrics:globalThis.gpuiExample.metadata.runs.map(run=>{
            const c=document.querySelector('canvas').getContext('2d');c.save();
            c.font='normal 400 16px "IBM Plex Sans"';c.textRendering='geometricPrecision';c.fontKerning='normal';
            const m=c.measureText(run.text),chars=Array.from(run.text),prefixes=[0];let prefix='';
            const advances=chars.map(char=>c.measureText(char).width);
            for(const char of chars){prefix+=char;prefixes.push(c.measureText(prefix).width);}
            c.textRendering='auto';const raster=c.measureText(run.text);c.restore();
            return {text:run.text,width:m.width,prefixes,advances,ascent:m.fontBoundingBoxAscent,descent:m.fontBoundingBoxDescent,
              actual_ascent:m.actualBoundingBoxAscent,actual_descent:m.actualBoundingBoxDescent,
              raster_ascent:raster.fontBoundingBoxAscent,raster_descent:raster.fontBoundingBoxDescent};
          })}));
        const sceneBytes=Buffer.from(JSON.stringify({...observation,binding:result.captures[name].binding},null,2)+'\n');
        const sceneFile=`uniform-list-moonbit-${name}-scene.json`;
        await writeFile(join(evidence,sceneFile),sceneBytes);result.captures[name].scene={file:sceneFile,sha256:sha256(sceneBytes)};
        return;
      }
      previous=attempt;await page.waitForTimeout(100);
    }while(Date.now()<deadline);
    throw new Error(`${name}: two identical decoded-RGBA samples were not observed`);
  }
  const cdp=await context.newCDPSession(page);
  async function perform(operation) {
    const record={...operation,input_method:'CDP.Input.dispatchMouseEvent',status:'pending_delivery'};result.operations.push(record);
    const start=await page.evaluate(()=>uniformListOracleEvents.length),a=operation.action;
    await cdp.send('Input.dispatchMouseEvent',{type:'mouseWheel',x:a.x,y:a.y,deltaX:a.deltaX,deltaY:a.deltaY,buttons:0});
    record.input_acknowledged=true;
    await page.waitForFunction(start=>uniformListOracleEvents.length===start+1,start);
    await page.waitForTimeout(30);await frames();
    await page.waitForFunction(()=>uniformListOracleEvents.every(event=>event.defaultPrevented!==null));
    record.events=await page.evaluate(start=>uniformListOracleEvents.slice(start),start);
    assertWheelDelivery(record.events,operation.action);
    record.status='delivered';record.post_delivery_animation_frames=2;
  }
  await frames();
  result.startup_events=await page.evaluate(()=>uniformListOracleEvents.slice());result.operation_start=result.startup_events.length;
  await capture('initial');
  result.discovered_geometry=discoverGeometry(images.initial);
  const profile=makeProfile(rustGeometry);
  for(const operation of profile.operations){await perform(operation);await capture(operation.name);}
  await Promise.all(responseTasks);
  assertCandidateRuntime(result,retained.assets,retained.responses);
  assert.deepEqual(result.errors,[],'Runtime/console/network errors fail discovery');
  result.status=`${runtime}_profile_captured`;
  console.log(`CAPTURED: actual ${runtime} uniform_list wheel profile and original stable PNGs. Independent pair verification still required.`);
}catch(error){result.failure=error.stack;throw error;}
finally {
  if(page) {
    try{result.events=await page.evaluate(()=>uniformListOracleEvents.slice());}catch(error){result.final_event_read_error=error.message;}
    if(result.status==='failed')try {
      const bytes=await page.screenshot({animations:'disabled',scale:'device'}),file=`uniform-list-${runtime}-failure-full-dpr1.png`;
      await writeFile(join(evidence,file),bytes);result.failure_screenshot={file,png_sha256:sha256(bytes)};
    }catch(error){result.failure_screenshot_error=error.message;}
  }
  await Promise.all(responseTasks);
  const inputBytes=Buffer.from(JSON.stringify(inputEvidence(result),null,2)+'\n'),inputFile=`uniform-list-${runtime}-trusted-input.json`;
  await writeFile(join(evidence,inputFile),inputBytes);result.input_evidence={file:inputFile,sha256:sha256(inputBytes)};
  await writeFile(join(evidence,`uniform-list-${runtime}-result-dpr1.json`),JSON.stringify(result,null,2)+'\n');
  if(browser)await browser.close();if(server)await new Promise(done=>server.close(done));
}
