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
- Candidate public core: `89108ad966c2d37b0cb44909b1aac3ecfa8e3c4a`,
  tree `dd5612a412d251b468c358a25baa0b0dd592c807`.
- Historical local source checks below used `13ba1f611d2b22feeb9b789b4451bab5db6c02a1`,
  tree `c29dd688e359c6f306d807d081fbaa28d21fdbbe`, identical to then-public
  `0153b1963bb6b2e434189ecf8591fb2c4c5a7929`. Those results are not
  reassigned to the current additive core pin; current runtime checks require CI.

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
phi line-height snapped at the actual DPR using pinned `text.rs` /
`Window.pixel_snap` (positive half ties toward zero) plus py_0p5 (2px each side). It is not read from
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

The frozen comparison profile remains widths750/480, height600, DPR1. Live
viewports accept width4–4096, height4–16384, DPR0.25–4, with rounded backing
sides at most16384 and area at most33554432 pixels. Every output remains
`conformance: unverified`; `anchor.comparison_profile_match` only identifies
membership, never establishes parity. An anchor-only notice labels live output
outside the reference profile. That historical live-viewport change preserved the frozen oracle, comparator,
profile and then-current core pin. The current additive core pin is listed above.

The minimum4 allows a backing pixel at minimum DPR. Fixed120×65 decorated
buttons remain valid while the viewport clips overflowing source content;
a popup larger than a tiny viewport may itself be clipped. Source padding is
not removed to force small viewports to fit. The width cap conservatively keeps
the existing renderer's shadow caster (translated4096px left) offscreen.
Centered grid positions plus the largest allowed popup width1016 remain well
left of4096 even at width4096; compiled paint probes include width1000 text
metrics and fractional snapping. An experimental uncapped8192-wide frame
exposes a caster; accepting all renderer-size widths would therefore be unsafe.
The shared renderer is unchanged.

Invalid dimensions, DPR, backing resources or shaping metrics clear stale hover
and successful output; supported dimensions recover in the same document.
Logical CSS pixels transport trusted mouse coordinates unchanged, while backing
allocation rounds width×DPR and height×DPR. A self-rearming resolution observer
handles same-size DPR changes. Pagehide removes input/scale observers and resets
hover; pageshow restores them without duplicating listeners. Unit lifecycle
coverage does not claim an actual BFCache hit. Touch, pen and keyboard popup
interaction remain unsupported.

Exports: `anchor_metadata()`, `anchor_frame(width,height,widths,scale)`,
`anchor_pointer(x,y,inside)`, `anchor_reset()`. Widths are title16, nine source
labels16, nine source labels14. The center measurements are unused.

Focused checks:

- `moon test examples/anchor --target js --deny-warn` (after copying the package
  into the pinned core tree) runs four white-box source-layout/resource tests.

- `node --test web/tests/anchor-candidate-host.test.mjs` checks transport/source
  boundaries without a compiled runtime.
- `GPUI_ANCHOR_RUNTIME=/absolute/path/to/anchor.mjs node --test
  web/tests/anchor-candidate-runtime.test.mjs` requires actual compiled exports;
  without the environment variable this check explicitly skips.
- The compiled test executes all eight states at750→480→750, source anchor
  equations, deferred scene order, padding, alpha, inert center, idle restoration,
  invalid metrics, unsupported resources and the real Canvas adapter via a call
  recorder. It observes no browser pixels and is not the actual pair gate.

Full-image, text raster, exact decorative compositing, native, callback-count,
other browser/GPU and arbitrary viewport/DPR conformance remain unverified.

## Live-only regression checks

`GPUI_ANCHOR_RUNTIME=/absolute/path/to/anchor.mjs node --test
web/tests/anchor-live-runtime.test.mjs` checks actual compiled layout, scale,
line boxes, all visible hover targets, maximum shaping inputs, invalid resources,
recovery and actual `drawFrame` command acceptance/caster paths. This is not a
pixel comparison. `anchor-live-host.test.mjs` checks the real host wiring with
synthetic transport/lifecycle fixtures, including DPR-only changes and history
lifecycle cleanup. Grid host regressions remain separate.

`anchor-live-browser.mjs` runs only in the isolated Chromium CI gate against
the actual compiled candidate. It retains live resize/DPR/hover/history states,
explicitly labeled Canvas PNG exports and direct Canvas pixel probes, including
the width4096 shadow boundary. History records observed device metrics first because CDP emulation
can reset on navigation; only observed `pageshow.persisted` reports a BFCache
return. Live-only checks do not expand the strict Rust comparison profile.

Live images are Canvas exports, not composited-page screenshots. They exclude
DOM notices and other page overlays. Each capture binds exact viewport, DPR,
frame/hover and document identity before and after a synchronous export. A
separate live `getImageData` buffer is retained beside the PNG; the pinned Pillow
decoder must reproduce its complete RGBA bytes and backing dimensions, including
maximum-width hover pixel probes. This rejects same-sized stale images as well
as wrong dimensions and changed capture state. Notice state remains a DOM
observation, not an image claim. Original strict pair screenshots are unchanged.
