# Browser pixel investigation — 2026-10-16

The existing PR #19 pair is reused, not rebuilt as a different demo. The saved
Rust/MoonBit screenshots and SceneSnapshot at `c447bb70` reproduce **1,641 /
250,000 unequal RGB pixels (0.6564%)**. A controlled correction to the Canvas
host's dashed-border geometry reduces this to **1,532 (0.6128%)**. The exact
comparison still reports **different**. No pixel is masked, rescaled, replaced
with reference pixels or accepted with a tolerance.

## Complete spatial accounting

[`analyze_screenshots.py`](scripts/analyze_screenshots.py) partitions every
pixel, including matching pixels, using SceneSnapshot bounds and the recorded
capture offset `(0, 0.640625)`. Rectangles use their border width and radius;
corner boxes and straight-edge bands are exclusive. A one-pixel support
margin assigns antialiasing to the primitive, without excluding anything from
the comparison. Categories describe spatial ownership, not a claim that all
pixels in a category have one causal explanation.

| Region | Saved baseline | Corrected host | Max channel delta, before → after |
| --- | ---: | ---: | ---: |
| Text | 856 | 856 | 175 → 175 |
| Rounded corners of six swatches | 377 | 377 | 249 → 66 |
| Straight dashed edges of six swatches | 408 | 299 | 255 → 39 |
| Swatch interiors | 0 | 0 | 0 → 0 |
| Blue outer rectangular border | 0 | 0 | 0 → 0 |
| Remaining background | 0 | 0 | 0 → 0 |
| Outside root | 0 (no visible area) | 0 (no visible area) | unobservable |
| **Total** | **1,641** | **1,532** | |

| Swatch ID / color | Before, corner + straight | After, corner + straight |
| --- | ---: | ---: |
| 4 / red | 63 + 68 = 131 | 63 + 50 = 113 |
| 5 / green | 63 + 68 = 131 | 63 + 50 = 113 |
| 6 / blue | 63 + 68 = 131 | 63 + 50 = 113 |
| 7 / yellow | 63 + 68 = 131 | 63 + 50 = 113 |
| 8 / black | 62 + 68 = 130 | 62 + 50 = 112 |
| 9 / white | 63 + 68 = 131 | 63 + 49 = 112 |

The intervention restores exact equality at 109 pixels, introduces **zero**
new unequal pixels, and leaves 1,532 unequal pixels. Within the border/corner
regions, the absolute RGB delta sum falls from 181,470 to 27,299 (84.96%).
This magnitude measure is supplementary; it does not turn the remaining
unequal pixels into a pass.

## Confirmed implementation error: dash lengths, seam and corner parameterization

The old host supplied `dash: [3,3]` directly to Canvas `setLineDash` on the
inset centerline of a `roundRect`. That creates approximately 19 periods on a
32×32 rectangle. It is not GPUI's definition.

