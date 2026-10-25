# Intrinsic-parent point flex-basis qualification

Status: **132/132 actual full-rectangle comparisons pass**, plus all 452
unchanged legacy regression cases. Production point-to-Auto mutation detects
96 expected mismatches while 36 controls pass; root-width corruption detects
132/132 mismatches. This is headless layout qualification only.

The measured source was core `a7b949a13eb04ee8744845245745e83a5c7bfc78`, tree
`15a59cef4d1348b9671005be21fe6a7565c97d54`, and suite
`fbc969cbf969a5adfd1da6969dfbe4baa8a26516`, tree
`64e5f3e319d32498f6e4d4018d2b51e8f8da8aab`. Both were clean during the runs.
This later results-only documentation does not relabel those source identities.

`intrinsic_basis_scenarios.json` adds 132 independently authored layouts: eleven
profiles across four directions and device scales 1, 1.5 and 2. A definite outer
viewport contains a zero-grow, zero-shrink child container whose main dimension
is Auto and cross dimension is 100. Its children have zero grow/shrink, finite
nonnegative point bases or Auto controls. Asymmetric border/padding, distinct
axis gaps, empty Auto dimensions, zero/fractional basis, and min/max bounds are
included. Positive flex factors, wrapping, content and percentage basis are out
of scope. The corpus contains no expected runtime rectangles.

Both adapters use the real nested container and child APIs. The comparator
requires outer, container and every source-order child x/y/width/height at the
existing 1e-5 tolerance. No intrinsic-size formula is implemented in either
adapter. Exact viewport and scale checks remain unchanged. The existing
production point-to-Auto resolver mutation and root-width corruption control
are available; 96 expected mutation failures and 36 controls (24 Auto and 12 min-saturated point cases) were independently authored
expectations, and all were subsequently observed as expected.

The existing `build_flex_basis.py` and `run_flex_basis.py` accept
`--pins intrinsic_basis_pins.json`; the runner additionally accepts
`--scenarios intrinsic_basis_scenarios.json`. Build against a clean exact pin,
using the documented explicit offline/online/cache modes. Any local dirty
preparation requires `--allow-dirty-worktree` and is recorded as such.

Six new synthetic contract tests and 95 related existing contract tests pass.
They are separate from the actual executions below and do not establish
desktop, pixel or GPU behavior.

## Public source identity and reproducibility

The current profiles pin public core commit
`d2bbcd0537645daccc2dd21e9112ecd2d7ad0b9c`, based on public main
`727c7086053cc2c710bf52347156a9be2011a95f`. Its tree is
`24125f4c69431a4675373ba26f7fab7f2af44aeb`, identical to the final local
candidate `8a42a2f4810c28beaccb802429a082e53004cb01`. The public base tree
is `bd96cf73878353c9cd1e9bd495cdd94672a304de`, identical to the historical
local baseline `82a95274964939b172e97b074e0ec13fae99cca7`.

An actual fetched public-commit checkout is used for the new source-bound
requalification, rather than assigning its SHA to a local-commit run. Previous
manifests and the independent diagnostic retain their observed local revisions.
The initial candidate measurements below remain tied to `a7b949a` and the
independent expanded sample remains 95/96, with its retained baseline-existing
fractional-spacing mismatch. Tree equivalence is not a second implementation
commit and publication is not counted as additional development.

## Initial actual oracle observations, 2026-10-25 UTC

The freshly compiled Rust adapter uses GPUI revision
`5a5fbe79917971a4d52a96b6ddb04da198a5012e` with the checked-in Cargo lock and
Rust 1.98.1. All 132 cases returned observed rectangles. The source-bound initial
build is retained under `intrinsic-baseline-build`; the later 132-case direct
upstream run records its own corpus/executable hashes and does not relabel that
build's earlier source identity.

The zero-flex intrinsic contribution is not simply the final basis-sized child:

- Explicit main sizes 40/20/30 and point bases 16/32/24 yield inner intrinsic
  main size 102, while actual child main sizes are 16/32/24.
- Zero bases preserve inner intrinsic main size 90 with zero-size children.
- Bases 60/40/50 with max limits 24/28/22 yield inner intrinsic main size 150,
  while children clamp to 24/28/22.
