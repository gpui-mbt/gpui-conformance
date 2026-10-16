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

[The text_layout exact RGB analysis](TEXT_LAYOUT_PIXEL_ANALYSIS_20261016.md)
measures the original 800×600 PR #25 captures: 9,797 / 480,000
unequal pixels, with regional counts and separate provenance. The browser CI
now writes raw and visual text-layout differences and a JSON analysis in
addition to the untouched hello_world comparator. Exact text-layout parity
and independent Rust layout metrics remain unverified.

The retained hello_world screenshot measurements apply only to hello_world.
The catalog labels text_layout as implemented but unverified until its own
retained comparison evidence exists. The build and E2E execute the real pair
and retain separate text_layout candidate/Rust images and candidate scene output.

## Implemented port: `text` (typography)

This port follows the real unchanged upstream `crates/gpui/examples/text.rs` at
the pinned revision, source blob `7fa2a157601277cb3c0d58de045f1d5a6f21ab2e`.
Its independent 920×720 selection is **not** the earlier `text_layout` fixture.
The initial `.ZedMono` font-switch button, Unicode/CJK/emoji samples, upstream
20-column character grid, and paired inverse specimens over the original 1.33
type scale are created by `moonbit/text/text.mbt` using gpui.mbt
`Element → request_layout → prepaint → SceneSnapshot`. The layout is
recomputed from browser-provided text measurements, rather than screenshot
coordinates. The unmodified Rust `text.rs` binary is built as WASM alongside it.

Browser-host adaptations are explicit: the default Zed Mono family uses
the pinned Lilex face; subsequent family selections rely on browser/system
fallback; font metrics/shaping run in Canvas. Trusted canvas pointer and
keyboard events cycle the upstream five families. Wheel/arrow input controls
a host-side viewport clip/translation; that operation is **not** a native
gpui.mbt scroll implementation. The upstream uses GPUI hit testing, event
dispatch and overflow scrolling, so interactive/native equivalence is not
established by this adapter. Grid rows use the available 888-pixel inner width;
the original 62-pixel cell bases shrink through gpui.mbt flex resolution, with
browser-measured text minima. The final row retains upstream's flexible empty
cells. All 20 columns fit the 920-pixel viewport with the tested font choices.

The ASCII type-scale phrase wraps within its 900-pixel padded content width.
The host supplies shaped-prefix measurements, while MoonBit chooses word breaks
(with character fallback), creates every line as a real Element, and computes
specimen heights and the scroll extent from the resulting layout. Per-specimen
frame diagnostics retain the complete chosen lines. Font changes remeasure and
reflow the specimens and clamp a prior scroll offset to the new content extent.
This remains a fixture-local wrapping adapter; Canvas prefix measurements are
only a proxy for native glyph advances, and broader text semantics are unverified.

The browser workflow captures both 920×720 outputs and the candidate scene,
then exercises the font cycle and scroll with trusted browser events. Image
artifacts are inspection evidence, not pixel equality. Unicode fallback,
line shaping, CSS/native font resolution, interaction semantics, compositor
presentation and native parity are **unverified**.

## Implemented port: `text_wrapper`

The third port follows the same pinned upstream revision and unchanged
`crates/gpui/examples/text_wrapper.rs`; its source blob is recorded in
`examples.json`. It retains the static 800×600 logical viewport, the three
red-bordered flex/normal text boxes, blue single-line ellipsis and two-line
ellipsis rows, green truncation rows including a three-line clamp, a black
nowrap row, and the final wrapped multilingual paragraph. The source includes
English, Chinese, Japanese, a long word and a URL. Page padding and gaps
are 8 pixels; the three small samples use 16-pixel text in 26-pixel line boxes,
and the remaining six runs use 20-pixel text in 32-pixel line boxes.

