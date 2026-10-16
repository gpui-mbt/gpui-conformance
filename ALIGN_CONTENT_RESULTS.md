# Wrapped-line content alignment — 2026-10-16

## Scope and identities

This adds `align_content` start/center/end/stretch to the bounded headless
conformance contract and the gpui.mbt layout API. The baseline has no named
align-content API and always stretches wrapped line boxes. Its differences
show a missing capability, not a regression of an existing named mode.

- Read-only Zed/GPUI: `d9afb21688e04f89d9e94d96d33eb530aef90886` (GPUI 0.2.2).
- Engine baseline: `afca4b1a479792de8a566ecdbf47ddd6e8d33675`.
- Engine candidate: `c0ba99d36bfe5793e3801d5e9430f6fb9d1d6326`.
- Baseline suite: [`a510e66c1a61da3b094156e60fe460238a2d2a9e`](https://github.com/gpui-mbt/gpui-conformance/tree/a510e66c1a61da3b094156e60fe460238a2d2a9e).
- Executed candidate suite: [`380af03595025db042a85a79126b491c6b15b2b8`](https://github.com/gpui-mbt/gpui-conformance/tree/380af03595025db042a85a79126b491c6b15b2b8), using an explicit candidate revision.
- Linux x86_64, Rust 1.98.1, MoonBit 0.1.20261012 / moonc 0.10.15+943464bfa.

Rust invokes actual GPUI `content_start`, `content_center`, `content_end`, and
`content_stretch` public builders and measures completed GPUI/Taffy bounds.
MoonBit maps the same field into the library's `AlignContent` and
`FlexTreeStyle::with_align_content`, then measures request-layout → prepaint →
painted element bounds. No adapter implements line distribution or emits
expected geometry. The upstream source is unchanged.

## Real executions

| Execution | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| Baseline, 36 new cases | 15 | 21 | 0 | 0 |
| Candidate, 36 new cases | 36 | 0 | 0 | 0 |
| Candidate measured-width control | 0 | 36 | 0 | 0 |
| All ten headless corpora | 191 | 0 | 1 | 2 |

Each of the four modes has nine cases: positive row/column space, row/column
wrap-reverse, normal/reverse overflow, a single wrapped line, a nowrap control,
and an auto-cross child with min/max limits. Every case compares complete root
and child rectangles at the existing 0.0001 logical-pixel tolerance and device
scale 2. Rust asserts the actual TestWindow scale; MoonBit uses the existing
opt-in snapping boundary. This does not configure or qualify native windows.

For two row lines of heights 10 and 14, gap 4, in cross extent 64, start places
them at 0/14, center at 18/32, end at 36/50, and stretch at 0/32. In extent 20,
center uses signed overflow (-4/10), and end uses -8/6. With wrap-reverse,
explicit start anchors at the flex start and can overflow before the physical
origin (10/-8). Default stretch keeps its existing safe physical-start overflow
behavior (18/0). A single wrapping line still honors content alignment; nowrap
ignores it. Content alignment is separate from within-line item alignment.

The control perturbs a measured MoonBit child width by one pixel after real
execution. All 36 nonempty cases detect it. All 155 previously executed
headless cases still match. IME remains unsupported and native window/GPU
placeholders remain unverified.

## Reproduction and retained artifacts

The current suite pins the candidate. With exact engine/upstream checkouts:

```sh
python3 run.py --upstream-source /path/to/zed --moonbit-source /path/to/gpui.mbt \
  --scenarios align_content_scenarios.json --output _build/align-content-positive-published
python3 run.py --upstream-source /path/to/zed --moonbit-source /path/to/gpui.mbt \
  --scenarios align_content_scenarios.json --negative-control \
  --output _build/align-content-negative-published
```

The baseline branch above uses identical corpus bytes and intentionally lacks
the new MoonBit mapping; its authoritative run is
`_build/align-content-baseline-published`. The combined run is
`_build/align-content-regression-published`, with retained `scenarios.json`
concatenating original, boundary, fractional-grow, gap-budget, fractional-shrink,
min/max, flex-wrap, space-between, distributed-spacing, and align-content corpora.

[The result index](results/align-content-linux-x86_64-20261016.json) records the
exact manifests and comparisons with SHA-256 identities. Each run uses clean
immutable source/suite revisions, retained executables, fresh execution challenges,
raw output, and build/execution timing/status. An index alone is not execution
proof: the comparator requires the full retained artifact directory. Exploratory
local snapshots remain separate from these public-revision results.

Local validation also passes 61 portable contract tests, 29 catalog contract
tests, and 38 adversarial execution/evidence checks. The engine passes formatting,
warning-denied all-target checks, all 84 layout tests on four targets, full tests
(516 each wasm/wasm-gc/JS, 729 native), and 142 Python checks. These local results do not imply cloud CI success. Before merge, the paired
PRs require all exact-head CI green and explicit independent
GPT-6.1-sol/xhigh approval with no P1 findings or blockers.

## Limits

This covers finite definite-size bounded flex layouts. Distributed align-content,
RTL/reversed main flow, margins, baseline alignment, general intrinsic sizing,
text shaping, native input, IME, and GPU pixel equivalence remain outside scope.
No physical host, OS permission, browser-lab UI, or catalog record is changed.
The catalog retains its separately recorded earlier result; this batch does not
relabel historical evidence.
