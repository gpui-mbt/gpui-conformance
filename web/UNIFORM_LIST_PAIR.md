# Compiled `uniform_list` browser pair

This profile is separate from the immutable unchanged-Rust baseline. It builds
only `web/moonbit/uniform_list` against the exact public core revision/tree in
`web/pairs/uniform_list.json`. Existing examples, focus and drag contracts use
their existing paths. The shared host adds one module and one input/metric route.
The original example, Rust capture, original comparator, source profile, frozen
catalog fixture and baseline workflow remain unchanged by this implementation.

## Genuine production boundary

The compiled candidate calls production `UniformList::new`, real recursive
request-layout/prepaint, `ElementTree::scroll_wheel`, and list-specific stable-row
click ownership. It retains the core's returned offset. Production core measures
two prototype calls, selects the lazy visible range, assigns checked stable IDs,
computes the complete 50-row extent, places current row subtrees and emits clips.
Neither JavaScript nor this example computes a list range, row Y, scroll limit or
pointer-selected row. There are no spacers, eager 50-row paint trees, replaced
core masks or manually positioned row rectangles.

Each source row is auto-sized, with actual horizontal padding8 and an intrinsic
text leaf. Source-authored line height is16×phi, not an observed Rust26px input.
At DPR1 genuine core measurement currently rounds the outer row to26. The core
returns width/height, all positions and all clip chains. A transparent leaf is
lowered by compiled MoonBit into text runs at that exact core-provided anchor.
The opaque white root, 300×300 viewport,50 `Item n` labels and pointer cursor
follow the unchanged upstream source.

The browser can observe the original source's paint and wheel response. Its
`println!` click is not observable in the WASM host, so neither actual Rust click
callbacks nor Rust lazy-factory semantics are claimed by this browser profile.
Supplemental test-platform semantics remain a separately labeled gate.

## Explicit source-led ASCII text boundary

Source5a has two different font stages:

