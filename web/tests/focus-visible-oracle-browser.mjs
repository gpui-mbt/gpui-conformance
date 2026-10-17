// PLAYWRIGHT_ROOT=... BROWSER_EVIDENCE=... node web/tests/focus-visible-oracle-browser.mjs _build/browser-lab
// Independent Rust or compiled MoonBit execution. No exported diagnostic state is used.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {decodeScreenshotRgba} from './screenshot-rgba.mjs';
import {FOCUS_VISIBLE,SOURCE_CONSTRAINTS,inspectState,assertPanelSame,assertPanelDifferent,
  assertUnchanged,assertDelivery,assertProvenance,provenanceNegativeControls,focusVisibleNegativeControls}
  from './focus-visible-comparator.mjs';
import {assertPairedProvenance,pairedProvenanceNegativeControls,expectedRuntimeFiles,
  validateFocusVisibleEvents} from './focus-visible-pair-comparator.mjs';

const sha256=data=>createHash('sha256').update(data).digest('hex');
const arguments_=process.argv.slice(2);
assert(arguments_.filter(argument=>!argument.startsWith('--')).length<=1&&
  arguments_.filter(argument=>argument.startsWith('--')).every(argument=>argument==='--candidate'),
  'Only --candidate and the fixed 800x600 DPR1 profile are supported');
const candidate=arguments_.includes('--candidate'),runtime=candidate?'moonbit':'rust';
const site=resolve(arguments_.find(argument=>!argument.startsWith('--'))||'_build/browser-lab');
const evidence=resolve(process.env.BROWSER_EVIDENCE||'_build/browser-example-evidence');
if(process.env.BROWSERS_PATH&&!process.env.PLAYWRIGHT_BROWSERS_PATH)
  process.env.PLAYWRIGHT_BROWSERS_PATH=process.env.BROWSERS_PATH;
const result={status:'failed',runtime,candidate:'not_implemented',comparison:'not_run',
  scope:candidate?'Compiled MoonBit core focus-visible port; independent screenshots and trusted inputs':'Unchanged focus_visible.rs in actual Rust WASM; independent screenshots and trusted inputs',
  profile:{width:800,height:600,dpr:1,input:'Trusted Chromium mouse, keyboard and pixel wheel'},
  source_constraints:SOURCE_CONSTRAINTS,checks:{},captures:{},operations:[],requests:[],served_requests:[],
  runtime_responses:[],console:[],errors:[],
  unverified:['MoonBit comparison','native parity','private Rust focus handles or input modality',
    'text content/OCR or cross-renderer text rasterization','other browsers/GPUs','other viewports/DPRs',
    'touch/IME','nested tab groups','OS-level keyboard navigation']};
