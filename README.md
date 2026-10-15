# GPUI Conformance Suite

Execute shared scenarios against pinned Rust GPUI and gpui.mbt, retaining the
programs and raw process output that produced each comparison. The headless
runner creates no native windows. The separate native runner uses isolated,
self-closing hidden AppKit/Metal accessory fixtures on an Apple Silicon Mac.

Pins: Zed/GPUI `d9afb21688e04f89d9e94d96d33eb530aef90886` (GPUI 0.2.2) and
gpui.mbt `bb3fa1ef552ae22d372cfcea8723e99498aa5fe7` (current main). See [pins.json](pins.json).

## First coverage slice

| Scenarios | Execution and observation |
| --- | --- |
| Fixed row with gap; proportional shrink | GPUI Render → Taffy → drawn debug bounds; MoonBit request-layout → prepaint → paint snapshot → element bounds |
| Painted opaque rectangle scene | GPUI `Window::painted_quads` from the completed frame; MoonBit painted scene snapshot items, comparing logical bounds and RGBA8 colors |
| Interior, far-edge and zero-extent pointer samples | GPUI test-platform mouse dispatch → child listeners; MoonBit input dispatch → element target |
| Plain/modified/repeated key down | GPUI focused element listener; MoonBit focused capture/bubble dispatch callback |
| Nested positive rectangle clips | GPUI window content-mask stack during canvas prepaint; MoonBit scene snapshot clip chain intersected by its geometry API |
| Native window create/resize/remove | Separate native runner observes logical content size and handle liveness in both AppKit backends |
| Native GPU pixels | Separate native runner compares three requested pixel samples, bound to the complete retained RGBA8 readbacks |
| IME composition | Outside this bounded slice: **unsupported** |

Headless layout/paint preparation and clip geometry do not establish pixel
rendering, Metal correctness, AppKit lifecycle, physical input, accessibility,
text shaping, or general GPUI compatibility. The root's implicit pointer target
is normalized to null: pointer cases compare only the two child listeners.
The original trees/data are authored here; no upstream test fixture is copied.

## Run

Requires Python 3.12+, Rust **1.98.1**, MoonBit, and Xcode command-line tools.
The measured local MoonBit version is recorded in each manifest. The local run
used `moon 0.1.20260920 (914d7da)` and the matching installed core library.
The publication candidate on the updated gpui.mbt main uses the already
installed `moon 0.1.20261012 (748b63c)`, `moonc 0.10.15+943464bfa` and matching
core. See [PUBLICATION_RESULTS.md](PUBLICATION_RESULTS.md) for that separate run.

Clone the repositories into separate directories; check out the exact SHAs in
[pins.json](pins.json). Keep the upstream checkout read-only after checkout. The
runner checks both revisions and tracked cleanliness before and after execution.
It builds Rust outside upstream and extracts tracked MoonBit files into a fresh
build directory, adding only the suite's probe package there.

```sh
python3 run.py --upstream-source /path/to/zed --moonbit-source /path/to/gpui.mbt \
  --output _build/baseline
python3 comparator.py _build/baseline
python3 tests/test_comparator.py --evidence _build/baseline
python3 run.py --upstream-source /path/to/zed --moonbit-source /path/to/gpui.mbt \
  --negative-control --output _build/negative
```

Set `CARGO_HOME` to an isolated cache to keep downloads separate from other
work. Cargo runs offline and locked by default. For a cold cache, use `--online`
with normal network permission. The checked-in lockfile is resolved from the
pinned upstream lockfile; it preserves upstream's locked yanked `spin 0.10.0`
dependency. No dependency substitution is made. Rust probes are built in debug
mode because GPUI debug selectors are unavailable in release mode.

### Native AppKit/Metal slice

Run `python3 run_native.py --moonbit-source /path/to/background-host-engine
--candidate-revision FULL_SHA --output _build/native`, using a committed engine
with `Host::start_background()` (see [the qualified candidate](NONACTIVATING_NATIVE_RESULTS.md)).
Add `--build-only` to compile both probes and the MoonBit
test-hook dylib without launching anything; this correctly reports unverified.
The same source/candidate options apply. Both builds finish before any launch,
and probes run sequentially with 15-second process deadlines. Only owned child
processes can be terminated. Both probes select accessory policy before creating
one hidden, unfocused window. Own-process telemetry binds the execution PID and
window ID to hidden, inactive, non-key state throughout the lifecycle. The
runner never activates or restores another application. Older engine libraries
reject the distinct background-start operation; they cannot fall back to an
activating path. See [the fixture protocol](NONACTIVATING_NATIVE_FIXTURES.md).

