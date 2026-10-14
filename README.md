# GPUI Conformance Suite

Execute shared scenarios against pinned Rust GPUI and gpui.mbt, retaining the
programs and raw process output that produced each comparison. This first slice
runs on an Apple Silicon Mac without opening windows or changing keyboard focus.

Pins: Zed/GPUI `d9afb21688e04f89d9e94d96d33eb530aef90886` (GPUI 0.2.2) and
gpui.mbt `f9f59fe074da3858ca82fe1d5fadd84cd17f0438` (0.7.2). See [pins.json](pins.json).

## First coverage slice

| Scenarios | Execution and observation |
| --- | --- |
| Fixed row with gap; proportional shrink | GPUI Render → Taffy → drawn debug bounds; MoonBit request-layout → prepaint → paint snapshot → element bounds |
| Painted opaque rectangle scene | GPUI `Window::painted_quads` from the completed frame; MoonBit painted scene snapshot items, comparing logical bounds and RGBA8 colors |
| Interior, far-edge and zero-extent pointer samples | GPUI test-platform mouse dispatch → child listeners; MoonBit input dispatch → element target |
| Plain/modified/repeated key down | GPUI focused element listener; MoonBit focused capture/bubble dispatch callback |
| Nested positive rectangle clips | GPUI window content-mask stack during canvas prepaint; MoonBit scene snapshot clip chain intersected by its geometry API |
| Window create/resize/remove | Rust test window executes; native MoonBit counterpart awaits coordinated foreground execution: **unverified** |
| Native GPU pixels | No native readback executed: **unverified** |
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

For a separately committed gpui.mbt fix, pass its checkout and full immutable
SHA with `--candidate-revision`. The result retains both candidate and baseline
revisions; the suite pin remains the baseline. Existing output directories are
rejected so prior evidence cannot be overwritten.

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
