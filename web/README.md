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
The dash lengths, seam and corner parameterization follow the pinned GPUI
shader. Exact border coverage, the Canvas shadow kernel, font measurement,
shaping and rasterization remain unqualified. A matching scene or screenshot
of the candidate alone does not yield a conformance pass.

## Implemented port: `text_layout`

The second port follows the unchanged pinned `crates/gpui/examples/text_layout.rs`.
Its source blob is recorded in `examples.json`. The 800×600 logical viewport,
16-pixel padding, 8-pixel gaps, left/center/right alignment, underline and
strikethrough rows, two blue bordered nowrap boxes, and styled `ABCD` are retained.
The first letter requests weight 800 and `C` italic, using the same bundled IBM
Plex Sans faces as upstream (the closest bundled bold face is SemiBold).

`moonbit/text_layout/text_layout.mbt` constructs a real gpui.mbt Element tree
and emits SceneSnapshot text items and clip chains. Browser-measured text widths
are inputs; candidate layout computes the positions. Because this pinned gpui.mbt
only has start/center/end justification, a flexible spacer composes the two-box
`justify_between` layout. This is an example port, not a new library API claim.
Font metrics, weight/style, and decoration drawing are explicit Canvas host
extensions. Decoration formulas follow the pinned GPUI text renderer, but font
shaping, rasterization, exact pixel equality and native parity remain unverified.

The retained hello_world screenshot measurements apply only to hello_world.
The catalog labels text_layout as implemented but unverified until its own
retained comparison evidence exists. The build and E2E execute both real pairs,
and retain separate text_layout candidate/Rust images and candidate scene output.

## Other upstream examples

`text`, `text_wrapper`, `input`, `dynamic_fonts`, and `hello_web` (Prime sieve)
retain their real upstream names and source paths. They remain marked
**gpui.mbt not implemented**. Selecting one clears both old runtimes; it never
loads a substitute. Text input needs editing, selection and IME independently,
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
under `moonbit/`. Both iframe URLs use the same origin and the selected upstream logical viewport
(500×500 for hello_world, 800×600 for text_layout). There is no external runtime URL or substitute Rust image.
The Rust loader compiles and starts the actual upstream `hello_world` and `text_layout` binaries
from the standalone `crates/gpui_web/examples/hello_web/Cargo.toml`. Rust
source and upstream platform/renderer implementations remain unchanged.
Builds use disposable archives; original source checkouts remain read-only.
The standalone dependency lock is retained in `web/rust/Cargo.lock` and Cargo
uses `--locked`. The measured Rust/MoonBit compilers, binding generator,
source pins, lab commit and tracked-dirty state, font digest, WASM/binding file digests and lockfile accompany the
site in `build-manifest.json`. The MoonBit compiler is measured, not pinned.
The MoonBit source link uses the recorded lab commit so it survives deletion
of the feature branch. For a dirty local build, that link identifies its base
commit; use a clean commit for a published artifact.
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

The generated test catalog can link its implemented entries to this live lab
when the GitHub Actions repository variable
`CATALOG_BROWSER_LAB_BASE_URL` is set to the verified worker root URL. Leave the
variable unset until the deployment URL is confirmed. The catalog link opens
the static sample at `/?example=hello_world`; it does not make the sample
interactive. text_layout links to its own static pair; missing ports remain unlinked.

`result.json` separates overall execution, candidate, Rust, verified items,
unverified items and exact screenshot pixel differences. A missing Rust
bundle fails `--require-rust`; one candidate screenshot cannot pass a pair.
`difference-x4.png` visualizes exact RGB differences at four times brightness.
Differences are measured without tolerance or masking and are never promoted
to native conformance. Captures are integer-coordinate 500×500 browser page
regions, without image rescaling; raw canvas bounds, clip coordinates and
equal fractional offsets are recorded. They are not intrinsic canvas readbacks.
Text shaping, exact border coverage, shadows, unimplemented
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
Select `feat/browser-side-by-side-lab` before integration, or `main` after
the PR is merged. Other refs cannot publish. A preflight job checks that both
credentials are present before starting the Rust/MoonBit build; the same
environment applies to the publishing job.
The old Pages workflow is disabled with an explicit explanation; it cannot
overwrite the existing published site. Once a Cloudflare URL exists, an
existing Pages site can link to it as a top-level navigation. An unisolated
Pages iframe is not presented as a working shared-memory runtime host.
Neither workflow runs deployment on push or pull request.

Current execution evidence and deployment status are recorded in the PR.
The original [2026-10-15 results](RESULTS_20261015.md) are retained as the
baseline. The [2026-10-16 correction and complete spatial accounting](PIXEL_ANALYSIS_20261016.md)
measure **1,532 / 250,000 unequal pixels (0.6128%)**: text 856, rounded corners
377, straight dashed borders 299. Execution passes; exact pixel equality
remains **different**. A successful build or CI run does not mean deployment
has run.
The browser work leaves `pins.json`, native adapters, runners, existing
conformance scenarios and `harness.yml` unchanged.

## Practical synchronized load observations

“Start both / measure load” starts a fresh pair from one parent
`performance.timeOrigin + performance.now()` timestamp. Both iframe navigation
assignments happen in one JavaScript task with no `await` or ready barrier;
which side goes first alternates, and the assignment gap is displayed. That
gap measures assignment order, **not exact network request simultaneity**.
No runtime startup is hidden behind preloading. The same start is used for
both sides rather than subtracting each frame's own navigation start.

The page reports comparable response milestones from each iframe's Navigation
and Resource Timing entries:

- **Document response:** end of the iframe HTML response.
- **Main payload received:** latest response end of the explicitly declared
  main files: MoonBit runtime JavaScript and its external font, versus Rust
  generated JavaScript bindings and WASM (which embeds fonts). This endpoint
  excludes host modules and worker dependencies and is not all-network-idle,
  compilation completion, or rendering completion. If any declared file lacks
  timing evidence, the metric is unavailable.
- **Runtime signal:** separate implementation-specific diagnostics. MoonBit's
  Canvas2D draw calls have returned; Rust's WASM initialization has returned
  and a canvas exists. These endpoints are deliberately not ranked as a fair
  render-speed comparison.
- **First presented frame:** unavailable on both sides. Neither signal proves
  presentation; the existing screenshot/probe E2E remains independent evidence.

Cache mode is **normal browser cache, uncontrolled**. The fresh run ID changes
only each iframe document URL. JavaScript, WASM, and font URLs remain stable;
this is neither a cache flush nor a cold-load benchmark. Browser/CDN caches,
code caches, GPU/connection warm-up and contention between simultaneously
loading panes can affect the observation. Repeat runs are useful practical
observations only. No winner, statistically stable benchmark, or native parity
is inferred.

Timing reports must come from the expected same-origin iframe and current
run/example/side. Repeated clicks cancel earlier results; missing examples
clear them. Host failure and a bounded 60-second timeout produce unavailable
results, and late/duplicate signals cannot replace them. `gpuiLoadComparison`
is the inspectable current-run snapshot used by browser tests.

`node --test web/tests/*.test.mjs` covers timestamp and generation contracts.
`PLAYWRIGHT_ROOT=/path/to/playwright-install node web/tests/load-timing-browser.mjs`
uses explicitly synthetic runtimes to exercise common-clock plumbing,
alternating order, rapid reload, missing ports, failures, timeout and rejected
stale/spoofed messages. These tests establish instrumentation behavior only;
they never supply conformance results or Rust/MoonBit speed measurements.
