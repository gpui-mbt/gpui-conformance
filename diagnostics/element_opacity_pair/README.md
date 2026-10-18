# Bounded inherited element opacity pair

This fixture exercises real pinned Rust GPUI `TestAppContext` rendering, Taffy
layout, `Window::painted_quads`, and dispatched mouse listeners against production
MoonBit request-layout/prepaint/paint and input dispatch. It is not the full
asset-rich upstream `opacity.rs` example and does not increase catalog coverage.
No renderer pixels, native windows, text, images, SVG, GIF, shadows or animation
are qualified by this headless fixture.

## Policy frozen before execution

`policy.json` pins each inspected upstream source blob. `window.rs` lines
4226–4242 multiply then restore the element opacity. `div.rs` line 2544 applies
that scope to its own style paint and its descendants. Intrinsic paint alpha
and binding opacity are multiplied once, with no group isolation.

`window.rs` lines 1031–1045, 3953–3991, and 4518–4543 establish that deferred
records do not capture element opacity. Every deferred group starts outside
ancestor opacity scopes; local opacity inside that group still multiplies.
The separate ordinary clipping case uses a zero-offset scroll viewport in core.
Deferred cases cannot also use scrolling because the current anchored API
explicitly rejects that composition. That limitation is retained, not faked.

Nine cases cover default/unit, nested overlap, intrinsic alpha, binding alpha,
zero-opacity pointer input, clipping, deferred reset, and nested priorities.
Each backend reports its actual geometry and paint traversal. Candidate raw
intrinsic alpha and scalar opacity are preserved. The only normalization removes
alpha-zero or wholly clipped candidate solid commands, matching GPUI scene
insertion. GPUI sorts scene quads by overlap order; the comparison permits
disjoint quads to commute while requiring the same ordering for every pair of
intersecting visible rectangles. Raw order remains retained. Numeric tolerances are fixed in `policy.json`; no observed Rust answer
is substituted into the candidate.

## Validation and execution

Portable tests use synthetic values to test the comparator. They are not actual
framework results:

    python -m unittest discover -s tests -p test_element_opacity_pair.py

The profile binds the independently reviewed immutable core commit/tree.
Unbound profiles and changed source identities cannot execute. The scoped
`element-opacity-pair` CI workflow uses the existing fixture jobs' pinned setup
actions and read-only permissions. It does not deploy or change repository
security settings:

    python diagnostics/element_opacity_pair/run.py \
      --core-source /path/to/core --upstream-source /path/to/zed \
      --output _build/element-opacity-pair
    python diagnostics/element_opacity_pair/evidence.py _build/element-opacity-pair

Requires installed Rust 1.98.1, MoonBit and Node, with 9 GiB initial build
headroom. The runner retains raw stdout/stderr, fresh compiler invocations,
Cargo artifact linkage, compiler source inputs, executable hashes, candidate
runtime and standard-library inputs, source identities, and distinct challenges.
Its four negative controls rebuild and execute mutated MoonBit applications;
failed builds are not counted as detected semantic controls. The checker
recomputes the comparison and rejects missing runtime/source/stale capture.
Retain the entire output directory. Its hash inventory is an audit trail, not
remote attestation against a malicious host.

Current state: source prepared and portable tests only. Neither Rust nor MoonBit
has been compiled or executed in the source-preparation environment. No paired
pass count or visual parity result is claimed.
