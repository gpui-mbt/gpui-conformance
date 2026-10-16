# Tab stops and groups candidate

This ports unchanged upstream `crates/gpui/examples/tab_stop.rs`, blob
`cc7c34a9979ce4027578ec2c358f503d944ee26f`, at
`5a5fbe79917971a4d52a96b6ddb04da198a5012e`. The compatibility revision
`d9afb21688e04f89d9e94d96d33eb530aef90886` has identical bytes. The source
viewport remains 800×600, with 16px padding, 12px root/ordinary-row gaps and
original labels/messages. It is not scaled, reflowed or rewritten to fit.

Runtime frames always report `conformance: "unverified"`. Local source tests,
compiled negative controls and historical Rust-only discovery are not paired
browser evidence. No candidate browser, native, full-image, exact text/shaping,
or GPU shadow-kernel parity is established. The actual comparison profile is
Chromium at 800×600 DPR1; other scales accepted by the session are unqualified.

## Core, layout and ownership

The candidate uses genuine `Element → request_layout_with_device_scale →
prepaint → paint_snapshot` and portable `SceneSnapshot` items. Text-marker
quads become text items with their genuine bounds and inherited clip IDs.

Initial independently tested core pin: public `eb968228bbea56aff13721dc427875c2dacffc14`, tree
`ae9072d350ef6d1546e408226218ec08efc96552`. Local source commit
`a2718fcbf92dbbfd53f756642cc95813a402c431` has that same tree; initial package
tests used a disposable archive of the local commit. Final suite builds use a
disposable archive of the exact public commit. The source checkout is untouched.

The first valid frame retains one input tree and focuses its non-stop root.
Each later frame validates its metrics and layout, then calls genuine core
`ElementTree::with_layout_bounds(Prepainted)`. That method copies only compatible
layout bounds into the retained live lineage. It rejects changed positional
IDs/parents, input eligibility/group/pointer metadata, root viewport, or scroll
viewports. It preserves exact FocusOwner acquisition and all retained node
metadata, including backgrounds. Paint comes from the fresh Prepainted frame;
its owners are never imported or synthesized from numeric IDs.

This refresh matters. Initial unchanged-Rust discovery showed ordinary buttons
at x16/w378 and x406/w378. Focusing button1 yields w380 and x408/w376; focusing
button2 yields w376 and x404/w380. Every individual frame retains the source
12px gap. Cards also redistribute one device pixel when the focused border
changes from1px to3px. Old initial hit rectangles would misroute real input.
These numbers are test expectations only, never construction coordinates.

The source adapter explicitly lowers the bounded border-box rules into existing
core flex primitives. Pinned Taffy0.13.0 `src/compute/flexbox.rs:806–820`
floors outer flex bases by padding/border and derives an inner flex basis;
`:833–854` derives automatic content minima; `:1338–1347` scales shrink by
inner basis. Therefore:

- Ordinary flex1 children lower basis0 to two border widths, with grow1 and
  measured text-plus-border minima.
- Cards keep source outer height40. Their core shrink factor is
  `(height − 2×border)/height`, translating Taffy's inner scaled weight into
  the core's outer-basis weight. Their content minimum is the smaller of
  height40 and one source linebox plus borders.
- Message, ordinary row and groups retain source content minima. These two
  default-Block groups contain three definite40px blocks each, no margins or
  gaps. This profile lowers to stretched zero-gap columns with no child flex.
  It is not a general Block-layout implementation.
- Source lengths and phi lineboxes use the existing device-grid layout path.
  Actual placement and rounding remain core-owned, with no observed y table.

## Focus and input

Card handles have indices1,2,3,0(non-stop),2 in source order. Ordinary buttons
have4/5. Group containers retain handle index6/7 independently from prefix6/7,
are focusable non-stops, and contain child indices1/2/3. Their own ordering
anchors are [6,6]/[7,7], not [6]/[7]. Core `focus_next`/`focus_prev` chooses all
12 destinations, including repeated-index source ties and global reverse/wrap.
No JavaScript order array or remapping is involved.

