# Independently executed tab-stop source profile

This is a separate paired harness for unchanged upstream `tab_stop.rs` and the
compiled MoonBit counterpart. It preserves the historical Rust-only runner,
contracts, source pin and failure artifacts. It does not relabel those reports.
The corrected Rust-only full profile passed actual CI run `38924410871`: 128
operations, 176 events, 72 stable states and 144 original PNGs. Its original
source labels and artifact `12056466658` (SHA-256
`538ae8beae9429c55a6244f531d5208d5d3d283063089382d36d0a0b7613442d`)
remain historical Rust-only evidence. This new paired execution is unverified;
unit fixtures and retrospective paint analysis do not establish a pair.

## Pinned inputs and build boundary

- Unchanged source: `crates/gpui/examples/tab_stop.rs` at upstream
  `5a5fbe79917971a4d52a96b6ddb04da198a5012e`, blob
  `cc7c34a9979ce4027578ec2c358f503d944ee26f`, SHA-256
  `be187a56c091ee0b609fa396cae4a13b49dcf98ff9e602d8caed3126de3f6a8e`.
- Candidate core: public `fc53cb382c66f68bfc1b3e1cc72d01056cd3c625`, exact tree
  `c9ec59c5fbdbd84548b7d6ffe2c99b8403509db9`.
- Current clean suite Git HEAD/tree and the exact current catalog bytes must
  match retained build/catalog provenance before a pair can be verified.
- The implemented candidate catalog entry and compiled module are required.
  Historical `rust_oracle_only` records cannot supply paired provenance.

`build_rust.py --implemented-example tab_stop` compiles one explicitly named
implemented example. This path rejects unknown/unimplemented names, duplicates,
empty subsets and combinations with `--oracle-only`/`--extra-example`. The
historical extra-oracle guard remains intact. The relocated standalone upstream
manifest, immutable source input, eight embedded font inputs, actual toolchain,
bindings, command, packaging hash and all output hashes are retained. No Rust
source or original upstream manifest is edited. The single-example Cargo target
cache remains separate from the normal full matched build; its key uses the
fixed Rust toolchain, exact upstream revision and locked dependencies.

## Independent capture and verification

The dedicated `tab-stop-oracle.yml` workflow prepares the genuine compiled
candidate site, builds only the unchanged Rust tab-stop subset, then executes
`tab-stop-pair-browser.mjs` separately for Rust and `--candidate`. The same
adaptive source profile runs independently in each browser context at actual
800×600 DPR1 with requested SwiftShader. No private focus/scene diagnostics are
read as oracle input. DOM observations only identify the keyboard transport.

Each runtime retains its own build/catalog copies, actual executed JavaScript,
WASM/host/font responses, source/font inputs, full trusted event sequence,
console/network errors and all original full-viewport PNG attempts. A pinned
Pillow 12.0.0 decoder uses bounded local binary RGBA transport. Each state needs
two independently requested original PNGs with identical complete decoded RGBA.
Failure preserves preceding captures and the raw failure report/screenshot.

The shared source profile contains 128 operations and 72 capture states. Every
frame independently locates all five source cards, both ordinary buttons and
both default-Block groups. Source identities follow physical paint order, with
exact 12px gaps, black 1px/blue 3px borders, a gray 0.4-opacity non-stop card and
source flex/border constraints. Forward/reverse/wrap, equal-index ties, non-stops,
only the authored ordinary-button click listeners and within-renderer message
relations are checked. Three moving-edge probes deliberately lie outside frozen
initial hit bounds: item0's new 1px bottom edge and both ordinary buttons' new
2px edges. Hover/down/up states and the next Tab destination expose stale input
geometry or unexpected owner changes.

`compare-tab-stop-results.mjs` independently rereads and hashes actual retained
files, decodes every PNG attempt and both stable samples, validates complete
trusted operation/capture positions and recomputes per-runtime geometry. It then
compares actual physical controls, focused destinations, adaptive input plans,
source hover/fill/opacity behavior and message categories. It checks candidate
regular-font bytes and all eight source font inputs against pinned hashes; the
actual served Rust WASM must contain the complete retained embedded fonts.

The behavioral result is bounded to this source profile. Message equality is
within each renderer; cross-renderer OCR, glyph/antialiasing, complete-image,
shadow-kernel and native parity are unverified. Directly focused group-container
anchors, touch/IME, other browsers/GPUs/viewports/DPRs are unqualified.

## Failure sensitivity and runtime budget

Unit inputs are explicitly synthetic. They test successful pure measurement
comparison plus rejection of wrong order/focus/geometry, frozen edge coordinates,
missing hover, wrong disabled opacity, unstable samples, stale or corrupted
provenance and absent/forged retained bytes. Verification also runs six corrupted-pixel/operation controls per actual side in addition to the five source traversal controls. Metadata and matching artificial
images alone cannot certify actual paired execution.

The dedicated job is bounded to 75 minutes, with 15 minutes per independent
runtime and 10 minutes for verification. Candidate capture still runs after a
Rust capture failure when the build/browser setup succeeded, and evidence is
always uploaded. The existing 45-minute matched-examples workflow does not run
this full tab profile. Original failed and corrected Rust-only phases remain
separately attributable through their source commits and retained artifacts.

## First candidate paint discrepancy

Actual paired run `38929962683` at candidate `1652518a` retained the complete
unchanged-Rust capture and the first 27 stable candidate states, then rejected
the candidate's exact-color group geometry. A later sibling's inline Canvas
shadow darkened an earlier focused blue border. The original failure evidence
is preserved. [The bounded paint-order correction](TAB_STOP_SHADOW_PAINT_ORDER.md)
records the pinned-source rationale, mutation controls, local validation and
remaining requirement for a fresh actual paired browser run.

The active profile is `tab_stop_paired_state_specific_v2_drag_session_pin`. The
prior v1 artifacts retain their original `eb968228` core identity; a new clean
current-checkout run is required after the additive drag-session pin advance.
The source pixel and traversal predicates are unchanged.