`moonbit/text_wrapper/text_wrapper.mbt` makes the wrapping and elision
decisions in MoonBit from browser-measured font inputs. It builds gpui.mbt
Elements and uses request_layout → prepaint → SceneSnapshot for the final
text items, boxes and clipping. The pinned candidate
`01818aa4e96fc21d1676f747a6b23d91445648a1` has no text-wrapping API, so this
is an example-local algorithm rather than a library capability claim.
The host segments with `Intl.Segmenter('und', { granularity: 'grapheme' })`
and measures individual grapheme advances, whole-string prefix widths, and
the 16/20-pixel ellipsis widths. It does not choose line breaks. MoonBit uses
the advances for truncation/clamping and the prefix positions for final
wrapping, following the pinned source's word-character classification,
CJK/URL break candidates, long-word fallback and trailing whitespace/ASCII
punctuation trimming. The clamp limits are two lines with an ellipsis and
three lines with an empty affix. Per-run frame diagnostics expose the
original text, chosen lines, truncation/clamp flags, content budget and bounds.

Browser font measurement and grapheme segmentation are explicit host
boundaries. Native scalar/glyph iteration can choose different boundaries
from the port's indivisible graphemes; Canvas prefix widths are only a proxy
for native glyph positions. The fixed paragraphs have no explicit newlines
or leading indentation, and the helpers do not claim broader paragraph
semantics. For the small row, the two visible-overflow flex samples use
`ceil(measured text width)` plus borders as an explicit candidate minimum-main
constraint, following upstream's automatic minimum-content measurement. The
overflow-hidden third sample has a zero content minimum and absorbs shrink.
The positions still come from gpui.mbt flex resolution; this adaptation does
not claim general native intrinsic-sizing equivalence.
Shaping, ligatures, bidi, font fallback, kerning, exact Unicode line breaking,
rasterization and native parity remain unverified.

The catalog labels text_wrapper as implemented and unverified. It includes
retained actual candidate/Rust screenshots with source-run provenance, without
inferring a pixel-conformance result. The hello_world 1,532-pixel difference is
never attached to either new text example.

## Implemented port: `hello_web` (Prime sieve)

The fourth counterpart follows unchanged upstream
`crates/gpui_web/examples/hello_web/main.rs` at the pinned revision (source blob
recorded in `examples.json`). The original 640×560 viewport, 10M/50M/100M
presets, 12 half-open chunks, progress bar/dots, accumulated history, colors
and labels are preserved. Despite its title, the upstream computation is a
brute-force 6k±1 primality test, and the MoonBit port executes that same algorithm.
It never substitutes saved counts or a smaller range for a selected preset.

MoonBit owns the application state, count algorithm, chunk partitioning,
preset/start actions, stale/duplicate-result checks, progress and history.
Its real gpui.mbt Element tree supplies layout, pointer dispatch and
SceneSnapshot output. Canvas only supplies font measurements/rounded fills
and browser pointer coordinates. A bounded pool of 2–12 module Web Workers
imports the compiled MoonBit runtime and computes the 12 real chunks; the
browser host handles scheduling, message transport and teardown. The displayed
thread count is the candidate's actual pool capacity, not a claim of scheduler
or thread-count equality with Rust. Workers are terminated when exhausted,
on errors and on pagehide. A worker error is visibly terminal until reload.

Browser E2E runs the full 10M preset and verifies 664,579 primes, all 12
contiguous chunk ranges, progress/history and resource cleanup. It executes
the unchanged upstream WASM with a trusted browser click and retains both the
actual rendered result and OCR confirming its count. Selection of 50M/100M,
repeated clicks while running, restart and leaving during a run are covered;
the full 50M/100M computations are not exercised by CI. Unit tests cover
primality, half-open boundaries, stale/duplicate messages and worker errors.

Elapsed milliseconds are CPU-task observations including host scheduling.
They are separate from load timing, are not renderer-startup benchmarks and
do not establish a performance ranking. Exact pixel equality, font shaping,
native parity, browser scheduler equivalence, keyboard accessibility and
full 50M/100M execution remain unverified. The catalog must keep this example
implemented/unverified with no borrowed hello_world result.

All catalog entries now have example ports. Their execution evidence does not
establish native or pixel conformance; see each port's boundaries below.

## Implemented port: `tree`

