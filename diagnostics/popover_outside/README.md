# Source-derived two-level popover outside dismissal

Status: source-only, uncompiled and unexecuted. This addition is a prospective actual-GPUI observer, a frozen fixture and a source-hypothesis checker. It contains no observed Rust results, no MoonBit adapter, no core fix and no parity claim. Independent source review is required before any dedicated CI execution. The seven Python tests use clearly synthetic traces and source inspection; they do not execute or mutate GPUI.

## Exact lineage and additive boundary

Suite base: `717506fb6e752fb8f375bcac786d8fc5cd52a5d1`, tree `96d216f94a10d73591416ca09a74cfbb3ca80311`. All 723 historical tracked blobs and executable modes are preserved. Exactly seven additions are allowed: this README, `scenarios.json`, `verify.py`, `tests/test_popover_outside.py`, and `adapters/popover_outside_rust/{Cargo.toml,Cargo.lock,src/main.rs}`. Old scripts and evidence must not be relabeled or rerun as this diagnostic.

Upstream: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`, tree `990fb995914d51a546b20e5cf0382dafc105c299`.

Pinned source blobs:

- `crates/gpui/examples/popover.rs`: `7678a6a3ed865d9874b72cb99b473a115591d35c`
- `crates/gpui/src/elements/div.rs`: `5d3b03b057bcac09f987a4587598a08a06872361`
- `crates/gpui/src/window.rs`: `33fa14bfea6ebad50743d6d4014955d1055ef772`
- `crates/gpui/src/app/test_context.rs`: `b8a120f942cbf166b0d73f1b5d77aa3a6ea0d1ac`
- `crates/gpui/src/platform/test/window.rs`: `5692b1e7cb81a80f5cf9393c68bab3f56448e3e3`

Cargo manifest and lock are inherited from the existing nested-deferred-fitting Rust adapter with only the root package name changed. They have not been resolved or compiled anew. The path dependency expects a sibling `zed-source` next to the suite checkout.

## Actual dispatcher, not host emulation

`VisualTestContext::simulate_mouse_down/up` creates upstream input events; `simulate_event` (`test_context.rs1057–1061`) calls `TestWindow::simulate_input`, invoking the installed platform input callback. Upstream `Window::dispatch_mouse_event` (`window.rs5966–6003`) performs real hit testing and calls the retained mouse-listener vector in capture order, then reverse bubble order. The observer does not hit-test, route, sort listeners, decide outside membership, or update state from its input driver. All four mutations occur only inside actual `on_click` and `on_mouse_down_out` callbacks. Opening is a down/up pair; dismissal uses the specific down event. The callback trace records before/after state and actual button. API semantics establish capture-phase delivery; a phase parameter is not directly exposed by `on_mouse_down_out` and is not falsely presented as a measured field.

The parent/child booleans, `on_click` opens, conditional parent outside handler while child closed, child outside handler, nested deferred priorities 1/2, TopLeft anchoring and margin8 derive from `popover.rs48–80,116–156`. `div.rs257–277` checks capture, no active prompt and geometric outside bounds, without a primary-button filter. Because listeners belong to the rendered frame, closing the child on one event cannot retroactively install the parent's absent listener during that same event. The second outside down follows a settled redraw and can reach the newly registered parent handler. These are source hypotheses pending actual execution, not captured outcomes.

## Deliberate font-free lowering

Viewport 320×240; trigger at (20,20), size60×24; parent at explicit Window position(60,70), size180×110; child trigger at parent-local(16,16), size64×24; child at explicit Window position(160,130), size100×60. Parent and child overlap, but neither fills the viewport. These explicit positions replace the example's text-dependent flow positions to isolate input delivery. No text, border, shadow, padding, gap, margin-derived reference size, flex layout, clipping or transforms are included. No fonts are loaded and the upstream headless test text system is unused. The checker treats bootstrap scale2 as a frozen hypothesis; an unexpected actual scale or rectangle is an investigation failure, never normalization or a reason to silently widen tolerances.

Transparent Element decorators delegate all original states, arguments and return values. They record actual host request-layout frame starts and every wrapped prepaint/paint bound. `host_paint_return` is specifically the ordinary host paint return, not the end of deferred painting or the entire engine frame. All frames are retained; their count is not hardcoded. Render records expose the booleans and handler registration conditions. The checker independently requires source-derived geometry and one strict cross-phase chronology (all prepaints, ordinary host/trigger paints, host paint return, then deferred parent/child paints), complete operation brackets, monotonic sequence/frame identities, registration state, callback order/count and settled states. It uses exact equality at these integer coordinates, without geometry tolerance. Bounds and input points are well inside their respective regions, avoiding edge-inclusion ambiguity.

## Frozen sequence

`scenarios.json` holds 23 individual input events, preceded by opening the window. Each event is separately bracketed and drained through the upstream executor:

1. Open parent using a primary down/up at (30,30).
2. Open child using a primary down/up at (90,96).
3. Down/up inside child at (180,150), inside the overlapping parent too.
4. Down/up inside parent but outside child at (70,160): source predicts only child closes.
5. Reopen child using the real child trigger.
6. Down/up outside both at (300,220): source predicts child closes and parent remains open.
7. Second down/up outside both: source predicts parent closes.
8. Reopen parent and child through their real buttons.
9. Right-button release only outside both: source predicts no dismissal.
10. Right-button down/up outside both twice: source predicts child then parent dismissal on separate downs, proving the API's any-button behavior.

Callbacks, states and rectangles in the fixture/checker are explicitly source hypotheses, never fed into the Rust dispatcher. Repeated opens and dismissal exercise listener removal/reinstallation. Synthetic mutation controls cover same-event cascade, primary-only filtering, release dismissal, wrong registration, callbacks missing/duplicated/reordered, geometry and frame identity/scale. Cross-phase controls retain each phase's node order and the host-return count while moving paint before prepaint or moving host return prematurely or after deferred paint; each must fail before and after JSON serialization. The Python trace synthesizer is only a checker test utility and must never produce retained upstream evidence.

## Lightweight source checks

From the suite root:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_popover_outside.py -v
```

