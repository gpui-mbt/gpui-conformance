# Reference provenance

The input/focus/layout boundary batch uses independently authored scenarios and
adapters. Additional inspected public interfaces are capture/bubble key and
mouse listeners in `crates/gpui/src/elements/div.rs`, focus/blur/readback and
dispatch in `crates/gpui/src/window.rs`, and GPUI's flex style builders. Layout
observations still come from completed GPUI Render/Taffy bounds, not copied
upstream tests or expected coordinate tables.

Reference: `https://github.com/zed-industries/zed` at
`d9afb21688e04f89d9e94d96d33eb530aef90886`. This matches gpui.mbt's existing
`docs/upstream.json` compatibility target. Upstream remains unmodified.

Inspected paths:

- `crates/gpui/Cargo.toml`: GPUI 0.2.2, `license = "Apache-2.0"`.
- `crates/gpui/LICENSE-APACHE`: symlink to `../../LICENSE-APACHE`.
- `LICENSE-APACHE`: SHA-256
  `752daf2fb234ca4a1fa372c073fe127f44b7b90fd2529ae44273a64f9d53da7a`.
- `crates/gpui/src/app/test_context.rs`: public deterministic test/visual context.
- `crates/gpui/src/elements/div.rs`, `elements/canvas.rs`: public layout,
  debug-bound and listener interfaces.
- `crates/gpui/src/window.rs`: public content-mask/window APIs.
- `crates/gpui/src/geometry.rs`: investigated after observed boundary divergence;
  `Bounds::contains` excludes the right/bottom edges.
- `.agents/skills/gpui-test/SKILL.md`: test scheduler/workflow guidance.
- `Cargo.lock`: initial dependency-resolution seed for the adapter lockfile.

Destination: `adapters/`, `scenarios.json`, and comparator/runner code.
Method: **independent_from_behavior**. Shared scenarios are original synthetic
rectangles and events; probes call library APIs and are independently authored.
No upstream implementation, test bodies, artwork, screenshots or font files are
copied. The adapter Cargo.lock records dependency versions from the pinned
workspace. Scope deviations: two headless child rectangles; the native corpus
observes content-size/liveness and three opaque-rectangle GPU pixel samples,
not desktop positions, all pixels, physical input, IME or accessibility.

The native adapter also links pinned `gpui_platform`, `gpui_macos` and
`gpui_apple` public APIs. Their owning Cargo manifests declare Apache-2.0.
Inspected native paths: `crates/gpui_platform/src/gpui_platform.rs`,
`crates/gpui_macos/src/window.rs`, `crates/gpui_apple/build.rs` and its renderer
readback API. Sources remain unmodified; runtime Metal compilation uses the
upstream `runtime_shaders` feature. The small foreground-restoration helper
under `adapters/native_moonbit/` is original AppKit API usage, not copied code.
