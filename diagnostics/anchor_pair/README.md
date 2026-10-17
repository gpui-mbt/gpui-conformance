# Supplemental native anchor semantic pair

This is an additional font-free bounded diagnostic, not a replacement for the
unchanged upstream anchor example or its browser oracle. The production MoonBit
adapter calls real anchored/deferred layout, prepaint, scene, hit-testing,
pointer-dispatch callbacks and focused-dispatch APIs. It does not compute popup
rectangles, normalize output geometry or emulate an engine in JavaScript.

## Two separately qualified corpora

1. The immutable original `diagnostics/anchor/scenarios.json` has 24 cases and
   five paired clicks. Every raw frame is validated. The comparison uses the
   final observed state for each operation, inheriting the preceding state when
   there is no redraw. Actual redraw counts remain visible and are not paired.
   Geometry, painted quad order, logical effective viewport masks, actual
   down/up callback ancestry and focused dispatch ancestry are compared.
2. `fractional_viewport.corpus()` is a separately authored two-case extension:
   viewport 160.5 × 120 at scales 1 and 1.25, an interactive 320 × 240 popup,
   interior x=160.25 and exterior x=160.75 clicks at y=40. Both also observe the
   Rust test platform's bootstrap scale 2. Its input, runs, raw files, commands,
   tokens, binary hashes and counts are retained separately. It reuses the
   genuine Rust ELF only after exact source-bound qualification. No downloaded
   executable is run locally. The original Rust adapter, corpus and verifier
   remain byte-identical to their approved hashes.

The original verifier assumes integral physical viewport sizes. The separate
extension validator explicitly checks device-rounded host layout independently
from the logical requested viewport and its content masks. It checks all actual
lifecycle frames, callback targets and ancestry, with no modification to raw
observations. Candidate routing eligibility uses the logical viewport, never the
rounded root layout bounds. Boundary probes avoid closed-edge ambiguity.

Both layers retain the reviewed absolute 2^-10 logical-pixel geometry allowance
and bounded raw domain; device-grid checks have a separately named 2^-10 device-
pixel allowance. There is no fitted epsilon or output normalization. Exact
content masks and structural fields are not subject to a geometry allowance.
Raw JSON rejects duplicate keys, NaN and Infinity, and both trace schemas are
validated before semantic comparison. The candidate schema is retained with the
executed checker. Python requires jsonschema 4.26.0.

The original 96 candidate outside-viewport probes exercise transparent or
nonoverlapping content and are labeled accordingly. They alone do not establish
hit-mask correctness. Earlier local WIP snapshots also contained a separately
labeled candidate-only interactive extension; these are preserved as historical
smoke evidence. The final adapter emits only its supplied corpus. The stronger
new fractional extension is an actual two-engine pair in CI, not an extra pair
claimed from those candidate-only observations.

## Qualification and source identity

`profile.json` deliberately rejects execution while its published candidate
commit/tree pin is pending. A local source review or local JS smoke is not a
public native pair. Future CI records its own actual suite checkout, including
the actual PR merge commit when applicable. The historical Rust artifact's
public head/merge/tree are recorded only as historical evidence, not reused as
the identity of a future execution.

`run.py` first independently validates the selected Rust baseline against exact
suite and upstream Git objects and approved fixture hashes. It projects the four
production packages without editing their bytes, retains the original module
metadata, adapter, complete source inputs, generated native build outputs,
compiler executables and MoonBit core bundle/header/runtime inputs. The focused
module contains only those four genuine packages and the observer adapter. All
source and tool identities are checked again after execution. Linux native ELF
is mandatory for the qualified bundle. Compiler and system-toolchain versions
are recorded; this is not a claim of hermetic capture of every system libc or
linker input.

`verify.py` independently checks Git blobs, source inventories, full artifact
hashes, exact build/execution commands, tokens, input hashes, native ELF identity,
raw observations and both saved/recomputed comparisons. Recorded execution paths
remain explicit, so a copied bundle can be verified without running its binary
or pretending it executed in the new location. Only Moon's lock/database caches
are explicitly omitted; they are not compiled source inputs.

## Controls and CI

`run_controls.py` corrupts retained JSON. Those are synthetic checker controls,
never executed engine mutation kills. Unit tests likewise use explicitly
synthetic data and cannot establish engine correctness.

`run_mutants.py` will not start until the ordinary exact source-bound native pair
and the separate fractional pair both pass. Each of ten isolated production
mutations is compiled and executed with the same compiler/runtime, original
corpus and a fresh token. Source diffs, original/mutated hashes, complete source
input hashes, complete generated direct-native build inputs (.core/.mi, linked probe.o, runtime .o/.a), ELF, logs, raw outputs and manifests are
retained. Nine controls must fail original paired semantics. The tenth restores
the rounded-root viewport-mask bug and must pass the original 24 cases before
failing the separately labeled fractional Rust pair. Compiler rejection,
invalid transport, crash and timeout are never counted as semantic kills.

`verify_mutants.py` recomputes outcomes from copied evidence, verifies each
isolated source change against the qualified ordinary source, checks commands
and binary identities, checks the actual direct-native build plan and all planned generated inputs/outputs before cache reuse, and checks every outcome against the exact retained
mutation definitions. CI explicitly copies both bundles before this reread.

The workflow builds the unchanged actual Rust baseline, builds and executes the
genuine native MoonBit core, qualifies both pairs, runs synthetic checker controls
and compiled production controls, and uploads retained evidence even on failure.
The exact published core pin, successful native run, mutation results and final
independent artifact review remain mandatory publication gates.

No native-window, text/font, screenshot, browser-pixel, OS-input, native click
callback implementation or full backend parity is claimed.

### Native retention correction

The first native CI run used the compiler's direct-object backend and completed
both semantic pairs and all controls, but correctly failed copied verification:
the earlier retention loop assumed generated C and retained no per-mutant build
inputs. That failed artifact remains unchanged. The corrected runner keeps the
same direct-native backend, retains the complete generated build subtree for
each mutation before cache reuse, binds .core/.mi, linked probe.o, runtime
objects/archive and ELF to the actual build plan, and checks compiler aliases,
archiver identity, environment, commands and all hashes on copied verification.
Unknown backends and missing or changed required inputs reject. The previous
run does not qualify the corrected evidence pipeline; a fresh native run and
independent artifact review are required.
