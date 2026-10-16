import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, join, extname, sep } from 'node:path';
const require = createRequire(join(process.env.PLAYWRIGHT_ROOT, 'package.json'));
const { chromium } = require('playwright');
const site = resolve(process.argv[2] || '_build/browser-lab');
const evidence = resolve(process.env.BROWSER_EVIDENCE || '_build/browser-example-evidence');
const required = process.argv.includes('--require-rust');
const manifest = JSON.parse(await readFile(join(site, 'build-manifest.json'), 'utf8'));
const paired = Boolean(manifest.rust_bundled);
await mkdir(evidence, { recursive: true });
const types = { '.html':'text/html', '.js':'text/javascript', '.mjs':'text/javascript', '.css':'text/css', '.json':'application/json', '.ttf':'font/ttf', '.wasm':'application/wasm' };
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://localhost');
    if (!url.pathname.startsWith('/gpui-conformance/')) throw new Error('Outside test site');
    let relative = decodeURIComponent(url.pathname.slice('/gpui-conformance/'.length));
    if (!relative || relative.endsWith('/')) relative += 'index.html';
    const path = resolve(site, relative);
    if (!path.startsWith(site + sep)) throw new Error('Outside test site');
    const content = await readFile(path);
    response.writeHead(200, { 'content-type': types[extname(path)] || 'application/octet-stream', 'Cross-Origin-Opener-Policy':'same-origin', 'Cross-Origin-Embedder-Policy':'require-corp', 'Cross-Origin-Resource-Policy':'same-origin' }); response.end(content);
  } catch { response.writeHead(404); response.end('Not found'); }
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
let browser;
const report = { overall: 'failed', candidate: 'failed', rust: 'not_run', comparison: 'unverified', verified: [], unverified: ['native parity', 'text shaping and rasterization', 'application event handling', 'IME and interactive examples'], operations: [], errors: [], console: [], requests: [] };
report.build = manifest;
report.environment = {platform: process.platform, arch: process.arch, node: process.version, graphics: 'Chromium with SwiftShader requested; raw backend logs retained'};
let page;
try {
  assert(!required || paired, 'Required Rust bundle is missing');
  browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  report.environment.browser = await browser.version();
  page = await browser.newPage({ viewport: { width: 1400, height: 950 }, deviceScaleFactor: 1 });
  const errors = report.errors; page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => report.console.push({type: message.type(), text: message.text()}));
  page.on('response', response => report.requests.push({url: response.url(), status: response.status()}));
  await page.addInitScript(() => {
    globalThis.browserEvents = [];
    for (const type of ['pointerdown', 'pointerup', 'click', 'keydown', 'keyup']) {
      addEventListener(type, event => globalThis.browserEvents.push({type, key: event.key, x: event.clientX, y: event.clientY, trusted: event.isTrusted, target: event.target.tagName, time: performance.now()}), true);
    }
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/gpui-conformance/`);
  async function waitForNewDocuments() {
    await page.waitForFunction(paired => ['moon', ...(paired ? ['rust'] : [])].every(side => {
      const iframe = document.getElementById(side + '-frame');
      try {
        return iframe.contentWindow.location.href === iframe.src &&
          iframe.contentDocument.documentElement.dataset.runtimeStatus === (side === 'moon' ? 'ready' : 'initialized');
      } catch { return false; }
    }), paired, {timeout:60000});
    await page.waitForFunction(paired => globalThis.gpuiLoadComparison &&
      ['moon', ...(paired ? ['rust'] : [])].every(side => gpuiLoadComparison.sides[side].status === 'complete'), paired, {timeout: 60000});
    const timing = await page.evaluate(() => gpuiLoadComparison);
    assert.equal(timing.firstPresentedFrame, 'unavailable');
    assert.equal(timing.cache, 'normal-browser-cache-uncontrolled');
    assert.equal(timing.example, await page.locator('#fixture').inputValue());
    for (const side of ['moon', ...(paired ? ['rust'] : [])]) {
      const observed = timing.sides[side];
      for (const key of ['documentMs', 'payloadMs', 'runtimeSignalMs']) assert(Number.isFinite(observed[key]) && observed[key] >= 0, `${side} ${key} must come from actual Resource/Navigation Timing`);
      assert(observed.runtimeSignalMs >= observed.payloadMs);
      const names = observed.files.map(file => new URL(file.url).pathname.split('/').at(-1));
      assert.deepEqual(names, side === 'rust' ? [`${timing.example}.js`, `${timing.example}_bg.wasm`] :
        timing.example === 'hello_world' ? ['runtime.mjs', 'IBMPlexSans-Regular.ttf'] :
        ['text_wrapper', 'hello_web', 'input'].includes(timing.example) ? [`${timing.example}.mjs`, 'IBMPlexSans-Regular.ttf'] :
        ['text_layout.mjs', 'IBMPlexSans-Regular.ttf', 'IBMPlexSans-Italic.ttf', 'IBMPlexSans-SemiBold.ttf']);
    }
    report.load_runs ||= [];
    report.load_runs.push(timing); // Observations only: not first-paint or benchmark evidence.
  }
  await waitForNewDocuments();
  assert.match(manifest.lab_revision, /^[0-9a-f]{40}$/);
  assert.equal(await page.locator('#moon-source').getAttribute('href'),
    `https://github.com/gpui-mbt/gpui-conformance/blob/${manifest.lab_revision}/web/moonbit/hello_world/hello_world.mbt`);
  assert.equal(typeof manifest.lab_tracked_dirty, 'boolean');
  const moon = page.frameLocator('#moon-frame');
  await moon.locator('html[data-runtime-status="ready"]').waitFor({ timeout: 30000 });
  const frame = await moon.locator('html').evaluate(() => globalThis.gpuiExample);
  assert.equal(frame.metadata.id, 'hello_world');
  assert.equal(frame.metadata.text, 'Hello, World!');
  assert.equal(frame.frame.snapshot.items.length, 8);
  assert.equal(frame.frame.conformance, 'unverified');
  const swatches = frame.frame.snapshot.items.filter(item => item.kind === 'quad' && item.id !== 1);
  assert.equal(swatches.length, 6);
  assert.equal(swatches[0].bounds.x, 134); assert.equal(swatches[0].bounds.y, 256);
  assert.equal(swatches[5].bounds.x, 334);
  assert.deepEqual(swatches.map(s => [s.color.red,s.color.green,s.color.blue]), [[255,0,0],[0,128,0],[0,0,255],[255,255,0],[0,0,0],[255,255,255]]);
  await writeFile(join(evidence, 'moonbit-scene.json'), JSON.stringify(frame, null, 2));
  report.text_metrics = await moon.locator('canvas').evaluate(canvas => {
    const {frame, metadata} = globalThis.gpuiExample;
    const item = frame.snapshot.items.find(item => item.kind === 'text');
    const context = canvas.getContext('2d');
    context.save();
    context.font = `${item.font_size}px "${metadata.font_family}"`;
    const m = context.measureText(item.text);
    context.restore();
    const metrics = Object.fromEntries(['width','fontBoundingBoxAscent','fontBoundingBoxDescent',
      'actualBoundingBoxAscent','actualBoundingBoxDescent','actualBoundingBoxLeft','actualBoundingBoxRight']
      .map(key => [key, m[key]]));
    return {font: metadata.font_family, font_size: item.font_size, bounds: item.bounds, ...metrics,
      baseline: item.bounds.y + (item.bounds.height - m.fontBoundingBoxAscent - m.fontBoundingBoxDescent) / 2 + m.fontBoundingBoxAscent};
  });
  async function captureCanvas(locator, side, width = 500, height = 500) {
    await locator.scrollIntoViewIfNeeded();
    // Center away from viewport edges: rounding a fractional bottom-edge origin
    // up to an integer can otherwise truncate a 500px clip to 499px.
    await locator.evaluate(canvas => canvas.scrollIntoView({block: 'center', inline: 'center', behavior: 'instant'}));
    const bounds = await locator.boundingBox();
    assert.equal(bounds.width, width); assert.equal(bounds.height, height);
    const clip = {x: Math.ceil(bounds.x), y: Math.ceil(bounds.y), width, height};
    const viewport = page.viewportSize();
    assert(clip.x >= 0 && clip.y >= 0 && clip.x + width <= viewport.width && clip.y + height <= viewport.height,
      'The full integer clip must fit inside the viewport');
    report.captures ||= {};
    report.captures[side] = {bounds, clip, method:'integer CSS pixel page clip; no rescaling or masking'};
    const buffer = await page.screenshot({clip});
    assert.equal(buffer.readUInt32BE(16), width, 'PNG width must equal the complete fixture width');
    assert.equal(buffer.readUInt32BE(20), height, 'PNG height must equal the complete fixture height');
    return buffer;
  }
  await writeFile(join(evidence, 'moonbit.png'), await captureCanvas(moon.locator('canvas'), 'moonbit'));
  report.candidate = 'passed';
  if (paired) {
    report.rust = 'failed';
    await page.frameLocator('#rust-frame').locator('html[data-runtime-status="initialized"]').waitFor({timeout: 60000});
    assert.equal(await page.evaluate(() => crossOriginIsolated), true);
    for (const id of ['rust-frame', 'moon-frame']) {
      const url = await page.locator('#' + id).getAttribute('src');
      assert.equal(new URL(url).origin, new URL(page.url()).origin);
    }
    const rust = page.frameLocator('#rust-frame');
    assert.equal(await rust.locator('html').evaluate(() => crossOriginIsolated), true);
    const probes = [[150,272,255,0,0], [190,272,0,128,0], [230,272,0,0,255], [270,272,255,255,0], [310,272,0,0,0], [350,272,255,255,255]];
    async function inspectCanvas(locator, side) {
      const buffer = await captureCanvas(locator, side);
      const pixels = await page.evaluate(async ({url, probes}) => {
        const image = new Image(); image.src = url; await image.decode();
        const canvas = document.createElement('canvas'); canvas.width = 500; canvas.height = 500;
        const context = canvas.getContext('2d', {willReadFrequently:true}); context.drawImage(image, 0, 0);
        return probes.map(([x,y]) => [...context.getImageData(x,y,1,1).data].slice(0,3));
      }, {url: 'data:image/png;base64,' + buffer.toString('base64'), probes});
      return {buffer, pixels};
    }
    const expected = probes.map(p => p.slice(2));
    let observed;
    const deadline = Date.now() + 30000;
    do {
      observed = await inspectCanvas(rust.locator('canvas'), 'rust');
      if (JSON.stringify(observed.pixels) === JSON.stringify(expected)) break;
      await page.waitForTimeout(200);
    } while (Date.now() < deadline);
    await writeFile(join(evidence, 'rust.png'), observed.buffer);
    report.probes = {coordinates: probes.map(p => p.slice(0,2)), expected, rust: observed.pixels, moonbit: (await inspectCanvas(moon.locator('canvas'), 'moonbit')).pixels};
    const offsets = Object.fromEntries(['rust','moonbit'].map(side => [side, {
      x: report.captures[side].clip.x - report.captures[side].bounds.x,
      y: report.captures[side].clip.y - report.captures[side].bounds.y,
    }]));
    assert(Math.abs(offsets.rust.x - offsets.moonbit.x) < 1e-7);
    assert(Math.abs(offsets.rust.y - offsets.moonbit.y) < 1e-7);
    report.capture_alignment = {offsets, equal_fractional_offsets: true};
    assert.deepEqual(report.probes.rust, expected, 'Real Rust canvas must render all six color probes');
    assert.deepEqual(report.probes.moonbit, expected);
    assert(report.requests.some(r => r.url.includes('/rust/') && r.url.endsWith('.wasm') && r.status === 200), 'Actual WASM response required');
    for (const [side, pane] of [['rust',rust], ['moonbit',moon]]) {
      await pane.locator('canvas').click({position:{x:150,y:272}});
      await page.keyboard.press('Enter');
      const events = await pane.locator('html').evaluate(() => browserEvents);
      assert(events.some(e => e.type === 'click' && e.trusted));
      assert(events.some(e => e.type === 'keydown' && e.key === 'Enter' && e.trusted));
      await writeFile(join(evidence, side + '-browser-events.json'), JSON.stringify(events, null, 2));
      assert.deepEqual((await inspectCanvas(pane.locator('canvas'), side)).pixels, expected);
      report.operations.push({side, action:'pointer click then Enter', delivery:'passed', color_probes_after:'passed', application_handling:'not_applicable_static_example'});
    }
    report.rust = 'passed';
    report.comparison = 'color_probes_matched_pixel_parity_unverified';
    report.verified.push('same-origin compiled Rust WASM and MoonBit JS', '500x500 viewports', 'six rendered swatch RGB probes', 'trusted browser click/key delivery; static swatches retained');
  }
  await page.screenshot({ path: join(evidence, 'hello-world-pair.png'), fullPage: true });
  await page.setViewportSize({width:2000,height:1100});
  await page.selectOption('#fixture', 'text_layout');
  await waitForNewDocuments();
  const textFrame = await moon.locator('html').evaluate(() => globalThis.gpuiExample);
  assert.equal(textFrame.metadata.id, 'text_layout');
  assert.deepEqual([textFrame.metadata.width,textFrame.metadata.height], [800,600]);
  assert.equal(textFrame.frame.snapshot.items.filter(i => i.kind === 'text').length,15);
  assert.equal(textFrame.frame.snapshot.clip_chains.length,2);
  assert.equal(textFrame.frame.conformance,'unverified');
  assert.equal(textFrame.frame.text_styles.filter(s=>s.decoration==='underline').length,3);
  assert.equal(textFrame.frame.text_styles.filter(s=>s.decoration==='line_through').length,3);
  for (const side of ['moon', ...(paired ? ['rust'] : [])]) {
    const bounds = await page.locator('#' + side + '-frame').boundingBox();
    assert.deepEqual([bounds.width,bounds.height],[800,600]);
  }
  assert.equal(await page.locator('#moon-source').getAttribute('href'),
    `https://github.com/gpui-mbt/gpui-conformance/blob/${manifest.lab_revision}/web/moonbit/text_layout/text_layout.mbt`);
  for (const side of ['moon', ...(paired ? ['rust'] : [])]) {
    const visible = await page.locator('#' + side + '-frame').evaluate(iframe => {
      const canvas = iframe.contentDocument.querySelector('canvas');
      const frame = iframe.getBoundingClientRect();
      const scroll = iframe.parentElement.getBoundingClientRect();
      return canvas.width > 0 && canvas.height > 0 && frame.left >= scroll.left &&
        frame.top >= scroll.top && frame.right <= scroll.right && frame.bottom <= scroll.bottom;
    });
    assert(visible, `${side} full text_layout canvas must fit its ancestor before capture`);
  }
  await writeFile(join(evidence,'text-layout-moonbit-scene.json'),JSON.stringify(textFrame,null,2));
  await writeFile(join(evidence,'text-layout-moonbit.png'), await captureCanvas(moon.locator('canvas'), 'text_layout_moonbit', 800, 600));
  if (paired) {
    assert(report.requests.some(r => r.url.endsWith('/rust/text_layout_bg.wasm') && r.status===200), 'Actual text_layout WASM response required');
    // A canvas existing is insufficient: wait for dark ink in the first text line.
    const rustCanvas = page.frameLocator('#rust-frame').locator('canvas');
    let ink = false;
    for (let attempt=0; attempt<100 && !ink; attempt++) {
      const buffer=await captureCanvas(rustCanvas, 'text_layout_rust', 800, 600);
      ink = await page.evaluate(async url => {
        const img=new Image(); img.src=url; await img.decode();
        if (img.width !== 800 || img.height !== 600) throw new Error('Expected exact 800x600 text_layout capture');
        const c=document.createElement('canvas');c.width=800;c.height=600;
        const ctx=c.getContext('2d');ctx.drawImage(img,0,0);
        const pixels=ctx.getImageData(16,16,120,26).data;
        for(let i=0;i<pixels.length;i+=4) if(pixels[i]<100 && pixels[i+1]<100 && pixels[i+2]<100) return true;
        return false;
      },'data:image/png;base64,'+buffer.toString('base64'));
      if (ink) await writeFile(join(evidence,'text-layout-rust.png'),buffer);
      else await page.waitForTimeout(200);
    }
    assert(ink,'Upstream text_layout must render actual dark text ink');
  }
  report.operations.push({action:'select text_layout',candidate:'15 text scene items, decorated runs and clip chains',rust:paired?'actual WASM and text ink verified':'not_run',comparison:'unverified'});
  await page.screenshot({path:join(evidence,'text-layout-pair.png'),fullPage:true});
  await page.selectOption('#fixture', 'text_wrapper');
  await waitForNewDocuments();
  const wrapperFrame = await moon.locator('html').evaluate(() => globalThis.gpuiExample);
  assert.equal(wrapperFrame.metadata.id, 'text_wrapper');
  assert.deepEqual([wrapperFrame.metadata.width,wrapperFrame.metadata.height],[800,600]);
  assert.equal(wrapperFrame.frame.conformance,'unverified');
  assert.equal(wrapperFrame.frame.runs.length,9);
  const runs = wrapperFrame.frame.runs;
  for(const index of [0,1]) {
    assert.deepEqual(runs[index].lines,[runs[index].original_text], 'Visible-overflow flex samples retain their intrinsic text');
    assert.equal(runs[index].truncated,false);
    const measured = wrapperFrame.textWidth.prefixes[index].at(-1);
    assert.equal(runs[index].content_width,Math.ceil(measured));
    assert.equal(runs[index].box_bounds.width,Math.ceil(measured)+2);
  }
  assert.equal(runs[0].box_bounds.width+runs[1].box_bounds.width+runs[2].box_bounds.width+16,784);
  assert(runs[3].truncated && runs[3].lines.length === 1 && runs[3].lines[0].endsWith('…'));
  assert(runs[4].clamped && runs[4].lines.length === 2 && runs[4].lines.at(-1).endsWith('…'));
  assert(runs[5].truncated && runs[5].lines.length === 1 && !runs[5].lines[0].endsWith('…'));
  assert(runs[6].clamped && runs[6].lines.length === 3 && !runs[6].lines.at(-1).endsWith('…'));
  assert.deepEqual(runs[7].lines,[runs[7].original_text]);
  assert.equal(runs[7].truncated,false);
  assert(runs[8].lines.length > 3 && !runs[8].truncated);
  assert.equal(runs[8].lines.join(''),runs[8].original_text);
  assert.match(runs[8].original_text,/你好世界/);
  assert.match(runs[8].original_text,/こんにちは/);
  assert.match(runs[8].original_text,/https:\/\/github.com\/zed-industries\/zed\/pull\/35724/);
  assert.equal(wrapperFrame.frame.decorations.length,8);
  assert.deepEqual(wrapperFrame.frame.decorations.map(d => d.border),
    ['#ff0000','#ff0000','#ff0000','#0000ff','#0000ff','#008000','#008000','#000000']);
  assert.equal(wrapperFrame.frame.snapshot.clip_chains.length,6);
  assert.equal(await page.locator('#moon-source').getAttribute('href'),
    `https://github.com/gpui-mbt/gpui-conformance/blob/${manifest.lab_revision}/web/moonbit/text_wrapper/text_wrapper.mbt`);
  for (const side of ['moon', ...(paired ? ['rust'] : [])]) {
    const bounds=await page.locator('#'+side+'-frame').boundingBox();
    assert.deepEqual([bounds.width,bounds.height],[800,600]);
  }
  await writeFile(join(evidence,'text-wrapper-moonbit-scene.json'),JSON.stringify(wrapperFrame,null,2));
  async function wrapperInk(buffer) {
    return page.evaluate(async url => {
      const image=new Image(); image.src=url; await image.decode();
      if(image.width !== 800 || image.height !== 600) throw new Error('Expected complete text_wrapper canvas');
      const canvas=document.createElement('canvas');canvas.width=800;canvas.height=600;
      const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);
      const pixels=ctx.getImageData(0,0,800,600).data;
      const counts={red:0,blue:0,green:0,dark:0,lowerDark:0};
      for(let i=0;i<pixels.length;i+=4) {
        const [r,g,b]=pixels.slice(i,i+3);
        if(r>220 && g<35 && b<35) counts.red++;
        if(r<35 && g<35 && b>220) counts.blue++;
        if(r<35 && g>=100 && g<=155 && b<35) counts.green++;
        if(r<100 && g<100 && b<100) {
          counts.dark++;
          if(i/4/800 >= 350) counts.lowerDark++;
        }
      }
      return counts;
    },'data:image/png;base64,'+buffer.toString('base64'));
  }
  const renderedWrapper = counts => counts.red>200 && counts.blue>1000 && counts.green>1000 && counts.dark>1000 && counts.lowerDark>50;
  const candidateWrapper=await captureCanvas(moon.locator('canvas'),'text_wrapper_moonbit',800,600);
  const candidateInk=await wrapperInk(candidateWrapper);
  assert(renderedWrapper(candidateInk),'Candidate must draw actual colored borders and paragraph ink');
  await writeFile(join(evidence,'text-wrapper-moonbit.png'),candidateWrapper);
  let rustInk=null;
  if(paired) {
    assert(report.requests.some(r => r.url.endsWith('/rust/text_wrapper_bg.wasm') && r.status===200),'Actual text_wrapper WASM response required');
    const rustCanvas=page.frameLocator('#rust-frame').locator('canvas');
    for(let attempt=0;attempt<100;attempt++) {
      const buffer=await captureCanvas(rustCanvas,'text_wrapper_rust',800,600);
      rustInk=await wrapperInk(buffer);
      if(renderedWrapper(rustInk)) {
        await writeFile(join(evidence,'text-wrapper-rust.png'),buffer);
        break;
      }
      await page.waitForTimeout(200);
    }
    assert(renderedWrapper(rustInk),'Upstream must draw actual colored borders and paragraph ink');
  }
  report.operations.push({action:'select text_wrapper',candidate:'MoonBit ellipsis, two/three-line clamps, nowrap and complete wrapped text verified',rust:paired?'actual WASM, colored borders and text ink verified':'not_run',ink:{candidate:candidateInk,rust:rustInk},comparison:'unverified'});
  await page.screenshot({path:join(evidence,'text-wrapper-pair.png'),fullPage:true});
  const wrapperUrl=await page.locator('#moon-frame').getAttribute('src');
  await page.locator('#settings button').click();
  await waitForNewDocuments();
  assert.notEqual(await page.locator('#moon-frame').getAttribute('src'),wrapperUrl);
  assert.deepEqual(await moon.locator('html').evaluate(() => gpuiExample.frame.runs),runs);
  report.operations.push({action:'reload text_wrapper pair',result:'fresh runtimes and stable wrapping output'});
  // Real upstream Prime sieve, including actual 10M computation. This is a CPU
  // task result, never a renderer-startup measurement or a performance ranking.
  await page.selectOption('#fixture', 'hello_web');
  await waitForNewDocuments();
  const primeCanvas=moon.locator('canvas');
  let prime=await moon.locator('html').evaluate(()=>gpuiExample);
  assert.deepEqual([prime.metadata.width,prime.metadata.height,prime.metadata.interactive],[640,560,true]);
  assert.equal(prime.content.running,false);
  async function clickPrime(id) {
    const bounds=await moon.locator('html').evaluate((_,id)=>gpuiExample.frame.snapshot.items.find(item=>item.id===id).bounds,id);
    await primeCanvas.click({position:{x:bounds.x+bounds.width/2,y:bounds.y+bounds.height/2}});
  }
  for(const [id,selected] of [[24,1],[25,2],[23,0]]) {
    await clickPrime(id);
    assert.equal(await moon.locator('html').evaluate(()=>gpuiExample.content.selected),selected);
  }
  await writeFile(join(evidence,'prime-sieve-moonbit-initial.png'),await captureCanvas(primeCanvas,'hello_web_moonbit_initial',640,560));
  await clickPrime(26);
  assert.equal(await moon.locator('html').evaluate(()=>gpuiExample.content.running),true);
  await clickPrime(25);await clickPrime(26);
  prime=await moon.locator('html').evaluate(()=>gpuiExample);
  assert.equal(prime.content.selected,0);
  assert.equal(prime.content.generation,1);
  await writeFile(join(evidence,'prime-sieve-moonbit-running.png'),await captureCanvas(primeCanvas,'hello_web_moonbit_running',640,560));
  await moon.locator('html').evaluate(async()=>{
    const end=performance.now()+120000;
    while(gpuiExample.content.running && performance.now()<end) await new Promise(r=>setTimeout(r,50));
    if(gpuiExample.content.running) throw new Error('10M worker computation timed out');
  });
  prime=await moon.locator('html').evaluate(()=>gpuiExample);
  assert.equal(prime.content.total,664579);
  assert.equal(prime.content.chunks_done,12);
  assert.equal(prime.content.failed,false);
  assert.equal(prime.content.history.length,1);
  assert.equal(prime.workers.active,0);
  assert.equal(prime.workers.created,prime.workers.terminated);
  assert.equal(prime.workers.completed.length,12);
  assert.equal(prime.workers.completed.reduce((sum,c)=>sum+c.count,0),664579);
  const chunks=[...prime.workers.completed].sort((a,b)=>a.index-b.index);
  assert.equal(chunks[0].start,0);assert.equal(chunks.at(-1).end,10000000);
  for(let i=1;i<12;i++) assert.equal(chunks[i-1].end,chunks[i].start);
  await writeFile(join(evidence,'prime-sieve-moonbit-result.png'),await captureCanvas(primeCanvas,'hello_web_moonbit_result',640,560));
  await writeFile(join(evidence,'prime-sieve-moonbit-scene.json'),JSON.stringify(prime,null,2));
  let rustPrimeOcr=null;
  if(paired) {
    assert(report.requests.some(r=>r.url.endsWith('/rust/hello_web_bg.wasm')&&r.status===200));
    const rustCanvas=page.frameLocator('#rust-frame').locator('canvas');
    const initial=join(evidence,'prime-sieve-rust-initial.png');
    let button=null;
    for(let attempt=0;attempt<60;attempt++) {
      const image=await captureCanvas(rustCanvas,'hello_web_rust_initial',640,560);
      await writeFile(initial,image);
      button=await page.evaluate(async url=>{
        const image=new Image();image.src=url;await image.decode();
        const c=document.createElement('canvas');c.width=640;c.height=560;
        const ctx=c.getContext('2d');ctx.drawImage(image,0,0);
        const pixels=ctx.getImageData(0,0,640,560).data;
        let count=0,x=0,y=0;
        for(let i=0;i<pixels.length;i+=4) {
          if(pixels[i]===166 && pixels[i+1]===227 && pixels[i+2]===161) {
            count++;x+=(i/4)%640;y+=Math.floor(i/4/640);
          }
        }
        return count>1000?{x:x/count,y:y/count,pixels:count}:null;
      },'data:image/png;base64,'+image.toString('base64'));
      if(button) break;
      await page.waitForTimeout(250);
    }
    // The upstream idle screen has exactly one green region: Count Primes.
    // Derive its center from actual rendered pixels, never candidate geometry.
    assert(button,'Actual upstream green Count Primes button must be rendered');
    await rustCanvas.click({position:{x:button.x,y:button.y}});
    const resultPath=join(evidence,'prime-sieve-rust-result.png');
    const end=Date.now()+120000;
    do {
      await writeFile(resultPath,await captureCanvas(rustCanvas,'hello_web_rust_result',640,560));
      rustPrimeOcr=execFileSync('tesseract',[resultPath,'stdout','--psm','6'],{encoding:'utf8',stdio:['ignore','pipe','pipe']});
      if(/Found\s+664,579\s+primes\s+below\s+10,000,000/.test(rustPrimeOcr)) break;
      await page.waitForTimeout(500);
    } while(Date.now()<end);
    await writeFile(join(evidence,'prime-sieve-rust-ocr.txt'),rustPrimeOcr);
    assert.match(rustPrimeOcr,/Found\s+664,579\s+primes\s+below\s+10,000,000/,'Real upstream rendered result must confirm the full 10M run');
  }
  await page.screenshot({path:join(evidence,'prime-sieve-pair.png'),fullPage:true});
  report.operations.push({action:'run actual 10M Prime sieve',candidate:'12 real compiled MoonBit worker chunks; total 664579; pool released; preset and repeated-start clicks ignored while running',rust:paired?'actual hello_web WASM, trusted Count Primes click and rendered 664579 result verified by retained OCR':'not_run',comparison:'functional count matched; pixel, scheduler and performance equivalence unverified',unexecuted_presets:[50000000,100000000]});
  // A completed run can restart; switching away while that next run is in flight
  // must release worker resources and a fresh document must start with empty state.
  await clickPrime(26);
  assert.equal(await moon.locator('html').evaluate(()=>gpuiExample.content.generation),2);
  await page.evaluate(()=>{globalThis.oldPrimeWorkers=document.getElementById('moon-frame').contentWindow.gpuiExample.workers;});
  await page.selectOption('#fixture','input');
  await page.waitForFunction(()=>globalThis.oldPrimeWorkers?.active === 0);
  await page.selectOption('#fixture','hello_web');
  await waitForNewDocuments();
  prime=await moon.locator('html').evaluate(()=>gpuiExample);
  assert.equal(prime.content.generation,0);assert.equal(prime.content.running,false);
  assert.equal(prime.content.history.length,0);assert.equal(prime.workers.active,0);
  assert.equal(await page.evaluate(()=>oldPrimeWorkers.active),0);
  assert.equal(await page.evaluate(()=>oldPrimeWorkers.created===oldPrimeWorkers.terminated),true);
  assert.equal(await page.evaluate(()=>oldPrimeWorkers.stopped),true);
  report.operations.push({action:'leave Prime sieve during second real run and reopen',result:'fresh idle state, no retained history or active worker pool'});

  await page.setViewportSize({width:1400,height:950});
  await page.selectOption('#fixture', 'input');
  await waitForNewDocuments();
  const inputFrame = await moon.locator('html').evaluate(() => globalThis.gpuiExample);
  assert.equal(inputFrame.metadata.id, 'input');
  assert.deepEqual([inputFrame.metadata.width,inputFrame.metadata.height],[300,300]);
  assert.equal(inputFrame.frame.conformance,'unverified');
  assert(inputFrame.frame.snapshot.items.some(item => item.kind==='text_run'),
    'Actual gpui.mbt TextField.paint_items run must be rendered');
  assert.equal(inputFrame.input.text,'');
  const inputEditor = moon.locator('textarea[data-gpui-input="true"]');
  await inputEditor.focus();
  const getInput = () => moon.locator('html').evaluate(() => globalThis.gpuiExample.input);
  await page.keyboard.type('abc');
  assert.deepEqual([ (await getInput()).text, (await getInput()).head ],['abc',3]);
  await page.keyboard.press('ArrowLeft');
  assert.equal((await getInput()).head,2);
  await page.keyboard.press('Shift+ArrowRight');
  assert.deepEqual([(await getInput()).anchor,(await getInput()).head],[2,3]);
  await page.keyboard.press('Control+c');
  assert.equal((await getInput()).text,'abc');
  const copyEvents = await moon.locator('html').evaluate(() => gpuiExample.inputEvents.filter(e=>e.type==='copy'));
  assert(copyEvents.some(e=>e.length===1 && e.trusted),'Trusted Chromium copy must reach isolated host');
  await page.keyboard.press('Control+x');
  assert.equal((await getInput()).text,'ab');
  await page.keyboard.press('Control+z');
  assert.equal((await getInput()).text,'abc');
  await page.keyboard.press('Control+Shift+z');
  assert.equal((await getInput()).text,'ab');
  await page.keyboard.press('Control+a');
  assert.deepEqual([(await getInput()).anchor,(await getInput()).head],[0,2]);
  // A DataTransfer/ClipboardEvent is a deterministic browser transport test,
  // not a claim that the OS clipboard or platform IME was exercised.
  await inputEditor.evaluate(editor => {
    const data = new DataTransfer();
    data.setData('text/plain','日本\n語');
    editor.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:data}));
  });
  assert.equal((await getInput()).text,'日本 語');
  assert.deepEqual([(await getInput()).anchor,(await getInput()).head],[4,4]);
  await page.keyboard.press('Home');
  assert.equal((await getInput()).head,0);
  await page.keyboard.press('End');
  assert.equal((await getInput()).head,4);
  await page.keyboard.press('Backspace');
  assert.equal((await getInput()).text,'日本 ');
  await page.keyboard.press('Control+z');
  assert.equal((await getInput()).text,'日本 語');
  await writeFile(join(evidence,'input-moonbit-edited.png'),
    await captureCanvas(moon.locator('canvas'),'input_moonbit',300,300));
  // Chromium event objects exercise sequencing, NOT a live Japanese IME.
  await inputEditor.evaluate(editor => {
    editor.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:''}));
    editor.dispatchEvent(new CompositionEvent('compositionupdate',{bubbles:true,data:'にほん'}));
  });
  let composing=await getInput();
  assert.equal(composing.composing,true);
  assert.equal(composing.markedStart,4);
  assert.equal(composing.markedEnd,7);
  await inputEditor.evaluate(editor =>
    editor.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'日本'})));
  assert.equal((await getInput()).text,'日本 語日本');
  assert.equal((await getInput()).composing,false);
  await page.keyboard.press('Control+z');
  assert.equal((await getInput()).text,'日本 語');
  await inputEditor.evaluate(editor => {
    editor.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:''}));
    editor.dispatchEvent(new CompositionEvent('compositionupdate',{bubbles:true,data:'かな'}));
    editor.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,key:'Escape',cancelable:true}));
    editor.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'かな'}));
  });
  assert.equal((await getInput()).text,'日本 語');
  assert.equal((await getInput()).composing,false);
  await writeFile(join(evidence,'input-moonbit-final.png'),
    await captureCanvas(moon.locator('canvas'),'input_moonbit_final',300,300));
  const inputEventTrace = await moon.locator('html').evaluate(() => globalThis.gpuiExample.inputEvents);
  await writeFile(join(evidence,'input-browser-events.json'),JSON.stringify(inputEventTrace,null,2));
  assert(inputEventTrace.some(event=>event.type==='compositionupdate'));
  assert(inputEventTrace.some(event=>event.type==='compositionend' && !event.committed));
  report.operations.push({action:'Chromium MoonBit text field',result:'trusted typing, UTF-16 caret/selection, copy/cut, undo/redo, paste adapter, composition preview/commit/cancel',imei:'synthetic composition events only: live Japanese IME unverified'});
  if(paired) {
    const rustInput = page.frameLocator('#rust-frame').locator('canvas');
    const before=await captureCanvas(rustInput,'input_rust_initial',300,300);
    await rustInput.click({position:{x:35,y:53}});
    await page.keyboard.type('abc');
    const after=await captureCanvas(rustInput,'input_rust_edited',300,300);
    await writeFile(join(evidence,'input-rust-initial.png'),before);
    await writeFile(join(evidence,'input-rust-edited.png'),after);
    report.operations.push({action:'Chromium Rust WASM input',result:before.equals(after)?'no visible difference observed':'pixels changed after trusted keyboard typing',checked:'actual pinned upstream rendered canvas; semantic selection/IME parity unverified'});
  }
  report.unverified=report.unverified.filter(v=>v!=='IME and interactive examples');
  report.unverified.push('real Japanese IME and native composition', 'Unicode grapheme movement parity', 'Rust-MoonBit semantic input equivalence and exact pixels');
  report.verified.push('real Chromium trusted typing/copy/cut with MoonBit UTF-16 selection and undo/redo',
    'synthetic Chromium composition preview/commit/cancel transport with MoonBit TextComposition');
  await page.selectOption('#fixture', 'hello_world');
  await waitForNewDocuments();
  const previous = await page.locator('#moon-frame').getAttribute('src');
  await page.locator('#settings button').click();
  assert.notEqual(await page.locator('#moon-frame').getAttribute('src'), previous);
  await waitForNewDocuments();
  report.operations.push({action:'reload both', result:'runtimes_initialized'});
  await page.setViewportSize({width:390,height:850});
  for (const id of ['rust-frame','moon-frame']) {
    if (id === 'rust-frame' && !paired) continue;
    const bounds = await page.locator('#' + id).boundingBox();
    assert.equal(bounds.width,500); assert.equal(bounds.height,500);
  }
  await page.screenshot({path:join(evidence,'mobile.png'),fullPage:true});
  report.verified.push('missing-port clearing', 'reload both', 'fixed viewport in narrow layout');
  assert.deepEqual(errors, []);
  report.overall = 'passed';
  console.log(paired ? 'PASS: actual Rust WASM and MoonBit JS rendered on one origin; screenshots, browser events and color probes retained. Pixel parity UNVERIFIED.' : 'PASS: compiled MoonBit; Rust comparison NOT RUN.');
} catch (error) {
  report.failure = error.stack;
  if (page) await page.screenshot({path:join(evidence,'failure.png'),fullPage:true}).catch(() => {});
  throw error;
} finally {
  await writeFile(join(evidence, 'result.json'), JSON.stringify(report, null, 2) + '\n');
  if (browser) await browser.close();
  await new Promise(done => server.close(done));
}