Rust syntax formatting was checked with the existing Rust1.98.1 rustfmt; formatting is not compilation or type checking. No local Rust build or run is permitted. The seven paths occupy less than512KiB, under the cumulative16MiB source/evidence cap. Before any additional write, preserve at least1GiB+32MiB available space; stop rather than delete historical evidence to make room.

## Prospective dedicated invocation and evidence gate

These commands document the future observer interface only; they do not authorize a local build, CI, push or artifact download. First obtain independent source review and an approved dedicated runner with adequate build headroom and continuous disk checks. That runner is not included in this seven-path source-only addition. Freeze the suite commit/tree and seven new file hashes before running. Authenticate all 723 baseline mode/blob identities and the upstream commit/tree/source blobs above. Use a clean `work/suite` checkout and its sibling `work/zed-source` checkout at the pinned upstream. Retain original source, manifest, lock, toolchain versions, exact command/environment, binary hash, UTC timestamps, session/run token, exit status, stdout and stderr, including failures. Do not accept self-reported JSON revision/token as provenance.

From `work/suite`, in that future separately approved execution environment:

```
CARGO_INCREMENTAL=0 cargo +1.98.1 build --locked -j2 --manifest-path adapters/popover_outside_rust/Cargo.toml --target-dir ../popover-outside-target
../popover-outside-target/debug/gpui-popover-outside-diagnostic diagnostics/popover_outside/scenarios.json "$RUN_TOKEN" > "$EVIDENCE/raw.json" 2> "$EVIDENCE/stderr.txt"
PYTHONDONTWRITEBYTECODE=1 python3 diagnostics/popover_outside/verify.py "$EVIDENCE/raw.json" > "$EVIDENCE/source-hypotheses.json"
```

The verifier intentionally reports `execution_authenticated: false`: it checks raw shape and hypotheses, not external execution provenance. A fabricated trace can match; therefore independent original-artifact/source-session review remains mandatory before calling anything actual observed GPUI behavior. No exact CI workflow or reproducible evidence runner is yet supplied. Raw mismatch must be investigated before changing hypotheses. Only after authenticated genuine Rust evidence should a focused MoonBit observer and core implementation be proposed. Existing core's topmost-ancestry dispatcher is a separate target, not substituted with JS outside-click emulation here.

Excluded: unchanged/full popover example parity; native-window/browser integration; text, padding and margin lowerings; focus, keyboard, click-through/occlusion, active prompts, boundary points, middle/back/forward buttons, drag and capture cancellation, deeper nesting and arbitrary listener-order interactions. Those require separate fixtures and audits.

## Source-review correction

The initial source review found that separate prepaint/paint arrays and a host-return count accepted impossible cross-phase ordering. Its synthetic emitter also placed host return after deferred paint. The corrected checker compares one combined chronological stream, and the emitter places host return after ordinary root/trigger paint but before deferred paint, matching `window.rs3760–3765` and the transparent observer. Initial review/proof evidence is retained separately unchanged. This is a checker/source correction, not a runtime finding.
