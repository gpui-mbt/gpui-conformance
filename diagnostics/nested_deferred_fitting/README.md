# Two-level nested anchored fitting and rounding oracle

This additive Rust-only diagnostic observes a bounded evidence gap, not a known core defect. It uses public GPUI callbacks at upstream `5a5fbe79917971a4d52a96b6ddb04da198a5012e` / tree `990fb995914d51a546b20e5cf0382dafc105c299`. Suite base is `ca784321838a59942cfdbc2a24804f038484974f` / tree `e61878c51a5c42dfd0d5fd34b485c48a76586007`. All 693 existing blob IDs, modes and content hashes are frozen; exactly eleven new paths are permitted. No old observer/checker is modified or rerun under this incompatible additive source identity.

Independent source review must approve this exact model and allowance before dedicated actual CI. Independent review of its original artifact is required before deciding whether any core change or candidate pair is needed. Synthetic tests are checker sensitivity controls, not executed GPUI engine mutations or actual Rust evidence.

## Authored structure and static-reference hypotheses

The viewport is 320×240. An absolute ancestor has authored origin (24,20) and extent 272×192. Its immediate child layout is explicitly Block. It contains an absolute before sentinel, a genuine in-flow 12×8 reference box, two outer deferred/anchored attachments, and an absolute after sentinel. Each outer anchor has one 96×72 root whose immediate child layout is explicitly Block. That root contains an absolute before sentinel, a genuine in-flow 12×8 reference, one nested deferred/anchored 40×32 root, and an absolute after sentinel. Sentinels are 12×12; their absolute positions contribute no unintended flow height. There are exactly two anchored/deferred levels.

Source: `Style::default` is Block (style.rs771–775); `Div::compute_style_internal` starts with that style and refines it (div.rs3413–3414); `Styled::block` explicitly selects Block (styled.rs38–40). `Anchored::request_layout` creates an Absolute/Flex layout node, and `Deferred` forwards that layout ID. The anchor's own Flex layout arranges its one root child; it does not change the explicitly Block immediate parent. The locked Taffy0.13.0 Block implementation records an absolute child's static y from the current Block cursor (block.rs913–935), advances that cursor by the preceding flow child's height (1419–1434), and uses the static position for auto insets (1637–1661); positive reference height prevents collapse-through. Block's cursor therefore advances through the preceding in-flow reference. This supports static outer O0=(24,28) and nested N0=(24,36), before inherited prepaint offsets, as unexecuted source hypotheses. Actual reference, root, anchor and deferred-wrapper bounds must validate those hypotheses. No raw measurement is accepted as an unchecked placement input.

The nested reference-height operation changes both inner reference heights from 8 to 12, making the authored N0.y=40 while O0.y stays28. Ancestor movement changes its origin by (+16,+12), and therefore the two static references. Neither operation supplies final popup rectangles.

The Taffy package binding was checked read-only against an already present registry archive: its SHA-256 is the locked `c034e05f6ee85a12daa63863c2245797715075c70649947aa0da54f3f2ab1d0f`. The archive's `src/compute/block.rs` equals the extracted registry source and Git blob `612747685ba5c3257c5fb3e58c473708145eee87`, matching the assessor's independently inspected official tag commit `45a56299d366ddb383e593a1f0372158d00e8530`. This binds the cited Block source to package bytes; it is source inspection, not an executed layout result.

## Frozen eight cases

All anchors are TopLeft, use scalar SnapToWindowWithMargin, and have no extra offset or client inset. Positions are Local except A's nested Window control. `scenarios.json` is the exact machine-readable input.

