# Source-derived popup compositing correction

## Original failed observation remains a failure

The first unchanged browser run 38991697801, job 117275284232, public head
`12fe1ef3`, successfully built Rust/WASM and captured initial idle plus one trusted
TopLeft hover. It failed before 41-state completion. Artifact 12085432851 original
ZIP is 11,207,464 bytes, SHA-256
`776635b445c179d80f8999cd9044a767b32387df9de78f8b488d6e53f3afafaa`.
All 166 original entries, including 90 identical hover-attempt PNGs, remain intact.

Every hover attempt had PNG SHA-256
`caf42e4317049a69349fa7ab0b5997ba76b61f59c54c95b4482d7e8b6923e652`
and complete decoded RGBA SHA-256
`434fcdfe01d324a6d16ad0d1c1bf04cc3067421385e33a454b7a54f87c5abb3f`.
The source 120x65 hovered button was independently measured at visible bounds
`[119,82,239,147]`. Trusted pointer/mouse transport was delivered inside it.
The visible popup was present, but the original exact 63/64-gray component mask
found no substantial popup. Its largest exact-gray fill was52, with shadow-varying
interior grays. This diagnoses a color-segmentation premise, not missing hover
state, source placement or instability.

The original profile v1, failed JSON, PNGs, input stream and verifier failure are
not rewritten. A replay under corrected source premises can establish only the
already captured idle/TopLeft states. It cannot supply missing hover exits,
other anchors, inert center, resize, snap or restoration evidence. Full profile
qualification remains pending fresh isolated CI and independent artifact review.

## Pinned source derivation

All following sources belong to the same exact engine revision
`5a5fbe79917971a4d52a96b6ddb04da198a5012e`, tree
`990fb995914d51a546b20e5cf0382dafc105c299`:

- `crates/gpui/examples/anchor.rs`: source popup is black opacity 0.75 with
  `shadow_sm`; blob `b4b280b714a61cea2cd3f3a8ffd82a8f0000eb6b`.
- `crates/gpui_macros/src/styles.rs:428-438`: `shadow_sm` is two black alpha 0.1
  drop-shadow layers, each offset (0,1). First blur radius 3; second blur radius 2,
  spread −1. Blob `4a1bb5c98a3efbb8da8ab3274b8d8ef1e34a08d4`.
- `crates/gpui/src/style.rs:691-740`: drop shadows paint before background,
  then inset shadows/contents. Blob `9150fdded91b817305454f18beb0a0b7d6c5966a`.
- `crates/gpui/src/window.rs:4572-4605`: each non-inset shadow becomes a separate
  scene primitive with its authored color/alpha. Blob
  `33fa14bfea6ebad50743d6d4014955d1055ef772`.
- `crates/gpui_wgpu/src/shaders.wgsl:320-341,391-395,1000-1045`: separable shadow
  coverage multiplies source alpha; final color handles straight/premultiplied
  output. Blob `718cb7595d86f73cd91a65bcbf42682004dbba4d`.
- `crates/gpui_wgpu/src/wgpu_renderer.rs:383-392,708-718`: prefers non-sRGB 8-bit
  UNORM surfaces; selects matching alpha/premultiplied blend state. Blob
  `ff4af7d26e1e6706bdd02e0079fea46ace274086`.

The x shadow integral is bounded by 0..1. The y integral uses four positive
Gaussian midpoint samples, spacing at most 1.5 standard deviations. Its finite
sum is no larger than the infinite Gaussian lattice. Poisson summation bounds
that lattice by `1 + 2q/(1-q) < 1.00031`, where
`q = exp(-2*pi*pi/1.5^2)`. The source-derived envelope uses the conservative
coverage upper bound 1.001, also leaving room for f32 arithmetic; it does not
assume that the four-sample approximation is perfectly normalized.

For fully covered black fill on a white backdrop with the two preceding shadows,
straight and premultiplied alpha yield the same channel product:

    255 * (1 - 0.1*c1) * (1 - 0.1*c2) * (1 - 0.75)

Coverage values range from zero to the conservative1.001 bound. Permitting
8-bit downward rounding at each layer gives minimum gray 51:

    floor(floor(floor(255 * .8999) * .8999) * .25) = 51

With no shadow coverage, `ceil(255 * .25) = 64`. Thus the corrected mask is
opaque achromatic integer gray 51..64. It includes the source-permitted range
before considering any observed 52. This is a compositing interval, not a wider
geometric tolerance. Shadow-only pixels stay near 206..255 and cannot provide
this substantial fill class. Text and rounded antialias edge pixels may fall
outside the interval and remain holes/uncertain curved edges.

All original popup/button area, density, width/height, 2px edge, source Local
placement, trusted input, window-snap, inertness and restoration predicates stay
unchanged. Component discovery still scans the full original PNG independently
of expected coordinates and candidate/report geometry.

## Sensitivity and claim boundary

New synthetic tests cover the 51 and 64 boundaries, independent forward compositing
through varying shadow coverage, and unchanged 100x24 synthetic popup geometry.
They reject 50/65, shadow-only 207, non-achromatic (52,53,52), and selected incorrect
alpha 0.5/0.9 results 103/21 under full source shadows. These are explicitly selected
wrong-opacity controls. Another alpha can produce an in-range gray, and its
pixels may pass this bounded mask. The interval does not measure or uniquely
prove source opacity, exact shadow coverage/kernel or decorative compositing
parity. Those remain unverified.

The profile revision changes to
`unchanged_anchor_hover_local_snap_shadow_composite_v2`. Failed v1 evidence is
never relabeled as a completed v2 baseline. A fresh complete run is required.
