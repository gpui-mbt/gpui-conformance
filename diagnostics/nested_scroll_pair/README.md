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

Seven sequences cover 31 initial/post-wheel frames: repeated and reversed inner
scroll, overscroll and inner-boundary propagation, vertical wheels through the
inner container, outer clamping, outside/far-edge hit rejection, dominant-axis
selection, zero deltas, and offscreen threshold/reentry. All 31 frames compare
both scroll offsets/maxima, five translated node bounds and six pointer targets.

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
