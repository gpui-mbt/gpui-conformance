# GPUI Conformance Suite

Execute shared scenarios against pinned Rust GPUI and gpui.mbt, retaining the
programs and raw process output that produced each comparison. The headless
runner creates no native windows. The separate native runner uses isolated,
self-closing hidden AppKit/Metal accessory fixtures on an Apple Silicon Mac.

Pins: Zed/GPUI `d9afb21688e04f89d9e94d96d33eb530aef90886` (GPUI 0.2.2) and
gpui.mbt `b16210d9363aaac778d9c9240deadd392347b9d6` (distributed align-content candidate). See [pins.json](pins.json).

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
| IME composition | Web-only synthetic DOM transport (`web/tests/input-ime-host.test.mjs`); no live IME and no Rust reference comparison; **candidate-only** |

Headless layout/paint preparation and clip geometry do not establish pixel
rendering, Metal correctness, AppKit lifecycle, physical input, accessibility,
text shaping, or general GPUI compatibility. The root's implicit pointer target
is normalized to null: pointer cases compare only the two child listeners.
The original trees/data are authored here; no upstream test fixture is copied.

### Web TextField/IME lane

`ime_scenarios.json` declares the existing Web TextField composition cases as a
separate `ime` corpus. It is executed by the Node lane, not by `run.py`:

```sh
node --test web/tests/input-ime-host.test.mjs
python3 -m unittest discover -s tests -p 'test_ime_scenarios.py'
```

The corpus has no differential reference: the pinned Rust GPUI has no TextField
or IME transport. Its cases are therefore `candidate-only`, and the corpus
validator rejects a `pass` status or a live-Japanese-IME claim. The separate
Chromium programmatic-event test is not a physical keyboard or live IME result.

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


## Distributed `space-around` / `space-evenly` capability batch

[distributed_spacing_scenarios.json](distributed_spacing_scenarios.json) adds
24 complete-rectangle layout cases for the two previously absent modes. The
pinned Rust oracle executes GPUI's public `.justify_around()` and
`.justify_evenly()` builders. The engine baseline has 8 matches/16 differences;
the new library implementation has 24 matches/zero differences. A real combined
rerun preserves all prior 131 headless passes, for 155 total, while one unsupported
IME and two unverified native rows remain visible. All 22 nonempty new cases
reject a one-pixel measured-width negative control; the two empty controls have
no child width to perturb. See [the exact scope and evidence](DISTRIBUTED_SPACING_RESULTS.md).


## Wrapped-line `align_content` capability batch

[align_content_scenarios.json](align_content_scenarios.json) adds 36 complete-bound
cases for start, center, end, and stretch. They execute the pinned GPUI public
content-alignment builders against the new library API, including both axes,
wrap-reverse, signed overflow, single-line wrapping, nowrap controls, and limited
auto cross sizing. The baseline has 15 matches/21 differences; the candidate has
36 matches/zero differences. All 36 cases detect the measured-width control.
A real combined rerun preserves all prior 155 headless passes, for 191 total;
one unsupported IME and two unverified native rows remain visible. See
[the exact scope and evidence](ALIGN_CONTENT_RESULTS.md).


## Distributed wrapped-line content capability batch

[content_distribution_scenarios.json](content_distribution_scenarios.json) adds
42 full-rectangle cases for align-content space-between, space-around, and
space-evenly using actual pinned GPUI public builders and the new library modes.
The baseline has 20 matches/22 differences; the candidate has 42 matches/zero
differences. The measured-width control detects all 39 nonempty cases; three
empty controls remain passing. A real combined rerun retains all prior 191
headless passes, for 233 total, with one unsupported IME and two unverified
native cases unchanged. See [the exact scope and evidence](CONTENT_DISTRIBUTION_RESULTS.md).

### Nested scroll runtime diagnostic

[The nested-scroll pair](diagnostics/nested_scroll_pair/README.md) executes actual
pinned Rust/MoonBit wheel routing, offsets, maxima, translated bounds and hit
clipping. It retains offscreen-handle differences as explicit mismatches; it is
not a native-input or pixel-parity claim.

### Per-item cross-axis alignment diagnostic

