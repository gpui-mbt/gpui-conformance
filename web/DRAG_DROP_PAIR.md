# Independent current drag-drop source-behavior pair

This harness executes unchanged upstream `drag_drop.rs` and the compiled
MoonBit candidate separately. The candidate core is pinned to the published, independently reviewed commit
listed below. The pair is unverified: source-derived unit fixtures do not
establish execution or runtime parity. No placeholder or historical build
manifest can establish current paired provenance. Fresh CI execution and
independent artifact review remain required.

## Historical baseline remains immutable

The independent Rust-only baseline is PR #49, run `38945456947`, artifact
`12067400103`, SHA-256
`66e7c1ad7a5f6a07693bfd43e87ddd92753ad552fccc706ce28e268f1c368681`.
Its signed CI merge checkout is `bc65f1eeefeb2a74602aee2e4268655174de667d`.
The independently reread evidence contains 108 original PNGs, 54 stable states,
54 trusted operations, 15 behavior/input controls and nine provenance controls.
In particular, down `(400,232)` followed by up `(400,420)` has no intervening
move and no activation. These are historical Rust-only results.

The source-only comparator, runner, verifier, oracle record and artifacts keep
their original pins and labels. Recheck those artifacts only at their original
clean checkout. They must not be relabeled as current paired evidence. The
current paired workflow replaces the active source-only job only after the
candidate and reviewed core are integrated. It never downloads historical PNGs
or substitutes them for a fresh current Rust execution.

## Exact source and current build provenance

