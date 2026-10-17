# Supplemental actual GPUI scalar anchor-margin diagnostic

This separately authored font-free diagnostic targets Zed commit
`5a5fbe79917971a4d52a96b6ddb04da198a5012e`, tree
`990fb995914d51a546b20e5cf0382dafc105c299`. It invokes real `anchored`, `deferred`,
`TestAppContext`, and `VisualTestContext` APIs. Source authoring and synthetic
checks do not establish that it compiles or that GPUI produced margin observations.
Actual Rust execution is a later, separately audited CI gate.

Suite base: `46659f7e8d8e503964e41c4e9eb20e0ace08931a`.
Core `4c2e525f02c00a9c1a560152a914f523a4c2fe47` is context only: this stage contains
no candidate build, core change or candidate result.

## Exact bounded domain

There are 88 authored inputs: 22 placement families × symmetric scalar margins
0 and 8 logical pixels × requested scales 1 and 1.25. Every case also retains the
test platform's actual bootstrap-scale-2 frames separately. No redraw count is
assumed. The 22 families are:

- Four crossings by 0.25 pixels beyond a raw viewport edge
- Four positions 0.5 pixels inside a raw edge, within the requested 8-pixel margin
- Four exact raw-edge boundaries
- Four two-edge corner crossings
- Horizontal-only, vertical-only and both-axis oversized popups
- A popup that fits the raw viewport but crosses the opposite edge after a
  right/bottom margin correction, exposing sequential correction order
- Positive and negative Local half-logical-pixel offsets

The 20 edge/corner/oversized families use TopLeft in Window mode. The positive
Local half-offset also uses TopLeft; the negative Local half-offset uses
BottomRight. This is not an eight-anchor margin cross-product. The common fitting
rule operates after anchor subtraction. The unchanged original eight-anchor
coverage remains a separate regression, with its original 24 cases and previous
82 observed frames, plus the separately counted two-case fractional viewport
extension. These are historical qualifications, not fresh results from this
probe. The profile retains hashes of all 26 original anchor and anchor-pair source
files, and the runner rejects changes to them.

The API accepts `impl Into<Edges<Pixels>>`; passing `px(popup.margin)` uses the
existing scalar-to-four-equal-edges conversion. No per-edge public margin surface
is introduced. Raw input contains the original scalar margin and all authored
positions, modes, sizes, parent/window dimensions and scale. The viewport is
160×120 logical pixels; popup and outer layout sizes have integral physical
extents at all exercised scales. The parent is ordinary default-Block layout
with a fixed 120×65 leaf followed by one priority-zero deferred anchor.
No host/browser/catalog/shared-build source is changed.

## Pinned source rule, awaiting actual observations

Locations refer to exact pinned Git blobs, not a possibly older checkout HEAD:

1. `crates/gpui/src/elements/anchored.rs:73–76` selects
   `SnapToWindowWithMargin(edges.into())`.
   `crates/gpui/src/geometry.rs:2155–2163` copies one Pixels value to all edges.
2. `anchored.rs:261–285` derives desired bounds from the anchor and Window/Local
   position before fitting. Static origin and child size come from real GPUI
   observations, never a guessed block-origin witness.
3. `anchored.rs:180–186` adds client inset to each edge. Every frame records
   `Window.client_inset()` and requires None. Other client insets are excluded.
4. `anchored.rs:190–205` uses strict raw viewport predicates in right, left,
   bottom, top sequence: `desired.right() > limits.right()`, then
   `desired.left() < limits.left()`, and the vertical equivalents. Right/bottom
   corrections subtract overflow plus margin. Subsequent left/top corrections
   assign the margin. It does not always clamp positions to an inset viewport.
   Inside and exact-boundary cases therefore must not be inset.
5. `anchored.rs:207–211` subtracts the observed static origin and applies logical
   `offset.x.round()` / `offset.y.round()`, ties away from zero, before
   `with_element_offset`.
6. `crates/gpui/src/window.rs:4196–4224,4308–4314` stores and returns the element
   offset. Our `Observed<E>::prepaint` logs the public `window.element_offset()`
   immediately before delegating to the original element. It is an actual
   getter value, never a predicted intermediate. `window.rs:5289–5301` separately
   snaps that offset to the device grid when obtaining layout bounds. Source
   therefore predicts that logical ±1 becomes ±0.8 in bounds at scale 1.25. Actual
   getter and bounds observations must confirm this interpretation in CI.

Example source-derived hypotheses: with a 40-wide popup and margin8, desired
x 120.25 crosses the 160-wide window and fits at x 112. Desired x 119.5 or exactly 120
does not activate margin correction. An oversized 200-wide popup resolves at x 8
after right then left correction. The 156-wide margin-induced case starts at x 10:
margin 8 produces x 8 after both predicates; margin 0 produces x 4 after right only.
These remain hypotheses until actual Rust observations confirm them.

