# Distributed spacing device-grid precision

This profile compares complete headless GPUI TestWindow and MoonBit root/container/
child rectangles. It does not qualify desktop input, rendering, or pixel output.
The shared comparator tolerance remains 1e-5; no epsilon or geometry normalization
is introduced.

## Independently observed baseline

The merged core `cbefdb08f97a0be1adf2afc2eb9cb68dd8675367` (tree
`24125f4c69431a4675373ba26f7fab7f2af44aeb`) was run against actual pinned GPUI
`5a5fbe79917971a4d52a96b6ddb04da198a5012e`. A new Rust adapter was compiled and
linked against the verified read-only dependency cache, adding all five child
selectors rather than truncating observations after three children.

The original baseline suite source was `0801d4d` (before mutation classifications
were filled from observed baseline results). Source/executable-bound evidence is
retained in `reverse-rounding-baseline-build/build-manifest.json` and
`reverse-rounding-baseline-run/manifest.json`, including every batch's original
input and process output. It produced **1,262 passes and 35 mismatches out of
1,297 cases**.

The cases cover the full Cartesian product of four directions, three wrap modes,
three distributed justification modes, scales 1/1.5/2, physical starting padding
0/14/14.25, and 2–5 children (1,296 cases), plus the original intrinsic-parent
counterexample. The 35 observed failures include 29 reverse-flow cases (including
the original intrinsic case) and six forward-flow cases. The forward cases expose
the same precision/operation-order problem, not a reverse-only condition.

The integer-input minimal reproduction is a 142-unit main extent with start/end
padding 14/10, gap 6, Auto-sized children 12/20/49, zero grow/shrink, scale 1, and
space-around. The middle reversed child starts at 82 device pixels in Rust but 81
in the baseline MoonBit implementation. No fractional authored inputs are needed:
distributed space introduces fractional intermediate values. Taffy computes f32
physical-origin-first accumulation; the baseline uses binary64 relative offsets
and adds the origin later. The rounding rule itself is not changed.

## Controls and candidate status

`production-distributed-spacing-double` replaces only the production helper's
initial fallback guard, forcing the existing binary64 placement path. Its complete
original/mutated function and file hashes are validated. Expected failure IDs are
exactly the 35 separately observed baseline IDs, not all reverse cases. The other
1,262 cases are controls. Root-width corruption must fail all 1,297 cases.

The batched runner retains every full input and raw output; batching only avoids
OS environment-size limits, never filters cases. Synthetic tests validate this
contract but are not runtime parity evidence. Actual candidate `0e5b427f2490a53082ca273cdda8a17b25db9ec0` (tree
`d772cc117583e283db8ed5c728834a6630da3350`) paired with suite `b680430`
passed all 1,297 positive cases. Its production fallback mutant reproduced
exactly the baseline 35 mismatch IDs, while 1,262 controls passed. Root-width
corruption was detected in every one of the 1,297 cases. Source-bound runs are
`reverse-rounding-positive-run`, `reverse-rounding-mutant-run`, and
`reverse-rounding-width-run`; raw output is retained separately for all 21 batches.

All original 584 regression cases were rerun unchanged: 120 point-basis, 144
percentage-basis, 132 intrinsic-basis, 72 justify, 48 align-self, and 68 reverse-flow
cases passed. Their source-bound evidence directories are
`reverse-rounding-regression-{flex_basis,percent_basis,intrinsic_basis,legacy}`.
The old intrinsic discrepancy is retained historically in its diagnostic rather
than having its original observed source identity rewritten.

The production change applies f32 physical-origin-first accumulation only in
bounded device-grid zero-grow/zero-shrink distributed placement. Raw Double
layout, huge finite metrics, non-fitting lines, and flexible layout retain their
prior paths. A complete arbitrary-Taffy/CSS precision compatibility claim is not
made. The four directions and all three wrap modes in this profile passed; actual
desktop, GPU, IME and image comparisons were not run.

## Final source binding

The final pins name core `0e45d9ee82c251eab3f6102014f1bf8e4d92ad64` (tree
`9b1836c7b5f35fdad966ec5f704424d7f8d5c1b1`). Its production implementation is
unchanged from the observed `0e5b427` candidate; documentation and fallback tests
were added. Fresh final-source build/run directories use the prefix
`reverse-rounding-final-`. Their manifests retain the exact suite source identity,
input bytes, executable hashes and raw output. Earlier directories remain bound
to their original observed identities rather than being relabeled as final runs.

