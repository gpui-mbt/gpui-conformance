# Linux flex-wrap conformance results

The 12-case bounded headless corpus was run against pinned Zed/GPUI
`d9afb21688e04f89d9e94d96d33eb530aef90886` (GPUI 0.2.2) and gpui.mbt
candidate `4f8529a396347c752d02727b6bd0b56a54214139`. The clean conformance
suite is `9125706b3566e94a9bfb6e687a697656f5147bd3`.

| Run | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| Flex-wrap corpus (12) | 12 | 0 | 0 | 0 |
| Flex-wrap negative control (12) | 2 | 10 | 0 | 0 |
| Existing 104 headless cases + flex-wrap corpus (116) | 113 | 0 | 1 | 2 |
| Full negative control (116) | 15 | 98 | 1 | 2 |

The two retained non-pass results in the aggregate are the existing unsupported
IME case and two native-unverified placeholders. The negative control alters
only MoonBit observations; both decimal fixtures mismatch at
`observation.line_origins[1]`, so the projection remains sensitive to a changed
second-child line origin. All ordinary layout cases continue to compare full
root and child bounds.

## Decimal precision boundary

GPUI's pinned `TestWindow` has a 2.0 scale-factor default. Its Taffy integration
snaps authored absolute lengths to integer device pixels before layout, so the
decimal exact-fit input is observed as a 100.5-wide root with 50-wide children;
the MoonBit engine currently preserves the authored `Double` values 100.3,
50.1, and 50.2. The pinned upstream Taffy adapter documents this two-phase
device-pixel snapping in `crates/gpui/src/taffy.rs`.

The original full-bounds run is retained at
`_build/flex-wrap-candidate-final-4f8529a-c95acb1/comparison.json`
(SHA-256 `dc31ecd1b2784d4bae251cc81b5f6624ef3184d7d21ef0537ab600e86aca2f6d`).
It records 10 passes and two expected precision mismatches. In the exact-fit
case, both implementations keep one line, but their snapped/authored bounds
differ. In the original just-over case (50.1 + 50.2001 in a 100.3 container),
GPUI snaps both child widths to 50 and keeps one line; MoonBit retains the
Double values and wraps the second child to y=10. This is a known input
quantization compatibility gap, not an oracle result to hide.

The current decimal cases explicitly select `layout_observation: "line_origins"`
to compare the behavior both systems can meaningfully exercise at their
respective input precision: exact fit yields `[0, 0]`, while a larger overflow
(50.1 + 50.8) yields `[0, 10]` in both. This projection verifies cross-axis
line placement only; it does not certify decimal root/child sizes or main-axis
coordinates. The retained raw full-bounds mismatch remains available for
future work on GPUI-compatible f32/device-pixel input quantization.

## Evidence and local checks

The final manifests and raw process artifacts are in:

- `_build/flex-wrap-candidate-final-9125706`
- `_build/flex-wrap-negative-final-9125706`
- `_build/flex-wrap-full-candidate-final-9125706`
- `_build/flex-wrap-full-negative-final-9125706`

Each manifest records the clean suite commit above, the pinned upstream and
candidate revisions, and their source-tree identities. The negative controls
are intentional evidence and should not be interpreted as candidate failures.

Local CI-equivalent checks passed: portable contract tests (18), visual
contracts (13), fixture contracts (8), observer contracts (16), Rust adapter
formatting, plus engine `moon fmt --check`, all-target `moon check --deny-warn`,
and all-target `moon test --deny-warn` (493 each on wasm, wasm-gc, and JS; 706
native). The optional `GPUI_FIELD_E2E=1` gate was not enabled. No GitHub CI run
or publication is claimed by these local results.
