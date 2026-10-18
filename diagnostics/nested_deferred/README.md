# First-stage nested deferred diagnostic

This supplemental diagnostic observes actual public GPUI element callbacks on the pinned headless test platform. It does not implement a nested-deferred core feature or establish core, browser, native-window, raster, input, cache-reuse, scrolling, arbitrary nesting/content, or unchanged popover parity. Existing flat deferred input/lifecycle qualifications remain unchanged. The original external 109/55 corpora are not rerun or edited.

## Frozen inputs and source hypothesis

Suite base: `e576fd9ee3864238eacf59f796e756a44f24790a`, tree `83d2dd9b59421317b670f6547cb61d979804e246`.
Upstream: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`, tree `990fb995914d51a546b20e5cf0382dafc105c299`.

Eight cases comprise four families at scales 1 and 1.25. Every bootstrap frame at the test platform's actual scale 2 is retained and checked, as are all later frames. The window is 320×240; ancestor origin is (24,20), size 272×192; its final movement is (+16,+12). Each structural outer attachment A/B uses Local, TopLeft and scalar snap margin 8, positions (24,24)/(144,64), root size 96×72. Each has one nested attachment at Local (32,24), size 40×32. Geometry is authored layout/reference input, never final popup rectangles. Every position and extent lies on the physical pixel grid at all retained scales. The geometry avoids overflow and clipping intentionally; it does not requalify margin fitting.

Priorities (A parent/child; B parent/child; updated A parent):

- Increasing: 1/2; 2/3; update to 3
- Child lower: 2/0; 3/1; update to 4
- All equal: 1/1; 1/1; update to 2
- Reversed parents: 2/3; 1/3; update to 0

Each session opens the window, sets the requested scale, changes A's parent priority, removes only A's nested child while retaining the updated priority, restores the entire original tree, then moves the ancestor while retaining original priorities. Every operation's exact input and every observed frame boundary is retained. Two ordinary 12×12 sentinels bracket outer wrappers; two ordinary 12×12 sentinels bracket the nested wrapper inside each outer root. There is no text, listener, occlusion, pointer event, cache, scrolling, or third nesting level.

Pinned `window.rs` lines 3883–3996 sorts each prepaint discovery round by priority while preserving the append registry, then globally stable-sorts that final registry for paint. `deferred.rs` delegates request-layout and defers the child during prepaint. `anchored.rs` computes Local geometry and composes rounded logical element offsets. These are source-derived checker hypotheses, never raw observations.

The reversed-parent baseline is a discriminating witness: append registry A,B,B.nested,A.nested; prepaint rounds B,A then B.nested,A.nested; global paint B,A,B.nested,A.nested. Structural DFS tie order B,A,A.nested,B.nested and parent-contiguous B,B.nested,A,A.nested are wrong hypotheses. Child-lower cases additionally require a nested child to paint before its parent.

## Observations and interpretation

The transparent observing decorator delegates original request-layout and prepaint state and return values unchanged. It records callback entry and return IDs; prepaint entry/return bounds, current logical offset and content mask; paint entry/return bounds and content mask. `Window::element_offset` is a prepaint-only API at this pin, so it is not called from paint or request-layout. No artificial discovery-round events, scheduling model, sorting, or predicted rectangles are emitted by Rust. Full wrapper callbacks are retained separately from the checker's paintable-box projection, which excludes host/ancestor/anchored/deferred wrappers. Every paintable box appears exactly once per phase, with nine boxes after nested removal and ten otherwise.

The checker validates the complete callback transcript, including return boundaries, before geometry and projection checks. Static layout origins, inherited logical offsets, and final device-grid bounds remain distinct. The predeclared absolute geometry allowance and physical-grid allowance are each 2^-10; IDs, priority order, masks, offsets, operation inputs and frame sequencing have zero tolerance. No tolerance may be fitted to execution output.

## Evidence and running

Only the dedicated `nested-deferred-diagnostic.yml` job builds/runs Rust. The cloud development task must not compile or execute the adapter. CI requires at least 8 GiB initial workspace build headroom and monitors strict 1 GiB free floors on the workspace and `/tmp`. It kills the child process group on resource-floor breach or timeout and preserves original output. It uses Rust 1.98.1, the retained locked dependencies, two build jobs, no incremental compilation, and no display server. All baseline tracked hashes are frozen, and source-bound verification requires an exclusively additive diff containing precisely this diagnostic's owned files.

Run in approved CI:

```
python3 -m unittest discover -s tests -p 'test_nested_deferred_diagnostic.py' -v
python3 diagnostics/nested_deferred/run.py --online --upstream-source _build/upstream-source --output _build/nested-deferred-evidence
python3 diagnostics/nested_deferred/verify.py _build/nested-deferred-evidence --suite-commit "$(git rev-parse HEAD)" --suite-tree "$(git rev-parse HEAD^{tree})" --suite-source . --upstream-source _build/upstream-source
```

The evidence contains exact retained suite and upstream source, source commits/trees and cleanliness before/after, relocated build manifest and unchanged lock, toolchain stdout/stderr, build plan and command/environment, executable ELF, raw stdout/stderr and byte-identical raw JSON, timestamps, session token, runtime status and SHA-256 inventory. Original build/runtime failures are retained, never rewritten into success. Workflow uploads are unconditional. Downloaded bundles can pass `--recorded-execution-root` for verification of the original absolute invocation paths.

The checker sensitivity tests use explicitly synthetic transcripts and synthetic bundle fixtures. They reject structural DFS ties, parent-contiguous paint, a missing second discovery round, omitted/duplicated nested boxes, stale removal, bad restoration, offset/mask/geometry errors, forged source, changed raw bytes, wrong session tokens, command/lock/toolchain/budget drift and unsafe paths. They are checker controls, not mutations executed inside GPUI. Source/synthetic checks are not an actual Rust result. An actual immutable CI artifact and independent review approval are required before any later core implementation.
