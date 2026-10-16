// Focused smoke/exact-pixel runner. No Rust comparison is implied unless bundled.
// PLAYWRIGHT_ROOT=... node web/tests/tree-browser-standalone.mjs _build/tree-site [--require-rust] [--dpr=2]
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join,sep,extname} from 'node:path';
import {checkTreePair} from './tree-browser.mjs';
const require=createRequire(join(process.env.PLAYWRIGHT_ROOT,'package.json'));
const {chromium}=require('playwright');
const site=resolve(process.argv[2]||'_build/tree-site');
const evidence=resolve(process.env.BROWSER_EVIDENCE||'_build/tree-browser-evidence');
const dpr=Number(process.argv.find(arg=>arg.startsWith('--dpr='))?.slice(6)||1);
assert([1,2].includes(dpr));
const manifest=JSON.parse(await readFile(join(site,'build-manifest.json'),'utf8'));
assert(!process.argv.includes('--require-rust')||manifest.rust_bundled,'Required Rust bundle is missing');
await mkdir(evidence,{recursive:true});
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.wasm':'application/wasm','.ttf':'font/ttf'};
const server=createServer(async(request,response)=>{
  try {
    const url=new URL(request.url,'http://localhost');
    if(!url.pathname.startsWith('/gpui-conformance/'))throw new Error('Outside site');
    let relative=decodeURIComponent(url.pathname.slice('/gpui-conformance/'.length));
    if(!relative||relative.endsWith('/'))relative+='index.html';
    const path=resolve(site,relative);if(!path.startsWith(site+sep))throw new Error('Outside site');
    response.writeHead(200,{'content-type':types[extname(path)]||'application/octet-stream',
      'Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp','Cross-Origin-Resource-Policy':'same-origin'});
    response.end(await readFile(path));
  } catch {response.writeHead(404);response.end('Not found');}
});
await new Promise(done=>server.listen(0,'127.0.0.1',done));
let browser;
try {
  browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  const page=await browser.newPage({viewport:{width:1400,height:950},deviceScaleFactor:dpr});
  await page.goto(`http://127.0.0.1:${server.address().port}/gpui-conformance/?example=tree`);
  const result=await checkTreePair({page,evidence,paired:Boolean(manifest.rust_bundled)});
  result.environment={browser:await browser.version(),platform:process.platform,arch:process.arch,node:process.version,
    graphics:'Chromium with SwiftShader requested; raw browser console retained'};
  await writeFile(join(evidence,`tree-result-dpr${dpr}.json`),JSON.stringify(result,null,2)+'\n');
  console.log(manifest.rust_bundled?`PASS: tree actual Rust/MoonBit full RGBA match at DPR ${dpr}; native/other depths unverified.`:
    `PASS: tree MoonBit scene, full screenshot contract, and negative controls at DPR ${dpr}. Rust comparison NOT RUN.`);
} finally {
  if(browser)await browser.close();await new Promise(done=>server.close(done));
}
