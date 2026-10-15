# Visible fixture and accessibility qualification

The retained-image evaluator is usable without a visible window, screen capture,
Accessibility permission, physical input, browser launch or model credentials.
It evaluates the exact previously recorded revisions. It does not qualify a
live external observer or any current native candidate.

## Qualified fixture increment

Both fixtures default to hidden accessory windows. Explicit `--observe-visible`
orders only the owned window behind others after completed GPU readback, then
publishes a nonce/PID/start/executable/window/frame record and holds it for at
most five seconds. Actual WindowServer ownership bindings, ready/ack chains
and invalid-identity controls passed on both implementations. See
[the protocol](OBSERVER_READY_PROTOCOL.md) and
[actual results](OBSERVER_READY_RESULTS.md). Historical classifications are unchanged.

## Remaining barriers

The actual observer has AX trust without requesting permission. On this host,
both fixtures' `AXWindows` entries reported `AXApplication` with title `probe`,
not a nonce-matching `AXWindow`; AX calls reported no error. The collector
correctly rejects that association. Its underlying cause is undetermined.
External AX window matching, semantic nodes, post-action native state and
physical input remain unverified. No screenshot/content-rectangle transform is
qualified; WindowServer outer bounds alone do not establish one.

## Required fixture lifecycle

The reviewed fixture increment exposes an explicit observer mode.
The default hidden/build-only behavior remains available. The fixture creates
only its own window and emits a nonce-bound ready
record after its first completed frame. The record must bind executable hash,
PID, process start identity, native window identifier, content size, scale,
source revision, scene revision and frame sequence. The owned window remains
alive for a bounded acknowledgment interval. Completion and timeout close only
that fixture's window/process and never target another app by title or frontmost
status. The runner never restores or activates another app.

## Required observer and action binding

The observer checks process/executable/start identity and the exact native window
before reading AX nodes or accepting a screenshot. It reads only the fixture's
AX subtree and owned content rectangle. Missing, duplicate, stale, replaced,
foreign-PID, hidden or zero-sized window candidates produce unverified results.
AX trust must already be available to the actual observer identity; a read-only
trust check must not prompt or change TCC settings. If permission is absent,
record it and coordinate the exact permission request before dependent work.
No unrelated window capture is an acceptable fallback.

Before physical input can be qualified, tie each action to the same owned
window, an observed pre-action state and a unique action sequence. Afterward,
require a new completed frame and matching semantic/AX state acknowledgment.
Timeout, focus loss, stale frame reuse, unexpected target or missing native
event evidence cannot pass. Include wrong-window/stale-state negative controls
before declaring this observer practical. VLM judgments remain advisory;
exact RGBA, dimensions/scale, native event and state evidence remain authoritative.
