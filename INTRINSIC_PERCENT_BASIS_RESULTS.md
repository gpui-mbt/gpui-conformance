# Bounded intrinsic-parent percentage flex-basis

## Scope

144 independently authored inputs: 12 profiles × 4 flex directions × device scales
1, 1.5 and 2. The distinct `intrinsic_percent_basis` schema profile requires a
nested intrinsic-main parent, definite cross size, nowrap, and zero grow/shrink
for every child. Existing intrinsic point and definite percentage profiles keep
their previous restrictions. Content/text, flexible children, wrapping, authored
percentage dimensions and translated wrapper profiles are not included.

Compare all outer/container/source-order child rectangle coordinates, with the
existing 1e-5 tolerance, and exact physical/snapshot viewport and scale checks.
These are headless GPUI TestWindow observations, not renderer/desktop parity.

## Oracle-first baseline (2026-10-26 UTC)

The unchanged actual GPUI Rust adapter was executed against all 144 inputs before
implementing the new core branch. The preserved executable SHA-256 was
`ada284a4dad8121baaf3c132592cfe27d46ba44b0365ad25e2aa44e3b986db07`, and adapter
`src/main.rs` SHA-256 was
`45aab7a634754cfffe0a7321b44211fffc6051a1dc713d4a2bc7da19cc75b6bf`.
Original build manifest, executable bytes and complete adapter hashes were
verified before reuse; this is an archived binary execution, not a new Rust build.
Pinned GPUI source revision: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`.

For row / scale 1, authored main sizes [40,20,30] produce container width 115,
with inner main extent 98. All percentage profiles retain that measured extent
unless authored sizes/minimums change. Observed child widths:

| Profile | Container width | Child widths |
|---|---:|---|
| Auto controls | 115 | 40,20,30 |
| Point controls | 131 | 24,36,12 |
| Percent 0 | 115 | 0,0,0 |
| Percent .25/.5/.75 | 115 | 24,49,74 |
| Percent 1 | 115 | 98,98,98 |
| Percent 1.5/2/.5 | 115 | 147,196,49 |
| Auto / Percent .5 / Point24 | 115 | 40,49,24 |
| Empty Auto authored dimensions | 25 | 4,4,4 |
| Minimum main constraints | 165 | 60,37,45 |
| Maximum main constraints | 115 | 15,10,12 |
| Zero authored + positive minimum | 52 | 17,18,17 |
| Fractional authored/basis | 116 | 37,17,62 |

These are observations, not embedded expected rectangles or adapter formulas.
They verify unresolved percentage fallback during intrinsic measurement and
subsequent resolution against measured parent inner extent in the nested GPUI
layout, including overflow and constraints.

The preserved baseline MoonBit executable (SHA-256
`6d34ef6e05dcf13a61945fde3b2fe204380e368f34d05d1c2c17ee37613e56f0`)
completed the 24 Auto/Point control inputs. Each of the 10 percentage-containing
profile batches aborted at `RequestedLayout`; the 144-case combined run also
aborted. This is 10 rejecting batch executions, not a claim of 120 individually
executed refusals.

## Candidate qualification (2026-10-26 UTC)

Core candidate: `85981ca7df45cbb2c6728c8c0dd758786d115d4d`.
The candidate run pinned that complete revision and tree. Fresh MoonBit native
adapters were built from the recorded source bytes; the unchanged pinned Rust
adapter was reused with exact compiler, upstream, adapter and executable hash
checks. No fresh Rust compilation is claimed.

| Lane | Observed result |
|---|---|
| New corpus | 144 pass / 0 mismatch |
| Production intrinsic fallback mutation | 84 expected mismatches / 60 unchanged |
| One-logical-pixel root-width corruption | 144 detected mismatches |
| Legacy 72 + 48 + 68 | 188 pass |
| Existing point / definite percent / intrinsic point | 120 + 144 + 132 pass |
| Distributed reverse rounding | 1297 pass |
| Percentage / far-edge / nested-origin preservation | 11 + 1 + 1 pass |

The production mutation targets only `intrinsic_percent_contribution` in
`layout/tree.mbt`, replacing `Some(value) => Ok(value)` with
`Some(_) => Ok(0.0)`. It leaves the adapter, final percentage resolver, empty-Auto
fallback and unsupported-content guard intact. Auto, Point, empty, minimum-bound
and zero-with-minimum profiles are the 60 unchanged controls. The runner verifies
the original helper, exact replacement and complete original/mutated file hashes.

The first candidate exposed a real empty-main/definite-cross rejection and three
scale-1.5 overflow representation mismatches (about 1.017e-5). Those failed raw
runs were retained. The core corrected its guard to inspect the measured axis,
and restricted GPUI Float representation to the newly qualified device-layout
subtree. No corpus inputs, comparison tolerance or full-rectangle checks were
weakened to obtain the passing result.

Evidence consists of original build manifests, source-byte identities, actual
executable hashes, input snapshots, complete process stdout/stderr, per-case
comparison and separate mutation/negative-control runs. The source-bound
regression lanes retain all original corpus bytes. Synthetic Python contracts
remain separate from this actual runtime qualification.


## Public-core pin transition

The current profile and regression pin files name public core commit
`c58a53c11eaad138de1ee4b380e5dbfd512adb14` from
[core PR #152](https://github.com/gpui-mbt/gpui.mbt/pull/152).
Its tree `994c5c56405b492e2fe85193de1c945fe1ce04eb` is identical to the reviewed
local candidate above. Publication creates a different commit identity, not an
additional implementation change.

The original local qualification remains identified by core `85981ca…`, suite
`314215ed8007041bcfce6c2bef90c97cce358eef`, and its `final-*` run records. Those
historical records are retained unchanged, not relabeled as public-core runs.
Separate `public-core-*` builds and observations bind the public commit and the
updated suite source bytes, with fresh MoonBit native adapters and the same
hash-verified unchanged Rust oracle. Tree equivalence alone is not substituted
for actual public-core execution. CI and merge status are not asserted here.
