# Nested scrollable example

This source-derived port follows `scrollable.rs` blob
`c81795618875aecf06e06043bd1709c48630b58f`. Rust browser comparison is recorded separately for each executed profile;
the runtime reports `conformance: unverified`.

The host measures the three 16px IBM Plex Sans labels and passes their shaped
widths, in metadata run order, to `scrollable_frame(widths, scale)`. MoonBit
owns the element hierarchy, lifecycle layout, offsets, wheel updates, pointer
state, core hit paths, hover selection, and scene. No DOM scroll positions or
host-computed rectangles are accepted. Short single-line labels are bounded
to their available source widths; general wrapping is outside this example.

Exports:
- `scrollable_metadata()` returns labels and host font requirements.
- `scrollable_frame(widths, scale)` returns a canonical scene and actual
  MoonBit core viewport diagnostics. Render once before dispatching events,
  and render after each accepted wheel so subsequent input uses current
  prepainted geometry.
- `scrollable_pointer(x,y)` and `scrollable_leave()` retain the pointer and
  return false: the source's anonymous green div does not request a repaint
  for pointer-only changes. The next explicit frame recomputes hover from
  the real clipped core hit path. The reported `hovered` value describes
  the last rendered frame, not a fabricated pointer-state paint.
- `scrollable_wheel(x,y,dx,dy)` accepts finite pixel deltas in the browser's
  positive-content-offset convention. It returns false for invalid input or
  an uninitialized tree, a zero delta, or input outside every eligible scroll
  viewport. A valid nonzero delta with an eligible core viewport returns true
  even when the resulting offsets are clamped unchanged. Core updates are
  retained in `frame.scrollable.updates`.
- `scrollable_reset()` clears the example-local state.

Text markers and fill quads obtain their geometry and inherited clip IDs
from the actual core snapshot. Text and the source's one-pixel border strips
replace or extend those items in preorder. Fill opacity is exactly 0.05,
0.1, or 0.2 in the scene, with opaque color components; it is not approximated
by an eight-bit color alpha. These assembly steps do not replace layout,
scrolling, hit testing, or clip-chain generation.
Painting rounds the authored one-pixel border to the device grid with GPUI's
half-toward-zero/minimum-one-device-pixel stroke rule; zero-area boxes emit no
border strips. Tests cover tiny valid scales without treating them as browser
parity evidence. The target browser comparison profile is 500×500 at DPR 1.

Tests exercise measured boxes, limits, nested same-delta routing, translated
descendants, unchanged sibling X, clipped hover, endpoint recovery, precise
scene opacity, inherited text/border clips, and malformed input rejection.
They are source-derived unit tests, not a claim of Rust or native parity.

## Anonymous hover invalidation

At the pinned upstream revision, the green div has no `.id()`.
`crates/gpui/src/window.rs:4470-4495` omits retained element state for such
anonymous elements, and `crates/gpui/src/elements/div.rs:2845-2868` only
notifies pointer-hover changes when that retained hover state exists.
`div.rs:3460-3480` can nevertheless apply the hover style during a separate
paint. Accordingly, pointer movement alone leaves the displayed fill alone;
a later nonzero wheel can repaint it. `div.rs:3339-3383` notifies after adding
raw deltas, before `div.rs:2473-2485` clamps on prepaint, so even an upward
wheel while already at the top can trigger that repaint. A zero wheel cannot.
