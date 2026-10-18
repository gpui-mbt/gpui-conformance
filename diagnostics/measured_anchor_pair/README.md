# Measured-leaf anchor pairing

Status: source-only preparation, not an execution or parity claim. The profile is
bound for independent source review to PR115 R4 after format/all-target core
checks passed. Other mutation workflows remain pending at binding time. This
source binding does not authorize publication/execution or merge; a later core
change requires repinning and renewed review. Unbound profiles cannot execute.

## Frozen comparison

`comparison_spec.json` was written before any candidate execution. Its SHA-256 is
`dba66cc5599a99e4f74e58ea7bec0eff089e08bb42da663bf6ef1050cdc551eb`.
The runner and independent verifier require these exact bytes.

The unchanged Rust fixture has two variants and fourteen ordered operations:
28 settled operations, 42 attachments, and 84 actual Rust Div hitbox records.
Compare each rectangle as physical left/top/right/bottom edges, retaining every
signed residual, using inclusive absolute epsilon 1/1024 physical pixel.
State, presence/counts, ordering, restoration and logical viewport masks are
exact requirements. Explained f32/Double differences remain strict failures.
No post-result tolerance changes, rounded-only checks or aggregate acceptance.

The corresponding core records are named `corresponding_core_input_geometry`.
They are actual core node outer bounds with the logical viewport mask, not
invented Div Hitbox objects. Input dispatch, occlusion and hit testing are outside
this geometry-only correspondence. Host snapped bounds do not define the mask.

## Distinct source identities

- S, immutable Rust fixture: `4bf568614f9a5707855a441314eec8080adbc8a7`,
  tree `02f135a1b1dd34add72e200813a1bdcba6f7f5ef`.
- B, merged PR71 integration baseline: `1afff3fc1540657cd6060c7e7bb29be0030ad66e`,
  tree `492373682d7af423e27833d3582ad43109dd5a4a`.
- R is the new paired runner commit, distinct from both. Every B path's mode/blob
  must remain unchanged and exactly fourteen additive paths are permitted.
