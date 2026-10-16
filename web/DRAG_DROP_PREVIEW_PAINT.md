# Bounded drag preview paint

This is source-derived Canvas host support, not a browser-pair or pixel-parity
result. The upstream source is unchanged Zed
`5a5fbe79917971a4d52a96b6ddb04da198a5012e`; `drag_drop.rs` has blob
`8f038ef3308fee9b097e7289665c9fa47cd6945b`.

## Source and descriptor contract

- `crates/gpui/examples/drag_drop.rs:36-52`: the preview is 120×50, uses
  selected-color background alpha **0.5**, opaque white text, and `shadow_md`.
  This background alpha is not element opacity.
- `drag_drop.rs:93-104,112-124`: sources have 2px opaque borders and hover
  background alpha 0.2; the target has a 3px opaque border and selected-color
  background alpha 0.5.
- `crates/gpui_macros/src/styles.rs:444-452`: the first `shadow_md` layer is
  black alpha 0.1, offset (0,4), blur 6, spread −1; the second is black alpha
  0.1, offset (0,2), blur 4, spread −2. Declaration order is preserved.
- `crates/gpui/src/style.rs:711-753`: shadows precede background, child content
  paints next, and a full-bounds border quad paints afterward.
- `crates/gpui/src/window.rs:4572-4603`: shadow color is multiplied by element
  opacity, independently of the background alpha.

`render.mjs` accepts only the fixed preset descriptor
`{id, kind: 'shadow_md', element_opacity: 1}` for this preview. The required
independent `element_opacity` must be finite and in [0,1]. Missing/extra fields,
duplicate IDs, non-quad references, nonpositive spread-adjusted dimensions,
scroll, nonidentity transforms, and mixed legacy shadows fail before any
Canvas call. For `shadow_md`, both dimensions must exceed 4 logical pixels.
Absolute preview bounds therefore require identity transforms.

The preview quad carries opaque RGB plus exact `SceneItem.opacity = 0.5`;
white text carries opacity 1. The descriptor supplies opacity 1 to both shadow
commands, retaining effective alpha 0.1 for each layer. Alpha 128/255 and two
0.05-opacity shadows are not substitutes. The unchanged `shadow_sm` descriptor
is `{id, kind: 'shadow_sm'}` and continues to inherit its item's opacity.

Solid border widths are explicitly 1, 2, 3, or 4. Existing finite/radius and
minimum-bound checks remain; 2px requires at least 4px extent. Dashed borders
remain limited to 1px. Candidate callers lower a source border continuation to
a separate full-bounds transparent quad after text, with an opaque border
decoration. This keeps fill alpha independent of text/borders and retains the
source border's ordering rectangle; the renderer invents no border strips or
after-the-fact repaint.

## Ordering and limits

The existing [tab-stop scheduling model](TAB_STOP_SHADOW_PAINT_ORDER.md) is
preserved with preset-specific offset, spread, and blur parameters:

1. Intersect inherited logical content masks, then outward-cover that mask in
   device pixels (`window.rs:3327-3343,4177-4188`).
2. Outward-cover offset/spread shadow bounds, **without blur tails**; intersect
   the covered primitive and mask; skip empty intersections.
3. Assign one plus the maximum strictly intersecting prior order
   (`bounds_tree.rs:116-135`; `geometry.rs:965-972`). Edge touching is not overlap.
4. Sort by order, then primitive kind (`Shadow` before `Quad`), with stable
   source ties (`scene.rs:88-109,151-162,201-210,288-320`).

Actual Canvas blur tails retain viewport and inherited clips. Independent
commands use save/restore, including when drawing throws. Absent or empty
explicit shadows retain the previous snapshot sequence. There is no inline
per-item shadow substitution or global shadow prepass.

Canvas/GPU blur-kernel equality, full-image/text rasterization parity, arbitrary
transforms, retained layers, general parent continuations, and native rendering
remain unclaimed. The tests use synthetic source-derived scene/command inputs;
they do not execute or imitate trusted browser input or supply original PNGs.
Previously retained failed behavior and original artifacts remain untouched.

## Local validation, 2026-10-16 UTC

- Full bounded host contracts: `node --test web/tests/*.test.mjs`, 549/549 pass.
- Relevant Python contracts: `python3 -m unittest discover -s web/tests -p
  'test_*.py' -v`, 26/26 pass with pinned Pillow 12.0.0.
- Focused renderer contracts: 38/38 pass, including all 18 existing focus/sm
  tests. Only deliberate old 2px-rejection fixtures are changed to explicit
  acceptance; fractional/invalid-width rejection remains.
- Recorder controls reject each missing md layer, incorrect offset/blur/spread,
  reversed layer order, inline ordering, a global prepass, and legacy shadow
  substitution. Reusing fill opacity 0.5 fails **both** independent layer checks
  because each becomes 0.05.

Logs remain under ignored `_build/drag-preview-paint-validation/`. No browser,
Mac, Rust build, candidate/core edit, catalog/pin migration, workflow edit,
publication, comparator-tolerance change, or new runtime qualification was
performed by this paint extension.
