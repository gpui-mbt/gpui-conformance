# Input, focus and layout boundaries — 2026-10-15

This batch adds 13 independently authored shared scenarios while preserving the
original eight headless cases, the two native cases and their negative controls.
New observations come from actual independent Rust GPUI and MoonBit executions
on Darwin arm64, macOS 26.5.2. No native GUI fixture was launched in this batch.

## Exact revisions

- Upstream Zed/GPUI: `d9afb21688e04f89d9e94d96d33eb530aef90886` (GPUI 0.2.2), read-only.
- Batch baseline main: `2badfaf54482d4fe11d64a39b2c247350cc01bea` (gpui.mbt 0.7.2), including the separately completed X11 readiness fix.
- Layout candidate: `553bff7e35cea7b1d6aeaf20dc22b2348af9b865` (0.7.2).
- Clean executed suite: `f1219ea0d530a99f0c22fa8a40471dbe5dba3c09`.

Original immutable pins remain unchanged for historical reproducibility. Both
batch revisions use explicit `--candidate-revision` mapping to original pin
`f9f59fe0`. “Baseline” here means current main before the separate layout fix;
it does not relabel the first-slice baseline.

## Measured cases

| Group | Actual observation |
| --- | --- |
| Six layout boundaries/controls | GPUI Render/Taffy completed bounds versus MoonBit layout/prepaint/paint bounds: row/column, overflowing center/end alignment, exact fit and exhausted gap budget |
| Three pointer routes | Mouse-down listeners versus input-dispatch callbacks: ordered capture/bubble IDs, root-capture stop, child-bubble stop, repeated events and an outside point |
| Four focus/key routes | Real focus handles, focus/blur and key-down/key-up listeners versus tree focus/clear and dispatch callbacks: focused IDs and ordered phases across switches, blur and stops |

Adapters emit no expected trace. Root/children have logical IDs 1, 2 and 3.
Every callback is retained in order. Null focus and empty no-hit/blur steps are
measured; a completely empty route/focus case is unverified.

| New corpus | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| Current-main baseline | 9 | 4 | 0 | 0 |
| Layout candidate | 13 | 0 | 0 | 0 |
| Candidate width-perturbation control | 7 | 6 | 0 | 0 |

The four real differences are confined to child origins:

| Fixture | Upstream | Baseline MoonBit |
| --- | --- | --- |
| Main center, overflowing row | x = −20, 20 | x = 0, 40 |
| Main end, overflowing column | y = −40, 0 | y = 0, 40 |
| Cross center, overflowing row | y = −10, −20 | y = 0, 0 |
| Cross end, overflowing column | x = −20, −40 | x = 0, 0 |

The separate gpui.mbt fix uses signed remaining space for center/end placement
and reports leading main-axis overflow. Start/stretch, size resolution, input
dispatch and public signatures are unchanged. The seven new input/focus cases
already match current main and remain passing.

The executed control adds one pixel to a child's measured width after the real
MoonBit library path. All six layout cases mismatch at
`observation.bounds[1][2]`; seven routing/focus cases still pass. This is an
intentional comparator control, not an implementation defect.

## Preservation and validation

| Original corpus | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| Current main | 8 | 0 | 1 | 2 |
| Layout candidate | 8 | 0 | 1 | 2 |
| Candidate width control | 6 | 2 | 1 | 2 |

Native placeholders remain unverified; IME remains unsupported. Current-main
and candidate native **build-only** runs compile both probes, AppKit runtime
and foreground guard, reporting zero passes/two unverified. They do not extend
earlier native claims to this candidate. Native preparation selects its own
adapter directly, preventing headless routing files from entering that fixture.

- 11 adversarial boundary checks on the fresh baseline detect altered focus,
  lost callbacks, altered phases, empty traces, short sequences, invalid IDs
  and malformed focus fields.
- 31 original comparator checks, 19 native-evidence preservation checks and
  10 portable contract/index/preparation checks pass.
- Relevant gpui.mbt layout/element/primitives/scene tests pass 120/120 on native
  and 120/120 on JavaScript; full JavaScript tests pass 457/457. All-target
  checking with warnings denied passes.
- Before the fix, targeted regressions fail as expected (19 passed, 5 failed).
  Nine added regression/control tests cover signed origins, both axes and
  directions, exact fit, insets, start/stretch, fractional tolerance and overflow.
  Contracts, changelog guards, formatting and generated-interface checks pass.

Machine-readable indexes in `results/` are
`boundary-macos-arm64-20261015.json`, `regression-macos-arm64-20261015.json`
and `native-build-only-macos-arm64-20261015.json`. Complete `_build/` result
directories retain executables, process records, raw stdout/stderr and all
build/runtime/guard artifacts. Indexes alone cannot establish execution.

## Reproduce

Use compatible installed SDKs (this run used October moonc 0.10.15, Rust
1.98.1, Python 3.12+) and an isolated offline Cargo cache:

```sh
python3 run.py --upstream-source /path/to/zed \
  --moonbit-source /path/to/current-main \
  --candidate-revision 2badfaf54482d4fe11d64a39b2c247350cc01bea \
  --scenarios boundary_scenarios.json --output _build/boundary-baseline
python3 run.py --upstream-source /path/to/zed \
  --moonbit-source /path/to/layout-fix \
  --candidate-revision 553bff7e35cea7b1d6aeaf20dc22b2348af9b865 \
  --scenarios boundary_scenarios.json --output _build/boundary-candidate
python3 tests/test_boundary_evidence.py --evidence _build/boundary-baseline
```

Add `--negative-control` for width perturbation. Omit `--scenarios` for the
unchanged original corpus. `run_native.py --build-only` opens no windows.

This does not establish physical input, native pixel parity for the new fix,
IME, focus-owner restoration after removal, full CSS flex, text rendering or
general GPUI compatibility. Historical native evidence retains its original
revision/scope. Existing applications and unrelated worktrees were preserved;
no installation or security-setting change was made.
