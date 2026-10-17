import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,readdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {randomUUID} from 'node:crypto';
import {sha256,decode,validateProfile,validateManifest,samples} from './gradient-diagnostic-contract.mjs';
import {installBackendObserver,classifyBackend} from './gradient-backend-observer.mjs';
assert.equal(process.argv.length,4,'Pass isolated site and evidence directories');
const site=resolve(process.argv[2]),evidence=resolve(process.argv[3]);
await mkdir(evidence,{recursive:true});assert(!(await readdir(evidence)).some(f=>f.startsWith('gradient-diagnostic-')),'Fresh diagnostic evidence required');
const result={status:'failed',kind:'synthetic_rust_gpu_diagnostic_only',original_example:false,candidate:'not_implemented',conformance:'not_claimed',session:randomUUID(),responses:[],served:[],screenshots:[],console:[],errors:[],inputs:[]};
let browser,server,page;const pending=[];
const save=async(name,bytes)=>{await writeFile(join(evidence,name),bytes);return {file:name,sha256:sha256(bytes),bytes:bytes.length};};
try {
 const manifestBytes=await readFile(join(site,'build-manifest.json'));const manifest=JSON.parse(manifestBytes);validateManifest(manifest);
 result.manifest=await save('gradient-diagnostic-build-manifest.json',manifestBytes);
 for(const [path,hash] of Object.entries(manifest.files)) {
  assert(!path.split('/').includes('..'));const bytes=await readFile(join(site,path));assert.equal(sha256(bytes),hash);
  result.inputs.push({path,...await save('gradient-diagnostic-input-'+sha256(Buffer.from(path))+'.bin',bytes)});
 }
 for(const path of ['web/tests/gradient-diagnostic-browser.mjs','web/tests/gradient-diagnostic-contract.mjs','web/tests/gradient-backend-observer.mjs','web/tests/verify-gradient-diagnostic.mjs','web/scripts/decode_gradient_diagnostic_png.py','web/scripts/build_gradient_diagnostic.py','.github/workflows/gradient-diagnostic.yml']) {
  result.inputs.push({suite_path:path,...await save('gradient-diagnostic-suite-'+sha256(Buffer.from(path))+'.bin',await readFile(new URL('../../'+path,import.meta.url)))});
 }
 const profile=validateProfile(JSON.parse(await readFile(join(site,'profile.json'))));
 server=createServer(async(req,res)=>{const item={url:req.url};result.served.push(item);try{
  const url=new URL(req.url,'http://localhost');if(url.pathname==='/favicon.ico'){res.writeHead(204);res.end();return;}let path=decodeURIComponent(url.pathname);if(path==='/')path='/index.html';
  const file=resolve(site,'.'+path);assert(file.startsWith(site+sep));const bytes=await readFile(file);
  Object.assign(item,{status:200,sha256:sha256(bytes)});res.writeHead(200,{'content-type':({'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.wasm':'application/wasm','.json':'application/json'})[extname(file)]||'application/octet-stream','cache-control':'no-store','Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp'});res.end(bytes);
 }catch(error){item.status=404;res.writeHead(404);res.end();}});
 await new Promise(done=>server.listen(0,'127.0.0.1',done));
 assert(process.env.PLAYWRIGHT_ROOT);const require=createRequire(join(process.env.PLAYWRIGHT_ROOT,'package.json'));assert.equal(require('playwright/package.json').version,'1.56.1');
 const flags=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'];
 browser=await require('playwright').chromium.launch({headless:true,args:flags});
 const context=await browser.newContext({viewport:{width:1000,height:900},deviceScaleFactor:1,serviceWorkers:'block'});page=await context.newPage();
 result.environment={browser:browser.version(),playwright:'1.56.1',node:process.version,requested_flags:flags};
 const cdp=await browser.newBrowserCDPSession();result.system_info=await cdp.send('SystemInfo.getInfo');await cdp.detach();
 await page.addInitScript(installBackendObserver);
 page.on('console',m=>{result.console.push({type:m.type(),text:m.text()});if(m.type()==='error')result.errors.push(m.text());});
 page.on('pageerror',e=>result.errors.push(String(e)));page.on('requestfailed',r=>result.errors.push(r.url()+': '+r.failure()?.errorText));
 let ordinal=0;
 page.on('response',response=>{const id=++ordinal;pending.push((async()=>{try{
  if(response.url().endsWith('/favicon.ico')&&response.status()===204)return;const bytes=await response.body();result.responses.push({ordinal:id,url:response.url(),status:response.status(),type:response.request().resourceType(),...await save(`gradient-diagnostic-response-${id}.bin`,bytes)});
 }catch(error){result.errors.push('Response body '+response.url()+': '+error);}})());});
 result.url=`http://127.0.0.1:${server.address().port}/`;
 await page.goto(result.url);await page.locator('html[data-runtime-status="initialized"]').waitFor({timeout:60000});
 assert.equal(await page.evaluate(()=>crossOriginIsolated),true);
 await page.locator('canvas').waitFor();await page.waitForTimeout(300);
 const deadline=Date.now()+30000;let previous;
 while(Date.now()<deadline) {
  await page.evaluate(()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done))));
  const png=await page.screenshot({animations:'disabled',scale:'device'}),record=await save(`gradient-diagnostic-frame-${result.screenshots.length}.png`,png);
  result.screenshots.push(record);const rgba=decode(png);record.rgba_sha256=sha256(rgba);
  // Nonwhite solid and red/blue probes show actual painting before stability can pass.
  const at=(x,y)=>Array.from(rgba.subarray((y*1000+x)*4,(y*1000+x)*4+3));
  record.painted=JSON.stringify(at(96,48))!=='[255,255,255]'&&JSON.stringify(at(410,48))!=='[255,255,255]';
  if(record.painted&&previous?.painted&&previous.rgba_sha256===record.rgba_sha256){result.stable=[previous.file,record.file];result.samples=samples(rgba,profile);result.raw_rgba=await save('gradient-diagnostic-stable.rgba',rgba);break;}
  previous=record;await page.waitForTimeout(100);
 }
 assert(result.stable,'No two independently requested painted identical frames');
 result.backend=classifyBackend(await page.evaluate(()=>gradientBackendSnapshot()));
 result.canvas=await page.locator('canvas').evaluateAll(cs=>cs.map(c=>({width:c.width,height:c.height,bounds:{x:c.getBoundingClientRect().x,y:c.getBoundingClientRect().y,width:c.getBoundingClientRect().width,height:c.getBoundingClientRect().height}})));
 await Promise.all(pending);assert.deepEqual(result.errors,[]);result.status='captured_raw_observations';
} catch(error){result.failure=String(error.stack);process.exitCode=1;} finally {
 if(page){try{result.backend=classifyBackend(await page.evaluate(()=>gradientBackendSnapshot()));}catch(error){result.backend_read_failure=String(error);}
 if(result.status==='failed')try{result.failure_screenshot=await save('gradient-diagnostic-failure.png',await page.screenshot({animations:'disabled',scale:'device'}));}catch(error){result.failure_screenshot_error=String(error);}}
 await Promise.all(pending);await save('gradient-diagnostic-result.json',Buffer.from(JSON.stringify(result,null,2)+'\n'));
 if(browser)await browser.close();if(server)await new Promise(done=>server.close(done));
}
