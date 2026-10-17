# Source-derived anchor browser candidate

This candidate is implemented, not browser-pair-qualified. The frozen Rust-only
oracle remains separate and unchanged. No local Rust/WASM or browser build/run
was used to produce the source and compiled-export checks below.

## Provenance and ownership

- Upstream engine: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`.
- Unchanged `crates/gpui/examples/anchor.rs` blob:
  `b4b280b714a61cea2cd3f3a8ffd82a8f0000eb6b`.
- Source SHA-256:
  `5be423ce91b36db94857a8f7758f7f5967d0103b77941fa7bc7c5a64e3c4fe72`.
- Candidate public core: `0153b1963bb6b2e434189ecf8591fb2c4c5a7929`,
  tree `c29dd688e359c6f306d807d081fbaa28d21fdbbe`.
- Local source checks use identical core tree at local `13ba1f611d2b22feeb9b789b4451bab5db6c02a1`.

`moonbit/anchor/anchor.mbt` creates genuine Element grid/flex nodes and calls
`anchored_after(..., Local, ...)`, `deferred`, layout, prepaint, core hit testing
and SceneSnapshot. No JavaScript placement, snapping, hover selection or hidden
replacement renderer is used. Every frame hit-tests current viewport geometry;
hover frames request a second layout with a real deferred popup. This two-pass
adapter is explicitly not Rust callback-count parity.

## Source dimensions and painting

The white root has 40px padding, a 16px gap and a centered 512px-wide three-column
grid with 24px gaps. Its source vertical flex shrinking is lowered into the core
flex item with a source-derived minimum of three 65px buttons plus two 24px gaps.
Each genuine hover target is 120×65 with black border1 and rounded_lg8. The
center is an unlabeled white, non-interactive cell.

Popup width comes from browser-measured label width at text_sm14 plus px_2
(8px each side), with source min_w100. Height comes from the pinned default
phi line-height rounded at DPR1 plus py_0p5 (2px each side). It is not read from
an oracle PNG. The core measures that subtree, applies the source corner and
resolved Local position, snaps it to the window and defers its paint. The popup
and text have no pointer hitbox. Text layout positions are real child bounds;
the Canvas host supplies widths and draws the resulting scene text.

The popup uses white text, rounded_sm2, black with .75 alpha represented as the
SceneSnapshot color byte191, and the existing two-layer shadow_sm Canvas
extension. The root/button backgrounds remain opaque white except the hovered
button's black background and white text. Canvas shadow kernels, font metrics,
shaping/rasterization and byte-alpha quantization are explicit boundaries;
source-permitted popup gray is not evidence of exact shadow/opacity parity.

## Bounded protocol and tests

Only widths750/480, height600, DPR1 are accepted. Other viewports visibly reject
and clear the prior frame; returning to a supported viewport can recover in the
same document. The host transports trusted mouse pointer coordinates and leave;
touch, pen, keyboard popup interaction and arbitrary DPR/viewports are unsupported.

Exports: `anchor_metadata()`, `anchor_frame(width,height,widths,scale)`,
`anchor_pointer(x,y,inside)`, `anchor_reset()`. Widths are title16, nine source
labels16, nine source labels14. The center measurements are unused.

Focused checks:

- `moon test examples/anchor --target js --deny-warn` (after copying the package
  into the pinned core tree) runs three white-box source-layout tests.

- `node --test web/tests/anchor-candidate-host.test.mjs` checks transport/source
  boundaries without a compiled runtime.
- `GPUI_ANCHOR_RUNTIME=/absolute/path/to/anchor.mjs node --test
  web/tests/anchor-candidate-runtime.test.mjs` requires actual compiled exports;
  without the environment variable this check explicitly skips.
- The compiled test executes all eight states at750→480→750, source anchor
  equations, deferred scene order, padding, alpha, inert center, idle restoration,
  invalid metrics, unsupported profiles and the real Canvas adapter via a call
  recorder. It observes no browser pixels and is not the actual pair gate.

Full-image, text raster, exact decorative compositing, native, callback-count,
other browser/GPU and arbitrary viewport/DPR conformance remain unverified.
