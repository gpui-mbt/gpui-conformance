import { acceptHostTiming, epochNow } from './load-timing.mjs';

export function createLoadComparison({ frames, output, timeoutMs = 60000 }) {
  let active = null;
  let timer;
  let sequence = 0;
  const format = value => value === null || value === undefined ? 'Unavailable' : `${value.toFixed(1)} ms`;
  const sideName = side => side === 'rust' ? 'gpui.rs (Rust/WASM)' : 'gpui.mbt (MoonBit/JS)';
  function render() {
    globalThis.gpuiLoadComparison = active ? structuredClone(active) : null;
    if (!active) return;
    output.replaceChildren();
    const summary = document.createElement('p');
    const loading = Object.values(active.sides).some(side => side.status === 'loading');
    summary.textContent = `Run ${active.sequence} · ${loading ? 'Loading…' : 'Finished'} · ${active.launchOrder.map(sideName).join(' then ')} · navigation assignment gap ${format(active.launchSkewMs)}. Normal browser cache; not a cold-load benchmark.`;
    output.append(summary);
    const results = document.createElement('div'); results.className = 'load-results';
    for (const side of ['rust', 'moon']) {
      const record = active.sides[side];
      const panel = document.createElement('div');
      const title = document.createElement('strong'); title.textContent = sideName(side); panel.append(title);
      const values = document.createElement('p');
      if (record.status === 'complete') {
        values.textContent = `Document response: ${format(record.documentMs)}\nMain payload received: ${format(record.payloadMs)}\nRuntime signal: ${format(record.runtimeSignalMs)} (${record.milestone})`;
      } else {
        values.textContent = { loading: 'Waiting for runtime signal…', failed: 'Runtime failed. Load result unavailable.',
          timeout: `No runtime signal within ${timeoutMs / 1000} seconds. Load result unavailable.`, unavailable: 'Runtime not bundled. Comparison unavailable.' }[record.status];
      }
      panel.append(values); results.append(panel);
    }
    output.append(results);
  }
  function finishIfSettled() {
    if (active && Object.values(active.sides).every(side => side.status !== 'loading')) clearTimeout(timer);
    render();
  }
  addEventListener('message', event => {
    if (!active || event.origin !== location.origin) return;
    const side = ['rust', 'moon'].find(side => event.source === frames[side].contentWindow);
    if (!side || !acceptHostTiming(active, side, event.data, epochNow())) return;
    finishIfSettled();
  });
  return {
    cancel(message = 'Select an implemented pair to measure loading.') {
      clearTimeout(timer); active = null;
      globalThis.gpuiLoadComparison = null;
      output.textContent = message;
    },
    start({ example, urls }) {
      clearTimeout(timer);
      const id = crypto.randomUUID();
      const order = ++sequence % 2 ? ['rust', 'moon'] : ['moon', 'rust'];
      const navigationUrls = Object.fromEntries(Object.entries(urls).map(([side, value]) => {
        if (!value) return [side, null];
        const url = new URL(value); url.searchParams.set('run', id); return [side, url.href];
      }));
      active = { id, example, sequence, cache: 'normal-browser-cache-uncontrolled',
        startedAt: epochNow(), launchOrder: order.filter(side => navigationUrls[side]), launchSkewMs: null,
        firstPresentedFrame: 'unavailable', sides: {} };
      for (const side of ['rust', 'moon']) active.sides[side] = { status: urls[side] ? 'loading' : 'unavailable' };
      // No preload, await, readiness barrier or UI work between the two navigation assignments.
      for (const side of active.launchOrder) {
        active.sides[side].assignedMs = epochNow() - active.startedAt;
        frames[side].src = navigationUrls[side];
      }
      if (active.launchOrder.length === 2) active.launchSkewMs = Math.abs(active.sides.rust.assignedMs - active.sides.moon.assignedMs);
      for (const side of active.launchOrder) frames[side].hidden = false;
      timer = setTimeout(() => {
        if (active?.id !== id) return;
        for (const side of Object.values(active.sides)) if (side.status === 'loading') side.status = 'timeout';
        render();
      }, timeoutMs);
      render();
      return id;
    },
  };
}