- [Cosmic shaping](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui_wgpu/src/cosmic_text_system.rs#L758)
  uses `Hinting::Disabled`.
- [Swash glyph rasterization](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui_wgpu/src/cosmic_text_system.rs#L530)
  uses `hint(true)`.
- [Glyph paint placement](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/src/window.rs#L4850)
  quantizes device X to four subpixel variants, with halves toward zero.

Canvas default text measurement rounds the tested font's advances to integral
pixels. `geometricPrecision` supplies unhinted metrics but also changes the
raster. The bounded adapter therefore measures all label widths, prefix widths
and individual glyph advances with geometricPrecision/normal kerning, restores
the Canvas state, then gives those raw metric arrays to MoonBit. MoonBit derives
the ASCII glyph origins from prefix width minus current glyph advance and
performs the source's quarter-device-pixel X quantization. Each text_run retains
its original core anchor bounds, transform and clip chain. Canvas auto mode
rasterizes each character. Scene IDs derive from the stable text anchor and
character slot; the verifier checks every character, ID, order, origin and clip.

This is deliberately only the source ASCII `Item 1` through `Item 50`. It does
not implement a general complex-text shaper, fallback, ligature or native font
parity. Font bytes, source line-height, all host metrics, actual raster mode and
the compiled scene are retained independently.

## Original execution and independent verification

The job first builds/captures/verifies unchanged source5a Rust in a separate
Rust-only site. Its actual generated worker response bodies, not merely source
templates, remain separately retained and verified by the existing worker guard.
The candidate is launched independently with a fresh runtime session. Its wheel
corpus is derived from the independently reread original Rust initial PNG, never
candidate range telemetry. Both runs preserve every original full300×300 PNG,
including failed stability attempts, and require two independent identical-RGBA
captures of each state. No crop, resize, synthetic reference or PNG rewriting is
performed.

The candidate retains actual HTML and every executed JS/font response, a separate
server-byte log, actual graphics metadata, trusted DOM wheel events, raw CDP
acknowledgements, every per-state compiled scene and independently remeasured
host typography input. Unexpected external/blob/data candidate execution fails.
Rust's actual worker responses are checked with the unchanged original guard.
Current suite revision/tree, frozen Rust catalog and current live catalog are
bound separately. The verifier rereads the exact published core checkout and
compares every retained dependency source to its actual Git object; compiler,
commands, test/build output, source bytes and original font hashes are retained.
An explicit `--local-core-override` emits `unqualified_local_override`, which the
qualifier rejects. It never substitutes a guessed SHA for a published pin.

Each runtime must independently establish50 distinct complete row rasters,
full1300-style measured content extent, overlap-linked translations, both axis
rules, endpoint clamps, top restoration and actual partial surface-edge ink.
Cross-runtime image differences remain descriptive, not a full-image/AA claim.
The original strict predicate (`uniform_list_exact_glyph_envelope_v1`) requires
exact measured pitch, vertical ink band, row ink-left support and all50 row glyph
envelopes. Its result, including any failure, is always written first as a
separate immutable JSON artifact with all50 row differences and image statistics.

A separately named `uniform_list_bounded_placement_scroll_clip_v1` result checks
exact measured pitch, row ink-left support and vertical bands for every row; independent
complete raster progression, surface clipping and wheel/endpoints; and the
candidate's source-bound glyph count, identity, order, origins, anchor bounds and
clips against its separately retained metric inputs. It does not require equal
horizontal glyph support. Every right-edge difference remains in its output,
without an accepted tolerance. If those support differences exist, its status is
`bounded_placement_scroll_clip_verified_with_typography_mismatch`. This status
never replaces the original failed strict result and is not full conformance.

Corrupted-evidence controls cover motion, endpoints, X fallback, mixed-axis
behavior, glyph origin/order/cardinality, core pin, font, scene masks, extent and
factory traces. These are comparator-sensitivity controls, not executed engine
mutants. Actual production API tests are run separately; semantic mutation
qualification belongs to the supplemental diagnostic pair.

## Local findings and current gate

At implementation time, bounded candidate-only tests used existing
Chromium141.0.7390.37; no Rust or browser was built locally. Earlier original
captures are retained separately from subsequent corrections:

1. Whole-label Canvas auto: correct26px pitch/top8/bottom19/left8, but wider
   integral advances (`Item1`49px; `Item10`59px) and one-pixel right-edge mismatch.
2. Whole-label geometricPrecision: unhinted widths48.080093/57.680115, but top
   glyph ink6px instead of Rust8px, demonstrating the shaping/raster distinction.
3. Compiled per-glyph lowering: correct source stages; unquantized X had a
   one-pixel narrow `Item1` envelope.
4. Source quarter-pixel X quantization: initial measured geometry matches Rust,
   and24 states/48 original PNGs pass independent candidate raster progression.
   Some individual glyph right edges still differ by one pixel between the
   Canvas and Swash rasters. The strict exact-envelope predicate rejects this. The separately named bounded
   placement/scroll/clip result can pass while explicitly reporting that mismatch.

These are explicitly unqualified development observations compared with the
historical approved original Rust artifact, not current exact-pair CI evidence.
None is relabeled onto the final public core pin. Actual final bounded qualification
requires the dedicated workflow and independent original-artifact review. No
full-image, native, OCR, Rust click/laziness or internal-mask parity is claimed.

## Commands

From a clean committed suite and exact core/upstream checkouts:

    python3 web/scripts/build_uniform_list_pair.py --gpui-source _sources/core --upstream-source _sources/zed --out _build/uniform-list-candidate
    python3 web/scripts/prepare_uniform_list_site.py --out _build/uniform-list-rust-site
    python3 web/scripts/build_rust.py --upstream-source _sources/zed --site _build/uniform-list-rust-site --target-dir _build/uniform-list-rust-target --oracle-only --extra-example uniform_list
    BROWSER_EVIDENCE=_build/uniform-list-oracle-evidence PLAYWRIGHT_ROOT=/path/to/pw node web/tests/uniform-list-oracle-browser.mjs _build/uniform-list-rust-site
    node web/tests/verify-uniform-list-results.mjs _build/uniform-list-oracle-evidence
    BROWSER_EVIDENCE=_build/uniform-list-pair-evidence PLAYWRIGHT_ROOT=/path/to/pw node web/tests/uniform-list-pair-browser.mjs _build/uniform-list-candidate _build/uniform-list-oracle-evidence
    node web/tests/verify-uniform-list-pair.mjs _build/uniform-list-pair-evidence _build/uniform-list-oracle-evidence _sources/core

`.github/workflows/uniform-list-pair.yml` preserves both sites and all original
runtime evidence even on a failed build, capture or comparison. Rechecks append
new verification files instead of replacing the initial result.