The unchanged pinned `crates/gpui/examples/tree.rs` (blob
`891be4790a59ae258da3380d2ef54fba26979346`) is now paired with
`moonbit/tree/tree.mbt`. The upstream default is 50 wrapping operations around
an initial node: **51 colored blocks**, not 50. The innermost block is red;
wrapping cycles blue, CSS green (`0,128,0`), yellow, red, so the outermost block
is green. Every block retains `p_0p5()` (2 logical pixels), and the viewport
is 300×300. The static browser fixture keeps the upstream default; it does not
invent a depth selector or interactive behavior.

The MoonBit tree uses real auto-sized Elements, nested padding, stretched
single-child columns, request_layout → prepaint → paint_snapshot. This
single-child column composition represents the upstream block flow. There
are no hardcoded scene rectangles, browser text measurements, fonts or new
paint extensions. The colored outer block is the window root and fills the
300×300 viewport. This mirrors the pinned `window.rs` call to
`stretch_auto_size_to_fill` in `taffy.rs`: auto root dimensions stretch before
layout, while explicitly sized roots retain their size. Recursive intrinsic
measurement derives a 200-pixel-high first child and a 4-pixel-high innermost
block. Unit tests cover all 51
bounds/colors/paint positions and alternative depths 0, 1, 3, 12 and 63;
they do not establish upstream equivalence at those alternative depths.
The pinned library's bounded tree depth remains unchanged.

The Rust standalone package did not register `tree` as a binary. The build
therefore relocates its Cargo manifest into a disposable sibling harness,
retains its dependencies/config/locked versions, and adds a binary entry
pointing to the original `tree.rs`. **No archived upstream file is edited.**
`build-manifest.json` records this packaging adaptation and its manifest digest
separately from source modification. Example logic, renderer and platform
implementation remain pinned upstream bytes.

The browser test captures the actual pair at an integer-aligned 300×300
viewport, retains the candidate SceneSnapshot, checks all nested ring pixels
including the root-only bottom 96 rows, and compares the complete RGBA image
without masking or thresholds. Negative controls reject displaced bounds,
missing nodes, wrong paint order, changed colors and a shrink-wrapped root.
The first actual Rust run exposed exactly 28,800 incorrect pixels from treating
the window root as a 204-pixel-high child. The corrected Element root models
upstream root sizing directly; no canvas-background workaround is used. Candidate-only execution must
record Rust as not run. Exact image equality, when observed, applies only to
that recorded browser run; native parity, arbitrary depth, display presentation
and other rendering backends remain unverified. Catalog status stays unverified.
Paired acceptance currently runs at DPR 1. A DPR 2 attempt was rejected because
the pinned Rust backing canvas stayed 300×300 while the candidate was 600×600;
no resampling is permitted and DPR 2 equivalence remains unverified.

## Rust-only baseline: `scrollable`

`web/oracles/scrollable.json` records the unchanged upstream `scrollable.rs`
source blob `c81795618875aecf06e06043bd1709c48630b58f` at the same browser pin.
`build_rust.py --extra-example scrollable` builds it without adding a claimed
MoonBit counterpart to the catalog. The opt-in binary is recorded separately in
`build-manifest.json` as `rust_oracle_only` with `candidate: not_implemented`.
The normal Rust build still includes only implemented catalog examples.

The baseline uses a direct 500×500 browser viewport at DPR 1, trusted wheel
input, and full actual screenshots. Any text/border coordinates derived from
those images describe observed movement; the unchanged example exposes no
private scroll offsets or ScrollHandle telemetry. Browser event logs establish
input delivery only. No CSS scroll container or JavaScript-computed scroll
state stands in for GPUI behavior. The first execution of this oracle remains
pending CI while its baseline harness is being introduced.

Core integration is required for a faithful MoonBit counterpart: current
`gpui.mbt` main `d4debae44d16bc9b6f631122b4b4164a3e1b64b5` has standalone
`ScrollState`, but no scroll viewport, descendant translation or clipping in
its Element lifecycle. Upstream `div.rs` applies the same wheel delta to each
eligible ancestor, clamps offsets during prepaint, and applies inherited
content masks to both painting and hit testing. A future candidate must test
those semantics instead of assuming residual-delta scroll chaining. Native,
other-DPR, private-state and MoonBit equivalence are not claimed by this baseline.

## Upstream example inventory

