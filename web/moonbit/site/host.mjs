import { createHostTiming } from '../load-timing.mjs';
const loadTiming = createHostTiming('moon');
import { drawFrame } from './render.mjs';
import { measureWrapperInputs } from './text-metrics.mjs';
import { createInputHost } from './input-host.mjs';
const canvas = document.getElementById('canvas');
const error = document.getElementById('error');
try {
  const example = new URL(location.href).searchParams.get('example') || 'hello_world';
  const modules = {hello_world: './runtime.mjs', text_layout: './text_layout.mjs', text_wrapper: './text_wrapper.mjs', hello_web: './hello_web.mjs', input: './input.mjs'};
  if (!modules[example]) throw new Error(`gpui.mbt not implemented: ${example}`);
  const runtime = await import(modules[example]);
  const metadata = JSON.parse(runtime[example + '_metadata']());
  canvas.style.width = `${metadata.width}px`; canvas.style.height = `${metadata.height}px`;
  const labels = {hello_world:'Hello, World! Six colored squares', text_layout:'Upstream text_layout: aligned and decorated text with styled ABCD spans', text_wrapper:'Upstream text_wrapper: mixed-language wrapping, ellipsis, line clamps and nowrap', hello_web:'Upstream Prime sieve: select 10 M, 50 M or 100 M and Count Primes', input:'Upstream TextInput: type, select, copy, paste and composition'};
  canvas.setAttribute('aria-label', labels[metadata.id]);
  document.title = `${example} · gpui.mbt`;
  const font = new FontFace(metadata.font_family, 'url(./IBMPlexSans-Regular.ttf)');
  document.fonts.add(await font.load());
  if (example === 'text_layout') {
    for (const [file, descriptors] of [['Italic', {style:'italic'}], ['SemiBold', {weight:'800'}]]) {
      // The upstream font registry resolves EXTRA_BOLD to the bundled SemiBold face.
      document.fonts.add(await new FontFace(metadata.font_family, `url(./IBMPlexSans-${file}.ttf)`, descriptors).load());
    }
  }
  await document.fonts.ready;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Canvas 2D is unavailable');
  let prime;
  let input;
  if (example === 'hello_web') {
    const { createPrimeHost } = await import('./prime-host.mjs');
    prime = createPrimeHost({ runtime, canvas, render: () => render(), onFailure: cause => console.error(cause) });
  }
  function render() {
    const scale = Math.min(devicePixelRatio || 1, 4);
    canvas.width = Math.round(metadata.width * scale); canvas.height = Math.round(metadata.height * scale);
    context.font = `${metadata.font_size}px "${metadata.font_family}"`;
    const content = example === 'hello_web' ? JSON.parse(runtime.hello_web_content()) : null;
    const width = example === 'input' ? null : content ? content.runs.map(run => {
      context.font = `${run.font_size}px "${metadata.font_family}"`;
      return context.measureText(run.text).width;
    }) : example === 'text_wrapper' ? measureWrapperInputs(context, metadata) : metadata.runs ? metadata.runs.map(run => {
      context.font = `${run.style} ${run.weight} ${metadata.font_size}px "${metadata.font_family}"`;
      return context.measureText(run.text).width;
    }) : context.measureText(metadata.text).width;
    const frame = JSON.parse(example === 'input' ? runtime.input_frame(scale)
      : example === 'text_wrapper'
      ? runtime.text_wrapper_frame(width.graphemes, width.advances, width.prefixes, width.ellipsisWidths, scale)
      : runtime[example + '_frame'](width, scale));
    drawFrame(context, frame, metadata, scale);
    // Expose actual candidate output for inspection, never fabricated oracle results.
    globalThis.gpuiExample = { metadata, frame, textWidth: width, scale, ...(content ? { content, workers: prime.diagnostics } : {}), ...(input ? { input: input.readState(), inputEvents: input.events } : {}) };
    document.documentElement.dataset.runtimeStatus = 'ready';
  }
  if (example === 'input') {
    input = createInputHost({runtime, canvas, render});
  }
  render();
  const payloads = [modules[example], './IBMPlexSans-Regular.ttf'];
  if (example === 'text_layout') payloads.push('./IBMPlexSans-Italic.ttf', './IBMPlexSans-SemiBold.ttf');
  loadTiming.complete(payloads, 'Canvas2D draw calls returned');
  window.addEventListener('resize', render);
} catch (cause) {
  loadTiming.fail();
  canvas.hidden = true; error.hidden = false;
  document.documentElement.dataset.runtimeStatus = 'failed';
  error.textContent = `gpui.mbt example failed: ${cause.message}. Build web assets with web/scripts/build_moonbit.py before serving the page.`;
}
