# Reverse flex flow: bounded headless differential

This independently authored 68-case bounded diagnostic compares actual GPUI
`5a5fbe79917971a4d52a96b6ddb04da198a5012e` (tree
`990fb995914d51a546b20e5cf0382dafc105c299`) and public MoonBit candidate
`50373f51aa0cf8b4adc0adbdd665879008723bfb`, tree
`0c584786b2d76546ef99f34671173f6c9580d85a`, from
[core draft PR #123](https://github.com/gpui-mbt/gpui.mbt/pull/123).
This is an explicitly selected diagnostic reference, consistent with the
recent runtime diagnostic work. It is separate from the suite's older overall
compatibility target `d9afb21688e04f89d9e94d96d33eb530aef90886` in pins.json.
No differential result here is attributed to d9afb216. A provenance check
caught the initial incorrect assumption that the supplied checkout matched
that legacy target; the build helper now enforces the actual diagnostic pin.
It compares complete root and source-order child rectangles, not projections,
with a numeric tolerance of 0.00001 and explicit device scale 2 on both sides.
The adapters are isolated copies of the existing layout corpus adapters. No
upstream layout implementation was copied into the candidate or fixtures.

## Scope and results (5a5fbe7 diagnostic reference)

- Candidate: 68 pass, 0 mismatch.
- Process-backed negative control: 0 pass, 68 mismatch. Only the MoonBit
  observation's first child width is increased by one pixel.
- Capability-negative control with reversal disabled: 58 mismatch, 10 pass.
  The ten passes are direction-insensitive singleton placements.
- Pre-feature core 7f62b92832abe00b6f792a977d2b163c3103a32c fails to
  compile this adapter with two missing reverse-constructor errors.
- Comparator/corpus contract tests: 16 pass.
- Existing portable, visual, observer and fixture contracts: 62 pass.

Both row-reverse and column-reverse cover asymmetric physical padding,
independent x/y gaps, all six justification modes, wrap and wrap-reverse with
all seven cross-line alignment modes, capped growth, bounded shrinking,
main-axis overflow, and fitting/overflowing singletons in distributed modes.
Child arrays retain authored order; reversal changes physical placement.

## Important semantics exposed by the actual oracle

Pinned GPUI's `justify_start()` and `justify_end()` builders use physical
Start/End. Reversing item flow does not reverse these physical anchors.
Overflowing space-between/around/evenly fall back to physical start. Fitting
space-between singletons remain on the reverse edge, whereas around/evenly
singletons are centered. The initial differential caught the implementation's
incorrect reversal of physical Start/End before this was corrected.

There is an explicit default boundary: the MoonBit style defaults to physical
Start, as it did before this addition. In GPUI, omitting justification entirely
uses a reverse-edge default for reverse flows. This corpus explicitly sets
justification on both implementations and does not claim equivalence of those
omitted defaults. No FlexStart/FlexEnd API is introduced by this work.

Initial unscaled observations also reproduced the known device-grid precision
boundary. Explicit scale 2 allows full rectangles, including fractional flex
resolution and distributed offsets, to be compared without hiding dimensions.

## Reproduce

Use Rust 1.98.1, a suitable MoonBit toolchain, cached Cargo dependencies, a
clean pinned upstream checkout, and a clean committed candidate checkout.
Set PATH, CARGO_HOME, RUSTUP_HOME and MOON_HOME for those tools as needed.
The build helper operates only in the requested output directory. An optional
local copy of a compatible Cargo target cache can be placed at BUILD/rust/target
before building; do not point CARGO_TARGET_DIR at a shared writable cache.

```sh
python build_reverse_flow.py --upstream-source UPSTREAM --moonbit-source CORE --output BUILD
python run_reverse_flow.py --upstream-source UPSTREAM --moonbit-source CORE \
  --rust-exe BUILD/rust/target/debug/gpui-conformance-probe \
  --moon-exe BUILD/moon/_build/native/debug/build/conformance_probe/conformance_probe.exe \
  --build-manifest BUILD/build-manifest.json --output RESULTS
# Repeat with a new output directory and --negative-control (expected exit 1).
# Build separately with --disable-reversal to test the capability-negative mutant.
python -m unittest discover -s tests -p 'test_reverse_flow.py' -v
python -m unittest discover -s tests -p 'test_*contracts.py' -v
```

Both build and runner enforce the exact upstream and public core revision/tree
pairs in reverse_flow_pins.json, including rejection of a different commit with
the same tree. The build manifest records clean source revisions/trees, compiler versions, and
executable hashes and any explicit capability mutation. The runner validates
executable hashes and clean source trees against that build manifest, validates
backend labels and every numeric coordinate, and rejects negative dimensions.
Each run records process return codes, stdout/stderr hashes,
corpus hash, source identities and per-coordinate differences. Executions use
no run token, native window, browser, image publication, or Mac automation.
No publication or CI result is claimed.

## Broad-suite qualification

An initial full Python discovery ran 667 tests and reported 9 failures,
244 errors and 3 skips. A separate unmodified bd9d268 baseline checkout ran
661 tests with exactly the same 9 failures, 244 errors and 3 skips. All 253
ordered failing/error test identities matched, with no candidate-only failure
or error identity. The six additional tests in that initial run were the new
reverse-flow contracts; subsequent hardening and public-pin enforcement expanded these to sixteen, all
passing separately. Thus the broad suite is not green in this environment;
these observed broad failures also reproduce on the unmodified baseline.