Checked 2026-10-16 against upstream main
`32b16ce2ada96ba86c9052e456a2642102b39b7a` and the existing browser pin
`5a5fbe79917971a4d52a96b6ddb04da198a5012e`. Both contain the same **41 top-level
Rust example files**, with identical blob IDs. This count excludes asset/support
subdirectories. Six of these now have browser counterparts: hello_world, text,
text_layout, text_wrapper, input and tree. The two additional counterparts,
dynamic_fonts and Prime sieve, live under `crates/gpui_web/examples/hello_web`.
Eight catalog entries therefore do **not** mean all upstream examples are covered.

The remaining 35 top-level examples are: a11y, active_state_bug, anchor,
animation, data_table, drag_drop, focus_visible, gif_viewer, gradient,
grid_layout, image_gallery, image_loading, layer_shell, list_example,
mouse_pressure, move_entity_between_windows, on_window_close_quit, opacity,
ownership_post, painting, paths_bench, pattern, popover, scrollable, set_menus,
shadow, system_notifications, tab_stop, testing, toggle_headless, uniform_list,
window, window_movable, window_positioning and window_shadow. These are an
inventory of missing counterparts, not unsupported-feature verdicts or passes.

## Build and verify the actual pairs

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
(500×500 for hello_world, 800×600 for text_layout/text_wrapper and 640×560 for Prime sieve). There is no external runtime URL or substitute Rust image.
The Rust loader compiles and starts every implemented example in `examples.json`
using the standalone `crates/gpui_web/examples/hello_web/Cargo.toml`. Rust
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

The E2E serves under `/gpui-conformance/` and verifies real WASM loading,
the same origin and cross-origin isolation. For hello_world it samples six
actual swatch RGB pixels in each rendered canvas and retains both 500×500
screenshots, the whole comparison, narrow-layout screenshot, actual MoonBit
scene, HTTP and console records, trusted browser click/key delivery traces,
and operation results. Each text example has its own 800×600 candidate/Rust
screenshots and candidate scene. text_wrapper also retains
`text-wrapper-pair.png` and separate operation/load-run entries in `result.json`.
These artifacts establish execution and inspectable differences; they do not
supply a new catalog measurement. Selecting a missing port clears both frames. Reload waits for fresh
iframe documents rather than accepting the old ready document. Click/Enter
probes only establish browser delivery and unchanged static color probes;
they do not establish GPUI application event semantics. This upstream example
has no interactive application controls.

The generated test catalog can link its implemented entries to this live lab
when the GitHub Actions repository variable
`CATALOG_BROWSER_LAB_BASE_URL` is set to the verified worker root URL. Leave the
variable unset until the deployment URL is confirmed. The catalog link opens
the static sample at `/?example=hello_world`; it does not make the sample
interactive. text_layout and text_wrapper each link to their own static pair;
missing ports remain unlinked.

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

## Implemented port: `dynamic_fonts`

The sixth counterpart follows unchanged upstream
`crates/gpui_web/examples/hello_web/dynamic_fonts.rs` (source blob
`33d4d6cc1721b24f86241ae53a417313c4ae0ed3`), with its 900×500
viewport, dark background, IBM Plex Sans, Devanagari and emoji samples,
download/status messaging, and original Google Fonts raw-TTF URL.

`moonbit/dynamic_fonts/dynamic_fonts.mbt` uses gpui.mbt Element →
request_layout → prepaint → SceneSnapshot to position seven text rows, with long download errors wrapped and reflowed.
Browser-measured text widths are inputs; positioning and SceneSnapshot
emission are MoonBit outputs. Each row inherits the pinned GPUI `TextStyle`
default `phi()` line height (1.618034 times its font size), snapped to the
nearest device pixel with midpoint ties toward zero. At scale 1 the line
heights are 39, 26, 65, 52, 26, 26, 26 logical pixels.
The 32-pixel padding and 16-pixel gaps then place the rows at y = 32, 87, 129,
210, 278, 320, 362. MoonBit unit tests and the normal paired browser E2E
assert all seven line boxes, including after a mocked font-registration
redraw and at device scales 1.5 and 2. The source rules are in the pinned
`crates/gpui/src/style.rs` (`TextStyle::default`), `geometry.rs` (`phi`),
`elements/text.rs` (`TextLayout::layout`), `window.rs` (`pixel_snap`) and
`util.rs` (`round_to_device_pixel`). The candidate uses its scale-aware
layout path to snap the example-local line boxes, padding and gaps.
These assertions establish the example's logical layout only.
The initial font is the bundled upstream
IBM Plex Sans. When the known example text contains Devanagari, the host
makes **one** request to the exact upstream TTF URL, validates the response,
registers the returned bytes with FontFace, and redraws after completion.
Network failure, HTTP errors, empty data and font-decoding errors are shown
in the scene; no retries are made until a fresh page load. The remote
font is **not** bundled. Source attribution and the upstream SIL OFL note
remain visible.

