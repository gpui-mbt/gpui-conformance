# Cross-axis min/max conformance

## Scope and result

This batch adds ten original layouts to `minmax_scenarios.json`, bringing that
corpus from 29 to 39 cases. The existing contracts and both adapters already
accepted `min_cross` and `max_cross`; this was missing executed coverage, not a
reported product defect. No `gpui.mbt` source was changed because the measured
behavior matched pinned GPUI.

The ten cases cover:

- Row and column auto cross dimensions stretched up to a per-child maximum
- Explicit cross-axis dimensions clamped by max or min, with center/end alignment
- A zero maximum contrasted with a null (unbounded) maximum
- A minimum that exceeds the parent cross extent
- An uncapped auto/stretch control
- Wrapped line-local stretch maxima and wrap-reverse min/max with center/end alignment

Focused execution against the actual pinned Rust GPUI and current gpui.mbt main
recorded **39 pass, 0 mismatch, 0 unsupported, 0 unverified**. The deliberate
one-pixel MoonBit width perturbation recorded **0 pass, 39 mismatch**; each of
the ten new cases detected that negative control.

As a preservation check, the eight existing corpus files plus the ten added
cases were executed together: **131 pass, 0 mismatch, 1 unsupported, 2
unverified**. The existing IME composition row remains unsupported and the
native-window/native-GPU rows remain unverified. The combined negative-control
run recorded **16 pass, 115 mismatch, 1 unsupported, 2 unverified**. This
negative control is expected and is not a candidate regression.

## Pinned identities

- Rust oracle: `zed-industries/zed@d9afb21688e04f89d9e94d96d33eb530aef90886`,
  GPUI 0.2.2, source tree `eb865ba992a7d5f47e64121bae7ed87092021d5e`
- MoonBit candidate: `gpui-mbt/gpui.mbt@bb3fa1ef552ae22d372cfcea8723e99498aa5fe7`,
  version 0.7.2, source tree `b034cf8bb867c716fc84e4b1ce56c03ddb4bd36b`
- Conformance suite before the slice: public main `f84caf55f12a63003b8fb7cf9d3e5a9f57706e50`
- Suite source used for the clean runs: local commit
  `85b623ca622b3d0c9947c154c8ef5496a1383a2f`, tree
  `599542819e9ea82794adbe9a7e84de8b80019607`
- Host: Linux x86_64
- Rust: `rustc 1.98.1 (48a229cea 2026-09-01)`
- MoonBit: `moon 0.1.20261012 (748b63c 2026-10-12)`; flags
  `rr_moon_mod,rr_moon_pkg`
- Focused input SHA-256:
  `2dacbf64d3b62392c55d8e9f90b7827c737bea5bf23e5f52a8b9e8bc12a9b7da`
- Combined 134-case input SHA-256:
  `beaef1fc0db04fe5f914e8bab70a63b9a22f9cb988f90ce97d102957de2c3bc6`

The result index `results/cross-axis-limits-linux-x86_64-20261015.json` embeds
the focused run manifests and comparisons and the full-combination manifests,
comparisons, and artifact digests. Exact output paths in the index are relative
to the conformance worktree. The compiled probes, process logs, and scenario
files are retained in the local `_build/cross-axis-focused-positive`,
`_build/cross-axis-focused-negative`, `_build/cross-axis-final-positive`, and
`_build/cross-axis-final-negative` directories; these ignored execution outputs
are not committed as 30+ MiB binaries. Without those raw local files, the
published index alone cannot qualify execution, as enforced by the portable
harness contract.

## Checks

- Focused `run.py`: 39 pass; negative control: 39 mismatch, all ten new cases
  detected
- Full combined `run.py`: 131 pass, 0 mismatch, 1 unsupported, 2 unverified;
  full negative control: 16 pass, 115 mismatch, 1 unsupported, 2 unverified
- `test_portable_contracts.py`: 20 passed
- `test_visual_contracts.py`: 13 passed
- `test_fixture_contracts.py`: 8 passed
- `test_observer_contracts.py`: 17 passed
- `test_ax_regression.py`: 11 passed
- Comparator evidence tests on the full combined positive and negative runs: 38 passed each; focused minmax comparisons were verified directly against their retained outputs (the generic adversarial test requires the original first-slice corpus as a prefix)
- `cargo +1.98.1 fmt --check --manifest-path adapters/rust/Cargo.toml`: passed
- `git diff --check`: passed

An unscoped `python3 -m unittest discover -s tests -p 'test_*.py'` was also
attempted once; it is not a repository CI entrypoint and fails setup for
195 evidence-dependent tests because no default native-evidence directory was
supplied. That invocation is not counted as a passing suite. The documented CI
entrypoints and the headless comparator evidence tests above passed.
