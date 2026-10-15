# Fractional flex-shrink results

Actual Rust GPUI 0.2.2 at
`zed-industries/zed@d9afb21688e04f89d9e94d96d33eb530aef90886` and MoonBit 0.7.2
were executed on macOS 26.5.2 / Darwin 25.5.0 arm64 using the unchanged headless
framework adapters, locked Rust 1.98.1 dependency graph and existing pinned
MoonBit 0.10.15 toolchain. The corpus contains independently authored inputs,
not expected positive answers.

Executed clean suite: `8843d05d7e1c84e7bce36c1acbce32ff0bf2ea60`.
Executed clean baseline: `9fb1f278789da554975bfe388dfcf58c3e0e9287`.
Executed clean candidate: `7dcf28f6f1eaaad3ee799d937850a65645bb1952`.
The later suite documentation/index commit does not change executed adapters,
runner, comparator, contracts, pins or any corpus bytes. Existing historical
indexes and all earlier 38 headless cases remain unchanged; the preceding 17-case
gap slice is also retained.

| Real execution | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| Shrink baseline,17 cases |7|10|0|0|
| Shrink candidate |17|0|0|0|
| Shrink negative control |0|17|0|0|
| Earlier gap candidate |17|0|0|0|
| Earlier gap negative |0|17|0|0|
| Earlier grow candidate |17|0|0|0|
| Earlier grow negative |0|17|0|0|
| Earlier boundary candidate |13|0|0|0|
| Earlier boundary negative |7|6|0|0|
| Earlier original candidate |8|0|1|2|
| Earlier original negative |6|2|1|2|
| Current native build-only |0|0|0|2|

The five positive headless corpora total 72 passes with zero mismatches. In the
retained row/column reproductions, two 40-point bases in a 40-point container
with shrink factors 0.25 each now agree at 30/30. The resulting overflow remains
visible; the implementation no longer forces the entire deficit into children.

The correction separates raw-factor totals from scaled `shrink * basis` weights.
Totals below one limit the gap-adjusted negative budget, bounded by the original
deficit. Existing weights determine shares. Unit/above-unit factors, zero
factors, positive/exact free space, signed alignment, and prior positive-grow
gap behavior retain measured controls. The corpus includes unequal/zero bases,
small factors and two gap cases that distinguish partial from full deficits.

## Evidence and checks

Six new `results/fractional-shrink-*.json` / `native-fractional-shrink-*.json`
indexes retain full comparisons and manifests with digests. Their twelve actual
result directories under `_build/` retain compiled executables, independent
challenge tokens, successful build/execution commands/PIDs/timing, platform and
toolchain identities, exact clean source trees, raw stdout/stderr and artifact
hashes. Bare indexes cannot establish a pass. The negative controls actually
execute the MoonBit library and perturb only its measured first-child width.
The independent reference observations remain unchanged.

Fresh engine checks passed 140 relevant native unit tests, 477 full JavaScript
tests, all-target type checks, formatting/interface generation, contracts and
changelog guards. Five regression tests fail before correction. The public
interface remains unchanged. Portable coverage now includes malformed/nonfinite
shrink-factor guards. Historical comparator/native/boundary evidence tests
validate retained real baselines without claiming new native execution.

After configuring the existing documented toolchains, reproduce:

```sh
python3 run.py --upstream-source ../zed-source --moonbit-source ../gpui-shrink-fix \
  --candidate-revision 7dcf28f6f1eaaad3ee799d937850a65645bb1952 \
  --scenarios fractional_shrink_scenarios.json --output _build/shrink-reproduction
```

Repeat with a different output directory and `--negative-control`; exit 1 and 17
mismatches are expected. Run all four earlier corpora separately to retain their
status distinctions. The baseline is a separate clean checkout of 9fb1 above;
`run.py` requires the supplied checkout's HEAD to match its requested revision.

## Remaining limits

Current native preparation successfully built both probes, the runtime library
and foreground guard. It has no execution record: zero native passes and two
unverified cases. No native GUI was launched. The original IME unsupported row
and native placeholders stay visible; prior historical native success is not
reused for this candidate.

The bounded line engine still clamps once and does not implement full flex
freeze/redistribution. Binary64 geometry does not claim arbitrary reference
rounding parity. Native rendering/pixels/window lifecycle, physical input and
IME execution require separately coordinated work. No unrelated mismatch was
hidden or reclassified. Upstream remained read-only; user work/services and
installed software were preserved.
