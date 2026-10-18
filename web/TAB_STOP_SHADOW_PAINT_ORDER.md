# Tab-stop source shadow paint ordering

## Actual failed pair

PR #48 candidate `1652518a` / actual pair run `38929962683` retained a complete
unchanged-Rust capture and the candidate's first 27 stable capture states before
candidate geometry verification failed. The first failing state is
`forward_group1_child1`: source group children occupy `(16,332,768,40)`,
`(16,372,768,40)` and `(16,412,768,40)`. The first child's blue 3px border should
remain RGB `(0,0,255)`. In the original candidate PNG, pixels `(16,370)` and
`(16,371)` are `(0,0,254,255)` and `(0,0,252,255)`; unchanged Rust retains
`(0,0,255,255)` at both positions. The exact-color edge scan consequently splits
one group into two runs and finds nine runs instead of eight. The second child
in either group has the same later-sibling shadow signature.

These retained original PNGs and failed reports remain unchanged. No border
predicate, geometry, expected color, or capture threshold was relaxed.

## Pinned source rationale

The reviewed source is Zed `5a5fbe79917971a4d52a96b6ddb04da198a5012e`.
Relevant paths and line ranges at that revision:

- `crates/gpui_macros/src/styles.rs:428-436`: `shadow_sm` declares two black
  0.1-opacity layers, both offset `(0,1)`, with blur/spread `(3,0)` and `(2,-1)`.
- `crates/gpui/src/style.rs:711-753`: drop shadows precede the background;
  children paint in the continuation; borders paint afterward.
- `crates/gpui/src/window.rs:4572-4603`: scene ordering bounds are the covered
  offset/spread shadow rectangle. They do not include the Gaussian blur tail.
- `crates/gpui/src/window.rs:3327-3343,4177-4188`: inherited content masks
  intersect before device-pixel coverage.
- `crates/gpui/src/scene.rs:88-109,151-162,201-210,288-320`: clipped nonempty
  primitive bounds determine order; stable sorting and batch selection use
  draw order followed by primitive kind, including `Shadow` before `Quad`.
- `crates/gpui/src/bounds_tree.rs:116-135` and
  `crates/gpui/src/geometry.rs:965-972`: insertion receives one plus the maximum
  intersecting order. Edge touching alone does not intersect.

The compatibility source checkout is also unchanged at
`d9afb21688e04f89d9e94d96d33eb530aef90886`; its scene insertion/batching,
strict intersections and shadow-bound construction use these same relevant
rules. Its `crates/gpui_wgpu/src/shaders.wgsl:976-989` expands only the drawn
shadow geometry by three blur radii. That expansion does not change the
ordering rectangle.

For adjacent opaque group children, the later child's unblurred shadow boxes
do not overlap the previous child's body. Their shadow commands can therefore
batch before that earlier opaque body. An immediate per-item Canvas shadow
paint instead applies the later blur tail over the already painted blue border.
This is a host scheduling discrepancy; no core change is required.

## Bounded correction

Only frames containing the explicit `frame.shadows` / `shadow_sm` extension use
the new command scheduling. Each declared shadow still draws both original
Canvas approximation layers, with the original offset, blur, spread, opacity,
scale and inherited clip. Commands receive clipped, unblurred ordering bounds,
strict overlap orders and stable kind/source ties. Intersecting later shadows
remain above earlier bodies; there is no global all-shadows prepass, special
focus coordinate, focus-dependent scheduling, or after-the-fact border repaint.
Frames with absent or empty explicit shadows retain their old snapshot paint
sequence, including existing legacy preview shadows and scroll behavior.

The extension rejects scroll, nonidentity item transforms, duplicate item IDs
and mixing the legacy shadow model before any Canvas call. Empty clipped
ordering boxes emit no command. Nested masks intersect logically before device
coverage, preventing fractional gaps from manufacturing an overlap.

Existing fill/border host operations remain atomic, and text remains a host
operation. This is sufficient for the current square, opaque tab-stop buttons
and their centered labels. It does not reconstruct GPUI parent-border
continuations, border strips, explicit retained layers, text atlas batches,
arbitrary transformed scenes or general GPUI compositing. Canvas blur remains
an approximation of the GPU kernel. The source behavior pair, original PNG
verification and complete-image/GPU shadow parity remain separate claims.

## Local validation, 2026-10-16 UTC

- Full host contracts: `node --test web/tests/*.test.mjs`, 524/524 pass with
  the already available Pillow 12.0.0 dependency on `PYTHONPATH`.
- Web Python unit tests: 22/22 pass.
- Focused renderer tests: 15/15 pass. Coverage includes zero-gap siblings,
  stable source ties, strict touching/kind ties, intersecting later shadows,
  non-adjacent siblings, clips, opacity, DPR scaling, fully clipped casters,
  disjoint nested fractional masks, atomic unsupported rejection, and the
  unchanged no-explicit-shadow sequence.
- Replacing only the renderer with the exact old source at
  `1d088c359fef7bc121594d438b47f57be69a6cdb` fails 7/15 focused tests. Its SHA-256
  is `0bb19888de98c58e8f6a5aa2c34d06cea161e1ddfddeb74c94e82e2f95dca932`.
- A deliberate global-shadow-prepass mutation fails 2/15 tests, including
  intersecting-shadow interleaving.
- A safe command recorder imports the actual retained compiled candidate
  module (SHA-256
  `aac842c72d2a27188f4d27c2dbe30d412cb996061d708c99606a9916523d516e`). With
  explicit synthetic text-width inputs, it exercises 54 compiled frames:
  27 initial/forward/reverse states at each of DPR 1 and 2. All 16 adjacent
  focused-sibling order checks pass. The exact old renderer fails all 16 with
  the identical compiled module. Every frame retains all 16 shadow layers.

Recorder outputs establish command ordering and failure sensitivity, not new
pixels or trusted browser events. Local validation artifacts are preserved in
`_build/shadow-paint-validation/` in the isolated correction checkout. No local
browser, Rust build, Mac execution, core edit or public write was performed.
The actual independent browser pair must rerun against the final clean committed
suite and retain its fresh assets, PNGs and current-checkout provenance before
this correction can qualify that profile.
