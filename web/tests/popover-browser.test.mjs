// Offline oracle/contract tests only. These do not execute either runtime,
// Playwright, OCR, or establish browser conformance.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync,mkdtempSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import vm from 'node:vm';
import {profiles,limits,parseTsv,phraseBox,visibleState,ObservationUnavailable,inverseScreenshot,measureCanvasGeometry,probeScaleGeometry,withProfileBrowser,fractionalLaunchOptions,assertProfileGeometry} from './popover-browser.mjs';
const header='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext';
const row=(text,i=1,conf=95,line=1)=>`5\t1\t1\t1\t${line}\t${i}\t${10+i*40}\t30\t35\t20\t${conf}\t${text}`;
const words=text=>parseTsv([header,...text.split(' ').map((w,i)=>row(w,i))].join('\n'));
test('profiles are bounded declared and narrower fractional smoke, never arbitrary viewport coverage',()=>{
  assert.deepEqual(profiles,[{width:800,height:600,dpr:1,kind:'declared-source-profile'},
    {width:480,height:600,dpr:1.25,kind:'narrow-fractional-smoke'}]);
  assert(limits.captures<=160);assert(limits.events<=128);assert(limits.ocrBytes<=4*1024*1024);
  assert(limits.ocrMs<=8000);assert(limits.runMs<=120000);
});
test('TSV only admits finite confident word observations',()=>{
  const data=[header,row('Open'),row('Popover',2),row('noise',3,10),row('invalid').replace('\t50\t30','\tNaN\t30'),'bad\trow'].join('\n');
  assert.deepEqual(parseTsv(data).map(w=>w.text),['Open','Popover']);
});
test('OCR target distinguishes Open from Opened and accounts for screenshot DPR',()=>{
  const observed=words('Opened Popover Open Popover');
  assert.deepEqual(phraseBox(observed,'Open Popover',1.25),{x:102,y:32,width:60,height:16});
  assert.throws(()=>phraseBox(words('Opened Popover'),'Open Popover'),ObservationUnavailable);
  assert.throws(()=>phraseBox(words('Open Popover Open Popover'),'Open Popover'),ObservationUnavailable);
});
test('OCR target cannot bridge lines or low-confidence words',()=>{
  assert.throws(()=>phraseBox(parseTsv([header,row('Open',1),row('Popover',2,95,2)].join('\n')),'Open Popover'),ObservationUnavailable);
  assert.throws(()=>phraseBox(parseTsv([header,row('Open',1),row('Popover',2,39)].join('\n')),'Open Popover'),ObservationUnavailable);
});
test('fail closed on missing required positive labels rather than qualifying absent text',()=>{
  for(const [text,parent,child] of [['',false,false],['Popover',false,false],['Popover',true,false],['first level Popover',true,true]])
    assert.throws(()=>visibleState(words(text),{blueBorder:0},parent,child),ObservationUnavailable);
});
test('observed child blue border and popup labels must agree with every expected state',()=>{
  visibleState(words('default opened Popover'),{blueBorder:0},false,false);
  visibleState(words('first level Popover'),{blueBorder:0},true,false);
  visibleState(words('first level Popover second level Popover'),{blueBorder:50},true,true);
  assert.throws(()=>visibleState(words('default opened Popover first level'),{blueBorder:0},false,false),/remains visible/);
  assert.throws(()=>visibleState(words('first level Popover second level'),{blueBorder:0},true,false),/remains visible/);
  assert.throws(()=>visibleState(words('first level Popover second level'),{blueBorder:0},true,true),/border ink/);
  assert.throws(()=>visibleState(words('first level Popover'),{blueBorder:50},true,false),/border ink/);
});
test('main existing workflow entrypoint invokes independent qualification before overall pass',()=>{
  const harness=readFileSync(new URL('./candidate-browser.mjs',import.meta.url),'utf8');
  assert.match(harness,/import \{ checkPopoverPair \} from '\.\/popover-browser\.mjs'/);
  assert(harness.indexOf('report.popover = await checkPopoverPair')<harness.indexOf("report.overall = 'passed'"));
});
test('harness retains originals, errors and trusted pointer evidence without runtime mutation',()=>{
  const source=readFileSync(new URL('./popover-browser.mjs',import.meta.url),'utf8');
  assert.doesNotMatch(source,/dispatchEvent|new (?:Mouse|Pointer|Keyboard)Event|wasmBindings\.|runtime\.|\.popover_pointer\(|\.popover_frame\(/);
  assert.match(source,/derived_from:`\$\{side\} actual screenshot OCR`/);
  assert.match(source,/ocr\.stderr\|\|''/);assert.match(source,/ocr\.stdout\|\|''/);
  assert.match(source,/events:await p\.evaluate\(\(\)=>popoverQualificationEvents\)/);
  for(const stage of ['initial','parent','child','child-dismissed','parent-dismissed','child-outside-release'])
    assert(source.includes(`observe('${stage}'`));
  assert.match(source,/\.mouse\.down\(\{button:'right'\}\)/);
  assert.match(source,/\.mouse\.up\(\{button:'right'\}\)/);
  assert.match(source,/events\.every\(e=>e\.trusted\)/);
  assert.match(source,/observation_unavailable/);
});

test('two OCR passes deduplicate only the same spatial target and retain ambiguity',()=>{
  const original=words('Open Popover');
  const inverse=original.map(w=>({...w,pass:'inverse',line:'inverse/'+w.line,x:w.x+1}));
  assert.deepEqual(phraseBox([...original,...inverse],'Open Popover'),phraseBox(original,'Open Popover'));
  const distinct=inverse.map(w=>({...w,x:w.x+200}));
  assert.throws(()=>phraseBox([...original,...distinct],'Open Popover'),ObservationUnavailable);
  assert.throws(()=>phraseBox([...original,...original,...inverse],'Open Popover'),ObservationUnavailable);
  assert.throws(()=>phraseBox([...original,...inverse,...inverse],'Open Popover'),ObservationUnavailable);
  assert.throws(()=>phraseBox([original[0],inverse[1]],'Open Popover'),ObservationUnavailable);
});
test('inverse pass changes only RGB in detached screenshot Canvas, preserving alpha and dimensions',async()=>{
  const data=new Uint8ClampedArray([0,10,255,255,120,200,31,78]);let canvas;
  const context={drawImage(){},getImageData(){return {data};},putImageData(p){assert.equal(p.data,data);}};
  class Image {width=2;height=1;async decode(){}}
  const inverse=vm.runInNewContext('('+inverseScreenshot.toString()+')',{
    Image,document:{createElement(type){assert.equal(type,'canvas');canvas={getContext:()=>context,toDataURL:()=> 'data:image/png;base64,fixture'};return canvas;}}
  });
  assert.equal(await inverse('data:image/png;base64,retained-original'),'data:image/png;base64,fixture');
  assert.deepEqual([...data],[255,245,0,255,135,55,224,78]);
  assert.deepEqual([canvas.width,canvas.height],[2,1]);
});
test('real retained failing screenshot gains an independent button target via inverse OCR',
  {skip:!process.env.POPOVER_OCR_FIXTURE},()=>{
  const input=process.env.POPOVER_OCR_FIXTURE;
  const directory=process.env.POPOVER_OCR_EVIDENCE||mkdtempSync(join(tmpdir(),'popover-inverse-'));
  mkdirSync(directory,{recursive:true});
  const digest=path=>createHash('sha256').update(readFileSync(path)).digest('hex');
  const before=digest(input),inverse=join(directory,'actual-inverse.png');
  const converted=spawnSync('convert',[input,'-channel','RGB','-negate',inverse],{encoding:'utf8',timeout:limits.ocrMs,maxBuffer:limits.ocrBytes});
  writeFileSync(join(directory,'convert-stderr.txt'),converted.stderr||'');
  assert.equal(converted.status,0,converted.error?.stack||converted.stderr);
  function ocr(path,pass,args){
    const result=spawnSync('tesseract',[path,'stdout',...args,'tsv'],{encoding:'utf8',timeout:limits.ocrMs,maxBuffer:limits.ocrBytes});
    writeFileSync(join(directory,pass+'.tsv'),result.stdout||'');
    writeFileSync(join(directory,pass+'-stderr.txt'),result.stderr||'');
    assert.equal(result.status,0,result.error?.stack||result.stderr);return parseTsv(result.stdout,pass);
  }
  const original=ocr(input,'original',['--psm','11']);
  const inverted=ocr(inverse,'inverse',['--psm','6','-c','tessedit_do_invert=0']);
  assert.throws(()=>phraseBox(original,'Open Popover'),ObservationUnavailable);
  const target=phraseBox([...original,...inverted],'Open Popover');
  assert(target.x>417&&target.x<543&&target.y>224&&target.y<255,'Target must land in independently inspected visible black button');
  assert.equal(digest(input),before,'Retained original screenshot must remain unchanged');
  writeFileSync(join(directory,'offline-recognition.json'),JSON.stringify({source:input,source_sha256:before,
    derived_sha256:digest(inverse),target,original_target:'observation_unavailable',inverse_target:'observed',
    scope:'Offline OCR replay of one actual captured MoonBit image only; no new browser behavior or Rust qualification'},null,2));
});

test('passive geometry observer reports actual backing and disconnects on delivery/timeout/error',async()=>{
  for(const mode of ['delivery','timeout','error']) {
    let disconnected=0,cleared=0,timeout;
    const canvas={width:480,height:600,clientWidth:480,clientHeight:600,
      getBoundingClientRect:()=>({x:0,y:0,width:480,height:600})};
    class Observer {
      constructor(callback){this.callback=callback;}
      observe(target,options){
        assert.equal(target,canvas);assert.equal(options.box,'device-pixel-content-box');
        if(mode==='error')throw Error('observer unavailable');
        queueMicrotask(()=>{if(mode==='timeout')timeout();else {
          canvas.width=600;canvas.height=750;
          this.callback([{target:canvas,contentRect:{x:0,y:0,width:480,height:600},
            contentBoxSize:[{inlineSize:480,blockSize:600}],devicePixelContentBoxSize:[{inlineSize:600,blockSize:750}]}]);
        }});
      }
      disconnect(){disconnected++;}
    }
    const measure=vm.runInNewContext('('+measureCanvasGeometry.toString()+')',{
      ResizeObserver:Observer,window:{devicePixelRatio:1.25,innerWidth:480,innerHeight:600,visualViewport:{width:480,height:600,scale:1}},
      getComputedStyle:()=>({width:'480px',height:'600px',transform:'none',zoom:'1'}),
      setTimeout(callback,ms){assert.equal(ms,2000);timeout=callback;return 1;},clearTimeout(){cleared++;}
    });
    const observed=await measure(canvas);
    assert.equal(disconnected,1);assert.equal(cleared,1);
    assert.equal(observed.window_dpr,1.25);
    assert.equal(observed.resize_observer.status,mode==='delivery'?'observed':mode==='timeout'?'timeout':'unavailable');
    if(mode==='delivery'){
      assert.equal(observed.canvas.backing_width,600,'Snapshot must follow observer delivery');
      assert.equal(observed.resize_observer.device_pixel_content_box[0].inline_size,600);
    }
  }
});
test('scale probe has exactly two isolated blank pages and closes owned browser even on failures',async()=>{
  for(const failure of [false,true]){
    let pagesClosed=0,browsersClosed=0,launches=0,screenshots=0;
    const png=Buffer.alloc(24);png.writeUInt32BE(600,16);png.writeUInt32BE(750,20);
    const active={version:async()=>'test-only',newPage:async options=>{
      assert.deepEqual(options,{viewport:{width:480,height:600},deviceScaleFactor:1.25});
      return {setDefaultTimeout:ms=>assert.equal(ms,5000),setDefaultNavigationTimeout:ms=>assert.equal(ms,5000),
        setContent:async html=>{assert.doesNotMatch(html,/script|popover/);},
        locator:()=>({evaluate:async fn=>{assert.equal(fn,measureCanvasGeometry);if(failure)throw Error('diagnostic failed');return {test:true};}}),
        screenshot:async()=>{screenshots++;return png;},close:async()=>{pagesClosed++;}};
    }};
    const browser={...active,browserType:()=>({launch:async options=>{
      launches++;assert.equal(options.timeout,15000);assert(options.args.includes('--force-device-scale-factor=1.25'));
      return {...active,close:async()=>{browsersClosed++;}};
    }})};
    const result=await probeScaleGeometry({browser,directory:'/unused-by-mock'});
    assert.equal(launches,1);assert.equal(browsersClosed,1);assert.equal(pagesClosed,2);
    assert.equal(screenshots,failure?0:2);assert.equal(result.captures,screenshots);
    assert(result.runs.every(run=>run.status===(failure?'unavailable':'observed')));
  }
});

test('fractional profile runs both runtimes in one coherent owned browser and closes on success or failure',async()=>{
  for(const failure of [false,true]) {
    let launches=0,closed=0;const runtimes=[];
    const owned={version:async()=>'Chromium-test',close:async()=>{closed++;}};
    const browser={browserType:()=>({launch:async options=>{launches++;assert.deepEqual(options,fractionalLaunchOptions);return owned;}})};
    const work=async(active,launch)=>{
      assert.equal(active,owned);assert.equal(launch.browser,'Chromium-test');
      assert.equal(launch.mode,'coherent-physical-scale-launch');
      assert.deepEqual(launch.requested_args,[...fractionalLaunchOptions.args]);
      for(const side of ['moon','rust']){runtimes.push(side);if(failure)throw Error('original application failure');}
      return 'both checked';
    };
    if(failure)await assert.rejects(withProfileBrowser(browser,profiles[1],work),/original application failure/);
    else assert.equal(await withProfileBrowser(browser,profiles[1],work),'both checked');
    assert.equal(launches,1);assert.equal(closed,1);assert.deepEqual(runtimes,failure?['moon']:['moon','rust']);
  }
});
test('normal profile keeps existing browser, while launch/version failures cannot leak owned browser',async()=>{
  let closed=0;const existing={version:async()=>'normal',close:async()=>{closed++;},browserType:()=>{throw Error('unexpected launch');}};
  await withProfileBrowser(existing,profiles[0],async(active,launch)=>{assert.equal(active,existing);assert.equal(launch.mode,'inherited-DPR1-launch');});
  assert.equal(closed,0);
  const badVersion={browserType:()=>({launch:async()=>({version:async()=>{throw Error('version failed');},close:async()=>{closed++;}})})};
  await assert.rejects(withProfileBrowser(badVersion,profiles[1],()=>assert.fail('work must not run')),/version failed/);
  assert.equal(closed,1);
  const badLaunch={browserType:()=>({launch:async()=>{throw Error('launch failed');}})};
  await assert.rejects(withProfileBrowser(badLaunch,profiles[1],()=>assert.fail('work must not run')),/launch failed/);
  await assert.rejects(withProfileBrowser(existing,{dpr:2},()=>assert.fail('unsupported profile')),/declared fractional/);
});
function coherentGeometry({width,height,dpr}) {
  return {window_dpr:dpr,inner_width:width,inner_height:height,
    canvas:{backing_width:Math.round(width*dpr),backing_height:Math.round(height*dpr),client_width:width,client_height:height,
      css_rect:{x:0,y:0,width,height},style:{transform:'none',zoom:'1'}},
    visual_viewport:{width,height,scale:1,offset_left:0,offset_top:0,page_left:0,page_top:0},
    resize_observer:{status:'observed',content_rect:{x:0,y:0,width,height},
      content_box:[{inline_size:width,block_size:height}],device_pixel_content_box:[{inline_size:Math.round(width*dpr),block_size:Math.round(height*dpr)}]}};
}
test('strict profile geometry accepts coherent observed surfaces and rejects proven context-only mismatch',()=>{
  for(const profile of profiles)assertProfileGeometry(coherentGeometry(profile),profile);
  const incorrect=coherentGeometry(profiles[1]);incorrect.canvas.backing_width=480;incorrect.canvas.backing_height=600;
  incorrect.resize_observer.device_pixel_content_box=[{inline_size:480,block_size:600}];
  assert.throws(()=>assertProfileGeometry(incorrect,profiles[1]),/Canvas backing/);
  for(const mutate of [
    g=>g.window_dpr=1,g=>g.inner_width=384,g=>g.canvas.css_rect.x=1,g=>g.canvas.client_width=384,
    g=>g.canvas.style.transform='scale(1.25)',g=>g.canvas.style.zoom='1.25',
    g=>g.resize_observer.status='timeout',g=>g.resize_observer.content_rect.width=384,
    g=>g.resize_observer.content_box=[{inline_size:384,block_size:480}],
    g=>g.resize_observer.device_pixel_content_box=[{inline_size:480,block_size:600}],
    g=>g.visual_viewport.scale=1.25,g=>g.visual_viewport.offset_left=1,
  ]) {
    const geometry=coherentGeometry(profiles[1]);mutate(geometry);
    assert.throws(()=>assertProfileGeometry(geometry,profiles[1]));
  }
});
test('application paths retain independent source-derived targets and require geometry before initial input and every stage',()=>{
  const source=readFileSync(new URL('./popover-browser.mjs',import.meta.url),'utf8');
  assert.match(source,/for\(const profile of profiles\)await withProfileBrowser/);
  assert.match(source,/activeBrowser.newPage/);
  assert.match(source,/assertProfileGeometry\(run.geometry_initial,profile\)/);
  assert.match(source,/assertProfileGeometry\(record.geometry,profile\)/);
  assert.match(source,/result.scale_probe=await probeScaleGeometry/);
  assert.match(source,/const target=phraseBox\(words,label,profile.dpr\)/);
  assert.match(source,/await p.mouse.click\(target.x,target.y\)/);
});
