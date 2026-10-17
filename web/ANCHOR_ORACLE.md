# Unchanged `anchor.rs` Rust-only browser baseline

Status (2026-10-17 UTC): implementation and source-only synthetic tests. No
local Rust/WASM build or browser capture was run. Actual unchanged-source PNGs,
trusted input and independent evidence verification remain pending isolated CI.
No measured Rust result or MoonBit conformance is claimed here.

## Immutable input and isolation

- Engine revision: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`
- Engine tree: `990fb995914d51a546b20e5cf0382dafc105c299`
- Example: `crates/gpui/examples/anchor.rs`
- Blob: `b4b280b714a61cea2cd3f3a8ffd82a8f0000eb6b`
- SHA-256: `5be423ce91b36db94857a8f7758f7f5967d0103b77941fa7bc7c5a64e3c4fe72`
- [Pinned source](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/anchor.rs)

Independent upstream-main inspection at revision
`322cd509dcccaee1f6bc44725d270598ae8171ad` on 2026-10-17 found the same example
blob and SHA-256. This establishes example-byte freshness only, not engine
revision equivalence. Execution uses source5a exclusively.

The relocated standalone package registers the unchanged example outside the
archived upstream tree. Build evidence retains exact example bytes, relocated
manifest, lock, eight embedded fonts, compiler/bindgen versions, command,
completion time and clean suite revision/tree. It builds only `--bin anchor`.
There is no modified upstream example, replacement rectangle renderer, executed
MoonBit candidate or live candidate-catalog registration in this job.

The baseline freezes `web/examples.json` from suite base `a20e5888` as
`anchor-rust-only-catalog-a20e5888.json`, SHA-256
`2bf21a873708712eeb43cfb028138b15f8859ae6660c73407b7e83b4ae9adae8`.
Its core pin `aafa754affa049c1eaf69c75c1d04c5d895d3677` is unused metadata.
`implemented` is empty, `moonbit_execution` and `comparison_status` are
`not_run`. Future candidate work must use a separate profile and cannot relabel
this frozen Rust-only baseline.

## Predicates fixed before observing CI

The exact profile is one Linux Chromium/SwiftShader document at DPR1, full
600px height, with real viewport sequence `750 -> 480 -> 750`.

1. Capture initial idle at 750.
2. For all eight corners in source row-major order, move the real pointer into
   the independently discovered visible button interior; capture; move to the
   independently observed white safe patch; capture restoration.
3. Move to the source-inferred center lattice point, capture inert output,
   return to the safe patch, capture.
4. Resize to 480, capture idle, repeat all eight entry/exit and center steps.
5. Resize back to 750, capture exact idle restoration, repeat TopLeft entry/exit.

That is 41 independently captured states, 38 trusted pointer moves and two trusted
viewport resizes. Every state retains at least two separately requested complete
original PNGs with identical decoded RGBA. All attempts and failure screenshots
remain intact. No PNG is cropped, padded, resampled or replaced in success
evidence. Browser inner size, DPR, canvas DOM bounds and backing size are
measured at every state. One document identity and exactly one navigation reject
reload substitution.

Pointer coordinates come from full original PNGs. Exhaustive dark-achromatic
8-connected component discovery (`R=G=B<=220`) finds exactly eight outline
components with substantial perimeter and low fill density. Source sizes bound
the outline class (visible width80..122, height63..67), not its coordinates.
Only afterward are components sorted into source rows3/2/3 and named. At 480,
the first-column observed bounds are explicitly clipped visible pixels. The
center is an inferred vacant lattice point, not an observed center button box.
The safe and center points must have independently observed 7x7 white patches.

At hover, one independently discovered exact-black substantial component must
occupy the selected button's visible outline bounds. An independent full-image
63/64-gray 4-connected component identifies the source 75%-opaque black popup
on white; it must have substantial area, at least 70% fill density, width 95..180
and height 15..40. Text holes are allowed. Neither report geometry nor candidate
coordinates participate in discovery. Exact text/glyph output is unverified.

Source geometry is checked separately, with 2 physical pixels maximum edge
uncertainty from antialiasing, fractional origins and rounded translation. Popup
sizes are measured, never hardcoded or inferred from caption widths. The source
120x65 button, local resolved positions and anchor subtraction imply these
reference points relative to the unrounded button origin:

- TopLeft `(0,65)`, TopCenter `(60,65)`, TopRight `(120,65)`
- LeftCenter `(120,32.5)`, RightCenter `(0,32.5)`
- BottomLeft `(0,0)`, BottomCenter `(60,0)`, BottomRight `(120,0)`

This explicitly tests the source-derived hypothesis that the default block's
absolute static origin follows its 65px preceding button. It is not a directly
instrumented runtime origin. If it fails, the job retains the failure instead of
fitting positions. `anchored.rs` applies Local origin plus authored position,
subtracts the selected popup anchor, clamps right/left then bottom/top to the
viewport and rounds final translation in logical pixels. The 2px uncertainty
covers logical rounding plus fill-pixel raster bounds; guaranteed 1px regression
detection and exact layout-box geometry are not claimed.

The fixed 512px grid and 24px column gaps predict 178 2/3px track pitch. At 480,
all fully visible middle/right-column button measurements must independently
show a 135px left translation and unchanged y, within 1px. Their average observed
translation applied to the original 750 left-column observations supplies a
separate *unclipped-origin hypothesis*. The clipped original 480 button bounds
must agree with its viewport intersection. This origin is never labeled a
direct observation. Both TopLeft and BottomLeft desired popup x values must be
negative, their measured popup fill must begin at x0, and their full popup
width/height must agree with the original 750 popup within 1px. This distinguishes
snapping from a partially clipped, unsnapped popup. Ambiguous components or
inconsistent translation fail closed. No assertion of other snap edges is made.

An earlier source-only assessment considered 560px. It was not executed: that
width was rejected because it likely would not activate snapping. It is not a
failed runtime observation. No short-height source variant or authored probe is
substituted for this example.

Every hover exit and center capture must restore the complete original idle
RGBA for its viewport.750 restoration must equal initial750 RGBA. Repeating
TopLeft must restore its measured component geometry. Full-image identity is a
within-Rust restoration predicate, not a claim of cross-runtime glyph parity.
Trusted pointer/mouse event pairs bind exact observed target interiors; these
are DOM transport observations. Application hover entry/exit is established by
paint changes and restoration, not by claiming DOM elements for canvas buttons.

## Evidence and limits

Retained evidence includes original HTML, every executed document/script/font
response, each generated worker response, server-served hashes, actual graphics
metadata and complete input stream. The generated worker is derived solely from
the exact wasm_thread 0.3.3 revision/template pinned by Cargo.lock and the observed
anchor loader URL. The actual served WASM must embed the complete worker
template and all eight complete font files. Unpinned executable dependencies,
foreign URLs and altered current HTML/host/loader/font/source/lock bytes fail.
All retained current suite inputs must byte-match their committed HEAD blobs;
revision/tree and frozen catalog identity must match the current clean checkout.

The independent verifier rereads original PNG/runtime/support bytes; report
pass flags, reported geometry and supplied coordinates cannot substitute for
observations. Portable unique filenames, bounded strict PNG framing/CRC/order,
complete bounded zlib streams, single-frame RGB/RGBA8, and path/symlink/hardlink
checks fail closed. Reverification appends rather than replacing prior results.

Corrupted-evidence controls include missing popup/hover, wrong anchor/offset,
stale exit hover, active center, clipped unsnapped popup, lost restoration pixel,
missing/untrusted/wrong-target pointer input, missing resize, wrong backing,
reload/different-document substitution and altered source/font/runtime/worker/
HTML/catalog bytes. These controls are not executed engine mutants and do not
replace success evidence.

The unchanged popup is background-only and inserts no hitbox (`div.rs:2407`).
This profile makes no popup clickability, deferred hit-routing, ancestry or
internal dispatch-order claim. The source uses `deferred`, but nonoverlapping
visible popup output alone cannot independently prove general deferred paint
ordering. Any separately authored semantic diagnostic must retain its own
identity and cannot be called unchanged `anchor.rs`.

Other explicit limits: MoonBit counterpart/comparison, exact glyph shaping,
rounded-corner/border antialias/shadow raster fidelity, native or full-image
cross-runtime parity, callbacks/hidden work, other browsers/GPUs/viewports/DPRs.

## CI and local checks

The isolated `.github/workflows/anchor-oracle.yml` builds only unchanged anchor
Rust WASM, then captures and independently verifies original evidence. Build,
site and failure artifacts upload with `always()`. It does not launch a native
app or compile MoonBit. Actual results require exact-head independent artifact
review before this can be treated as an established baseline.

Source-only local checks:

    node --test web/tests/anchor*.test.mjs
    python3 -m unittest discover -s web/tests -p 'test_anchor*.py' -v
    python3 -m unittest discover -s web/tests -p 'test_rust_packaging.py' -v
    python3 -m unittest discover -s web/tests -p 'test_rust_subset.py' -v

PNG tests require Pillow 12.0.0. Local checks reused an existing pinned install;
no dependency or browser download, Rust build or WASM build was performed, and
free disk remained above the 1 GiB floor.
