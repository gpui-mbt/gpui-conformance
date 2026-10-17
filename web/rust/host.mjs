import { createHostTiming } from '../load-timing.mjs';
const loadTiming = createHostTiming('rust');
try {
  if (!crossOriginIsolated) throw new Error('Shared-memory WASM requires COOP/COEP response headers on the whole comparison site.');
  const example = new URL(location.href).searchParams.get('example') || 'hello_world';
  const modules = {gradient: './gradient.js', anchor: './anchor.js', grid_layout: './grid_layout.js', uniform_list: './uniform_list.js', drag_drop: './drag_drop.js', tab_stop: './tab_stop.js', focus_visible: './focus_visible.js', scrollable: './scrollable.js', tree: './tree.js', hello_world: './hello_world.js', text_layout: './text_layout.js', text_wrapper: './text_wrapper.js', text: './text.js', input: './input.js', dynamic_fonts: './dynamic_fonts.js', hello_web: './hello_web.js'};
  if (!modules[example]) throw new Error(`Rust example not bundled: ${example}`);
  document.title = `${example} · gpui.rs`;
  const bindings = await import(modules[example]);
  await bindings.default();
  globalThis.wasmBindings = bindings;
  await new Promise((resolve, reject) => {
    const deadline = performance.now() + 30000;
    function check() {
      if (document.querySelector('canvas')) resolve();
      else if (performance.now() > deadline) reject(new Error('Upstream GPUI did not create a canvas.'));
      else requestAnimationFrame(check);
    }
    check();
  });
  // Canvas creation is not evidence of a rendered frame; the E2E inspects its pixels.
  document.documentElement.dataset.runtimeStatus = 'initialized';
  loadTiming.complete([modules[example], `./${example}_bg.wasm`], 'WASM initialized and canvas exists');
} catch (cause) {
  loadTiming.fail();
  document.documentElement.dataset.runtimeStatus = 'failed';
  const error = document.getElementById('error');
  error.hidden = false;
  error.textContent = `gpui.rs failed: ${cause.message}`;
  console.error(cause);
}
