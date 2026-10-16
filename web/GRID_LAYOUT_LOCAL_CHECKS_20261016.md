# Grid-layout baseline local checks

Recorded 2026-10-16 22:59 UTC, on a branch based exactly on suite main
`b078110468db8bab5ad0ac2eab055fa3172a72ab`.

- New grid JavaScript tests: 13 passed, including synthetic geometry discovery,
  source invariants, all corrupted-evidence controls, runtime/worker/source/font
  provenance and same-document viewport delivery contracts.
- New grid Python tests: 10 passed (6 source-only packaging, 4 strict PNG decoder).
- All browser JavaScript tests with cached Pillow 12.0.0: 626 passed, 3 compiled
  candidate tests skipped, 0 failed (629 total).
- All browser Python tests with cached Pillow 12.0.0: 51 passed.
- Existing portable root contract suites: 73 passed (24 portable, 13 visual,
  8 fixture, 17 observer and 11 AX contracts). No native execution occurred.
- `git diff --check`, Python syntax checks, and browser/verifier JavaScript
  syntax checks passed.

The first broad Node attempt used the environment's Pillow 12.3.0 and correctly
failed the existing pinned-decoder checks. The full rerun selected the already
cached Pillow 12.0.0 and passed. An indiscriminate root `test_*.py` discovery was
also attempted: 195 errors required absent retained native/headless evidence
arguments. It is not a full-suite pass. The five intended portable CI contract
suites were then run independently and passed. These attempts' separate logs
remain outside the source checkout; failures were not overwritten or hidden.

There was no Rust compilation, browser launch, artifact download, candidate
build, public write, upstream source modification, reset, cleanup or deletion of
unrelated work. Roughly 1.3 GiB free space remained at the last check.

The new workflow must still execute the unchanged Rust browser baseline and
produce original screenshots for exact-head independent review. Local synthetic
fixtures are never evidence of Rust grid behavior or conformance.
