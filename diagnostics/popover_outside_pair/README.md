# Fresh actual popover outside pairing

This additive diagnostic preserves all 738 files at integration baseline
`044d1a1982f7cc407e483b90a5f36f5dd33ded29` (tree
`3c110221f33168a295b76360674ed6c24f0b836e`). The separate actual oracle remains
`d24cf54f770bd8146944a6e13b7aead7a6a7115a` with its original 734-file checkout.
It executes that unchanged Rust observer afresh against upstream `5a5fbe79917971a4d52a96b6ddb04da198a5012e` and
pairs it with compiled production MoonBit core
`e2f7a23d65702b9b21d7bf654d1168afb4841648`.

The new dedicated `run_rust.py` owns execution. It does not invoke the original
frozen runner with altered environment identities. Pair HEAD, the oracle source,
core source and upstream source are separate immutable identities in the bundle.
The original PR69 artifact is historical comparison evidence, never a runtime
dependency on an expiring Actions artifact.

## Scope

The fixture supplies 23 inputs to actual implementations. The candidate performs
real anchored/deferred request-layout and prepaint, builds the new production
PointerOutsideFrame snapshot, and routes normal inputs into production Button.
Outside dismissal is never implemented with application containment checks.
The adapter registers parent outside capture only when its child is closed.
Callback state changes affect the next frame, not the registry of the current
input. Rendering follows production Button pressed-state changes and callback
state changes, not operation labels or a forced frame count.

Only observed operation state, callbacks, registrations, geometry and whether a
frame was produced are projected from the genuine Rust trace. Rust prepaint,
paint and host-return chronology remains checked by the unchanged original
verifier; corresponding phases are not invented for MoonBit. General listener
interleaving and click parity are outside this narrow contract. The new core
entry point explicitly delivers outside capture before the legacy normal route.

Five rebuilt controls must compile and execute successfully, then differ
semantically: disabled outside delivery, primary-only delivery, release-only
delivery, incorrect simultaneous parent registry, and same-event redispatch
through a newly rendered registry. Compiler, process or malformed-output failures
never count as a successful semantic kill.

## Evidence and execution

The dedicated Linux CI job checks out exact source pins under ignored `_build`,
runs unchanged old tests in the oracle checkout, runs the new
`tests/test_outside_pointer_pair.py`, and produces fresh Rust and six MoonBit runs.
The distinct test filename avoids the frozen legacy popover workflow path filter.

`run.py --core-source PATH --oracle-source PATH --upstream-source PATH --output
_build/popover-outside-pair` runs only in the dedicated CI job. `evidence.py`
reopens the bundle against source checkouts and the expected Actions session.
Original CI logs and the original ZIP are required corroboration: internally
consistent hashes alone cannot authenticate execution.

Evidence retains the original/staged source, compiler plans, tool identities,
standard library inputs, executable outputs, process logs and all five controls.
MoonBit tool binaries and standard library inputs are copied once in the ordinary
candidate; controls use the literal bundle-root reference `candidate`. No
symlinks or arbitrary shared paths are allowed. Live tool/stdlib hashes are
rechecked after compilation. Rust tooling and standard libraries are hash-bound
without making another large distribution copy.

Successful bundles have a 512 MiB expanded-file ceiling. Retrieval must first
check artifact metadata, preserve the original ZIP durably within a 128 MiB cap,
then inspect central-directory sizes, paths and CRCs before bounded extraction.
No compression ratio is assumed. Processes enforce the 1 GiB + 32 MiB free-space
floor and preserve failed build/runtime records. Compilation is CI-only; local
source checks do not establish actual paired behavior.

These sources were reconstructed after a workspace reset. Fresh hashes and fresh
review apply; they are not claimed byte-identical to the lost unpublished draft.

## Explicit current-main integration

PR45 and then PR55 advanced main while this diagnostic was in review. The
original baseline check correctly rejected the third CI merge-ref because it contained three
changed browser IME files and two added browser regression files. The source
branch now integrates the later public main commit, including PR55, and pins it
as the 738-file preservation baseline. No browser changes are reverted or allowlisted
out of validation. PR45 added input-ime-browser.mjs and
input-ime-host.test.mjs; its changed files are web/README.md,
web/moonbit/site/input-host.mjs and web/tests/candidate-browser.mjs. None overlap
the actual Rust observer, fixtures or original evidence verifier.

The original oracle checkout and old tests remain pinned at d24. The integration
baseline is additionally recorded in the outer source attestation. GitHub's
actual merge-ref checkout and GITHUB_SHA are unchanged, so CI still exercises the
integrated tree. This is an explicit baseline-code correction plus main
integration, not a claim that all 734 historical suite files stayed identical
in the integrated current tree.

PR55 additionally changes the separate browser-examples workflow, web/README.md
and web/tests/contracts.test.mjs, and adds web/scripts/browser_build_artifacts.py
and web/tests/test_browser_build_artifacts.py. Those five paths remain byte-for-
byte equal to the explicit 044d integration baseline. The popover workflow does
not call that browser workflow or its packaging helper; its own checkout,
process execution and source/session binding remain unchanged.
