# Compiled anchor browser pair

Status: implementation pending exact-current-head actual Rust/Chromium CI. Source
and synthetic packaging tests do not establish browser parity. The original
Rust-only v2 oracle, predicates, and historical failed v1 remain unchanged.

The separate `web/pairs/anchor.json` pins production core
89108ad966c2d37b0cb44909b1aac3ecfa8e3c4a (tree
dd5612a412d251b468c358a25baa0b0dd592c807), unchanged upstream Zed
5a5fbe79917971a4d52a96b6ddb04da198a5012e and anchor.rs blob
b4b280b714a61cea2cd3f3a8ffd82a8f0000eb6b. Both runtime builds must identify the
same committed suite HEAD/tree. The production checkout must be clean and match
its exact published pin. Local override manifests are explicitly unqualified.

## Observations and bounded claims

Each runtime independently executes all 41 original states in one document:
750x600 → 480x600 → 750x600 at DPR1, 38 trusted mouse moves and two trusted
resizes. Eight buttons are entered and exited at each width; center remains
inert; TopLeft is repeated after restoring width. Pointer targets come from
original idle PNG outline discovery, never candidate scene geometry. The host
only transports input/viewport and browser font measurements to compiled MoonBit.
Core grid/flex, hit testing, anchored_after and deferred prepaint own geometry.

Every state retains at least two independently requested complete original PNGs
with equal decoded RGBA. Pinned Pillow12.0.0 re-decodes every attempt. The verifier
reopens actual source/build profiles, exact core source inventory, served runtime
and font responses, server observations, document/session bindings, trusted input,
original PNGs and diagnostic scenes. Rust generated-worker provenance is checked
by the unchanged oracle verifier. Missing, stale, aliased or tampered files fail.

Both runtimes independently satisfy every unchanged source predicate: eight
button outlines, black hover fill, popup geometry from source Local/static-origin
and corner rules, measured left-edge snapping, clipped narrow buttons, inert
center and exact complete same-runtime idle restoration. Both independently
measured button/hover/popup edges must also agree across runtimes within ±2px.
The existing source-permitted achromatic popup interval51..64 remains unchanged:
it accounts for the two alpha0.1 shadow_sm layers before .75 black fill. This
interval is not an exact opacity or decorative-shadow measurement. No tolerance
is fitted to candidate output. One-pixel geometry defects are not guaranteed
caught. Pixel counts are descriptive across runtimes.

There is no full-image, typography/glyph/shaping, exact shadow kernel/opacity,
rounded-corner, native, internal callback/deferred-order, offscreen-work or other
viewport/DPR/browser/GPU claim. Candidate scenes are diagnostics, not raster proof.

## Real compiled controls and ordinary baseline gate

Two separately compiled candidate-example mutations use the same harness:

- wrong_geometry adds12px to authored Local anchor x before compilation.
- wrong_color replaces popup black with purple before compilation.

The copied source must compile and execute all41 states. Source-valid idle PNGs
still supply pointer targets. Capture stabilization deliberately does not require
correct hover geometry/color, so actual faulty images can reach the independent
comparator. Original package assertions are skipped only for explicit faults;
the manifests disclose that. Ordinary package assertions run normally.

A fault counts only after source/runtime/font/input/provenance verification and
expected original-raster rejection of both stable sample sets. Compiler failure,
startup/transport failure and missing artifacts are failed controls. Both the
runner and direct verifier require an explicit successful ordinary evidence
directory. The verifier reopens that ordinary source/runtime/font/input/PNG
provenance and recomputes the full pair for both stable sets, binding the exact
report, current suite, source profile, core and Rust report hashes. It requires
the fault to start at the ordinary source and load a different compiled module.
A forged success flag, stale run or control-as-baseline cannot qualify faults.

Unmodified/modified source, exact diff, compiler commands/logs, actual loaded
runtime and PNG files, and original rejection stacks are retained. Synthetic
PNG/report corruptions are separately labeled and never count as executed faults.

## Execution

`.github/workflows/anchor-browser-pair.yml` builds actual unchanged Rust and
compiled MoonBit, runs Chromium/SwiftShader and controls, and uploads all ordinary
and fault outputs even after failure. Rust nightly2026-10-14, wasm-bindgen0.2.129
(verified archive hash), Playwright1.56.1 and Pillow12.0.0 match the original oracle.
Use fresh evidence paths; verification rechecks write a new file, preserving the
original failure. Builders require at least1GiB free. Heavy builds/captures belong
in CI, not the storage-constrained local worker. These scripts do not publish.

Lightweight checks:

```
node --test --test-concurrency=1 web/tests/anchor-pair-comparator.test.mjs web/tests/anchor-pair-evidence.test.mjs
python3 -m unittest discover -s web/tests -p test_anchor_pair_packaging.py -v
```

Packaging tests explicitly mock compilation and mark outputs unqualified. Only
retained actual CI artifacts plus independent review can establish this profile.
