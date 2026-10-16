# Retained text example captures

These PNGs and `result.json` are byte-for-byte copies from
[browser CI run 38848834623](https://github.com/gpui-mbt/gpui-conformance/actions/runs/38848834623),
artifact `browser-example-evidence` (ID 12024552084). The downloaded ZIP SHA-256 is
`51d12b0359e62cd04f830baab9c5631d2d7cb9fb41bd6a6d20ddac508147bb70`.

The run tested PR head `422f94adda8be205248f370a335785a9d5940118` through synthetic merge
`0cf172c7c2855ef35f1688f30b2b1610e590b276`. Both have tree
`a2b0383ed0b26a334160ffe30f25eaa30b78a23e`. These are the original capture revisions,
not the later commit that retains the images or publishes the catalog.

`captures.json` records the source run, build, source-file blobs, report digest and
each image digest/dimension. The two catalog assets exactly match the candidate PNGs.
Neither the source images nor their display copies are resized, cropped or retouched.
CSS scales the catalog preview while retaining the complete image.

The actual compiled MoonBit and unchanged upstream Rust/WASM examples executed in
Chromium on Linux. Both captures for each example are 800×600. The report records
the integer CSS-pixel capture bounds and runtime details. The existing `raster_comparison`
inside the raw report measures **hello_world only**. It is not a text example score.

These images supply previews and inspection evidence, not pixel/native conformance.
The text examples retain `unverified` status and no pixel counts. In particular,
text_wrapper's CJK fallback differs: the Rust capture contains missing-glyph boxes
while the Canvas2D candidate uses the browser's fallback font. The Rust images are
retained alongside the candidates so that difference remains inspectable.