Outputs distinguish right-before-left and bottom-before-top. They cannot
separately distinguish an arbitrary interleaving of independent horizontal and
vertical checks. The full documented sequence comes from pinned source; no
calculated branch list is claimed as an observed runtime branch trace.

## Observations versus derivations

`Observed<E>` delegates original request-layout, prepaint and paint states and
returns unchanged. It records lifecycle entries/returns, frame/operation,
viewport, scale, client inset, static bounds, child bounds, actual element-offset
getter values and content masks. It contains no placement solver, expected
rectangle input, hitbox insertion, alternate layout engine or rectangle override.
All actual frames are retained. Deferred callbacks after host return belong to
the same frame until the next genuine frame start or operation boundary.

The checker validates nesting, counts, ancestry, deferred order, fixed dimensions,
shared deferred/anchor bounds, logical viewport masks, actual element offsets and
final device-grid placement. It uses observed child size and static origin.
Calculated branches and positions appear only under
`checker_derivation_not_observation`. It does not force a static-origin hypothesis.

Logical viewport masks, rounded layout bounds, paint callback bounds, clipped
raster pixels and hit boundaries differ. This diagnostic checks the first three.
It does not inspect clipped pixels, dispatch pointer input, test hit edges, or
claim background-only divs are interactive. Old hit/fractional tests stay separate.
There is no text/font, screenshot, OS/native-window, browser, full-popover,
nested-priority, outside-down, offset API, SwitchAnchor or candidate-parity claim.

## Fixed numerical contract

The corpus reuses the original finite geometry domain and separate allowances:
2^-10 logical pixels for arithmetic and 2^-10 device pixels for grid checks.
Raw coordinates and far edges have magnitude ≤ 4096; sizes lie in 0..2048.
Scales 1, 1.25, 2 and margins 0, 8 are binary-exact. Popup dimensions are integral on
the physical grid. The immutable original `diagnostics/anchor/README.md`
derives the conservative f32 bound: 1.25 ×(2^-13+2^-12+2^-13+2^-13+2^-14+2^-14)
=0.00091552734375 device pixels < 2^-10. The logical bound is
0.0006103515625 pixels < 2^-10. Integral margins add no new fractional term.

Margins, requested scales, viewport, client inset, shared bounds, prepaint/paint
copies and rounded integer element offsets are checked exactly. No allowance is
fit to actual output. Out-of-domain output is a retained qualification failure.
Allowance tests are checker tests, not GPUI precision evidence.

## Execute and audit

Source-only tests:

    python3 -m unittest discover -s tests -p 'test_anchor_margin_diagnostic.py' -v

CI uses Rust 1.98.1, jsonschema 4.26.0, the existing dependency lock with only the
probe package name renamed, and the established headless build/run pattern:

    python3 diagnostics/anchor_margin/run.py --online \
      --upstream-source _build/upstream-source --output _build/anchor-margin-evidence

The runner requires clean suite/upstream source, fresh ignored output and at
least 8 GiB free. It never removes evidence/caches. Local source authoring must not
compile Rust in the constrained workspace. This is no new browser/native pipeline.

The bundle retains probe/profile/schema/checker/workflow sources, frozen original
sources, relevant upstream files, original/relocated Cargo inputs, compiler
versions, build plan, exact command argv/timings/return codes, stdout/stderr, ELF,
complete raw JSON, run token and exact file hashes. The checker reopens originals,
rejecting missing/extra files or inventory, symlink/hardlink aliases, changed
bytes, stale tokens, wrong commands, changed input/profile/lock/build-plan
bindings, malformed/non-finite/duplicate-key JSON, and coherent incorrect traces.
Exact independent suite commit/tree and suite/upstream Git objects bind retained
bytes to original committed blobs. A copied pass report is not evidence.

    python3 diagnostics/anchor_margin/verify.py _build/anchor-margin-evidence \
      --suite-commit COMMIT --suite-tree TREE --suite-source . \
      --upstream-source _build/upstream-source

Copied bundles may supply `--recorded-execution-root ORIGINAL_ABSOLUTE_PATH`.
The checker still reopens all copied original files and validates original
command identity, without needing the old filesystem. Without all independent
identities/source stores it reports unqualified integrity/semantic inspection.
Bindings are an audit trail, not cryptographic execution attestation. Failures
are retained/uploaded, never fitted away. The synthetic 176-frame fixture is not
a real redraw count; synthetic checker sensitivity is not an executed mutant.

A later candidate stage can start only after independent source review and
actual Rust artifact verification. It needs ordinary-pass gating, actual
executed wrong-margin/always-inset/swapped-edge controls, and unchanged original
anchor regression. This first-stage source claims none of those outcomes.