1. Exact/inside edges, margin8: A outer(200,140), inner(56,32); B outer(199.75,139.75), inner(55.75,31.75). Baseline outer(224,168), nested(280,208); strict tests apply no margin on exact or noncrossed edges.
2. Outer-only fit, margin8: A outer(200.25,140.25), inner(32,24) gives outer(216,160), nested(248,192). B outer(-24.25,-28.25), inner(32,24) gives outer(8,8), nested(40,40).
3. Inner-only fit, margin8: both outer(24,24) gives outer(48,52). A inner(232.25,148.25) gives nested(272,200); B inner(-48.25,-60.25) gives nested(8,8).
4. Both levels fit, margin8: A outer(200.25,140.25), inner(64.25,40.25) gives outer(216,160), nested(272,200). B outer(-24.25,-28.25), inner(-8.25,-16.25) gives outer/nested(8,8).
5. Logical threshold/device half, margin8: A outer(.25,-.25), inner(1.75,-1.75); B outer(.75,-.75), inner(1.25,-1.25). At1.25 A outer(24,28), B outer(24.8,27.2), both nested(25.6,34.4). At1 A outer(24,28), B outer(25,27), both nested(26,34). Composed offsets(2,-2) create exact device ±2.5 ties.
6. Signed logical halves/composed snap, margin8: A outer(.5,-.5), inner(1.5,-1.5); B outer(-.5,.5), inner(-1.5,1.5). At1.25 A outer(24.8,27.2), nested(27.2,32.8); B outer(23.2,28.8), nested(20.8,39.2). At1 the respective origins are(25,27)/(27,33) and(23,29)/(21,39). The witness distinguishes snap(1+2)=3.2 from snap1+snap2=2.4.
7. Fit-created halves, margin.5: A outer(200.25,140.25), inner(56.25,32.25), fitted targets(223.5,167.5)/(279.5,207.5), final outer(224,168), nested(280,208). B outer(-24.25,-28.25), inner(-.25,-8.25), final outer(0,0), nested(.8,0) at1.25 and(1,0) at1. There is no second fitting pass after rounding.
8. Window/Local, margin8: both outer(200.25,140.25) gives outer(216,160). A inner Window(80,96) stays(80,96); B inner Local(80,96) fits to(272,200).

Every case performs eight bracketed operations: open window (retain every bootstrap-scale2 frame); set scale1; set scale1.25; set child-lower priorities A2/0 B3/1; set all priorities1; restore baseline priorities A2/3 B1/3 and move ancestor(+16,+12); restore ancestor and change both nested references8→12; restore original state. Scale stays1.25 for the final five operations. Every actual frame is retained; no fixed redraw count is assumed, discarded or compared as parity. Priority-only operations must preserve geometry/offsets. Nonfitting Local cases include +4 reference-height witnesses; Window position remains window-relative.

Baseline global group paint is B,A,B.nested,A.nested; child-lower is A.nested,B.nested,A,B; all-equal is A,B,A.nested,B.nested. Per-round prepaint discovery and final global stable paint are distinct source hypotheses. Observed wrapper callbacks and the 13-box paintable projection remain distinct.

## Rational geometry and numerical contract

After independently validating static/reference layout, the checker uses exact rational arithmetic:

- outerDelta = logicalRound(fittedOuter − O0)
- innerStatic = N0 + deviceSnap(outerDelta)
- innerDelta = logicalRound(fittedInner − innerStatic)
- nestedFinal = N0 + deviceSnap(outerDelta + innerDelta)

It never substitutes innerStatic + deviceSnap(innerDelta). Fitting uses strict overflow comparisons; margins are not universal viewport padding. Local desired positions use the inherited inner static origin; Window desired positions do not. Logical nearest-integer halves round away from zero. Device nearest-integer halves round toward zero. There is no post-rounding refit. The model derives every transition from authored inputs; it never normalizes observations to baseline constants.

Pinned source locations: anchored.rs135–214 and261–288; deferred.rs43–66; window.rs3883–3996,4194–4223,5285–5302 and3184–3206; util.rs128–142; geometry.rs2689 and2815–2822; taffy.rs291–376. Exact retained upstream blobs, not a checkout's moving HEAD, bind source inspection.

The allowances are frozen before observations:

