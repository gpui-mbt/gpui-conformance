# Nested scroll runtime pair

A font-free, authored reduction of the nested scroll containers in pinned
`crates/gpui/examples/scrollable.rs`. This is a headless behavior diagnostic,
not a complete example port, pixel comparison, browser wheel test or native
input result. It is separate from the Web IME and native text-host lanes.

The Rust probe creates actual GPUI `Div` scroll containers, retains real
`ScrollHandle`s, dispatches `ScrollWheelEvent`s through `VisualTestContext`,
and observes offsets, maxima, debug bounds and mouse-listener targets after
each completed frame. The MoonBit probe uses production `Element` layout,
prepaint, `ElementTree.scroll_wheel`, scroll viewports and pointer dispatch.
Neither side emits expected geometry or reimplements scrolling. The only
normalization is the documented sign difference between GPUI content-translation
deltas/offsets and gpui.mbt positive viewport deltas/offsets.

The seven original sequences cover 31 initial/post-wheel frames: repeated and reversed inner
scroll, overscroll and inner-boundary propagation, vertical wheels through the
inner container, outer clamping, outside/far-edge hit rejection, dominant-axis
selection, zero deltas, and offscreen threshold/reentry. The expanded fixture has 40 sequences and 202 initial/post-wheel frames (20 sequences at each scale).
Seven horizontally transposed sequences preserve the original actions. Three
fractional sequences cover quarter/half-pixel accumulation, reversal and clamping
in vertical, horizontal and both-axis layouts. Three additional both-axis sequences
exercise y-boundary propagation, axis switching/ties, and a clamped dominant axis.
Each frame compares both scroll offsets/maxima, five translated node bounds and
16 pointer targets, including fractional near-edge samples.

The vertical layout keeps the original 160×120 outer viewport and 160×60 inner
viewport, with 320×360 and 320×60 content respectively. Horizontal mode transposes
all block dimensions and child flow. Both-axis mode retains the vertical geometry
but gives the inner content height 180, so its maxima are (160, 120). GPUI bubbles
wheel events to both eligible scroll ancestors; this is not a residual-delta
handoff implementation. Once an inner viewport is clipped out, subsequent events
at the old point only reach the outer viewport.

Each case explicitly records device scale 1 or 2. The Rust probe changes the test
window scale through the production test context, reads Window::scale_factor(),
asserts it equals the fixture and emits the observed value; MoonBit calls production request_layout_with_device_scale.
This is necessary for fractional bounds: the unscaled logical-layout API does not
perform the device snapping used by GPUI. Offsets remain fractional and the exact
comparator retains every field difference, without rounding or tolerance.

## Run

Use clean checkouts at the exact commits in `pins.json`, Rust 1.98.1, MoonBit
and Node. On Linux the normal GPUI native build prerequisites are required.
The existing grid diagnostic lockfile supplies the unchanged dependency graph;
only the root package name is renamed in the retained build copy.

    python diagnostics/nested_scroll_pair/run.py \
      --upstream-source /path/to/pinned-zed --core-source /path/to/pinned-core \
      --output /path/to/new-evidence --online

An optional `--cargo-target-dir` reuses a compilation cache. Cargo still builds
the retained adapter against the clean pinned upstream source. The runner retains
both source stages, compiler/version/stdout/stderr logs, executable/JS artifacts,
source hashes, suite/core/upstream commits and trees, and comparison details.
It checks source cleanliness before and after execution. Exit 0 means this bounded
pair matches; exit 1 means a measured mismatch or a failed build/execution, with
details retained. No mismatch field is discarded or converted into a pass.

    python -m unittest discover -s tests -p test_nested_scroll_pair.py

These unit tests use deliberately synthetic records solely to test validation
and comparison. They do not establish runtime compatibility.

## Observed upstream difference

An initial actual run at the pinned commits found that the inner handle's
vertical maximum increases while its child is entirely above the global origin.
At outer y offset 240, GPUI reports inner max y 180 and gpui.mbt reports 0.
Scrolling back restores upstream max y to 0. Offsets, node bounds and hit targets
still match in that sequence; the inner viewport is clipped and cannot receive
pointer scroll there.

The source explains this behavior: upstream `Div::prepaint` initializes
`child_max` at `(0, 0)` before taking the maximum of child bottom-right positions.
When all child bottom edges are negative, the resulting content extent includes
the distance back to zero. `clamp_scroll_position` then derives `ScrollHandle`'s
maximum from that inflated extent. gpui.mbt computes its scroll extent in local
layout coordinates. This diagnostic preserves the difference as a mismatch;
it does not copy the upstream quirk into core or claim full parity.

## Expanded runtime findings (2026-10-19)

At the unchanged pinned core/upstream revisions, the 202-frame actual pair has
16 maximum-only mismatches: the original four and their transposed horizontal
counterparts at each device scale. Offsets, all five node bounds and all 16 hit targets agree in every
frame. The result remains `mismatch`, not a full compatibility pass. No core fix
is justified by these measurements.

A preliminary run with MoonBit's unscaled layout API produced fractional-bound
mismatches. Using its existing explicit device-scale API resolved those adapter
configuration differences; no core algorithm or expected geometry was substituted.

The real negative controls rebuild two deliberately broken MoonBit adapters:

    python diagnostics/nested_scroll_pair/negative_controls.py \
      --baseline /path/to/completed-evidence --output /path/to/new-controls

The no-wheel control zeroes both wheel deltas and detects 408 field differences
(138 offsets, 135 bounds, 119 targets, 16 maxima). The no-scale control calls the
unscaled production layout API and detects 62 differences (33 bounds, 13 targets,
16 maxima), with every offset still matching. Both controls compile and execute
real production core code; their mismatches never count as compatibility evidence.
The script verifies baseline source and observation hashes before mutation and
retains mutated source hashes, compiler logs, outputs and comparisons.
