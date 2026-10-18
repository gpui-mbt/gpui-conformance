# Supplemental actual GPUI flat deferred priorities

Status: authored first-stage diagnostic. No Rust execution is claimed by local source or synthetic tests. Independent source approval must precede publication/CI. Independent inspection of the resulting original Rust artifact must precede any candidate-core implementation.

## Bounded scope

Pinned upstream: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`, tree `990fb995914d51a546b20e5cf0382dafc105c299`.
Suite base: `550e7f9a62190a31a76bd61a1de44fbf3944acf1`, tree `930d673885e3eb21f2656fd6ef28413ae7a49fba`.

Sixteen font-free cases cover eight families at scales 1 and 1.25, with the test platform's initial scale 2 retained separately. Families: ascending 0/1/2, descending 2/1/0, equal priority 1, reversed equal-priority structure, equal priority 0, explicitly transparent/noninteractive top layer, explicitly occluding top layer, and propagation-stopping top layer. Each has ordinary overlapping content before and after three flat anchored attachments. Every attachment owns a root plus two overlapping child boxes. Each case observes baseline, priority change, removal, and restoration of the complete original configuration, with an actual left-click after each stage.

`deferred.rs` delegates layout, queues the child in prepaint and has an empty wrapper paint. Pinned `window.rs` sorts each prepaint round by priority, then sorts all deferred records stably for paint. The diagnostic restricts itself to one flat round. `examples/popover.rs` motivates the priorities only; it is retained as source context and is not executed unchanged.

Excluded: nested deferred elements, outside-click semantics, view caching/reuse, arbitrary deferred content, full popovers, native windows, browser/core parity, raster pixels and clipping behavior. Bounds and masks are observations at real element callbacks, not a GPU scene primitive dump or proof of raster visibility.

## Observation versus prediction

The Rust adapter contains no priority sorter, expected callback list, geometry solver or hit tester. Its `Observed<E>` wrapper logs before/after callbacks and delegates arguments, returned layout state and prepaint state unchanged to public GPUI elements. Raw events retain actual request-layout, prepaint and paint entry/return ordering, bounds, prepaint offsets, prepaint/paint content masks, operation/frame numbers, and actual mouse-down callbacks. Raw input is echoed unchanged and includes every listener, propagation and occlusion setting. Transparent content has alpha zero, no listener and no `.occlude()`.

Checker predictions are separately named `checker_derivation_not_observation` and `checker_input_derivation_not_observation`. Input prediction is not a core reverse-paint topmost-hit approximation. Pinned GPUI builds hovered hitboxes in reverse prepaint order until an explicitly blocking hitbox, then invokes separately paint-registered bubble listeners in reverse registration order until explicit `stop_propagation`. With ordinary non-occluding listeners the overlap can invoke many callbacks. Div's listener installation and window's hit testing/dispatch are retained and source-bound. Observed callback sequences remain in the raw artifact and report, independently of those hypotheses.

The predeclared allowance is `2^-10` logical pixels for qualified geometry and `2^-10` physical pixels for grid checks. IDs, callback order, phase, masks, propagation settings and operation identities are exact. The corpus fixes a 320×240 viewport, attachment bounds 48,48,128,96, two 80×64 children at offsets 0,0 and 24,16, and input 88,80. All authored extents are integral physical pixels at every exercised scale. This does not generalize a tolerance to arbitrary layouts.

## Evidence and failure retention

The runner requires clean exact suite/upstream identities. It retains source bytes, upstream contract bytes, the input/profile/schema, frozen unchanged reference-diagnostic bytes, the original and relocated manifest, original/build lock, compiler and Cargo original stdout/stderr, a pre-build plan, commands, run token, build stdout/stderr, ELF, exact original runtime stdout/stderr and an identical `raw.json` copy. Digests cover the complete successful inventory; external independent verification can compare every retained byte with exact committed source objects. Merely rehashing changed source does not establish authenticity. No source-bound claim is made without the expected suite commit/tree and both source repositories.

Build/runtime failures and invalid/partial runtime JSON are retained. A failure writes `run-failure.json` or `verification-failure.json` with the original logs. A fresh output directory and unique build/run token prevent overwrite or cross-run reuse. Failure artifacts are for diagnosis and are never accepted as a passing observation bundle. The workflow uploads artifacts with `if: always()`.

The isolated build requires 8 GiB initial headroom; workspace and `/tmp` must retain a strict 1 GiB floor, monitored while subprocesses run. It never deletes retained evidence or caches. Local source/synthetic tests do not compile Rust. No Mac Mini, browser or native executor is involved.

## Commands

Lightweight source/synthetic controls:

```sh
python3 -m unittest discover -s tests -p 'test_deferred_priority_diagnostic.py' -v
```

After independent source approval, the dedicated CI workflow runs:

```sh
python3 diagnostics/deferred_priority/run.py --online \
  --upstream-source _build/upstream-source --output _build/deferred-priority-evidence
python3 diagnostics/deferred_priority/verify.py _build/deferred-priority-evidence \
  --suite-commit "$(git rev-parse HEAD)" --suite-tree "$(git rev-parse HEAD^{tree})" \
  --suite-source . --upstream-source _build/upstream-source
```

When inspecting a downloaded artifact, supply `--recorded-execution-root` with the exact original evidence directory recorded by CI. This relocates inspection only; the verifier still checks the exact original build and execution commands. A synthetic test ELF header is a packaging control, not execution or source authenticity evidence. Frozen reference files are retained unchanged without claiming a new run of those existing diagnostics.