[native_scenarios.json](native_scenarios.json) specifies one window followed by
one pixel case with the same initial viewport: 256×192 logical pixels, resize
to 320×224, a black background and an opaque red 64×48 rectangle at (32,32).
Both adapters consume those scene inputs. Pixel positions are logical; scale
and physical readback dimensions come from each backend. The comparison covers
three interior samples, not every pixel or anti-aliased edges. Full buffers are
retained and the comparator derives each sample from those bytes. Window origin
is normalized to content coordinates (0,0); desktop position, close-request
events, user interaction and physical input are outside this native slice.

Rust uses `gpui_platform::application().with_windowing(WindowingRequest::Headless)`
and native `Window::render_to_image`,
which renders its completed scene through the native Metal renderer into an
owned drawable without presenting. The MoonBit AppKit host presents its own
Metal drawable in its hidden background-host window and reads the completed
frame through `GPUI_TESTING`. The
runtime-shader feature is enabled for upstream's own Metal shader compilation.
Add `--negative-control` to actually render the MoonBit rectangle blue while
upstream renders the shared red input. A real GPU color mismatch must result.
No expected pixel answers are emitted by the probes.

Run `python3 tests/test_native_evidence.py --evidence _build/native` to check
missing/short readbacks, dishonest samples, missing/tampered dylibs, bad native
identities, malformed scenarios, and owned timeout cleanup without GUI launches.
Historical headless outputs keep their native placeholders unverified; native
qualification is a separate corpus and never overwrites earlier evidence.
Fresh native executions at merged suite `316a62d3` and merged gpui.mbt
`24bf42ca` are recorded in [MERGED_NATIVE_RESULTS.md](MERGED_NATIVE_RESULTS.md).
The separately qualified nonactivating candidate and real GPU divergence control
are recorded in [NONACTIVATING_NATIVE_RESULTS.md](NONACTIVATING_NATIVE_RESULTS.md).
An explicit bounded `--observe-visible` mode now qualifies owned WindowServer
identity and ready/ack lifecycle; see [its actual results](OBSERVER_READY_RESULTS.md).
External AX window matching, semantic behavior, physical input and screenshot
content binding remain unverified.

Optional `--ax-diagnostics` reads only the owned fixture's local accessibility
objects and the already bound external candidates' attribute names. Add
`--bundle-fixtures` to stage private accessory `.app` fixtures with measured
runtime bundle identities; both flags require explicit `--observe-visible`.
The exact retained executable is launched as an owned child, with the same
deadlines and strict match. See [the measured diagnostic results](AX_DIAGNOSTIC_RESULTS.md)
and the separately evidenced correction for existing Accessory policy.
The [follow-up investigation](AX_PROJECTION_INVESTIGATION.md) separates recorded
facts from unresolved causes and adds local unignored-element, indexed-query
and current-session diagnostics. These fields do not qualify AX association.

### Portable CI checks

GitHub Actions runs `python3 -m unittest discover -s tests -p
'test_portable_contracts.py'` on a clean checkout. These checks validate the
shared corpora, numeric comparison rules and published index consistency, and
prove that indexes without retained execution artifacts produce zero passes.
They do not rerun either implementation or qualify native conformance. The
real-evidence adversarial commands above require the entire retained result
directories and remain a separate validation step.

### Linux headless oracle run

The retained Linux x86_64 run on gpui.mbt `71da96d9` measured 101 headless
passes with no mismatches. IME remains unsupported and native window/GPU rows
remain unverified; this is not Linux native-GUI qualification. Exact pins,
summary, evidence-checker commands and reproduction command are recorded in
[the Linux results note](LINUX_HEADLESS_RESULTS_20261015.md).