## Independent review correction: Percent far-edge preservation

The first final-pin run above is retained as **intermediate**, not release approval.
Independent review found 10 newly introduced Percent-basis far-edge regressions
among 2400 exploratory cases. The compatibility helper now excludes every line
containing a Percent basis item, preserving the existing Double path for that
line; Percent precision compatibility is not claimed by this change.

All 10 observed regressions plus the minimized 1/3-basis case are retained without geometry edits in
`reverse_rounding_percent_preservation_scenarios.json` (IDs prefixed only).
Scale 1.25 from the actual review counterexamples is admitted explicitly by the validator; comparator tolerance remains unchanged.
These 11 cases are an additional positive preservation corpus, executed with
`reverse_rounding_regression_pins.json` through the Percent-capable adapter;
they do not replace or alter the original 584 regression scenarios.
The review's wider exploratory corpus includes pre-existing mismatches and is
not claimed as passing. Fresh qualification after this correction is retained
under `reverse-rounding-qualified-*`; earlier final-named artifacts remain
historical evidence rather than being overwritten or relabeled.

Corrected qualification core pin: `bf749e5e0ebe450b7174cd6682ac8a17966a6863`
(tree `308a4c671c9af146b677897ba5322cfac362c00d`).


## Seven-child far-edge preservation
Review additionally identified a source-faithful Auto-basis arithmetic case beyond
the original five-child corpus. The Rust adapter now observes all seven children
(selectors a–g), and `reverse_rounding_far_edge_scenarios.json` retains the
84px row-reverse case as an additional actual-GPUI preservation check. The main
1297 cases and original 584 cases remain unchanged. Its child index3 exercises
the rounded far edge, not only the start coordinate. All root/child rectangles
are still compared at the original tolerance.


The qualified compatibility path is additionally restricted to absolute container
main-axis origin zero, exactly Float-representable sizes, and matching rounded
Float/Double far edges. Any Percent basis or authored Percent main-axis size
keeps the entire line on the pre-existing Double path. Nonzero container origins
are not a new compatibility claim; padding inside a zero-origin container remains
covered. These guards avoid extending local-origin arithmetic to unqualified
absolute-coordinate and far-edge cases.


## Final guarded qualification
The final reviewed core pin is `93ce6a9e345944cf740db2be74e8e8f0d3876704`
(tree `cfdc2e40146c52482744c7dc9ad4851b02348ebd`).
Fresh exact-pair evidence is under `reverse-rounding-reviewed-*`.
Earlier qualified/final-named runs are intermediate and are not relabeled.

A narrow optional `parent_offset_x` adapter field models a definite horizontal
container inside an outer wrapper with leading padding. The retained case uses
viewport189, offset47, inner width142, padding14/10, gap6 and Auto sizes12/20/49.
Both adapters observe the outer, inner, and every child rectangle without
projection. Actual pinned GPUI and merged-baseline MoonBit both place the middle
child at128, confirmed in `reverse-rounding-nested-baseline-run`. This preserves
the nonzero-origin fallback rather than claiming new nonzero-origin compatibility.
The validator rejects mixing the offset wrapper with intrinsic-parent mode.

Final positive qualification includes the unchanged1297 corpus, unchanged584
regressions, 11 Percent preservation cases, one seven-child far-edge case and one
nested-origin case. Final runtime results and source/executable identities are
authoritative in their manifests; this document does not replace those checks.


## Public core provenance and fresh checkout qualification

The ordered publication step produced public core
`222c0fbe865d5a66dccc4017abfb6bb10bab8018` on
`fix/distributed-device-grid-precision-20261026`. Its tree
`cfdc2e40146c52482744c7dc9ad4851b02348ebd` is identical to reviewed local
`93ce6a9e345944cf740db2be74e8e8f0d3876704`; these are the same source
change, not two development achievements. Existing reviewed manifests retain
their actual local revisions and are not relabeled as public-SHA execution.

Both profiles now pin the public core revision. A detached checkout fetched from
the repository is used for fresh builds and full qualification under
`reverse-rounding-public-*`, including 1297 positive cases, exact old-path
mutation and width-negative controls, unchanged584 regressions and13 additional
preservation cases. The fresh manifests identify the public core and actual
suite revision used; retained source and executable hashes remain authoritative.
This suite pin commit is local until separately published by the publisher.
