# Bounded native scalar anchor-margin pair

This layer compares the unchanged actual Rust margin observer with a genuine
compiled production `gpui.mbt` adapter. It adds no browser/catalog claim. The
frozen 88 cases are 22 authored placements × margins 0/8 × scales 1/1.25; the
Rust test platform's bootstrap scale 2 remains separately observed. Every raw
frame is retained and validated, including additional configured redraws. Final
states of both initial and configured operations are compared without requiring
equal redraw counts. All 88 configured comparisons must pass.

The candidate calls `Element::anchored_after(..., margin=...)`, deferred layout,
`request_layout_with_device_scale`, `prepaint`, actual tree bounds, scene
commands, and hit testing. It has no anchor placement or clamp implementation.
The actual Rust `element_offset()` getter remains a Rust-only observation.
Candidate popup-minus-wrapper translation is explicitly derived from observed
bounds, never labeled a getter or directly equated to the logical Rust offset.
Both popup and ordinary button are noninteractive, matching this margin corpus;
the two outside-viewport candidate probes per frame are only noninteractive hit
API smoke checks. They establish no new paired pointer or hit-mask correctness.

## Fixed policy before execution

`profile.json`, `raw.schema.json`, `compare.py`, and `mutations.json` are frozen
and hashed before candidate execution. The absolute geometry allowance is the
existing reviewed 2^-10 logical pixels within the same bounded coordinate
(±4096), size (0..2048), and far-edge (±4096) domain. Device-grid checks have a
separate 2^-10 device-pixel allowance. Structural data and logical viewport
masks are exact. There is no epsilon fitting, coordinate normalization, guessed
static block origin, or synthetic replacement of raw output. JSON rejects
NaN/Infinity and duplicate keys; all raw schemas and lifecycle frames are checked.

The Rust first-stage artifact was independently approved at public PR60 head
`cb4ace3f4b6a252db88c1a7d92cfb9c2d5e33b84`, tree
`1098d462cb250cc280a23dcf854772cd50ee7f4b`, actual CI merge
`11d18c9dd7322aa134733f3a4fa99973b9cef267`. Its 88 cases produced 264 frames,
not the synthetic fixture's 176 frames. Those are historical baseline facts,
not the identity or result of a future pair run. New CI rebuilds both frozen
Rust observers and records its own actual suite checkout and run identity.

## Three independent ordinary gates

1. New margin: 88 cases, 176 operation-final comparisons, including 88 configured.
2. Frozen original corpus/checker with compatibility-derived observer: 24 cases, 53 operations, five paired
   clicks against the same final core revision. The old pair profile's historical
   core pin is not changed. A new scoped provenance wrapper binds the exact
   original source and checks the new public core pin instead.
3. Unchanged separately authored fractional viewport extension: two cases,
   eight operations, four clicks. Original and fractional outputs keep their own
   inputs, session tokens, Rust/candidate raw output, and counts.

All three must be source-bound and pass before controls. Neither the old 24-case
corpus nor its fractional extension is folded into the 88-case margin claim.

## Narrow original-observer compatibility derivation

The gradient-enabled core adds a `Paint` scene variant. The frozen original
observer therefore fails exhaustive matching under `--deny-warn` (actual local
compile failure retained; CI proves the same failure before deriving). Its
committed bytes remain frozen. `observer_compatibility.json` authorizes exactly
one staging-only substitution: add `@scene.Paint => abort("unexpected non-quad
paint")` to that observer's scene-kind match. No warning is suppressed. The
original SHA, exact one-site transform, derived SHA and bytes, failed-original
compile command/logs, complete original/derived source inventories, and actual
derived build plan are retained and independently checked. Source drift,
nonunique match, changed transform, or unexpected Paint rejects. This is an
honestly labeled compatibility-derived compiled observer; it is not a claim
that unchanged original source still compiles. Input corpora, checkers,
observed fields, and comparison policies are unchanged.

## Executed controls and forensic checker controls

Each production control reopens all three ordinary gates before it starts. It
changes only the pinned production `element/anchored.mbt` correction block in an
isolated copied source projection. Each compiles and executes with the same
native compiler/runtime and frozen 88-case input, using a fresh token:

- `wrong-margin`: zeroes the actual correction margin; configured
  `cross-right-margin8-scale1` popup bounds must disagree.
- `always-inset`: tests inset edges instead of raw viewport edges; configured
  `exact-left-margin8-scale1` popup bounds must disagree.
- `swapped-opposite-edges`: applies left before right and top before bottom;
  configured `oversized-both-margin8-scale1` popup bounds must disagree.

A control counts only if its compile and execution succeed, strict transport and
all-frame candidate structure pass, and its predeclared Rust-paired witness
fails. Compile errors, crashes, timeouts, bad transport, incomplete observations,
unrelated mismatches, and copied JSON corruption are never margin semantic kills.

`run_controls.py` separately edits normal evidence copies, including coherent
outer-manifest rehashes for missing/changed source, build plans, generated native
objects, ELF identity, raw session tokens, and missing regression gates. It
reopens each copy without executing binaries. These are forensic sensitivity
tests, not production controls. Original artifacts are never rewritten.

## Provenance and independent reopening

The complete fixed source inventory includes all 26 original anchor/pair files,
all 11 frozen Rust-margin files, and every new adapter/checker/schema/profile/
mutation/compatibility/helper/test/workflow file. Required production inputs are enumerated
from independently selected exact Git trees, not a supplied arbitrary subset.
The native four-package projection preserves production bytes. Module metadata,
compiler executables and aliases, toolchain bundles/headers/runtime inputs,
actual direct-native build plans, all generated `.core`/`.mi` files, linked object,
runtime objects/archive, ELF, commands, execution paths, tokens, full raw traces,
and before/after source/tool identities are retained. Only named Moon database
and lock caches are omitted. Unknown native backends and missing planned inputs
reject. No generated-C assumption is made.

Copied verification binds sources against independent suite/core/upstream Git
objects, keeps original recorded execution roots, reruns all raw checks and
comparisons, and independently recalculates each control classification. Hashes
and CI records are source-bound forensic evidence, not cryptographic
build/execution attestation or a hermetic system-libc/linker capture.

The core public pin remains fail-closed until independently reviewed and
published. Source/unit checks or local JS smoke do not qualify this native pair.
Actual successful native CI, all three ordinary gates, three executed controls,
copied reopening, and independent original-artifact review are required before a
passing claim. No native-window, raster, browser, OS-event, general nesting,
other margin/scale domain, or full popover parity is implied.