For a separately committed gpui.mbt fix, pass its checkout and full immutable
SHA with `--candidate-revision`. The result retains both candidate and baseline
revisions; the suite pin remains the baseline. Existing output directories are
rejected so prior evidence cannot be overwritten.

## Input, focus and layout boundary batch

[boundary_scenarios.json](boundary_scenarios.json) adds 13 separate headless
cases: six layout boundary/control cases, three pointer capture/bubble routes
and propagation stops, and four focus-switch/blur/key-up/propagation cases.
The original and native corpora remain unchanged. Use `run.py --scenarios
boundary_scenarios.json` with an explicit `--candidate-revision` for this batch.
See [BOUNDARY_RESULTS.md](BOUNDARY_RESULTS.md) for exact before/after revisions,
fresh execution evidence, regression checks and limitations.

The bounded route/focus contract retains every listener callback in execution
order, including its element ID and phase. Empty no-hit/blur steps are allowed
inside a case containing observed callbacks; an entirely empty case cannot
establish a pass. Portable CI checks contracts/indexes without framework execution.

## Fractional flex-grow batch

[fractional_grow_scenarios.json](fractional_grow_scenarios.json) adds 17 layout
cases using the existing adapters: fractional and zero factors, totals below,
equal to and above one, row/column placement, center/end leftovers, unequal
bases, gaps and small positive factors. Run it with `run.py --scenarios
fractional_grow_scenarios.json` and an explicit candidate revision.

That batch baseline has six passes/eleven mismatches; its separately committed
fix has sixteen passes/one mismatch. The partial-grow-with-gap case was retained
as an explicit difference against the pinned dependency's gap accounting. It is
neither deleted nor classified as unsupported. All prior 21 executed headless
cases and their controls are preserved. See
[FRACTIONAL_GROW_RESULTS.md](FRACTIONAL_GROW_RESULTS.md) for exact revisions,
retained real executions, the known difference and native limits.

## Partial-grow gap-budget batch

[gap_budget_scenarios.json](gap_budget_scenarios.json) adds 17 shared layouts
for signed partial-grow budgets, row/column placement, center/end offsets,
zero/asymmetric factors and unchanged controls. The baseline records six
passes/eleven mismatches; the correction records 17 passes/zero mismatches.
Its deliberate width control records zero passes/17 mismatches. All earlier
38 measured headless cases now pass, including `grow-partial-with-gap`;
the original unsupported IME and unverified native placeholders remain visible.
See [GAP_BUDGET_RESULTS.md](GAP_BUDGET_RESULTS.md) for immutable revisions,
raw-evidence indexes, reproduction commands and remaining coverage limits.

## Fractional flex-shrink batch

[fractional_shrink_scenarios.json](fractional_shrink_scenarios.json) adds 17
shared layouts for raw shrink totals below/equal to/above one, weighted shares,
zero/unequal bases, signed overflow placement and gap-budget bounds. Actual
baseline execution records seven passes/ten mismatches; the separate shrink
correction records 17 passes/zero mismatches. Its deliberate width control
records zero passes/17 mismatches. All 55 earlier measured headless cases pass;
the original unsupported IME and unverified native rows remain visible. See
[FRACTIONAL_SHRINK_RESULTS.md](FRACTIONAL_SHRINK_RESULTS.md) for exact identities,
raw-evidence indexes and limitations.

## Flex min/max redistribution batch

[minmax_scenarios.json](minmax_scenarios.json) adds 29 shared layouts covering
capped growth, minimum-clamped shrink, hypothetical factor selection and
fractional controls. Baseline execution records nine passes/twenty mismatches;
the separate engine correction records 29 passes/zero mismatches, and its
width control records zero passes/29 mismatches. All 72 previous measured
headless cases pass. Native preparation remains build-only/unverified under
the no-focus-disruption constraint. See [FLEX_LIMIT_RESULTS.md](FLEX_LIMIT_RESULTS.md)
for exact identities, evidence indexes, reproduction and coverage limits.

## Cross-axis min/max coverage

The min/max corpus now has 39 shared layouts, including ten cases for auto cross
sizes stretched under row/column maxima, explicit cross-axis clamping, zero
versus unbounded maxima, minimum overflow, wrapped line-local caps,
wrap-reverse alignment, and an uncapped control. This was a verified coverage
gap, not an observed defect: both adapters and the engine already exposed the
necessary cross-axis limits.

