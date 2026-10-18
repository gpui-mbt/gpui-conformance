import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {mkdir, writeFile} from 'node:fs/promises';
import {join} from 'node:path';

// Source-specific interaction qualification, never a pixel-parity oracle.
export const profiles = Object.freeze([
  {width:800,height:600,dpr:1,kind:'declared-source-profile'},
  {width:480,height:600,dpr:1.25,kind:'narrow-fractional-smoke'},
]);
export const limits = Object.freeze({captures:160,derivedImages:44,ocrRuns:204,events:128,ocrBytes:4*1024*1024,ocrMs:8000,runMs:120000});
export class ObservationUnavailable extends Error {}
const normalize = text => text.toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
export function parseTsv(tsv, pass='original') {
  return tsv.split(/\r?\n/).slice(1).filter(Boolean).map(line=>{
    const c=line.split('\t');
    return {pass,level:Number(c[0]),line:pass+'/'+c.slice(1,5).join('/'),x:Number(c[6]),y:Number(c[7]),
      width:Number(c[8]),height:Number(c[9]),confidence:Number(c[10]),text:c.slice(11).join('\t')};
  }).filter(w=>w.level===5 && w.confidence>=40 && normalize(w.text) &&
    [w.x,w.y,w.width,w.height].every(Number.isFinite) && w.width>0 && w.height>0);
}
export function phraseBox(words, phrase, dpr=1) {
  const wanted=normalize(phrase).split(' '), found=[];
  for(let i=0;i<words.length;i++) {
    const run=words.slice(i,i+wanted.length);
    if(run.length!==wanted.length || run.some(w=>w.line!==run[0].line) ||
      run.map(w=>normalize(w.text)).join(' ')!==wanted.join(' '))continue;
    const x=Math.min(...run.map(w=>w.x)), y=Math.min(...run.map(w=>w.y));
    const right=Math.max(...run.map(w=>w.x+w.width)),bottom=Math.max(...run.map(w=>w.y+w.height));
    found.push({pass:run[0].pass,x:(x+right)/2,y:(y+bottom)/2,width:right-x,height:bottom-y});
  }
  // Only merge two passes' observations of the same spatial phrase. Never
  // hide two occurrences within one pass or combine words across passes.
  const unique=[];
  for(const box of found) {
    const matches=unique.filter(other=>{
      const intersection=Math.max(0,Math.min(box.x+box.width/2,other.x+other.width/2)-Math.max(box.x-box.width/2,other.x-other.width/2))*
        Math.max(0,Math.min(box.y+box.height/2,other.y+other.height/2)-Math.max(box.y-box.height/2,other.y-other.height/2));
      return !other.passes.has(box.pass) && intersection/(box.width*box.height+other.width*other.height-intersection)>=0.8;
    });
    if(matches.length===1)matches[0].passes.add(box.pass);
    else unique.push({...box,passes:new Set([box.pass])});
  }
  if(unique.length!==1)throw new ObservationUnavailable(`Expected one visible OCR phrase ${JSON.stringify(phrase)}; observed ${unique.length}`);
  const {x,y,width,height}=unique[0];return {x:x/dpr,y:y/dpr,width:width/dpr,height:height/dpr};
}
export function visibleState(words, pixels, parent, child) {
  const text=normalize(words.map(w=>w.text).join(' '));
  if(!text.includes('popover'))throw new ObservationUnavailable('No reliable Popover text observed');
  if(parent && !text.includes('first level'))throw new ObservationUnavailable('First-level label not observable');
  if(child && !text.includes('second level'))throw new ObservationUnavailable('Second-level label not observable');
  if(!parent && text.includes('first level'))throw new Error('First-level popup remains visible');
  if(!child && text.includes('second level'))throw new Error('Second-level popup remains visible');
  assert.equal(pixels.blueBorder>20,child,'Saturated source child-border ink must agree with visible child state');
  if(!parent && !text.includes('default opened'))throw new ObservationUnavailable('Always-open default label not observable');
}

