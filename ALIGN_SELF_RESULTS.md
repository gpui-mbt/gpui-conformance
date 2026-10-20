# Per-item cross-axis alignment: bounded headless diagnostic

This independent 48-case corpus compares actual Rust GPUI
`5a5fbe79917971a4d52a96b6ddb04da198a5012e` (tree
`990fb995914d51a546b20e5cf0382dafc105c299`) with the exact committed
MoonBit candidate in `align_self_pins.json`. This diagnostic reference is
separate from the suite's older overall `pins.json` compatibility target.
It compares complete root and source-order child rectangles at device scale 2,
with absolute numeric tolerance 0.00001. It does not project away dimensions.

## Scope

The seven modes are auto/inherit, physical start/end, center, stretch, and
flex-relative start/end. Each is exercised in rows, columns, and reversed main
flows. Cases include mixed per-item overrides, explicit versus auto cross
sizes, inherited defaults, min/max caps, signed overflow, asymmetric padding,
wrapping and wrap-reverse. In particular, GPUI `self_start`/`self_end` are
physical while `self_flex_start`/`self_flex_end` and inherited
`items_start`/`items_end` reverse their cross edges under wrap-reverse.
Stretch resizes only an auto cross dimension and preserves min/max limits.

Baseline core `603cbfe15bf30e775ec71821d8b540e184e738d9` has no align-self
API. This is a capability addition, not a correction to an existing API.
No baseline fallback that silently ignores the requested override is called
conformance. The explicit capability-negative build instead disables the new
production alignment resolver, and remains labeled as a mutation.

## Current integrated public candidate