- Upstream: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`, tree
  `990fb995914d51a546b20e5cf0382dafc105c299`.
- Unchanged source: `crates/gpui/examples/drag_drop.rs`, blob
  `8f038ef3308fee9b097e7289665c9fa47cd6945b`, SHA-256
  `4011afde7c64fac2559b78918e6fdabdc563fe9f7591c74425d72da906dcc47a`.
- Current candidate core: `fc53cb382c66f68bfc1b3e1cc72d01056cd3c625`, tree
  `c9ec59c5fbdbd84548b7d6ffe2c99b8403509db9` (published PR #97; source review
  approved the identical tree; CI and runtime qualification remain separate).
- Current clean suite HEAD/tree and exact catalog bytes must match the retained
  build and catalog. Historical/mismatched HEAD, tree, dirty checkout or changed
  catalog bytes fail independently.
- `build_moonbit.py` checks the exact core checkout and compiles/tests the real
  catalog candidate. `build_rust.py --implemented-example drag_drop` builds only
  the unchanged implemented Rust subset. Source-only/extra-oracle manifests are
  ineligible for a pair.

The workflow retains the actual MoonBit compiler version, Rust toolchain,
wasm-bindgen version, build commands/logs, relocated Cargo manifest, unchanged
source, eight source-embedded fonts, candidate source/package/tests, builders,
harness/decoder source, actual compiled JS/WASM and served host/renderer/font
responses. Both actual runtime HTML document responses are mandatory and pinned
to the exact source `web/rust/index.html` and `web/moonbit/site/index.html` bytes.
Directory document URLs retain their actual query in the independent server
observation and normalize only the retained artifact path to `index.html`.
Every document, script, stylesheet or font resource, and every requested `.js`,
`.mjs`, `.wasm`, `.ttf`, `.css` or `.html` dependency, must be retained and hashed,
including static imports shared with other routes. Current HTML/host/renderer/
source bytes are checked against the actual clean suite checkout. Missing,
modified or extra inline execution cannot be blessed by changing generated-site
HTML and report-provided hashes together.
The served Rust WASM must contain every complete retained source font.

## Independent browser execution

`drag-drop-pair-browser.mjs SITE` executes Rust; `--candidate` executes MoonBit.
Each invocation uses its own fresh browser context and session identifier and
never reads the other runtime's captures, application state or coordinates.
The initial original PNG supplies that runtime's source/target geometry. The
immutable `makeProfile` and paint/input predicates are imported directly from
the historical source comparator without changing tolerances, exclusions,
event counts, source colors or the profile.

Both sides use exactly 800×600, DPR1, Playwright 1.56.1 and Pillow 12.0.0.
SwiftShader launch flags, actual `SystemInfo.getInfo` graphics data and console
logs are retained. Each operation uses `CDP.Input.dispatchMouseEvent`; passive
capture listeners observe actual trusted DOM pointer delivery and independently
record any compatibility mouse events. There are no synthetic DOM events,
screenshot overlays, screenshot-derived application state or model-driven
verdicts. Optional candidate diagnostics never choose expected state or pass.

Every state retains at least two independently requested full-viewport original
PNGs with identical complete decoded RGBA. All unsuccessful stability attempts
and prior successful captures remain; failure also retains its report and
available full-frame screenshot. State/session/runtime/operation ownership and
per-request ordinals prevent accidental swapped-state/cross-runtime reuse.
A separate raw trusted-input file is checked against the report. Missing,
fabricated or extra delivery cannot be silently accepted as browser suppression.

## Unchanged 54-operation / 54-state scope

Independent original-byte checks cover:

- Left-down without movement and strict **greater than 2** move-only activation
- Sticky activation after moving back toward the origin
- Coordinate-changing release without an intervening move
- Blue, red and source green `(0,128,0)` accepted drops
- Accepted release, release without a target, half-open target right edge
- Source hover, suppression during drag, target fill and exact border widths
- Centered 120×50 half-alpha preview for both baseline positive grips
- Release cleanup and actual duplicate-up delivery or suppression

`compare-drag-drop-results.mjs` reopens every original retained byte stream,
decodes every attempted PNG with the unchanged strict decoder, recomputes each
runtime's geometry/profile/paint/input predicates, then compares the independently
derived measurements. Report-provided geometry and checks cannot supply a
verdict. Verification reruns preserve earlier results rather than overwriting
original evidence.

Corrupted controls independently exercise each runtime: wrong activation,
stickiness, selected color, green128, target border, hover suppression, preview,
cleanup, target acceptance edge, coordinate/event order/count, missing or
untrusted delivery, fabricated duplicate-up, swapped captures, cross-runtime
borrowing, altered original pixels, compiled assets, hosts/renderers/fonts,
source/core pins, source-only relabeling and historical/dirty checkout identity.
Unit fixtures are explicitly synthetic and cannot certify a runtime pair.

The current evidence protocol is `drag_drop_paired_pointer_v3`; the unchanged
54-operation behavior profile is preserved. Review of initial source commit
`11f6fa0b6f07e3b9f095d234bf1f940a31c2c72e` found that document responses had been
omitted by an extension-only filter. A source-only negative control reproduced
the gap for both runtimes before this correction. No browser pair had been
qualified under that initial format. The correction requires the actual HTML
entrypoints and tests missing/changed HTML, inline-script injection, document
route/query ownership and the original current source bytes.

## Source-generated worker responses and portable evidence

The first actual current pair, run `38951347981` / job `117143210222`, failed
under v2. Its original decoded log (SHA-256
`c153e818aa970dc72212ef06eaa6a1995fc15d42ded00e4a1ff9601a02f1fbfd`)
records an executed blob-script hash compared with an undefined file pin. Its
URL-derived evidence filename contained a colon, so artifact upload also failed.
No original current PNG, trusted-input or executed-response artifacts were
available for independent review. The log-reported candidate capture is not
qualified paired evidence, and no pixel mismatch was established by that failure.

Version 3 retains this generated code and validates its exact source derivation:

- The current locked dependency is `wasm_thread` 0.3.3, revision
  `0cf96c7708dfb97ccf3da50347e25edcf75d6937`. The exact dependency lock and
  [original 964-byte module template](https://github.com/zed-industries/wasm_thread/blob/0cf96c7708dfb97ccf3da50347e25edcf75d6937/src/wasm32/js/web_worker_module.js)
  are retained source inputs. The copied fixture is licensed under the adjacent
  original MIT license. Its SHA-256 is
  `43f6beda7493508d3d8b6760d680195b08cc756db89e8aba6bbd5e1ce6da2ca4`.
- The complete template must occur in the fresh actual served Rust WASM; both
  original WASM and loader bytes must match the current build hashes. The expected
  body is the exact single `WASM_BINDGEN_SHIM_URL` replacement implemented by
  [the pinned source](https://github.com/zed-industries/wasm_thread/blob/0cf96c7708dfb97ccf3da50347e25edcf75d6937/src/wasm32/utils.rs#L40-L73),
  using the fresh actual retained loader response URL, including its server port.
- Each original blob-script body is reread separately and compared byte-for-byte
  with that derivation. Blob origin must match the same current Rust document and
  loader origin. Missing responses, changed/appended bodies, other runtimes,
  stale loader URLs, unknown scripts and other generated-worker kinds fail closed.
  Expected bytes never substitute for a failed browser body read.
- Source caches the blob URL, so multiple requests for that URL are retained as
  distinct original files and response IDs. Blobs have browser observations;
  they do not get fabricated HTTP-server observations.
- Every dynamic evidence filename uses a fixed ASCII prefix, response ordinal
  and full SHA-256 of the JSON-encoded original identity. Raw URL/path text never
  enters a filename. The original URL, resource type, response ID and runtime/
  session binding remain in the report. Validators reconstruct filenames and
  require unique IDs, so separators, colons, Unicode, escaped paths and collisions
  from lossy slash replacement cannot overwrite or block artifact upload.

For source diagnosis only, replacing the marker with the failed log's loader
URL produces 1,000 bytes and SHA-256
`1d49b54f3942aed12fce148a7409b23e44ac32a342b747acd5fece6d6b75a8fb`,
exactly the logged digest. This reconstruction is not a recovered original
response. Historical WASM was used only for source research, never as current
runtime evidence. Fresh current v3 CI artifacts and independent review remain
required. The HTML pins, fixed behavior profile and original pixel/input gates
are unchanged.

## Claim boundary and CI budget

This bounded profile does not establish exact text/OCR, glyph antialiasing,
full-image equality, GPU shadow blur-kernel equality, native parity,
native/global capture, touch, OS drag, other DPRs/browsers/viewports/GPUs,
foreign payloads, rejecting predicates or nested/overlapping targets.
Internal payload/grip identity needs separate source/core tests. Negative or
fractional grips are source-derived candidate behavior only; they are not added
to or claimed by the unchanged 54-state baseline.

The dedicated current paired job has a 75-minute limit, 15 minutes for each
independent runtime and 10 minutes for verification. Candidate capture and the
verifier still run after Rust capture failure when build/browser setup succeeded.
Both build logs, site and all evidence are uploaded on success or failure.
The ordinary matched-examples job does not substitute for this source profile.
