import test from 'node:test';
import assert from 'node:assert/strict';
import { TIMING_PROTOCOL, collectHostTimings, acceptHostTiming } from '../load-timing.mjs';

const origin = 1700000000000;
const perf = {
  timeOrigin: origin, now: () => 90,
  getEntriesByType: () => [{ responseEnd: 12 }],
  getEntriesByName: url => url === 'missing' ? [] : [{ responseEnd: url === 'runtime' ? 25 : 40, transferSize: 0, encodedBodySize: 100 }],
};
const run = () => ({ id: 'new-run', example: 'hello_world', startedAt: origin, sides: { rust: { status: 'loading' }, moon: { status: 'loading' } } });
const message = () => ({ protocol: TIMING_PROTOCOL, run: 'new-run', example: 'hello_world', side: 'moon',
  status: 'complete', milestone: 'Canvas2D draw calls returned', ...collectHostTimings(perf, ['runtime', 'font']) });

test('payload response timing includes every declared file and excludes later initialization', () => {
  const result = collectHostTimings(perf, ['runtime', 'font']);
  assert.equal(result.documentResponseEnd, origin + 12);
  assert.equal(result.payloadResponseEnd, origin + 40);
  assert.equal(result.runtimeSignal, origin + 90);
  assert.equal(result.files[0].transferSize, 0); // Cached is a valid normal-cache observation.
  const current = run();
  assert(acceptHostTiming(current, 'moon', message(), origin + 100));
  assert.equal(current.sides.moon.payloadMs, 40);
  assert.equal(current.sides.moon.runtimeSignalMs, 90);
});
test('missing Resource Timing is unavailable, never replaced with runtime readiness', () => {
  const result = collectHostTimings(perf, ['runtime', 'missing']);
  assert.equal(result.payloadResponseEnd, null);
  const current = run();
  assert(acceptHostTiming(current, 'moon', { ...message(), ...result }, origin + 100));
  assert.equal(current.sides.moon.payloadMs, null);
});
test('stale runs, wrong example, side mismatch, duplicates and late timeout signals cannot mutate a run', () => {
  for (const changes of [{ run: 'old-run' }, { example: 'input' }, { side: 'rust' }, { protocol: 'unknown' }]) {
    const current = run();
    assert.equal(acceptHostTiming(current, 'moon', { ...message(), ...changes }, origin + 100), false);
    assert.equal(current.sides.moon.status, 'loading');
  }
  const current = run();
  assert(acceptHostTiming(current, 'moon', message(), origin + 100));
  assert.equal(acceptHostTiming(current, 'moon', message(), origin + 100), false);
  current.sides.rust.status = 'timeout';
  assert.equal(acceptHostTiming(current, 'rust', { ...message(), side: 'rust' }, origin + 100), false);
});
test('impossible or fabricated payload clocks are rejected', () => {
  for (const changes of [{runtimeSignal: NaN}, {runtimeSignal: origin - 1}, {runtimeSignal: origin + 1000}, {runtimeSignal: origin + 30},
    {documentResponseEnd: undefined}, {payloadResponseEnd: origin + 30}, {files: []}, {files: [null]}, {files: [false]}, {files: [{}]}]) {
    assert.equal(acceptHostTiming(run(), 'moon', { ...message(), ...changes }, origin + 100), false);
  }
});
test('host failure is terminal without inventing load measurements', () => {
  const current = run();
  assert(acceptHostTiming(current, 'rust', { protocol: TIMING_PROTOCOL, run: current.id, example: current.example, side: 'rust', status: 'failed' }, origin + 10));
  assert.deepEqual(current.sides.rust, { status: 'failed' });
});
