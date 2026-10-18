# Local candidate validation, 2026-10-16

Qualification: source/compiled MoonBit and host unit tests only. No browser,
Rust execution, paired runtime, native, full-image or text/shadow parity claim.

Exact core build input: public `eb968228bbea56aff13721dc427875c2dacffc14`, tree
`ae9072d350ef6d1546e408226218ec08efc96552`. Initial package tests used local
`a2718fcbf92dbbfd53f756642cc95813a402c431`, with that identical tree. Both
source checkouts remained clean; all builds/tests used disposable archives.

- Package formatting,18 MoonBit JS unit tests and release build passed.
- `build_moonbit.py` tested and built all11 registered MoonBit packages from
  the exact public core. Its initial manifest truthfully records a dirty
  candidate suite during development; this is not committed provenance.
- All504 existing/new Node unit tests passed, including unchanged flat-focus,
  scroll, renderer and provenance contracts. PNG unit tests used the required
  Pillow12.0.0; they remain synthetic comparator-sensitivity tests.
- All18 web Python tests passed. Catalog/packaging/provenance selection passed
 52 tests, including the immutable historical Rust-only catalog fixture and
  current implemented-candidate duplicate-oracle rejection. Mocked packaging
  tests do not execute Rust despite their normal helper's status text.
- 84 actual compiled MoonBit frames validated against the renderer's scene
  schema across6 accepted scales and14 traversal steps. This checks valid
  output shape, not browser pixels or cross-scale parity.
- All12 deliberately wrong candidate mutations compiled and failed intended
  assertions. See [the result artifact](evidence/compiled-mutations.json) for
  exact source/test hashes, failing test names, counts and log hashes.
  Restoring exact source passed18/18. Mutations affected only a disposable
  package copy, never core or upstream source.

The decisive controls omit live-bounds refresh, omit group prefixes, replace
border-derived row bases, replace inner-card shrink with outer weighting,
make focus rings keyboard-only, insert a non-stop card into traversal, ignore
owner ABA, replace live lineage with a paint tree, suppress no keyboard hover,
and invent a card click callback. Local tests are not substitutes for the
independent actual-Rust/current-candidate browser profile.

The old isolated Rust-only workflow intentionally cannot package today's
implemented tab_stop as an extra oracle. Its historical fixtures remain
strict. A separate paired-profile workflow must replace that live workflow
when the parent integrates the independently corrected oracle/pair harness.
