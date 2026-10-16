// WheelEvent.deltaMode reports pixels, text lines, or pages depending on the input device.
export function wheelDeltaPixels(deltaY, deltaMode, viewportHeight) {
  if (!Number.isFinite(deltaY) || ![0, 1, 2].includes(deltaMode) ||
      !Number.isFinite(viewportHeight) || viewportHeight <= 0) {
    throw new Error('Invalid typography wheel input');
  }
  if (deltaMode === 1) return deltaY * (16 * 1.3);
  if (deltaMode === 2) return deltaY * viewportHeight;
  return deltaY;
}
