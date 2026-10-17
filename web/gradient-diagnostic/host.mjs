// Load actual compiled synthetic GPUI probes. No DOM/CSS substitute for probe pixels.
try {
  if (!crossOriginIsolated) throw new Error('COOP/COEP isolation required');
  const bindings = await import('./gradient_diagnostic.js');
  await bindings.default();
  document.documentElement.dataset.runtimeStatus = 'initialized';
} catch (error) {
  document.documentElement.dataset.runtimeStatus = 'failed';
  console.error(error);
}
