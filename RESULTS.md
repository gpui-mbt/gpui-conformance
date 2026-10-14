# Local macOS results — 2026-10-14

Executed suite: `eb477d5` on macOS 26.5.2 / Darwin arm64. Rust 1.98.1;
MoonBit `0.1.20260920 (914d7da)`. All three executions used committed, clean
suite and implementation sources. Machine-readable details, per-case values,
process identities and artifact hashes are in
[results/macos-arm64-20261014.json](results/macos-arm64-20261014.json).

| Execution | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| Pinned gpui.mbt baseline `f9f59fe` | 6 | 2 | 1 | 2 |
| Executed one-pixel width negative control | 4 | 4 | 1 | 2 |
| Separate gpui.mbt fix `e271a28864adb467c4523444affc965bffd1986e` | 8 | 0 | 1 | 2 |

Upstream is unchanged at `d9afb21688e04f89d9e94d96d33eb530aef90886`.
Baseline pointer-boundary samples targeted children 2,2,3 instead of no child;
zero-extent samples targeted children 2,3,3 instead of no child. The fix changes
only element pointer coverage to half-open bounds and preserves the closed
geometric `Rect::contains` API. Both cases pass when the identical suite runs
against the separately committed fix.

The negative control was an actual MoonBit probe execution with
`GPUI_NEGATIVE_CONTROL=1`. It changes the measured child width by one logical
pixel after framework layout. Both previously passing layout scenarios become
mismatches at `observation.bounds[1][2]`. It proves comparator sensitivity;
it is explicitly marked in its manifest and is not conformance evidence for a
changed implementation.

Validation: 31 adversarial comparator checks using copies of the actual retained
baseline; 111 relevant MoonBit native tests; 111 JavaScript tests; JavaScript
typecheck; repository contract check; changelog structure/date/duplicate guards.
The new boundary regression was observed failing before the fix. Independent
suite and pointer-fix reviewers approved the changes and rechecked evidence.

Full local evidence directories are `_build/baseline-final`,
`_build/negative-final` and `_build/candidate-final`. Each retains the two probes,
successful build logs, raw stdout/stderr and its manifest. Run
`python3 comparator.py <directory>` to verify hashes and recompute the result.
The JSON report in this repository is an index/summary; it cannot establish a
pass without those full execution artifacts. Executables are kept out of Git.

At this initial checkpoint, native window lifecycle and GPU pixels remained
**unverified**. The later, coordinated [native qualification](NATIVE_RESULTS.md)
executes both AppKit/Metal backends and qualifies bounded window/content-size
and three GPU sample cases. Historical headless artifacts retain their original
unverified placeholders. Rust's headless lifecycle is still one-sided evidence
and does not replace the new native execution.

IME composition remains **unsupported**; physical input is outside this slice.
All work remains local. No security setting, Gatekeeper exception, credential,
existing-app/service termination, remote branch, PR or release was changed.
