# Bounded owned-window observer on macOS arm64

Actual visible fixtures now complete native create/render/resize/destroy and
external WindowServer identity observation without requesting focus. A ready
record binds the process start, executable, source, scenario, window and
completed frame. Three real invalid-identity controls per implementation fail
before window/AX lookup. Each owned observer acknowledgment completes within
the fixture's five-second deadline; both processes close their windows and exit.

| Observation | Upstream GPUI | MoonBit GPUI |
| --- | --- | --- |
| Shared native lifecycle and pixels | 2 paired cases pass | 2 paired cases pass |
| Owned WindowServer binding and ready/ack | pass | pass |
| Stale start / PID zero / window zero controls | all rejected | all rejected |
| Existing AX trust, without prompt | available | available |
| Exact owned AX window match | unverified | unverified |

The passing positive execution used suite
`e8e9c794984950d4695ad3b765ecba907b74494a`, engine
`b78c058fa124286cfb5d59c4bbbb1801fc7b0b19` and upstream
`d9afb21688e04f89d9e94d96d33eb530aef90886` on macOS 26.5.2 arm64. Both retained
512 × 384 GPU frames at scale 2 are byte-identical (0 / 196608 changed pixels),
also verified with pinned vlmkit `b6ff83bb5f357e4ea3225af717479c6be74b2328`.

The actual visible blue-paint control used suite
`2dcc9e43f6eb7c30f96b4d0f7981567cdf787f3e` and merged engine
`d6afa474a20679725607f68b390f8a5dd8cd5b42` (same reviewed engine tree).
It preserves the lifecycle and owned-window handshake passes while producing
the expected pixel mismatch. The positive and control execute different fresh
processes and challenges; neither trace is reused as the other implementation.

The first visible attempt remains unverified: Rust logical removal preceded
its queued native close, so the strict closed-visibility check rejected it.
The adapter now yields briefly to that upstream asynchronous close before
recording native teardown. This changes observation timing, not upstream code.
No acceptance predicate was relaxed.

AX trust is present, and `AXWindows`, `AXRole`, `AXTitle` and PID queries returned
error code 0. However, each returned entry identifies role `AXApplication` and
title `probe`, rather than the required nonce-title `AXWindow`. The retained
candidate fields make this rejection reproducible. The underlying cause is
undetermined; missing permission is not established. AX remains unverified.

WindowServer identity alone does not qualify the screenshot content rectangle
or its transform to the GPU frame. No desktop capture, semantic-node proof,
physical input or post-action state is qualified. There were no permission
prompts, security-setting changes, activation requests or unrelated app actions.

Evidence is retained in `_build/observer-visible-{first,settled,negative}` and
`_build/images-observer-{visible,negative}`. The comparator validates hashes,
actual observer commands/timestamps, fixture/frame association, strict ack
types and real controls. Thirty-one real-evidence adversarial checks and
thirteen portable observer contract tests pass without launching GUI probes.
A document or standalone summary without the raw artifacts is not proof.