- Each observed x/y/width/height versus the independent rational expectation: absolute ≤2^-10 logical pixels, no relative tolerance.
- Separately, each near/far edge × observed scale: within2^-10 device pixels of an integer, using binary64 checker arithmetic.
- Integer logical offsets, full mask[0,0,320,240], scales, metadata, node/group IDs, order, operations and frame boundaries: exact. Signed zero is numerically equal.
- Paint versus its own prepaint bounds: exact.

Pixels is f32. Quarter/half inputs and scales1,1.25,2 are binary-exact, but division by1.25 creates fifths. At qualified observed coordinates≤320lp, maximum binary32 ULP2^-15 means this allowance is32ULPs; physical≤640dp gives16–32ULPs. This is a magnitude rationale, not a proof of the complete accumulated arithmetic error. The smallest intended incorrect-rounding witness .8lp/1dp is819.2/1024 times the respective allowances; an incorrect integer offset fails exactly. Unexpected actual observations require investigation, never retrospective tolerance widening. The old Rust nested verifier already declares2^-10 geometry/grid allowances; the prior native pair compares with zero allowance. Both remain untouched.

## Observation, provenance and operation

Rust is a transparent Element decorator. It delegates original state and return values unchanged and records real request-layout/prepaint/paint entry and return callbacks. Raw events retain authored group IDs/priorities, bounds and masks, prepaint-only logical offsets, operation inputs and every frame. `Window::element_offset` is prepaint-only and is not called from request-layout or paint. Rust contains no sorting, fitting model, rounding model or expected rectangles. Checker predictions are explicitly labelled separately. Test-only decimal construction and explicit fixed witnesses do not constitute observed output.

The dedicated workflow alone builds/runs Rust1.98.1 with the retained lock, two jobs, no incremental compilation and no display server. Source preflight requires complete Git history, exact ca784 base/tree, precisely eleven additions and no changed baseline mode/blob. CI requires ≥8GiB initial build headroom and continuously monitors1GiB+32MiB free on both workspace and /tmp. Original stdout/stderr, binary, lock, relocated build manifest, source trees/blobs, toolchain, execution plan/environment/session/timestamps and failures are retained. The artifact upload is unconditional. Do not rerun frozen historical diagnostics under this new additive HEAD.

Lightweight checks:

```
python3 -m unittest discover -s tests -p 'test_nested_deferred_fitting_diagnostic.py' -v
```

Dedicated approved CI only:

```
python3 diagnostics/nested_deferred_fitting/run.py --online --upstream-source _build/upstream-source --output _build/nested-deferred-fitting-evidence
python3 diagnostics/nested_deferred_fitting/verify.py _build/nested-deferred-fitting-evidence --suite-commit "$(git rev-parse HEAD)" --suite-tree "$(git rev-parse HEAD^{tree})" --suite-source . --upstream-source _build/upstream-source
```

Downloaded evidence uses its original `--recorded-execution-root`; source authentication requires all four source-binding arguments. Source-only local work has a cumulative16MiB shared allocation cap. No local Rust build/execution is permitted. A future original ZIP and one extraction require separate actual-size safety gates; planning sizes are not download authorization.

Controls cover disabled outer/inner fitting, premature exact-edge margin, per-level early snapping, wrong signed logical/device ties, lost/doubled inherited offset, Window-as-Local, stale reference height, wrong discovery/global order, and source/session/frame/mask/budget corruption. They test checker sensitivity only.

Complete passing bundle results, including every retained frame and projection, must equal their JSON save/load and recomputed results with strict equality. Intentionally failing synthetic bundles likewise save/load/recompute the complete runner-shaped failure record. These checks perform no tuple/list normalization or selected-field comparison; retained reports and projections are JSON-native from construction.

Excluded: input/outside-click/focus; third/arbitrary depth or ordinary deferred attachments; clipping/transforms/scroll/cache; text/raster/browser/native-window/full-popover; SwitchAnchor, non-TopLeft, extra offsets, per-edge margins; fractional viewport/sizes, oversized content and exhaustive rounding. Original external109/55 work remains untouched.
