# Resource-backed image prerequisite: acceptance frozen before runtime execution

Suite source baseline: `0816b45b743dc34376f5c945fe6fc01dfd0b240a`.
Upstream source: `zed-industries/zed@5a5fbe79917971a4d52a96b6ddb04da198a5012e`.
Exact future core commit must be recorded after independent source review, before paired execution.

This is a separate prerequisite, not a nineteenth full example port and not full opacity.rs pixel parity.

## Asset and preparation

Use the original `crates/gpui/examples/image/app-icon.png`, 168173 bytes,
Git blob `08b6d8afa0d1088e50f1e9697e01407c9c623f6d`, SHA256
`77453d98d46494b3b34b94aa863b686ea299e0190030a5c7ca5377b238332522`, 512×512 RGBA.
Retain original bytes, source URL, dimensions and digests. Resource identity means these exact encoded bytes.
Static PNG decoding is host preparation, not a core decoder claim. Browser preparation checks byte cap,
PNG header/chunk boundaries, static format, exact digest, dimensions, and decoded dimensions before admission.
Opaque prepared tokens keep decoded bitmaps private. Do not infer image content from resource ID alone.

## Required source/runtime proof

1. Real core layout/prepaint image binding emits resource-backed SceneSnapshot image items.
2. Core computes contain geometry. Independent pinned Rust source test uses a 100×200 portrait in an explicit
   100×100 element; fitted sprite is [25,0,50,100]. This geometry fixture is separate from the original square PNG.
3. Actual PNG displayed at 32×32, at nested inherited opacity .5×.5=.25 and sibling opacity 1.
   Preserve intrinsic encoded alpha; apply inherited scalar once. Clipping and image element crop are explicit.
4. Interleave quads/images in actual snapshot order. No host overlay, placeholder raster, fitted-bounds calculation,
   or JavaScript ancestry traversal may produce the candidate result.
5. All referenced resources must be prepared and immutable-matching before any destination Canvas method.
   Missing resource test starts with a sentinel destination and requires unchanged pixels and zero draw/clear calls.
6. Retain two independent actual-runtime captures with fresh run IDs, exact code/core/asset provenance,
   original scene output, screenshot bytes, browser version and scale. Tests or handwritten frames cannot satisfy this gate.
7. Independent actual Rust GPUI observer emits live sprite bounds, content mask, opacity and atlas sprite properties;
   source constants cannot substitute for observations. If no Rust GPU screenshot is available, report numerical
   sprite parity and browser-visible asset proof separately. Never label them full cross-runtime pixel parity.

## Negative controls

Each control must be rejected by its relevant acceptance assertion: omit image; use wrong resource bytes;
ignore inherited opacity; apply inherited opacity twice; stretch portrait instead of contain; missing resource
after a valid earlier quad. Positive comparator self-checks and synthetic mutations alone are not runtime coverage.
Wrong-resource bytes must fail preparation; missing-resource must fail before destination mutation.

## Explicit bounded host subset

Static PNG, one frame, 32 resources, each axis ≤4096, aggregate decoded pixels ≤4194304,
aggregate encoded bytes ≤16777216. Identity item transforms only; transformed images and animations fail closed.
Core may represent a larger domain. Host subset does not promise GPU interpolation/color conversion equivalence.
No deployment, workflow or security changes. Publication waits for exact-core-pin independent review.

Full opacity.rs still needs its GIF timeline, SVG semantics, custom shadow, wavy underline and event/animation
composition. No current catalog admission or passing status is changed by this prerequisite.
