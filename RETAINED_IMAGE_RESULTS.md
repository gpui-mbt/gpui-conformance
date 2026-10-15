# Deterministic evaluation of retained native images

The new evaluator is usable end to end without launching a window or browser,
reading another app, requesting macOS permissions, or using VLM credentials.
It verifies the existing suite's complete native execution evidence, encodes
its unchanged RGBA8 buffers to PNG and runs pinned vlmkit's deterministic PNG
diff. Whole RGBA bytes, physical dimensions and device scale remain authoritative.
A normal tool exit or a subjective model judgment cannot establish a pass.

| Retained input / control | Exact differing pixels | vlmkit JSON / exit | Analysis result |
| --- | ---: | --- | --- |
| Historical native positive pair | 0 / 196,608 | pass / 0 | pass |
| Historical real blue-rectangle negative pair | 12,288 / 196,608 | changed / 0 | mismatch |
| Same negative with per-pixel threshold 1 | 12,288 / 196,608 | pass / 0 | mismatch |
| Current min/max build-only native preparation | no executed readback | not invoked | unverified |

Both retained frames are 512×384 physical pixels at device scale 2. The negative
changes 6.25% of the frame. A threshold is pixelmatch's per-pixel tolerance,
not an allowed changed-area ratio. No masks, rescaling, crop substitution or
ratio allowance is used. A complete exact pixel mismatch cannot be excused by
a permissive diagnostic threshold.

These results analyze **historical native artifacts**, not a new native run.
Their original suite is `316a62d3b33fa8038c900b4f2e1058b1c96f395e`,
GPUI is `d9afb21688e04f89d9e94d96d33eb530aef90886` (0.2.2), and MoonBit is
`24bf42ca3bfb5dd3d2fe2b03271605dee99e13ba` (0.7.2). The analyzer and complete
toolchain were actually executed at clean suite
`2f10d411d145e73f872c79de17871d732b377c83`. Later documentation/index commits
do not relabel those executions. Current min/max native evidence remains
build-only/unverified; no historical success is promoted to a current candidate.

## Reproduce and verify

`visual_pins.json` binds f4ah6o/vlmkit
`b6ff83bb5f357e4ea3225af717479c6be74b2328` (0.23.2), its complete source
archive, tree, lockfile and MIT license hashes. No vlmkit source was changed.
Preparation extracts a clean pinned Git archive into a fresh isolated directory,
installs locked dependencies with lifecycle scripts disabled (offline by
default), builds the MoonBit policy and JavaScript packages, then records all
11,897 runtime files/symlinks and 267 separate source/build-artifact hashes.
Export routing, dependency payloads, generated policy bytes and symlinks are
recomputed before and after evaluation. Missing inventory entries or changed
code/routing fail verification. Node, pnpm, MoonBit, process commands/PIDs,
aware timestamps, logs and exact source revisions are retained.

Use an existing compatible MoonBit SDK on PATH and set its matching MOON_HOME.
This run uses moon 0.1.20261012 / moonc 0.10.15+943464bfa, Node 26.8.2 and pnpm
10.29.3. Preparation explicitly builds vlmkit's MoonBit semantic policy; the
initial JS-only attempt failed on the negative because its lazy policy build
found the old default SDK. That failed attempt remains retained as unverified.
No SDK was installed and no source dependency was substituted.

```sh
python3 prepare_visual.py --vlmkit-source /path/to/pinned-vlmkit \
  --store /path/to/task-pnpm-cache --output _build/fresh-visual-toolchain
python3 evaluate_native_images.py --evidence /path/to/retained-native-run \
  --toolchain _build/fresh-visual-toolchain --output _build/fresh-image-analysis
python3 verify_native_images.py _build/fresh-image-analysis \
  --evidence /path/to/retained-native-run --toolchain _build/fresh-visual-toolchain
```

A cold dependency cache requires explicit `--online` and normal network access.
No browser/model credential is needed. The evaluator returns 0 for analysis
pass, 1 for mismatch and 2 for unverified. The verifier recomputes an existing
report; its own successful exit confirms verification, including a verified
mismatch, and does not indicate a new framework execution.

Each analysis directory retains source-bound PNGs, actual diff JSON/stdout,
stderr, process metadata and any heatmap. `report.json` distinguishes original
native revisions from the analyzer revision and says `native_execution: not-rerun`.
The diagnostic command is bound to the pinned entrypoint, both PNGs, exact
threshold and JSON/no-mask option shape. Verification accepts relocated raw
directories without changing recorded original process paths. The committed
`visual_results/macos-arm64-20261015.json` is an index, not a replacement for
raw evidence, runtime files or original native artifacts.

## Checks and remaining native work

Thirteen new portable guards cover lossless PNG bytes, whole-frame differences,
metadata/scale mismatches, invalid status/metrics, missing execution, runtime
inventory omission/tampering, symlink routing, command/SHA/threshold binding and
aware process chronology. Fourteen existing portable tests and all 61 original
real-evidence adversarial tests remain applicable. All 13 pinned vlmkit PNG-diff
tests pass. Synthetic unit data never qualifies a framework execution.

The first usable deliverable is deterministic analysis of verified retained
readbacks. Visible-window lifecycle, external AX observation and physical input
remain **unverified**. Rust's current native fixture is hidden and short-lived;
MoonBit's path presents and activates unconditionally. The needed owned-window
ready/ack lifecycle, PID/start/executable/window/frame binding, AX trust checks,
stale/foreign negative controls and post-action state proof are specified in
[NATIVE_OBSERVER_PREREQUISITES.md](NATIVE_OBSERVER_PREREQUISITES.md), with a
machine-readable status in [native_observer_status.json](native_observer_status.json).
No new permission, screen capture, security setting or running app/service was changed.