await mkdir(evidence,{recursive:true});
let browser,server,page;
const images={},responseTasks=[];
let runtimeFiles={},paired=false;
try {
  const manifestBytes=await readFile(join(site,'build-manifest.json'));
  const catalogBytes=await readFile(join(site,'examples.json'));
  const manifest=JSON.parse(manifestBytes),catalog=JSON.parse(catalogBytes);
  result.build=manifest;result.build_manifest_sha256=sha256(manifestBytes);
  result.catalog=catalog;result.catalog_sha256=sha256(catalogBytes);
  result.build_manifest_file=`focus-visible-${runtime}-build-manifest.json`;
  result.catalog_file=`focus-visible-${runtime}-catalog.json`;
  await writeFile(join(evidence,result.build_manifest_file),manifestBytes);
  await writeFile(join(evidence,result.catalog_file),catalogBytes);
  paired=catalog.examples.some(entry=>entry.id==='focus_visible'&&entry.moonbit==='implemented');
  assert(paired||!candidate,'Candidate execution requires current compiled implementation provenance');
  result.source=paired?assertPairedProvenance(manifest,catalog):assertProvenance(manifest,catalog);
  result.provenance_negative_controls=paired?pairedProvenanceNegativeControls(manifest,catalog):provenanceNegativeControls(manifest,catalog);
  if(paired)result.candidate='implemented';
  runtimeFiles=paired?expectedRuntimeFiles(manifest,runtime):Object.fromEntries(
    ['focus_visible.js','focus_visible_bg.wasm','host.mjs'].map(file=>['rust/'+file,manifest.rust.files[file]]));
  const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css',
    '.json':'application/json','.wasm':'application/wasm','.ttf':'font/ttf'};
  server=createServer(async(request,response)=>{
    const entry={method:request.method,url:request.url};result.served_requests.push(entry);
    try {
      const url=new URL(request.url,'http://localhost');
      if(url.pathname==='/favicon.ico') {
        Object.assign(entry,{status:204,bytes:0,purpose:'No site favicon'});response.writeHead(204);response.end();return;
      }
      if(!url.pathname.startsWith('/gpui-conformance/'))throw new Error('Outside site');
      let relative=decodeURIComponent(url.pathname.slice('/gpui-conformance/'.length));
      if(!relative||relative.endsWith('/'))relative+='index.html';
      const path=resolve(site,relative);if(!path.startsWith(site+sep))throw new Error('Outside site');
      const content=await readFile(path);
      Object.assign(entry,{status:200,bytes:content.length,sha256:sha256(content)});
      response.writeHead(200,{'content-type':types[extname(path)]||'application/octet-stream','cache-control':'no-store',
        'Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp','Cross-Origin-Resource-Policy':'same-origin'});
      response.end(content);
    }catch(error){Object.assign(entry,{status:404,error:error.message});response.writeHead(404);response.end('Not found');}
  });
  await new Promise(done=>server.listen(0,'127.0.0.1',done));
  assert(process.env.PLAYWRIGHT_ROOT,'PLAYWRIGHT_ROOT must identify the installed Playwright package');
  const require=createRequire(join(process.env.PLAYWRIGHT_ROOT,'package.json'));
  const {chromium}=require('playwright');
  browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  const context=await browser.newContext({viewport:{width:800,height:600},deviceScaleFactor:1,serviceWorkers:'block'});
  page=await context.newPage();
  result.environment={browser:await browser.version(),platform:process.platform,arch:process.arch,node:process.version,
    graphics:'Chromium SwiftShader requested; actual browser console retained'};
  page.on('pageerror',error=>result.errors.push({kind:'pageerror',message:error.message}));
  page.on('console',message=>{
    result.console.push({type:message.type(),text:message.text()});
    if(message.type()==='error')result.errors.push({kind:'console',message:message.text()});
  });
  page.on('requestfailed',request=>result.errors.push({kind:'requestfailed',url:request.url(),failure:request.failure()}));
  page.on('response',response=>{
    result.requests.push({url:response.url(),status:response.status()});
    const path=new URL(response.url()).pathname.replace(/^\/gpui-conformance\//,'');
    if(Object.hasOwn(runtimeFiles,path)||(paired&&/\.(mjs|js|wasm|ttf)$/.test(path))) {
      responseTasks.push((async()=>{
        try {
          assert(Object.hasOwn(runtimeFiles,path),`Loaded unpinned runtime dependency ${path}`);
          const bytes=await response.body(),file=`focus-visible-${runtime}-asset-${path.replaceAll('/','_')}.bin`;
          await writeFile(join(evidence,file),bytes);
          result.runtime_responses.push({url:response.url(),status:response.status(),sha256:sha256(bytes),file});
        } catch(error){result.errors.push({kind:'runtime_response',url:response.url(),message:error.message});}
      })());
    }
  });
  await page.addInitScript(()=>{
    // Passive read-only transport observation. Never inject focus/application state.
    globalThis.focusVisibleOracleEvents=[];
    for(const type of ['pointermove','pointerdown','pointerup','keydown','keyup','wheel','beforeinput','input'])
      addEventListener(type,event=>{
        const entry={type,trusted:event.isTrusted,target:event.target.tagName,time:performance.now(),
          defaultPrevented:null,shiftKey:event.shiftKey,ctrlKey:event.ctrlKey,altKey:event.altKey,metaKey:event.metaKey};
        if(type==='beforeinput'||type==='input')Object.assign(entry,{inputType:event.inputType,data:event.data,isComposing:event.isComposing,cancelable:event.cancelable});
        else if(type.startsWith('key'))Object.assign(entry,{key:event.key,code:event.code,repeat:event.repeat});
        else Object.assign(entry,{x:event.clientX,y:event.clientY,button:event.button,buttons:event.buttons,
          pointerType:event.pointerType,deltaX:event.deltaX,deltaY:event.deltaY,deltaMode:event.deltaMode});
        globalThis.focusVisibleOracleEvents.push(entry);
        // Capture-listener microtasks can precede later listeners; timer observes
        // the completed browser dispatch including the upstream canvas listener.
        setTimeout(()=>{entry.defaultPrevented=event.defaultPrevented;},0);
      },{capture:true,passive:true});
  });
  const base=`http://127.0.0.1:${server.address().port}/gpui-conformance/`;
  await page.goto(base+runtime+'/?example=focus_visible');
  await page.locator(`html[data-runtime-status="${candidate?'ready':'initialized'}"]`).waitFor({timeout:60000});
  assert.equal(await page.evaluate(()=>crossOriginIsolated),true);
  assert.equal(await page.evaluate(()=>devicePixelRatio),1);
  const canvas=page.locator('canvas');
  const bounds=await canvas.boundingBox(),backing=await canvas.evaluate(element=>({width:element.width,height:element.height}));
  result.canvas={bounds,backing};
  result.initial_transport=await page.evaluate(()=>{
    const input=document.querySelector('textarea');
    return {active_tag:document.activeElement?.tagName,canvas_tab_index:document.querySelector('canvas')?.tabIndex,
      textarea:input?{readOnly:input.readOnly,disabled:input.disabled,isContentEditable:input.isContentEditable,
        spellcheck:input.spellcheck,autocomplete:input.autocomplete,autocorrect:input.getAttribute('autocorrect'),
        autocapitalize:input.getAttribute('autocapitalize'),enterkeyhint:input.getAttribute('enterkeyhint'),
        inline_style:Object.fromEntries(['position','left','top','width','height','opacity','fontSize'].map(key=>[key,input.style[key]])),
        style:(()=>{const s=getComputedStyle(input);return {position:s.position,left:s.left,top:s.top,width:s.width,height:s.height,opacity:s.opacity,fontSize:s.fontSize};})(),
        bounds:(()=>{const r=input.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};})()}:null,
      note:'Actual DOM transport observation only; never application focus evidence'};
  });
  assert.deepEqual(bounds,{x:0,y:0,width:800,height:600},'Full unscaled integer-origin canvas');
  assert.deepEqual(backing,{width:800,height:600},'DPR1 backing canvas');
  await Promise.all(responseTasks);
  const requiredFiles=candidate?['moonbit/focus_visible.mjs','moonbit/host.mjs','moonbit/render.mjs',
    'moonbit/focus-visible-host.mjs','moonbit/IBMPlexSans-Regular.ttf','moonbit/IBMPlexSans-SemiBold.ttf','load-timing.mjs']:
    ['rust/focus_visible.js','rust/focus_visible_bg.wasm','rust/host.mjs',...(paired?['load-timing.mjs']:[])];
  for(const file of requiredFiles)assert(result.runtime_responses.some(response=>
    new URL(response.url).pathname==='/gpui-conformance/'+file),`Actual browser request required for ${file}`);
  for(const response of result.runtime_responses) {
    const file=new URL(response.url).pathname.replace(/^\/gpui-conformance\//,'');
    assert.equal(response.status,200);assert.equal(response.sha256,runtimeFiles[file],`Actually executed response hash for ${file}`);
  }
  async function frames() {
    await page.evaluate(()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(()=>done()))));
  }
  async function capture(name,state,extra=()=>({})) {
    const deadline=Date.now()+30000,attempts=[];let prior=null,buffer,image,measurement,lastError,stable=false;
    do {
      buffer=await page.screenshot({animations:'disabled',scale:'device'});image=await decodeScreenshotRgba(page,buffer);
      const hash=sha256(image.data);let valid=false;
      try{measurement={state:inspectState(image,state),...extra(image)};valid=true;lastError=null;}
      catch(error){lastError=error.message;}
      attempts.push({rgba_sha256:hash,png_sha256:sha256(buffer),valid,error:lastError});
      stable=valid&&prior?.hash===hash;
      if(!stable) {prior=valid?{hash,buffer}:null;await page.waitForTimeout(100);}
    }while(!stable&&Date.now()<deadline);
    const file=`focus-visible-${runtime}-${name}-dpr1.png`;
    await writeFile(join(evidence,file),buffer);
    const stabilityFile=stable?`focus-visible-${runtime}-${name}-stable-first-dpr1.png`:null;
    if(stable)await writeFile(join(evidence,stabilityFile),prior.buffer);
    result.captures[name]={file,stability_file:stabilityFile,png_sha256:sha256(buffer),rgba_sha256:sha256(image.data),
      width:image.width,height:image.height,stable,measurement,last_error:lastError,attempts,
      stability_png_sha256:stable?sha256(prior.buffer):null,stability_rgba_sha256:stable?prior.hash:null,
      after_operation:result.operations.length,
      method:'Two identical full-viewport screenshot RGBA captures; no crop, resample, pixel replacement or application diagnostics'};
    images[name]=image;
    assert(stable,`${name}: expected pixels and two stable captures not observed: ${lastError}`);
    return image;
  }
  async function perform(name,expected,action) {
    const operation={name,expected,status:'pending_delivery'};result.operations.push(operation);
    const start=await page.evaluate(()=>focusVisibleOracleEvents.length);
    await action();
    await page.waitForFunction(({start,count})=>focusVisibleOracleEvents.length>=start+count&&
      focusVisibleOracleEvents.slice(start).every(event=>event.defaultPrevented!==null),{start,count:expected.length});
    await frames();
    operation.events=await page.evaluate(start=>focusVisibleOracleEvents.slice(start),start);
    operation.delivery=assertDelivery(operation.events,expected);
    operation.status='delivered';operation.post_delivery_animation_frames=2;
  }
  let pointer={x:0,y:0};
  async function move(name,x,y) {
    await perform(name,[{type:'pointermove',x,y}],()=>page.mouse.move(x,y));pointer={x,y};
  }
  async function mouse(name,type,button='left') {
    const number=button==='left'?0:2;
    await perform(name,[{type:type==='down'?'pointerdown':'pointerup',...pointer,button:number}],()=>page.mouse[type]({button}));
  }
  const modifiers={shiftKey:false,ctrlKey:false,altKey:false,metaKey:false};
  async function key(name,key,type='press',shift=false) {
    const domKey=key==='Space'?' ':key;
    const expected=(type==='press'?['keydown','keyup']:[type==='down'?'keydown':'keyup']).flatMap(type=>[
      {type,key:domKey,...modifiers,shiftKey:shift,repeat:false},
      ...(key==='Enter'&&type==='keydown'?[{type:'beforeinput',inputType:'insertLineBreak',data:null,isComposing:false,cancelable:true,defaultPrevented:true}]:[])]);
    await perform(name,expected,()=>page.keyboard[type](key));
  }
  async function tab(name,focus,reverse=false) {
    if(reverse)await key(name+'_shift_down','Shift','down',true);
    await key(name+'_tab','Tab','press',reverse);
    if(reverse)await key(name+'_shift_up','Shift','up',false);
    const hover=pointer.x>=32&&pointer.x<768?([208,319,430].findIndex(y=>pointer.y>=y&&pointer.y<y+64)+1):0;
    return capture(name,{focus,modality:'keyboard',hover});
  }
  async function click(name,button,secondary=false) {
    const y=[240,351,462][button-1];await move(name+'_move',100,y);
    await mouse(name+'_down','down',secondary?'right':'left');await mouse(name+'_up','up',secondary?'right':'left');
    return capture(name,{focus:button,modality:'mouse',hover:button});
  }
  async function reset(name='root_reset') {
    await move(name+'_move',8,550);await mouse(name+'_down','down');await mouse(name+'_up','up');
    return capture(name,{focus:0,modality:'mouse',hover:0});
  }
  const same=(name,a,b)=>{result.checks[name]=assertPanelSame(images[a],images[b]);};
  const different=(name,a,b)=>{result.checks[name]=assertPanelDifferent(images[a],images[b]);};
  // Chromium may dispatch one startup move at its initial (0,0) pointer before
  // the canvas exists. Preserve that prefix separately, without clearing logs.
  await page.waitForFunction(()=>focusVisibleOracleEvents.every(event=>event.defaultPrevented!==null));
  result.startup_events=await page.evaluate(()=>globalThis.focusVisibleOracleEvents.slice());
  result.operation_start=result.startup_events.length;
  await move('initial_pointer',8,8);
  await capture('initial',{focus:0,modality:'mouse',hover:0});
  for(const [name,focus] of [['tab1',1],['tab2',2],['tab3',3],['wrap1',1]])await tab(name,focus);
  for(const [name,focus] of [['reverse3',3],['reverse2',2],['reverse1',1],['reverse_wrap3',3]])await tab(name,focus,true);
  different('tab_message_changes','initial','tab1');
  for(const name of ['tab2','tab3','wrap1'])same(name+'_message','tab1',name);
  different('reverse_message_changes','tab1','reverse3');
  for(const name of ['reverse2','reverse1','reverse_wrap3'])same(name+'_message','reverse3',name);
  for(const button of [1,2,3])await click('click'+button,button);
  different('button1_vs_button2_message','click1','click2');different('button2_vs_button3_message','click2','click3');
  different('button1_vs_button3_message','click1','click3');

  await move('down2_move',100,351);await mouse('down2_event','down');
  await capture('down2',{focus:2,modality:'mouse',hover:2},image=>({panel:assertPanelSame(images.click3,image)}));
  await move('outside_up2_move',8,550);await mouse('outside_up2_event','up');
  await capture('outside_up2',{focus:2,modality:'mouse',hover:0},image=>({panel:assertPanelSame(images.down2,image)}));
  await key('unrelated_key_reenables_ring','x');
  await capture('key2',{focus:2,modality:'keyboard',hover:0},image=>({panel:assertPanelSame(images.click3,image)}));
  await move('mouse_hover2_move',100,351);
  await capture('mouse_hover2',{focus:2,modality:'mouse',hover:2});
  await key('resting_pointer_key','x');
  await capture('hover_suppressed2',{focus:2,modality:'keyboard',hover:2},image=>({unchanged:assertUnchanged(images.key2,image)}));
  await perform('keyboard_wheel',[{type:'wheel',x:100,y:351,deltaX:0,deltaY:1}],()=>page.mouse.wheel(0,1));
  await capture('keyboard_wheel2',{focus:2,modality:'keyboard',hover:2},image=>({unchanged:assertUnchanged(images.hover_suppressed2,image)}));
  await key('unmatched_release_preserves_modality','z','up');
  await capture('keyboard_release2',{focus:2,modality:'keyboard',hover:2},image=>({unchanged:assertUnchanged(images.hover_suppressed2,image)}));
  await move('move2_event',101,351);
  await capture('move2',{focus:2,modality:'mouse',hover:2},image=>({panel:assertPanelSame(images.hover_suppressed2,image)}));
  await key('modifier_only_shift_down','Shift','down',true);await key('modifier_only_shift_up','Shift','up');
  await capture('modifier_only2',{focus:2,modality:'mouse',hover:2},image=>({unchanged:assertUnchanged(images.move2,image)}));
  await tab('next_after_move3',3);
  await reset();same('root_reset_preserves_message','next_after_move3','root_reset');
  await tab('root_tab1',1);

  // Desktop textarea Enter also emits trusted beforeinput; the unchanged web
  // adapter completes an internal Enter down/up pair before physical release.
  await key('enter_down1_event','Enter','down');
  await capture('enter_down1',{focus:1,modality:'keyboard',hover:0},image=>({panel:assertPanelSame(images.click1,image),changed:assertPanelDifferent(images.root_tab1,image)}));
  await key('enter_up1_event','Enter','up');
  await capture('enter_up1',{focus:1,modality:'keyboard',hover:0},image=>({panel:assertPanelSame(images.click1,image),unchanged:assertUnchanged(images.enter_down1,image)}));
  await tab('space_before2',2);
  await key('space_down2_event','Space','down');
  await capture('space_down2',{focus:2,modality:'keyboard',hover:0},image=>({panel:assertPanelSame(images.space_before2,image)}));
  await key('space_up2_event','Space','up');
  await capture('space_up2',{focus:2,modality:'keyboard',hover:0},image=>({panel:assertPanelSame(images.click2,image),changed:assertPanelDifferent(images.space_down2,image)}));
  await tab('activation_before3',3);await key('activation3_enter','Enter');
  await capture('activation3',{focus:3,modality:'keyboard',hover:0},image=>({panel:assertPanelSame(images.click3,image)}));

  await reset('stale_key_reset');await tab('stale_key_before',1);
  await key('stale_key_space_down','Space','down');await key('stale_key_interruption','x');await key('stale_key_space_up','Space','up');
  await capture('stale_key_after',{focus:1,modality:'keyboard',hover:0},image=>({panel:assertPanelSame(images.stale_key_before,image)}));
  await tab('stale_focus_before',2);await key('stale_focus_space_down','Space','down');
  // Secondary pointer clicks move focus without replacing the message or
  // introducing another key event, isolating the focus-generation ABA guard.
  await move('stale_focus_root_move',8,550);await mouse('stale_focus_root_down','down','right');await mouse('stale_focus_root_up','up','right');
  await capture('stale_focus_root',{focus:0,modality:'mouse',hover:0},image=>({panel:assertPanelSame(images.stale_focus_before,image)}));
  await click('stale_focus_return2',2,true);same('secondary_has_no_primary_click','stale_focus_before','stale_focus_return2');
  await key('stale_focus_space_up','Space','up');
  await capture('stale_focus_after',{focus:2,modality:'mouse',hover:2},image=>({panel:assertPanelSame(images.stale_focus_before,image)}));
  await tab('focus_generation_next3',3);

  // Upstream deliberately checks activation category/generation, not key identity.
  await reset('mixed_activation_reset');await tab('mixed_activation_before1',1);
  await key('mixed_space_down','Space','down');await key('mixed_enter_up','Enter','up');
  await capture('mixed_activation_up1',{focus:1,modality:'keyboard',hover:0},image=>({panel:assertPanelSame(images.click1,image),changed:assertPanelDifferent(images.mixed_activation_before1,image)}));
  await key('mixed_space_cleanup','Space','up');
  await capture('mixed_activation_cleanup1',{focus:1,modality:'keyboard',hover:0},image=>({unchanged:assertUnchanged(images.mixed_activation_up1,image)}));

  result.negative_controls=focusVisibleNegativeControls(images,result.operations);
  result.negative_controls_capture_sha256=Object.fromEntries(Object.entries(result.captures).map(([name,capture])=>[name,capture.rgba_sha256]));
  result.transport=await page.evaluate(()=>({active_tag:document.activeElement?.tagName,
    canvas_tab_index:document.querySelector('canvas')?.tabIndex,
    note:'DOM active element is transport only and was never used to infer GPUI focus'}));
  result.events=await page.evaluate(()=>globalThis.focusVisibleOracleEvents||[]);
  await Promise.all(responseTasks);
  if(paired)validateFocusVisibleEvents(result,runtime);
  assert.deepEqual(result.errors,[],'Runtime/console/network errors fail the profile');
  result.status=candidate?'moonbit_profile_passed':'rust_oracle_passed';
  console.log(`PASS: ${runtime} focus_visible at 800x600 DPR1; actual trusted operations and screenshot predicates. Independent paired comparison NOT RUN.`);
}catch(error){result.failure=error.stack;throw error;}
finally {
  if(page) {
    try{result.events=await page.evaluate(()=>globalThis.focusVisibleOracleEvents||[]);}catch(error){result.final_event_read_error=error.message;}
    if(result.status==='failed')try {
      const buffer=await page.screenshot({animations:'disabled',scale:'device'});
      const file=`focus-visible-${runtime}-failure-full-dpr1.png`;await writeFile(join(evidence,file),buffer);
      result.failure_screenshot={file,png_sha256:sha256(buffer)};
    }catch(error){result.failure_screenshot_error=error.message;}
  }
  await Promise.all(responseTasks);
  await writeFile(join(evidence,`focus-visible-${runtime}-result-dpr1.json`),JSON.stringify(result,null,2)+'\n');
  if(browser)await browser.close();
  if(server)await new Promise(done=>server.close(done));
}
