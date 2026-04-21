export type XhsDelayInput = {
  intervalMs: number;
  jitterMs: number;
  random?: () => number;
};

export function computeJitteredDelayMs(input: XhsDelayInput): number {
  const random = input.random ?? Math.random;
  const lowerBound = input.intervalMs - input.jitterMs;
  const span = input.jitterMs * 2;
  return Math.max(0, Math.floor(lowerBound + span * random()));
}

export function computeBackoffDelayMs(failureCount: number, baseDelayMs: number): number {
  if (failureCount <= 0) {
    return 0;
  }

  const multiplier = Math.min(8, 2 ** (failureCount - 1));
  return baseDelayMs * multiplier;
}
