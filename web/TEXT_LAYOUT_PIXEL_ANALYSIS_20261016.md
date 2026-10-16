# text_layout 800×600 exact-pixel investigation — 2026-10-16

## Grounded inputs and baseline

Original unmodified screenshot PNGs and SceneSnapshot come from [PR #25's successful paired browser run](https://github.com/gpui-mbt/gpui-conformance/actions/runs/38840675529), artifact **browser-example-evidence** (ID **12020809243**). Rust/WASM and MoonBit/JS each produced a real 800×600 image. No comparison images or fixture implementations were recreated.

**Exact raw RGB result: 9,797 / 480,000 pixels different (2.0410417%).** No masking, tolerance, substitution, translation or resampling. The original hello_world comparator is retained unchanged at **1,532 / 250,000** differing pixels.

| Exclusive region (using saved SceneSnapshot for spatial ownership) | Differing | All assigned |
| --- | ---: | ---: |
| Plain left/center/right text | 1,049 | 6,235 |
| Underlined text ×3 | 3,403 | 13,369 |
| Strikethrough text ×3 | 3,376 | 15,283 |
| Nowrap text + percent in bordered boxes | 1,763 | 9,251 |
| Styled ABCD | 206 | 1,276 |
| Blue borders of both boxes | **0** | 4,108 |
| Remaining box interiors | **0** | 7,389 |
| Background | **0** | 422,289 |
| Outside root on last fractional-crop row | **0** | 800 |
| **TOTAL** | **9,797** | **480,000** |

The one-pixel support padding assigns pixels to scene items for diagnosis only. It excludes **zero** pixels from the comparison, including the background, blue border, and last screenshot row. Both original page captures use the same x=0, y=0.640625 fractional offset, recorded by the E2E. The last 800 captured pixels are outside the root because of the original fractional clip; they do not validate bottom-edge clipping.

## Distinguishing semantic layout from raster differences

- The saved candidate has 15 text scene items, two box quads and two clip chains. The observed vertical ink bounding extents match between Rust and MoonBit in all 15 text items. Horizontal extents differ by approximately 0–2 pixels. **These observations are not equivalent to live Rust layout/glyph telemetry.**
- The three underline runs show a dense Rust scanline at y=139, 173, 207, while Canvas distributes coverage over y=138–139, 172–173, 206–207. The three strike runs similarly use Rust y=233, 267, 301 versus Canvas y=232–233, 266–267, 300–301. This is a reproducible **output/coverage** difference, not sufficient evidence to rewrite MoonBit layout offsets.
- Both blue box boundaries have exactly zero changed pixels; only their text changes. Overflow clipping cannot be assessed from strings fitting inside the boxes, despite clip chains being present.
- Styled ABCD differs at 206 pixels; the port requests weight 800 and has a SemiBold bundled face. Resolved Rust font-face IDs, glyph advances and font-style metrics are **not** captured. No weight-equivalence claim is made.
- Rust Cosmic/Swash/GPU glyph coverage and Chromium Canvas fillText/fillRect have distinct rendering paths. The evidence supports a raster-path contribution but **does not conclusively split** 9,797 pixels into layout vs shaping vs coverage/compositing.

**Change decision:** No MoonBit text layout semantic error is demonstrated by these screenshots. The existing text_layout implementation is not changed or shifted to optimize screenshots. Pixel equality is **FAIL**, semantic text-layout equivalence **UNVERIFIED**. The next discriminating step is paired Rust/Candidate glyph advance, baseline and primitive decoration traces plus an overflow/clipping case.

## Reproduction

The paired CI continues running the old 500×500 path and adds the independent 800×600 path. The new comparator validates the original PNG dimensions, screenshot capture bounds, equal origins, SceneSnapshot identity/viewport, and 15 text items. It writes **text-layout-difference-raw.png** (absolute RGB), **text-layout-difference-x4.png** (visualization only), and **text-layout-comparison.json** (exclusive spatial counts, 15 per-item ink bounds, line scans, file SHA256, capture offsets, source and runner metadata). These files are uploaded with the paired browser evidence artifact.

    python3 -m pip install Pillow==12.0.0
    python3 web/scripts/compare_screenshots.py _build/browser-example-evidence
    python3 web/scripts/compare_text_layout.py _build/browser-example-evidence
    python3 -m unittest discover -s web/tests -p 'test_text_layout_comparator.py' -v

Synthetic comparator guard tests: changed background pixels and border pixels remain counted; exact equality is zero; wrong image size or mismatched capture offsets fail. The original three tests passed in the local analysis environment. A fourth regression now checks that decoration scan windows subtract the capture offset when converting scene coordinates to image coordinates; it passes locally with the other three. The current-head paired browser CI is evaluated separately.

## Original run provenance

| Item | Measured value |
| --- | --- |
| Upstream Zed commit | 5a5fbe79917971a4d52a96b6ddb04da198a5012e |
| gpui.mbt commit | 01818aa4e96fc21d1676f747a6b23d91445648a1 |
| Conformance lab built commit | 127f654c2730c7e1d4eb7e002741c481cda7b0a7 |
| Rust toolchain | rustc 1.101.0-nightly (822182db4 2026-10-13) |
| wasm-bindgen | 0.2.129 |
| MoonBit | moon 0.1.20261012, moonc 0.10.15+943464bfa |
| Browser E2E environment | Linux x64; Node v22.23.3; Chromium 141.0.7390.37; SwiftShader requested |
| text-layout-rust.png SHA256 | 31b7b372b069003c346f9a3bc6f1b86cc06d93ee4f1a14a5918f807587da4818 |
| text-layout-moonbit.png SHA256 | 7aa7b524bbb77f3cc73f0a942aaa0891750114cb63170fe227ba63dabff2fe94 |
| text-layout-moonbit-scene.json SHA256 | 039e03b966771e4ae81152ef211918f71794761e779fd21adc7977758464f1a3 |

The JSON written in each CI run also records source pin commits, runtime and font SHA256 values, capture origins, browser version and all per-item ink bounds. This document describes **only the PR #25 saved artifact**; future CI results may differ by browser/runtime, and must not reuse this pixel tally.

**Status:** Original PR #25 paired E2E PASS. Saved-image local analysis and three new synthetic comparison tests PASS. Exact text_layout pixel equality FAIL. Semantic layout/Rust glyph tracing, forced overflow clipping, native/hardware GPU/macOS/other browsers **not run / unverified**.