- Mixed Auto/48/8 with explicit sizes 40/20/30, minimums 0/0/40 and maximums
  24/28/none yields inner intrinsic main size 128 and child sizes 24/28/40.
- The analogous all-Auto control yields inner intrinsic main size 100 and
  children 24/20/40, exposing an existing intrinsic max-limit disagreement.

These are real headless GPUI observations. Container insets/gaps and every
rectangle are retained in raw output; the inner-size descriptions above are
explanations, not comparison projections. Baseline MoonBit compilation and 12
unbounded Auto controls succeeded; non-Auto baseline rejection is expected.

## Candidate differential evidence

The positive and mutation adapters were freshly compiled against the exact
candidate. The upstream adapter executable is reused with verified source,
compiler and executable hashes from the fresh locked Cargo build. Reuse is
explicit in every build manifest; it is not represented as recompiling Rust.

- `intrinsic-positive-run`: 132/132 full outer/container/child bounds pass.
- `intrinsic-mutant-run`: 96/96 expected mismatches; 36/36 controls pass.
  The production Points resolver's success result is replaced with its fallback.
  Both intrinsic contribution and final layout use that resolver. No adapter
  mutation or expected-answer calculation is involved.
- `intrinsic-width-control`: 132/132 root-width corruptions detected.
- `intrinsic-regression-percent`: original 144/144 percent cases pass.
- `intrinsic-regression-point`: original 120/120 point cases pass.
- `intrinsic-regression-legacy`: original justify 72/72, align-self 48/48 and
  reverse-flow 68/68 pass with unchanged corpus bytes and legacy root request.

All raw process output, observations, complete comparisons and manifests remain
under the named local evidence directories. This document is an index, not a
replacement for those files. The reviewed scope excludes actual native windows,
rendering, IME, input and physical-device acceptance.

Build/run manifest SHA-256 values:

- intrinsic-positive-build: `b32bd5f218847a7e6557da452124259d61b4aea24e0024b7c609c9ca0ab6244f`
- intrinsic-mutant-build: `a961211c0be6dffe39c2af025260d7795379a6515f263e6a84c865c66840ba5d`
- intrinsic-regression-build: `6b0f8c7bdef734ce24abbf0fc118e25927b282ceeec257bd43e1e851c93f68fe`
- intrinsic-positive-run: `117fcbd59ea3a75bfaf5006b4e2bfb368f2bb9cc75f64cc62e6f7af2e404a211`
- intrinsic-mutant-run: `7d9ee65435dc3b82a0604bea80c5eff4dc8cd9596b1a07238ce995b01d39cf70`
- intrinsic-width-control: `b666d3385e393f648565374c2ec7722c4cc40a66182690b966ac9a2b12cf6aa5`
- intrinsic-regression-percent: `59bf1a2d175cb84bf4ab127efda3d6a7d9f3e1ab307e3c8de508e9856d77f4a4`
- intrinsic-regression-point: `89dd93aac4146fd001232f0055d3a4425d84c4f81c2d34de4e4e2b4761576957`
- intrinsic-regression-legacy: `f91c62b3f1f504a22d5e09bbc278c929d91eedbb7633ef4203af4699a73fb0c0`


## Retained out-of-profile fractional-spacing counterexample

Independent expanded sampling (96 additional layouts, not the 132-case passing
corpus) found one mismatch: `review-row_reverse-1.5-3`, row-reverse,
space-around justification, scale 1.5. The second child's x is
54.66666793823242 in GPUI and 54 in MoonBit; the intrinsic container extent and
all other compared coordinates agree within the unchanged tolerance.

The same disagreement reproduces in the pre-feature core `82a9527` when the
parent is given the equivalent definite width 142/1.5 and height 100. This is a
pre-existing distributed-spacing rounding limitation, not fixed by this slice.
It is retained in `diagnostics/intrinsic_point_fractional_spacing.json`, with
both nested and baseline definite observations and hashes of the independent
raw evidence. Do not describe the additional 96 cases as all passing, add this
case to the positive corpus as a pass, or widen tolerance to hide it. The
qualified intrinsic corpus uses start justification; it does not establish
fractional distributed-justification parity.
