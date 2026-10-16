# Unchanged `tab_stop.rs` Rust-only baseline

This packages the actual upstream example without editing its Rust source. No
MoonBit counterpart is registered. The existing engine pin remains
`61b237b0963c3252736a27293aa1f5b7de3886fa`, tree
`29449e394c0faf2b25beb2a1b6a4bce2806b3231`.

## Exact source

- Browser source revision: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`
- Path: `crates/gpui/examples/tab_stop.rs`
- Git blob: `cc7c34a9979ce4027578ec2c358f503d944ee26f`
- SHA-256: `be187a56c091ee0b609fa396cae4a13b49dcf98ff9e602d8caed3126de3f6a8e`
- The compatibility revision `d9afb21688e04f89d9e94d96d33eb530aef90886`
  contains the same blob and bytes.
- The source already defines a WASM start at lines 215–219.

`build_rust.py --oracle-only --extra-example tab_stop` adds this single binary
in the relocated standalone gallery manifest. The original package and all
archived upstream files remain unchanged. `--oracle-only` without an explicit
recognized extra oracle fails; an already implemented example cannot be relabeled
as an extra Rust-only baseline. The manifest retains the actual compiler,
bindings generator, command, source commit/tree, UTC completion timestamp,
packaging hash, unchanged source input and output-file hashes. All eight source
font inputs are retained and independently checked against their pinned hashes
and the actual served WASM bytes that embed them.

## Source order and observations

At actual 800×600 DPR1, forward traversal from the initially focused non-stop
root is:

1. item0 [1]
2. item1 [2]
3. item4 [2], the fifth card on screen
4. item2 [3], the third card on screen
5. el1 [4], el2 [5]
6. group1 children [6,1], [6,2], [6,3]
7. group2 children [7,1], [7,2], [7,3], then wrap

Reverse traversal and wrap use the inverse order. Root, item3 and the group
containers are not tab stops. The groups' literal anchors are [6,6] and [7,7];
this baseline does not claim that directly focusing a container enters its own
first child. Only el1/el2 have click-message listeners. Cards and group buttons
must not acquire invented listeners. Tab and Shift-Tab each set their own
source-authored message.

Focus is inferred from the source's 3px blue border and subsequent navigation.
DOM active element is transport metadata only. No private diagnostic focus state,
substitute screenshot, candidate renderer or mocked oracle is used.

The root is flex-column, but group divs retain default Block layout. The natural
content may exceed 600px. The first actual run observed flex-shrunk cards and
fully visible groups. A
focus border change from 1px to 3px changes flex allocation and rounded card edges;
rectangles from differently focused screenshots cannot be combined. The corrected
runner first retains the entire forward/reverse sequence, then independently
parses all five cards, both ordinary buttons and both groups within each frame.
It checks source paint identities, exact 12px gaps, black 1px/blue 3px card borders,
the gray non-stop card, and equal ordinary flex1 inner widths after subtracting
their own source borders. No observed y/height lookup table defines the oracle.
The coordinate-dependent click extension is adaptive: each next click uses the
immediately preceding retained frame's current control bounds. It fails closed
if that source geometry does not hold. A failed hypothesis retains all prior attempts, the complete operation log and a failure screenshot;
the Rust source is never changed to make it fit.

## Isolated CI and retained evidence

The `Unchanged tab-stop Rust oracle` workflow is separate from the existing
45-minute matched-examples job. Its 60-minute job prepares the normal pinned
site, builds only tab_stop Rust WASM, then gives discovery 15 minutes and the
independent verifier 10 minutes. Existing matched-example gates are unchanged.
This artifact-only site is not a publication or a complete matched runtime lab.

The discovery runner retains:

- Every original full-viewport PNG attempt, including failed attempts
- Two separately requested samples with identical complete decoded-RGBA hashes
- Pinned Pillow 12.0.0 decoding through a bounded local binary stream, avoiding
  large browser-side JSON pixel transport; decoder source and hash are retained
- Actual served JavaScript/WASM/host response bytes and hashes
- Source input, embedded font inputs, build/catalog copies and hashes
- Trusted pointer/keyboard events, exact complete operation order, console,
  network errors, canvas dimensions and observed border geometry

`verify-tab-stop-results.mjs` rereads the retained PNGs and executable/input
bytes. It recomputes geometry, checks physical card positions, hierarchical
forward/reverse order, wrap, the fourth non-stop card, only the authored click
listeners, message pixel relations, exact trusted operations and stable samples.
The revised source profile has 128 operations and 72 capture states. Its three
moving-edge probes click item0's newly visible 1px bottom edge and el1/el2's new 2px
ordinary-button edges, deliberately outside frozen initial hit bounds. Each
retains hover/down/up focus and message evidence plus the next Tab destination.
Coordinates are derived from independently parsed current frames, not copied
from the historical capture. These additional click/edge states still require
actual CI execution.

It does not trust the discovery report's claimed checks or geometry. Strict
verification also binds the retained build's lab revision/tree to actual current
Git HEAD and HEAD^{tree},
requires clean tracked files, and hashes the actual current `web/examples.json`
bytes against the retained catalog hash. Historical artifacts keep their original
labels and require their exact frozen build checkout for strict verification;
changing labels cannot make them current. Corrupted
copies test sensitivity, including the decisive flattened-order negative control:
flattening local [6,1] to [1] changes the second Tab from item1 to group1 child1.
Synthetic unit fixtures only test comparator rejection; they are never runtime
evidence or a conformance pass.

After a committed build, run:

    python3 web/scripts/build_rust.py --upstream-source _sources/zed --site _build/tab-stop-browser-lab --target-dir _build/tab-stop-rust-target --oracle-only --extra-example tab_stop
    BROWSER_EVIDENCE=_build/tab-stop-oracle-evidence PLAYWRIGHT_ROOT=/path/to/pw node web/tests/tab-stop-oracle-browser.mjs _build/tab-stop-browser-lab
    node web/tests/verify-tab-stop-results.mjs _build/tab-stop-oracle-evidence

Status at introduction was source/packaging/comparator unit contracts only.
The retained first CI run below established a partial Rust discovery prefix;
the corrected full 72-state source profile remains unexecuted locally and must
be established by a new actual CI run. A successful source-profile verification
still makes no claim about a MoonBit counterpart, native parity, exact message
OCR/text or full-image equality, other browsers/GPUs/viewports/DPRs, touch/IME,
or directly focused group-container anchors.

## Retained first-run failure and separate correction

[GitHub Actions 38919267792](https://github.com/gpui-mbt/gpui-conformance/actions/runs/38919267792)
compiled the unchanged Rust binary and retained 27 stable states, 54 original PNG
samples, 53 operations and 80 events. It failed before the click phase because the
original comparator combined el1's focused-frame right edge with el2's separate
focused-frame left edge, manufacturing an 8px gap. Each individual original frame
has the source-authored 12px gap. Initial-card height equality across focus frames
was likewise invalid because border widths affect flex shrink/rounding.

The first artifact 12054297704 has SHA-256
`4f607c244fb609218852165378d9f38c4bf7b34e353725513425e1a065c5b4c3`.
Its original lab revision is `79b09d1133d650a94c91991ed6c42c03e618d0ff`, tree
`ae5899e1ebb4a1839e61194a7f85b26b2abc745a`. The original failed report, PNGs,
operations, runtime/font/source inputs and failure screenshot remain unchanged.

A separate read-only reanalysis with the corrected per-frame parser rehashes and
decodes all 54 samples and validates the 27-state traversal prefix and its negative
controls. This is retrospective partial evidence, not a rerun, a relabeled pass,
a full click/edge profile, or counterpart qualification. Corrected future runs
carry profile revision `state_specific_geometry_and_moving_edges_v2`.
