# Focus-visible example

This candidate ports the unchanged `crates/gpui/examples/focus_visible.rs`,
blob `c5b3d5dfec3a189d088a621baff55eb55a121b6c`, at upstream
`5a5fbe79917971a4d52a96b6ddb04da198a5012e` (the example is identical at
compatibility revision `d9afb21688e04f89d9e94d96d33eb530aef90886`). It uses
actual gpui.mbt lifecycle layout, core hit paths, focus ownership, tab
traversal, and Mouse/Keyboard modality. Runtime output remains
`conformance: "unverified"`; source-derived unit tests are not Rust browser
or native equivalence evidence. The comparison profile is 800×600 at DPR 1.

## Host interface

- `focus_visible_metadata()` returns the fixed viewport, source provenance,
  font requirements, and initial eight runs.
- `focus_visible_content()` returns the current `message` and eight `runs`.
  Each run contains `id`, `text`, `font_size`, `font_weight`, and
  `line_height`. Read this after input and measure these current strings
  before each frame. Run order is title, message, label 1, button 1, label 2,
  button 2, label 3, button 3. Fonts are IBM Plex Sans, 24px/700 for the title,
  14px/700 for section labels, and 16px/400 otherwise.
- `focus_visible_frame(widths, scale)` accepts exactly eight finite positive
  shaped widths and a finite scale greater than zero and no greater than 4.
  Width limits are `[736, 704, 736, 728, 736, 728, 736, 728]`; the button
  limits reserve both 4px border insets. Invalid metrics, including scales
  that collapse text or rounded-box dimensions, return
  `{ "ok": false, "error": "invalid_metrics" }` without mutating state.
  Changing a live session's scale returns `scale_changed_requires_reset`.
- `focus_visible_pointer(kind, x, y, button, shift, control, alt, meta)`
  accepts finite logical coordinates, `kind` equal to `move`, `down`, or
  `up`, and DOM button numbers 0–4. `move` ignores the button number, so -1
  is supported. MoonBit decides hit testing, deepest focus target, hover,
  retained primary press, and click synthesis. No rectangles or target IDs
  are accepted from JavaScript.
- `focus_visible_key(label, down, shift, control, alt, meta, repeat)` takes
  DOM `KeyboardEvent.key`, with the ordinary single-space value for Space
  (`Space` is also accepted), and a label length of 1–128 UTF-16 code units.
  The host filters upstream's modifier-only DOM events. MoonBit does not
  guess which events the browser should have delivered.
- `focus_visible_wheel(x, y, dx, dy)` validates finite logical coordinates and
  pixel deltas, routes a genuine core Scroll event, and preserves modality.
  This source contains no scrollable region.
- `focus_visible_leave()` removes the stored pointer without clearing focus,
  modality, or pending keyboard activation. Browser blur must not call reset
  or invent a focus-clear policy.
- `focus_visible_reset()` clears the example session. Render a valid first
  frame before dispatching input. All input functions return false for
  invalid or uninitialized input; true means accepted input and a repaint
  may be requested. It does not mean a click or focus change occurred.

The frame contains a canonical `snapshot`, explicit `decorations`,
`rounded_fills`, `text_styles`, and candidate-only `focus_visible`
diagnostics. Root ID is 1; message panel ID is 3; button IDs are 12, 22, 32;
text IDs are `[2, 4, 11, 13, 21, 23, 31, 33]`. Diagnostics report core
focus, modality, source message, each button's focus/hover/ring selection,
and pending input status. IDs are diagnostics, not host input commands.

## Ownership and layout

The first successful frame retains one input ElementTree and focuses its
non-tab-stop root. Redraws build separate paint trees but never restore old
FocusOwners into fresh lineage and never replace the authoritative input
tree. Only measured text widths change during this fixed-size session;
text nodes are not hit targets, and title/message/label lineboxes and button
bounds remain stable. Explicit reset permits a new lineage and scale.

Root and button focus are genuine core acquisitions. Same-target requests
are guarded because upstream Window::focus does not increment its focus
generation when the handle is unchanged. Core `with_focus` deliberately
creates a new acquisition, so blindly calling it on every redraw or pointer
press would break keyboard activation. Core focus errors are not bypassed.

Layout preserves root padding 32, root gap 24, message padding 16, section
gap 16, label/button gap 8, and full-width 64px buttons. Phi line metrics
are snapped to device pixels before layout, following TextLayout::layout
and Window::pixel_snap. At DPR 1 the analytical test expectations are
39/26/23px lineboxes and button boxes at x=32, y=208/319/430, width=736,
height=64. These are test expectations, never construction coordinates.
Text centers and all scene bounds come from layout/prepaint, with inherited
clip IDs preserved when marker quads become text scene items.

