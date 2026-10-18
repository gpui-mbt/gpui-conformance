# Padded text-first anchored attachment: prospective Rust observer

Status: source-only, uncompiled and unexecuted. No observed Rust numeric golden,
core change, candidate adapter, screenshot comparison, or parity result exists.
Python tests inspect source and deliberately synthetic traces only.

## Baseline and additive boundary

Suite baseline: `908f39d73b70b0c9d1bf59d8d3fc76e1e3506cf8`, tree
`de80e7d598470a75cc052c951848391551dba813`. Exactly seven additions:

- `adapters/padded_text_anchor_rust/Cargo.toml`
- `adapters/padded_text_anchor_rust/Cargo.lock`
- `adapters/padded_text_anchor_rust/src/main.rs`
- `diagnostics/padded_text_anchor/README.md`
- `diagnostics/padded_text_anchor/scenarios.json`
- `diagnostics/padded_text_anchor/verify.py`
- `tests/test_padded_text_anchor.py`

All historical paths are unchanged. This source overlay is separate from the
baseline checkout. The dependency manifest and lock are copied from this exact
baseline's `adapters/popover_outside_rust/`, changing only the root package name.
No dependency resolution or compiler execution was performed. The GPUI path
expects `zed-source` beside the suite checkout.

Upstream: `5a5fbe79917971a4d52a96b6ddb04da198a5012e`, tree
`990fb995914d51a546b20e5cf0382dafc105c299`. Selected source blobs:

- `crates/gpui/examples/popover.rs`: `7678a6a3ed865d9874b72cb99b473a115591d35c`
- `crates/gpui/src/elements/anchored.rs`: `29260061bb72ef9ca4dc66ac12919c9407d246cb`
- `crates/gpui/src/elements/div.rs`: `5d3b03b057bcac09f987a4587598a08a06872361`
- `crates/gpui/src/elements/text.rs`: `d1896ad0a65cc659f39d18cd601e2f9f2342ee64`
- `crates/gpui/src/window.rs`: `33fa14bfea6ebad50743d6d4014955d1055ef772`
- `crates/gpui/src/platform.rs`: `193f94c601cb8c3355f1f928e8930b0c6cc199da`
- `crates/gpui/src/platform/test/platform.rs`: `3c65219d36b80916a5a9f109974953cea6e32e20`
- `crates/gpui/src/app/test_context.rs`: `b8a120f942cbf166b0d73f1b5d77aa3a6ea0d1ac`
- `crates/gpui/src/style.rs`: `9150fdded91b817305454f18beb0a0b7d6c5966a`
- `crates/gpui/src/taffy.rs`: `b9e583a8df43a95a8dd87ae73822ad52efb0d5ee`

## Faithful branch, explicit reduction

The `example_branch` variant preserves the example's ordinary Block trigger,
`px_3/py_1`, literal `Open Popover` first child, and its absolute anchored sibling
with no supplied position. It preserves the first-level paragraph in full,
including the newline before `Click outside to close.`, popover flex-column,
centering, shadow, padding3, radius, colors, border1, text-sm, width96 and gap3.
The secondary trigger retains margin-top2, padding, literal `Child Popover`, and
the nested anchored sibling. The child retains its complete original paragraph,
blue border and unconstrained content-derived width. Both anchors are TopLeft,
snap margin8, with deferred priorities1/2.

The host is reduced to one centered primary branch. The always-open sibling,
other explanatory text and colored lines are omitted; their absence changes the
host's overall layout. Primary is already open, nested state is set by the test
driver so geometry can be isolated, and primary click/dismiss handlers are inert.
Secondary callbacks retain open/close behavior but this fixture sends no pointer
input. This is NOT an unchanged full example or an input-dismissal test. Existing
outside-pointer diagnostics remain separate, unchanged evidence.

The `asymmetric_fractional` diagnostic variant ONLY overrides both button owners'
padding to left11.25/right17.5/top3.75/bottom6.5 logical px and adds borders
left1.25/right2.5/top0.75/bottom1.5. It is separately labelled and never described
as an original example style. Its purpose is to distinguish potential content,
padding and border reference origins after authentic measurement.

