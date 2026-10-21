# Current-source popover integrity policy v2

The original seven reviewed files, historical `evidence.py`, and historical
`run.py` remain byte-for-byte unchanged. Their v1 CLI remains historical-only.
A v1 bundle is not accepted by the v2 evidence verifier, or vice versa.

## Two distinct source assertions

1. Historical proof is fixed to commit
   `999e3d95ee2b67d387223ef3eaecd693f285924e`, tree
   `0e71d50fd4cfbff3f42cb4d66919822f9943a062`: exactly the original 723 baseline
   files, unchanged in blob and mode, plus the original eleven additions.
   `contracts_current_v2.py` authenticates a separate historical checkout before
   executing its unchanged tests, including the original 723-file assertion and
   the unchanged v1 validator. No check is skipped or given refreshed hashes.
2. Current source is bound to a caller-supplied exact commit and tree, a clean
   checkout, and the closed inventory in `source_policy_v2.json`. Unrelated
   repository evolution is allowed, but it is not relabeled as the historical
   723-file proof. Every scoped file's bytes and nonexecutable regular-file mode
   are checked against that commit. Missing, extra, ignored, or symlinked scoped
   files fail, including ignored test caches and special filesystem objects.
   Git replacement refs and relocated bytecode caches are rejected; v2 Git reads
   disable object replacement and inherited Git repository overrides. Original frozen hashes and historical verifier/runner hashes are
   enforced. Policy JSON must equal the versioned verifier's canonical policy;
   a bundle cannot select or relax the inventory.

The scope is `adapters/popover_outside_rust/`, `diagnostics/popover_outside/`,
`tests/test_popover_outside*`, and the diagnostic workflow. The separate MoonBit
pair diagnostic retains its existing source and runtime policy.

The trusted boundary is the independently selected, reviewed verifier commit
and tree. A self-authored bundle, self-reported commit, or changed policy cannot
choose its own authority. Changes to this version's policy/verifier need review;
new guarantees or scope require a separately reviewed policy version.

## CI and local source checks

CI uses an exact checkout of the historical commit and an independent current
checkout. With both available, run from the current suite root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 diagnostics/popover_outside/contracts_current_v2.py \
  --historical-source /path/to/verified/historical-checkout \
  --suite-commit "$EXPECTED_COMMIT" --suite-tree "$EXPECTED_TREE"
```

The historical suite executes all unchanged historical tests. The current suite
executes every original behavior test against current source; the historical
preservation assertion is executed only against its authenticated historical
root. Current evidence tests include the host-disk-independent synthetic process
capture controls. The new v2 tests exercise isolated tiny Git repositories and
synthetic bundles, never Rust or MoonBit. They do not establish runtime parity.
The historical process capture test still uses the actual disk floor, so its
full suite requires that floor even though it does not compile Rust.

Generic discovery of `test_popover_outside*.py` from evolving main is not this
entry point: its frozen test deliberately still requires the historical root.
Do not change that test or the frozen README to make current main resemble history.

## Current runtime evidence

Only `run_current_v2.py` produces v2 current runtime records, in the dedicated
Ubuntu CI job, using externally provided `--suite-commit` and `--suite-tree`.
`evidence_current_v2.py` independently reopens them against the same explicit
external source and CI identities. V2 includes the complete policy/source
inventory and an exact policy ID/hash, retains every original v1 evidence,
process, resource-floor, session, chronology, source-byte and raw-checker check,
and rejects historical/v2 cross-profile replay. The v1 implementation is not
monkey-patched, and the bundle never supplies executable verifier code.

Historical source tests and synthetic v2 tests are not execution attestations.
Both runtime verifiers continue to return `execution_authenticated: false`:
process records must be corroborated with original CI logs and artifact
provenance. No historical runtime result proves execution of current source.
