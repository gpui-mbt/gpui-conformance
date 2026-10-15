# Flex limit clamping and redistribution

Actual shared-scenario executions on macOS 26.5.2 arm64 compare pinned
Zed/GPUI `d9afb21688e04f89d9e94d96d33eb530aef90886` (GPUI 0.2.2, locked
Taffy 0.13.0), gpui.mbt baseline `e7854d297ebd8f64ef332ba17e9893061b930a03`
and separate candidate `b3d668e643e67c7c689ab92941a65c74c2811c6c` (both 0.7.2).
The executed clean suite revision is `48e40200c15f61eb2b4799fe9391ff91aa3b13ef`.
This later documentation/index commit does not relabel the executed revision.

| Corpus | Baseline pass/mismatch | Candidate pass/mismatch | Deliberate control pass/mismatch |
| --- | --- | --- | --- |
| Min/max limits (29) | 9 / 20 | 29 / 0 | 0 / 29 |
| Fractional shrink (17) | preservation checked | 17 / 0 | 0 / 17 |
| Partial-grow gap (17) | preservation checked | 17 / 0 | 0 / 17 |
| Fractional grow (17) | preservation checked | 17 / 0 | 0 / 17 |
| Layout/input boundaries (13) | preservation checked | 13 / 0 | 7 / 6 |
| Original headless slice (8 executed) | preservation checked | 8 / 0 | 6 / 2 |

All **101 measured headless cases pass** after correction. The original corpus
also retains one unsupported IME case and two unverified native placeholders
in both positive and control runs. The separate current-candidate native
build-only run has zero passes and two unverified cases. Historical native
executions are not promoted to this candidate.

The new authored inputs cover maximum-capped growth, minimum-clamped shrink,
row/column axes, both children constrained, unequal shares/bases, zero factors
and maxima, gaps, center/end placement, mixed min/max limits and hypothetical
exact-fit factor selection. Fractional controls retain their initial budget
when a child freezes. No golden output is part of the corpus. The existing
five corpora, pinned dependencies, comparator and tolerance remain unchanged.

For example, two 20-point bases growing in a 100-point row with the first
capped at 30 produce GPUI 30/70 versus baseline MoonBit 30/50. Two 40-point
bases shrinking into 40 with the first minimum 30 produce 30/10 versus 30/20.
The separate engine branch adds iterative main-axis freezing/redistribution;
five of six new unit tests failed before that implementation. Cross-axis
clamping, signed placement and numerical contracts remain unchanged.

Both adapters consume optional two-entry `min_main` and `max_main` arrays;
missing arrays preserve old behavior and null maxima are unbounded. The
contract rejects booleans, nonfinite/negative/oversized limits, reversed ranges
and limit fields on non-layout cases. Extended adapters were first run against
the unchanged baseline to preserve all 72 earlier executed cases and controls.
Candidate runs then repeat every corpus. Controls change only a measured
MoonBit child width by one point; upstream observations stay identical.

## Retained evidence and reproduction

The seven `results/*flex-limits*20261015.json` indexes embed actual manifests
and comparisons, including source/tree/platform/toolchain/process identities
and hashes. They cannot qualify passes without their retained raw artifacts.
Directories `_build/limits-baseline`, `_build/limits-reviewed`,
`_build/limits-reviewed-negative`, `_build/limits-reviewed-{shrink,gap,grow,boundary,original}`
and their `-negative` counterparts contain builds, Mach-O probes, process logs,
unique execution challenges, scenarios and comparisons. Native preparation is
`_build/limits-reviewed-native-build-only`. Preserve entire directories when
sharing evidence; re-running the comparator is a verification, not a new execution.

```sh
python3 run.py --upstream-source /path/to/zed --moonbit-source /path/to/gpui.mbt \
  --candidate-revision b3d668e643e67c7c689ab92941a65c74c2811c6c \
  --scenarios minmax_scenarios.json --output _build/fresh-limits
python3 comparator.py _build/fresh-limits
python3 run.py --upstream-source /path/to/zed --moonbit-source /path/to/gpui.mbt \
  --candidate-revision b3d668e643e67c7c689ab92941a65c74c2811c6c \
  --scenarios minmax_scenarios.json --negative-control --output _build/fresh-limits-negative
```

Local checks pass: 146 relevant native unit tests, 483 full JavaScript tests,
299 all-target static-check tasks, formatting, API information and repository
contracts; 14 portable suite tests plus 61 real-evidence adversarial tests.
The native adversarial tests validate historical retained evidence parsing;
they are not current native execution. Full all-target execution on this Mac
stops on the absent generated Ubuntu/Wayland `text-input-v1-protocol.c`; it is
not counted as a passing check. Linux CI remains a separate publication gate.

## Limits

This is a definite, single-line, two-child headless layout corpus. Three-child
successive freezing has a MoonBit unit test, not GPUI oracle qualification.
Wrapping, margins, intrinsic minimums, binary32 rounding, general CSS flex,
text, physical input and IME remain outside it. The MoonBit native window path
unconditionally calls `makeKeyAndOrderFront` and `activateIgnoringOtherApps`;
its restoration helper runs afterward. Under the no-focus-disruption constraint
no native fixture was launched, so native results remain unverified. No security
setting, permission or running app/service was changed.

Independent exploratory controls also retain a pre-existing device-scale edge
snapping difference. GPUI snaps post-Taffy bounds to physical pixels, so a
fractional 1:2 grow split may report 10.5/29.5 while MoonBit keeps continuous
10.6667/29.3333. The same results occur on baseline and corrected engines and
without min/max limits. Those exploratory cases are not counted in the 101
formal passes; device-scale snapping is the next focused compatibility target.
