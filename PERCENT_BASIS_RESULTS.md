# Definite percentage flex-basis and device-space layout

## Scope

The additive `percent_basis_scenarios.json` corpus contains 144 headless layouts:
12 profiles × four flow directions × device scales 1, 1.5 and 2. It covers Auto
and point controls, zero/fractional/100%/overfull percentage bases, mixed bases,
growth, weighted shrink, limits, wrapping, wrap-reverse and fractional geometry.
Asymmetric padding/border and distinct nonzero axis gaps exercise the containing
inner main extent. Percent ratios are passed unchanged to the real GPUI and
MoonBit basis APIs, not converted into point sizes by the adapters.

Every root and source-order child x/y/width/height is compared at the unchanged
1e-5 tolerance. Observed scales, the headless TestWindow viewport and exact
MoonBit physical/snapshot viewports are checked separately. There is no
children-only projection, expected-answer adapter, pixel/image normalization or
native desktop/window/GPU qualification. Content basis and intrinsically sized
parent main axes remain unsupported by the bounded production API.

## Actual executions, 2026-10-24 UTC

All source checkouts were clean and immutable during the measured executions.
The upstream pin is GPUI `5a5fbe79917971a4d52a96b6ddb04da198a5012e`, tree
`990fb995914d51a546b20e5cf0382dafc105c299`.

Initial clean candidate:

- Core `053b86e50818f67a91f28f54b5141fe6a9baea13`.
- Suite `16dd54f02e0f79ed3f8590894c0751edfef06f8f`.
- Actual result: 134 passes, 10 mismatches. The original outputs remain in
  `run-positive`; they are not overwritten or relabeled as passing evidence.
- All ten disagreements occurred at scale 1.5. Four were unchanged Auto/point
  controls. The corpus therefore exposed an existing device-grid arithmetic
  issue as well as qualifying the new percentage API.

Corrected clean candidate:

- Core `82a95274964939b172e97b074e0ec13fae99cca7`, tree
  `bd96cf73878353c9cd1e9bd495cdd94672a304de`.
- Suite `4945bb47321e8bcb6c624f5fc843c5166689affd`, tree
  `fa2b3a1860685877c64ec3a8773f8a1247d9698e`.
- Positive differential: **144/144 pass**.
- Separately compiled production Percent→Auto resolver mutation: **120/120
  expected mismatches**, with all **24 Auto/point controls passing**. These are
  observed results, not merely the corpus's declared expectations.
- Root-width corruption control: **144/144 mismatches**, no missing cases.
- Original point-basis corpus: **120/120 pass**, unchanged input bytes.
- Original flex-justify, align-self and reverse-flow corpora: **72/72, 48/48,
  68/68 pass**, with full rectangles and original legacy root request behavior.
- Combined positive coverage in these runs: **452/452 pass**.

The mutation replaces only the production resolver success arm
`Ok(Some(resolved)) => Ok(resolved)` with `Ok(Some(_)) => Ok(fallback)`.
Validation, error paths, point bases and the adapter remain intact. The complete
mutated source hash, exact function substitution, selected parser and distinct
MoonBit executable are bound into the build/run manifests. An earlier mutation
attempt failed compilation because its now-unused binding violated `--deny-warn`;
that failed build is retained as `build-disabled` and is not counted as execution.

## Why device-space arithmetic was required

Pinned GPUI converts authored lengths to device pixels before passing them to
Taffy, solves there, rounds absolute device edges and only then divides the
completed rectangle by scale. Previously MoonBit divided each snapped metric
back into logical units before solving. At scale 1.5, recurring thirds could turn
an exact device edge such as 89.5 into 89.50000000000001 and round it upward.

