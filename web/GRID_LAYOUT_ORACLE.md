# Unchanged `grid_layout.rs` Rust-only browser baseline

Status at introduction (2026-10-16 UTC): local source implementation and
synthetic/static tests only. The unchanged Rust build, browser observations and
independent original-artifact verification are pending the isolated PR CI job.
No measured grid result or candidate conformance is claimed in this commit.
There is no grid MoonBit candidate, matched catalog entry or core implementation.

## Immutable source and packaging

- Engine revision: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`
- Engine tree: `990fb995914d51a546b20e5cf0382dafc105c299`
- Example: `crates/gpui/examples/grid_layout.rs`
- Git blob: `51f9b13e41fb7913c653d716da3e8ce05a96109d`
- SHA-256: `c82663a8c48340464f70f96dfa60135f4cd3b48670882b7bc23a9ca787fb261e`
- [Pinned upstream source](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/grid_layout.rs)

The example at upstream revision
`322cd509dcccaee1f6bc44725d270598ae8171ad` was independently inspected on
2026-10-16 and has the same blob and SHA-256. This establishes example-byte
freshness only; it does not equate the two engine revisions. This job executes
source5a exclusively.

The relocated standalone gallery registers `grid_layout` outside the archived
upstream tree. It retains the unchanged source, relocated Cargo manifest, lock,
all eight embedded font inputs, exact compiler/bindgen versions, command, source
revision/tree, clean suite revision/tree and UTC build completion. No upstream
source is patched. `--oracle-only --extra-example grid_layout` builds only this
binary. The shared builder and Rust loader gain an explicit grid route; existing
uniform-list, tree and other evidence predicates are unchanged.

`prepare_grid_layout_site.py` invokes no compiler. Its immutable catalog snapshot
is `grid-layout-rust-only-catalog-b0781104.json`, SHA-256
`c9879cb868de5f0ad5cc21cb427401bca2bc7e6f3d344196fd625449c0e8b753`.
The current core revision in that snapshot is unused metadata. The site records
`implemented: []`, `moonbit_execution: not_run`, and `comparison_status: not_run`.
Future candidate registration cannot relabel or alter this baseline profile.

## Actual capture protocol

The dedicated Linux Chromium job checks out the exact PR head (or dispatch SHA),
then will open one unchanged Rust application at
DPR1 and use real `Playwright.page.setViewportSize` calls in this sequence:

    500 → 399 → 400 → 401 → 500 → 399 → 400 → 500

Every viewport is 500 pixels high. The profile measures browser `innerWidth`,
`innerHeight`, `devicePixelRatio`, canvas DOM bounds and canvas backing dimensions
at every state. It retains the original trusted window-resize event stream,
operation acknowledgements and post-delivery animation-frame waits. A per-document
identity and exactly one main-frame navigation reject reload-based substitution.
WindowOptions alone is not accepted as browser viewport evidence.

Each state requires two separately requested complete original PNGs with identical
decoded RGBA. All startup/stability attempts and failure screenshots are retained.
The exact input PNGs are never cropped, resampled, rewritten or replaced. The
strict Pillow 12.0.0 decoder accepts only noninterlaced RGB/RGBA8 PNGs at the four
requested widths and height 500, checks chunk framing/CRC/order, bounded complete
zlib data, row filters, single-frame structure and absence of trailing bytes.

The runner saves observed component geometry even on a sample that fails source
constraints. The verifier ignores report-provided geometry, expected coordinates
and pass flags, rereading the originals independently.

## Bounded observation and source hypotheses

Measurement starts with the full original RGBA image. It identifies the largest
connected exact-color component for each source color: white header, red table of
contents, green content, blue ad and black footer. Text holes and detached border
or glyph fragments do not supply geometry. Each region must have substantial
area, at least 75% fill density and a unique dominant connected component.

The resulting fill-pixel bounds and counts are observations. They are not assumed
layout boxes. Separate source-derived mathematical checks use the default
`Window` rem size 16 (`window.rs:2144`) and the example's styling:

- Width 399 selects the strict `<400` single-column branch, in original source
  order. Header/footer are 3rem high; TOC/ad are 5rem; content takes the remaining
  height after four quarter-rem gaps.
- Widths 400, 401 and 500 select five columns and five rows. `grid_cols(5)` and
  `grid_rows(5)` lower to `repeat(5,minmax(0,1fr))`; equal tracks use the available
  dimension after four gaps.
- Header/footer span all columns. Content spans three columns and three rows;
  ad spans three rows. TOC has fixed 14rem height, visibly overhanging its one-row
  area without enlarging the zero-minimum fraction track.
- Sparse row-major placement puts the footer below the occupied spans. The
  lower-left grid area below TOC remains gray instead of being backfilled.

Observed solid-fill edges have a declared maximum 2-physical-pixel uncertainty
from border and fractional raster edges. Fill-to-fill separation can therefore
have up to 4 pixels of combined edge uncertainty. Exposed gray gaps are measured
independently as contiguous original-color runs, with at most 1 pixel uncertainty
against the source 4px gap. Long original gray scanlines through horizontal gaps,
vertical gaps and the lower-left vacancy are also checked. Exact layout-box edges and guaranteed single-pixel geometry regression detection
are not claimed. These tolerances are fixed before real execution; no fixture coordinates are fitted to make CI pass.

Repeated widths must restore exactly the independently measured component bounds,
counts and densities. Complete RGBA stability is required within each state, but
full-image equality between different visits is not a claim of this profile.

Source rem 16 is an expectation checked against visible sizes, not a directly
instrumented runtime rem measurement. The unchanged viewport example can
establish bounded responsive paint output. It cannot independently prove nested
container-query assigned-size isolation, callback counts, invisible work, general
layout semantics or a reusable MoonBit core implementation.

## Evidence and sensitivity

The actual HTML, all executable/document/font responses, each generated worker
response and server-served hashes are retained. Worker derivation is independently
scoped to `grid_layout.js` using the exact Cargo.lock-pinned wasm_thread 0.3.3
revision `0cf96c7708dfb97ccf3da50347e25edcf75d6937` and its complete 964-byte source
template. The actual served WASM must embed that template and each complete
pinned font. Arbitrary blobs, unretained dependencies, foreign URLs and altered
HTML/host bytes fail closed. Playwright 1.56.1 and actual SwiftShader graphics
metadata are required; requested launch flags alone are insufficient.

Every screenshot, runtime response and support file is independently retained
under a portable unique filename. Runtime/session/state/document/operation and
viewport bindings prevent swapping evidence. Verifier reads reject symlinks,
hardlink aliases, traversal, oversized inputs, missing files, changed hashes,
wrong current revision/tree/catalog and dirty tracked suite files. Every retained
suite input must also byte-match its committed HEAD blob; unrelated untracked
work cannot impersonate a committed source input. Reverification
appends a unique result rather than overwriting an earlier record.

Negative controls are corrupted-evidence sensitivity tests, not executed engine
mutants. They include ignored/wrong-sized resizes, a stacked 399 image padded to
400 so a wrong threshold fails even with correct dimensions, changed restoration
fill, swapped TOC/ad, shortened content span, truncated TOC/header, missing footer,
corrupt gaps, missing/untrusted/reordered resize delivery, wrong canvas backing,
reload/different-document substitution and changed source/font/runtime/worker/
HTML/catalog bytes. They never replace actual success evidence.

Explicitly unverified: text content/shaping/glyph raster, dashed-border fidelity,
rounded-corner fidelity, shadow fidelity, exact full-image/native parity,
MoonBit comparison, internal callbacks/nested isolation and other browsers,
GPUs, viewports or DPRs.

## Dedicated CI and local checks

`.github/workflows/grid-layout-oracle.yml` is an isolated 75-minute Linux job with
15-minute capture and 10-minute independent verification bounds. It installs the
fixed nightly and bindgen, builds only the unchanged grid binary, captures all
states and uploads original evidence plus site even on failure. It does not run
a native app or build any candidate. Existing historical workflows and harness
profiles are unchanged.

After committing a clean checkout, CI executes:

    python3 web/scripts/prepare_grid_layout_site.py --out _build/grid-layout-browser-lab
    python3 web/scripts/build_rust.py --upstream-source _sources/zed --site _build/grid-layout-browser-lab --target-dir _build/grid-layout-rust-target --oracle-only --extra-example grid_layout
    BROWSER_EVIDENCE=_build/grid-layout-oracle-evidence PLAYWRIGHT_ROOT=/path/to/pw node web/tests/grid-layout-oracle-browser.mjs _build/grid-layout-browser-lab
    node web/tests/verify-grid-layout-results.mjs _build/grid-layout-oracle-evidence

Local checks require no Rust compilation or browser artifacts:

    node --test web/tests/grid-layout*.test.mjs
    python3 -m unittest discover -s web/tests -p 'test_grid_layout*.py' -v
    python3 -m unittest discover -s web/tests -p 'test_rust_packaging.py' -v
    python3 -m unittest discover -s web/tests -p 'test_rust_subset.py' -v

Pillow 12.0.0 is required for decoder tests; local checks reused an existing cache.
The local environment intentionally did not compile Rust or download browser
artifacts because free space must remain above 1 GiB. A verified CI artifact will
report `rust_source_profile_verified`, candidate `not_implemented`, comparison
`not_run`, and conformance `not_claimed`. Exact-head independent artifact review
is still required before treating this as an established baseline.
