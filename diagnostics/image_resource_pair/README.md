# Static image resource prerequisite

This separate diagnostic proves a bounded actual asset path and numerical Rust sprite parity.
It does not register a nineteenth example or claim full opacity.rs/pixel parity.
The frozen acceptance is `ACCEPTANCE.md`; source review and an exact core commit/tree binding
in `profile.json` are required before execution. No deployment is involved.

Four source-equivalent cases: original PNG under nested .5×.5 opacity with opaque sibling;
same with 20px parent clipping; portrait100×200 contained in explicit100square; and
interleaved candidate parent-background/image painting. The browser verifies candidate compositing only.
The Rust JSON observes sprites, not the full primitive stream; cross-runtime quad/image ordering parity
is explicitly unverified. Disjoint sibling regions cannot prove cross-sibling overlay ordering. The portrait is an explicitly synthetic
geometry fixture (constant RGBA31,127,223,255), never substituted for the original icon.

Production source is pinned Zed `5a5fbe79917971a4d52a96b6ddb04da198a5012e`.
`prepare_rust.py` verifies the clean upstream commit, image source Git blob and asset bytes,
then appends a test-only observer module to img.rs without changing its existing bytes.
It builds an actual GPUI lib-test binary and observes rendered sprites after real element draw.
No GPU/Rust screenshot is claimed: the Rust test platform provides sprite geometry, mask and opacity.

The candidate compiles actual core production packages and the tiny lifecycle adapter to JavaScript,
executes it in Node and retains raw SceneSnapshot JSON. The browser consumes that exact output,
prepares identity-checked static PNG resources, and invokes the existing Canvas scene painter.
It neither calculates fit nor traverses element ancestry. Two separate Chromium processes retain
screenshots, exact RGBA readbacks and scene JSON. Six controls mutate only the browser negative-control
inputs: omit, wrong resource, double alpha, ignore alpha, stretch, and missing resource. These are
transport/presentation negative controls, not rebuilt core fault injection.

Host resource bounds are narrower than generic core metadata: static PNG, one frame, identity transform,
32 resources, each axis≤4096, aggregate4M pixels and16MiB encoded. GIF/APNG and transformed items fail closed.
ImageData in core is immutable metadata, not decoded pixels. Browser decoding/interpolation/color
conversion remain an explicitly host-provided boundary.

Run after profile binding:

    python diagnostics/image_resource_pair/run.py --core-source CORE --upstream-source ZED --output FRESH_OUTPUT

Requires pinned Rust1.98.1, MoonBit0.10.15+943464bfa, Node24.11.0, Playwright1.56.1 and Chromium.
`PLAYWRIGHT_ROOT` points at the installed Playwright prefix. Pristine suite/core/upstream checkouts are required.
The upstream checkout will contain the recorded test append afterward; do not reuse it as pristine source.

Source checks:

    node --test web/tests/image-resources.test.mjs web/tests/scene-opacity.test.mjs
    python -m unittest discover -s tests -p test_image_resource_pair.py

Full opacity still requires original GIF timing, SVG rendering, custom shadow, wavy decoration and event/animation
composition. A passed diagnostic cannot change that status.