// Called only on a retained screenshot data URL, using an unattached canvas.
// No application canvas, runtime state, dimensions, or input is changed.
export async function inverseScreenshot(data) {
  const image=new Image();image.src=data;await image.decode();
  const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
  const context=canvas.getContext('2d');context.drawImage(image,0,0);
  const pixels=context.getImageData(0,0,canvas.width,canvas.height);
  for(let i=0;i<pixels.data.length;i+=4)for(let channel=0;channel<3;channel++)
    pixels.data[i+channel]=255-pixels.data[i+channel];
  context.putImageData(pixels,0,0);return canvas.toDataURL('image/png');
}

// Passive DOM diagnostics only. A single independently owned ResizeObserver
// is disconnected after its first delivery, error, or two-second timeout.
export async function measureCanvasGeometry(canvas) {
  const snapshot=()=>{const rect=canvas.getBoundingClientRect(),style=getComputedStyle(canvas),visual=window.visualViewport;
  return {window_dpr:window.devicePixelRatio,inner_width:window.innerWidth,inner_height:window.innerHeight,
    canvas:{backing_width:canvas.width,backing_height:canvas.height,client_width:canvas.clientWidth,client_height:canvas.clientHeight,
      css_rect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},
      style:{width:style.width,height:style.height,transform:style.transform,zoom:style.zoom}},
    visual_viewport:visual?{width:visual.width,height:visual.height,scale:visual.scale,
      offset_left:visual.offsetLeft,offset_top:visual.offsetTop,page_left:visual.pageLeft,page_top:visual.pageTop}:null};};
  const geometry={};
  geometry.resize_observer=await new Promise(resolve=>{
    let observer,timer,finished=false;
    const finish=value=>{if(finished)return;finished=true;clearTimeout(timer);observer?.disconnect();resolve(value);};
    timer=setTimeout(()=>finish({status:'timeout',timeout_ms:2000}),2000);
    try {
      observer=new ResizeObserver(entries=>{
        try {
          const entry=entries.find(entry=>entry.target===canvas);
          if(!entry){finish({status:'unavailable',reason:'No canvas entry'});return;}
          const boxes=value=>value?Array.from(value).map(box=>({inline_size:box.inlineSize,block_size:box.blockSize})):null;
          finish({status:'observed',content_rect:{x:entry.contentRect.x,y:entry.contentRect.y,
            width:entry.contentRect.width,height:entry.contentRect.height},
            content_box:boxes(entry.contentBoxSize),device_pixel_content_box:boxes(entry.devicePixelContentBoxSize)});
        }catch(error){finish({status:'unavailable',reason:String(error)});}
      });
      observer.observe(canvas,{box:'device-pixel-content-box'});
    }catch(error){finish({status:'unavailable',reason:String(error)});}
  });
  return {...snapshot(),...geometry};
}