[The align-self diagnostic](ALIGN_SELF_RESULTS.md) adds 48 full-rectangle cases
for inherited and per-item physical/flex-relative alignment, center, and
bounded auto-size stretch. It runs real Rust and MoonBit probes with explicit
source pins, build binding and capability/comparator negative controls.
It is separate from native input, pixels, and the older overall suite pins.

### Flow-relative main-axis justification

The [bounded flow-relative justification comparison](FLEX_JUSTIFY_RESULTS.md)
adds actual GPUI/MoonBit headless cases for explicit FlexStart/FlexEnd without
changing physical Start/End defaults. See `flex_justify_pins.json`,
`build_flex_justify.py` and `run_flex_justify.py` for exact-source replay; this is
separate from legacy pins and does not imply native/IME acceptance.

### Process-isolated Python contract checks

On Linux or macOS (POSIX), run `python3 scripts/run_contract_tests.py` from any working directory to run
all `tests/test_*.py` modules serially, each in a fresh standard-library unittest
process with the repository root as its working directory. This avoids unrelated
diagnostics' bare `run` / `compare` imports colliding in one interpreter; it does
not make monolithic in-process discovery supported. `web/tests` is out of scope.
Select a bounded subset with repeated `--module test_name` options. The default
per-module timeout is 300 seconds (`--timeout SECONDS`). Each child owns a process
group, which is killed on exit, timeout or interruption and its direct child
reaped. Descendants remaining in that group cannot overlap the next module;
this is not a sandbox for tests that deliberately detach into other sessions.
Windows execution is rejected rather than claiming unsupported tree cleanup. Child output is streamed;
the final summary counts modules, not test methods. Unittest reports its own test
counts, failures and skips in each child's output. Existing failures are not hidden.

Six modules require retained evidence: `test_background_evidence`,
`test_boundary_evidence`, `test_bundle_evidence`, `test_comparator`,
`test_native_evidence`, and `test_observer_evidence`. Supply each separately with
`--evidence MODULE=DIRECTORY` (repeatable); these use their existing script CLI.
For comparator evidence with a non-default corpus, also supply `--corpus FILE`
and `--expected-summary FILE`. Paths supplied on the command line are resolved
relative to the caller's directory. Missing evidence directories or explicitly
supplied missing comparator files are BLOCKED, not skipped. Invalid evidence and
other child failures remain failures. Any failed, errored or blocked module makes
the runner exit nonzero after attempting all selected modules.

This runner does not generate evidence or build prerequisites for you. Tests may
invoke tools or copy retained evidence, so provision their dependencies and disk
space before selecting them. A subset passing is not a full-suite or native
conformance qualification. Existing workflow-specific commands remain unchanged.
The runner's own tests use isolated synthetic suites and do not recursively run
the repository suite.

### Explicit point flex-basis

The additive bounded Auto/point-basis corpus has 120 cases across all four flow
directions and scales 1/1.5/2, including grow/shrink, mixed/zero/fractional basis,
wrapping and min/max constraints. See [FLEX_BASIS_RESULTS.md](FLEX_BASIS_RESULTS.md)
for actual full-rectangle GPUI observations, production-mutation controls,
legacy regression replay, reproducibility and the explicit unsupported scope.

### Definite-parent percentage flex-basis

The separate `percent_basis_scenarios.json` adds 144 independently authored cases:
12 families across four directions and scales 1/1.5/2. The JSON basis encoding is
`null` for Auto, a number for points, or exactly `{"percent": ratio}` for a finite
nonnegative ratio (including values above one). Cases cover zero, fractional,
unit and overfull ratios; asymmetric padding/borders; axis-specific gaps; mixed
bases; grow/shrink; main/cross limits; wrap/wrap-reverse; and fractional rounding.
The 24 Auto/point controls should remain unchanged by the percentage-only
production mutation; 120 percentage cases have logically authored mismatch
expectations. No expected rectangles are embedded in this corpus.

`percent_basis_pins.json` selects its exact core/upstream sources and the
`production-percent-resolve-as-auto` control. The shared builder overlays a small
percentage parser, passing ratios unchanged to `FlexBasis::percent`; the
historical point profile keeps its Auto/Points-only parser and old core pin.
The Rust adapter uses GPUI's real `flex_basis(relative(ratio))`. All root and
source-order child rectangle coordinates, scale metadata, headless viewport,
and exact MoonBit physical/snapshot viewports remain checked. These are bounded
headless layout observations, not native desktop, rendering, or pixel evidence.
Indefinite intrinsic parent main axes and content bases remain outside scope.

