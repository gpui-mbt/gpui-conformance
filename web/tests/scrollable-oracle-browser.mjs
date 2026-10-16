// Rust-only unchanged-source oracle. No MoonBit comparison or private state.
// PLAYWRIGHT_ROOT=... PLAYWRIGHT_BROWSERS_PATH=... BROWSER_EVIDENCE=...
// node web/tests/scrollable-oracle-browser.mjs _build/browser-lab
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {SCROLLABLE,SOURCE_CONSTRAINTS,inspectInitial,assertTranslation,assertUnchanged,
  assertClipping,assertHover,assertSameFill,assertHorizontalEnd,assertVerticalEnd,
  assertWheelDelivery,scrollableNegativeControls} from './scrollable-comparator.mjs';

const sha256=data=>createHash('sha256').update(data).digest('hex');
const site=resolve(process.argv.slice(2).find(arg=>!arg.startsWith('--'))||'_build/browser-lab');
const evidence=resolve(process.env.BROWSER_EVIDENCE||'_build/browser-example-evidence');
const dpr=Number(process.argv.find(arg=>arg.startsWith('--dpr='))?.slice(6)||1);
if(process.env.BROWSERS_PATH&&!process.env.PLAYWRIGHT_BROWSERS_PATH)
  process.env.PLAYWRIGHT_BROWSERS_PATH=process.env.BROWSERS_PATH;
const result={status:'failed',scope:'unchanged scrollable.rs; actual Rust WASM; screenshot-derived browser behavior only',
  candidate:'not_implemented',comparison:'not_run',profile:{width:500,height:500,dpr,wheel:'trusted Chromium pixel wheel'},
  source_constraints:SOURCE_CONSTRAINTS,checks:{},captures:{},operations:[],requests:[],console:[],errors:[],
  unverified:['MoonBit comparison','native parity','private Rust scroll offsets','text rasterization parity',
    'other browsers/GPUs','other viewport sizes','other DPRs','line/page wheel deltas','diagonal wheel gestures','touch/momentum']};
