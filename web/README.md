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

## Build and verify the actual pair

Requires Python 3.12+, Node.js, MoonBit, Rustup, and clean checkouts of the
exact candidate and upstream revisions in `examples.json`.

```sh
rustup toolchain install nightly-2026-10-14 --profile minimal --component rust-src --target wasm32-unknown-unknown
# Install wasm-bindgen-cli 0.2.129; CI verifies the release archive SHA256.
node --test web/tests/contracts.test.mjs
python3 web/scripts/build_moonbit.py --gpui-source /path/to/gpui.mbt --upstream-source /path/to/zed
python3 web/scripts/build_rust.py --upstream-source /path/to/zed
python3 web/scripts/serve.py _build/browser-lab
```

Open `http://127.0.0.1:8080/`. Rust WASM is under `rust/`; MoonBit JS is
under `moonbit/`. Both iframe URLs use the same origin and fixed 500×500
logical viewports. There is no external runtime URL or substitute Rust image.
The Rust loader compiles and starts the actual upstream `hello_world` binary
from the standalone `crates/gpui_web/examples/hello_web/Cargo.toml`. Rust
source and upstream platform/renderer implementations remain unchanged.
Builds use disposable archives; original source checkouts remain read-only.
The standalone dependency lock is retained in `web/rust/Cargo.lock` and Cargo
uses `--locked`. The measured Rust/MoonBit compilers, binding generator,
source pins, font digest, WASM/binding file digests and lockfile accompany the
site in `build-manifest.json`. The MoonBit compiler is measured, not pinned.
Existing output directories are rejected instead of deleting previous work.

For browser evidence (install Playwright as in `browser-examples.yml`):

```sh
PLAYWRIGHT_ROOT=/path/to/playwright-install node web/tests/candidate-browser.mjs _build/browser-lab --require-rust
python3 web/scripts/compare_screenshots.py _build/browser-example-evidence
```

The E2E serves under `/gpui-conformance/`, verifies real WASM loading, the
same origin and cross-origin isolation, and samples six actual swatch RGB
pixels in each rendered canvas. It retains both 500×500 screenshots, the
whole comparison, narrow-layout screenshot, actual MoonBit scene, HTTP and
console records, trusted browser click/key delivery traces, and operation
results. Selecting a missing port clears both frames. Reload waits for fresh
iframe documents rather than accepting the old ready document. Click/Enter
probes only establish browser delivery and unchanged static color probes;
they do not establish GPUI application event semantics. This upstream example
has no interactive application controls.

`result.json` separates overall execution, candidate, Rust, verified items,
unverified items and exact screenshot pixel differences. A missing Rust
bundle fails `--require-rust`; one candidate screenshot cannot pass a pair.
`difference-x4.png` visualizes exact RGB differences at four times brightness.
Differences are measured without tolerance or masking and are never promoted
to native conformance. Captures are integer-coordinate 500×500 browser page
regions, without image rescaling; raw canvas bounds, clip coordinates and
equal fractional offsets are recorded. They are not intrinsic canvas readbacks.
Text shaping, border dash phase, shadows, other
examples, IME, hardware GPU browsers and native parity remain separate work.

[The pixel investigation](PIXEL_ANALYSIS_20261016.md) accounts for all 1,641
saved unequal pixels and corrects the host's dash geometry. The remaining
1,532 unequal pixels are still reported as different. Reproduce the spatial
analysis with `python3 web/scripts/analyze_screenshots.py _build/browser-example-evidence
--font _build/browser-lab/moonbit/IBMPlexSans-Regular.ttf --baseline web/evidence/20261015`.

## Cloudflare hosting and existing GitHub Pages

The upstream WASM uses atomics and shared memory. The top-level comparison
page, both frames and assets need cross-origin isolation. Ordinary GitHub
Pages cannot apply this site's `_headers` file as HTTP response headers.
Hosting only Rust on another origin does not give a non-isolated Pages parent
the required isolation. Therefore the complete lab is packaged as one
Cloudflare Worker static-assets deployment with `_headers` containing
COOP `same-origin`, COEP `require-corp` and CORP `same-origin`.

```sh
npx wrangler@4.92.0 deploy --config wrangler.browser-lab.jsonc
```

The `browser-lab-cloudflare.yml` manual workflow first builds and tests the
pair, then publishes to the dedicated Worker `gpui-conformance-browser-lab`.
It requires `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` in the
`browser-lab-cloudflare` GitHub environment (or repository secrets).
The old Pages workflow is disabled with an explicit explanation; it cannot
overwrite the existing published site. Once a Cloudflare URL exists, an
existing Pages site can link to it as a top-level navigation. An unisolated
Pages iframe is not presented as a working shared-memory runtime host.
Neither workflow runs deployment on push or pull request.

Current execution evidence and deployment status are recorded in the PR.
The browser work leaves `pins.json`, native adapters, runners, existing
conformance scenarios and `harness.yml` unchanged.
