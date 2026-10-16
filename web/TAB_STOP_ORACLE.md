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
content may exceed 600px. Exact vertical positions, shrink behavior and clipping
have not been observed yet. The runner first retains the entire forward/reverse
sequence, then derives actual border geometry constrained by source paint order
and independently detected initial card edges. The coordinate-dependent click
extension fails closed if those hypotheses do not hold. A failed hypothesis
retains all prior attempts, the complete operation log and a failure screenshot;
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
It does not trust the discovery report's claimed checks or geometry. Corrupted
copies test sensitivity, including the decisive flattened-order negative control:
flattening local [6,1] to [1] changes the second Tab from item1 to group1 child1.
Synthetic unit fixtures only test comparator rejection; they are never runtime
evidence or a conformance pass.

After a committed build, run:

    python3 web/scripts/build_rust.py --upstream-source _sources/zed --site _build/tab-stop-browser-lab --target-dir _build/tab-stop-rust-target --oracle-only --extra-example tab_stop
    BROWSER_EVIDENCE=_build/tab-stop-oracle-evidence PLAYWRIGHT_ROOT=/path/to/pw node web/tests/tab-stop-oracle-browser.mjs _build/tab-stop-browser-lab
    node web/tests/verify-tab-stop-results.mjs _build/tab-stop-oracle-evidence

Status at introduction: source/packaging/comparator unit contracts only. Rust
build, browser discovery and independent actual-artifact verification have not
run locally. CI must establish them. A successful source-profile verification
still makes no claim about a MoonBit counterpart, native parity, exact message
OCR/text or full-image equality, other browsers/GPUs/viewports/DPRs, touch/IME,
or directly focused group-container anchors.
