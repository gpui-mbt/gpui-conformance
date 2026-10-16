# Supplemental actual-GPUI grid/container-query diagnostic

This separately authored, font-free diagnostic executes public GPUI APIs at Zed
`5a5fbe79917971a4d52a96b6ddb04da198a5012e` (tree
`990fb995914d51a546b20e5cf0382dafc105c299`) on `TestAppContext` and
`VisualTestContext`. It is **not the unchanged `grid_layout` example** and supplies
no screenshot, font, native-window, application, browser comparison, or candidate
MoonBit/core parity claim. The unchanged example's observations stay separate.

## Bounded contract

`scenarios.json` is the small shared input for a possible future genuine production
core pair. Each case specifies window size, root origin, scale factor, a tree of
`grid`, `query`, and opaque clickable `box` nodes, and hit positions. Every root
has a numeric width and height. Missing node width/height means `size_full()`;
numeric height can overflow its assigned grid track. A grid specifies equal
`minmax(0, 1fr)` columns and rows through `grid_cols`/`grid_rows`, a uniform gap,
and ordered children. Placement supports auto spans, explicit grid lines, and
`full_columns`, exactly GPUI's `col_span_full()` (`1 .. -1`). The validator rejects
ambiguous combined placement spellings. A query has exactly one child built in
its callback. Inputs are bounded quarter-pixel numbers exactly representable in
f32; observations may have other fractional values after device-edge snapping.

Twelve curated cases cover:

- Equal tracks, row-major sparse holes, explicit overlapping cells and hit order
- Fixed-height overflow beyond tracks and the grid rectangle
- The font-free 5-by-5 holy-grail structure and full-column header/footer
- Auto spans around a two-row item
- Nested assigned query size and world origin
- Identical query assignments with tiny versus oversized child content
- Fractional dimensions/origins at scales 1, 1.25 and 2

Each case opens at the test platform's actual bootstrap scale 2, explicitly sets
its requested scale and notifies the view, then sends each paired mouse click.
Frame count is observed, not assumed to equal operation count. Every actual frame
is retained, including redraws during input processing.

## Observation and verification

The Rust `Observed<E>` wrapper delegates the original `request_layout`, `prepaint`
and `paint` calls, preserving their states and return values. It records lifecycle
entry/return nesting, real bounds and content masks, callback size/timing, actual
mouse-click callbacks, scale, and viewport size. It never computes track geometry,
queries metadata for expected bounds, or implements hit testing. Font-free boxes
use `.occlude()` and stop event propagation so overlap has one topmost recipient.

`verify.py` validates trace completeness, event sequence, real lifecycle nesting,
one callback per query per frame during its own prepaint, child construction after
that callback, assignment-size agreement and nested origin. It cross-checks actual
clicks against the observed painted opaque leaves and masks. `witnesses.json`
contains small hand-authored integer-layout assertions independent of the Rust
observer. Fractional cases preserve actual geometry and check physical-edge
alignment; they do not pretend to provide a second complete rounding/layout
implementation. The small/large content pair independently asserts identical
query/sibling bounds. A failed assertion is evidence to investigate, not permission
to overwrite the input or manufacture a passing trace.

## Run and evidence

Local checker/corruption units (synthetic fixtures are explicitly not GPUI output):

    python3 -m unittest discover -s tests -p 'test_grid_layout_diagnostic.py' -v

The dedicated CI workflow installs Rust 1.98.1, builds the lockfile-bound adapter
against the exact unmodified source pin, then runs the actual ELF without DISPLAY
or WAYLAND_DISPLAY. To run on a suitably provisioned Linux machine:

    python3 diagnostics/grid_layout/run.py --online --upstream-source PATH --output _build/grid-layout-evidence

At least 8 GiB free is required; never clear existing evidence/caches to satisfy
that guard. No Rust build was run during authoring in the constrained local
workspace. Contract checks alone do not establish runtime success. CI is the
execution and validation gate; failed build/semantic logs are retained.

Artifacts retain original adapter/lock/input/verifier/workflow sources, relevant
exact upstream source files plus independently checked Git commit/tree identity,
the relocated build manifest, compiler versions, build stdout/stderr, ELF, complete
raw JSON/stderr, a hash inventory and run token, verification or verification
failure. The independent workflow step re-reads committed Git blobs rather than
trusting a report's pass field. Selective source retention is not a huge duplicate
checkout/archive. A verifier run without the independent Git checkout/identities
is explicitly labeled integrity/semantic inspection with source authenticity
unqualified. These hashes and source bindings are an audit trail, not a
cryptographic attestation that arbitrary untrusted artifact authors executed an
ELF.
