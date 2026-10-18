# Source-derived pattern candidate

Original: `zed-industries/zed@5a5fbe79917971a4d52a96b6ddb04da198a5012e`,
`crates/gpui/examples/pattern.rs`, blob `7d2e98d16e24dc23dc307296a3b35c18e624d9e3`.
The Rust builder registers that unchanged file in a relocated standalone manifest.

The candidate retains the fixed 600×600 root, column/gap12/center alignment,
two intrinsic-width label groups, all eight source rectangles, four blue borders,
translucent half-green parent, red control and 45-degree red→blue control.
ElementTree performs layout and prepaint. Scene bindings call the actual core
SlashPattern API. There is no JavaScript stripe renderer or geometry fixture.

Only 600×600 at DPR1 is initially supported. Other viewport/DPR combinations
fail closed, rather than borrowing a qualification from this profile.

## Paint order and alpha

The source has two labels interleaved with paint. Its paint is normalized to
one opaque core run followed by the two labels, retaining their original order.
This is safe only when later source paint cannot overlap the actual rendered
label ink. The host uses the same font/baseline as the existing Canvas text
renderer, measures actual glyph bounding boxes, expands by one physical pixel
for antialiasing, and rejects overlapping later source rectangles before drawing.
MoonBit tests retain the source layout ordering; host tests reject glyph overflow
that line boxes alone would miss. This normalization must be independently reviewed.

The opaque run includes the white root, parent alpha, stripes and borders.
Core performs linear source-over and final byte conversion. Canvas uploads that
opaque tile and then paints the disjoint labels; it does not blend pattern alpha.
The root shadow lies behind an opaque viewport-sized white root, with external
shadow clipped by the source viewport. Its kernel remains unverified.

## Evidence boundaries

`web/pairs/pattern.json` freezes source-specific screenshot acceptance before
candidate execution. Original Rust and MoonBit screenshots come from independent
runtime navigations. Eight stripe regions, alpha background and two controls are
checked separately, with retained original pixels and served executable hashes.
Text/shaping, shadow kernels, antialias edges, full-image equality, arbitrary
viewport/DPR, native/Metal and general SlashPattern parity are not claimed.

`build_pattern_controls.py` compiles disposable wrong-interval, phase, color and
missing-row mutations. Its separate manifest states intentional modification,
retains baseline/source/runtime identities and records failing mutation tests.
The browser control runner requires the expected named pixel-region rejection;
an arbitrary setup/runtime crash cannot count as a visual control. Missing
runtime is a separate blocked-executable failure control.

Local source checks do not establish an actual browser pass. MoonBit compilation
and the real paired capture must succeed at the exact reviewed core/suite heads.
