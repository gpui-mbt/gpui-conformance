# Bounded grid/container-query semantic pair

This is a supplemental, font-free diagnostic. It does not run or establish
conformance for the unchanged upstream `grid_layout.rs` example. The candidate
executes production `request_layout_with_device_scale`, `prepaint`, published
`ElementTree`, scene painting, and pointer `dispatch_input`. The adapter contains
no track solver, injected rectangles, or coordinates copied from Rust evidence.

## Scope and observation policy

The corpus contains the original twelve diagnostic cases and one explicit
negative-origin query-root regression. Twelve cases are compared; the explicit
line-placement collision remains named `unsupported` because that placement is
outside the candidate core slice. A pass never counts it as supported.

Both the actual Rust bootstrap frame at scale 2 and the configured 1, 1.25, or 2
operation are observed. Every raw frame remains in each artifact and is checked
for lifecycle, callback, topology, numeric and scene consistency. The comparison
uses the final published frame of each semantic operation; when an operation
has no redraw, it inherits the previously published frame. Different scheduler
redraw counts are not themselves equivalence failures. Earlier invalid frames
are never discarded. No coordinates are re-rounded by the comparator. The explicit numeric domain is
|coordinates, far edges, sizes| <= 1024 logical pixels; out-of-domain traces fail.
The absolute allowance is 2^-12 = 0.000244140625 logical pixels, two Float32 ULPs
at 1024. This covers up to three half-ULP roundings from snapped-edge division and
subtraction when comparing Rust f32 observations to MoonBit Double. It cannot
hide even one device-pixel discrepancy at scales 1, 1.25, or 2. A
just-beyond-tolerance geometry corruption is rejected. This numeric allowance
does not normalize coordinates and is separate from final-operation frame
selection. The original eleven supported cases measured maximum coordinate
difference 0.000006103515630684342 (Rust grid width 201.60000610351562 versus
candidate 201.6 at 1.25×), callback difference zero, and maximum absolute edge
920. The earlier 0.01 local comparison was retained before tightening this
source-justified policy; no actual mismatch was discarded or tuned away.

Rust instrumentation observes delegated per-node lifecycle calls and click
callbacks. Candidate instrumentation observes actual whole-request boundaries,
callback invocations, published nodes, scene quads, and down/up dispatch routes.
These different interfaces are kept distinct in raw evidence. Comparison maps
the candidate's actual leaf route target to the Rust leaf callback, without
claiming a native click recognizer, accessibility instrumentation, or identical
per-node lifecycle APIs. Callback logs prove invocation timing, not when a
language allocated an object.

Generated query roots use the production `with_query_root_size` API for the
8×7 and 900×700 cases. Their outer query allocation is independently compared.
The extra regression uses a real row-flex host with cross-axis end alignment:
a 10×12 query in a 100×10 viewport gets y=-2, then returns a filling 1×8 grid.
The leaf height witness is 1.5 at scale 2 and 1 at scale 1, testing independent
local rounding before applying the negative origin. Neither implementation
uses negative padding or an injected expected rectangle to produce the offset.

## Provenance and failure retention

`profile.json` pins the exact public core commit/tree and frozen baseline source
hashes. `run.py` requires clean exact checkouts and a source-bound fresh actual
Rust baseline from the same suite checkout. It retains projected production
packages, the unchanged adapter, build commands/logs, executable, input token,
raw trace, copied original Rust bundle, source identities and hashed inventory.
`verify.py` rereads those bytes against independently selected Git objects and
recomputes the comparison. The original execution root of a copied Rust bundle
is recorded and checked, including exact executable/input/token argv and the
relocated Cargo manifest path. Path consistency and hashes are provenance
checks, not cryptographic execution attestation.

Semantic mismatches produce `comparison.json` with both values and fail the run.
Invalid traces, compile errors and runtime errors retain logs and raw outputs;
they cannot be reported as successful equivalence. The CI job uploads evidence
with `if: always()` and independently verifies a produced pair even after its
comparison fails. Heavy actual Rust/native pair builds belong in CI; no caches
or evidence are deleted to make room locally.

The original successful twelve-case artifact remains separate and immutable:
run 38982997354, artifact 12082311036, ZIP SHA-256
`b6c32507f2474db19116ecb238856772201f7f3f7a52d68c25a3f9e955650130`.
That result is not evidence that the extended thirteenth case or candidate pair
has passed. Those need their own actual CI observations.

## Controls

`run_mutants.py` copies the qualified production source and applies one exact
engine mutation at a time: dense placement, lost span, wrong gap allocation,
viewport-sized callback, lost generated origin, ignored generated-root size, and
absolute rather than independent-local query-root rounding.
Every mutation retains changed source/diff, source hashes, compiler output,
executable and execution output. Only a successfully compiled, successfully
executed mutant that is rejected semantically counts as an engine control kill.
Compile rejection, crash, timeout, and a surviving mutation fail the control
suite. An already-failing baseline cannot be used to claim a mutant kill.

`run_controls.py` separately corrupts retained JSON. Its results are explicitly
checker sensitivity, never executed engine mutants. Python unit fixtures are
also synthetic checker inputs and cannot establish engine behavior.

```sh
python3 -m unittest discover -s tests -p 'test_grid_layout*.py' -v
python3 diagnostics/grid_layout/run.py --online \
  --upstream-source _build/upstream-source --output _build/grid-pair-rust-evidence
python3 diagnostics/grid_layout_pair/run.py \
  --core-source _build/candidate-core --core-commit EXACT_PROFILE_COMMIT \
  --baseline _build/grid-pair-rust-evidence --baseline-suite-source . \
  --baseline-suite-commit "$(git rev-parse HEAD)" \
  --upstream-source _build/upstream-source --output _build/grid-pair-evidence
```