Only ordinary buttons author click messages. Cards, the non-stop card, root,
group containers and all group children have no invented click callbacks.
Ordinary primary press/release and keyboard activation preserve source retained
gestures. Same-target focus is guarded to avoid creating a new acquisition.
Focus-away/back ABA invalidates keyboard activation; repaint/geometry refresh
and same-target focus preserve it. Core Enter/Space waits for activation release,
with the source's cross-key generation semantics and modifier/key cancellation.

`tab-stop-host.mjs` only maps export names into the unchanged shared
`createFocusVisibleHost` transport. The hidden editable textarea, modifier-only
filtering, raw coordinates/keys/modifiers/repeat, pixel wheels and cleanup are
reused. Actual Chromium `beforeinput` linebreak/paragraph events forward their
own unmodified core Enter down/up pair. They are not inferred from a physical
Enter keydown and do not change platform-native key delivery.

## Exports and painting

- `tab_stop_metadata()` returns source identity, viewport and initial14 runs.
- `tab_stop_content()` returns current source message and14 current runs.
  Measure widths in message, five cards, two ordinary buttons, group1's three
  children, group2's three children order. All use IBM Plex Sans16px/400.
- `tab_stop_frame(widths, scale)` accepts14 finite positive shaped widths and
  a finite session-fixed scale greater than0 and at most4. Width bounds are
  `[768,762,762,762,762,762,370,370,762,762,762,762,762,762]` to keep this
  source's labels single-line. Invalid/collapsed metrics return an error
  without changing the live tree or pending gestures. Changing scale requires
  reset. The response includes snapshot, explicit decorations/shadows and
  candidate-only core diagnostics.
- `tab_stop_pointer(kind,x,y,button,shift,control,alt,meta)`,
  `tab_stop_key(label,down,shift,control,alt,meta,repeat)`,
  `tab_stop_wheel(x,y,dx,dy)` and `tab_stop_leave()` reuse the focus example's
  finite input contract. MoonBit handles hits, focus, modality and gestures.
  Leave does not clear focus; there is no invented DOM-blur policy or scrolling.
- `tab_stop_reset()` explicitly clears state and starts a new lineage on the
  next successful frame. Uninitialized/invalid input returns false.

Blue3px source focus borders apply in both Mouse and Keyboard modality; the
non-stop card stays black1px with opacity0.4 on border and text. Only eligible
cards have Mouse-only black-opacity0.1 hover. Their portable hover-background
quad is separate from the full-opacity border, avoiding alpha quantization or
accidentally dimmed focus strokes. Black button fills/white labels are retained.

Solid3px borders are a narrowly validated Canvas host extension. Explicit
`shadows:[{id,kind:"shadow_sm"}]` renders the source's two black-alpha0.1 layers:
(0,1),blur3,spread0 then (0,1),blur2,spread−1. The caster is separate from the
fill, with save/restore isolation. Canvas blur remains an approximation of the
GPUI GPU shadow kernel. The existing hello_world legacy shadow and1px dashed /
4px focus borders remain unchanged.

## Local validation

The18 compiled MoonBit JS tests cover source content/metadata, source-derived
initial/focused geometry, all12 stops and anchors, moving2px ordinary/1px card
edge hits, click-negative controls, exact authored messages, source paint order,
opacity/hover, modality-independent rings, pending gestures, same acquisitions,
ABA, reset/fresh paint isolation, core key activation, modifiers, repeat,
wheel, invalid input/metrics and fixed session scale. Host/renderer tests cover
transport reuse and actual beforeinput separately, validated3px strokes and
both shadow layers, invalid-payload fail-before-draw, alpha and existing paths.

Run the package in a disposable exact-core archive as
`examples/conformance_tab_stop` with `moon fmt --check`, `moon test --target js`
and `moon build --target js --release`. `build_moonbit.py` also tests/builds all
registered candidate packages without running Rust or a browser. Historical
Rust-only packaging tests use an immutable old catalog fixture; normal current
packaging includes tab_stop and rejects duplicate `--extra-example tab_stop`.

Current site builds use the exact published core in `../../examples.json`. The drag
session integration advances that pin to `fc53cb382c66f68bfc1b3e1cc72d01056cd3c625`, tree
`c9ec59c5fbdbd84548b7d6ffe2c99b8403509db9`; this does not relabel the initial local or
retained tab-stop evidence above. A fresh strict paired regression is required.
