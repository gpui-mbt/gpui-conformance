# Authored root box and physical viewport: bounded conformance slice

This suite adds an opt-in MoonBit authored-root-box request and keeps the old
fixed-viewport root request available as a compatibility-negative control.
It compares complete observed root and source-order child rectangles. It never
rewrites, clamps, removes, or derives a reported rectangle in the adapter.

## Evidence boundary

The upstream side is real pinned Rust GPUI in `TestAppContext`/`VisualTestContext`,
not a model. The root is an ordinary `div().w_full().h_full()` with actual padding
and border-width style. The adapter applies the public simulated display-scale
change, verifies `Window::scale_factor()`, and reports `Window::viewport_size()`.
This is headless TestWindow evidence, not a real desktop/window-manager metric.
No native desktop, renderer, physical clipping, pixel, or screenshot parity is
claimed by this differential.

MoonBit calls the production `Element::request_layout_root_box_with_device_scale`
API, then `prepaint`, then `paint_snapshot`. It records the actual node bounds,
`Prepainted::viewport_bounds()`, and `SceneSnapshot::viewport()`. The latter two
must equal the supplied origin-zero logical physical-window rectangle exactly,
not within a rounding tolerance. Root/child bounds use the existing 0.00001
comparison tolerance, and the reported GPUI TestWindow viewport uses that same
small tolerance for f32 conversion. Device-scale equality is also checked.
This does not itself prove raster clipping or interactive input behavior; those
are separate core tests.

## Corpus and controls

`root_box_scenarios.json` contains 132 cases:

- 108 threshold cases: padding-only, border-only, and combined asymmetric insets;
  width and height one device pixel below, equal to, and above the snapped inset
  minimum at 1x, 1.5x, and 2x, both empty and populated roots.
- 12 retained original narrow-padding reproductions: row/row-reverse, nowrap/
  wrap/wrap-reverse, physical start/end justification, three differing children.
- Six intentionally non-device-aligned wide physical viewports, in reversed rows
  and columns, proving that snapshot viewport is not substituted with root bounds.
- Six zero-size physical viewports, empty/populated at all three scales.

The positive corpus expects 132 matches. `--fixed-root-control` calls the old
`request_layout_with_device_scale` API inside the same executable and expects
exactly the 54 narrow/zero cases to mismatch, while 78 equal/wide controls match.
This mode deliberately does not assert the new exact physical-viewport contract
for the old API. It still retains the old actual viewport/snapshot observations.

`--negative-control` changes only each observed MoonBit root width by one logical
pixel, including empty roots, to prove the complete root rectangle is compared.
It expects all 132 comparisons to mismatch. This deliberate output corruption is
only a test control, never used in positive evidence. Mismatch-ID sets, not just
counts, must equal their expected controls for a successful runner exit.

`run_root_box_regressions.py` additionally reruns the original unchanged
72-case flex-justify, 48-case align-self, and 68-case reverse-flow scenario files
with the legacy root API selected. The original comparator sees every root/child
rectangle unchanged; only the added viewport metadata is omitted from its input.
Full original process output and exact original scenario bytes are retained.

## Provenance and reproducibility

`root_box_pins.json` fixes the upstream and candidate MoonBit revision/tree and records the MoonBit base.
The build records the actual file list, SHA-256 of every source file, and an
aggregate source-byte identity for upstream/core/suite. Dirty worktrees are allowed
only with explicit `--allow-dirty-worktree` and are honestly marked dirty. The
base HEAD revision and tree are not passed off as the identity of changed bytes.
MoonBit is built from that verified byte snapshot, not `git archive HEAD`.
The build and runners reject source changes, wrong pins, binary tampering,
missing/reordered cases, unsupported projections, malformed/nonfinite rectangles,
and non-exact MoonBit physical viewport values.

