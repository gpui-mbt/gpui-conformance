// Browser lifecycle/scheduling only: MoonBit owns computation, application state,
// target dispatch and rendering decisions. The pool is bounded by the 12 chunks.
export function createPrimeHost({runtime, canvas, render, onFailure,
  workerFactory = () => new Worker(new URL('./prime-worker.mjs', import.meta.url), {type:'module'}),
  concurrency = navigator.hardwareConcurrency || 2, now = () => performance.now(),
  lifecycle = window}) {
  const capacity = Math.min(12, Math.max(2, Math.floor(concurrency) || 2));
  runtime.hello_web_init(capacity);
  const diagnostics = {capacity, active:0, created:0, terminated:0, completed:[], failures:[], stopped:false};
  let workers = new Set(), pending = [], generation = 0, started = 0;
  function cleanup() {
    for (const worker of workers) { worker.terminate(); diagnostics.terminated++; }
    workers.clear(); pending = []; diagnostics.active = 0;
  }
  function fail(cause) {
    const failedGeneration = generation;
    cleanup();
    runtime.hello_web_fail(failedGeneration);
    diagnostics.failures.push(String(cause?.message || cause));
    render(); onFailure(cause);
  }
  function dispatch(worker) {
    const next = pending.shift();
    if (next) {
      worker.task = next;
      worker.postMessage({generation, ...next});
    } else {
      worker.terminate(); workers.delete(worker);
      diagnostics.terminated++; diagnostics.active = workers.size;
    }
  }
  function begin(action) {
    cleanup(); generation = action.generation;
    pending = action.chunks.slice(); started = now();
    try {
      for (let i = 0; i < capacity; i++) {
        const worker = workerFactory(); workers.add(worker);
        diagnostics.created++; diagnostics.active = workers.size;
        worker.onmessage = ({data}) => {
          // A message queued before termination may still arrive. Never accept it
          // into a later run, including after navigation/unload or worker failure.
          if (diagnostics.stopped || !workers.has(worker) || data.generation !== generation) return;
          const task = worker.task;
          if (data.index !== task.index || data.start !== task.start || data.end !== task.end ||
              !Number.isInteger(data.count) || data.count < 0 || data.count > task.end-task.start) {
            fail(new Error('Invalid background worker response')); return;
          }
          const elapsed = Math.round(now() - started);
          if (!runtime.hello_web_receive(generation, data.index, data.count, elapsed)) {
            fail(new Error('Rejected background worker response')); return;
          }
          diagnostics.completed.push({...data, elapsed_ms:elapsed});
          dispatch(worker); render();
        };
        worker.onerror = event => { event.preventDefault?.(); if (workers.has(worker)) fail(new Error(event.message || 'Background worker error')); };
        worker.onmessageerror = () => { if (workers.has(worker)) fail(new Error('Unreadable background worker response')); };
        dispatch(worker);
      }
    } catch (cause) { fail(cause); }
  }
  function click(event) {
    if (diagnostics.stopped || event.button !== 0) return;
    const bounds = canvas.getBoundingClientRect();
    const action = JSON.parse(runtime.hello_web_click((event.clientX-bounds.left)*640/bounds.width, (event.clientY-bounds.top)*560/bounds.height));
    if (action.action === 'start') begin(action);
    if (action.action !== 'none') render();
  }
  function stop() {
    diagnostics.stopped = true; cleanup();
    canvas.removeEventListener('click', click);
    lifecycle.removeEventListener('pagehide', stop);
  }
  canvas.addEventListener('click', click);
  lifecycle.addEventListener('pagehide', stop);
  return {diagnostics, stop};
}
