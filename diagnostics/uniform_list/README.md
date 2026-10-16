# Supplemental real-GPUI uniform-list diagnostic

This is a separately authored, font-free diagnostic linked to unchanged GPUI
at **5a5fbe79917971a4d52a96b6ddb04da198a5012e** (tree
`990fb995914d51a546b20e5cf0382dafc105c299`). It is **not** the unchanged
`uniform_list.rs` example. It does not open an OS/native comparison app, shape
fonts, compare browser pixels, or claim gpui.mbt candidate equivalence.
`TestAppContext::single()` uses the GPUI test platform and `NoopTextSystem`.
The fixture contains no text.

## Why this evidence is separate

Original example screenshots cannot distinguish eager factory calls from lazy
construction, masked surplus rows from correct visible ranges, or callback item
identities. This diagnostic observes actual GPUI callbacks and lifecycle/input
APIs. It never emits a source-derived expected Rust trace. The Python verifier
checks raw observations against the bounded contract independently; it does not
consume a report pass flag. No candidate adapter is included until a genuine
production core API and actual upstream baseline are available.

The older root `pins.json` engine is deliberately not used. Its identical example
file does not imply an identical list engine: source5a uses f64 range/placement
arithmetic and includes a far-down long-list fix.

## Fixture and observations

The actual row is `.id(item).w_full().child(nested_div).on_click(...)`. The row
has **no authored height**; its nested child initially has height 26 and later
31. GPUI measures this auto-height row, chooses callback ranges, creates the
visible rows, positions them, maintains the full virtual extent, and dispatches
mouse clicks. A delegating `Element` wrapper logs real request-layout and
prepaint calls without adding a layout node, rewriting bounds, implementing a
hitbox, or changing element IDs.

The list is positioned at (40,50), size 220×300, inside a 420×420 test window.
Partially visible rows extend into the window outside the smaller list. The
recorded `window.content_mask()` and real edge clicks therefore distinguish
list masking from surface clipping.

`raw.schema.json` defines the raw document and its input corpus (`$defs.input`).
`scenarios.json` is the exact machine-readable input:

- Counts 0, 1, 50 and 1,000,000; viewports 13, 52, 300 and 350
- Offsets 0, 25, 26, 27, endpoint, excessive and negative requests
- Nested height 26→31, viewport growth, count shrink and empty-after-scroll
- Large offsets, bounded construction, window resize
- Pixel wheel Y, X-only fallback, nonzero Y with larger/opposite X, outside and exact-edge input
- Stable item callbacks after scroll and press→scroll→release while still visible
- Press→omit→restore→release, and count-remove→numeric-index-reuse→release
- No-down up, duplicate up, another-row release, outside release, clipped row portions and half-open right/bottom edges

Operation inputs retain raw GPUI pixel-wheel deltas. `set_offset.y` is a positive
logical top request, converted to GPUI's negative offset. Raw output retains
negative `scroll.offset` and positive `scroll.max_offset` without normalization.
`last_item_size.item` is the viewport size and `contents` the complete virtual
extent; it is **not** an exposed prototype row size. Actual row/inner prepaint
bounds establish the measured row height.

Every event has a sequence number, input-operation ID and actual frame number.
A frame begins in the root's real `request_layout` and ends after its paint.
`factory_call` joins the callback range, actual constructed IDs and prepaint
records. Nonempty frames normally contain two `[0,1)` prototype factory calls
and one visible-range call. Prototype rows have request-layout observations but
no prepaint or hit-active presence. Multiple frames per operation and operations
without a new frame are retained in full. The raw trace is never collapsed to
one assumed frame per input.

The omitted-row and removed-row pending-click results are intentionally read
as upstream observations. The verifier checks that any click belongs to the
actual current clipped row, but does not presume that stable numeric identity
survives absent frames. A future candidate comparator must match the actual
retained upstream outcome.

## Run and retain

The dedicated `uniform-list-diagnostic.yml` workflow runs the actual binary on
Linux. It does not change shared harness workflows, native fixtures, root pins,
browser catalog entries, or historical results. It requires a clean exact suite
and upstream tree, a fresh output directory, Rust 1.98.1, and at least 8 GiB free.
This disk floor intentionally prevents a full build in the constrained local
workspace. No cache, source checkout or evidence deletion is part of the runner.

```sh
python3 -m unittest discover -s tests -p 'test_uniform_list_diagnostic.py' -v
python3 diagnostics/uniform_list/run.py --online \
  --upstream-source /path/to/source5a \
  --output _build/uniform-list-evidence
python3 diagnostics/uniform_list/verify.py _build/uniform-list-evidence \
  --suite-commit "$(git rev-parse HEAD)" --suite-tree "$(git rev-parse HEAD^{tree})" \
  --suite-source . --upstream-source /path/to/source5a
```

`--online` permits locked dependency downloads. The default is offline. The
runner copies the exact adapter and relocates only its GPUI path dependency,
retaining both original and build manifests. It builds in the dev profile with
debug information disabled; debug assertions remain enabled because GPUI's
debug selector requires them. It records compiler/Cargo versions, command
arguments, process/run IDs and timestamps, exact suite/upstream commit+tree,
CI identity, executable and input hashes, stdout/stderr, lockfile, fixture,
verifier, and relevant unchanged upstream implementation source files. It checks
source cleanliness and identities again after execution. Failed build/output
logs are retained; a failure is never labeled an observed passing run.

The independent checker rereads `raw.json` and all manifest-bound files, rather
than trusting `verification.json`. An independent artifact review still needs
to bind the manifest's suite SHA/tree and CI run to the exact published head.
Hash self-consistency alone is not an authenticity proof. Standalone checks
without all four source-binding arguments explicitly return `source_bound:false`
and label their output as integrity/semantic inspection with source authenticity
unqualified. The runner and dedicated CI provide all four arguments.

## Local qualification status

A fresh offline lock resolution against source5a resolved 396 packages. Locked
offline metadata for `x86_64-unknown-linux-gnu` succeeds. Full all-target offline
metadata stopped on uncached `android_system_properties` 0.1.6. Neither metadata
check is a compile check or runtime result. No full Rust build or
actual GPUI execution has been performed locally. The dedicated CI execution
and independent raw-artifact review are separate pending gates.

Unit tests use explicitly synthetic minimal checker inputs to test rejection
of corrupted ranges, bounds, masks, IDs, counts, offsets, operation order and
provenance. These are **comparator sensitivity controls**, not executed engine
mutants and not retained oracle observations. Eager-list, range, clip, height,
axis-policy and callback-binding engine mutants require separate disposable
candidate builds after the real core API exists.
