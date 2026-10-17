import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {performance} from 'node:perf_hooks';
import {decodeScreenshotRgba} from './screenshot-rgba.mjs';

const evidence=resolve(process.env.BROWSER_EVIDENCE||'_build/browser-example-evidence');
const report={status:'failed',scope:'Complete Chromium-decoded RGBA equality against the original numeric-array transport',
  timing:'One observation per path and fixture; no speed assertion or runtime-performance claim',cases:[]};
const sha256=data=>createHash('sha256').update(data).digest('hex');
await mkdir(evidence,{recursive:true});
let browser;

async function numericArrayDecode(page,buffer) {
  const image=await page.evaluate(async url=>{
    const source=new Image();source.src=url;await source.decode();
    const canvas=document.createElement('canvas');canvas.width=source.width;canvas.height=source.height;
    const context=canvas.getContext('2d',{willReadFrequently:true});context.drawImage(source,0,0);
    return {width:source.width,height:source.height,data:Array.from(context.getImageData(0,0,source.width,source.height).data)};
  },'data:image/png;base64,'+buffer.toString('base64'));
  image.data=Uint8Array.from(image.data);return image;
}

async function pngFixture(page,width,height) {
  const encoded=await page.evaluate(({width,height})=>{
    const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
    const context=canvas.getContext('2d',{willReadFrequently:true}),image=context.createImageData(width,height);
    for(let pixel=0;pixel<width*height;pixel++) {
      image.data.set([(pixel*73+19)&255,(pixel*37+53)&255,(pixel*151+101)&255,pixel&255],pixel*4);
    }
    if(width*height===1)image.data.set([17,85,203,129]);
    else {
      const colors=[[0,0,0,0],[0,0,0,255],[255,255,255,255],[255,0,0,255],[0,255,0,255],[0,0,255,255]];
      for(let pixel=0;pixel<colors.length;pixel++)image.data.set(colors[pixel],pixel*4);
    }
    context.putImageData(image,0,0);
    return canvas.toDataURL('image/png').slice('data:image/png;base64,'.length);
  },{width,height});
  return Buffer.from(encoded,'base64');
}

function coverage(image) {
  const alpha=new Set(),colors=new Set();let transparent=0,opaque=0,translucent=0;
  for(let i=0;i<image.data.length;i+=4) {
    const [r,g,b,a]=image.data.subarray(i,i+4);alpha.add(a);colors.add((r<<16)|(g<<8)|b);
    if(a===0)transparent++;else if(a===255)opaque++;else translucent++;
  }
  return {alpha_values:alpha.size,distinct_rgb:colors.size,transparent,opaque,translucent};
}

try {
  assert(process.env.PLAYWRIGHT_ROOT,'PLAYWRIGHT_ROOT must identify the installed Playwright package');
  const require=createRequire(join(process.env.PLAYWRIGHT_ROOT,'package.json'));
  const {chromium}=require('playwright');
  browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||undefined,
    args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  report.environment={browser:await browser.version(),node:process.version,platform:process.platform,arch:process.arch};
  const page=await browser.newPage();
  for(const [name,width,height] of [['focus-visible',800,600],['scrollable',500,500],['tree',300,300],['odd',257,131],['tiny',1,1]]) {
    const result={name,width,height,status:'failed'};report.cases.push(result);
    const png=await pngFixture(page,width,height),originalPng=Buffer.from(png);
    result.png_sha256=sha256(png);result.png_bytes=png.length;
    const baselineStart=performance.now(),baseline=await numericArrayDecode(page,png);
    result.numeric_array_ms=performance.now()-baselineStart;
    const optimizedStart=performance.now(),optimized=await decodeScreenshotRgba(page,png);
    result.base64_ms=performance.now()-optimizedStart;
    result.observed_ratio=result.numeric_array_ms/result.base64_ms;
    assert.deepEqual([baseline.width,baseline.height,optimized.width,optimized.height],[width,height,width,height]);
    assert.equal(optimized.data.length,width*height*4);assert.equal(baseline.data.length,width*height*4);
    result.rgba_bytes=optimized.data.length;
    result.numeric_array_rgba_sha256=sha256(baseline.data);result.base64_rgba_sha256=sha256(optimized.data);
    assert.equal(Buffer.compare(baseline.data,optimized.data),0,`${name}: every decoded RGBA byte must match`);
    assert.equal(result.base64_rgba_sha256,result.numeric_array_rgba_sha256);
    assert.deepEqual(png,originalPng,'The original PNG bytes must remain unchanged');
    result.coverage=coverage(baseline);
    assert(result.coverage.translucent>0,'Alpha-bearing colors are required');
    if(width*height>1) {
      assert.equal(result.coverage.alpha_values,256);assert(result.coverage.transparent>0);assert(result.coverage.opaque>0);
      assert(result.coverage.distinct_rgb>32);
      assert.deepEqual([...optimized.data.subarray(4,24)],[0,0,0,255,255,255,255,255,255,0,0,255,0,255,0,255,0,0,255,255]);
    }
    result.status='passed';
    console.log(`PASS: ${name} ${width}x${height}; numeric_array_ms=${result.numeric_array_ms.toFixed(1)}; `+
      `base64_ms=${result.base64_ms.toFixed(1)}; matching_rgba_sha256=${result.base64_rgba_sha256}`);
  }
  report.status='passed';
  console.log('PASS: screenshot RGBA transport preserves every browser-decoded byte, original PNG, alpha/color coverage and SHA-256 at five dimensions. Timings are observations only.');
} catch(error) {
  report.failure=error.stack;process.exitCode=1;console.error(`FAIL: screenshot RGBA transport: ${error.message}`);
} finally {
  await writeFile(join(evidence,'screenshot-rgba-transport.json'),JSON.stringify(report,null,2)+'\n');
  if(browser)await browser.close();
}
