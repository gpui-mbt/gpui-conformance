# Supplemental actual-GPUI anchor/deferred diagnostic

This separately authored font-free diagnostic targets public GPUI APIs at Zed
`5a5fbe79917971a4d52a96b6ddb04da198a5012e` (tree
`990fb995914d51a546b20e5cf0382dafc105c299`) with `TestAppContext` and
`VisualTestContext`. It is **not the unchanged `anchor` example**. It does not
establish screenshots, text/font shaping, native-window behavior, browser or
candidate-core parity, or application behavior. Runtime execution is pending CI;
synthetic checker tests and source inspection are not execution evidence.

## Bounded input, 24 scenarios

`scenarios.json` defines logical window pixels and an explicit requested scale.
Every case has a window size, parent origin and size, scale factor, ordered flat
popups, an optional later ordinary sibling rectangle, and interior pointer hits.
Each popup specifies its eight-way anchor, position, Local/Window mode, fixed
font-free size, priority zero and interactive flag. Numeric inputs are bounded
quarter pixels. The parent is an ordinary authored relative, default-Block div
inside a positioned wrapper. It contains a fixed 120×65 button followed by
`deferred(anchored().snap_to_window().child(...))`. The diagnostic never assigns
an expected rectangle to the anchored element, replaces its layout origin, or
calls an alternative layout solver.

Coverage is:

- Eight Local anchors with the unchanged example's `resolved_position` values
- A Local/Window pair with the same position and nonzero parent origin
- Each overflow edge and a popup larger than both viewport dimensions
- Positive and negative half-logical-pixel translations at scales 1, 1.25 and 2
- Three overlapping interactive deferred leaves with stable flat priority-zero ties
- A later ordinary interactive sibling under a background-only transparent popup,
  and the same geometry under an interactive deferred popup

There are five paired mouse-click operations. The example-style background-only
popup has no listeners, focus tracking, cursor, group, occlusion or other
hitbox-triggering style. A mere background does not insert a GPUI hitbox. The
interactive extension deliberately adds `.occlude()`, actual mouse/click handlers,
a focus handle and a leaf key context. It is separately labeled supplemental
semantics; it does not claim the unchanged example's popup is interactive.

Only flat priority-zero deferred ordering is in scope. SwitchAnchor, offset,
margins, client inset, nested deferred, container query, lists, scrolling and
arbitrary CSS absolute positioning are excluded. All pointer points are strictly
interior or exterior to observed interactive boxes and masks. Edge samples are
rejected: GPUI's closed `Bounds::contains` must not silently replace the paired
core's established half-open contract.

## Genuine observation and independent checks

`Observed<E>` delegates every original request-layout, prepaint and paint call,
returning the original request and prepaint states unchanged. It logs all entries
and returns, real bounds/content masks, paint order and the anchored element's
actual prepaint static origin. It neither reads expected values nor computes
placement/hit testing. The parent's Block static position after the fixed button
is deliberately **not** a required guessed witness before actual execution. Raw
`anchor_*` and `deferred_*` bounds establish what GPUI did.

Each real host request-layout starts a numbered frame. Deferred prepaint occurs
after the host prepaint returns; deferred paint occurs after the host paint
returns. Therefore host-paint return is not labeled frame-end. All lifecycle
events are retained until the next actual frame start or operation boundary;
completeness and nesting are checked without assuming one frame per operation.
The platform's bootstrap scale 2 is observed first, then every requested scale is
explicitly applied with a view notification. Focus/input redraws remain in raw
traces.

The verifier checks source identity, lifecycle phase/return/ancestry, actual
static origin sharing between deferred and anchored, child measured size, Local
versus Window translation, each clamp and oversized behavior, and logical offset
rounding with ties away from zero, followed by Window's device snapping of the
element offset with ties toward zero. Taffy also physically snaps layout with
ties toward zero. At 1.25×, the rounded logical offset +1 therefore becomes +0.8
logical pixels in the observed bounds, and -1 becomes -0.8. The check uses observed static origins
and child sizes, not a fabricated static-position solver. The fixed button's
height is physically snapped at 1.25×; it is not assumed to remain 65 logical
pixels at every scale.

Actual mouse-down and click callbacks identify the topmost painted interactive
leaf. The callback moves focus to its real tracked handle and records
`Window.context_stack()` primary contexts. This checks the actual focused dispatch
ancestry survives deferred extraction: Root→Parent→Leaf for a popup or button,
Root→Leaf for the ordinary sibling. It does not claim that GPUI mouse dispatch
itself follows the keyboard dispatch tree. Background-only popups must allow
that ordinary sibling's real callbacks through.

## Run and retained evidence

Source/schema/checker tests, with explicitly synthetic trace fixtures:

    python3 -m unittest discover -s tests -p 'test_anchor_diagnostic.py' -v

The dedicated workflow builds with pinned Rust 1.98.1 and the renamed existing
lockfile against the exact unmodified upstream pin:

    python3 diagnostics/anchor/run.py --online --upstream-source PATH --output _build/anchor-evidence

The runner requires 8 GiB free and never deletes evidence/caches to meet that guard.
No heavy Rust/WASM/browser compilation was performed during authoring in the
constrained local workspace. CI is the actual execution and semantic gate;
failures are retained, never fitted away.

Evidence retains adapter/lock/input/verifier/workflow source, relevant upstream
source with Git commit/tree checks, relocated build manifest, compiler versions,
command argv and timings, build logs, ELF, complete raw JSON/stderr, run token,
hash inventory and verification or failure. The independent workflow rereads
exact committed Git blobs; a pass field alone is not trusted. These bindings are
an audit trail, not cryptographic attestation of arbitrary artifact authors.

A copied unchanged bundle may be inspected with `--recorded-execution-root`
pointing to its original canonical absolute output directory. Exact
executable/input/token and relocated Cargo manifest paths remain checked. With
no independent suite/upstream checkouts and exact suite identity, the result is
explicitly integrity/semantic inspection with source authenticity unqualified.

Negative controls separately reject changed inventory bytes, mismatched engine,
compiler/command/token, rewritten source even if rehashed, and coherent
engine-shaped lifecycle output with wrong translation, ordering or callbacks.
A checksum failure is evidence corruption; a semantic failure in intact,
source-bound actual output is an engine/observer/checker investigation. Neither
is a passing conformance result. Synthetic controls are never called GPUI faults.