The current pin is public core
`bc89003e8412afa6c81fc8eb2073bf0b39e6b605`, tree
`c51031f08b708c36a2d64700fb4383a864ba9968`, from
[core Draft PR #139](https://github.com/gpui-mbt/gpui.mbt/pull/139).
It retains latest main `eea3c1443c61fb4e7ae4a4ad2a79fd778cd9670c` and all
unrelated text-host/accessibility work. The four layout blobs are unchanged
from the earlier independently reviewed candidate below. Its changelog entry
is now correctly under Unreleased; this work makes no registry release.

Fresh integrated library checks pass: format and all-target deny-warn
typechecking; native layout/element **594/594**; JS, Wasm and Wasm-GC each
**1105/1105**; full native **1362/1362** with the same documented font fixture.
Field E2E remains gated/skipped. These are the current integrated totals; the
1092/1347 totals below belong only to the historical local candidate.

The exact public core pin and clean current suite tree are rebuilt and replayed
into `build-public-candidate/`, `build-public-disabled/` and
`run-public-{candidate,width-control,disabled,reverse-regression}/` under the
same external evidence root. The required observations remain **48 matches**,
**48 width-control mismatches**, **44 capability mismatches with four inherited
controls**, and **68 Auto regression matches**. Final manifests retain the
exact public suite revision/tree after publication. No old artifact is
relabeled as a new-source execution.

## Earlier local execution results

Against the exact core candidate
`2a19d1b038265292c9ac7d2607915cad688ba60d`, tree
`ba979f613b8a1f3c73a6868fb554f6a71892951c`:

- Actual candidate: **48 matches, zero mismatches**.
- Process-backed one-pixel width control: **48 mismatches, zero matches**.
- Separately compiled production-resolver capability negative: **44
  mismatches, four matches**. The four passes are precisely the per-direction
  inherit-center controls, which request no overrides.
- Baseline `603cbfe15bf30e775ec71821d8b540e184e738d9`: actual compilation
  fails with nine missing `with_align_self`/`AlignSelf` API errors. All 951
  extracted baseline blobs, including symlink targets, match the Git tree.
  No baseline runtime pass is claimed.
- A real regression rerun adds explicit Auto overrides to the previous 68
  reverse-flow cases and preserves **68 matches, zero mismatches**.
- New portable corpus/comparator/build-cache contracts: **17 pass**.
- Existing portable/fixture/visual/observer contract discovery: **62 pass**.
- Independent core review also executed an independently generated 848-case
  deterministic/seeded corpus against actual GPUI: **848 matches**.

The immutable implementation/suite build at `a38a615` was executed before the
final documentation and dependency-metadata ledger hardening. Final replay
manifests bind the subsequent clean suite revision/tree and unchanged core pin;
the result note does not embed its own self-referential Git commit SHA.

Local retained evidence is rooted at `/tmp/align-self-20261020/`:
`build-final-candidate/`, `build-final-disabled/`, `run-final-candidate/`,
`run-final-width-control/`, `run-final-disabled/`, and
`run-final-reverse-regression/`. The build manifests and raw process output are
necessary evidence; this source-controlled note is only a result index.
`baseline-capability.json` and `baseline-build.{stdout,stderr,exit}` retain the
actual missing-capability build. These local files are not published artifacts.

## Earlier library and broader-suite checks

The unchanged core candidate passes all-target deny-warn type checking;
JavaScript, Wasm and Wasm-GC each pass **1092/1092**, and native passes
**1347/1347**. The focused native layout/element run passes **587/587**.
The native run first required the repository's `scripts/prepare_ubuntu.sh`
using the existing cloud Wayland sysroot. It also required the documented
`tests/linux_text/fonts.conf`, verified by `check_linux_text_fonts.sh`, plus a
writable XDG cache. The initial unconfigured run's two font-sensitive failures
are not presented as a clean native run. The opt-in field E2E gate remained
skipped; no live physical-input qualification is inferred.

A full Python discovery on implementation suite `a38a615` ran 696 tests and
reported 10 failures, 244 errors and three skips. An isolated, unchanged current
main `fa395040ea0ad1260d750277f88f8a6b26d8c0ae` with Git metadata ran 682 tests
with exactly the same 10 failures, 244 errors and three skips. All 254 ordered
failing/error identities match; there is no candidate-only failure/error
identity. The broad suite is therefore not green in this environment. The
observed failures include frozen historical-source assertions, import-name
collisions, missing retained native evidence/historical objects and an existing
process-exit control. No unrelated fixes are included. Three additional cache-
provenance contracts were added afterward and pass in the focused 17-test run.
An earlier archive-only baseline lacked Git metadata, produced different Git-
related errors, and was explicitly excluded from this comparison.

## Reproduce

Use clean pinned source checkouts, Rust 1.98.1, MoonBit, and cached offline
Cargo dependencies. Neither build helper nor runner writes into either source
checkout. Choose new output directories; old evidence is never overwritten.

```sh
python build_align_self.py --upstream-source UPSTREAM --moonbit-source CORE --output BUILD
python run_align_self.py --upstream-source UPSTREAM --moonbit-source CORE \
  --rust-exe BUILD/rust/target/debug/gpui-conformance-probe \
  --moon-exe BUILD/moon/_build/native/debug/build/conformance_probe/conformance_probe.exe \
  --build-manifest BUILD/build-manifest.json --output RESULTS
# Repeat the runner with --negative-control in a new output directory.
# Build separately with --disable-align-self for the capability-negative mutant.
python -m unittest discover -s tests -p test_align_self.py -v
```

On a storage-constrained machine, `--rust-dependency-cache PRIOR_BUILD` can
reuse the immutable Rust dependencies of a prior exact-pin build read-only.
The new adapter is still compiled and linked. The helper checks its upstream
source revision/tree, compiler version and Cargo.lock, records the prior build
manifest and each dependency hash, and rechecks hashes after linking. In this
mode the new Rust executable is BUILD/gpui-conformance-probe, not under
BUILD/rust/target. This is dependency reuse, not a fresh rebuild of GPUI.

The build/runner reject dirty sources, wrong pinned revisions even with the
same tree, changed suite revisions/trees, changed executable bytes, duplicate
backend executables, malformed numeric geometry, hidden projections, and
missing/reordered observations. Manifests retain source identities, compiler
versions, build commands/results, executable hashes, corpus hash, process
stdout/stderr and return codes, explicit mutations, and per-coordinate diffs.
No native windows, GPU pixels, physical input, font baselines, stretch margins,
or general GPUI compatibility are qualified by this bounded diagnostic.
