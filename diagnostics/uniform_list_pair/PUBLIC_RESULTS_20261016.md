# Public-core local semantic pair and prospective fresh CI

Date:2026-10-16. No fresh public suite CI result is claimed in this report.

## Exact executed public-core candidate

- Public core `b9916950350b7d433ecca0d6fa88e39c957b8b6b`, tree `be95df375c707bd6cf961ef7959e93772b34a966`.
- Local suite `0547212e6ccb4674daa8e81b340cee667678c1e7`, tree `d46aec15b40529bf01ac33f31d45a842e7898ecd`; both source checkouts clean before/after.
- Actual native candidate build and execution exited0. Exact93operational comparisons and8callbacks pass against the independently retained approved actual Rust run38968060005.102candidate frames and85Rust frames remain separate. Bootstrap2x is excluded as documented.
- Self-contained bundle: `_build/public-core-b9916950-pair-v5`.
- Independent exact-Git/raw verification: `_build/public-core-b9916950-pair-v5-independent-verification.json`, `candidate_source_bound:true`.
-281manifest-bound files include16suite inputs and complete compiled-core/toolchain inputs. There are zero hidden manifest paths. Only the named non-input incremental caches `.moon_db` and `.moon-lock` are omitted; unexpected hidden inputs now fail retention.
-11observed-raw corruption controls all reject: `_build/public-core-b9916950-checker-controls-v3`.
-28focused Python tests passed for the executed v5 source:11pair and17original diagnostic tests. Fresh-mode tests explicitly distinguish checker-only synthetic fixtures from observed engine data.

The later mutation-gate hardening adds a twelfth pair unit test. It requires all twelve named behavioral controls to produce complete-trace semantic rejections; only `visible_only_extent` and `eager_all_n_resource` may satisfy the gate through runtime rejection. Missing, duplicate, unknown, surviving, timed-out, or unexecuted controls fail. The unchanged retained local2159 results satisfy this stricter classification gate; no new engine execution or rebinding is claimed by that check.

## Review correction and preserved history

Independent review found that the previous checker could accept deletion of a complete candidate frame when its terminal state was unchanged. Actual prior bundles contain all102candidate frames, so their observations remain unchanged. New code explicitly requires the candidate's documented one-synchronous-frame-per-operation behavior. It still compares every actual Rust frame and supports zero/multiple Rust frames. A full-frame deletion control now fails and a parser-level2Rust/1candidate plus0Rust/1candidate test passes.

The preceding public-core v4 local run is retained unchanged but its manifest still includes the generated hidden `.moon-lock` cache, so it is not the portable-CI bundle. v5 names both cache omissions explicitly. Historical882/4197/2159 bundles and the incomplete882mutant inventory remain unmodified and separately labeled in RESULTS_20261016.md.

The independently reviewed2159local-source mutation evidence remains bound to that exact local pin:14executed mutations,12complete-trace comparator rejections and2SIGSEGV-only controls. They are not rebound to the public core despite identical production tree. NoOOM cause is asserted. The bound fractional range-unit evidence remains core-only, with baselinepass/mutantSIGABRT and warning29 suppression for intentionally unused original test imports. Its fixture and driver first became committed in `a2cc0ab`; no retroactive suitea37binding is claimed.

## Prospective fresh public CI

The bounded profile pins public coreb991 and source5a without changing root/catalog/browser pins. The diagnostic workflow now freshly builds and runs both Rust and MoonBit, checks the actual pair, executes14production mutations,11trace-corruption controls and the separate fractional unit mutation, and uploads retained evidence.

Fresh mode requires an explicitly supplied exact CI suite commit and its independently obtained Git tree/source5a. Fresh Rust source is Git-bound and seven critical fixture/build/input/schema/verifier files must remain byte-identical to the approved diagnostic. Fresh records use their own executable/raw/manifest hashes and never reuse the old artifact ID. Default approved-artifact mode stays strict. Final public suite/core qualification requires the future actual CI output plus independent review; this local report does not substitute for it.

## Fingerprints

- public-core pair manifest: `5aac42a62de1ee75abe72c64a43e70fb035217c801b4daee0ec4b452b208a21a`
- public-core native executable: `7d2105ea9c0a1c3ce4027d99c5a682644968e3faad7e585db08e8b816be23a85`
- public-core raw candidate: `002a0933c6141ef453a1f08b5a29c0dfb4eb9145f2b277477c3ffb29c00440f2`
- independent local verification: `0271a3638809e7a144e2402c1f3b37397a6d3a099f51cc2f95b79d68fedcaa99`
- eleven corruption controls: `01c31767ee48c27f636b702be3f31e4243213fd1504d91a7490ec9645f4d105e`
