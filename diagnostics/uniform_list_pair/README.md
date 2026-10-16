# Compiled uniform-list semantic pair

This is a bounded supplemental semantic comparison, not unchanged-example,
font, browser-pixel, native-window, OS-input or device-scale equivalence.
The independent Rust baseline is the approved run38968060005 artifact12075667392,
with exact hashes in `approved_baseline.json`. Its original source, manifest,
inputs, binary, logs, all85frames and callbacks are retained unchanged.

## Actual candidate

`adapters/uniform_list_moonbit` compiles to a native executable. It calls genuine
production `UniformList`, recursive `Element` request-layout/prepaint, factory
ranges/IDs, current-tree scroll routing, scene clip/quad lowering and
`UniformListClickSession`. JavaScript and Python do not implement candidate
list layout, range, clamp, input selection or click lifetime. Python builds,
retains and compares raw observations only.

The fixed source fixture's sole list is allocated at(40,50) with root padding,
not absolute positioning, because the supported core layout has no absolute
position API. The list dimensions and window are actual layout inputs. This
substitution is bounded to this single-child, fixed-size corpus. The root's
zero-offset ordinary scroll viewport supplies a real window clip. Rows are
zero-intrinsic auto-sized containers; the inner leaf's explicit source-authored
width220 and height26/31 are intrinsic inputs. Core recursive measurement owns
the resulting row height. Transparent row/inner backgrounds expose genuine
scene commands without claiming visual rendering equivalence.

Every candidate operation synchronously renders one fresh frame and reconciles
the click session immediately after that successful frame, before the next
input. Neither factories nor observers precompute a visible index or row rect.
Factory calls, constructed identities, all live nodes, every actual scene
command, routes, scroll updates, callbacks and snapshots are retained.

## Explicit normalization and comparison

- Original scenario bytes are identical. Original and applied operations are
  both retained. MoonBit converts input numbers through Float to mirror Rust's
  f32 parsing; 99,999,999 remains original and100,000,000 is actually applied.
- Raw GPUI wheel signs are inverted at the candidate input boundary. Candidate
  positive scroll top is compared to negative Rust handle Y. No delta policy
  is implemented in the adapter.
- Source IDs are indices. Candidate IDs use the actual range API with first1000,
  stride2, root slot0/inner slot1. The comparator checks that explicit stable
  encoding and joins actual constructed IDs to live nodes and callbacks.
- Every frame is parsed and retained. Operations may have zero, one or multiple
  Rust frames. Ordered normalized state sequences are compared per operation;
  only consecutive identical semantic states may be collapsed. A different
  intermediate state causes failure even if the terminal state agrees.
- The real9initial2x Rust bootstrap frames are preserved and validated, but
  excluded from operational equivalence. All93post-bootstrap operations are
  compared against actual1x Rust state;76actual1x Rust frames are retained.
  Candidate layout is logical pixels, has no platform scale, and makes no
  device-scale claim. Its102logical frames are never relabeled as Rust frames.
- Comparison is exact numeric equality, with tolerance0. All this corpus's
  resulting geometry is exactly representable. There is no inferred fractional
  or unexecuted-case coverage.
- Actual ordered factory ranges and constructed IDs are compared per frame,
  including two prototype calls and the live call; prototypes may not paint.
  Candidate metadata, live tree and scene geometry must agree. Effective masks
  are independently folded from actual core clip commands and compared to
  actual Rust row/inner prepaint masks. Empty lists have no measured prototype.
- Callbacks are compared by operation, stable index and original down/up points,
  and must join the preceding live factory call. Omission/removal cancellation
  therefore cannot be faked by a terminal-state-only comparison.
- Candidate row routes are additionally checked against the prior actual Rust
  row bounds intersected with its actual content mask. This is explicitly an
  observed-mask-derived route contract, not an assertion that Rust exposed a
  raw dispatch route. It detects missing ancestor hit clipping separately from
  callback equality.

## Run and verify

Set MOON_HOME and PATH to a usable pinned MoonBit toolchain, then run:

    python3 diagnostics/uniform_list_pair/run.py \
      --core-source /path/to/core --core-commit EXACT40CHARCOMMIT \
      --baseline /path/to/approved/uniform-list-evidence \
      --baseline-suite-source /path/to/suite-with-CI-Git-object \
      --upstream-source /path/to/source5a \
      --output _build/uniform-list-pair-UNIQUE