**Evidence boundary:** the browser does not expose GPUI's
`on_missing_glyphs` callback or Cosmic Text's `add_fonts`. A known Devanagari
range probe and the browser's FontFace/Canvas fallback are explicit host
extensions. Their triggering and shaping behavior are not equivalent to
the native GPUI text system. Loaded status confirms FontFace registration,
**not** Devanagari glyph coverage or pixel parity. Remote CDN reachability,
font rasterization, fallback order, emoji shaping, and macOS/native
equivalence remain unverified. The paired browser test exercises a
deterministic error route and a mocked FontFace-success route separately;
neither is presented as real CDN/shaping conformance.

## Implemented port: `input` (TextField browser adapter)

This port targets the pinned, unchanged `crates/gpui/examples/input.rs`
(source blob `106d06dc7e3ab225d0fda1aee009f601767b34da`) and uses the
300×300 upstream viewport and initial `Type here...` placeholder.
`moonbit/input/input.mbt` uses gpui.mbt's `TextField`,
`TextComposition`, `TextMeasurement`, Element layout, and
`SceneSnapshot` output. The host `moonbit/site/input-host.mjs` alone
owns browser `beforeinput`, keyboard, ClipboardEvent, and IME composition
event delivery. The DOM textarea never owns the document value.

The port covers click caret placement, forward/backward drag selection,
Shift-click/drag selection, arrows/Home/End,
Backspace/Delete, copy/cut/paste, Ctrl/Cmd+A/Z/Y, redo, composition preview,
commit, cancellation, and reset. It supplies a **fixed 12px-per-scalar
measurement proxy**, not browser font shaping or native GPUI text layout.
Selections are UTF-16 indices and the model rejects splitting a surrogate.
The browser cancels the canvas's native mouse-focus action before focusing its
transport textarea. Pointer capture delivers movement and release outside the
canvas; cancellation, capture loss, blur, reset and page exit end the gesture.
MoonBit owns the active selection gesture and reuses the pinned TextField's
validated Shift-click path for drag updates. Hit testing retains captured
coordinates beyond the horizontal viewport, accounts for horizontal scroll,
and maps dragging above/below the single line to its document start/end. This is an example-local adapter, not a new library
pointer API.

The paired Chromium regression suite enters editing through trusted visible
canvas clicks, including Reset, rather than directly focusing the hidden
textarea. It covers click-to-type, caret placement, trusted copy/cut, directional
and Shift drag ranges, outside release, capture loss, blur cleanup, supplementary
Unicode, scrolled/offscreen text and above/below-line endpoints. Pointer cancellation is tested with a synthetic
PointerEvent; it is not hardware-touch evidence.

The upstream uses grapheme segmentation; this port currently exposes scalar
boundaries instead, so grapheme movement equivalence (combining marks and
ZWJ emoji) is **UNVERIFIED**. `TextField` owns undo/redo; these shortcuts
are an additive candidate behavior absent from this upstream example.

Synthetic Chromium composition event tests cannot activate a genuine
Japanese IME or validate its candidate window, platform-specific selection
reporting, or keyboard-layout changes. Actual Japanese IME, Rust–MoonBit
interactive equivalence, exact pixel matching, font shaping and native
composition behavior remain **UNVERIFIED**. Recorded independent browser
runtime behavior must be distinguished from these boundaries.
