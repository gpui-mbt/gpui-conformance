// Execute each actual runtime independently. The verifier rereads original bytes afterward.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {randomUUID} from 'node:crypto';
import {createServer} from 'node:http';
import {readFile,mkdir,readdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {SOURCE_CONSTRAINTS,sha256,decodePng,discoverGeometry,makeProfile,assertPointerDelivery} from './drag-drop-comparator.mjs';
import {PAIR_REVISION,SUITE_INPUTS,GRAPHICS_ARGS,captureBinding,inputEvidence,assertPairedProvenance as assertProvenance,
  pairedProvenanceNegativeControls as provenanceNegativeControls,expectedRuntimeFiles,requiredRuntimeFiles} from './drag-drop-pair-comparator.mjs';
const args=process.argv.slice(2);assert(args.filter(arg=>!arg.startsWith('--')).length<=1&&args.filter(arg=>arg.startsWith('--')).every(arg=>arg==='--candidate')&&args.filter(arg=>arg==='--candidate').length<=1,'Only a site path and --candidate are accepted');
const runtime=args.includes('--candidate')?'moonbit':'rust';
const site=resolve(args.find(arg=>!arg.startsWith('--'))||'_build/drag-drop-browser-lab');
const evidence=resolve(process.env.BROWSER_EVIDENCE||'_build/drag-drop-pair-evidence');
const result={status:'failed',runtime,candidate:'implemented',capture_session:randomUUID(),comparison:'not_run',
  conformance:'not_claimed',mode:'paired_profile_capture',profile_revision:PAIR_REVISION,profile:{width:800,height:600,dpr:1},
  source_constraints:SOURCE_CONSTRAINTS,captures:{},operations:[],requests:[],served_requests:[],runtime_responses:[],
  support_files:[],suite_inputs:[],console:[],errors:[],decoder:{name:'Pillow',version:'12.0.0',transport:'Bounded local dimensions + raw RGBA; original PNG bytes unchanged'},
  unverified:['Independent paired comparison until verifier runs','native parity','text/OCR or full-image parity',
    'native/global capture, touch and OS drag','other browser/GPU/viewport/DPR','foreign payloads, rejecting predicates or nested/overlapping targets','internal activation grip itself (visible offsets cancel)','negative/fractional grips outside this unchanged 54-state baseline']};
await mkdir(evidence,{recursive:true});
assert(!(await readdir(evidence)).some(name=>name.startsWith(`drag-drop-${runtime}-`)),'Choose a fresh evidence directory; original runtime evidence is never overwritten');
let browser,server,page;
const images={},responseTasks=[];let files={},responseId=0;
try {
  const manifestBytes=await readFile(join(site,'build-manifest.json')),catalogBytes=await readFile(join(site,'examples.json'));
  result.build=JSON.parse(manifestBytes);result.catalog=JSON.parse(catalogBytes);
  result.source=assertProvenance(result.build,result.catalog);
  result.provenance_negative_controls=provenanceNegativeControls(result.build,result.catalog);
  for(const [name,bytes] of [['build-manifest.json',manifestBytes],['catalog.json',catalogBytes]]) {
    const file=`drag-drop-${runtime}-${name}`;await writeFile(join(evidence,file),bytes);
    result[name==='catalog.json'?'catalog_evidence':'build_evidence']={file,sha256:sha256(bytes)};
  }
  const decoder=await readFile(new URL('../scripts/decode_drag_drop_png.py',import.meta.url));
  await writeFile(join(evidence,`drag-drop-${runtime}-png-decoder.py`),decoder);result.decoder.sha256=sha256(decoder);
  files=expectedRuntimeFiles(result.build,runtime);
  for(const path of SUITE_INPUTS) {
    const bytes=await readFile(new URL('../../'+path,import.meta.url)),file=`drag-drop-${runtime}-suite-${path.replaceAll('/','_')}.bin`;
    await writeFile(join(evidence,file),bytes);result.suite_inputs.push({path,file,sha256:sha256(bytes),bytes:bytes.length});
  }
  for(const path of ['rust/unchanged-source/drag_drop.rs','rust/packaging-Cargo.toml',...Object.values(result.build.rust.embedded_fonts).map(font=>'rust/'+font.file)]) {
    const bytes=await readFile(join(site,path));assert.equal(sha256(bytes),result.build.rust.files[path.slice(5)]);
    const file=`drag-drop-${runtime}-input-${path.replaceAll('/','_')}.bin`;await writeFile(join(evidence,file),bytes);
    result.support_files.push({path,file,sha256:sha256(bytes),bytes:bytes.length,purpose:path.endsWith('.rs')?'Unchanged source input':path.endsWith('.toml')?'Relocated standalone package manifest':'Font bytes embedded in the compiled Rust WASM; not a separate browser font request'});
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
  const context=await browser.newContext({viewport:{width:800,height:600},deviceScaleFactor:1,serviceWorkers:'block'});page=await context.newPage();
  result.environment={playwright:playwrightVersion,browser:await browser.version(),node:process.version,platform:process.platform,arch:process.arch,
    graphics_requested:GRAPHICS_ARGS};
  const browserCdp=await browser.newBrowserCDPSession();
  result.graphics_actual=await browserCdp.send('SystemInfo.getInfo');await browserCdp.detach();
  const graphicsBytes=Buffer.from(JSON.stringify(result.graphics_actual,null,2)+'\n'),graphicsFile=`drag-drop-${runtime}-graphics.json`;
  await writeFile(join(evidence,graphicsFile),graphicsBytes);result.graphics_evidence={file:graphicsFile,sha256:sha256(graphicsBytes)};
  page.on('pageerror',error=>result.errors.push({kind:'pageerror',message:error.message}));
  page.on('console',message=>{result.console.push({type:message.type(),text:message.text()});
    if(message.type()==='error')result.errors.push({kind:'console',message:message.text()});});
  page.on('requestfailed',request=>result.errors.push({kind:'requestfailed',url:request.url(),failure:request.failure()}));
  page.on('response',response=>{
    const response_id=++responseId;
    result.requests.push({url:response.url(),status:response.status(),response_id});
    const path=new URL(response.url()).pathname.replace(/^\/gpui-conformance\//,'');
    if(/\.(mjs|js|wasm|ttf)$/.test(path))responseTasks.push((async()=>{
      try {
        const bytes=await response.body(),file=`drag-drop-${runtime}-asset-${path.replaceAll('/','_')}-response-${response_id}.bin`;
        // Retain even unexpected/failed executable responses before checking pins.
        await writeFile(join(evidence,file),bytes);result.runtime_responses.push({path,url:response.url(),status:response.status(),response_id,file,sha256:sha256(bytes),bytes:bytes.length});
        assert(Object.hasOwn(files,path),`Unpinned browser runtime dependency ${path}`);
      }catch(error){result.errors.push({kind:'runtime_response',url:response.url(),message:error.message});}
    })());
  });
  await page.addInitScript(()=>{
    globalThis.dragDropOracleEvents=[];globalThis.dragDropOracleMouseEvents=[];
    for(const type of ['mousemove','mousedown','mouseup'])addEventListener(type,event=>{
      const entry={type,trusted:event.isTrusted,target:event.target.tagName,time:performance.now(),defaultPrevented:null,
        x:event.clientX,y:event.clientY,button:event.button,buttons:event.buttons};
      globalThis.dragDropOracleMouseEvents.push(entry);setTimeout(()=>{entry.defaultPrevented=event.defaultPrevented;},0);
    },{capture:true,passive:true});
    for(const type of ['pointermove','pointerdown','pointerup'])
      addEventListener(type,event=>{
        const entry={type,trusted:event.isTrusted,target:event.target.tagName,time:performance.now(),defaultPrevented:null,
          shiftKey:event.shiftKey,ctrlKey:event.ctrlKey,altKey:event.altKey,metaKey:event.metaKey};
        Object.assign(entry,{x:event.clientX,y:event.clientY,button:event.button,buttons:event.buttons,pointerType:event.pointerType});
        globalThis.dragDropOracleEvents.push(entry);setTimeout(()=>{entry.defaultPrevented=event.defaultPrevented;},0);
      },{capture:true,passive:true});
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/gpui-conformance/${runtime}/?example=drag_drop`);
  await page.locator(`html[data-runtime-status="${runtime==='rust'?'initialized':'ready'}"]`).waitFor({timeout:60000});
  assert.equal(await page.evaluate(()=>crossOriginIsolated),true);assert.equal(await page.evaluate(()=>devicePixelRatio),1);
  const canvas=page.locator('canvas');result.canvas={bounds:await canvas.boundingBox(),backing:await canvas.evaluate(element=>({width:element.width,height:element.height}))};
  assert.deepEqual(result.canvas,{bounds:{x:0,y:0,width:800,height:600},backing:{width:800,height:600}});
  result.transport=await page.evaluate(()=>({active_tag:document.activeElement?.tagName,canvas_tab_index:document.querySelector('canvas')?.tabIndex,
    note:'Transport observation only, never application-focus evidence'}));
  const frames=()=>page.evaluate(()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done))));
  async function capture(name) {
    const attempts=[];result.captures[name]={attempts,after_operation:result.operations.length,binding:captureBinding(result,name,result.operations.length-1)};let previous;
    const deadline=Date.now()+30000;
    do {
      const bytes=await page.screenshot({animations:'disabled',scale:'device'});
      const file=`drag-drop-${runtime}-${name}-sample-${attempts.length+1}-dpr1.png`;
      await writeFile(join(evidence,file),bytes);
      const attempt={file,png_sha256:sha256(bytes),bytes:bytes.length,binding:result.captures[name].binding,request_ordinal:attempts.length+1,method:'Playwright.page.screenshot'};attempts.push(attempt);
      // The PNG has already been retained if decoding fails.
      const image=decodePng(bytes);Object.assign(attempt,{rgba_sha256:sha256(image.data),width:image.width,height:image.height});
      if(previous?.rgba_sha256===attempt.rgba_sha256) {
        Object.assign(result.captures[name],{file,stability_file:previous.file,stable:true,png_sha256:attempt.png_sha256,
          stability_png_sha256:previous.png_sha256,rgba_sha256:attempt.rgba_sha256,stability_rgba_sha256:previous.rgba_sha256,
          width:800,height:600,
          method:'Two independently requested original full-viewport PNGs with identical pinned-Pillow decoded RGBA; no crop/resample/substitution'});
        images[name]=image;return;
      }
      previous=attempt;await page.waitForTimeout(100);
    }while(Date.now()<deadline);
    throw new Error(`${name}: two identical decoded-RGBA samples were not observed`);
  }
  const cdp=await context.newCDPSession(page);
  async function perform(operation) {
    const record={name:operation.name,action:operation.action,expected:operation.expected,duplicate:operation.duplicate,
      input_method:'CDP.Input.dispatchMouseEvent',status:'pending_delivery'};result.operations.push(record);
    const start=await page.evaluate(()=>dragDropOracleEvents.length),mouseStart=await page.evaluate(()=>dragDropOracleMouseEvents.length);
    const action=operation.action,mouse=operation.mouse_expected;
    await cdp.send('Input.dispatchMouseEvent',{type:action.kind==='move'?'mouseMoved':action.kind==='down'?'mousePressed':'mouseReleased',
      x:mouse.x,y:mouse.y,button:action.kind==='move'?'none':'left',buttons:mouse.buttons,clickCount:action.kind==='move'?0:1,pointerType:'mouse'});
    record.input_acknowledged=true;
    if(!operation.duplicate)await page.waitForFunction(start=>dragDropOracleEvents.length===start+1,start);
    await page.waitForTimeout(30);await frames();
    await page.waitForFunction(()=>[...dragDropOracleEvents,...dragDropOracleMouseEvents].every(event=>event.defaultPrevented!==null));
    record.events=await page.evaluate(start=>dragDropOracleEvents.slice(start),start);
    record.mouse_events=await page.evaluate(start=>dragDropOracleMouseEvents.slice(start),mouseStart);
    const expected=operation.duplicate?[{x:mouse.x,y:mouse.y,button:0,buttons:0,pointerType:'mouse'}]:operation.expected;
    record.delivery=assertPointerDelivery(record.events,expected,{duplicate:operation.duplicate});
    record.status='delivered';record.post_delivery_animation_frames=2;
  }
  await page.waitForFunction(()=>[...dragDropOracleEvents,...dragDropOracleMouseEvents].every(event=>event.defaultPrevented!==null));
  result.startup_events=await page.evaluate(()=>dragDropOracleEvents.slice());result.operation_start=result.startup_events.length;
  result.startup_mouse_events=await page.evaluate(()=>dragDropOracleMouseEvents.slice());result.mouse_operation_start=result.startup_mouse_events.length;
  async function execute(profile,start=0) {
    for(let index=start;index<profile.operations.length;index++) {
      await perform(profile.operations[index]);
      for(const [name,spec] of Object.entries(profile.captures))if(spec.after_operation===index+1)await capture(name);
    }
  }
  await execute(makeProfile());
  result.discovered_geometry=discoverGeometry(images.initial);
  await execute(makeProfile(result.discovered_geometry),result.operations.length);
  await Promise.all(responseTasks);
  for(const path of requiredRuntimeFiles(runtime))
    assert(result.runtime_responses.some(response=>response.path===path),`Actual browser response required for ${path}`);
  for(const response of result.runtime_responses){assert.equal(response.status,200);assert.equal(response.sha256,files[response.path]);}
  assert.deepEqual(result.errors,[],'Runtime/console/network errors fail discovery');
  result.status=`${runtime}_profile_captured`;
  console.log(`CAPTURED: actual ${runtime} drag_drop 54-operation profile and original stable PNGs. Independent paired verification still required.`);
}catch(error){result.failure=error.stack;throw error;}
finally {
  if(page) {
    try{result.events=await page.evaluate(()=>dragDropOracleEvents.slice());result.mouse_events=await page.evaluate(()=>dragDropOracleMouseEvents.slice());}catch(error){result.final_event_read_error=error.message;}
    if(result.status==='failed')try {
      const bytes=await page.screenshot({animations:'disabled',scale:'device'}),file=`drag-drop-${runtime}-failure-full-dpr1.png`;
      await writeFile(join(evidence,file),bytes);result.failure_screenshot={file,png_sha256:sha256(bytes)};
    }catch(error){result.failure_screenshot_error=error.message;}
  }
  await Promise.all(responseTasks);
  const inputBytes=Buffer.from(JSON.stringify(inputEvidence(result),null,2)+'\n'),inputFile=`drag-drop-${runtime}-trusted-input.json`;
  await writeFile(join(evidence,inputFile),inputBytes);result.input_evidence={file:inputFile,sha256:sha256(inputBytes)};
  await writeFile(join(evidence,`drag-drop-${runtime}-result-dpr1.json`),JSON.stringify(result,null,2)+'\n');
  if(browser)await browser.close();if(server)await new Promise(done=>server.close(done));
}
