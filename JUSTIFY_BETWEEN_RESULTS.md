# Flex `space-between` capability batch — 2026-10-15

This batch adds one missing main-axis justification mode to the bounded flex
engine and compares it with real GPUI layout. The baseline had no
`space-between` mode, so the positive-space differences are a capability
addition, not regressions in an existing MoonBit mode. The Rust oracle invokes
GPUI's public `.justify_between()` style builder through an independent
headless `Render` adapter; no expected coordinates are substituted for an
oracle run.

## Revisions and execution

- Read-only Zed/GPUI: `d9afb21688e04f89d9e94d96d33eb530aef90886`, GPUI 0.2.2.
- gpui.mbt baseline: `01818aa4e96fc21d1676f747a6b23d91445648a1`.
- gpui.mbt candidate: `67b31732900c00cc11f068f13ca0fbceca5014a5`.
- The candidate adapter/schema suite is committed and clean; each retained
  manifest binds its exact suite revision. The baseline uses a clean suite
  adapter commit that deliberately leaves the unavailable mode at start.
- Linux x86_64; Rust 1.98.1 and MoonBit `0.1.20261012`.
- The Rust and MoonBit adapters independently build and execute their layout
  paths. Geometry is compared as logical rectangles.

## Cases and evidence

The six new shared cases cover empty and singleton item lists; positive free
space in rows and columns with a nonzero fixed gap; negative overflow; and
four children split into two wrapped lines, checking line-local distribution.
The scenario bytes are `justify_between_scenarios.json`.

| Execution | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| Existing engine baseline | 3 | 3 | 0 | 0 |
| `space-between` candidate | 6 | 0 | 0 | 0 |
| Candidate one-pixel width control | 1 | 5 | 0 | 0 |

At the baseline, GPUI's second child starts at 80 points in both the 100-point
row and column, while MoonBit's default start placement puts it at 28. In the
55-point wrapped row, GPUI starts the second child at 35 on each line; the
baseline starts both at 28. The empty and singleton controls already match.
The overflowing pair matches at origins 0 and 68 in both implementations,
confirming GPUI's start fallback when no positive free space remains.

The candidate distributes positive free space over the inter-item spaces and
recomputes that amount independently per wrapped line. It uses no division for
zero/one-item cases, and a zero or negative remainder keeps the observed start
fallback. Raw geometry and scale-specific comparisons/tolerances are unchanged.
The one-pixel control perturbs a measured MoonBit child width after layout; all
five nonempty cases mismatch, while the empty case has no child coordinate to
perturb. It confirms comparator sensitivity, not candidate behavior.

The pre-existing headless corpora were rerun against the candidate: the 11-case
original corpus retains 8 passes, one unsupported IME case, and two unverified
native cases; boundary 13/13, wrap 14/14, min/max 29/29, fractional grow 17/17,
fractional shrink 17/17, and gap-budget 17/17 pass. In total, all previous 115
executed headless cases pass, with the original unsupported/unverified entries
unchanged. The engine's full MoonBit test suite passes 503/503 tests.

## Retained artifacts and limits

The authoritative clean executions are `_build/justify-between-final-baseline-run4`,
`_build/justify-between-final-baseline-negative-run4`,
`_build/justify-between-final-candidate-run2`,
`_build/justify-between-final-candidate-negative-run2`, and all seven
`_build/justify-between-final-regression2-*` directories. Each directory
contains selected scenario bytes, source/platform/toolchain identities,
process/build logs, executable hashes, raw outputs, `manifest.json`, and
`comparison.json`; preserve the full directories to audit the results. The
manifests identify the exact clean suite and framework commits for each
execution. Earlier retry directories are not authoritative evidence.
Run `python3 comparator.py <directory>` to validate hashes and recompute a
comparison. The six-case oracle establishes only this bounded logical-layout
subset. It does not establish native rendering, all justification modes,
all flex configurations, pixel equivalence, physical input, or IME behavior.
