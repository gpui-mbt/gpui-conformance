# Partial-grow gap-budget results

Executed on macOS 26.5.2 / Darwin 25.5.0 arm64. The reference is actual Rust
GPUI 0.2.2 at `zed-industries/zed@d9afb21688e04f89d9e94d96d33eb530aef90886`,
using the locked Cargo graph (including Taffy 0.13.0), Rust 1.98.1 and headless
`VisualTestContext` layout. MoonBit 0.7.2 runs its real element request-layout
path using the existing pinned 0.10.15 toolchain. Both adapters and all earlier
corpora are unchanged.

Executed suite: `3d28d4f6b8db42fe88862a6b891bb726e97789c1` (clean).
Baseline: `1c34285b5520f933d7644ab23aef678b04072532` (clean merged main).
Candidate: `5db9dbee4d688141ac6e47097af1230191e07db4` (clean separate branch).
Engine publication head `9fb1f278789da554975bfe388dfcf58c3e0e9287` adds
only a public docstring clarification after the executed candidate. The
subsequent suite documentation/index commit does not change executed code or
scenario bytes. The immutable `pins.json` first-slice baseline is preserved;
explicit candidate revisions are recorded in every new manifest.

| Real execution | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| Gap baseline,17 cases |6|11|0|0|
| Gap candidate |17|0|0|0|
| Gap negative control |0|17|0|0|
| Earlier grow candidate |17|0|0|0|
| Earlier grow negative |0|17|0|0|
| Earlier boundary candidate |13|0|0|0|
| Earlier boundary negative |7|6|0|0|
| Earlier original candidate |8|0|1|2|
| Earlier original negative |6|2|1|2|
| Current native build-only |0|0|0|2|

The original 38 measured headless cases and 17 new gap cases total 55 passes.
The retained `grow-partial-with-gap` now agrees: a 108-point row with 8-point
gap, 20-point bases and grow factors 0.25 each produces 31-point children in
both implementations. The independent correction matches the observed signed
partial-grow budget. The gap can reduce bases on a growing line; the matrix
retains zero and negative distribution budgets rather than clamping them away.
This is pinned compatibility behavior, not a general CSS specification claim.

## Evidence and reproduction

The five new `results/gap-budget-*.json` / `native-gap-budget-*.json` indexes
retain complete manifests, comparisons and their digests. Each listed directory
under `_build/` retains actual compiled probes, build/stdout/stderr logs, unique
process challenges, source trees, versions/platform, commands/PIDs and timing.
Indexes without their artifacts cannot establish any pass. All 72 harness
checks passed using the retained real historical baselines for adversarial
comparator/native/boundary evidence tests and current portable contracts.
Historical native execution is used only to validate the evidence parser;
it does not establish execution of this candidate.

With the documented toolchains/environment configured, reproduce a fresh run:

```sh
python3 run.py --upstream-source ../zed-source --moonbit-source ../gpui-gap-fix \
  --candidate-revision 9fb1f278789da554975bfe388dfcf58c3e0e9287 \
  --scenarios gap_budget_scenarios.json --output _build/gap-reproduction
```

Repeat with a new output directory and `--negative-control`; its exit 1 and
17 mismatches are expected. Run the three earlier corpora separately to keep
their unsupported/unverified rows visible. The actual negative controls modify
only the measured first-child width by one after invoking the MoonBit library.
Their independently executed upstream observations remain unchanged.

Native preparation successfully built the two probes, runtime library and
foreground guard. It contains no execution record, so both native cases remain
unverified with zero passes. No native GUI was launched in this batch. Native
pixels/input/window lifecycle require separately coordinated execution.

## Scope and remaining limits

The engine regression checks passed 133 relevant native unit tests, 470 full
JavaScript tests, 299 all-target check tasks, formatting/interface generation,
contract/provenance checks and changelog guards. Three new/revised tests fail
before the source correction. No public interface change is introduced.

This slice changes only positive initial free space with a grow total below
one. Shrink and one-pass min/max clamping retain their existing bounded
behavior. The separately observed fractional-shrink row/column mismatches are
not claimed fixed here. Full CSS flex/freeze behavior, arbitrary floating-point
rounding parity, IME, physical input and native rendering remain outside these
headless results. Upstream stayed read-only; user work and services were kept.
