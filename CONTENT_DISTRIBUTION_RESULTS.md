# Distributed wrapped-line content alignment — 2026-10-16

## Scope and identities

This adds align-content `space-between`, `space-around`, and `space-evenly` to
the real conformance suite and the gpui.mbt library. The baseline library has
start/center/end/stretch but no distributed content modes. Its adapter retains
the existing unknown-mode Stretch fallback, so differences show an absent
capability rather than a regression in an existing named API.

- Unchanged read-only GPUI: `d9afb21688e04f89d9e94d96d33eb530aef90886` (0.2.2).
- Engine baseline: `edcec9a91d392af20b90c7fbbfb74170f8058f33`.
- Engine candidate: `b16210d9363aaac778d9c9240deadd392347b9d6`.
- Baseline suite: [`b85281cab8989aeb483a000c658dfef1aa0ece47`](https://github.com/gpui-mbt/gpui-conformance/tree/b85281cab8989aeb483a000c658dfef1aa0ece47).
- Executed candidate suite: [`685565bd8a9d3bd3d167e0601642f2cf6ea0b76c`](https://github.com/gpui-mbt/gpui-conformance/tree/685565bd8a9d3bd3d167e0601642f2cf6ea0b76c), using an explicit candidate revision.
- Linux x86_64, Rust 1.98.1, MoonBit 0.1.20261012 / moonc 0.10.15+943464bfa.

Rust invokes actual public GPUI `content_between`, `content_around`, and
`content_evenly` builders and observes completed GPUI/Taffy bounds. MoonBit
passes the same input into `AlignContent` and `FlexTreeStyle::with_align_content`,
then measures the request-layout → prepaint → painted element bounds. Neither
adapter distributes lines, emits expected geometry, or modifies the oracle.

## Real executions

| Execution | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| Baseline, 42 new cases | 20 | 22 | 0 | 0 |
| Candidate, 42 new cases | 42 | 0 | 0 | 0 |
| Candidate measured-width control | 3 | 39 | 0 | 0 |
| All eleven headless corpora | 233 | 0 | 1 | 2 |

Each mode has fourteen cases: empty, positive row/column, row/column
wrap-reverse, normal/reverse overflow, a single wrapped line, a reverse single
line, overflowing single line, nowrap, three unequal lines, limited auto cross
sizing, and exact fit. All compare complete root and child rectangles at the
existing 0.0001 logical-pixel tolerance and asserted test scale 2. The three-line
around case exercises fractional placement and real GPUI snapping, not an origin
projection or relaxed tolerance. Native-window scaling is not tested.

Two row lines of heights 10/14 with gap 4 in cross extent 64 appear at 0/50
(between), 9/41 (around), and 12/38 (evenly). Three lines of heights 10/14/18 in
extent 90 produce 0/34/72, 6.5/34/65.5, and 10/34/62 at the asserted scale.
Distribution adds spacing between natural-size line boxes; it does not stretch
their sizes or change within-line item gaps. Around/evenly center a fitting
single line. All three modes use safe physical-start fallback for overflowing
content, including wrap-reverse: the two overflowing lines above become 18/0
in reverse cross extent 20. This differs from explicit unsafe center/end.

The negative control changes a measured child width by one pixel after real
execution. It detects all 39 nonempty scenarios. Three empty controls contain
no child width to alter and remain passing. All 191 previous headless passes
are preserved; the existing unsupported IME and two native-unverified rows
remain explicit. Additional exploratory reverse-singleton checks are not added
to these authoritative totals.

## Reproduction and retained artifacts

The final suite pins the candidate. With exact engine/upstream checkouts:

```sh
python3 run.py --upstream-source /path/to/zed --moonbit-source /path/to/gpui.mbt \
  --scenarios content_distribution_scenarios.json --output _build/content-distribution-positive-published
python3 run.py --upstream-source /path/to/zed --moonbit-source /path/to/gpui.mbt \
  --scenarios content_distribution_scenarios.json --negative-control \
  --output _build/content-distribution-negative-published
```

The public baseline branch intentionally lacks the distributed MoonBit mapping
and uses identical corpus bytes. Its authoritative run is
`_build/content-distribution-baseline-published`. The combined run is
`_build/content-distribution-regression-published`; its retained scenarios
concatenate original, boundary, fractional-grow, gap-budget, fractional-shrink,
min/max, flex-wrap, space-between, distributed-spacing, align-content, and new
content-distribution corpora.

[The result index](results/content-distribution-linux-x86_64-20261016.json)
contains exact manifests/comparisons and SHA-256 identities. Each run records
clean immutable public source/suite revisions, executable hashes, fresh execution
challenges, raw output, and build/execution timing/status. The index is not a
substitute for the retained executable/artifact directory: comparator validation
rejects index-only evidence. Earlier exploratory snapshots remain separate.

Local validation passes 62 contract tests, 29 catalog tests, and 38 adversarial
evidence checks. The engine passes formatting, warning-denied all-target checks,
95 layout tests per target, full tests (527 each wasm/wasm-gc/JS, 740 native),
and 142 Python checks. These local results do not imply cloud CI success. Before
merge, both paired PRs require all exact-head CI green and explicit independent
GPT-6.1-sol/xhigh approval with no P1 findings or blockers.

## Limits

This is finite definite-size bounded flex coverage. Independent row/column gaps,
RTL/reversed main flow, margins, baseline alignment, general intrinsic sizing,
text shaping, physical input, IME, and GPU pixel equivalence remain outside scope.
No browser-lab UI or historical catalog record is changed or relabeled.