The default requires clean suite/core sources and an explicitly selected core
commit. The opt-in `--allow-unqualified-checkout` preserves exploratory runs
with clear unqualified provenance; it cannot claim reviewed/published source.
Build inputs are the complete four-package production source set, copied
byte-for-byte. A generated tiny module manifest only disables unrelated host
prebuilds; the original module manifest is retained. All original source
inputs, compiler commands, timestamps/PIDs, tool version/binary hashes,
compiled native/C artifacts, executable and raw output are retained. The
runner preserves failed build/run/comparison evidence too.

    python3 diagnostics/uniform_list_pair/verify.py _build/uniform-list-pair-UNIQUE \
      --suite-source . --suite-commit EXACTSUITECOMMIT \
      --core-source /path/to/core --core-commit EXACTCORECOMMIT \
      --upstream-source /path/to/source5a

The verifier rereads actual raw files, independently compares retained source
bytes to exact Git blobs, verifies complete source inventories and manifest
hashes, and never accepts stored comparison pass flags. Clean local source
binding does not itself mean the pin has been reviewed or published.

## Negative controls

`tests/test_uniform_list_pair.py` uses explicitly synthetic checker fixtures.
They are never engine evidence. Corruption controls edit copies of observed
raw output and must be labeled comparator sensitivity. Executed engine mutants
must instead modify isolated production-core copies, compile them and run the
unchanged candidate/input against the untouched Rust baseline. Keep mutation
diffs, source hashes, build/run commands and raw observations for each. A
compiler rejection is not an executed engine mutant, and a surviving mutant
is an explicit coverage gap rather than a passing negative control.

The executed mutation driver uses one reused isolated build tree. Each mutant
retains its complete input-hash inventory, exact changed source and unified
diff, compiler/run logs, native binary and raw stdout. `bounded_overconstruction`
requests two extra rows within the valid ID namespace so the comparator can
inspect a complete wrong trace. `eager_all_n_resource` separately exercises the
all-N mistake under a768MiB process bound; exhaustion/crash is only a resource
safety observation, never called a behavioral comparator rejection. Likewise
any visible-extent runtime failure is distinguished from wrong measured data.
`run_controls.py` retains ten altered trace copies solely as checker sensitivity.

## Public pin and fresh CI pair

The bounded `profile.json` selects public core
`b9916950350b7d433ecca0d6fa88e39c957b8b6b`, tree
`be95df375c707bd6cf961ef7959e93772b34a966`. Root/catalog/browser pins are unchanged.
Omitting `--core-commit` selects this public profile; explicitly supplied local
pins remain available for honestly labeled historical/provisional runs.

The updated diagnostic workflow freshly builds/runs BOTH actual Rust and the
compiled candidate, then independently rereads both raw outputs. Fresh mode
requires `--fresh-baseline-suite-commit EXACT_CURRENT_CI_COMMIT` on run and verify
(and mutant driver), plus the independently selected suite/upstream repositories.
It source-binds the fresh Rust bundle to that exact suite commit/tree and source5a
and additionally checks byte hashes of the already approved Rust fixture,
Cargo manifest/lock, original scenarios, raw schema, runner and verifier.
Fresh output records its own manifest/executable/raw hashes, not the old run or
artifact IDs. The default approved-artifact mode remains strict and cannot
accept a different raw run. The schema2 pair bundle retains the new profile,
workflow and all pair/control code as source-bound inputs; legacy schema1
bundles keep their original eight-input source set unchanged.

The compiler installer is retrieved from the official vendor and retained by
CI. Actual compiler versions, binaries' hashes, native stdlib/runtime/header
inputs and build plan are retained per run; no unchanged compiler version is
presumed. The non-input incremental `.moon_db` and `.moon-lock` build caches are explicitly omitted
from new manifests so ordinary artifact upload cannot silently drop a required
hidden file. Any other hidden retained input fails the runner. The workflow source itself is retained at a safe nonhidden path.

The candidate's synchronous implementation requires exactly one complete
frame per operation. The comparator enforces that known candidate contract;
Rust may have zero or multiple frames, and every Rust frame remains compared.
A full candidate-frame deletion control was added after independent review;
its absence does not change the complete102-frame earlier observed pair, but
old comparator sensitivity is not retroactively upgraded. Current checker
controls include11corruptions, including a fully removed final candidate frame.
