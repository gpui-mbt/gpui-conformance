# Explicit point flex-basis (bounded headless slice)

The corpus covers Auto and finite nonnegative point basis independently of each
child's authored main size. Four flow directions × three device scales (1, 1.5,
2) × ten profiles give 120 cases. Profiles cover Auto compatibility, explicit
points, grow, shrink weights, zero, mixed Auto/points, fractional points, wrap,
wrap-reverse, and min/max constraints. Every root and source-order child x/y/w/h
is compared, along with separately observed viewport and scale metadata.

This is not percentage/content basis support or indefinite-parent main-axis
measurement. The production API rejects the latter explicitly. No renderer,
window-system, native desktop, clipping, screenshot or pixel parity is claimed.

## Observed local results (2026-10-21 UTC)

Initial qualification used GPUI 5a5fbe79917971a4d52a96b6ddb04da198a5012e
and local core cbd938aa85c354840a00316db69f4dcbf4308345. The strict
flex_basis_pins.json file is updated to the corresponding public integration
commit for reproduction; the original local result is not relabeled as a new run:

- Actual positive differential: 120/120 pass.
- Separately compiled production resolver mutation: 108/108 expected mismatches;
  all 12 Auto controls still pass. The adapter is unchanged. Only the production
  resolver's successful Points value changes to its Auto fallback; validation
  stays intact. This is not an input-ignoring adapter simulation.
- Root-width corruption control: 120/120 mismatches, no missing cases.
- Original, unmodified legacy corpora: flex justify 72/72, align-self 48/48,
  reverse-flow 68/68. Root/child rectangles are not projected or normalized.
- Python contract tests are synthetic checks, not a substitute for these runs.

Raw process outputs, comparison JSON, executable hashes and manifests are retained
locally in run-positive, run-disabled, run-width-control and run-regressions beside
the checkout. These initial exploratory runs truthfully record an uncommitted
suite snapshot and four unrelated generated core interface files. They do not
claim a clean published suite commit. A subsequent committed-source rerun can be
recorded separately without rewriting the original evidence.

The actual upstream adapter was freshly compiled/linked against read-only,
exact-pin cached GPUI dependencies. Compiler, lockfile and dependency hashes were
verified. This is not a fresh full Cargo dependency build. The disabled build
reused the verified upstream adapter executable and freshly compiled MoonBit.

## Reproduction

Use build_flex_basis.py with --upstream-source, --moonbit-source, --output,
--rust-dependency-cache and --execute-build. The dependency cache must be a prior
compatible build with its complete manifest, lockfile and dependency artifacts.
No full Cargo fallback is performed. Uncommitted source snapshots additionally
require --allow-dirty-worktree and remain labeled dirty in the manifest.

Use run_flex_basis.py with --rust-exe, --moon-exe, --upstream-source,
--moonbit-source, --build-manifest and --output. The default corpus is
flex_basis_scenarios.json. --negative-control requires all cases to mismatch.
For the capability control, create a separate build with --disable-flex-basis
(optionally --reuse-rust-build pointing to the positive build manifest), and run
with --capability-control. A positive build cannot be relabeled as this control.

run_flex_basis_regressions.py accepts the same required runner arguments and uses
the positive binaries with the legacy root request. It preserves all complete
rectangles and strips only extra viewport metadata before original comparators.

Run synthetic contracts with:

    python3 -m unittest discover -s tests -p 'test_flex_basis.py' -v

The workflow runs only these contracts and explicitly makes no runtime parity
claim. Runners fail closed on missing/reordered cases, projected observations,
invalid numeric input, source/pin changes, or executable hash mismatches.
