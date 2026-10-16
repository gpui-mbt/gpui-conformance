import { createHostTiming } from '../load-timing.mjs';
const loadTiming = createHostTiming('moon');
import { drawFrame } from './render.mjs';
import { measureWrapperInputs, measureTypographyInputs } from './text-metrics.mjs';
import { wheelDeltaPixels } from './text-wheel.mjs';
import { createInputHost } from './input-host.mjs';
const canvas = document.getElementById('canvas');
const error = document.getElementById('error');
try {
  const example = new URL(location.href).searchParams.get('example') || 'hello_world';
  const modules = {tree: './tree.mjs', hello_world: './runtime.mjs', text_layout: './text_layout.mjs', text_wrapper: './text_wrapper.mjs', hello_web: './hello_web.mjs', text: './text.mjs', input: './input.mjs', dynamic_fonts: './dynamic_fonts.mjs'};
  if (!modules[example]) throw new Error(`gpui.mbt not implemented: ${example}`);
  const runtime = await import(modules[example]);
  const metadata = JSON.parse(runtime[example + '_metadata']());
  const isText = example === 'text';
  const isTree = example === 'tree';
  const families = ['Zed Mono', 'system-ui', 'Menlo', 'Monaco', 'Courier New'];
  let fontIndex=0, scrollY=0, lastFrame=null;
  canvas.style.width = `${metadata.width}px`; canvas.style.height = `${metadata.height}px`;
  const labels = {tree: 'Upstream tree: 51 nested red, blue, green and yellow blocks', hello_world:'Hello, World! Six colored squares', text_layout:'Upstream text_layout: aligned and decorated text with styled ABCD spans', text_wrapper:'Upstream text_wrapper: mixed-language wrapping, ellipsis, line clamps and nowrap', hello_web:'Upstream Prime sieve: select 10 M, 50 M or 100 M and Count Primes', text:'Upstream typography: font switching, character grid and type scale', input:'Upstream input: editing, selection, Clipboard and IME', dynamic_fonts:'Upstream dynamic fonts: Devanagari font is downloaded once on demand'};
  canvas.setAttribute('aria-label', labels[metadata.id]);
  document.title = `${example} · gpui.mbt`;
  if (!isTree) {
    const font = new FontFace(isText ? 'Zed Mono' : metadata.font_family, isText ? 'url(./Lilex-Regular.ttf)' : 'url(./IBMPlexSans-Regular.ttf)');
    document.fonts.add(await font.load());
    if (example === 'text_layout') {
      for (const [file, descriptors] of [['Italic', {style:'italic'}], ['SemiBold', {weight:'800'}]]) {
        // The upstream font registry resolves EXTRA_BOLD to the bundled SemiBold face.
        document.fonts.add(await new FontFace(metadata.font_family, `url(./IBMPlexSans-${file}.ttf)`, descriptors).load());
      }
    }
    await document.fonts.ready;
  }
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Canvas 2D is unavailable');
  let prime;
  let input;
  let dynamicFonts;
  if (example === 'dynamic_fonts') {
    const {createDynamicFontHost} = await import('./dynamic-font-host.mjs');
    dynamicFonts = createDynamicFontHost({fetchFont: (...args) => fetch(...args), FontFaceType: FontFace, fonts: document.fonts, onChange: () => render()});
  }
  if (example === 'hello_web') {
    const { createPrimeHost } = await import('./prime-host.mjs');
    prime = createPrimeHost({ runtime, canvas, render: () => render(), onFailure: cause => console.error(cause) });
  }
  function render() {
    const scale = Math.min(devicePixelRatio || 1, 4);
    canvas.width = Math.round(metadata.width * scale); canvas.height = Math.round(metadata.height * scale);
    if (isText) metadata.font_family = families[fontIndex];
    if (!isTree) context.font = `${metadata.font_size}px "${metadata.font_family}"`;
    const content = example === 'hello_web' ? JSON.parse(runtime.hello_web_content()) : null;
    if (dynamicFonts) metadata.runs[4].text = dynamicFonts.state.message;
    const width = isTree || example === 'input' ? null : content ? content.runs.map(run => {
      context.font = `${run.font_size}px "${metadata.font_family}"`;
      return context.measureText(run.text).width;
    }) : isText ? measureTypographyInputs(context, metadata) : example === 'text_wrapper' ? measureWrapperInputs(context, metadata) : metadata.runs ? metadata.runs.map(run => {
      context.font = `${run.style || 'normal'} ${run.weight || 400} ${run.font_size || metadata.font_size}px "${metadata.font_family}"${metadata.font_fallback ? `, "${metadata.font_fallback}"` : ''}`;
      return context.measureText(run.text).width;
    }) : context.measureText(metadata.text).width;
    let statusPrefixes;
    if (dynamicFonts) {
      const status = dynamicFonts.state.message;
      context.save();
      try {
        context.font = `normal 400 16px "${metadata.font_family}"${metadata.font_fallback ? `, "${metadata.font_fallback}"` : ''}`;
        let prefix = '';
        statusPrefixes = [0];
        for (const character of status) {
          prefix += character;
          statusPrefixes.push(context.measureText(prefix).width);
        }
      } finally { context.restore(); }
    }
    const frame = JSON.parse(isTree ? runtime.tree_frame(scale) : example === 'input' ? runtime.input_frame(scale)
      : example === 'text_wrapper'
      ? runtime.text_wrapper_frame(width.graphemes, width.advances, width.prefixes, width.ellipsisWidths, scale)
      : isText ? runtime.text_frame(width.widths, width.prefixes, scrollY, fontIndex, scale)
      : dynamicFonts ? runtime.dynamic_fonts_frame(width, dynamicFonts.state.message, statusPrefixes, scale)
      : runtime[example + '_frame'](width, scale));
    drawFrame(context, frame, metadata, scale);
    if (isText) { lastFrame=frame; scrollY=frame.scroll.y; }
    // Expose actual candidate output for inspection, never fabricated oracle results.
    globalThis.gpuiExample = { metadata, frame, textWidth: width, scale, ...(content ? { content, workers: prime.diagnostics } : {}), ...(input ? { input: input.readState(), inputEvents: input.events } : {}), ...(dynamicFonts ? {dynamic_fonts: dynamicFonts.state} : {}) };
    document.documentElement.dataset.runtimeStatus = 'ready';
  }
  render();
  if (example === 'input') { input = createInputHost({runtime,canvas,render}); render(); }
  if (dynamicFonts) void dynamicFonts.start(metadata.runs[2].text);
  if (isText) {
    canvas.tabIndex=0;
    canvas.setAttribute('role','application');
    const cycle = () => { fontIndex=(fontIndex+1)%families.length; render(); };
    canvas.addEventListener('click', event => {
      const bounds=canvas.getBoundingClientRect();
      const x=(event.clientX-bounds.left)*metadata.width/bounds.width;
      const y=(event.clientY-bounds.top)*metadata.height/bounds.height;
      const b=lastFrame.font_button;
      if(x>=b.x && x<b.x+b.width && y>=b.y && y<b.y+b.height) cycle();
    });
    canvas.addEventListener('wheel', event => {
      event.preventDefault();
      scrollY=Math.max(0,Math.min(lastFrame.scroll.max,scrollY+wheelDeltaPixels(event.deltaY,event.deltaMode,lastFrame.scroll.height)));
      render();
    },{passive:false});
    canvas.addEventListener('keydown',event=>{
      if(event.key==='Enter'||event.key===' ') { event.preventDefault(); cycle(); }
      else if(event.key==='ArrowDown'||event.key==='ArrowUp') {
        event.preventDefault();
        scrollY=Math.max(0,Math.min(lastFrame.scroll.max,scrollY+(event.key==='ArrowDown'?62:-62)));
        render();
      }
    });
  }
  const payloads = isTree ? [modules[example]] : [modules[example], isText ? './Lilex-Regular.ttf' : './IBMPlexSans-Regular.ttf'];
  if (example === 'text_layout') payloads.push('./IBMPlexSans-Italic.ttf', './IBMPlexSans-SemiBold.ttf');
  loadTiming.complete(payloads, 'Canvas2D draw calls returned');
  window.addEventListener('resize', render);
} catch (cause) {
  loadTiming.fail();
  canvas.hidden = true; error.hidden = false;
  document.documentElement.dataset.runtimeStatus = 'failed';
  error.textContent = `gpui.mbt example failed: ${cause.message}. Build web assets with web/scripts/build_moonbit.py before serving the page.`;
}
