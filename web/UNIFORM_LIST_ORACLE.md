# Unchanged `uniform_list.rs` Rust-only browser baseline

Status at introduction: source implementation and local synthetic/static tests
only. No Rust build, actual browser execution, or observed 26px result is claimed.
The dedicated CI workflow must establish actual unchanged source5a behavior;
its exact artifact needs independent review before this baseline is qualified.
There is no uniform-list MoonBit implementation, matched catalog entry, native
comparison, OCR, or full-image/text parity claim.

## Immutable source and isolation

- Browser engine revision: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`
- Engine tree: `990fb995914d51a546b20e5cf0382dafc105c299`
- Example: `crates/gpui/examples/uniform_list.rs`
- Example Git blob: `4a2c4788b192d802ee3d51714c250e7c5a82db76`
- Example SHA-256: `939b065c2db96ce38400c0ea79a0dd74803aa27793698bb5d00f6652a58f4e3a`
- [Exact upstream file](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/uniform_list.rs)

The compatibility d9 revision has identical example bytes but different
uniform-list engine arithmetic. This baseline executes source5a. It does not
silently reuse the root historical native-harness pin. `build_rust.py --oracle-only
--extra-example uniform_list` registers only the unchanged example in a relocated
standalone package, leaving every archived upstream file unmodified. The source
file, relocated Cargo manifest, dependency lock, actual compiler/bindgen version,
command, source revision/tree and completion UTC are retained.

`prepare_uniform_list_site.py` copies static host inputs and the current catalog
without running MoonBit. Its manifest explicitly records `implemented: []`,
`moonbit_execution: not_run`, and `comparison_status: not_run`. Existing catalog
entries and the core revision/tree are metadata only. They do not assert any
candidate execution. The catalog bytes are frozen in a hash-checked source-only
fixture. Later candidate work needs a separate implemented profile; historical
source-only evidence must never be relabeled. Existing pins, catalog, historical
results/profiles, and `harness.yml` remain unchanged.

## What this profile can observe

The original source has a white full-size root and a 50-item vertical list. Each
row has stable source `id(ix)`, horizontal `px_2()` padding, a pointer cursor and
`Item n` text. Its only click side effect is `println!`; this target's no-op stdout
means browser delivery cannot establish a click callback or clicked row identity.

The browser host explicitly uses 300×300 logical and backing pixels at DPR1.
The native WindowOptions alone is not accepted as browser-size evidence.
`discoverGeometry` scans original initial PNG ink bands to measure integral row
pitch and ink insets. The source-derived 26px line-height hypothesis is reported
separately and checked against the measured value only after actual capture.
The comparator supports other measured pitches in its bounded 16–48px range;
synthetic 26px and 31px cases reject a hardcoded 26px assumption.

The fixed source-led wheel plan, derived from that measured initial image, covers:

- `h-1`, `h`, and `h+1` small boundary positions, followed by exact top restoration
- A horizontal-only wheel mapping to vertical movement
- A diagonal wheel with much larger X but nonzero Y following Y
- Top and bottom partial text ink crossing the drawing-surface edge
- Forward integral-row sweeps no larger than 208px, with at least 92px overlap
- The full 50-row extent, endpoint clamp, repeated endpoint input, reverse 1px,
  return 1px, large negative return and repeated top clamp

Every state retains at least two separately requested original full-viewport
PNGs with identical complete decoded RGBA. Startup samples without measurable
paint and all unsuccessful stability attempts remain retained. No PNG is cropped,
resampled, rewritten, synthesized, or substituted. The verifier rereads all
original attempts and requires independent runtime/session/state/operation
bindings and unique evidence filenames.

For every forward or reverse state, the comparator matches overlapping complete
original scanlines at the source-constrained wheel translation. The overlap chain
covers the entire 50×measured-pitch content extent, so a wrong earlier clamp cannot
pass merely by repeating an endpoint screenshot. Complete original row rasters
are retained as hashes and must be 50 distinct rasters. A corrupted row-order
control swaps two demonstrably different original row rasters and fails the
translation predicate. This establishes bounded raster progression, not OCR
identity of the 50 strings. Source bytes establish which unchanged application was
compiled; no candidate telemetry supplies a Rust fact or expected pixel.

White root, bounded neutral glyph ink and stationary text origin/padding are
checked directly. Clipping claims are limited to actual partial ink at the canvas
edges. Because the unchanged list fills the surface, these pixels cannot
independently distinguish an internal content mask from ordinary surface clipping.
An eager all 50-row implementation or extra offscreen factory calls can produce
identical pixels. Factory laziness, callback ranges, internal mask semantics and
click IDs belong to the separately labeled supplemental real-GPUI diagnostics.

## Provenance and fail-closed verification

The runner retains actual HTML, every JS/module/WASM response, and each generated
worker response separately, including repeated blob URL responses. The v3-style
worker guard uses the exact Cargo.lock-pinned `wasm_thread` 0.3.3 source template
at revision `0cf96c7708dfb97ccf3da50347e25edcf75d6937`. The actual served WASM must
contain that complete template. Each actual worker body must equal its exact
single-marker substitution with the current loopback loader URL. Arbitrary blob,
data, external, unretained or unexpected executable responses fail closed.

The exact HTML entrypoint is hash pinned. Actual host and timing bytes must match
the current clean suite checkout. All eight pinned font inputs must match their
exact hashes and occur as complete bytes in the actual served WASM. Original
unchanged source is checked by both SHA-256 and Git blob. Actual graphics metadata,
console/network errors, Playwright 1.56.1, raw CDP wheel acknowledgements, trusted
DOM wheel events and post-delivery frame waits are retained. The server records
its own served-byte hashes separately. The graphics observation must show
SwiftShader; merely requesting a launch flag is insufficient.

The dedicated Pillow 12.0.0 decoder checks original 300×300 noninterlaced RGB/RGBA8
PNG framing, chunk order/CRC, bounded complete zlib raster, legal row filters,
no animation and no trailing bytes. It transports only dimensions plus complete
RGBA to the verifier; original PNG files are preserved. Local files are bounded,
portable, regular, independently retained and cannot be symlink/hardlink aliases.

The verifier ignores report-provided geometry, expected offsets or pass flags.
It recomputes pitch, row raster progression, wheel effects and edge output from
original bytes. A result from a different commit/tree, dirty checkout or catalog
cannot be certified as current. Failed runs preserve evidence and a failed
verification result. Rechecks append uniquely named results instead of replacing
an original verification record.

Negative controls are **corrupted-evidence sensitivity tests, not executed engine
mutants**. They reject unchanged-after-wheel images, wrong shift/pitch, distinct
row swaps, wrong endpoints, failed top restoration, erased partial edge ink,
missing/reordered/untrusted/wrong-coordinate/wrong-unit/wrong-delta input,
ignored X-only fallback, swapped-state/cross-runtime images, corrupted HTML/host/
WASM/worker/source/font inputs and changed pins/catalog. They do not claim to
kill eager factories, invisible extra rows, internal-mask bypass or click mutants.

## Dedicated CI and commands

`.github/workflows/uniform-list-oracle.yml` is a separate 75-minute Linux browser
job with 15-minute capture and 10-minute verification bounds. It installs the
fixed Rust nightly and bindgen, prepares only static host inputs, builds only
unchanged `uniform_list`, captures it, independently verifies it, and uploads
site plus original evidence even after a failure. It does not open a native app,
modify native-harness automation, or build any MoonBit candidate.

After committing a clean checkout:

    python3 web/scripts/prepare_uniform_list_site.py --out _build/uniform-list-browser-lab
    python3 web/scripts/build_rust.py --upstream-source _sources/zed --site _build/uniform-list-browser-lab --target-dir _build/uniform-list-rust-target --oracle-only --extra-example uniform_list
    BROWSER_EVIDENCE=_build/uniform-list-oracle-evidence PLAYWRIGHT_ROOT=/path/to/pw node web/tests/uniform-list-oracle-browser.mjs _build/uniform-list-browser-lab
    node web/tests/verify-uniform-list-results.mjs _build/uniform-list-oracle-evidence

A verified artifact reports `rust_source_profile_verified`, candidate
`not_implemented`, comparison `not_run` and conformance `not_claimed`. Actual
artifact review remains a separate gate. No native, text/OCR/full-image parity,
factory/callback/internal-mask/click evidence, other viewports/DPRs or other
browser/GPU claims are made.
