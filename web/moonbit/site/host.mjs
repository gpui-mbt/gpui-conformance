import { createHostTiming } from '../load-timing.mjs';
const loadTiming = createHostTiming('moon');
import { drawFrame, drawCoreRasterFrame, validateCoreRasterFrame } from './render.mjs';
import { measureWrapperInputs, measureTypographyInputs } from './text-metrics.mjs';
import { wheelDeltaPixels } from './text-wheel.mjs';
import { createInputHost } from './input-host.mjs';
import { createScrollableHost } from './scrollable-host.mjs';
import { createFocusVisibleHost } from './focus-visible-host.mjs';
import { createTabStopHost } from './tab-stop-host.mjs';
import { createDragDropHost } from './drag-drop-host.mjs';
import { createPopoverHost, readPopoverFrame } from './popover-host.mjs';
import { loadPopoverFont } from './popover-text.mjs';
import { createUniformListHost } from './uniform-list-host.mjs';
import { measureUniformListInputs } from './uniform-list-text.mjs';
import { readGridFrame, watchGridDeviceScale } from './grid-layout-host.mjs';
import { readAnchorFrame, createAnchorHost } from './anchor-host.mjs';
import {readGradientFrame,createGradientHost} from './gradient-host.mjs';
import {readPatternFrame,createPatternLifecycle} from './pattern-host.mjs';
const canvas = document.getElementById('canvas');
const error = document.getElementById('error');
try {
  const example = new URL(location.href).searchParams.get('example') || 'hello_world';
  const modules = {pattern:'./pattern.mjs',popover:'./popover.mjs',gradient:'./gradient.mjs',anchor: './anchor.mjs', grid_layout: './grid_layout.mjs', uniform_list: './uniform_list.mjs', drag_drop: './drag_drop.mjs', tab_stop: './tab_stop.mjs', focus_visible: './focus_visible.mjs', scrollable: './scrollable.mjs', tree: './tree.mjs', hello_world: './runtime.mjs', text_layout: './text_layout.mjs', text_wrapper: './text_wrapper.mjs', hello_web: './hello_web.mjs', text: './text.mjs', input: './input.mjs', dynamic_fonts: './dynamic_fonts.mjs'};
  if (!modules[example]) throw new Error(`gpui.mbt not implemented: ${example}`);
  const runtime = await import(modules[example]);
  const metadata = JSON.parse(runtime[example + '_metadata']());
  const isPattern = example === 'pattern';
  const isPopover = example === 'popover';
  const isText = example === 'text';
  const isTree = example === 'tree';
  const isFocusVisible = example === 'focus_visible';
  const isTabStop = example === 'tab_stop';
  const isGrid = example === 'grid_layout';
  let gridNotice;
  if (isGrid) {
    gridNotice = document.createElement('p');
    gridNotice.id = 'grid-live-notice';
    gridNotice.setAttribute('role', 'status');
    gridNotice.hidden = true;
    Object.assign(gridNotice.style, {position:'fixed',bottom:'0',right:'0',maxWidth:'30rem',margin:'0',padding:'.4rem .6rem',background:'#fff4d6',color:'#49340b',font:'12px system-ui',pointerEvents:'none'});
    document.body.append(gridNotice);
  }
  const isGradient = example === 'gradient';
  const gradientPolicy = isGradient && new URL(location.href).searchParams.get('policy') === '1';
  let patternNotice;
  if(isPattern){patternNotice=document.createElement('p');patternNotice.id='pattern-live-notice';patternNotice.setAttribute('role','status');patternNotice.hidden=true;Object.assign(patternNotice.style,{position:'fixed',bottom:'0',right:'0',margin:'0',background:'#fff4d6',font:'12px system-ui',pointerEvents:'none'});document.body.append(patternNotice);}
  let gradientNotice;
  if(isGradient&&!gradientPolicy){gradientNotice=document.createElement('p');gradientNotice.id='gradient-live-notice';gradientNotice.setAttribute('role','status');gradientNotice.hidden=true;Object.assign(gradientNotice.style,{position:'fixed',bottom:'0',right:'0',margin:'0',background:'#fff4d6',font:'12px system-ui',pointerEvents:'none'});gradientNotice.textContent='Live gradient preview outside the frozen wide/tall DPR1 profile. This viewport is unverified.';document.body.append(gradientNotice);}
  const isAnchor = example === 'anchor';
  let anchorNotice;
  if (isAnchor) {
    anchorNotice = document.createElement('p');
    anchorNotice.id = 'anchor-live-notice';
    anchorNotice.setAttribute('role', 'status');
    anchorNotice.hidden = true;
    Object.assign(anchorNotice.style, {position:'fixed',bottom:'0',right:'0',maxWidth:'30rem',margin:'0',padding:'.4rem .6rem',background:'#fff4d6',color:'#49340b',font:'12px system-ui',pointerEvents:'none'});
    anchorNotice.textContent = 'Live anchor preview is outside the frozen 750/480 × 600, DPR 1 reference profile. This viewport remains unverified.';
    document.body.append(anchorNotice);
  }
  const families = ['Zed Mono', 'system-ui', 'Menlo', 'Monaco', 'Courier New'];
  let fontIndex=0, scrollY=0, lastFrame=null;
  canvas.style.width = `${metadata.width}px`; canvas.style.height = `${metadata.height}px`;
  const labels = {popover:'Upstream popover: default, parent and nested child deferred layers',uniform_list: 'Upstream uniform list: 50 virtualized Item rows', drag_drop: 'Upstream drag and drop: three colored items and a typed drop target', tab_stop: 'Upstream tab stops: source indices, non-stops, group prefixes and global traversal', focus_visible: 'Upstream focus-visible: keyboard and pointer focus, tab traversal and focus rings', scrollable: 'Upstream nested scrollable: horizontal and vertical viewports with clipped hover', tree: 'Upstream tree: 51 nested red, blue, green and yellow blocks', hello_world:'Hello, World! Six colored squares', text_layout:'Upstream text_layout: aligned and decorated text with styled ABCD spans', text_wrapper:'Upstream text_wrapper: mixed-language wrapping, ellipsis, line clamps and nowrap', hello_web:'Upstream Prime sieve: select 10 M, 50 M or 100 M and Count Primes', text:'Upstream typography: font switching, character grid and type scale', input:'Upstream input: editing, selection, Clipboard and IME', dynamic_fonts:'Upstream dynamic fonts: Devanagari font is downloaded once on demand'};
  labels.pattern = 'Upstream pattern: eight slash rectangles, two labels, solid and gradient controls';
  labels.gradient = 'Upstream gradient: twelve gradients, two solids, polygon and color-space toggle';
  labels.anchor = 'Upstream anchor: eight hover popovers and inert center';
  labels.grid_layout = 'Upstream responsive grid: header, table of contents, content, advertisement and footer';
  canvas.setAttribute('aria-label', labels[metadata.id]);
  document.title = `${example} · gpui.mbt`;
  if (isPopover) await loadPopoverFont({FontFaceType:FontFace,fonts:document.fonts});
  if (!isTree && !isPopover) {
    const font = new FontFace(isText ? 'Zed Mono' : metadata.font_family, isText ? 'url(./Lilex-Regular.ttf)' : 'url(./IBMPlexSans-Regular.ttf)');
    document.fonts.add(await font.load());
    if (example === 'text_layout') {
      for (const [file, descriptors] of [['Italic', {style:'italic'}], ['SemiBold', {weight:'800'}]]) {
        // The upstream font registry resolves EXTRA_BOLD to the bundled SemiBold face.
        document.fonts.add(await new FontFace(metadata.font_family, `url(./IBMPlexSans-${file}.ttf)`, descriptors).load());
      }
    }
    if (isFocusVisible) {
      // Upstream requests BOLD700; its bundled closest face is SemiBold.
      document.fonts.add(await new FontFace(metadata.font_family,
        'url(./IBMPlexSans-SemiBold.ttf)', {weight:'700'}).load());
    }
    await document.fonts.ready;
  }
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Canvas 2D is unavailable');
  let prime;
  let input;
  let dynamicFonts;
  let scrollable;
  let focusVisible;
  let tabStop;
  let dragDrop;
  let uniformList;
  let anchor;
  let gradient;
  let patternLifecycle;
  let popover;
  let popoverSuspended = false;
  if (example === 'dynamic_fonts') {
    const {createDynamicFontHost} = await import('./dynamic-font-host.mjs');
    dynamicFonts = createDynamicFontHost({fetchFont: (...args) => fetch(...args), FontFaceType: FontFace, fonts: document.fonts, onChange: () => render()});
  }
  if (example === 'hello_web') {
    const { createPrimeHost } = await import('./prime-host.mjs');
    prime = createPrimeHost({ runtime, canvas, render: () => render(), onFailure: cause => console.error(cause) });
  }
  function render() {
    if(isPattern) {
      if(patternLifecycle?.suspended)return;
      try {
        const {frame,width,height,scale,widths,glyphInk,rasterWidth,rasterHeight,backingWidth,backingHeight,actualDeviceScale,effectiveRenderScale,renderScaleReduced}=readPatternFrame(runtime,context,window,metadata);
        const rasterMetadata={...metadata,width:rasterWidth,height:rasterHeight};
        validateCoreRasterFrame(frame,rasterMetadata,scale);
        metadata.width=width;metadata.height=height;
        canvas.style.width=`${width}px`;canvas.style.height=`${height}px`;
        if(canvas.width!==backingWidth)canvas.width=backingWidth;
        if(canvas.height!==backingHeight)canvas.height=backingHeight;
        drawCoreRasterFrame(context,frame,rasterMetadata,scale);
        globalThis.gpuiExample={metadata,frame,textWidth:widths,scale,glyphInk,actualDeviceScale,effectiveRenderScale,renderScaleReduced,rasterWidth,rasterHeight};
        patternNotice.hidden=frame.pattern.comparison_profile_match;
        patternNotice.textContent=`Live pattern preview outside 600×600 DPR1; this viewport is unverified.${renderScaleReduced ? " Backing resolution reduced to fit the raster budget." : ""}`;
        canvas.title=`Live rendering; numerical comparison is qualified only at 600×600 DPR1. Text, shadows and full-image parity remain unverified.${renderScaleReduced ? " Backing resolution reduced to stay within the raster budget." : ""}`;
        canvas.hidden=false;error.hidden=true;document.documentElement.dataset.runtimeStatus='ready';
      } catch(cause) {
        delete globalThis.gpuiExample;canvas.hidden=true;error.hidden=false;document.documentElement.dataset.runtimeStatus='failed';
        patternNotice.hidden=true;
        error.textContent=`Pattern candidate failed: ${cause.message}. Live viewport is resource-bounded; numerical comparison remains limited to 600×600 DPR1. Text, shadows and full-image parity remain unverified.`;
      }
      return;
    }
    if (isPopover) {
      if (popoverSuspended) return false;
      try {
        const {frame,width,height,scale,prefixes,backingWidth,backingHeight}=readPopoverFrame(runtime,context,window,metadata);
        metadata.width=width;metadata.height=height;
        canvas.style.width=`${width}px`;canvas.style.height=`${height}px`;
        if(canvas.width!==backingWidth)canvas.width=backingWidth;
        if(canvas.height!==backingHeight)canvas.height=backingHeight;
        context.textRendering='auto';
        drawFrame(context,frame,metadata,scale);
        globalThis.gpuiExample={metadata,frame,textWidth:prefixes,scale,popoverEvents:popover?.events||[]};
        canvas.hidden=false;error.hidden=true;document.documentElement.dataset.runtimeStatus='ready';
        return true;
      } catch(cause) {
        runtime.popover_reset();delete globalThis.gpuiExample;
        canvas.hidden=true;error.hidden=false;document.documentElement.dataset.runtimeStatus='failed';
        error.textContent=`Popover candidate failed: ${cause.message}. Live viewport is resource-bounded; browser and pixel parity remain unverified.`;
        return false;
      }
    }
    if(isGradient) {
      try {
        const {frame,width,height,scale,widths,actualDeviceScale,effectiveRenderScale,backingWidth,backingHeight,renderScaleReduced}=readGradientFrame(runtime,context,window,metadata,gradientPolicy);
        const nextMetadata={...metadata,width,height};
        validateCoreRasterFrame(frame,nextMetadata,scale); // before backing reset
        metadata.width=width;metadata.height=height;
        canvas.style.width=`${width}px`;canvas.style.height=`${height}px`;
        if(canvas.width!==backingWidth)canvas.width=backingWidth;
        if(canvas.height!==backingHeight)canvas.height=backingHeight;
        drawCoreRasterFrame(context,frame,metadata,scale);
        if(gradientNotice){gradientNotice.hidden=frame.gradient.comparison_profile_match;gradientNotice.textContent=renderScaleReduced?`Live preview at effective render scale ${effectiveRenderScale.toFixed(3)} (device DPR ${actualDeviceScale}); resolution reduced to fit bounded resources. This viewport is unverified.`:'Live gradient preview outside the frozen wide/tall DPR1 profile. This viewport is unverified.';}
        globalThis.gpuiExample={metadata,frame,textWidth:widths,scale,actualDeviceScale,effectiveRenderScale,backingWidth,backingHeight,renderScaleReduced,gradientEvents:gradient?.events||[]};
        canvas.hidden=false;error.hidden=true;document.documentElement.dataset.runtimeStatus='ready';
      } catch(cause) {
        delete globalThis.gpuiExample;canvas.hidden=true;error.hidden=false;document.documentElement.dataset.runtimeStatus='failed';runtime.gradient_reset();
        if(gradientNotice)gradientNotice.hidden=true;
        error.textContent=`Gradient candidate failed: ${cause.message}. Supported live size: width240–2048px, height300–2048px, device DPR0.25–64 (bounded effective scale), backing at most2048 per side and1048576 pixels.`;
      }
      return;
    }
    if (isAnchor) {
      try {
        const {frame,width,height,scale,widths} = readAnchorFrame(runtime,context,window,metadata);
        metadata.width = width; metadata.height = height;
        canvas.style.width = `${width}px`; canvas.style.height = `${height}px`;
        canvas.width = Math.round(width * scale); canvas.height = Math.round(height * scale);
        drawFrame(context,frame,metadata,scale);
        anchorNotice.hidden = frame.anchor.comparison_profile_match;
        globalThis.gpuiExample = {metadata,frame,textWidth:widths,scale,anchorEvents:anchor?.events || []};
        canvas.hidden = false; error.hidden = true;
        document.documentElement.dataset.runtimeStatus = 'ready';
      } catch (cause) {
        delete globalThis.gpuiExample;
        canvas.hidden = true; error.hidden = false;
        document.documentElement.dataset.runtimeStatus = 'failed';
        runtime.anchor_reset();
        anchorNotice.hidden = true;
        error.textContent = `Anchor candidate failed: ${cause.message}. Live viewport requires width 4–4096px and height 4–16384px, DPR 0.25–4, and a rounded Canvas of 1–16384px per side and at most 33554432 pixels.`;
      }
      return;
    }
    if (isGrid) {
      // Pass the actual browser viewport to MoonBit. Only its measured query
      // chooses the stack/grid branch and allocates all tracks and spans.
      const scale = devicePixelRatio;
      try {
        const {frame,content,prefixes,width,height} = readGridFrame(runtime,context,window,scale);
        metadata.width = width; metadata.height = height;
        canvas.style.width = `${width}px`; canvas.style.height = `${height}px`;
        canvas.width = Math.round(width * scale); canvas.height = Math.round(height * scale);
        drawFrame(context,frame,metadata,scale);
        globalThis.gpuiExample = {metadata,frame,content,textWidth:prefixes,scale};
        gridNotice.hidden = frame.grid_layout.comparison_profile_match;
        gridNotice.textContent = 'Live viewport outside the comparison profile. Rendering and text wrapping here are unverified.';
        canvas.hidden = false; error.hidden = true;
        document.documentElement.dataset.runtimeStatus = 'ready';
      } catch (cause) {
        // A rejected resize must not leave a stale successful frame visible.
        // The same document can recover on returning to a supported viewport.
        delete globalThis.gpuiExample;
        canvas.hidden = true; error.hidden = false;
        document.documentElement.dataset.runtimeStatus = 'failed';
        gridNotice.hidden = true;
        error.textContent = `Grid candidate failed: ${cause.message}. Live viewport requires width 16–16384px and height 32–16384px, DPR 0.25–4, and a rounded Canvas of 1–16384px per side and at most 33554432 pixels.`;
      }
      return;
    }
    const scale = Math.min(devicePixelRatio || 1, 4);
    canvas.width = Math.round(metadata.width * scale); canvas.height = Math.round(metadata.height * scale);
    if (isText) metadata.font_family = families[fontIndex];
    if (!isTree) context.font = `${metadata.font_size}px "${metadata.font_family}"`;
    const content = example === 'hello_web' ? JSON.parse(runtime.hello_web_content())
      : isFocusVisible || isTabStop ? JSON.parse(runtime[example + '_content']()) : null;
    if (dynamicFonts) metadata.runs[4].text = dynamicFonts.state.message;
    const width = isTree || example === 'input' ? null : example === 'uniform_list' ? measureUniformListInputs(context, metadata) : content ? content.runs.map(run => {
      context.font = `${run.font_weight || 400} ${run.font_size}px "${metadata.font_family}"`;
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
    const frame = JSON.parse(example === 'uniform_list' ? runtime.uniform_list_frame(width.widths, width.prefixes, width.advances, scale) : isTree ? runtime.tree_frame(scale) : example === 'input' ? runtime.input_frame(scale)
      : example === 'text_wrapper'
      ? runtime.text_wrapper_frame(width.graphemes, width.advances, width.prefixes, width.ellipsisWidths, scale)
      : isText ? runtime.text_frame(width.widths, width.prefixes, scrollY, fontIndex, scale)
      : dynamicFonts ? runtime.dynamic_fonts_frame(width, dynamicFonts.state.message, statusPrefixes, scale)
      : runtime[example + '_frame'](width, scale));
    if (example === 'uniform_list') context.textRendering = 'auto';
    drawFrame(context, frame, metadata, scale);
    if (example === 'uniform_list') {
      if (frame.cursor !== 'pointer') throw new Error('Invalid uniform-list cursor');
      canvas.style.cursor = frame.cursor;
    }
    if (example === 'drag_drop') {
      if (!['default', 'move'].includes(frame.cursor)) throw new Error('Invalid drag-drop model cursor');
      canvas.style.cursor = frame.cursor;
    }
    if (isText) { lastFrame=frame; scrollY=frame.scroll.y; }
    // Expose actual candidate output for inspection, never fabricated oracle results.
    globalThis.gpuiExample = { metadata, frame, textWidth: width, scale, ...(content ? { content, ...(prime ? {workers:prime.diagnostics} : {}) } : {}), ...(input ? { input: input.readState(), inputEvents: input.events } : {}), ...(dynamicFonts ? {dynamic_fonts: dynamicFonts.state} : {}), ...(scrollable ? {scrollableEvents:scrollable.events} : {}), ...(focusVisible ? {focusVisibleEvents:focusVisible.events} : {}), ...(tabStop ? {tabStopEvents:tabStop.events} : {}), ...(dragDrop ? {dragDropEvents:dragDrop.events} : {}), ...(uniformList ? {uniformListEvents:uniformList.events} : {}) };
    document.documentElement.dataset.runtimeStatus = 'ready';
  }
  render();
  if(isPopover) {
    popover=createPopoverHost({runtime,canvas,render});
    let stopScaleWatch=watchGridDeviceScale(window,render);
    window.addEventListener('pagehide',()=>{
      popoverSuspended=true;popover?.stop();popover=null;
      runtime.popover_reset();delete globalThis.gpuiExample;
      stopScaleWatch?.();stopScaleWatch=null;
    });
    window.addEventListener('pageshow',()=>{
      if(!popover){popoverSuspended=false;popover=createPopoverHost({runtime,canvas,render});
        stopScaleWatch=watchGridDeviceScale(window,render);render();}
    });
  }
  if(isGradient&&!gradientPolicy) {
    gradient=createGradientHost({runtime,canvas,render});
    let stopScaleWatch=watchGridDeviceScale(window,render);
    window.addEventListener('pagehide',()=>{gradient?.stop();gradient=null;stopScaleWatch?.();stopScaleWatch=null;});
    window.addEventListener('pageshow',()=>{if(!gradient){gradient=createGradientHost({runtime,canvas,render});stopScaleWatch=watchGridDeviceScale(window,render);render();}});
  }
  if (isAnchor) {
    anchor = createAnchorHost({runtime,canvas,render});
    let stopScaleWatch = watchGridDeviceScale(window, render);
    window.addEventListener('pagehide', () => {
      anchor?.stop(); anchor = null;
      stopScaleWatch?.(); stopScaleWatch = null;
    });
    window.addEventListener('pageshow', () => {
      if (!anchor) {
        anchor = createAnchorHost({runtime,canvas,render});
        stopScaleWatch = watchGridDeviceScale(window, render);
        render();
      }
    });
  }
  if (example === 'input') { input = createInputHost({runtime,canvas,render}); render(); }
  if (dynamicFonts) void dynamicFonts.start(metadata.runs[2].text);
  if (example === 'uniform_list') {
    uniformList = createUniformListHost({runtime,canvas,render});
    window.addEventListener('pagehide', () => uniformList.stop(), {once:true});
  }
  if (example === 'scrollable') {
    scrollable = createScrollableHost({runtime,canvas,render});
    window.addEventListener('pagehide', () => scrollable.stop(), {once:true});
  }
  if (isFocusVisible) {
    focusVisible = createFocusVisibleHost({runtime,canvas,render});
    window.addEventListener('pagehide', () => focusVisible.stop(), {once:true});
  }
  if (isTabStop) {
    tabStop = createTabStopHost({runtime,canvas,render});
    window.addEventListener('pagehide', () => tabStop.stop(), {once:true});
  }
  if (example === 'drag_drop') {
    dragDrop = createDragDropHost({runtime,canvas,render});
    window.addEventListener('pagehide', () => dragDrop.stop(), {once:true});
  }
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
  if (isFocusVisible) payloads.push('./IBMPlexSans-SemiBold.ttf');
  if (document.documentElement.dataset.runtimeStatus === 'ready') loadTiming.complete(payloads, 'Canvas2D draw calls returned');
  else loadTiming.fail();
  window.addEventListener('resize', render);
  if(isPattern)patternLifecycle=createPatternLifecycle(window,render,()=>{
    delete globalThis.gpuiExample;canvas.hidden=true;patternNotice.hidden=true;
    document.documentElement.dataset.runtimeStatus='suspended';
  });
  if (isGrid) {
    let stopScaleWatch = watchGridDeviceScale(window, render);
    window.addEventListener('pagehide', () => { stopScaleWatch?.(); stopScaleWatch = null; });
    // BFCache restores this document without rerunning module initialization.
    window.addEventListener('pageshow', () => {
      if (!stopScaleWatch) { stopScaleWatch = watchGridDeviceScale(window, render); render(); }
    });
  }
} catch (cause) {
  loadTiming.fail();
  canvas.hidden = true; error.hidden = false;
  document.documentElement.dataset.runtimeStatus = 'failed';
  error.textContent = `gpui.mbt example failed: ${cause.message}. Build web assets with web/scripts/build_moonbit.py before serving the page.`;
}

