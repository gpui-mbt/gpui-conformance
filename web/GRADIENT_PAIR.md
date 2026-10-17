# Bounded gradient candidate and original-PNG pair

Implementation in progress. No browser parity or native conformance is claimed.
The reviewed public core pin is89108ad966c2d37b0cb44909b1aac3ecfa8e3c4a,
tree dd5612a412d251b468c358a25baa0b0dd592c807. Local core overrides remain
explicitly unqualified and are rejected by the evidence verifier.

The original Stage A oracle, its separate synthetic diagnostic, source/font
registries, capture profiles and verifiers remain unchanged. The new candidate
uses the source's ElementTree structure, request-layout/prepaint, core pointer
dispatch, ElementPaintBinding and canonical Scene/PaintCommand paint order. Its
12 gradient quads, two solids and polygon derive from live core bounds. It keeps
source green0.5, raw angles/stops, the omitted polygon canvas-origin-X addition,
and actual tight/clipped polygon normalization. JavaScript transports trusted
input, browser font widths and core RGBA tiles; it contains no gradient math.

## Predeclared comparison

The main document independently runs the exact seven wide/tall/restored source
states. The unchanged Rust verifier is rerun against original source, workers,
fonts, trusted input and complete original PNG attempts. The candidate receives
its own independent session and document, same source actions and viewports.
Source button targets come from its preceding original PNG, never its scene.
Both actual full-image sample sets must stabilize and same-runtime restoration
must be byte-exact. Complete originals, including failures, remain retained.

The separately named component-edge check permits ±2 physical pixels, reflecting
integer raster extent uncertainty. A separately named bounded color-sample check
permits2 UNORM8 RGB codes at selected common opaque interiors; alpha255 and
solid red/blue are exact. This chosen acceptance budget was declared before any
candidate execution. It is not a proved universal f32/Double bound. Every raw
sample/delta and exact-equality result is retained. No failure may be repaired by
changing the budget or dropping samples. Equal-stop central alignment ambiguity
is explicitly retained and separately qualified rather than silently excluded.

## Separately authored policy document

A second document uses the same compiled module and canonical paint pipeline.
It is not part of the unchanged upstream example. Its frozen161px equal-stop
red→blue row requires81 red pixels including the center, then80 blue pixels.
Additional exact witnesses are half-green [0,128,0,255], half-alpha half-green
over white [128,191,128,255], and the clipped polygon's [114,0,19,255] sample.
These expectations match the independently reviewed original SwiftShader WebGL2
diagnostic observations, not a universal GPU rule. A separate source module
freezes rectangles, vertices, clip, sample coordinates and exact predicates.

The policy run consists of exact canonical item IDs[1,2,3,4,6] in order, starting
at0, count5, including the actual opaque white background quad. Core performs
float source-over before one final UNORM8 quantization. No JavaScript blend or
fixture screenshot substitution is permitted. A separate document/session,
served dependency set, source inventory and complete PNG attempts are reopened.

## Transport and compatibility limits

The ordinary opaque example retains canonical item order. Core computes each
tight clipped physical tile, sampling/coverage/transform/opacity and raw linear
shader-output bytes; the host only uploads straight RGBA and source-over presents
it at identity/full opacity. Legacy text remains at its canonical position.
All operations are validated and all tile uploads prepared before destination
painting. Existing drawFrame validation/behavior remains intact. The source uses
binary coverage for core rounded/polygon shapes, so antialias edges are unclaimed.

Per-item RGBA8 introduces an additional fractional-alpha quantization boundary.
The opaque example does not establish arbitrary translucent/interleaved-text
parity. The text-free policy run avoids this boundary with core float composition.
Live sizes are admitted separately from comparison membership: width240–2048,
height300–2048 and actual device DPR0.25–64. The transport fits effective raster
scale to at most4, backing sides≤2048 and≤1,048,576 pixels (integer ceiling).
Logical layout/device snapping, font widths and clicks retain actual device scale.
Both scales are reported; reduced-resolution previews display an explicit notice.
Frozen profile membership requires actual and effective scale1. Other
accepted sizes are usable previews, not evidence extending the frozen profile.

## Genuine compiled controls and gates

