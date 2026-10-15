# Visible fixture and accessibility qualification

The retained-image evaluator is usable without a visible window, screen capture,
Accessibility permission, physical input, browser launch or model credentials.
It evaluates the exact previously recorded revisions. It does not qualify a
live external observer or any current native candidate.

## Current barriers

- The Rust fixture uses `show: false`, renders offscreen and closes quickly.
  An external observer cannot reliably attach after process discovery.
- The MoonBit host unconditionally presents and activates its window. Restoring
  the previous app afterward does not satisfy a no-focus-disruption constraint.
- The two fixtures do not yet publish a shared observer-ready handshake or
  retain a window until an owned observer acknowledges completion.
- No macOS AX collector, window ownership binding, trust check or post-action
  native state proof is qualified by this batch. Physical input remains
  unqualified; the separate physical-input PR stays Draft.

## Required fixture lifecycle

A separate reviewed fixture increment should expose an explicit observer mode.
The default headless/build-only behavior remains available. In a coordinated
session the fixture creates only its own window and emits a nonce-bound ready
record after its first completed frame. The record must bind executable hash,
PID, process start identity, native window identifier, content size, scale,
source revision, scene revision and frame sequence. The owned window remains
alive for a bounded acknowledgment interval. Completion and timeout close only
that fixture's window/process and never target another app by title or frontmost
status. User focus changes take precedence over restoration attempts.

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
