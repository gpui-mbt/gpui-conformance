# Bounded `grid_layout` browser candidate

This source-derived port follows unchanged
[`grid_layout.rs` at zed@5a5fbe7](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/grid_layout.rs).
The source blob is `51f9b13e41fb7913c653d716da3e8ce05a96109d` and its SHA256
is `c82663a8c48340464f70f96dfa60135f4cd3b48670882b7bc23a9ca787fb261e`.

## Implemented path

- The JavaScript adapter transports the actual `window.innerWidth`,
  `window.innerHeight`, and device pixel ratio. It does not select a responsive
  branch, calculate grid rectangles, or clamp a rejected viewport.
- The MoonBit `Element::container_query_root` callback runs during real core
  prepaint and receives its allocated size. It selects a column below 400px and
  the five-by-five grid at 400px and above.
- Core layout owns the four-pixel gaps, equal-fraction tracks, sparse spans,
  full-width header/footer, three-by-three content, three-row advertisement, and
  fixed 224px table-of-contents overflow. Paint retains source declaration order.
- Source blocks are `Display::Block`; `items_center` does not flex-center their
  children. Text begins at the one-pixel border inset. The header includes the
  upstream `Pixels` display suffix: `Header — 500px`.

The unchanged comparison profile is widths **399, 400, 401, and 500px**,
height **500px**, and **DPR 1**. Matching those dimensions does not establish
parity. Live rendering accepts width **16–16384px**, height **32–16384px**,
and **DPR 0.25–4**, provided the actual rounded Canvas backing store has each
side in **1–16384 pixels** and at most **33554432 pixels** total. Inputs must be
finite. DPR is limited to the shared Canvas renderer's supported maximum of 4.
The minimum sizes keep the bounded dashed-border and negative-spread
shadow adapters valid; the maximums bound browser memory allocation. Invalid
sizes clear the stale frame and recover after a valid resize.

Outside the comparison profile a visible notice identifies the live rendering
as unverified. The core still receives the actual logical viewport and DPR;
there is no fixed-size wrapper, host breakpoint, or fabricated geometry. The
frame exposes `comparison_profile_match`, separate from its always-unverified
`conformance`. Narrow text uses bounded wrapping with a fixed line-height
minimum, not general intrinsic multi-line sizing; text may overflow.

## Explicit boundaries

Browser prefix measurements supply font metrics. Bounded MoonBit word wrapping
retains source trailing spaces; it does not claim general GPUI text shaping.
Canvas draws the rounded, dashed white border and the two pinned `shadow_lg`
layers: black alpha 0.1, `(x,y,blur,spread) = (0,10,15,-3)` and `(0,4,6,-4)`.
Canvas blur is an approximation of the GPU kernel.

Text preflight runs one actual core layout to obtain the measured-width header,
then the presented frame runs a second actual layout. Each export reports its
own pass; the browser adapter reports `host_layout_passes: 2`. The callback count
is a candidate diagnostic, not Rust callback-count parity.

`conformance` remains `unverified`. Source tests, mock browser-host tests and
Canvas-call recorders do not establish paired browser execution, glyph pixels,
full-image equality, shadow-kernel equality, or native behavior. The earlier
Rust-only evidence and frozen catalog are a separate, unchanged baseline.

## Checks

The package's `grid_layout_wbtest.mbt` exercises actual candidate core bounds,
thresholds, overflow, resize restoration, labels, wrapping, live resource limits, comparison profile classification,
and metrics rejection. The catalog-driven `web/scripts/build_moonbit.py` copies
this package into the pinned core, tests it for JS, and builds the ESM export.

Source-only host and renderer checks:

    node --test web/tests/grid-layout-candidate-*.test.mjs

These include actual shared-host route execution with mocked imports, successive
viewport resize delivery, rejection/recovery, layer parameters, and distinction
between the live candidate catalog and immutable Rust-only evidence.
