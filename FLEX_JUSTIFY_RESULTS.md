# Flow-relative main-axis justification (2026-10-21)

Status: published source for a bounded headless comparison; measurements below
were obtained from the identical local source tree before publication. This is not native
window, rendering, physical-input or IME acceptance, and not full CSS flexbox.

## Change and fixed sources

The candidate adds `JustifyContent::flex_start()` / `flex_end()` without changing
physical Start/End or the existing physical-Start default. Both axes, reversed
flow, signed overflow and per-line wrap placement use the same production
resolver. Reverse FlexEnd preserves small near-edge offsets at large magnitudes.

- Actual GPUI reference: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`, tree
  `990fb995914d51a546b20e5cf0382dafc105c299`; upstream source is read-only.
- Candidate: `5126a95b507ca6c33144c92b820d3c35118309fc`, tree
  `d88538f600691d13fbd3a55f57a27e9bdff2b742` (published; byte-identical to reviewed local
  `efdf5c08db35450c2846082df83d6093fec257d6`).
- Baseline: merged core `e6ab2ecbc4e85bdbd4e73c7e58c0ab5beb49128e`, tree
  `9cd3cba8ce52dd323e7adfd2e49d527b8911c290`.
- The suite revision/tree is captured from the checked-out HEAD in every build
  and run manifest. `flex_justify_pins.json` is separate from legacy pins.

The Rust adapter explicitly assigns the GPUI enum; `justify_start/end()` are
physical-edge helpers, not aliases for these new flow-relative modes.

## Measurements

The 72-case corpus covers row/column and both reverse flows, fit, exact-fit,
overflow, oversized singleton, wrap/wrap-reverse, asymmetric padding, gaps and
min/max constrained grow/shrink. Eight physical-edge cases are unchanged controls.
Both implementations execute independently and emit root plus all source-order
child rectangles. All four coordinates are compared at absolute tolerance 1e-5,
with device scale 2. Expected answers are not manufactured by the adapters.

- Candidate: **72 pass / 0 mismatch**.
- Deliberate first-child width +1 negative: **0 pass / 72 mismatch**.
- Compiled production capability-negative: **44 pass / 28 mismatch**. The mutant
  treats both flow-relative variants as physical edges in spacing and reverse
  anchoring. The 44 expected controls are forward flows, physical modes and
  reverse exact-fit lines where the two definitions coincide.
- Previous align-self corpus: **48/48 pass** with the new actual adapters.
- Previous reverse-flow corpus: **68/68 pass** with explicit Auto align-self.
- Baseline probe compilation: **unsupported**; the two public constructors do
  not exist. This is not counted as a passing comparison or a geometry mismatch.
- New portable evidence contracts: **17/17 pass**. These are contract tests, not
  17 additional GPUI execution cases.
- Core: **1367 native tests** and **1110 each JS/Wasm/WasmGC tests** passed;
  all-target deny-warnings check and formatting passed. Field E2E remains gated
  and skipped, not physical-input evidence.

The first capability-negative build failed because its inserted MoonBit match
needed an explicit JustifyContent type; that failure is retained separately and
was not counted as detection of the capability. The corrected mutant was built
and actually executed to obtain the 28 mismatches above.

## Replay and evidence

Use `build_flex_justify.py --help` and `run_flex_justify.py --help`. Build with
`--upstream-source`, `--moonbit-source` and a new `--output` directory. The optional
`--rust-dependency-cache` reuses read-only exact-reference Cargo dependencies;
the reference/compiler/lockfile and all rlib/rmeta/shared/native input hashes are
validated and recorded. Both adapter executables are freshly compiled. The
`--disable-flex-justify` build option produces the explicit capability mutant.

Run with `--rust-exe`, `--moon-exe`, `--upstream-source`, `--moonbit-source`,
`--build-manifest` and a fresh `--output`. `--negative-control` enables width
mutation; `--scenarios` can select a separately retained regression corpus.
The runner rejects mismatched source revisions/trees, dirty inputs, changed
executables, missing/extra/reordered cases, nonfinite coordinates and projected
observations. Each manifest retains executable/source/corpus hashes, commands,
stdout/stderr and full-bounds comparisons. No network tokens are needed to run.

Raw build/run artifacts are currently local at `/tmp/flex-justify-20261021/`.
They are **not a published transferable bundle**; do not claim third-party
revalidation from this result note alone. An independent reviewer also compared 192 bounded supplemental cases with no
differences. Twelve exploratory cases with a root narrower than its horizontal
padding had a root-width-only mismatch, reproduced on the unchanged prior
candidate. That pre-existing root-sizing gap is outside this slice; all child
bounds agreed.

Existing broad-suite baseline failures
and missing historical artifacts have not been fixed by this slice. No upstream
writes, CI reruns, release or physical IME test were performed during the local
measurement run. Source was subsequently published with a public candidate pin;
publication does not turn the retained local measurements into a fresh run.