Measured clean-source runs, the initial ten scale-1.5 disagreements and their
production correction are recorded in [percentage-basis results](PERCENT_BASIS_RESULTS.md).

Synthetic contracts (also run by the portable harness workflow):

```sh
python3 -m unittest discover -s tests -p 'test_flex_basis.py' -v
python3 -m unittest discover -s tests -p 'test_percent_basis.py' -v
```

Build from the exact clean source checkouts using the pinned Rust 1.98.1 toolchain
and a compatible MoonBit toolchain. Omitting `--execute-build` only prepares a
plan. Without a dependency-cache or binary-reuse option, the builder performs a
full locked Cargo build, offline by default; `--online` explicitly permits
dependency downloads. Failed or incompatible caches never trigger a silent
fallback. Output directories must not already exist.

```sh
python3 build_flex_basis.py \
  --pins percent_basis_pins.json \
  --upstream-source /path/to/zed --moonbit-source /path/to/gpui.mbt \
  --output /tmp/percent-basis-positive --online --execute-build

python3 run_flex_basis.py \
  --pins percent_basis_pins.json --scenarios percent_basis_scenarios.json \
  --upstream-source /path/to/zed --moonbit-source /path/to/gpui.mbt \
  --build-manifest /tmp/percent-basis-positive/build-manifest.json \
  --rust-exe /tmp/percent-basis-positive/rust/target/debug/gpui-conformance-probe \
  --moon-exe /tmp/percent-basis-positive/moon/_build/native/debug/build/conformance_probe/conformance_probe.exe \
  --output /tmp/percent-basis-observations
```

Alternatively, replace `--online` with `--rust-dependency-cache /path/to/cache`
for verified read-only exact-pin Cargo dependencies (new adapter compile/link),
or `--reuse-rust-build /path/to/prior/build-manifest.json` for a verified identical
Rust adapter binary. The manifest reports the actual executable paths. Binary
reuse does not require a dependency cache. Neither reuse option accepts
`--online`.

For the capability control, build again with the percentage pins and
`--disable-flex-basis`, optionally reusing the positive Rust build, then run with
`--capability-control`. The only production mutation changes the percentage
resolver's `Ok(Some(resolved)) => Ok(resolved)` arm to
`Ok(Some(_)) => Ok(fallback)`, preserving validation, errors, point bases and the
adapter while avoiding an unused binding under `--deny-warn`. Its kind,
original/mutated function, complete source hash,
selected parser, pins and executable bytes are bound in the evidence. The runner
rejects point-versus-percentage control relabeling. Separately run the positive
build with `--negative-control` to perturb each observed root width and require
144 mismatches. The unchanged 120-case point corpus can also run with the
percentage-positive build by selecting `--scenarios flex_basis_scenarios.json`;
`run_flex_basis_regressions.py --pins percent_basis_pins.json` replays the original
72/48/68 legacy corpora with the original root request behavior.

Running these synthetic tests or preparing a build plan does not establish
runtime parity. Retain the fresh raw process output and manifests when executing
the commands before reporting an observed result.


## Intrinsic-parent point flex-basis

See [scope and source-bound results](INTRINSIC_BASIS_RESULTS.md). The additive
132-case corpus observes a definite outer viewport, auto-main-size nested flex
container and every source-order child. Only nowrap containers with zero child
grow/shrink and Auto or finite nonnegative point bases are qualified here.
Percentage/content bases and positive flex factors remain outside this profile.

Use `build_flex_basis.py --pins intrinsic_basis_pins.json` with the exact pinned
sources and an explicitly chosen build mode. Then use `run_flex_basis.py --pins
intrinsic_basis_pins.json --scenarios intrinsic_basis_scenarios.json` with the
resulting manifest/executables. The existing `--disable-flex-basis` build and
`--capability-control` run form the production point resolver negative control;
`--negative-control` corrupts root width separately. For unchanged 452-case
regressions against the same core, build with `intrinsic_regression_pins.json`
and use the original percent, point and legacy regression runners. Never reuse
a manifest after changing source or pin bytes; build a fresh source-bound one.
