import { drawFrame } from './render.mjs';
const canvas = document.getElementById('canvas');
const error = document.getElementById('error');
try {
  const example = new URL(location.href).searchParams.get('example') || 'hello_world';
  if (example !== 'hello_world') throw new Error(`MoonBit port not implemented: ${example}`);
  const runtime = await import('./runtime.mjs');
  const metadata = JSON.parse(runtime.hello_world_metadata());
  const font = new FontFace(metadata.font_family, 'url(./IBMPlexSans-Regular.ttf)');
  document.fonts.add(await font.load());
  await document.fonts.ready;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Canvas 2D is unavailable');
  function render() {
    const scale = Math.min(devicePixelRatio || 1, 4);
    canvas.width = Math.round(metadata.width * scale); canvas.height = Math.round(metadata.height * scale);
    context.font = `${metadata.font_size}px "${metadata.font_family}"`;
    const width = context.measureText(metadata.text).width;
    const frame = JSON.parse(runtime.hello_world_frame(width, scale));
    drawFrame(context, frame, metadata, scale);
    // Expose actual candidate output for inspection, never fabricated oracle results.
    globalThis.gpuiExample = { metadata, frame, textWidth: width, scale };
    document.documentElement.dataset.runtimeStatus = 'ready';
  }
  render();
  window.addEventListener('resize', render);
} catch (cause) {
  canvas.hidden = true; error.hidden = false;
  document.documentElement.dataset.runtimeStatus = 'failed';
  error.textContent = `gpui.mbt example failed: ${cause.message}. Build web assets with web/scripts/build_moonbit.py before serving the page.`;
}
