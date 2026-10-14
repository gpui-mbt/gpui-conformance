# Reference provenance

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
workspace. Scope deviations: only two child rectangles; no GPU pixels, native
window comparison, physical input, IME or accessibility qualification.