// Two source-independent blank pages diagnose context emulation versus browser
// launch scale. Neither page loads or qualifies application code. At most one
// extra browser is launched, and both pages/browser are closed even on failure.
export async function probeScaleGeometry({browser,directory}) {
  const probe={purpose:'diagnostics only; original application profile and gates unchanged',captures:0,runs:[]};
  for(const mode of ['context-only','forced-launch']) {
    const record={mode,status:'running'};probe.runs.push(record);let owned,page;
    try {
      const active=mode==='context-only'?browser:(owned=await browser.browserType().launch({headless:true,timeout:15000,
        args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--force-device-scale-factor=1.25']}));
      record.browser=await active.version();
      page=await active.newPage({viewport:{width:480,height:600},deviceScaleFactor:1.25});
      page.setDefaultTimeout(5000);page.setDefaultNavigationTimeout(5000);
      await page.setContent('<!doctype html><style>html,body{margin:0;width:100%;height:100%;overflow:hidden}canvas{display:block;width:480px;height:600px}</style><canvas width="480" height="600"></canvas>');
      record.geometry=await page.locator('canvas').evaluate(measureCanvasGeometry);
      assert(probe.captures<2,'Blank-page probe capture cap exceeded');probe.captures++;
      const name='scale-probe-'+mode+'.png',png=await page.screenshot({path:join(directory,name),timeout:5000});
      record.screenshot={image:name,width:png.readUInt32BE(16),height:png.readUInt32BE(20),sha256:createHash('sha256').update(png).digest('hex')};
      record.status='observed';
    }catch(error){record.status='unavailable';record.failure=error.stack;
    }finally{if(page)await page.close().catch(()=>{});if(owned)await owned.close().catch(()=>{});}
  }
  return probe;
}

export const fractionalLaunchOptions = Object.freeze({headless:true,timeout:15000,
  args:Object.freeze(['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--force-device-scale-factor=1.25'])});

// A harness-environment correction, supported by the retained context-only
// failure and blank-page measurements. The same physical-scale browser runs
// BOTH runtimes; neither their source nor their event coordinates are changed.
export async function withProfileBrowser(browser,profile,work) {
  if(profile.dpr===1)return work(browser,{mode:'inherited-DPR1-launch',requested_args:null,browser:await browser.version()});
  assert.equal(profile.dpr,1.25,'Only the declared fractional profile has a physical launch');
  const options={...fractionalLaunchOptions,args:[...fractionalLaunchOptions.args]};
  const owned=await browser.browserType().launch(options);
  try {return await work(owned,{mode:'coherent-physical-scale-launch',requested_args:options.args,
    headless:options.headless,timeout_ms:options.timeout,browser:await owned.version()});}
  finally {await owned.close();}
}

export function assertProfileGeometry(geometry,profile) {
  const {width,height,dpr}=profile,backing=[Math.round(width*dpr),Math.round(height*dpr)];
  assert.equal(geometry.window_dpr,dpr,'Actual window DPR must match the declared profile');
  assert.deepEqual([geometry.inner_width,geometry.inner_height],[width,height],'Actual CSS viewport must match the profile');
  const canvas=geometry.canvas;
  assert(canvas,'Actual canvas geometry must be observed');
  assert.deepEqual([canvas.backing_width,canvas.backing_height],backing,'Canvas backing must agree with CSS size × DPR');
  assert.deepEqual(canvas.css_rect,{x:0,y:0,width,height},'Canvas CSS rect must fill the declared viewport');
  assert.deepEqual([canvas.client_width,canvas.client_height],[width,height],'Canvas client size must match CSS viewport');
  assert.equal(canvas.style.transform,'none','Qualification forbids transformed canvas coordinates');
  assert.equal(canvas.style.zoom,'1','Qualification forbids canvas zoom compensation');
  const observer=geometry.resize_observer;
  assert.equal(observer?.status,'observed','ResizeObserver device-pixel geometry must actually be observed');
  assert.deepEqual(observer.content_rect,{x:0,y:0,width,height},'ResizeObserver CSS content rect must agree');
  assert.deepEqual(observer.content_box,[{inline_size:width,block_size:height}],'ResizeObserver CSS content box must agree');
  assert.deepEqual(observer.device_pixel_content_box,[{inline_size:backing[0],block_size:backing[1]}],
    'ResizeObserver device-pixel box must agree with CSS size × DPR; context-only emulation is insufficient');
  assert.deepEqual(geometry.visual_viewport,{width,height,scale:1,offset_left:0,offset_top:0,page_left:0,page_top:0},
    'Visual viewport must not introduce zoom or offsets');
}

export async function checkPopoverPair({browser,page,evidence,paired}) {
  const directory=join(evidence,'popover');await mkdir(directory,{recursive:true});
  const result={status:'running',environment_correction:'Fractional profile uses proven coherent physical browser launch for both runtimes; prior context-only emulation failure is retained separately',source_blob:'7678a6a3ed865d9874b72cb99b473a115591d35c',
    comparison:'source-specific observed interactions and same-runtime image restoration only; pixel, shaping, callback-count, native and arbitrary-viewport parity unverified',
    interrupted_press:'not_run: no reliable cross-runtime native focus-loss oracle',profiles:[],captures:0,derived_images:0,ocr_runs:0};
  try {
    result.scale_probe=await probeScaleGeometry({browser,directory});
    console.log('Popover scale diagnostic: '+JSON.stringify(result.scale_probe));
    await page.selectOption('#fixture','popover');
    const urls={moon:await page.locator('#moon-frame').getAttribute('src')};
    if(paired)urls.rust=await page.locator('#rust-frame').getAttribute('src');
    for(const profile of profiles)await withProfileBrowser(browser,profile,async(activeBrowser,launch)=>{
      for(const [side,url] of Object.entries(urls)) {
      assert(url && new URL(url,page.url()).searchParams.get('example')==='popover');
      assert.equal(new URL(url,page.url()).origin,new URL(page.url()).origin);
      const run={side,...profile,launch,status:'running',stages:[],actions:[],requests:[],errors:[],console:[]};
      result.profiles.push(run);
      const p=await activeBrowser.newPage({viewport:{width:profile.width,height:profile.height},deviceScaleFactor:profile.dpr});
      const deadline=Date.now()+limits.runMs;
      const baselineImages=new Map();
      p.on('pageerror',e=>run.errors.push(e.stack||String(e)));
      p.on('console',m=>run.console.push({type:m.type(),text:m.text()}));
      p.on('response',r=>run.requests.push({url:r.url(),status:r.status()}));
      try {
      await p.addInitScript(max=>{
        globalThis.popoverQualificationEvents=[];globalThis.popoverQualificationOverflow=false;
        for(const type of ['pointerdown','pointerup','click','contextmenu','blur'])addEventListener(type,e=>{
          if(popoverQualificationEvents.length>=max){popoverQualificationOverflow=true;return;}
          popoverQualificationEvents.push({type,trusted:e.isTrusted,x:e.clientX,y:e.clientY,button:e.button,
            pointerType:e.pointerType,time:performance.now()});
        },true);
      },limits.events);
        await p.goto(new URL(url,page.url()).href);
        await p.locator(`html[data-runtime-status="${side==='moon'?'ready':'initialized'}"]`).waitFor({timeout:60000});
        assert.equal(await p.evaluate(()=>crossOriginIsolated),true);
        const canvas=p.locator('canvas');
        run.geometry_initial=await canvas.evaluate(measureCanvasGeometry,undefined,{timeout:3000})
          .catch(cause=>({status:'unavailable',reason:String(cause)}));
        assertProfileGeometry(run.geometry_initial,profile);
        const bounds=await canvas.boundingBox();
        assert.deepEqual([bounds?.x,bounds?.y,bounds?.width,bounds?.height],[0,0,profile.width,profile.height],
          'Full runtime canvas must occupy the declared viewport without clipping');
        async function observe(stage,parent,child) {
          const record={stage,parent,child,attempts:[]};run.stages.push(record);
          record.geometry=await canvas.evaluate(measureCanvasGeometry,undefined,{timeout:3000});
          assertProfileGeometry(record.geometry,profile);
          let failure;
          for(let attempt=0;attempt<(stage==='initial'?8:3);attempt++) {
            assert(Date.now()<deadline,'Bounded popover run deadline exceeded');
            assert(result.captures<limits.captures,'Popover screenshot cap exceeded');result.captures++;
            await p.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
            const stem=`${side}-${profile.width}-dpr${profile.dpr}-${stage}-${attempt}`;
            const path=join(directory,stem+'.png');
            const png=await p.screenshot({path});
            assert.equal(png.readUInt32BE(16),Math.round(profile.width*profile.dpr));
            assert.equal(png.readUInt32BE(20),Math.round(profile.height*profile.dpr));
            assert(result.ocr_runs<limits.ocrRuns,'Popover OCR invocation cap exceeded');result.ocr_runs++;
            const ocr=spawnSync('tesseract',[path,'stdout','--psm','11','tsv'],
              {encoding:'utf8',timeout:limits.ocrMs,maxBuffer:limits.ocrBytes});
            await writeFile(join(directory,stem+'.tsv'),ocr.stdout||'');
            await writeFile(join(directory,stem+'-ocr-stderr.txt'),ocr.stderr||'');
            const attemptRecord={image:stem+'.png',png_sha256:createHash('sha256').update(png).digest('hex'),ocr:stem+'.tsv',events:await p.evaluate(()=>popoverQualificationEvents),ocr_status:ocr.status,
              ocr_signal:ocr.signal,ocr_error:ocr.error?.stack};record.attempts.push(attemptRecord);
            if(ocr.error || ocr.status!==0)throw new ObservationUnavailable(`OCR failed; original stdout/stderr retained: ${stem}: ${ocr.error?.message||ocr.status}`);
            const words=parseTsv(ocr.stdout);
            let targetWords=words;
            if(stage==='initial'||stage==='parent') {
              assert(result.derived_images<limits.derivedImages,'Popover derived-image cap exceeded');result.derived_images++;
              assert(result.ocr_runs<limits.ocrRuns,'Popover OCR invocation cap exceeded');result.ocr_runs++;
              assert(Date.now()<deadline,'Bounded popover run deadline exceeded');
              const inverse=Buffer.from((await p.evaluate(inverseScreenshot,'data:image/png;base64,'+png.toString('base64'))).split(',')[1],'base64');
              assert.equal(inverse.readUInt32BE(16),png.readUInt32BE(16));
              assert.equal(inverse.readUInt32BE(20),png.readUInt32BE(20));
              const inversePath=join(directory,stem+'-inverse.png');await writeFile(inversePath,inverse);
              const inverseOcr=spawnSync('tesseract',[inversePath,'stdout','--psm','6','-c','tessedit_do_invert=0','tsv'],
                {encoding:'utf8',timeout:limits.ocrMs,maxBuffer:limits.ocrBytes});
              await writeFile(join(directory,stem+'-inverse.tsv'),inverseOcr.stdout||'');
              await writeFile(join(directory,stem+'-inverse-ocr-stderr.txt'),inverseOcr.stderr||'');
              attemptRecord.inverse={image:stem+'-inverse.png',ocr:stem+'-inverse.tsv',
                transform:'RGB := 255 - RGB; alpha and dimensions unchanged; screenshot-only',
                png_sha256:createHash('sha256').update(inverse).digest('hex'),psm:6,tessedit_do_invert:0,
                status:inverseOcr.status,signal:inverseOcr.signal,error:inverseOcr.error?.stack};
              if(inverseOcr.error||inverseOcr.status!==0)throw new ObservationUnavailable(
                `Inverse OCR failed; original outputs retained: ${stem}: ${inverseOcr.error?.message||inverseOcr.status}`);
              targetWords=[...words,...parseTsv(inverseOcr.stdout,'inverse')];
            }
            const pixels=await p.evaluate(async data=>{
              const image=new Image();image.src=data;await image.decode();
              const c=document.createElement('canvas');c.width=image.width;c.height=image.height;
              const ctx=c.getContext('2d');ctx.drawImage(image,0,0);
              const a=ctx.getImageData(0,0,c.width,c.height).data;
              const counts={blueBorder:0,redBar:0,yellowBar:0,blueBar:0,greenBar:0};
              for(let i=0;i<a.length;i+=4){const r=a[i],g=a[i+1],b=a[i+2];
                if(b>230&&r<35&&g<35)counts.blueBorder++;
                if(r>245&&g>=180&&g<=205&&b>=180&&b<=205)counts.redBar++;
                if(r>245&&g>245&&b>=180&&b<=205)counts.yellowBar++;
                if(b>245&&r>=180&&r<=205&&g>=180&&g<=205)counts.blueBar++;
                if(g>=210&&g<=235&&r>=180&&r<=205&&b>=180&&b<=205)counts.greenBar++;
              }return counts;
            },'data:image/png;base64,'+png.toString('base64'));
            attemptRecord.pixels=pixels;
            try {
              visibleState(words,pixels,parent,child);
              // Absence in OCR alone cannot prove dismissal. Require exact
              // restoration of this runtime's own earlier screenshot. This
              // never compares Rust pixels with MoonBit pixels.
              const stateKey=child?'child':parent?'parent':'initial';
              if(baselineImages.has(stateKey)) {
                assert(png.equals(baselineImages.get(stateKey)),
                  `${stage}: same-runtime baseline image was not restored`);
                attemptRecord.same_runtime_baseline=stateKey;
              }
              if(stage==='initial')for(const color of ['redBar','yellowBar','blueBar','greenBar'])
                assert(pixels[color]>20,`Actual source ${color} must be visible`);
              if(side==='moon') {
                const scene=await p.evaluate(()=>globalThis.gpuiExample);
                await writeFile(join(directory,stem+'-scene.json'),JSON.stringify(scene,null,2));
                assert.equal(scene.metadata.id,'popover');assert.equal(scene.metadata.source_blob,result.source_blob);
                assert.equal(scene.frame.ok,true);assert.equal(scene.frame.conformance,'unverified');
                assert.equal(scene.frame.popover.comparison_profile_match,false);
                assert.deepEqual([scene.frame.popover.parent_open,scene.frame.popover.child_open],[parent,child]);
                assert(scene.frame.popover.bounds['6'],'Always-open popup must remain in actual candidate scene');
                assert.deepEqual([scene.metadata.width,scene.metadata.height,scene.scale],[profile.width,profile.height,profile.dpr]);
                record.scene=stem+'-scene.json';
              }
              if(!baselineImages.has(stateKey))baselineImages.set(stateKey,png);
              record.observed=true;record.image=stem+'.png';return targetWords;
            }catch(error){failure=error;attemptRecord.failure=error.stack;await p.waitForTimeout(200);}
          }
          throw failure;
        }
        async function clickLabel(words,label) {
          const target=phraseBox(words,label,profile.dpr);
          assert(target.x>0&&target.x<profile.width&&target.y>0&&target.y<profile.height);
          run.actions.push({action:'trusted-left-click',label,target,derived_from:`${side} actual screenshot OCR`});
          await p.mouse.click(target.x,target.y);
        }
        let words=await observe('initial',false,false);
        await clickLabel(words,'Open Popover');words=await observe('parent',true,false);
        await clickLabel(words,'Child Popover');words=await observe('child',true,true);
        // Release outside alone must not dismiss: begin a right press on the
        // independently observed child text, then release at the empty margin.
        const inside=phraseBox(words,'second level',profile.dpr);
        await p.mouse.move(inside.x,inside.y);await p.mouse.down({button:'right'});
        await observe('child-inside-down',true,true);
        await p.mouse.move(2,2);await p.mouse.up({button:'right'});
        await observe('child-outside-release',true,true);
        run.actions.push({action:'right press inside child then release outside',inside,outside:{x:2,y:2}});
        await p.mouse.down({button:'right'});
        await observe('child-dismissed',true,false);
        await p.mouse.up({button:'right'});
        await observe('child-dismissed-release',true,false);
        run.actions.push({action:'right outside down dismisses child only; release preserves parent',target:{x:2,y:2}});
        await p.mouse.down({button:'right'});
        await observe('parent-dismissed',false,false);
        await p.mouse.up({button:'right'});
        await observe('parent-dismissed-release',false,false);
        run.actions.push({action:'next right outside down dismisses parent; default remains',target:{x:2,y:2}});
        const events=await p.evaluate(()=>popoverQualificationEvents);
        assert.equal(await p.evaluate(()=>popoverQualificationOverflow),false);
        assert(events.every(e=>e.trusted),'No synthetic input qualifies');
        for(const type of ['pointerdown','pointerup']) {
          assert.equal(events.filter(e=>e.type===type&&e.button===0).length,2);
          assert.equal(events.filter(e=>e.type===type&&e.button===2).length,3);
        }
        assert(run.requests.some(r=>r.status===200&&new URL(r.url).pathname.endsWith(side==='rust'?'/popover_bg.wasm':'/popover.mjs')),
          'Actual compiled runtime response required independently for each profile');
        assert.deepEqual(run.errors,[]);run.status='passed';
      }catch(error){run.status=error instanceof ObservationUnavailable?'observation_unavailable':'failed';run.failure=error.stack;
        run.geometry_failure=await p.locator('canvas').evaluate(measureCanvasGeometry,undefined,{timeout:3000})
          .catch(cause=>({status:'unavailable',reason:String(cause)}));
        console.error('Popover failure diagnostics: '+JSON.stringify({side,width:profile.width,height:profile.height,dpr:profile.dpr,
          status:run.status,failure:error.message,initial:run.geometry_initial,current:run.geometry_failure}));
        throw error;
      }finally{
        run.events=await p.evaluate(()=>globalThis.popoverQualificationEvents||[]).catch(()=>[]);
        try {await writeFile(join(directory,`${side}-${profile.width}-dpr${profile.dpr}-events.json`),JSON.stringify(run.events,null,2));}
        finally {await p.close();}
      }
      }
    });
    result.status=paired?'passed':'candidate_only_rust_not_run';
    result.overlay='Source text and four bar colors observed; five required layer-state screenshots retained. Exact occlusion, shadows and pixel equality remain unverified.';
    return result;
  }catch(error){result.status=error instanceof ObservationUnavailable?'observation_unavailable':'failed';result.failure=error.stack;throw error;
  }finally{await writeFile(join(directory,'result.json'),JSON.stringify(result,null,2)+'\n');}
}
