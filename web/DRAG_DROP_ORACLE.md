# Unchanged `drag_drop.rs` Rust-only baseline

Status at introduction: source review and static/mock contracts only. No Rust
build or browser execution was run locally. The dedicated CI workflow must first
establish actual unchanged WASM behavior. There is no MoonBit drag/drop candidate,
matched gallery entry, native comparison, or full-image/text parity claim.
Existing catalog entries, engine pins, historical source-only profiles and their
strict guards are unchanged.

## Exact source and packaging

- Browser source revision: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`
- Source tree: `990fb995914d51a546b20e5cf0382dafc105c299`
- Path: `crates/gpui/examples/drag_drop.rs`
- Git blob: `8f038ef3308fee9b097e7289665c9fa47cd6945b`
- SHA-256: `4011afde7c64fac2559b78918e6fdabdc563fe9f7591c74425d72da906dcc47a`
- Compatibility revision `d9afb21688e04f89d9e94d96d33eb530aef90886` has
  the identical example blob and bytes.
- GitHub main was read on 2026-10-16 at approximately 17:51 UTC and returned the
  same blob. [Upstream example](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/drag_drop.rs)

`build_rust.py --oracle-only --extra-example drag_drop` registers only that
unchanged source file in the relocated standalone upstream package. It does not
edit the archived source or its original manifest. Without this explicit opt-in,
the normal matched build does not compile drag_drop. Only the Rust host can route
to the additional binary; `web/examples.json` has no placeholder candidate entry.
The existing engine remains `eb968228bbea56aff13721dc427875c2dacffc14`, tree
`ae9072d350ef6d1546e408226218ec08efc96552`.

The build retains actual Rust/bindgen versions, command, UTC completion time,
source commit/tree, unchanged source, relocated Cargo manifest, eight embedded
font inputs and file hashes. Verification checks source SHA-256 and Git blob,
exact font hashes and their complete bytes inside the actual served WASM. It
also binds the retained suite revision/tree/catalog bytes to the clean current
checkout; a historical build cannot be relabeled current.

## Source-led bounded behavior profile

The fixed profile is 800×600 DPR1 and has 54 input operations and 54 capture
states. Coordinates for sources and target are derived from the initial original
PNG's solid borders, rather than a hardcoded observed y-position. Source geometry
must show three 128×128 squares, 2px borders, 16px horizontal gaps, a 512×128 target
with a 3px border, and 60px source-to-target separation from margin10 plus gap5.
The colors are upstream blue `(0,0,255)`, red `(255,0,0)` and green `(0,128,0)`.

The profile covers:

- Same-position down/up without movement: no drag activation
- Exactly 2px movement: inactive; 3px: active; return toward 1px: remains active
- A coordinate-changing release with no preceding move, after a fresh source
  down: no release-only drag activation or target update
- Each color accepted by the target only on release, preserving the previous
  target paint while hovering; 50% target fill and selected-color border
- Outside-target release, repeated drags, and cleanup preserving the prior drop
- Right-edge minus 1px accepted; exact right edge and right edge plus 1px excluded,
  consistent with upstream half-open bounds
- Hover fill at 20% while inactive, and suppression while a drag is active
- A 120×50, 50%-alpha preview and pointer-centered geometry for the sampled
  centered and off-center positive-padding grabs
- Duplicate release injections after cleanup, with actual delivered or
  browser-suppressed event counts reported explicitly

Activation is authored in `div.rs` on a Bubble MouseMove whose distance from the
pending left down is strictly greater than 2px. A MouseUp does not run that
activation path. The browser runner uses direct trusted CDP mouse input commands
with explicit coordinates and button states, including a far-coordinate release
without a generated move. The exact trusted pointer stream must establish that
release's changed coordinates and absence of an intervening move. If the browser
cannot deliver that trace, the run fails and retains the failed evidence; the
runner does not silently substitute an ordinary click or claim coverage.

The optional compatibility mouse stream is retained and checked too. The
upstream canvas prevents default pointer handling, so a compatibility mousedown
or mouseup may be suppressed. A duplicate release may also produce no pointerup.
In that case it is evidence of browser suppression, not a claim that GPUI
received a second release or that internal callback counts were observed.

The activation grip is the activation move position minus the source origin,
not the original down position. `window.rs` places the drag view at pointer minus
that grip. The example then pads its child by grip minus `(60,25)`, so the offsets
cancel for the sampled grabs. The off-center down has source-relative offset
`(92,105)` and activation is `(95,105)`; the centered activation is `(67,64)`.
Actual PNG scanlines must confirm the resulting pointer-centered visible body.
This does not independently reveal the internal grip value. Near-top-left grabs
with negative padding are not sampled or claimed.

## Original evidence and independent verification

Each state retains at least two separately requested original full-viewport PNG
files with identical complete decoded RGBA. All failed stability attempts remain.
The capture runner refuses to overwrite an existing drag-drop evidence directory.
It retains the full input/event order, optional compatibility mouse events,
console/network failures, actual canvas dimensions, build/catalog/source/font
inputs, decoder source and actual served JS/WASM/host response bytes and hashes.
The local server separately records the hashes it actually served.

The drag-specific decoder leaves the historical decoder untouched. It requires
Pillow 12.0.0, exact full viewport, bounded PNG input, chunk framing/CRC/order,
single-frame noninterlaced RGB/RGBA8, a complete bounded zlib raster with valid
row filters, and no trailing bytes. It exports a bounded dimensions-plus-RGBA
binary stream, with no crop, resample or browser-side pixel substitution.

`verify-drag-drop-results.mjs` rereads every original attempt, executable/input
byte and stable sample; it ignores report-provided geometry and claimed checks.
It independently recomputes geometry, source/target border and fill relationships,
hover suppression, preview geometry/alpha and cleanup. Text ink and a bounded
preview-shadow area are explicitly excluded from the base-color predicates;
these are source paint checks, not full-image equality. Preview alpha is measured
from its color contribution after eliminating a neutral shadow's base scaling;
no GPU shadow-kernel equivalence is claimed.

Corrupted copies test sensitivity to activation at exactly 2px, early
cancellation on return, wrong accepted color, an outside release mutating the
target, a lingering/missing preview, leaked hover, wrong border width/gap,
untrusted/missing/reordered inputs and a release-only probe with a move or wrong
coordinates. Separate synthetic tests reject shifted/opaque previews, malformed
PNG framing/CRC/raster, wrong dimensions/version, APNG and trailing data. Synthetic
fixtures only exercise rejection; they are never observed Rust execution.

## Dedicated CI

`.github/workflows/drag-drop-oracle.yml` prepares the current pinned existing site,
builds only the unchanged drag_drop Rust binary, captures it, independently
verifies the artifact, and uploads both site and original evidence even on
failure. It has a separate 75-minute job with 15-minute capture and 10-minute
verification limits. Existing matched and tab-stop workflows are not weakened.

After a committed clean build, the relevant commands are:

    python3 web/scripts/build_rust.py --upstream-source _sources/zed --site _build/drag-drop-browser-lab --target-dir _build/drag-drop-rust-target --oracle-only --extra-example drag_drop
    BROWSER_EVIDENCE=_build/drag-drop-oracle-evidence PLAYWRIGHT_ROOT=/path/to/pw node web/tests/drag-drop-oracle-browser.mjs _build/drag-drop-browser-lab
    node web/tests/verify-drag-drop-results.mjs _build/drag-drop-oracle-evidence

A successful verifier reports `rust_source_profile_verified`, with candidate
`not_implemented`, comparison `not_run` and conformance `not_claimed`. Native or
global capture, touch, OS drag, foreign payloads, rejecting predicates,
nested/overlapping targets, internal grip values, other browsers/GPUs/viewports/
DPRs and candidate/full-image/text/native parity remain outside this baseline.


## Historical baseline retained after candidate integration

The introduction and engine pin above describe exact source-only suite head
`e278fce408aab28127560e1f250f11c030e8d042`, tree
`1cd3e18b31a4d2d8651871c0ab078c8059e7a702`. Its actual unchanged Rust
[CI run38945456947](https://github.com/gpui-mbt/gpui-conformance/actions/runs/38945456947)
passed: 54 operations, 54 stable states and 108 original PNGs. Artifact12067400103
SHA-256 is `66e7c1ad7a5f6a07693bfd43e87ddd92753ad552fccc706ce28e268f1c368681`.
That run does not include a MoonBit candidate.

Exact original catalog/workflow bytes are preserved in hash-checked fixtures
`tests/fixtures/drag-drop-rust-only-catalog-e278fce4.json` and
`tests/fixtures/drag-drop-rust-only-workflow-e278fce4.yml`. The original comparator,
runner, verifier and source-only record keep their strict historical contracts;
they reject the current implemented catalog rather than relabel the old result.
The new active candidate uses normal implemented-subset packaging and a separate
[paired harness](DRAG_DROP_PAIR.md). Its actual independent execution must pass
before any bounded agreement is claimed.
