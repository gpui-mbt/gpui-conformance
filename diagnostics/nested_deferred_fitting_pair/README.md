# Two-level nested fitting native pair

Source-only implementation. No native fitting candidate, production-control kill,
CI pass, independent approval, or publication is claimed by these files/tests.

The selected current core is e13c99d387738369e13a26302e556732d78a3b88
(tree e269ce546db3e13d8f82b742c0d7b1ae2ca35ca7). The reviewed fitting
Rust oracle suite is 2edaf30bcc9ec0c03045cd1db0f2a0f122dbb344 (PR67).
All 704 baseline Git blobs remain unchanged; exactly nineteen paths are added.

## Observation boundary

Eight cases cover strict exact/inside edges, outer-only and inner-only fitting,
both levels, device-half thresholds, signed-half composition, fit-created halves,
and Window versus Local placement. The original Rust artifact contains 80 actual
frames: initial once, scale1 and scale1.25 twice, then each remaining operation
once. Candidate observes one fresh frame per operation (64 total). All actual
Rust frames are compared with every candidate frame for that operation; redraw
count parity is excluded. Scales are bootstrap2, 1, and1.25.

The adapter emits actual layout and scene commands for thirteen painted boxes,
including three genuine reference boxes, and retains all 29 structural nodes.
Attachment owners are zero-gap columns with a real painted first ordinary child.
Ordinary sentinels are zero-extent row siblings. The observer checks live reference
positions/dimensions; the comparator checks actual O0/N0 against owner.left and
reference.bottom. It never feeds Rust geometry into candidate placement. Static
origin errors are semantic mismatches rather than observer aborts.

The actual Rust callback projection was read from reviewed artifact12109468360;
its raw digest and exact entries are frozen in actual-rust-projection.json.
Request/prepaint/paint wrappers remain in original raw evidence. Candidate scene
Quad order, bounds and actual clip-stack intersections are the paired surface.
All masks must match the full viewport. No structural traversal substitutes for
actual scene emission. Lifecycle, input, arbitrary nesting/content, nontrivial
clipping, cache, raster, browser, native-window and full-popover parity are excluded.

Separate absolute allowances are frozen before candidate execution:2^-10 logical
pixels for bounds/masks and2^-10 device pixels for the physical grid. IDs, ordering,
operation inputs and metadata stay exact. No relative or scale-expanded tolerance.
Candidate coordinates permit bounded negative origins so a successful disabled-fit
mutation can reach semantic comparison; ordinary parity still requires Rust match.

## Source and regression authentication

The new runner retains compiler/runtime/generated inputs, exact native argv,
ELF, stdout/stderr, session token, complete input and source inventories. It checks
34 compiled core inputs, module context and two API contexts. Current e13 source
identity is never replaced by historical5dbcc execution identity.

Frozen executable helpers are hashed before import. Legacy native build helpers
are reused only in scoped wrappers with the current direct-native contract;
old top-level core pins are never invoked. Every current-core execution must pass
original24, fractional2, margin88, flat-priority16 and prior-nested8 regression
corpora. The legacy Rust source checkout remains exact efc197a0ef9d64a35df6efe0ee2c97dff98ece04,
separate from the fitting oracle checkout. The unchanged prior-pair HEAD-sensitive
checker suite runs from exact ca784321838a59942cfdbc2a24804f038484974f; unchanged nested source validation is
not weakened to admit newer suite additions. Original anchor's only compatibility
derivation adds the unsupported Paint abort after retaining its genuine exhaustive
match rejection, with deny-warn preserved.

Six isolated exact production mutations cover disabled fitting, separately snapped
levels, logical-half toward-zero, device-half away-zero, Window-as-Local, and
owner.top instead of live reference.bottom. Each must compile and execute, pass
transport/structure, and reject every frozen named witness. Compile/runtime/schema
failures, unrelated differences and edited JSON are never engine kills. All five
same-core regressions and ordinary pair are reopened before each mutation.

## Lightweight verification

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_nested_deferred_fitting_pair.py' -v

Set GPUI_SELECTED_CORE_TEST_SOURCE for byte/inventory and exact mutation-site tests.
Synthetic Decimal fixtures test comparator sensitivity only, with the actual-Rust
freeze explicitly mocked only in those tests. A separate test requires those
synthetic traces to fail the real frozen projection. Parser-only MoonBit syncheck
is useful but is not a typecheck, native build, execution, or parity result.

The workflow source creates distinct fitting/legacy/core checkouts, all actual
Rust baselines, full source-bound pair, five regressions, six production controls,
relocated verification and rehashed forensic checker controls. Heavy execution
requires separately authorized dispatch and measured durable capacity: initial
8GiB headroom above a strict1GiB floor, plus per-process/copy reserves. Local
source work does not authorize any download, native execution or deletion.