The old flex-justify Rust adapter cannot be reused for this corpus: it ignores
`border`, assumes the TestWindow's default scale of 2, and has no window viewport
observation. It remains usable as independent old-corpus evidence. The new Rust
adapter uses `build_flex_justify.cached_rust` to compile/link just its source
against a compatible read-only exact-pin dependency cache. It records and rechecks
all cached dependency hashes. There is deliberately no full Cargo rebuild fallback.

The following commands must run with the installed shared toolchain on PATH.
Preparation without `--execute-build` writes a source snapshot and build plan only:

```sh
python build_root_box.py \
  --upstream-source /workspace/shared/interaction-conformance-20261019/upstream \
  --moonbit-source /tmp/root-box-20261021/core \
  --rust-dependency-cache /workspace/shared/reverse-flex-20261019/build-public-host-final-candidate \
  --output /tmp/root-box-20261021/build-candidate \
  --allow-dirty-worktree --execute-build
```

Use the returned executable paths and manifest with `run_root_box.py`, adding
`--fixed-root-control` or `--negative-control` in separate evidence directories.
Run `run_root_box_regressions.py` with the same executables/manifest/source paths.
All three runners require a new `--output` directory and retain stdout, stderr,
source/binary identities, original corpus bytes, and comparison results.

## Current execution status

Executed with actual Rust GPUI and MoonBit binaries against core
`26ec003a9fadb18aa4b969f0ff485a681a2ce6d1` / tree
`7a0b7cd362eb03d49c41799f60f1e8f3b228927e`:

- Positive root-box comparison: 132/132 pass, including exact MoonBit viewport.
- Legacy fixed-root negative: exactly 54 intended mismatches and 78 matches.
- Root-width corruption control: 132/132 mismatches detected.
- Unchanged legacy regressions: flex-justify 72/72, align-self 48/48,
  reverse-flow 68/68 pass.
- Focused portable contract modules pass independently: root-box 14 tests,
  flex-justify 17, align-self 17, reverse-flow 16. Synthetic tests do not
  constitute framework execution.

An initial threshold generator used half-up rounding for authored .25 lengths.
The unchanged production/upstream rule is half-toward-zero, making ten nominal
narrow samples at 2x actually equal/wide. Initial outputs were retained separately
(132 positive matches, but 44 rather than the intended 54 fixed-root mismatches).
The final threshold matrix uses non-half-tie fractional .2 lengths and tests the
actual snapped minima; separate fractional-viewport cases retain .25 inputs.
Nothing in the production implementation was changed to fit the corpus.

The first MoonBit build rejected an unused scene import under `--deny-warn`.
Only that import was removed; the failed command/logs and original source hashes
were preserved, and the same MoonBit build directory resumed successfully.
Rust compiled once against the existing read-only dependency cache, not a full
Cargo build. Later corpus/comparator/tests/docs refinements changed no compiled
adapter, core, or upstream bytes.

`attest_root_box_build.py` verifies the final committed source against the exact
compiled bytes without rebuilding. It checks prepared source copies, binaries,
and cached dependencies; accepts only a fixed list of noncompiled source changes;
and retains the original build manifest unchanged. It explicitly labels the
result as an attestation of existing binaries, not a build from the final commit.
Runners accept a later suite commit only when its recorded source bytes match.

A broad `unittest discover` invocation was also attempted: 727 tests, 10 failures,
244 errors, 3 skips. It encountered generic-module import collisions, missing
external evidence-fixture prerequisites, and unrelated baseline-identity checks.
No matching baseline aggregate run was done, so these are not asserted to be
pre-existing, nor is the aggregate suite called passing. Focused modules and
actual preserved regression corpora above are the verified scope.

Local retained evidence is under `/tmp/root-box-20261021/`: original `positive/`,
`fixed-control/`, corrected diagnostic `corrected-precommit/`, the actual
`build-candidate/` with failed-attempt logs, and final committed-source runs under
`final-positive/`, `final-fixed-control/`, `final-corrupt-control/`,
`final-regressions/`. Final attestation is `final-build-attestation.json`.
These paths are local artifacts, not published URLs or portable bundled evidence.