Pinned Rust GPUI and the current gpui.mbt main match all 39 min/max cases. A
second run combined all eight registered corpora and preserved 131 executed
headless passes, zero mismatches, one unsupported IME row, and two unverified
native rows. The deliberate width perturbation mismatched every focused min/max
case, including all ten new cases. No engine code changed. Exact source/toolchain
identities, scenario hashes, comparison results, and retained local artifact
paths are in [CROSS_AXIS_LIMIT_RESULTS.md](CROSS_AXIS_LIMIT_RESULTS.md) and
[the result index](results/cross-axis-limits-linux-x86_64-20261015.json).

## Flex `space-between` capability batch

[justify_between_scenarios.json](justify_between_scenarios.json) adds six
headless layouts for empty/singleton lists, positive row/column spacing,
negative-overflow fallback, and wrapped line-local distribution. The baseline
lacked this justification mode, so this is a capability addition, not a bug in
an existing mode. Its actual GPUI baseline records three passes/three
mismatches; the candidate records six passes/zero mismatches, and a one-pixel
negative control is detected on all five nonempty cases. All earlier 115
executed headless cases remain passing, with one unsupported IME and two
unverified native placeholders unchanged. See
[JUSTIFY_BETWEEN_RESULTS.md](JUSTIFY_BETWEEN_RESULTS.md) for exact revisions,
Linux execution evidence, regression counts and coverage limits.

## Evaluate retained native images with vlmkit

`prepare_visual.py`, `evaluate_native_images.py` and `verify_native_images.py`
provide a separate deterministic PNG diagnostic over verified retained RGBA8
readbacks. Whole-frame bytes, dimensions and scale remain authoritative.
The real retained negative is detected even when vlmkit exits normally; a
permissive per-pixel threshold cannot override an exact mismatch. Build-only
native evidence remains unverified. This analysis opens no windows and does
not qualify new native execution or physical input. See
[RETAINED_IMAGE_RESULTS.md](RETAINED_IMAGE_RESULTS.md) for exact versions,
reproduction, controls and [observer prerequisites](NATIVE_OBSERVER_PREREQUISITES.md).

## Result contract

`comparison.json` has one row per shared scenario with `pass`, `mismatch`,
`unsupported` or `unverified`, plus exact mismatching field paths and values.
Numeric geometry uses an absolute tolerance of **0.0001 logical pixels**.
Strings, booleans, IDs, list sizes and object field sets compare exactly.

A pass requires two independent successful builds and child executions, retained
executable/build/stdout/stderr hashes, clean immutable source identities,
matching platform/version/scenario identities, unique execution challenges,
and valid nonempty observations at the requested execution layer. Equal raw
traces, duplicated executables/challenges, missing execution, missing cases,
failed builds, tampered artifacts, and empty traces cannot pass. The negative
control deliberately perturbs a measured MoonBit width by one pixel; the two
layout cases must change from pass to mismatch. It is a comparator test, never
an implementation conformance claim.

The manifest includes OS/architecture/version, package versions, both Git tree
SHAs, suite revision/dirty state, toolchain versions, process commands/PIDs,
start/end times, return codes and timeout status. Evidence is a local audit
trail, not cryptographic remote attestation: a malicious host capable of forging
all binaries, logs and metadata is outside the threat model. Do not promote a
stand-alone JSON trace or a golden fixture to an executed result.

Exit status: `0` only when no mismatch or unverified cases remain; `1` when a
mismatch exists; `2` when unverified coverage remains. Unsupported coverage is
always visible. Artifacts under `_build/` are local and untracked; preserve the
entire result directory when sharing or archiving evidence.

## Provenance

Only the pinned `crates/gpui` public APIs and test-support interfaces are used.
Its Cargo metadata declares Apache-2.0, and its `LICENSE-APACHE` points to the
upstream root Apache license. The runner links upstream workspace dependencies
as development tools; none enters the MoonBit runtime. The upstream Zed tree
also contains GPL application code, which is outside the suite's source scope.
See [PROVENANCE.md](PROVENANCE.md) for the exact inspected paths and method.
