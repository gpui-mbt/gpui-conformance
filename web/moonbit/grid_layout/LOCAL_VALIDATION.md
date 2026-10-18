# Candidate-only local validation

This is source/candidate evidence, not a Rust or browser comparison.

The candidate was checked and compiled with Moon 0.1.20261012 (`748b63c`),
using the corrected local core commit
`2eea727505a46cecd16c9874ae5ed8e6fdc1d996`. Its exact tree is
`a6d5e8a048b6b4bc4a9f30912d8edf93581a8bd9`, identical to the live catalog's
published core commit `aafa754affa049c1eaf69c75c1d04c5d895d3677`.
The public/local commit IDs differ; the tested source tree does not.

- Six MoonBit JS white-box tests pass, including actual core layout bounds,
  threshold selection, spans, fixed overflow, source text anchors and wrapping,
  resize restoration, and invalid-profile/metrics rejection.
- A package-only debug ESM build succeeds. The actual-export Node test exercises
  all eight source-profile resize states and passes through the real SceneSnapshot
  validator and Canvas adapter with drawing recorders. It also rejects unsupported
  viewports and invalid metrics.
- The complete Node source suite passes 638 tests, with three existing unrelated
  actual-runtime tests skipped. The new grid actual-export test was enabled.
- All 51 web Python tests pass using the existing exact Pillow 12.0.0 installation.

The optional actual-export test requires an actual compiled file:

    GPUI_GRID_LAYOUT_RUNTIME=/absolute/path/to/grid_layout.mjs node --test web/tests/grid-layout-candidate-runtime.test.mjs

Without that input it explicitly skips. Mock host tests are named separately
and cannot stand in for this actual-export run.

Initial failures were retained: the first white-box test compile inferred `Int`
for two multiplication literals, corrected to `4.0`; the unpinned system Python
had Pillow 12.3.0 and was properly rejected by the unchanged 12.0.0 decoder gate.
No decoder pin, comparator tolerance, or behavior assertion was weakened.

The temporary candidate package reused the existing JS cache. Peak cumulative
cache growth was 4,839,961 bytes, below the 10MiB limit; free storage stayed above
1GiB. Only manifest-enumerated temporary candidate source/generated files were
removed afterward. A separate retained compiled module, source hashes, logs,
and cleanup manifest preserve the run locally.

No browser rendering, original candidate screenshot, GPU/text raster
comparison, paired Rust execution, or native conformance is established here.
The immutable Rust-only baseline catalog and historical engine pin are unchanged.