Source: [button/popover styles and nested branch](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/popover.rs#L18-L80),
[primary branch](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/popover.rs#L116-L154).

## Authentic test-font input, no visual-font claim

Text remains actual GPUI text elements; no text is replaced with fixed-size boxes,
computed text dimensions, or precomputed observed rectangles. The upstream
TestAppContext default really uses NoopTextSystem:
[platform selection](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/src/platform/test/platform.rs#L129-L134).
Its [metrics and shaping](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/src/platform.rs#L1536-L1662)
are deliberately synthetic upstream test behavior (including fixed em advances
and no glyph raster output), not system font shaping, browser font loading or
native rendered text. Calling add_fonts would not turn this backend into a real
font engine. No font bytes or installs are needed or claimed.

The observer records inherited effective font family, font size, rem size, line
height, units/em, ascent, descent and em advance from the actual TextSystem while
requesting each text element's layout. This makes font-dependent layout inputs
explicit. Family names alone do not identify an actual font file here. Test-font
layout compatibility is distinct from visual or full-font parity.

## What is observed and what is merely a hypothesis

Element decorators delegate request-layout, prepaint and paint with unchanged
arguments, states and returns. They do not create extra layout nodes or hitboxes.
The specialized Div decorator reads its returned `Option<Hitbox>` and records the
actual hit rectangle and content mask; absent hitboxes remain absent. It does
not construct a hit rectangle from a separately predicted formula. This is not
a proof of hit testing or occlusion at any point.

Observed nodes: host; primary owner/text/static anchor; parent popup/text;
secondary owner/text; and when open, secondary static anchor/child popup/text.
Every frame start records actual scale/viewport. Every observed prepaint/paint
bound is retained with frame, operation and sequence. Static anchor bounds are
recorded on entry to Anchored.prepaint, before its fitting translation; the popup
child receives the resulting actual translated bound. Host paint return means
the ordinary host's paint returned, not that all deferred painting finished.

Sources: [absolute anchored layout](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/src/elements/anchored.rs#L100-L119),
[fitting and logical-pixel rounding](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/src/elements/anchored.rs#L142-L214),
[default static-origin reference](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/src/elements/anchored.rs#L261-L287),
[Div prepaint state](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/src/elements/div.rs#L1893-L1895),
[public hitbox fields](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/src/window.rs#L840-L850).

Upstream passes margin and padding into Taffy and uses a distinct device-stroke
snapping path for borders; scale changes must not be assumed geometry-invariant.
See [style conversion and border snapping](https://github.com/zed-industries/zed/blob/5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/src/taffy.rs#L416-L495).

The source hypothesis is that padding, border, text line layout and secondary
margin contribute through the actual static layout, rather than a guessed
fixed-first-child bottom edge. The checker reports raw owner/static/popup
reference deltas but does not assert a guessed attachment formula or bake in
unobserved numeric goldens. Both `observed_numeric_goldens` and
`attachment_reference_hypothesis_confirmed` remain null. Even a successful shape
check leaves `execution_authenticated`, `font_parity` and
`unchanged_example_parity` false. A synthetic trace can pass; source/session
provenance is mandatory before referring to any result as observed upstream.

## Frozen geometry sequence

Both variants run the same14 steps: parent-only then nested-open at each of
900x700 scale1, resize520x360 scale1, narrow320x240 scale1, restored900x700 scale1,
fractional519.5x359.25 scale1.25, same viewport scale1.5, then scale2. The driver
uses real `simulate_resize` and `simulate_scale_factor_change`, updates nested
state and requests redraw, then drains the upstream executor. Bootstrap frames
are retained and labelled separately. Input changes can generate intermediate
frames, all retained; the checker assesses the final settled frame per operation
without imposing a fabricated frame count. This is a geometry-state fixture,
not a click/open interaction oracle.

## Lightweight checks and future execution gate

From the additive source root:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_padded_text_anchor.py -v
```

Tests are source inspection, fixture validation, lock/manifest parsing and
synthetic checker sensitivity. They are not compilation or type checking.
No Rust formatter/compiler is assumed installed. No build, install, push, CI,
core mutation or dependency resolution is authorized by this addition.

Budget: all seven new source files together <=2MiB; selected read-only projection
<=32MiB. Before any further write preserve >=1GiB+32MiB free disk; never delete
historical evidence to satisfy this. Independent source review precedes any
runner proposal. A later separately approved runner must freeze suite and
upstream identities, all seven file hashes, toolchain, exact command/environment,
process timestamps/session/run token, binary hash, stdout/stderr and failures;
verify baseline preservation and original Actions evidence; run the compiled
Rust observer; then independently reopen the evidence. Do not infer provenance
from self-reported JSON pins or passing synthetic tests. Numeric differences
must be investigated before freezing goldens or proposing any core change.

## Source-review correction

Independent initial review found that Python ordinary equality accepted five
boolean/numeric metadata substitutions despite a JSON round trip. The corrected
checker compares typed JSON recursively: booleans are never numbers; finite
int/float equivalents are allowed for geometry; schema versions remain strictly
integers. Separate raw/input/operation/frame controls reject the aliases before
and after serialization. Initial review and its failing proof remain retained
separately. This is a checker correction, not an actual Rust runtime finding.