The pinned
[GPUI WGPU shader](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui_wgpu/src/shaders.wgsl#L691-L892)
uses a two-border-width dash and one-border-width desired gap, with rounded
corner distances measured on the **outer radius**. It starts at the top-left
top tangent, proceeds clockwise, and increases the gap to fit a whole number
of periods. For this fixture:

- border width = 1, outer radius = 6;
- outer perimeter = `4×20 + 4×(π×6/2) = 117.699111843…`;
- dash count = `floor(perimeter / 3) = 39`;
- dash length = 2; adjusted gap = `perimeter / 39 - 2 = 1.017925945…`.

The corrected host receives `border_style: "dashed"` and splits solid Canvas
line/arc strokes in GPUI's outer-radius dash space, mapping them to the inset
stroke centerline (radius 5.5). A single ordinary Canvas dash array cannot
preserve that outer-radius parameterization on the corner arcs. The regression
contract checks the 39 periods and first dash `(140,256.5) → (142,256.5)`.
The MoonBit layout tree, six fill colors and all SceneSnapshot item bounds
remain unchanged. No GPUI upstream source is changed.

## Renderer paths and residual attribution

**Text, 856 pixels:** both sides load the same IBM Plex Sans Regular font
(`975dcda3…afa5`). The candidate's measured advance is 115 px and its title
box is `(192.5,212,115,32)`. Canvas reports ascent/descent 21/6 and baseline
235.5. Parsing the actual TTF yields 1000 units/em and hhea ascent/descent
1025/−275. The pinned Cosmic/Skrifa hhea selection gives scaled 20.5/5.5,
which derives the **same** baseline 235.5. This is a font-table/source
derivation, not instrumented Rust layout telemetry.

The saved ink bounds differ: Rust `[193,219,307,236)` and Canvas
`[194,220,307,237)`. The pinned
[WebTextSystem](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui_web/src/text_system.rs)
keeps this ASCII text on Cosmic (the Canvas fallback explicitly skips ASCII).
[CosmicTextSystem](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui_wgpu/src/cosmic_text_system.rs)
shapes through Cosmic/Harfrust and rasterizes glyphs with Swash, hinting and
GPUI subpixel variants into a GPU atlas. The candidate calls browser Canvas
`measureText`/`fillText`, which uses Chromium's text pipeline. This establishes
a renderer-path difference, not a wrong font, color, or demonstrated baseline
offset. The 856 pixels have **not** been causally split into shaping, hinting,
subpixel quantization and compositor contributions. Shifting text until the
screenshots look closer would not be a justified implementation correction.

**Borders, 676 pixels after the semantic fix:** GPUI uses signed-distance
quad coverage and a separate analytic `dash_alpha` ramp. Canvas uses Skia
path coverage with butt caps and sequential round-rect fill plus stroke
compositing. This explains why matching dash geometry does not imply pixel
equality. The remaining deltas are at corners and dash boundaries, with maxima
66 and 39 rather than 249 and 255. These are classified as residual coverage /
compositing differences; no per-pixel proof excludes every further adapter
error, and complete raster equivalence remains **unverified**. The corner
pixel count is unchanged while its RGB delta sum drops 60,721 → 16,883.

**Shadow:** the root occupies the entire clipped 500×500 canvas. Its exterior
shadow contributes no visible test area, so zero counted pixels does **not**
validate shadow parity. The pinned
[`shadow_lg`](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui_macros/src/styles.rs#L454-L465)
has two layers with negative spreads; this preview's existing one-layer
Canvas blur is an explicitly approximate host extension. Shadow behavior is
still unverified and is not changed or qualified by this investigation. A
fixture with visible space around the root is required to test it.

## Reproduction and retained evidence

- [Baseline spatial report](evidence/20261015/pixel-regions.json); the original
  images, scene and result are preserved byte-for-byte.
- [Corrected exact comparison and browser run](evidence/20261016/result.json)
- [Corrected spatial report and intervention accounting](evidence/20261016/pixel-regions.json)
- [Rust](evidence/20261016/rust.png), [MoonBit](evidence/20261016/moonbit.png),
  [exact difference ×4](evidence/20261016/difference-x4.png),
  [actual scene](evidence/20261016/moonbit-scene.json)

The existing Rust WASM bundle was reused locally and its hashes verified
against the retained build manifest. MoonBit was freshly tested/built from
the unchanged pinned candidate plus this port. The Rust screenshot SHA256
remains `37b9b0f9e4abad14593f5d3e2bf64c20f067ef31e50c758307a93462d7ec13ef`;
the corrected MoonBit SHA256 is
`262d5f8189e8e9cb232b429fa7a0bffd5db6a40c4bf5ae0d51d35b8d65dcc3be`.
CI rebuilds both runtime bundles through the existing workflow.

```sh
node --test web/tests/contracts.test.mjs
python3 -m unittest discover -s web/tests -p 'test_pixel_regions.py' -v
python3 web/scripts/build_moonbit.py --gpui-source /path/to/pinned/gpui.mbt --upstream-source /path/to/pinned/zed
python3 web/scripts/build_rust.py --upstream-source /path/to/pinned/zed
PLAYWRIGHT_ROOT=/path/to/playwright-install node web/tests/candidate-browser.mjs _build/browser-lab --require-rust
python3 web/scripts/compare_screenshots.py _build/browser-example-evidence
python3 web/scripts/analyze_screenshots.py _build/browser-example-evidence --font _build/browser-lab/moonbit/IBMPlexSans-Regular.ttf --baseline web/evidence/20261015
```

| Validation | Local observed result |
| --- | --- |
| Existing browser/catalog host contracts | PASS, 8 tests |
| Saved-pixel attribution / unexpected-fill regression / unchanged-oracle guard | PASS, 3 tests |
| MoonBit test and release JS build | PASS, 2 tests and generated runtime |
| Existing paired browser E2E | PASS: actual WASM, isolation, six RGB probes, input delivery, reload, missing-port clearing, narrow layout |
| Existing exact screenshot comparator | Completed, **different**, 1,532 / 250,000 |
| New spatial/intervention analysis | PASS accounting; equality status **different** |
| Fresh Rust compilation locally | NOT RUN; verified existing pinned bundle reused |
| Native/hardware GPU/other browsers/shadow visibility | NOT RUN / unverified |

The first local browser launch failed because the default Playwright package
expected browser revision 1234 while only 1243 was installed. The existing
matching Playwright 1.63.0 package completed the run and reproduced the original
image hashes. A MoonBit build initially failed because the old source worktree
pointed at a removed Git directory; a clean clone at the same pin built
successfully. Neither failure is reported as a passing test.

PR #19 tracks integration of the correction, final CI and deployment status.
No native or pixel-equality pass is inferred from the browser execution or
the spatial accounting.
