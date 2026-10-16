// One clock across same-origin documents. Host signals are diagnostics, not paint proof.
export const TIMING_PROTOCOL = 'gpui-load-timing-v1';
export const epochNow = () => performance.timeOrigin + performance.now();

export function collectHostTimings(perf, payloadUrls) {
  const navigation = perf.getEntriesByType('navigation')[0];
  const files = payloadUrls.map(url => {
    const entry = perf.getEntriesByName(url, 'resource').at(-1);
    return {
      url,
      responseEnd: entry?.responseEnd > 0 ? perf.timeOrigin + entry.responseEnd : null,
      transferSize: entry?.transferSize ?? null,
      encodedBodySize: entry?.encodedBodySize ?? null,
    };
  });
  return {
    documentResponseEnd: navigation?.responseEnd > 0 ? perf.timeOrigin + navigation.responseEnd : null,
    payloadResponseEnd: files.length && files.every(file => file.responseEnd !== null)
      ? Math.max(...files.map(file => file.responseEnd)) : null,
    runtimeSignal: perf.timeOrigin + perf.now(),
    files,
  };
}

export function createHostTiming(side) {
  const query = new URL(location.href).searchParams;
  let sent = false;
  function send(fields) {
    if (sent || !query.get('run') || parent === globalThis) return;
    sent = true;
    parent.postMessage({ protocol: TIMING_PROTOCOL, run: query.get('run'),
      example: query.get('example') || 'hello_world', side, ...fields }, location.origin);
  }
  return {
    complete(payloadPaths, milestone) {
      const urls = payloadPaths.map(path => new URL(path, location.href).href);
      send({ status: 'complete', milestone, ...collectHostTimings(performance, urls) });
    },
    fail() { send({ status: 'failed' }); },
  };
}

// Reject old generations, impossible clocks, malformed messages, and duplicate signals.
export function acceptHostTiming(run, side, message, receivedAt) {
  const target = run?.sides[side];
  if (!target || target.status !== 'loading' || message?.protocol !== TIMING_PROTOCOL ||
      message.run !== run.id || message.example !== run.example || message.side !== side) return false;
  if (message.status === 'failed') {
    target.status = 'failed';
    return true;
  }
  if (message.status !== 'complete' || typeof message.milestone !== 'string' ||
      !Array.isArray(message.files) || !message.files.length) return false;
  const validTime = value => value === null || (Number.isFinite(value) && value >= run.startedAt && value <= receivedAt + 1);
  if (![message.documentResponseEnd, message.payloadResponseEnd, message.runtimeSignal].every(validTime) ||
      message.runtimeSignal === null || !message.files.every(file => file && typeof file.url === 'string' && validTime(file.responseEnd))) return false;
  if ([message.documentResponseEnd, ...message.files.map(file => file.responseEnd)]
      .some(value => value !== null && value > message.runtimeSignal)) return false;
  // A final response may be absent (e.g. unavailable Resource Timing), but never fabricated from readiness.
  if (message.payloadResponseEnd !== null && (message.files.some(file => file.responseEnd === null) ||
      message.payloadResponseEnd !== Math.max(...message.files.map(file => file.responseEnd)))) return false;
  target.status = 'complete';
  target.documentMs = message.documentResponseEnd === null ? null : message.documentResponseEnd - run.startedAt;
  target.payloadMs = message.payloadResponseEnd === null ? null : message.payloadResponseEnd - run.startedAt;
  target.runtimeSignalMs = message.runtimeSignal - run.startedAt;
  target.milestone = message.milestone;
  target.files = message.files;
  return true;
}
