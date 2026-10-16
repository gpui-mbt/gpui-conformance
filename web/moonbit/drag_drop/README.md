# Source-faithful typed `drag_drop` candidate

This is a bounded MoonBit port of unchanged GPUI `drag_drop.rs`, source commit
`5a5fbe79917971a4d52a96b6ddb04da198a5012e`, blob
`8f038ef3308fee9b097e7289665c9fa47cd6945b`, SHA-256
`4011afde7c64fac2559b78918e6fdabdc563fe9f7591c74425d72da906dcc47a`.
It is source/model-tested, not a claim of paired browser, text, GPU shadow,
native, or general drag/drop equivalence. The catalog and core publication pin
are integrated separately after review; the normal build remains pin-strict.

## Ownership and real core use

`DragDropState` owns a genuine `@element.DragSession[DragInfo]`. `DragInfo` is an
immutable value with index, RGB color, and original position `(0,0)`. Each event
passes a real `InputEvent`, the current `ElementTree`, typed current sources,
and typed current targets into core `dispatch`. Core owns source admission,
strict distance greater than 2 on moves only, sticky activation, current binding
selection, frozen activation offset/payload, half-open target routing, and
one-shot typed consumption. The existing `DragGesture` is not used by this port.

`Dropped(target, payload)` changes the authored target only after dispatch has
consumed the session. The separate preview value alone receives the activation
cursor offset. Old aliases share consumed/cancelled state. Rerender uses a fresh
current non-focus tree with stable IDs; reset explicitly cancels the old session
before replacement. This fixed example never removes or reuses source IDs while
a session is live. Dynamic source removal/reuse requires explicit cancellation;
this is not generation-safe identity support.

Every `DragDispatchError` has an explicit diagnostic mapping. Core errors leave
the session untouched, including malformed release. This application's error
policy then explicitly calls `cancel`, reports the error and whether cancellation
changed state, and does not apply a drop callback. Invalid raw inputs fail before
core dispatch and leave the session unchanged. Neither error path invents a
successful release. Pointer leave clears hover only; there is no Escape handler.

## Geometry and paint

The base geometry goes through `Element -> request_layout_with_device_scale ->
prepaint`. The browser supplies only eight measured widths for the exact authored
strings, using bundled IBM Plex Sans Regular. Finite, positive, single-line-fit
widths and session-fixed scale are checked. GPUI's phi line heights snap to
32/26/19 pixels for 20/16/12 pixel text at DPR1. No browser rectangle table feeds
the MoonBit layout or input route.

The white 800x600 root centers a column with 20px gaps. The heading is `Drop &
Drop`, 20px, RGB(51,51,51). Three 128x128 sources have 2px borders and 16px gaps,
with exact blue(0,0,255), red(255,0,0), green(0,128,0) and 16px source-color labels.
A transparent non-hit row wrapper with a 40px bottom inset lowers the source's
anonymous bottom margin without introducing an extra root gap. The 512x128
target has a 3px black border initially, then exact 0.5 selected-color fill and
opaque selected-color border after accepted release. Hover is exact 0.2 and is
suppressed while core is active.

Preview body/text use a separate real 120x50 core flex layout. They never join
the input tree. The transparent source Block wrapper is lowered to an absolute
signed translation with visible overflow, preserving TWO independent signed
half-toward-zero snaps:

    Q(pointer - activation_offset) + Q(activation_offset - (60,25))

Each component uses `Q(v) = copy_sign(ceil(abs(v * scale) - 0.5), v) / scale`.
This preserves negative padding without changing nonnegative core Insets. It
must not be simplified into `pointer-(60,25)` for fractional grips. The signed
lowering is established by the pinned GPUI/Taffy source audit, not by an observed
negative-padding browser probe. Runtime parity for negative/fractional grabs and
other DPRs remains unqualified.

The preview quad uses opaque RGB plus `SceneItem.opacity=0.5`; white 12px text
has opacity1. The explicit paint descriptor is
`{id:90,kind:"shadow_md",element_opacity:1}`, with renderer-owned source md layers.
Source and target borders are separate full-bounds transparent quads after each
label, preserving source ordering rectangles and opaque border paint independent
of fill opacity. No border strips, legacy shadow stand-in or preview input nodes
are used. The renderer extension is a separately reviewed change.

## Transport and exports

- `drag_drop_metadata()` returns exact labels, font sizes and source identity
- `drag_drop_frame(widths, scale)` returns a SceneSnapshot, explicit host paint,
  model cursor and clearly candidate-only diagnostics
- `drag_drop_pointer(kind,x,y,button,shift,control,alt,meta)` converts raw input and
  returns JSON with success/error, outcome, changed/stopped status and cursor
- `drag_drop_leave()` clears hover without cancelling the core session
- `drag_drop_reset()` cancels, then replaces the model
- `drag_drop_state()` serializes actual candidate state; it is not a Rust oracle

`drag-drop-host.mjs` only converts DOM coordinates/buttons/modifiers, forwards
mouse input, applies the model's cursor, repaints, and retains bounded transport
logs with the original trusted flag. It has no payload state, threshold,
hit-testing, ID choice or target mutation. Teardown invokes reset. Native/global
capture, touch, OS drag, general overlap/occlusion and foreign payloads are not
claimed. Existing `build_moonbit.py` already discovers catalog-implemented package
names generically; it needs no bypass or per-example pin override for this port.

## Reproducible bounded local checks

`web/scripts/test_drag_drop_candidate.py` requires an exact clean core commit and
tree and retains its archive, all MoonBit source hashes, exact candidate sources,
compiler version, logs, JS runtime and runtime SHA-256. Its report is explicitly
local testing, not a site build-manifest. It refuses an existing output directory.

    MOON_HOME=/path/to/.moon PATH=/path/to/.moon/bin:$PATH \
      python3 web/scripts/test_drag_drop_candidate.py \
      --gpui-source /path/to/gpui.mbt \
      --core-revision <exact-commit> --core-tree <exact-tree> \
      --out /new/retained-test-directory

The initial exact-core integration used commit
`6b59cda4d072b50e63f419b623865b4634007c1a`, tree
`c9ec59c5fbdbd84548b7d6ffe2c99b8403509db9`. Seventeen MoonBit contracts passed,
including typed payload versus preview, current bindings, release timing, real
layout, styles and opacities, preview exclusion from input, aliases, duplicates,
error policy, target callbacks and signed snapping. The actual release JS module
also passed two Node tests plus nine transport tests. These are synthetic local
inputs, never mislabeled trusted browser observations.

Eight compiling candidate mutants are required to fail runtime assertions:
preview payload delivered instead of original; target update on activation;
active hover leaked; half alpha rounded to128/255; wrong green RGB; combined
preview snaps; original down offset substituted for activation offset; and raw
input replaced with a fake core event. Wrong generic payload type is a separately
labeled compiler-rejection control, not runtime sensitivity. The runner restores
and retests the positive candidate after mutants. Source-policy mutants remain
owned by the core package's separate tests.

The unchanged 54-state Rust profile, original captures and historical comparators
remain untouched. Paired qualification requires independently captured and
verified outputs from both runtimes against their exact published/build pins.
