# Distributed main-axis spacing — 2026-10-16

## Scope and identities

This adds `space-around` and `space-evenly` to the real headless conformance
suite and to the gpui.mbt library. Both modes were absent from the baseline.
The baseline adapter's existing unknown-mode fallback is start; the recorded
mismatches are missing-capability evidence, not a bug in an existing named mode.

- Read-only Zed/GPUI: `d9afb21688e04f89d9e94d96d33eb530aef90886` (GPUI 0.2.2).
- Engine baseline: `bb3fa1ef552ae22d372cfcea8723e99498aa5fe7`.
- Engine candidate: `1a8a8048cda725252a3b4fe1d84722ffc7ebab5b`.
- Baseline suite: `2958c5145b0c4c7b54f78ed73db0270b03ae985f`
  ([reproducible baseline](https://github.com/gpui-mbt/gpui-conformance/tree/2958c5145b0c4c7b54f78ed73db0270b03ae985f)).
- Linux x86_64, Rust 1.98.1, MoonBit 0.1.20261012 / moonc 0.10.15+943464bfa.
- Each authoritative run records a clean immutable suite SHA and both source
  trees, toolchain versions, process timings and statuses, executable hashes,
  unique execution challenges, input bytes, raw output and comparator output.

Rust calls GPUI's public `.justify_around()` / `.justify_evenly()` builders and
observes the completed GPUI/Taffy layout through debug selectors. MoonBit calls
`JustifyContent::space_around()` / `space_evenly()` in the library and observes
request-layout → prepaint → painted element bounds. Neither adapter emits
expected geometry or reimplements distribution. The Rust source is unchanged.

## Real executions

| Execution | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| Baseline, 24 new cases | 8 | 16 | 0 | 0 |
| Candidate, 24 new cases | 24 | 0 | 0 | 0 |
| Candidate measured-width control | 2 | 22 | 0 | 0 |
| All nine headless corpora | 155 | 0 | 1 | 2 |

For each mode, the 12 original cases cover empty/singleton lists, positive row
and column spacing with a fixed gap, three items, overflowing pairs, an
oversized singleton, exact fit, line-local wrapping, wrap-reverse columns,
capped flex-growth and fractional growth. All observations compare the full
root and child rectangles at the existing 0.0001 logical-pixel tolerance.

In a 108-point row with two 20-point children and gap 8, `space-around` places
children at 15 and 73; `space-evenly` places them at 20 and 68. Baseline start
placement is 0 and 28. A fitting singleton is centered, but an oversized
singleton and overflowing pair fall back to start. Wrapped singleton lines
center independently; spacing is calculated only after per-line sizing.

All cases explicitly request device scale 2. The Rust adapter asserts that its
TestWindow really reports that scale; MoonBit uses its existing opt-in snapping
boundary. This covers fractional distributed placement without silently changing
comparison tolerance or claiming unsnapped doubles equal snapped GPUI geometry.
The native window scale is not being configured or tested.

The one-pixel control changes a measured MoonBit child width after execution.
It detects every one of the 22 nonempty cases; two empty cases have no child
width and remain matching controls. This is comparator sensitivity evidence,
not a behavior claim. All 131 previously executed headless cases still match.

## Reproduction and retained artifacts

Check out the exact engine/source revisions above. The current suite is pinned
to the candidate. Run:

```sh
python3 run.py --upstream-source /path/to/zed --moonbit-source /path/to/gpui.mbt \
  --scenarios distributed_spacing_scenarios.json --output _build/distributed-positive-published
python3 run.py --upstream-source /path/to/zed --moonbit-source /path/to/gpui.mbt \
  --scenarios distributed_spacing_scenarios.json --negative-control \
  --output _build/distributed-negative-published
```

The baseline used the same corpus bytes in the clean baseline suite revision,
with the baseline engine and no candidate API mapping. The authoritative
baseline directory is `_build/distributed-baseline-published`; final focused
candidate and negative directories are the two shown above. The combined run
is `_build/distributed-regression-published`, whose retained `scenarios.json` is the
concatenation of the original, boundary, fractional-grow, gap-budget,
fractional-shrink, min/max, flex-wrap, space-between and new spacing corpora.

[The published index](results/distributed-spacing-linux-x86_64-20261016.json)
contains exact manifests/comparisons and SHA-256 identities. It is not a
substitute for retained executables and raw output. The comparator must reject
an index without the full artifact directory. Failed exploratory runs are
retained locally and are not promoted into these results.

The engine passes `moon fmt --check`, `moon check --target all --deny-warn`, all
75 layout tests on four targets, and full tests (507 each for wasm/wasm-gc/JS,
720 native). The headless adversarial evidence checks also reject missing,
failed, duplicated or tampered execution. Cloud CI is reported on the exact
published PR heads separately; these local results do not imply native-GUI CI.

## Limits

No browser lab UI, native host, OS permissions or physical input is changed.
IME remains unsupported in the headless corpus; native window/GPU placeholders
remain unverified. This is bounded finite definite-size flex coverage, not full
CSS/GPUI compatibility, intrinsic measurement, RTL/reversed main flow, margins,
align-content, text shaping, GPU pixel equivalence or native qualification.
The existing public catalog remains on its earlier separately recorded result
until a dedicated data refresh; this change does not relabel that old evidence.