await mkdir(evidence,{recursive:true});
let browser,server,page;
const images={};
try {
  const manifest=JSON.parse(await readFile(join(site,'build-manifest.json'),'utf8'));
  result.build=manifest;
  assert.equal(manifest.upstream.revision,SCROLLABLE.revision);
  assert.equal(manifest.rust_bundled,true,'Actual Rust WASM must be bundled');
  assert.equal(manifest.rust.source_modified,false,'Upstream Rust source must be unchanged');
  assert.equal(manifest.rust.packaging.upstream_files_modified,false);
  const record=manifest.rust_oracle_only?.find(entry=>entry.id==='scrollable');
  assert(record,'Explicit Rust-only oracle provenance record required');
  for(const [key,value] of Object.entries({source:SCROLLABLE.source,source_blob:SCROLLABLE.sourceBlob,
    upstream_revision:SCROLLABLE.revision,width:500,height:500,dpr,status:'rust_oracle_only',candidate:'not_implemented'}))
    assert.equal(record[key],value,`Oracle provenance ${key}`);
  result.source=record;
  assert(manifest.rust_implemented.includes('scrollable'));
  const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css',
    '.json':'application/json','.wasm':'application/wasm','.ttf':'font/ttf'};
  server=createServer(async(request,response)=>{
    try {
      const url=new URL(request.url,'http://localhost');
      if(!url.pathname.startsWith('/gpui-conformance/'))throw new Error('Outside site');
      let relative=decodeURIComponent(url.pathname.slice('/gpui-conformance/'.length));
      if(!relative||relative.endsWith('/'))relative+='index.html';
      const path=resolve(site,relative);if(!path.startsWith(site+sep))throw new Error('Outside site');
      const content=await readFile(path);
      response.writeHead(200,{'content-type':types[extname(path)]||'application/octet-stream',
        'Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp','Cross-Origin-Resource-Policy':'same-origin'});
      response.end(content);
    }catch{response.writeHead(404);response.end('Not found');}
  });
  await new Promise(done=>server.listen(0,'127.0.0.1',done));
  assert(process.env.PLAYWRIGHT_ROOT,'PLAYWRIGHT_ROOT must identify the installed Playwright package');
  const require=createRequire(join(process.env.PLAYWRIGHT_ROOT,'package.json'));
  const {chromium}=require('playwright');
  browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  const context=await browser.newContext({viewport:{width:500,height:500},deviceScaleFactor:dpr});
  page=await context.newPage();
  result.environment={browser:await browser.version(),platform:process.platform,arch:process.arch,node:process.version,
    graphics:'Chromium SwiftShader requested; raw console retained'};
  page.on('pageerror',error=>result.errors.push(error.message));
  page.on('console',message=>result.console.push({type:message.type(),text:message.text()}));
  page.on('response',response=>result.requests.push({url:response.url(),status:response.status()}));
  await page.addInitScript(()=>{
    // Read-only transport observation. No fabricated application state or scroll API.
    globalThis.scrollableOracleEvents=[];
    globalThis.scrollableOraclePointers=[];
    for(const type of ['pointermove','pointerleave'])addEventListener(type,event=>{
      globalThis.scrollableOraclePointers.push({type,x:event.clientX,y:event.clientY,
        trusted:event.isTrusted,target:event.target.tagName,pointerType:event.pointerType,time:performance.now()});
    },{capture:true,passive:true});
    addEventListener('wheel',event=>{
      const entry={type:'wheel',x:event.clientX,y:event.clientY,deltaX:event.deltaX,deltaY:event.deltaY,
        deltaMode:event.deltaMode,trusted:event.isTrusted,target:event.target.tagName,time:performance.now(),defaultPrevented:null};
      globalThis.scrollableOracleEvents.push(entry);
      // A timer runs after the complete dispatch, including the canvas listener.
      // A capture-listener microtask can run before later propagation listeners.
      setTimeout(()=>{entry.defaultPrevented=event.defaultPrevented;},0);
    },{capture:true,passive:true});
  });
  const base=`http://127.0.0.1:${server.address().port}/gpui-conformance/`;
  await page.goto(base+'rust/?example=scrollable');
  await page.locator('html[data-runtime-status="initialized"]').waitFor({timeout:60000});
  assert.equal(await page.evaluate(()=>crossOriginIsolated),true);
  assert.equal(await page.evaluate(()=>devicePixelRatio),dpr);
  const canvas=page.locator('canvas');
  const bounds=await canvas.boundingBox(),backing=await canvas.evaluate(c=>({width:c.width,height:c.height}));
  result.canvas={bounds,backing};
  assert.deepEqual(bounds,{x:0,y:0,width:500,height:500},'Integer origin and complete 500x500 canvas');
  assert.deepEqual(backing,{width:500*dpr,height:500*dpr},'No browser rescaling of the backing canvas');
  for(const file of ['scrollable.js','scrollable_bg.wasm']) {
    assert(result.requests.some(r=>new URL(r.url).pathname.endsWith('/'+file)&&r.status===200),`Actual runtime request for ${file}`);
    const response=await page.request.get(base+'rust/'+file);assert.equal(response.status(),200);
    assert.equal(sha256(await response.body()),manifest.rust.files[file],`Served ${file} must match manifest hash`);
  }
  async function decode(buffer) {
    const image=await page.evaluate(async url=>{
      const source=new Image();source.src=url;await source.decode();
      const target=document.createElement('canvas');target.width=source.width;target.height=source.height;
      const ctx=target.getContext('2d',{willReadFrequently:true});ctx.drawImage(source,0,0);
      return {width:source.width,height:source.height,data:Array.from(ctx.getImageData(0,0,source.width,source.height).data)};
    },'data:image/png;base64,'+buffer.toString('base64'));
    image.data=Uint8Array.from(image.data);return image;
  }
  async function frames() {
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  }
  async function capture(name,predicate=()=>true) {
    const deadline=Date.now()+30000;let previous=null,lastError,buffer,image,measurement,stable=false;
    do {
      buffer=await page.screenshot({animations:'disabled',scale:'device'});image=await decode(buffer);
      assert.equal(image.width,500*dpr);assert.equal(image.height,500*dpr);
      const hash=sha256(image.data);let valid=false;
      try{measurement=predicate(image);valid=true;lastError=null;}catch(error){lastError=error.message;}
      stable=valid&&hash===previous;previous=valid?hash:null;
      if(!stable)await page.waitForTimeout(100);
    }while(!stable&&Date.now()<deadline);
    const file=`scrollable-rust-${name}-dpr${dpr}.png`;
    await writeFile(join(evidence,file),buffer);
    result.captures[name]={file,png_sha256:sha256(buffer),rgba_sha256:sha256(image.data),
      width:image.width,height:image.height,stable,measurement,last_error:lastError,
      method:'full viewport screenshot; integer canvas origin; no cropping, resampling or replacement'};
    images[name]=image;
    assert(stable,`${name}: expected pixel predicate and two stable captures not observed: ${lastError}`);
    return image;
  }
  async function move(x,y){await page.mouse.move(x,y);await frames();}
  async function wheel(name,x,y,deltaX,deltaY,predicate) {
    const operation={name,x,y,deltaX,deltaY,status:'pending_delivery'};result.operations.push(operation);
    await move(x,y);
    const count=await page.evaluate(()=>scrollableOracleEvents.length);
    await page.mouse.wheel(deltaX,deltaY);
    await page.waitForFunction(count=>scrollableOracleEvents.length>count&&scrollableOracleEvents.slice(count).every(e=>e.defaultPrevented!==null),count);
    await frames();
    const events=await page.evaluate(count=>scrollableOracleEvents.slice(count),count);
    const delivery=assertWheelDelivery(events,{x,y,deltaX,deltaY});
    Object.assign(operation,{delivery,post_delivery_animation_frames:2,status:'pending_pixels'});
    const image=await capture(name,predicate);operation.status='passed';return image;
  }
  await move(8,300);
  const initialUnhover=await capture('initial_unhover',image=>inspectInitial(image,dpr));
  const initial=inspectInitial(initialUnhover,dpr);result.initial=initial;
  const g=initial.geometry.green,inside={x:100,y:g.y+75};
  await move(inside.x,inside.y);
  // This source's hover child is anonymous: pointer moves update hitboxes but
  // cannot notify persistent hover state. A genuine parent wheel notification
  // redraws it. At the top boundary the prepaint clamp restores the same layout.
  const moveOnly=await capture('pointer_only',image=>assertUnchanged(initialUnhover,image,dpr));
  const pointerDelivery=await page.evaluate(()=>scrollableOraclePointers);
  for(const point of [{x:8,y:300},inside])assert(pointerDelivery.some(event=>
    event.type==='pointermove'&&event.trusted&&event.target==='CANVAS'&&
    event.pointerType==='mouse'&&event.x===point.x&&event.y===point.y),
    `Trusted pointer delivery required at ${point.x},${point.y}`);
  result.checks.initial_pointer_delivery={status:'passed',events:pointerDelivery};
  result.checks.anonymous_pointer_no_redraw=assertUnchanged(initialUnhover,moveOnly,dpr);
  const initialHover=await wheel('initial_hover',inside.x,inside.y,0,-1,image=>{
    // A new background can change antialiased neutral-ink thresholds. Compare
    // opaque border layout here, keeping strict ink-shape checks for scrolling
    // between frames with the same hover fill below.
    assert.deepEqual(inspectInitial(image,dpr).geometry,initial.geometry);
    return assertHover(initialUnhover,image,initial,dpr);
  });
  result.checks.initial_hover=assertHover(initialUnhover,initialHover,initial,dpr);
  const x12=await wheel('x12',inside.x,inside.y,12,0,image=>assertTranslation(initialHover,image,initial,{afterX:-12},dpr));
  result.checks.horizontal=assertTranslation(initialHover,x12,initial,{afterX:-12},dpr);
  await move(g.x-4,inside.y);
  await capture('clipped_pointer_only',image=>assertUnchanged(x12,image,dpr));
  const x12Unhover=await wheel('x12_unhover',g.x-4,inside.y,0,-1,image=>{
    assertClipping(initialUnhover,image,initial,dpr);return assertSameFill(initialUnhover,image,initial,dpr);
  });
  result.checks.clipping=assertClipping(initialUnhover,x12Unhover,initial,dpr);
  result.checks.clipped_pointer=assertSameFill(initialUnhover,x12Unhover,initial,dpr);
  result.checks.hover_after_scroll=assertHover(x12Unhover,x12,initial,dpr);
  await move(inside.x,inside.y);
  await wheel('x12_hover_restored',inside.x,inside.y,0,-1,image=>assertUnchanged(x12,image,dpr));
  const y12=await wheel('y12',inside.x,inside.y,0,12,image=>assertTranslation(x12,image,initial,{beforeX:-12,afterX:-12,afterY:-12},dpr));
  result.checks.vertical_propagation=assertTranslation(x12,y12,initial,{beforeX:-12,afterX:-12,afterY:-12},dpr);
  await move(8,inside.y);
  // A clamped X wheel on the outer viewport redraws the new hover state without
  // changing its existing Y offset; the next identical wheel must be unchanged.
  const outsideBefore=await wheel('outside_before',8,inside.y,12,0);
  const outsideAfter=await wheel('outside_x',8,inside.y,12,0,image=>assertUnchanged(outsideBefore,image,dpr));
  result.checks.outside_inner_wheel=assertUnchanged(outsideBefore,outsideAfter,dpr);
  await wheel('vertical_top_restore',8,inside.y,0,-100000,image=>assertUnchanged(x12Unhover,image,dpr));
  const horizontalEnd=await wheel('horizontal_end',inside.x,inside.y,100000,0,image=>assertHorizontalEnd(image,initial,dpr));
  result.checks.horizontal_endpoint=assertHorizontalEnd(horizontalEnd,initial,dpr);
  await wheel('horizontal_end_repeat',inside.x,inside.y,100000,0,image=>assertUnchanged(horizontalEnd,image,dpr));
  await wheel('horizontal_top_restore',inside.x,inside.y,-100000,0,image=>assertUnchanged(initialHover,image,dpr));
  await wheel('horizontal_top_repeat',inside.x,inside.y,-100000,0,image=>assertUnchanged(initialHover,image,dpr));
  const verticalEnd=await wheel('vertical_end',8,300,0,100000,image=>assertVerticalEnd(image,dpr));
  result.checks.vertical_endpoint=assertVerticalEnd(verticalEnd,dpr);
  await wheel('vertical_end_repeat',8,300,0,100000,image=>assertUnchanged(verticalEnd,image,dpr));
  await wheel('vertical_top_return',8,300,0,-100000,image=>assertUnchanged(initialUnhover,image,dpr));
  await wheel('vertical_top_repeat',8,300,0,-100000,image=>assertUnchanged(initialUnhover,image,dpr));
  result.negative_controls=scrollableNegativeControls(images,initial,dpr);
  assert.deepEqual(result.errors,[],'Runtime errors are not allowed');
  result.status='rust_oracle_passed';
  console.log(`PASS: unchanged Rust scrollable screenshot translations, clipping/hover, wheel delivery and endpoint recovery at DPR ${dpr}. MoonBit NOT IMPLEMENTED; comparison NOT RUN.`);
}catch(error){result.failure=error.stack;throw error;}
finally {
  if(page) {
    try{result.events=await page.evaluate(()=>globalThis.scrollableOracleEvents||[]);}catch{}
    try{result.pointer_events=await page.evaluate(()=>globalThis.scrollableOraclePointers||[]);}catch{}
  }
  await writeFile(join(evidence,`scrollable-rust-result-dpr${dpr}.json`),JSON.stringify(result,null,2)+'\n');
  if(browser)await browser.close();
  if(server)await new Promise(done=>server.close(done));
}
