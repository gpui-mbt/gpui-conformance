# Bounded two-level anchored deferred native pair

This additive diagnostic compares actual Rust paint-entry box observations with
actual MoonBit production Quad emission for eight fixed cases. It changes no
prior oracle, pair, core, browser fixture, or external 109/55 corpus.

## Frozen contract before candidate execution

`comparison-policy.json`, `control-policy.json`, and
`actual-rust-projection.json` were written before any candidate execution. The
projection was extracted from the independently approved original Rust artifact
12100643370, run 39032334348, raw SHA-256
`b4fd41463d8a12da803ef04ffa37750ee25864e23a0def8e21f9528b5799fe50`.
It records all 56 frames and actual box-entry sequence IDs, names, order, bounds,
full-viewport masks, and corresponding candidate IDs. It is a reviewed mapping,
not a replacement for new actual Rust execution: the dedicated workflow builds
and runs the unchanged Rust observer and regenerates/checks the projection.

The compared domains are deliberately separate:

- Rust: actual named paint-entry callbacks for ten boxes, nine after removal.
- Core: genuine `Prepainted.tree()` layout and `paint().commands()` Quad IDs,
  emission order, bounds, and observed clip-push/pop stacks.
- Rust wrapper callbacks remain fully retained and source-verified, separately
  from boxes. Core helper/attachment nodes remain fully retained structural data.
  No tree walk is presented as emitted scene commands or lifecycle callbacks.

Every Rust frame is compared against every candidate frame in the same operation,
with the actual viewport and scale checked, including bootstrap scale 2 and both
base frames. Candidate redraw counts need not equal Rust counts. Order, identity,
geometry, masks and physical-grid alignment are exact. These authored coordinates
are integer and device-grid aligned at 1, 1.25 and 2. No tolerance is fitted.

Input, lifecycle callback, and redraw-count parity remain explicitly false.
Exactly two anchored deferred levels are covered. There is no claim for arbitrary
depth, ordinary deferred content, transforms, nontrivial nested clipping,
fractional logical nested rounding, cache, outside-click, raster, native windows,
browser behavior, or unchanged full upstream popover parity.

## Required source and execution gates

The new core pin is deliberately fail-closed until independent source review and
exact public commit/tree publication. The runner requires a clean, exact selected
suite and core and binds all production inputs to Git before staging. Existing
fixture hashes and the old public pins stay unchanged.

All native evidence is retained: exact module/package projections, original core
module and published API context, compiler/linker binaries and runtime inputs,
dry-run argv, generated `.mi`/`.core`/native objects/archive, built and executed
ELFs, stdout/stderr, process records, UUID session, full input, and all raw stages.
Unknown native backends, flags, package inputs, generated paths, or runtime
lineage fail closed. Relocated verification uses recorded historical execution
roots without executing copied binaries.

The same final core must also pass all frozen native regression corpora:
original anchor 24 cases, separate fractional viewport 2, margin 88, and flat
priority 16. The original anchor observer's genuine missing-`Paint` exhaustive
match compile failure is retained. Only its frozen one-site staging derivation
adding an explicit unsupported-`Paint` abort may then compile with `--deny-warn`.
No frozen observer or published pin is edited or silently bypassed.

## Genuine production controls

Before each control the runner independently reopens the passing source-bound
ordinary pair and all four same-core regressions. It compiles and executes an
isolated exact one-site mutation of production source, retaining every artifact:

1. Structural DFS child ties instead of discovery-dependent ties. Reversed-parent
   base and all-equal updated cases must reject on actual box paint order.
2. Parent-contiguous scheduling instead of globally sorted independent groups.
   Child-lower and reversed-parent base cases must reject on paint order.
3. Lost inherited outer Local offset. Increasing base and moved stages must
   reject on the actual `a.nested.root` bounds, whose expected origins are
   `(80,68)` and `(96,80)` respectively.

Build, timeout, runtime, transport, schema or unrelated rejection is never a
semantic kill. All named witnesses must fail only after successful execution and
valid observations. Exact source replacements are finalized from the reviewed
production sites before any candidate execution.

Copied/rehashed forensic controls separately test source, generated artifact,
ELF, plan, session, wrapper retention, and regression-gate sensitivity. They are
checker controls, never additional engine kills. Original evidence is immutable.

## Running

The dedicated `nested-deferred-native-pair.yml` workflow creates four fresh actual
Rust baselines, runs this pair and all same-core regressions, then compiles three
production controls and verifies relocated copies and rehashed controls.

For local checker-only tests:

    python3 -m unittest discover -s tests -p 'test_nested_deferred_pair.py' -v

Heavy execution needs a separately checked capacity budget, at least 2 GiB of
execution/evidence headroom above a strict 1 GiB free-space floor. No evidence is
deleted to make an execution pass. Source-only checks do not establish native
execution, actual parity, public release, or independent approval.
