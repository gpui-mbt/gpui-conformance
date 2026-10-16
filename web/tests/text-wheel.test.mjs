import test from 'node:test';
import assert from 'node:assert/strict';
import { wheelDeltaPixels } from '../moonbit/site/text-wheel.mjs';

test('WheelEvent pixel, line, and page units become viewport pixels', () => {
  assert.equal(wheelDeltaPixels(125, 0, 668), 125);
  assert.equal(wheelDeltaPixels(2, 1, 668), 41.6);
  assert.equal(wheelDeltaPixels(-3, 1, 668), -62.4);
  assert.equal(wheelDeltaPixels(1, 2, 668), 668);
  assert.equal(wheelDeltaPixels(-1, 2, 668), -668);
});

test('invalid wheel payloads cannot introduce a non-finite scroll offset', () => {
  for (const value of [NaN, Infinity, -Infinity]) {
    assert.throws(() => wheelDeltaPixels(value, 0, 668), /Invalid typography wheel input/);
  }
  assert.throws(() => wheelDeltaPixels(1, 3, 668));
  assert.throws(() => wheelDeltaPixels(1, 1, 0));
});
