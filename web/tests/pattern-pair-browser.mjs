// Two independent actual runtime navigations, no JavaScript pattern renderer.
import assert from 'node:assert/strict';
import {PATTERN_WORKER,assertPatternWorkerInputs,assertPatternWorkerResponse} from './pattern-runtime-evidence.mjs';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {readFile,mkdir,writeFile,readdir} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const hash=b=>createHash('sha256').update(b).digest('hex');
assert.equal(process.argv.length,5,'Usage: node pattern-pair-browser.mjs rust-site moonbit-site fresh-evidence-directory');
const expectedControl=process.env.PATTERN_EXPECT_CONTROL;
const [rustSite,moonSite,out]=process.argv.slice(2).map(p=>resolve(p));
await mkdir(out,{recursive:true});assert.equal((await readdir(out)).length,0,'original evidence requires fresh empty directory');
const contractBytes=await readFile(new URL('../pairs/pattern.json',import.meta.url));
const contract=JSON.parse(contractBytes);await writeFile(join(out,'pattern-contract.json'),contractBytes);
const suite=[];
for(const name of ['pattern-pair-browser.mjs','pattern-compare.py','pattern-negative-controls.test.py','pattern-runtime-evidence.mjs','fixtures/drag-drop-wasm-thread-0cf96c7-worker.js.txt']){const bytes=await readFile(new URL(name,import.meta.url));const file=name.replaceAll('/','-');await writeFile(join(out,file),bytes);suite.push({path:name,file,sha256:hash(bytes)});}
const report={suite_inputs:suite,profile:contract.profile,contract_sha256:hash(contractBytes),status:'failed',captures:{},not_claimed:contract.not_claimed};
const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.ttf':'font/ttf','.css':'text/css'};
assert(process.env.PLAYWRIGHT_ROOT,'PLAYWRIGHT_ROOT required for pinned Playwright 1.56.1');
const require=createRequire(join(resolve(process.env.PLAYWRIGHT_ROOT),'package.json'));
assert.equal(require('playwright/package.json').version,'1.56.1');
const {chromium}=require('playwright');
let browser;
try {
 browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-gpu-sandbox']});
 report.environment={playwright:'1.56.1',browser:await browser.version(),node:process.version};
 const cdp=await browser.newBrowserCDPSession();report.graphics_actual=await cdp.send('SystemInfo.getInfo');await cdp.detach();assert(/SwiftShader/i.test(JSON.stringify(report.graphics_actual)),'pinned software backend required');
 for(const [runtime,site] of [['rust',rustSite],['moonbit',moonSite]]) {
  report.stage=`${runtime}_capture`;
  const capture={session:randomUUID(),runtime,errors:[],responses:[],screenshots:[]};report.captures[runtime]=capture;
  const manifest=await readFile(join(site,'build-manifest.json'));capture.manifest_sha256=hash(manifest);const build=JSON.parse(manifest);
  if(runtime==='moonbit'){
   assert.equal(build.moonbit?.revision,contract.candidate.revision,'exact candidate revision');assert.equal(build.moonbit?.tree,contract.candidate.tree,'exact candidate tree');
   if(expectedControl){assert.equal(build.pattern_control?.id,expectedControl);capture.control=build.pattern_control;assert.equal(capture.control.core_baseline_revision,contract.candidate.revision);assert.equal(capture.control.core_baseline_tree,contract.candidate.tree);assert.equal(capture.control.baseline_rebuilt_runtime_sha256,capture.control.baseline_runtime_sha256);
    const base=await readFile(join(site,'pattern-control-evidence/baseline-build-manifest.json'));assert.equal(hash(base),capture.control.baseline_manifest_sha256);const baselineBuild=JSON.parse(base);assert.equal(baselineBuild.moonbit?.revision,contract.candidate.revision);assert.equal(baselineBuild.moonbit?.tree,contract.candidate.tree);
    for(const file of ['baseline-build-manifest.json','before-source.txt','after-source.txt','control.json','test.log','build.log','baseline-test.log','baseline-build.log']){const bytes=await readFile(join(site,'pattern-control-evidence',file));await writeFile(join(out,`pattern-control-${file}`),bytes);}
    assert.equal(hash(await readFile(join(site,'pattern-control-evidence/before-source.txt'))),capture.control.source_before_sha256);
    assert.equal(hash(await readFile(join(site,'pattern-control-evidence/after-source.txt'))),capture.control.source_after_sha256);
   }else assert(!build.pattern_control,'intentional mutant cannot be baseline candidate');
  }
  if(runtime==='rust') {
   assert.equal(build.rust?.source_revision,contract.upstream.revision,'unchanged Rust revision');assert.equal(build.rust?.source_modified,false,'unchanged Rust source');
   const source=build.rust.pattern_source||[...(build.rust_subset_sources||[]),...(build.rust_oracle_only||[])].find(s=>s.id==='pattern');
   assert(source,'source-bound Rust pattern record required');assert.equal(source.source_blob,contract.upstream.source_blob);assert.equal(source.source,contract.upstream.source);
   assert.equal(source.retained_file,'unchanged-source/pattern.rs','retained immutable source path');
   const sourceBytes=await readFile(join(site,'rust',source.retained_file));
   assert.equal(hash(sourceBytes),source.source_sha256,'retained upstream source SHA256');
   const blob=createHash('sha1').update(Buffer.from(`blob ${sourceBytes.length}\0`)).update(sourceBytes).digest('hex');
   assert.equal(blob,contract.upstream.source_blob,'retained upstream Git blob identity');
   await writeFile(join(out,'pattern-rust-unchanged-source.rs'),sourceBytes);
   capture.upstream_source={file:'pattern-rust-unchanged-source.rs',sha256:hash(sourceBytes),source_blob:blob};
  }
  capture.support_files=[];
  for(const [path,expected] of Object.entries(build.files||{}).filter(([path])=>path.startsWith('inputs/'))){const bytes=await readFile(join(site,path));assert.equal(hash(bytes),expected);const file=`pattern-${runtime}-input-${hash(Buffer.from(path)).slice(0,16)}`;await writeFile(join(out,file),bytes);capture.support_files.push({path,file,sha256:expected});}
  await writeFile(join(out,`pattern-${runtime}-build-manifest.json`),manifest);
  const server=createServer(async(req,res)=>{try {
   const url=new URL(req.url,'http://localhost');if(url.pathname==='/favicon.ico'){res.writeHead(204);res.end();return;}
   assert(url.pathname.startsWith('/gpui-conformance/'));
   let relative=decodeURIComponent(url.pathname.slice('/gpui-conformance/'.length));if(!relative||relative.endsWith('/'))relative+='index.html';
   const path=resolve(site,relative);assert(path.startsWith(site+sep));const data=await readFile(path);
   res.writeHead(200,{'content-type':mime[extname(path)]||'application/octet-stream','cache-control':'no-store','Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp','Cross-Origin-Resource-Policy':'same-origin'});res.end(data);
  }catch(error){res.writeHead(404);res.end('Not found');}});
  await new Promise(done=>server.listen(0,'127.0.0.1',done));
  const context=await browser.newContext({viewport:{width:600,height:600},deviceScaleFactor:1,serviceWorkers:'block'}),page=await context.newPage();
  await page.addInitScript(()=>{globalThis.patternContextObservations=[];const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){const context=get.call(this,kind,...args);if(context)patternContextObservations.push({kind,elementId:this.id,width:this.width,height:this.height});return context;};});
  const tasks=[],retainedResponses=new Map();let responseOrdinal=0;
  if(runtime==='moonbit'&&process.env.PATTERN_BLOCK_RUNTIME==='1')await page.route('**/pattern.mjs',route=>route.abort('failed')); 
  page.on('pageerror',error=>capture.errors.push(error.message));page.on('console',m=>{if(m.type()==='error')capture.errors.push(m.text());});
  page.on('requestfailed',req=>capture.errors.push(`${req.url()}: ${req.failure()?.errorText}`));
  page.on('response',response=>{
   const type=response.request().resourceType(),url=response.url(),ordinal=++responseOrdinal;
   if(['script','wasm'].includes(type)||/\.(m?js|wasm|ttf)(\?|$)/.test(url))tasks.push((async()=>{const bytes=await response.body();const file=`pattern-${runtime}-asset-${ordinal}-${hash(Buffer.from(url))}${extname(new URL(url).pathname)}`;await writeFile(join(out,file),bytes);capture.responses.push({url,status:response.status(),type,file,sha256:hash(bytes),bytes:bytes.length,ordinal});retainedResponses.set(ordinal,bytes);})());
  });
  try {
   await page.goto(`http://127.0.0.1:${server.address().port}/gpui-conformance/${runtime}/?example=pattern`);
   if(runtime==='moonbit')await page.locator('html[data-runtime-status="ready"]').waitFor({timeout:60000});
   else await page.locator('canvas').waitFor({timeout:60000});
   capture.viewport=await page.evaluate(()=>({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,isolated:crossOriginIsolated,canvases:[...document.querySelectorAll('canvas')].map(c=>({width:c.width,height:c.height,bounds:JSON.parse(JSON.stringify(c.getBoundingClientRect()))}))}));
   assert.equal(capture.viewport.width,600);assert.equal(capture.viewport.height,600);assert.equal(capture.viewport.dpr,1);assert(capture.viewport.isolated);
   assert(capture.viewport.canvases.some(c=>c.width===600&&c.height===600),'600x600 actual canvas required');
   const deadline=Date.now()+60000;let previous;
   while(Date.now()<deadline){
    await page.waitForTimeout(150);const bytes=await page.screenshot({animations:'disabled',scale:'device'}),file=`pattern-${runtime}-${capture.screenshots.length+1}-dpr1.png`;
    await writeFile(join(out,file),bytes);const record={file,sha256:hash(bytes),bytes:bytes.length,method:'Playwright.page.screenshot'};capture.screenshots.push(record);
    // A blank boot canvas must never count as a stable source render.
    let sourceVisible=false;
    try {
     record.probe=JSON.parse(execFileSync('python',[new URL('./pattern-compare.py',import.meta.url).pathname,'--diagnose',join(out,file)],{encoding:'utf8',maxBuffer:1024*1024}));
     sourceVisible=record.probe.source_visible===true;
    }catch(error){record.probe={source_visible:false,process_failure:true,status:error.status,code:error.code,error:error.message,stderr:error.stderr?.toString(),stdout:error.stdout?.toString()};}
    record.png_matches_previous=previous?.sha256===record.sha256;
    record.rgba_matches_previous=Boolean(record.probe.rgba_sha256&&record.probe.rgba_sha256===previous?.probe?.rgba_sha256);
    if(previous?.sha256===record.sha256&&sourceVisible){capture.stable=true;capture.final=file;break;}previous=record;
   }
   if(!capture.stable){const last=capture.screenshots.at(-1);capture.stability_failure={png_stable:last?.png_matches_previous,rgba_stable:last?.rgba_matches_previous,last_probe:last?.probe};console.error('PATTERN_CAPTURE_DIAGNOSTIC '+JSON.stringify({runtime,...capture.stability_failure,errors:capture.errors}));}
   assert(capture.stable,`${runtime}: original source image never stabilized; last probe: ${JSON.stringify(capture.screenshots.at(-1)?.probe)}`);
   capture.backend=await page.evaluate(()=>patternContextObservations);
   assert(capture.backend.some(c=>c.kind===(runtime==='rust'?'webgl2':'2d')),`${runtime}: scoped actual canvas backend missing`);
   if(runtime==='moonbit'){
   assert.equal(build.moonbit?.revision,contract.candidate.revision,'exact candidate revision');assert.equal(build.moonbit?.tree,contract.candidate.tree,'exact candidate tree');
    capture.scene=await page.evaluate(()=>({metadata:gpuiExample.metadata,frame:{...gpuiExample.frame,operations:gpuiExample.frame.operations.map(({rgba,...op})=>op)}}));
    assert.equal(capture.scene.metadata.source_blob,contract.upstream.source_blob);assert.equal(capture.scene.frame.pattern.comparison_profile_match,true);
    assert.equal(capture.scene.frame.raster_transport,'ordered_core_webgl2_linear_straight_v1');
    assert(capture.scene.frame.operations.some(o=>o.kind==='rgba'||o.kind==='rgba_run'),'missing core RGBA runtime');
   }
   await Promise.all(tasks);assert.deepEqual(capture.errors,[]);
   const blobs=capture.responses.filter(response=>new URL(response.url).protocol==='blob:');
   if(blobs.length){
    assert.equal(runtime,'rust','No generated blob scripts authorized for MoonBit');
    const inputs={};let loader;
    for(const response of capture.responses){const url=new URL(response.url);if(url.protocol!=='http:')continue;const path=url.pathname.replace('/gpui-conformance/','');if([PATTERN_WORKER.loader_path,PATTERN_WORKER.wasm_path].includes(path)){assert.equal(response.status,200);inputs[path]=retainedResponses.get(response.ordinal);if(path===PATTERN_WORKER.loader_path)loader=response.url;}}
    const lockBytes=await readFile(join(site,'rust/Cargo.lock'));await writeFile(join(out,'pattern-rust-worker-Cargo.lock'),lockBytes);
    assertPatternWorkerInputs(build,inputs,lockBytes);
    for(const response of blobs)assertPatternWorkerResponse(response,loader,retainedResponses.get(response.ordinal));
    capture.worker_provenance={...PATTERN_WORKER,loader_url:loader,lock_file:'pattern-rust-worker-Cargo.lock',responses:blobs.map(r=>({ordinal:r.ordinal,file:r.file,sha256:r.sha256})),qualification:'exact_source_derived_worker_bytes'};
   }
   for(const response of capture.responses){
    if(new URL(response.url).protocol==='blob:')continue; // Explicitly verified above, never broadly allowed.
    const path=new URL(response.url).pathname.replace('/gpui-conformance/','');
    const runtimeName=path==='moonbit/runtime.mjs'?'hello_world':path.match(/^moonbit\/(\w+)\.mjs$/)?.[1];
    const expected=runtime==='rust'?(build.rust.files[path.replace(/^rust\//,'')]||build.moonbit_host_files_sha256?.[path]):(build.files?.[path]||build.runtime_sha256_by_example?.[runtimeName]||build.moonbit_host_files_sha256?.[path]||build.font_sha256_by_file?.[path.replace(/^moonbit\//,'')]);
    assert(expected,`runtime response absent from build manifest: ${path}`);assert.equal(response.sha256,expected,`served executable differs: ${path}`);
   }
   assert(capture.responses.some(r=>r.status===200&&(/\.wasm(?:\?|$)/.test(r.url)||runtime==='moonbit'&&/pattern\.mjs(?:\?|$)/.test(r.url))),'missing retained compiled runtime');
  }finally {await Promise.allSettled(tasks);await context.close();await new Promise(done=>server.close(done));}
 }
 assert.notEqual(report.captures.rust.session,report.captures.moonbit.session);
 report.stage='comparison';
 const result=execFileSync('python',[new URL('./pattern-compare.py',import.meta.url).pathname,join(out,report.captures.rust.final),join(out,report.captures.moonbit.final),'--output',join(out,'pattern-comparison.json')],{encoding:'utf8'});
 report.comparison=JSON.parse(result);assert(!expectedControl,'negative compiled control unexpectedly qualified');report.status='qualified_source_regions';
 console.log(JSON.stringify({status:report.status,evidence:out,not_claimed:report.not_claimed},null,2));
}catch(error){report.failure=error.stack;throw error;}
finally{
 await writeFile(join(out,'pattern-pair-result.json'),JSON.stringify(report,null,2)+'\n');
 // Small independent diagnostic artifact; originals remain untouched in out.
 // Excludes executable assets and does not serve as complete pair evidence.
 const diagnostics=join(out,'diagnostics');await mkdir(diagnostics);
 await writeFile(join(diagnostics,'pattern-pair-result.json'),JSON.stringify(report,null,2)+'\n');
 await writeFile(join(diagnostics,'pattern-contract.json'),contractBytes);
 for(const capture of Object.values(report.captures))for(const sample of capture.screenshots.slice(-2))await writeFile(join(diagnostics,sample.file),await readFile(join(out,sample.file)));
 if(browser)await browser.close();
}
