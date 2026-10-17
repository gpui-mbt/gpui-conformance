# Compiled grid-layout browser pair

Status: implemented, awaiting exact-current-head actual Rust/Chromium CI. Local
source tests and mock packaging checks do not establish actual pair behavior.
The immutable Rust-only baseline and its metadata remain unchanged. The existing
candidate source/host and live catalog are not rewritten by this pair layer.

## Sources and scope

The pair profile is `web/pairs/grid_layout.json`. It pins production core
`aafa754affa049c1eaf69c75c1d04c5d895d3677`, tree
`a6d5e8a048b6b4bc4a9f30912d8edf93581a8bd9`, and unchanged upstream Zed
`5a5fbe79917971a4d52a96b6ddb04da198a5012e`, tree
`990fb995914d51a546b20e5cf0382dafc105c299`. The original `grid_layout.rs`
SHA256 is `c82663a8c48340464f70f96dfa60135f4cd3b48670882b7bc23a9ca787fb261e`.

A separate builder copies the current committed MoonBit example into an archive
of that exact clean core, runs its JS unit tests, and compiles an actual ESM
runtime. The Rust build continues to use the existing isolated unchanged-source
builder and frozen catalog. Both runtime builds must identify the same current
suite commit/tree. Neither source-only metadata nor catalog registration counts
as an executed comparison.

The candidate's production core computes the assigned query size, strict
`width < 400` branch, flex/grid allocation, spans and scene block bounds. Canvas
is the bounded text/decorative paint adapter already present in the candidate.
This pair does not infer Rust callback counts from candidate telemetry.

## Original browser observations

Each runtime independently executes this same one-document viewport cycle:

`500 → 399 → 400 → 401 → 500 → 399 → 400 → 500`, height 500, DPR 1.

The harness uses real Playwright viewport changes and retains trusted resize
observations, actual inner dimensions, canvas bounds/backing and document/session
identities. Every state has at least two separately requested, unchanged,
full-viewport PNG files with equal complete decoded RGBA. The pinned Pillow
12.0.0 decoder is rerun from original files during verification. The candidate
capture waits for stability independently of correctness so a real wrong-color
or wrong-gap runtime can complete its full capture cycle.

The verifier reopens the source/build profiles, exact upstream file, core source
inventory, actual executable and font response bodies, server observations,
trusted inputs, original PNG attempts and candidate diagnostic scenes. Required
files are independent regular files with bounded size; symlink/hardlink aliases,
missing responses, cross-session/cross-runtime capture borrowing, wrong fonts,
historical builds and local overrides are rejected. Rust's original generated
worker verification remains intact. Current suite inputs must equal committed
HEAD, and the production core checkout must match its pin and be clean.

## Bounded comparison, unchanged tolerances

Both runtimes must independently pass every frozen source-profile predicate.
Largest connected exact white/red/green/blue/black components are discovered
from the complete PNG before consulting source formulae. Bounds, order, spans,
TOC overhang/vacancy, exposed gray gaps and strict threshold behavior are checked.
Each runtime must exactly restore its own measured component bounds and counts
when a viewport returns.

The original source tolerances stay unchanged:

- Fill edges: ±2 physical pixels
- Exposed gray gap width: 4px ±1 physical pixel
- Fill-to-fill separation: 4px ±4 physical pixels

The additional measured Rust-versus-MoonBit checks use the same numerical bounds
for differences in fill edges, exposed gap widths and fill separations. Exact
source colors are required. Component pixel counts are retained descriptively
across runtimes, because glyph holes/borders/antialiasing differ. A one-pixel
geometry regression is not guaranteed to be detected. No tolerance is increased
in response to a failure.

There is no full-image, text/shaping/glyph/typography, dashed-border, corner,
shadow, native, callback-count, offscreen-work or other-viewport/DPR/browser/GPU
claim. The separate uniform-list strict typography failure remains untouched.

## Executed controls versus synthetic corruption

`run_grid_layout_pair_controls.py` builds and actually runs two copied-example
faults through the same original-PNG capture and independent verifier:

- `wrong_gap`: both source `.with_gap(4)` calls become `.with_gap(12)` before
  compilation. This is an executed compiled-candidate layout fault.
- `wrong_color`: the source green content fill becomes purple before compilation.
  This is an executed compiled-candidate paint fault.

These are candidate example faults, not production-core engine mutations. The
supplemental semantic suite separately tests core mutations. Each browser fault
retains unmodified and modified source bytes, an exact unified source diff,
compiler commands/logs, compiled-runtime/source/patch hashes, font/runtime
responses, all eight actual captures and the original raster rejection messages.
The original example unit tests are deliberately not run for faulty packages;
their manifest says so. The faulty source itself must compile successfully.

Full source/runtime/font/provenance/input verification must pass before the
expected raster rejection can count. Build failure, startup error, missing
artifact, invalid transport or provenance failure is a failed control. Both
original stable sample sets must reject the expected layout/color fault. Controls
require a successful exact ordinary Rust/MoonBit pair first. The workflow skips
them if ordinary comparison fails. Both the control runner and direct control
verifier CLI require the explicit ordinary-candidate evidence directory.

Before counting either fault, the verifier reopens the successful ordinary
verification artifact and binds it to the exact candidate/Rust report hashes,
source profile, production core and current suite commit/tree/catalog. It then
reopens ordinary source/runtime/font/input/PNG evidence and recomputes the full
pair predicate for both independent stable sample sets. A success flag alone is
insufficient. Missing, failed, stale, different-source or control-as-baseline
evidence is rejected. The fault's source must start at the successful ordinary
example bytes, and its compiled module must differ. The qualified ordinary
report/verification/source/runtime hashes are retained in each fault result.
They never replace or relabel an ordinary failure.

Synthetic raster substitutions and corrupted-report controls have separate
labels. They test comparator/evidence sensitivity and do not count as executed
compiled faults or browser parity evidence.

## CI and local checks

`.github/workflows/grid-layout-browser-pair.yml` is the dedicated actual pair
workflow. It uses Rust nightly-2026-10-14, wasm-bindgen 0.2.129 with verified
archive hash, Playwright 1.56.1, Chromium/SwiftShader and Pillow 12.0.0. It uploads
ordinary and fault evidence even after failure. Results are written exclusively;
a recheck creates a new artifact rather than overwriting the original failure.
No public writes or deployment are performed by these scripts.

Run lightweight source checks with:

```sh
node --test web/tests/grid-layout-pair-comparator.test.mjs web/tests/grid-layout-pair-evidence.test.mjs
python3 -m unittest discover -s web/tests -p test_grid_layout_pair_packaging.py -v
```

The packaging tests explicitly mock the compiler and mark their manifests as
unqualified. They validate packaging only. Actual Rust builds, actual Chromium
captures and actual compiled controls belong in CI, not the space-constrained
local worker. Builders require at least 1 GiB free before starting. Use fresh
output directories; retained originals are never replaced.
