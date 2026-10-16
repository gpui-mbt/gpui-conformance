// Actual unchanged Rust WASM discovery only. Independent verification runs afterward.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {TAB_STOP,SOURCE_CONSTRAINTS,sha256,assertProvenance,provenanceNegativeControls,
  decodePng,discoverBorder,sourceGeometry,makeProfile,assertDelivery} from './tab-stop-comparator.mjs';
assert(process.argv.length<=3,'Only a site path is accepted; the profile is fixed at 800x600 DPR1');
const site=resolve(process.argv[2]||'_build/tab-stop-browser-lab');
const evidence=resolve(process.env.BROWSER_EVIDENCE||'_build/tab-stop-oracle-evidence');
const result={status:'failed',runtime:'rust',candidate:'not_implemented',comparison:'not_run',
  conformance:'not_claimed',mode:'discovery',profile_revision:'state_specific_geometry_and_moving_edges_v2',profile:{width:800,height:600,dpr:1},
  source_constraints:SOURCE_CONSTRAINTS,captures:{},operations:[],requests:[],served_requests:[],runtime_responses:[],
  support_files:[],console:[],errors:[],decoder:{name:'Pillow',version:'12.0.0',transport:'Bounded local dimensions + raw RGBA; original PNG bytes unchanged'},
  unverified:['MoonBit counterpart/comparison','native parity','text/OCR or full-image parity',
    'unobserved fixed geometry','other browser/GPU/viewport/DPR','touch/IME','focus of group-container literal anchors']};