The source colors are retained: root #f3f4f6, title #111827, message
#dbeafe/#1e3a8a, labels #374151, buttons #2563eb, hover #1d4ed8, white
button text, focus yellow #fbbf24, and focus-visible green #10b981. Button 1
always gets yellow when focused; button 2 gets green only for keyboard
modality; button 3 gets yellow for focus, overridden by green for keyboard.

Rounded 6px fills, 4px solid focus borders, and requested font weight 700
are explicit Canvas host extensions. Border and radius are not claimed as
portable core scene primitives. The host must retain source weight 700 in
metadata even when the bundled SemiBold face is its closest available font.
Both borders are symmetric, so the centered single-line button text keeps
the same center with or without them. General wrapping is outside this
bounded port.

## Input correspondence

Production references are `window.rs` (Window::focus, focus traversal,
`dispatch_event` modality, hitbox hover), `elements/div.rs`
(`paint_mouse_listeners` and keyboard-activation regression tests), and
`elements/text.rs` (line-height snapping).

KeyDown selects Keyboard; MouseMove and MouseDown select Mouse. KeyUp,
MouseUp, and wheel retain the current modality. Keyboard suppresses
uncaptured hover even when the pointer rests over a button. Mouse movement
never blurs the focused element. Tab and Shift-Tab use core traversal,
wrap among the three stops, and set the exact source messages. Unrelated
keydown changes modality but not the message.

Any supported mouse button can focus the deepest tracked element. Root,
title, labels, message, and blank root areas focus the root. A primary
press records a click candidate; release outside cancels it. The source
checks the recorded down button, not whether down/up button identities
match. This port intentionally preserves that rule. Secondary-only presses
focus without clicking. MouseUp still observes current hover modality, so
an intervening keyboard event can suppress a pending mouse click.

At the core event boundary, unmodified Enter/Space down stores the current FocusOwner acquisition;
an activation release clicks only while that acquisition is current. The
source uses one generation marker, not the identity of the activation key:
Space-down/Enter-up and Enter-down/Space-up therefore both activate. Other
key presses or releases cancel activation. Focus-away/back is rejected even
when the node ID is the same. Repeated rendering, mouse movement, and a
same-target focus request preserve the acquisition. Root has no click
callback. Keyboard repeat follows the source's replacement of the same
pending generation marker.

The desktop browser adapter uses a real, focused, editable hidden textarea,
matching pinned `gpui_web` initialization. Enter has no upstream `key_char`, so
physical Enter-down keeps its browser default. Chromium then emits trusted
`beforeinput` (`insertLineBreak` or `insertParagraph`); the upstream adapter
translates that edit intent into an unmodified core Enter down/up pair. The
candidate transport does the same only when that actual event arrives.
Physical Enter-up cannot activate again because the core pending marker has
already been consumed. Space does not follow this path: its printable keydown
is default-prevented. This is a browser adaptation, not a claim that native
core Enter activates on keydown. The first real Rust baseline exposed this
difference and is retained as a failed expectation, not relabeled a pass.

Nested tab groups, touch, pointer capture, arbitrary viewport resizing,
wrapped text, native integration, and app lifetime/Command-Q are outside
this browser interaction profile. The host must not synthesize browser
blur handling or add click/key-identity rules absent from upstream.

## Validation

The package has 25 source-derived MoonBit JS unit tests covering source
strings/colors/order, exact layout, root default, both traversal directions
and wrap, same-target acquisition, ring precedence, focus retention, hover
suppression/restoration, pointer press/release/cancellation, root reset,
secondary focus, keyboard activation and cross-key identity, modifiers,
intervening keys, focus-away/back ABA, repeated renders, reset isolation,
finite-input rejection, and session-fixed scale validation.

Run with a gpui.mbt checkout that includes the production focus traversal
and InputModality APIs, copying this package to
`examples/conformance_focus_visible` in an isolated build tree:

    moon fmt examples/conformance_focus_visible --check
    moon test examples/conformance_focus_visible --target js
    moon build examples/conformance_focus_visible --target js --release

No browser or Rust runtime result is asserted by these tests. Actual
unchanged-Rust comparison must be evaluated separately in CI for the exact
suite/core/upstream revisions and the stated profile.
