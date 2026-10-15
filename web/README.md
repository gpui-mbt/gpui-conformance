# Matched upstream examples

The browser lab uses **the upstream GPUI examples as its specification**.
Weekboard and unrelated synthetic fixtures are no longer loaded on the MoonBit
side. Select one upstream example name for both panes.

## Implemented port: `hello_world`

Source: `zed-industries/zed`, revision
`5a5fbe79917971a4d52a96b6ddb04da198a5012e`,
`crates/gpui/examples/hello_world.rs` (blob
`d18cb048726d6953edef9ea482d92bac05993d33`).

The MoonBit implementation is `moonbit/hello_world/hello_world.mbt`. It uses
**gpui.mbt Element → request_layout → prepaint → SceneSnapshot**, rather than a
JavaScript recreation of the demo or hardcoded layout results. The candidate
library is pinned to `01818aa4e96fc21d1676f747a6b23d91445648a1` in
`examples.json`; native/headless `pins.json` remains untouched.

The port retains the 500×500 logical viewport, gray background, centered
`Hello, World!`, six red/green/blue/yellow/black/white squares, 32-pixel square
sizes, 12-pixel vertical gap, 8-pixel horizontal gap, blue outer border, and
contrasting dashed rounded borders. The text uses 20-pixel IBM Plex Sans from
the pinned upstream font assets, with a 32-pixel line box (upstream's rounded
`phi()` line height). The original is static: no invented buttons or input
behavior is added.

**Scope boundary:** rounded/dashed borders and shadow drawing are explicit
Canvas host extensions, not additions to the published SceneSnapshot API.
The dash phase, Canvas shadow kernel, font measurement, shaping, and
rasterization are not qualified against the Rust renderer. A matching scene
or screenshot of the candidate alone does not yield a conformance pass.

## Other upstream examples

`text`, `text_layout`, `text_wrapper`, `input`, `dynamic_fonts`, and
`hello_web` (Prime sieve) are listed using their real upstream names and source
paths. They are **not implemented** in MoonBit yet. Selecting one clears both
old runtimes and shows the missing-port state; it never loads a substitute.
Text input must eventually cover editing, selection and IME independently,
and Prime sieve must execute real background work rather than replay counts.

## Build and verify

Requires Python 3.12+, Node.js, MoonBit, and clean checkouts of the exact
candidate and upstream revisions in `examples.json`.

```sh
node --test web/tests/contracts.test.mjs
python3 web/scripts/build_moonbit.py \
  --gpui-source /path/to/gpui.mbt \
  --upstream-source /path/to/zed \
  --out _build/browser-lab
python3 -m http.server 8080 --bind 127.0.0.1 -d _build/browser-lab
```

The build script verifies both revisions and tracked cleanliness, checks the
upstream example's blob, stages a temporary copy of the candidate, runs the
MoonBit package tests, builds the real JS module, and includes the font with
its upstream license. It never changes either source checkout. Existing output
directories are rejected; select a fresh `--out` rather than deleting work.
Compiler version and output digests are recorded in `build-manifest.json`.
The installer in CI currently follows the official distribution; the compiler
version is measured, **not pinned**.

`browser-examples.yml` runs the host contracts, MoonBit compilation/unit tests,
and Playwright against the actual compiled candidate under a GitHub Pages-like
subpath. It retains a real screenshot and a report separating candidate
execution from the **unexecuted Rust comparison**. It does not fabricate a
Rust reference image or infer parity from the candidate's output.

## Rust side and Pages

The Rust WASM runtime is **not bundled by this change**. Enter the base URL of
a separately hosted upstream gallery; `hello_world` selects its
`hello-world` route. The host must allow framing and satisfy upstream's
shared-memory WASM isolation requirements. A failed/missing Rust frame never
becomes a pass. Both frames retain 500×500 logical pixels, with scrolling
rather than asymmetric scaling on narrow displays.

The manual Pages workflow now runs the same build and candidate browser tests
before publishing generated assets, instead of publishing source-only HTML.
It remains limited to `feat/browser-side-by-side-lab`, is not dispatched by a
push, and may replace the repository's published Pages site when deliberately
run by a maintainer. Pages setup and a complete same-origin Rust bundle remain
separate work. No merge or Pages deployment is performed by this change.