The correction keeps the opt-in pure and mixed flex/grid solve in device pixels.
Offered root sizes and supplied origins are scaled without pre-rounding;
explicit authored mixed-root sizes are pre-rounded. Ratios/factors stay
unitless, measured sizes ceil and positive strokes retain their one-device-pixel
minimum. Final rectangles and pre-edge metadata return to logical coordinates.
Raw scale-neutral APIs remain unchanged. No epsilon, f32 projection, tolerance
increase, scenario removal or reverse-flow placement workaround was used.

## Build provenance and retained evidence

Host: Linux x86_64. Toolchains: Rust 1.98.1 (`48a229cea`, 2026-09-01), Moon
0.1.20261012 (`748b63c`) and moonc 0.10.15+943464bfa with the matching core.
The initial dependency cache was freshly built with the checked-in lockfile
from the exact upstream checkout. Corrected probes freshly compile/link the
current Rust adapter against that verified read-only cache, and freshly compile
MoonBit. The mutation reuses the verified corrected Rust executable and compiles
its own MoonBit executable. No dependency or source substitution was made.

Corrected positive executable SHA-256 values:

- Rust: `ca52aab887a014b41a40cee90191958090a23ca2384a4852342666affcb964ab`.
- MoonBit: `70f643ee39bd1a5653bde942e3367ee55755d10efa544369c3666ff418dc05d6`.
- Mutated MoonBit: `250d7c961a54043b5be22b4accbc6908252e3db69a0e3dc0a51ce83925f6ae24`.

Raw stdout/stderr, scenarios, complete comparison JSON, executable hashes,
source identities and build manifests are retained in the local
`percent-basis-20261024` evidence directory. This note is an index, not a
substitute for retained process evidence. Manifest SHA-256 values:

| Directory | Manifest SHA-256 |
| --- | --- |
| run-positive | 552e5d29b1f355ba2285692981a131714ee089a4abaf4fb5707687b354d3f597 |
| run-corrected | 7818661c6160d99a29db078a979a8f6dd392a8428b9631cb2ad95743c4e36017 |
| run-percent-disabled | 58106aecc9c887a84c76bc134276390367eced8726fc7d434d82700f183ea5e2 |
| run-width-control | 6997d0865523464bcd90f0cb1ba19838ef1d8a03140c4288ccef00dae5501278 |
| run-point-regressions | fea9c65adceb4ad233583c231a05a5f325fed1bda24ad16ea0cd516b624271ca |
| run-legacy-regressions | 9d5b7d96aad8394db3f4066079bdb5fbdfbda191156b593b3e9712b73f9111a7 |

A later documentation-only commit does not relabel these source-bound builds.
For a fresh run, use the exact pins and [README build/run commands](README.md#definite-parent-percentage-flex-basis).
The builder also supports an explicitly selected full locked Cargo build,
offline by default or online with `--online`; a missing cache never silently
changes build mode. Output directories must be new.

## Other validation and limits

With the exact CI MoonBit toolchain, the corrected core passed all-target
checking, 1,158 tests on each of JS/Wasm/Wasm-GC, 727 related native tests
(layout/element/scene/app/controls), 177 layout tests on each of all four targets,
format checks, 167 Python tests, eight shared-UI-host tests and document checks.
The full native aggregate could not run in this cloud image because Ubuntu's
generated text-input protocol source and native system development libraries are
absent. This limitation is separate from the successfully executed headless
native probes and affected portable packages.

The suite's isolated full contract runner reported 37 passing modules, five
failing modules and six modules requiring unavailable historical evidence.
All five failures reproduce on untouched suite main
`75fdb7f6f159bf205f9fa8551fc9aabb372319e1`: the nested-deferred diagnostic/pair and
popover-outside historical profiles fail workflow/source-lineage checks,
including stale workflow hashes and unavailable historical Git objects. Those
historical checks were not silently updated as part of this feature. The 27 point/percentage basis
synthetic tests pass, as do the relevant justify/align/root/reverse contracts
and seven synthetic Node IME host tests. Synthetic checks do not establish
runtime or live IME parity.
