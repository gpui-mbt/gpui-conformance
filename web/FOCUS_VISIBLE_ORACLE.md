# Unchanged `focus_visible.rs` oracle

This baseline packages and executes the original Rust example. It does not
declare a MoonBit port or an interaction-conformance pass.

## Source identity

- Repository: `zed-industries/zed`
- Browser revision: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`
- Source: `crates/gpui/examples/focus_visible.rs`
- Blob: `c5b3d5dfec3a189d088a621baff55eb55a121b6c`
- The same example blob exists at the engine's compatibility revision,
  `d9afb21688e04f89d9e94d96d33eb530aef90886`.

`build_rust.py --extra-example focus_visible` registers an additional binary in
a relocated standalone gallery manifest. Neither the archived upstream source
nor its original manifest is edited. The build records the exact toolchain,
command, packaging-manifest hash and output-file hashes. The browser profile
checks the served JavaScript/WASM against those hashes and retains actual full
viewport PNGs, decoded RGBA hashes and trusted input observations.

## Source-derived specification, pending actual execution

The source creates an 800×600 window, a non-tab-stop focused root, and three
buttons with signed tab indices 1, 2 and 3. Tab and Shift-Tab wrap through those
buttons. Focus and tab eligibility are separate: pointer focus can return to the
root without adding it to traversal destinations.

Button 1 has a yellow 4px focus border. Button 2 has a green 4px border only in
keyboard modality. Button 3 applies yellow focus styling first, then a green
keyboard focus-visible override. Mouse movement changes modality without
clearing focus. Keyboard input suppresses the uncaptured mouse-hover fill,
including when the pointer stays over the button. Modifier-only browser key
events are filtered before GPUI key-down dispatch.

Pointer down acquires focus; a completed primary click updates the message.
Keyboard Enter/Space activation also invokes the click listener. Its arming
state tracks focus generation, not the identity of the activation key. Ordinary
intervening key events or focus moving away and back cancel a pending activation.
Consequently, the example's literal click message can say “no border” or “yellow
border” while the actual keyboard ring is green. Pixel evidence and delivered
events, rather than that prose, determine the visual assertions.

The DOM's hidden textarea transports keyboard input. Browser `activeElement`
and CSS `:focus-visible` do not identify GPUI's focused button.

## Execution and limits

The browser CI builds the unchanged Rust binary and runs
`node web/tests/focus-visible-oracle-browser.mjs _build/browser-lab`.
The selected profile is 800×600 at DPR1. Source-derived geometric expectations
are deliberately fail-closed until an actual Rust run establishes the baseline.
Failed runs retain captures and logs; a test fixture alone is not oracle evidence.

This baseline does not qualify MoonBit behavior, text rasterization equality,
native rendering, alternate DPRs/viewports, pointer capture, touch input, nested
tab groups or complete GPUI action/keymap semantics. Rounded borders are a
separate rendering concern from portable core focus ownership and traversal.
