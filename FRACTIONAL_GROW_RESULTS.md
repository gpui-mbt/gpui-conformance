# Fractional flex-grow — 2026-10-15

This batch adds 17 shared headless layouts using the existing real adapters.
The correction resolves ten of eleven measured baseline differences. One
partial-grow-with-gap difference remains visible. The original eight executed
headless cases and thirteen input/focus/layout boundary cases remain passing.
All results below come from independent pinned Rust GPUI and MoonBit builds
and executions on Darwin arm64, macOS 26.5.2. No native GUI fixture was launched.

## Revisions and branch relationships

- Read-only Zed/GPUI: `d9afb21688e04f89d9e94d96d33eb530aef90886`, GPUI 0.2.2.
- This suite branch depends on PR3 head `feac77230d58cced34b7742d4e72e584e5d238d0`.
- This batch's gpui.mbt baseline is PR75 head `553bff7e35cea7b1d6aeaf20dc22b2348af9b865`, version 0.7.2.
- The separate fix branch depends on that baseline; its candidate is `942aa14a71ceeb5e0d50372bcf1d95e91973c139`.
- All authoritative executions use clean suite `4bdc74df02c66458f992146ccf4f69baa62b6e09`. Subsequent suite changes retain documentation and indexes only.

PR3 and PR75 branches are unchanged by this batch. Original immutable pins
are also unchanged; the two gpui.mbt revisions use explicit candidate mappings
to original baseline pin `f9f59fe074da3858ca82fe1d5fadd84cd17f0438`.

## Measured behavior

The shared inputs exercise row/column partial growth, unequal factors and
bases, a zero factor, totals below one, center/end alignment, gaps, zero bases,
and small positive factors. Controls exercise zero growth, totals equal to or
above one, the maximum bounded factor, an exact fit and negative free space.
No adapter, comparator, input contract or earlier corpus changes were needed.

| New 17-case corpus | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| PR75 baseline | 6 | 11 | 0 | 0 |
| Fractional-grow candidate | 16 | 1 | 0 | 0 |
| Candidate width control | 0 | 17 | 0 | 0 |

For two 20-point bases in a 100-point row and grow factors `[0.25, 0.25]`,
GPUI measures widths `[35, 35]`, while the baseline measures `[50, 50]`.
The candidate measures `[35, 35]`. Factors below a combined one retain some
positive free space for the existing justification step; totals of at least
one keep proportional allocation. The correction preserves shrinking,
one-pass min/max clamping and signed overflow alignment.

The intentional control adds one pixel to a child's measured width after the
actual MoonBit layout path. Every new case mismatches; the sixteen candidate
passes become mismatches and the existing gap difference remains a mismatch.
These controls establish comparator sensitivity, not an implementation defect.

## Remaining gap difference

`grow-partial-with-gap` uses width 108, gap 8, two 20-point bases and factors
`[0.25, 0.25]`. Pinned GPUI measures child widths `[31, 31]` and origins
`[0, 39]`; the candidate measures `[35, 35]` and `[0, 43]`.

The locked Taffy 0.13.0 implementation first includes the gap when computing
initial free space, then subtracts it again in its partial-grow branch. The
MoonBit bounded contract subtracts the gap once before distribution. This
batch preserves that contract and records this separate pinned behavior as
`mismatch`. The case is retained unchanged, and this batch does not claim
complete GPUI or CSS flex parity. The gap-budget unit test explicitly checks
the independent MoonBit contract and is not an oracle-agreement assertion.

## Prior coverage and native preparation

| Corpus / control | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| Previous boundary candidate | 13 | 0 | 0 | 0 |
| Previous boundary width control | 7 | 6 | 0 | 0 |
| Original candidate | 8 | 0 | 1 | 2 |
| Original width control | 6 | 2 | 1 | 2 |
| Native baseline build-only | 0 | 0 | 0 | 2 |
| Native candidate build-only | 0 | 0 | 0 | 2 |

The IME case remains unsupported. Original native placeholders remain
unverified. Both fresh native build-only runs successfully compile Rust and
MoonBit probes, the AppKit test runtime and foreground guard. They contain
no execution records and confer zero native passes on this candidate.
Earlier native execution claims are not carried forward.

## Validation and retained evidence

- Nine new regression/control tests: before the correction, 28 layout tests
  pass and six fail; after it, all 34 layout tests pass.
- Relevant layout/element/primitives/scene packages: 129/129 native and 129/129
  JavaScript. Full-module JavaScript: 466/466. All-target checking with warnings
  denied: 285 tasks pass. Formatting, generated-interface, contract and changelog
  checks pass; public signatures are unchanged.
- Harness checks: 31 original comparator, 19 native-evidence preservation,
  11 boundary-event and 11 portable contract/index checks pass. Portable CI
  cannot establish oracle passes without the retained execution artifacts.
- Existing installed MoonBit SDK/core: `moon 0.1.20261012 (748b63c)`,
  `moonc 0.10.15+943464bfa`; Rust 1.98.1. No toolchain was installed.

Authoritative directories under `_build/`:

- `grow-baseline-reviewed`, `grow-candidate-final`, `grow-negative-final`.
- `prior-boundary-candidate`, `prior-boundary-negative`.
- `prior-original-candidate`, `prior-original-negative`.
- `native-grow-baseline-build-only`, `native-grow-candidate-build-only`.

Each contains selected input bytes, source/platform/toolchain identities,
successful process metadata, build logs, retained executables and raw outputs
where executed, plus `manifest.json` and `comparison.json`. Four new result
indexes embed those actual manifests and comparisons and their hashes; full
directories are needed to verify executed conformance. The initial
`grow-baseline-final` at clean suite `e9123a81dcc1221993edfa6a67b53da372600f30`
has the same 6/11 result; the later reviewed baseline above is authoritative.

The evidence does not establish native runtime/GPU behavior, physical input,
IME, text, accessibility, freeze/redistribution passes, wrapping or all flex
configurations. Independent review and exact-head CI are separate from the
framework observations and never turn the retained gap mismatch into a pass.
