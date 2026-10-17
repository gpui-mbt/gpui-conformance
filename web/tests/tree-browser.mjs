import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {decodeScreenshotRgba} from './screenshot-rgba.mjs';
import {TREE,assertTreeScene,inspectTreeImage,compareTreeImages,treeNegativeControls} from './tree-comparator.mjs';

const sha256=data=>createHash('sha256').update(data).digest('hex');

// Reusable from candidate-browser.mjs. Use direct runtime pages at an integer
// origin: no fractional iframe clipping, resizing, masks, or candidate-drawn oracle.
// The existing page's selection, viewport, and canvas are left untouched.
export async function checkTreePair({page,evidence,paired=true}) {
  await mkdir(evidence,{recursive:true});
  const base=new URL('./',page.url());
  const dpr=await page.evaluate(()=>devicePixelRatio);
  assert([1,2].includes(dpr),'Tree pixel evidence is scoped to DPR 1 or 2');
  const suffix=`dpr${dpr}`;
  const manifest=await (await page.request.get(new URL('build-manifest.json',base).href)).json();
  const catalog=await (await page.request.get(new URL('examples.json',base).href)).json();
  const example=catalog.examples.find(e=>e.id==='tree');
  assert.equal(example?.source_blob,TREE.sourceBlob,'Require the unchanged pinned tree.rs source');
  assert.equal(example.source,'crates/gpui/examples/tree.rs');
  assert.equal(manifest.upstream.revision,catalog.upstream.revision);
  assert(!paired || manifest.rust_bundled,'Rust comparison requested without real WASM artifacts');
  if(paired) {
    assert.equal(manifest.rust.source_modified,false);
    assert(manifest.rust_implemented.includes('tree'));
  }
  const result={status:'failed',comparison:paired?'pending':'not_run',
    scope:`pinned default tree.rs; 300x300 CSS pixels; Chromium DPR ${dpr}`,
    expected_source_blob:TREE.sourceBlob,build:manifest,captures:{},requests:[],console:[],errors:[],
    unverified:['native renderer parity','non-default depths','other viewport sizes','other browsers and GPUs']};
  const context=await page.context().browser().newContext({viewport:{width:300,height:300},deviceScaleFactor:dpr});
  const pages=[];const captures={};let scene;
  try {
    for(const side of ['moonbit',...(paired?['rust']:[])]) {
      const runtimePage=await context.newPage();pages.push(runtimePage);
      await runtimePage.setViewportSize({width:300,height:300});
      runtimePage.on('pageerror',error=>result.errors.push({side,message:error.message}));
      runtimePage.on('console',message=>result.console.push({side,type:message.type(),text:message.text()}));
      runtimePage.on('response',response=>result.requests.push({side,url:response.url(),status:response.status()}));
      await runtimePage.goto(new URL(`${side}/?example=tree`,base).href);
      await runtimePage.locator(`html[data-runtime-status="${side==='rust'?'initialized':'ready'}"]`).waitFor({timeout:60000});
      assert.equal(await runtimePage.evaluate(()=>crossOriginIsolated),true,'Same-origin isolated runtime required');
      assert.equal(await runtimePage.evaluate(()=>devicePixelRatio),dpr);
      const canvas=runtimePage.locator('canvas');
      const bounds=await canvas.boundingBox();
      assert.deepEqual(bounds,{x:0,y:0,width:300,height:300},'Full canvas must start at the exact viewport origin');
      const backing=await canvas.evaluate(c=>({width:c.width,height:c.height}));
      // Record sizing before rejecting it so unsupported upstream DPR behavior
      // stays visible in failed evidence rather than being resized away.
      result.captures[side]={url:runtimePage.url(),bounds,backing,dpr};
      assert.deepEqual(backing,{width:300*dpr,height:300*dpr},`${side}: backing canvas must match device-pixel size without resampling`);
      if(side==='moonbit') {
        scene=await runtimePage.locator('html').evaluate(()=>globalThis.gpuiExample);
        await writeFile(join(evidence,`tree-moonbit-scene-${suffix}.json`),JSON.stringify(scene,null,2)+'\n');
        result.scene=assertTreeScene(scene,dpr);
      }
      // The Rust host signal promises a canvas, not a presented frame. Require
      // actual palette pixels and two equal consecutive captures before judging.
      const deadline=Date.now()+30000;let previousHash=null,buffer,image,stable=false;
      do {
        buffer=await runtimePage.screenshot({animations:'disabled',scale:'device'});
        assert.equal(buffer.readUInt32BE(16),300*dpr);assert.equal(buffer.readUInt32BE(20),300*dpr);
        image=await decodeScreenshotRgba(runtimePage,buffer);
        let hasGreen=false,hasBlue=false;
        for(let i=0;i<image.data.length;i+=4) {
          hasGreen ||= image.data[i]===0&&image.data[i+1]===128&&image.data[i+2]===0;
          hasBlue ||= image.data[i]===0&&image.data[i+1]===0&&image.data[i+2]===255;
        }
        const hash=sha256(image.data);
        stable=hasGreen&&hasBlue&&hash===previousHash;previousHash=hash;
        if(!stable)await runtimePage.waitForTimeout(100);
      } while(!stable&&Date.now()<deadline);
      // Retain even failed final captures; no golden update or fallback is allowed.
      await writeFile(join(evidence,`tree-${side}-${suffix}.png`),buffer);
      captures[side]=image;
      result.captures[side]={url:runtimePage.url(),method:'complete 300x300 viewport screenshot at integer canvas origin',
        bounds,backing,dpr,png_sha256:sha256(buffer),rgba_sha256:sha256(image.data),stable_rendered_palette:stable};
      result[side]=inspectTreeImage(image,dpr);
      assert(stable,`${side}: no stable rendered tree palette before deadline`);
      const required=side==='rust'?['tree.js','tree_bg.wasm']:['tree.mjs'];
      for(const file of required) assert(result.requests.some(r=>r.side===side&&new URL(r.url).pathname.endsWith('/'+file)&&r.status===200),
        `${side}: actual ${file} HTTP 200 response required`);
      // Verify that the bytes served match the retained build manifest too.
      for(const file of required) {
        const response=await page.request.get(new URL(`${side}/${file}`,base).href);
        assert.equal(response.status(),200);
        const digest=sha256(await response.body());
        assert.equal(digest,side==='rust'?manifest.rust.files[file]:manifest.runtime_sha256_by_example.tree);
      }
    }
    result.negative_controls=treeNegativeControls(scene,captures.moonbit,dpr);
    assert.deepEqual(result.errors,[],'Runtime JavaScript errors are not allowed');
    if(paired) {
      result.comparison=compareTreeImages(captures.rust,captures.moonbit,dpr);
      assert.equal(result.comparison.status,'passed',`tree exact comparison failed: ${result.comparison.different_pixels} differing pixels; `+
        `Rust contract mismatches ${result.comparison.rust.mismatched_pixels}; MoonBit contract mismatches ${result.comparison.moonbit.mismatched_pixels}`);
      result.status='passed';
    } else {
      assert.equal(result.moonbit.status,'passed',`MoonBit tree has ${result.moonbit.mismatched_pixels} incorrect pixels`);
      result.status='candidate_only_passed';
      result.unverified.unshift('Rust/MoonBit pixel comparison: Rust bundle unavailable');
    }
    return result;
  } catch(error) {
    result.failure=error.stack;
    throw error;
  } finally {
    await writeFile(join(evidence,`tree-result-${suffix}.json`),JSON.stringify(result,null,2)+'\n');
    await context.close();
  }
}
