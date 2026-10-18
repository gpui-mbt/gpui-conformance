# Source-derived popover preview

This candidate follows the unchanged `crates/gpui/examples/popover.rs` at Zed
revision `5a5fbe79917971a4d52a96b6ddb04da198a5012e`, blob
`7678a6a3ed865d9874b72cb99b473a115591d35c`. It uses gpui.mbt revision
`e160f5ec7bf0c6f43738d0bdcf837098299d5569`, tree
`96d62ea12a6824ee20d04cb913191bc23a424522`.

The default popup remains present. The parent opens from its source trigger,
and its child opens from the nested trigger. Deferred priorities and
outside-pointer dismissal belong to MoonBit/core, including preserving the
parent when the child alone is dismissed. JavaScript does not calculate popup
positions, wrapping, hit regions or open state.

The browser loads the shipped IBM Plex Sans Regular face before measuring
seven exact source strings/styles, splitting the first-level paragraph at its
explicit newline into eight shaped-prefix arrays. Measurements use Canvas
geometricPrecision; painting uses auto. These are browser font/raster boundaries,
not evidence of equivalent Cosmic Text shaping. Font load or invalid metrics
fail closed rather than admitting fallback-font or fixed-width measurements.

The visible host reads the current viewport and DPR before each pointer event.
It supports logical sides 1–8192, DPR 0.25–4, rounded backing sides at most 16384,
and at most 33554432 backing pixels. The MoonBit numeric envelope is broader;
that does not expand browser-host support. Unsupported inputs hide stale output
and reset model interaction. Trusted primary mouse down/up is transported for
all mouse buttons; touch, pen, synthetic browser events and multi-pointer
interaction are outside this preview. Blur, pointer cancellation and pagehide
cancel an unfinished press. BFCache restoration reconnects fresh listeners and
rebuilds a fresh frame without replaying a stale press.

Canvas rounded borders (including device-snapped widths and 0.1 black border
opacity) and both source shadow_lg layers are explicit host approximations.
The source green bar uses GPUI's quarter-lightness green (RGB 0,128,0).
Portable RGBA8 represents the source bars' 0.25 opacity as alpha 64/255;
this quantization is not an exact floating-point color equivalence claim.
Text, exact shadows, full images, native behavior, browser interaction and
callback-count parity remain unverified. No viewport has a qualified comparison
profile: every emitted frame reports comparison_profile_match=false.

Node host tests and Python packaging tests use synthetic dependencies. They
verify transport and packaging contracts only. A compiler or browser run must
be recorded separately; these tests cannot establish that either runtime built
or that the two runtimes agree visually or interactively.

The existing compiled-browser harness now invokes a bounded popover check for
each available runtime at 800x600 DPR1 and 480x600 DPR1.25. It independently
targets each runtime using its own screenshot OCR, retaining screenshots,
OCR output and trusted pointer events for opening and child-first dismissal,
including secondary-button down and outside release. A passed run would verify
only those observed interactions; OCR failure is a failed qualification, not a
pass. Exact occlusion, pixel equality and interrupted-focus parity remain
outside this check. Adding the harness alone does not establish a passed run.