- Upstream GPUI: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`,
  tree `990fb995914d51a546b20e5cf0382dafc105c299`.
- Core PR115 R4: `8c744192ed6c1282a136efe3bcfe3d4ba5b16156`,
  tree `86c7c4df4d5c82e6ee09b8b63a4e5af3a548dd29`. This exact reviewed
  source is bound; compiler checks passed, remaining CI and paired actual
  qualification are separate gates.

The old Rust runner's compiler-binding helpers are reused as source, not invoked
under a spoofed historical environment. Fresh execution uses the real
`actual-measured-anchor-pair` Actions job, a new UUID token, current R identity,
a fresh Cargo home/target and staged S sources, and actual compiler graph and
executable hashes. All inherited Cargo/Rust overrides are removed. The only
fixture source transformation is the recorded Cargo dependency path relocation.

## Source-derived text metrics

`noop_metrics.mbt` is a bounded metrics adapter. It accepts the literal strings,
authored 14/16 px fonts (rem 16), authored available content width and current
scale. It does not read observed bounds, scenario names or an oracle trace.

The adapter transcribes pinned NoopTextSystem UTF-16 glyph advances, repeated
binary32 accumulation, explicit LF splitting, LineLayout word-break candidates
and strict overflow, WrappedLineLayout width and height, TextLayout width ceil,
and Window pixel-snapped inherited phi line height. JS `Math.fround` is confined
to this named metrics adapter. It is not a rewrite of production Double fitting.
Source blob identities for line_layout.rs, line_wrapper.rs, geometry.rs and
util.rs are retained in the profile and checked against the upstream checkout.
The runner snapshots these files along with the original audited GPUI sources.

A source-arithmetic hypothesis needs explicit testing: a binary32 line height
promoted to Double can sit just above a device-grid integer, so the core
measured-size ceiling can add one physical pixel. For example, source-derived
f32(25.6) is greater than exact 25.6; multiplying by 1.25 in Double can cross 32.
This is not an observed pair outcome or permission to change metrics/tolerance.
The source adapter retains its literal f32 result; strict mismatch stays failed.

The Python metrics tests are independent source-model/static-wiring checks.
They do not establish that MoonBit or the emitted JS ran. Actual compiler and
execution evidence is a separate required stage.

## Production core lifecycle

Measured metrics enter Auto/Auto, zero-grow/shrink intrinsic leaves. The adapter
builds the authored centered host, decorated primary button, parent popup with
width 384/padding 12/border 1/gap 12, secondary button and auto child popup.
The available paragraph width is derived from authored width minus individually
snapped padding/border, never from Rust's observed width or final height.

`anchored_after_measured_leaf` uses TopLeft, Local zero position, margin 8 and
nested deferred priorities 1 and 2. Every state recomputes metrics and invokes
`request_layout_with_device_scale -> prepaint -> paint`; scene validation,
background-quad traversal and clip commands are recorded. No glyph paint or
native-font rendering parity is claimed.

Secondary margin-top 8 is represented by an unpainted flow wrapper with top
inset 8. Comparator proof checks its geometry independently of the parent gap
12. No anchor-position adjustment substitutes for the margin.

## Controls

Five isolated builds mutate genuine production/API source paths:

1. `owner-origin`: use owner left/bottom instead of measured leaf left/bottom.
2. `no-logical-rounding`: bypass whole-logical-pixel fit-offset rounding.
3. `eager-device-snap`: snap a local offset before inherited composition.
4. `window-mode`: use Window coordinates for the same zero position.
5. `stale-scale-metrics`: retain scale-one metrics at fractional current scales.

Each must compile, execute, and produce a control-specific semantic witness,
including a new/worsened violation relative to baseline. A red baseline does
not kill controls. Compilation failure is failure to qualify, never a kill.
Raw outputs are never edited to simulate a control. Complete comparison results
are retained even when strict parity is false.

## Execution and independent reopening

The profile loader rejects unbound state before creating evidence or resolving
tools. After source review and explicit publication/execution approval, verify the
public core pin is unchanged, publish R, and let its dedicated workflow execute. The workflow pins MoonBit 0.10.15+943464bfa, Node 24.11.0 and Rust 1.98.1.
The run retains original setup/compiler/runtime logs, exact staged sources,
compiler dry-run graph, linked executable, raw output, all comparisons and
source mutations. Failure logs remain available.

`evidence.py` independently verifies the full inventory, exact external Git
identities and current Actions run identity, source transformations, compiler
input/link graphs, process chronology, executable bytes and fresh run token.
It recomputes comparisons and semantic control witnesses. It can reopen a
completed strict-mismatch bundle without claiming parity. Original Actions logs
and artifact provenance must still be reviewed: hashes and self-reported JSON
are not cryptographic proof of execution.

Source preparation cap is 2 MiB authored files and 32 MiB read-only projection;
no builds/installations are part of source preparation. Future CI requires
9 GiB initial headroom, a 1 GiB + 32 MiB live disk floor, 512 MiB retained evidence
expansion ceiling and 128 MiB estimated compressed artifact ceiling. Runtime
resource approval remains separate from source-only approval.

## Limits and stopping condition

This corpus represents one aggregate intrinsic text leaf under an authored,
bounded wrapping constraint. It is not general constraint-dependent measurement,
native shaping, semantic text identity, arbitrary owner layout, third-level
deferred nesting, scroll/query composition, screenshot or whole-popover parity.
Unsupported inputs fail rather than being approximated.

Qualification requires both exact public pins to compile, fresh evidence to be
independently reopened, complete 28/42/84 coverage, restoration, and genuine
compiled control witnesses. Every strict edge failure remains visible; a source
explanation does not turn it into success. Missing metrics coverage, unexplained
differences or failing CI stop qualification. Browser integration is subsequent
work and must preserve these scope qualifications.