await mkdir(evidence,{recursive:true});let browser,server,page;
const images={},responseTasks=[];let files={};
try {
  const manifestBytes=await readFile(join(site,'build-manifest.json')),catalogBytes=await readFile(join(site,'examples.json'));
  result.build=JSON.parse(manifestBytes);result.catalog=JSON.parse(catalogBytes);
  result.source=assertProvenance(result.build,result.catalog);
  result.provenance_negative_controls=provenanceNegativeControls(result.build,result.catalog);
  for(const [name,bytes] of [['build-manifest.json',manifestBytes],['catalog.json',catalogBytes]]) {
    const file='tab-stop-rust-'+name;await writeFile(join(evidence,file),bytes);
    result[name==='catalog.json'?'catalog_evidence':'build_evidence']={file,sha256:sha256(bytes)};
  }
  const decoder=await readFile(new URL('../scripts/decode_oracle_png.py',import.meta.url));
  await writeFile(join(evidence,'tab-stop-png-decoder.py'),decoder);result.decoder.sha256=sha256(decoder);
  files={...Object.fromEntries(Object.entries(result.build.rust.files).map(([file,hash])=>['rust/'+file,hash])),
    'load-timing.mjs':result.build.moonbit_host_files_sha256['load-timing.mjs']};
  for(const path of ['rust/unchanged-source/tab_stop.rs','rust/packaging-Cargo.toml',...Object.values(result.build.rust.embedded_fonts).map(font=>'rust/'+font.file)]) {
    const bytes=await readFile(join(site,path));assert.equal(sha256(bytes),files[path]);
    const file='tab-stop-input-'+path.replaceAll('/','_')+'.bin';await writeFile(join(evidence,file),bytes);
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
  browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  const context=await browser.newContext({viewport:{width:800,height:600},deviceScaleFactor:1,serviceWorkers:'block'});page=await context.newPage();
  result.environment={browser:await browser.version(),node:process.version,platform:process.platform,arch:process.arch,
    graphics:'SwiftShader requested; actual console retained'};
  page.on('pageerror',error=>result.errors.push({kind:'pageerror',message:error.message}));
  page.on('console',message=>{result.console.push({type:message.type(),text:message.text()});
    if(message.type()==='error')result.errors.push({kind:'console',message:message.text()});});
  page.on('requestfailed',request=>result.errors.push({kind:'requestfailed',url:request.url(),failure:request.failure()}));
  page.on('response',response=>{
    result.requests.push({url:response.url(),status:response.status()});
    const path=new URL(response.url()).pathname.replace(/^\/gpui-conformance\//,'');
    if(/\.(mjs|js|wasm|ttf)$/.test(path))responseTasks.push((async()=>{
      try {assert(Object.hasOwn(files,path),`Unpinned browser runtime dependency ${path}`);
        const bytes=await response.body(),file='tab-stop-rust-asset-'+path.replaceAll('/','_')+'.bin';
        await writeFile(join(evidence,file),bytes);result.runtime_responses.push({path,url:response.url(),status:response.status(),file,sha256:sha256(bytes),bytes:bytes.length});
      }catch(error){result.errors.push({kind:'runtime_response',url:response.url(),message:error.message});}
    })());
  });
  await page.addInitScript(()=>{
    globalThis.tabStopOracleEvents=[];
    for(const type of ['pointermove','pointerdown','pointerup','keydown','keyup','beforeinput','input'])
      addEventListener(type,event=>{
        const entry={type,trusted:event.isTrusted,target:event.target.tagName,time:performance.now(),defaultPrevented:null,
          shiftKey:event.shiftKey,ctrlKey:event.ctrlKey,altKey:event.altKey,metaKey:event.metaKey};
        if(type.startsWith('key'))Object.assign(entry,{key:event.key,code:event.code,repeat:event.repeat});
        else if(type==='beforeinput'||type==='input')Object.assign(entry,{inputType:event.inputType,data:event.data,isComposing:event.isComposing,cancelable:event.cancelable});
        else Object.assign(entry,{x:event.clientX,y:event.clientY,button:event.button,buttons:event.buttons,pointerType:event.pointerType});
        globalThis.tabStopOracleEvents.push(entry);setTimeout(()=>{entry.defaultPrevented=event.defaultPrevented;},0);
      },{capture:true,passive:true});
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/gpui-conformance/rust/?example=tab_stop`);
  await page.locator('html[data-runtime-status="initialized"]').waitFor({timeout:60000});
  assert.equal(await page.evaluate(()=>crossOriginIsolated),true);assert.equal(await page.evaluate(()=>devicePixelRatio),1);
  const canvas=page.locator('canvas');result.canvas={bounds:await canvas.boundingBox(),backing:await canvas.evaluate(element=>({width:element.width,height:element.height}))};
  assert.deepEqual(result.canvas,{bounds:{x:0,y:0,width:800,height:600},backing:{width:800,height:600}});
  result.transport=await page.evaluate(()=>({active_tag:document.activeElement?.tagName,canvas_tab_index:document.querySelector('canvas')?.tabIndex,
    note:'Transport observation only, never application-focus evidence'}));
  const frames=()=>page.evaluate(()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done))));
  async function capture(name) {
    const attempts=[];result.captures[name]={attempts,after_operation:result.operations.length};let previous;
    const deadline=Date.now()+30000;
    do {
      const bytes=await page.screenshot({animations:'disabled',scale:'device'});
      const file=`tab-stop-rust-${name}-sample-${attempts.length+1}-dpr1.png`;
      await writeFile(join(evidence,file),bytes);
      const attempt={file,png_sha256:sha256(bytes),bytes:bytes.length};attempts.push(attempt);
      // The PNG has already been retained if decoding fails.
      const image=decodePng(bytes);Object.assign(attempt,{rgba_sha256:sha256(image.data),width:image.width,height:image.height,
        observed_blue_border:discoverBorder(image)});
      if(previous?.rgba_sha256===attempt.rgba_sha256) {
        Object.assign(result.captures[name],{file,stability_file:previous.file,stable:true,png_sha256:attempt.png_sha256,
          stability_png_sha256:previous.png_sha256,rgba_sha256:attempt.rgba_sha256,stability_rgba_sha256:previous.rgba_sha256,
          width:800,height:600,observed_blue_border:attempt.observed_blue_border,
          method:'Two independently requested original full-viewport PNGs with identical pinned-Pillow decoded RGBA; no crop/resample/substitution'});
        images[name]=image;return;
      }
      previous=attempt;await page.waitForTimeout(100);
    }while(Date.now()<deadline);
    throw new Error(`${name}: two identical decoded-RGBA samples were not observed`);
  }
  async function perform(operation) {
    const record={name:operation.name,expected:operation.expected,status:'pending_delivery'};result.operations.push(record);
    const start=await page.evaluate(()=>tabStopOracleEvents.length);const action=operation.action;
    if(action.kind==='move')await page.mouse.move(action.x,action.y);
    else if(action.kind==='mouse')await page.mouse[action.down?'down':'up']({button:'left'});
    else await page.keyboard[action.type](action.key);
    await page.waitForFunction(({start,count})=>tabStopOracleEvents.length>=start+count&&tabStopOracleEvents.slice(start).every(event=>event.defaultPrevented!==null),{start,count:operation.expected.length});
    await frames();record.events=await page.evaluate(start=>tabStopOracleEvents.slice(start),start);
    record.delivery=assertDelivery(record.events,operation.expected);record.status='delivered';record.post_delivery_animation_frames=2;
  }
  await page.waitForFunction(()=>tabStopOracleEvents.every(event=>event.defaultPrevented!==null));
  result.startup_events=await page.evaluate(()=>tabStopOracleEvents.slice());result.operation_start=result.startup_events.length;
  async function execute(profile,start=0) {
    for(let index=start;index<profile.operations.length;index++) {
      await perform(profile.operations[index]);
      for(const [name,spec] of Object.entries(profile.captures))if(spec.after_operation===index+1)await capture(name);
    }
  }
  const discovery=makeProfile();await execute(discovery);
  // A failed source-geometry hypothesis cannot erase the complete discovery sequence.
  // It blocks the coordinate-dependent click extension and remains an explicit failure.
  result.discovered_geometry=sourceGeometry(images);
  result.adaptive_plans=[];
  while(true) {
    const plan=makeProfile(result.discovered_geometry.frames);
    result.adaptive_plans.push({through_operation:plan.operations.length,complete:plan.complete,blocked_on_capture:plan.blocked_on_capture||null});
    assert(plan.operations.length>result.operations.length,'Adaptive source profile must advance using a newly retained current-frame capture');
    await execute(plan,result.operations.length);
    result.discovered_geometry=sourceGeometry(images);
    if(plan.complete)break;
  }
  await Promise.all(responseTasks);
  for(const path of ['rust/host.mjs','rust/tab_stop.js','rust/tab_stop_bg.wasm','load-timing.mjs'])
    assert(result.runtime_responses.some(response=>response.path===path),`Actual browser response required for ${path}`);
  for(const response of result.runtime_responses){assert.equal(response.status,200);assert.equal(response.sha256,files[response.path]);}
  assert.deepEqual(result.errors,[],'Runtime/console/network errors fail discovery');
  result.status='rust_discovery_captured';
  console.log('CAPTURED: unchanged tab_stop.rs trusted sequence and original stable PNGs. Conformance not claimed; independent verifier still required.');
}catch(error){result.failure=error.stack;throw error;}
finally {
  if(page) {
    try{result.events=await page.evaluate(()=>tabStopOracleEvents.slice());}catch(error){result.final_event_read_error=error.message;}
    if(result.status==='failed')try {
      const bytes=await page.screenshot({animations:'disabled',scale:'device'}),file='tab-stop-rust-failure-full-dpr1.png';
      await writeFile(join(evidence,file),bytes);result.failure_screenshot={file,png_sha256:sha256(bytes)};
    }catch(error){result.failure_screenshot_error=error.message;}
  }
  await Promise.all(responseTasks);
  await writeFile(join(evidence,'tab-stop-rust-result-dpr1.json'),JSON.stringify(result,null,2)+'\n');
  if(browser)await browser.close();if(server)await new Promise(done=>server.close(done));
}