Ten source-anchored core mutations cover physical origin, color space, premature
green rounding, premature alpha rounding, angle, authored stops, equal-stop
boundary, gradient origin, clipped polygon basis and nominal polygon bounds.
Each modified core is genuinely compiled with the candidate, executed in both
documents, and independently reverified. Original and compiled core inventories,
mutation bytes/diff, compiler commands/logs and loaded runtime are retained.

A control counts only after an ordinary main AND policy baseline has passed.
Both the runner and direct verifier reopen that ordinary runtime/source/font/
input/PNG evidence and recompute its predicates. A stale or forged success flag,
control-as-baseline, compile/startup/transport error or absent artifact is not a
semantic kill. Both independent stable sample sets must reject the fault.
Synthetic metadata/PNG/byte corruption tests are separately labeled sensitivity
checks and never count as executed controls.

The workflow uses pinned Playwright1.56.1, Pillow12.0.0, Rust nightly2026-10-14,
wasm-bindgen0.2.129 and exact public source pins. Heavy Rust/browser work runs in
CI. Final claims require exact-current source review, actual CI artifacts and
independent review of original retained pixels and provenance.

No full-image cross-runtime, glyph/text, rounded-edge, native/Metal, physical-GPU,
WebGPU, arbitrary backend/DPR/viewport or universal gradient conformance claim.

## Candidate evidence type and live usability

The retained candidate report records the actual visible Canvas2D context and raw
backend observations. A typed candidate-only source-behavior adapter uses unchanged source interaction
and restoration predicates with candidate_canvas2d_core_rgba_transport metadata;
it never fabricates WebGL2/WebGPU or feeds candidate evidence to the Rust gate.
A negative test requires candidate evidence to fail that unchanged Rust backend
gate. Actual Rust remains visible WebGL2 via ANGLE Vulkan SwiftShader only.

The separately labeled Chromium live-usage regression checks800×600 DPR2,
same-size fractional/high-DPR transitions, trusted toggles, invalid-size recovery
and exact return to the initial paired-DPR1 canvas. It is outside all frozen
seven-state/policy conformance counts and numeric budgets. Its PNGs, input events,
actual/effective scales and backing sizes are retained separately. Local Node
checks establish byte-identical paired-DPR1 frames before/after the scale-fit
addition; actual browser results still require CI.

Mutation revision2 adds only required MoonBit parentheses around the forced
color-space match subject. The original registry and compile failure are retained
in preflight evidence, and gradient-mutation-revisions.json records the mapping.
No compile failure or compile-only success is a semantic kill.

Ordered transport preflights at most128 canonical items/operations, each tile at
most2048 per side and1,048,576 pixels, and at most4,194,304 cumulative tile pixels
(16,777,216 RGBA channel bytes) across the full stream. All bounds, canonical
membership, byte arrays and alias checks complete before any ImageData/offscreen
allocation or destination canvas mutation. Core additionally limits each raster
call to64 million item-pixel evaluations; transport does not widen that limit.

## Candidate geometry adapter revision2

The first actual public5c976 run39014283459 remains FAILED. Its original PNGs
show correct authored canonical geometry but binary-covered polygon bounds one
pixel inward on each side versus Rust antialias coverage. Reusing the Rust-only
absolute X/width raster predicates rejected this candidate despite passing both
frozen2px-edge/2-code pair comparisons and the exact policy probe. This is an
explicit candidate-adapter correction, not a reclassification of that old run.

Rust source predicates remain byte-frozen. Candidate polygon bounds now derive
independently from authored coordinates and pixel-center binary inclusion:
canvas width W−32, left0.1canvasWidth with omitted canvas-origin-X, right0.9width,
canvas top H−112, polygon top+30/bottom+80, horizontal slant80 across height50.
The last pixel row lies0.5 above the bottom, so its slant inset is0.8. Integer
rational units derive exact first/last pixel centers without fitted epsilon or
observed-coordinate normalization. Both independent stable sample sets must meet
this absolute source predicate, trusted target/toggle/unchanged-solid/restoration
checks and the unchanged paired numerical budgets. Rerasterized wrong-origin and
wrong-width fixtures test checker rejection across additional sizes; they are
separate synthetic checker controls, not executed compiled-engine mutants. All10
compiled controls still require a fresh ordinary+policy successful CI baseline.
