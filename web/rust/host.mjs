try {
  if (!crossOriginIsolated) throw new Error('Shared-memory WASM requires COOP/COEP response headers on the whole comparison site.');
  const example = new URL(location.href).searchParams.get('example') || 'hello_world';
  if (example !== 'hello_world') throw new Error(`Rust example not bundled: ${example}`);
  const bindings = await import('./hello_world.js');
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
} catch (cause) {
  document.documentElement.dataset.runtimeStatus = 'failed';
  const error = document.getElementById('error');
  error.hidden = false;
  error.textContent = `gpui.rs failed: ${cause.message}`;
  console.error(cause);
}
