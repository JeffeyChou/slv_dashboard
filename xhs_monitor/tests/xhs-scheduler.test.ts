import test from 'node:test';
import assert from 'node:assert/strict';

import { computeBackoffDelayMs, computeJitteredDelayMs } from '../src/core/xhs/scheduler.js';

test('computeJitteredDelayMs respects lower, midpoint, and upper jitter bounds', () => {
  const intervalMs = 30 * 60_000;
  const jitterMs = 5 * 60_000;

  assert.equal(computeJitteredDelayMs({ intervalMs, jitterMs, random: () => 0 }), 25 * 60_000);
  assert.equal(computeJitteredDelayMs({ intervalMs, jitterMs, random: () => 0.5 }), 30 * 60_000);
  assert.equal(computeJitteredDelayMs({ intervalMs, jitterMs, random: () => 0.999999 }), 35 * 60_000 - 1);
});

test('computeBackoffDelayMs caps exponential multiplier', () => {
  assert.equal(computeBackoffDelayMs(0, 3000), 0);
  assert.equal(computeBackoffDelayMs(1, 3000), 3000);
  assert.equal(computeBackoffDelayMs(4, 3000), 24_000);
  assert.equal(computeBackoffDelayMs(10, 3000), 24_000);
});
