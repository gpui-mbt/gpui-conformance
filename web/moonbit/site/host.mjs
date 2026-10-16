import { createHostTiming } from '../load-timing.mjs';
import { drawFrame } from './render.mjs';
import { measureWrapperInputs } from './text-metrics.mjs';
const loadTiming = createHostTiming('moon');
const canvas = document.getElementById('canvas');
const error = document.getElementById('error');
try {
  const example = new URL(location.href).searchParams.get('example') || 'hello_world';
  const modules = {hello_world:'./runtime.mjs', text_layout:'./text_layout.mjs', text_wrapper:'./text_wrapper.mjs', text:'./text.mjs'};
  if (!modules[example]) throw new Error('gpui.mbt not implemented: ' + example);
  const runtime = await import(modules[example]);
  const metadata = JSON.parse(runtime[example + '_metadata']());
  const interactiveText = example === 'text';
  const fonts = ['Zed Mono', 'system-ui', 'Menlo', 'Monaco', 'Courier New'];
  let fontIndex = 0, scrollY = 0, lastFrame = null;
  canvas.style.width = metadata.width + 'px';
  canvas.style.height = metadata.height + 'px';
  const labels = {
    hello_world:'Hello, World! Six colored squares',
    text_layout:'Upstream text_layout: aligned and decorated text with styled ABCD spans',
    text_wrapper:'Upstream text_wrapper: mixed-language wrapping, ellipsis, line clamps and nowrap',
    text:'Upstream typography example: font switching, character grid and scalable text specimens'
  };
  canvas.setAttribute('aria-label', labels[metadata.id]);
  document.title = example + ' · gpui.mbt';
  const family = interactiveText ? 'Zed Mono' : metadata.font_family;
  const fontUrl = interactiveText ? './Lilex-Regular.ttf' : './IBMPlexSans-Regular.ttf';
  document.fonts.add(await new FontFace(family, 'url(' + fontUrl + ')').load());
  if (example === 'text_layout') {
    for (const [file, descriptors] of [['Italic', {style:'italic'}], ['SemiBold', {weight:'800'}]]) {
      // This pinned upstream registry maps EXTRA_BOLD to the bundled SemiBold face.
      document.fonts.add(await new FontFace(metadata.font_family, 'url(./IBMPlexSans-' + file + '.ttf)', descriptors).load());
    }
  }
  await document.fonts.ready;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Canvas 2D is unavailable');
  function render() {
    const scale = Math.min(devicePixelRatio || 1, 4);
    canvas.width = Math.round(metadata.width * scale);
    canvas.height = Math.round(metadata.height * scale);
    if (interactiveText) metadata.font_family = fonts[fontIndex];
    context.font = metadata.font_size + 'px "' + metadata.font_family + '"';
    const widths = example === 'text_wrapper'
      ? measureWrapperInputs(context, metadata)
      : metadata.runs ? metadata.runs.map(run => {
        context.font = (run.style || 'normal') + ' ' + (run.weight || 400) + ' ' + (run.font_size || metadata.font_size) + 'px "' + metadata.font_family + '"';
        return context.measureText(run.text).width;
      }) : context.measureText(metadata.text).width;
    const json = example === 'text_wrapper'
      ? runtime.text_wrapper_frame(widths.graphemes, widths.advances, widths.prefixes, widths.ellipsisWidths, scale)
      : interactiveText ? runtime.text_frame(widths, scrollY, fontIndex, scale)
      : runtime[example + '_frame'](widths, scale);
    const frame = JSON.parse(json);
    drawFrame(context, frame, metadata, scale);
    lastFrame = frame;
    globalThis.gpuiExample = { metadata, frame, textWidth: widths, scale };
    document.documentElement.dataset.runtimeStatus = 'ready';
  }
  render();
  if (interactiveText) {
    canvas.setAttribute('role', 'application');
    canvas.tabIndex = 0;
    const advanceFont = () => {
      fontIndex = (fontIndex + 1) % fonts.length;
      render();
    };
    canvas.addEventListener('click', event => {
      const box = lastFrame.font_button;
      const rect = canvas.getBoundingClientRect();
      const x = (event.clientX - rect.left) * metadata.width / rect.width;
      const y = (event.clientY - rect.top) * metadata.height / rect.height;
      if (x >= box.x && x < box.x + box.width && y >= box.y && y < box.y + box.height) advanceFont();
    });
    canvas.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        advanceFont();
      } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        scrollY = Math.max(0, Math.min(lastFrame.scroll.max, scrollY + (event.key === 'ArrowDown' ? 62 : -62)));
        render();
      }
    });
    canvas.addEventListener('wheel', event => {
      event.preventDefault();
      scrollY = Math.max(0, Math.min(lastFrame.scroll.max, scrollY + event.deltaY));
      render();
    }, {passive:false});
  }
  const payloads = [modules[example], fontUrl];
  if (example === 'text_layout') payloads.push('./IBMPlexSans-Italic.ttf', './IBMPlexSans-SemiBold.ttf');
  loadTiming.complete(payloads, 'Canvas2D draw calls returned');
  window.addEventListener('resize', render);
} catch (cause) {
  loadTiming.fail();
  canvas.hidden = true; error.hidden = false;
  document.documentElement.dataset.runtimeStatus = 'failed';
  error.textContent = 'gpui.mbt example failed: ' + cause.message + '. Build web assets with web/scripts/build_moonbit.py before serving the page.';
}
