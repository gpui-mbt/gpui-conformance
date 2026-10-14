# Native verification at the merged revisions

Both native probes were freshly built and executed on 2026-10-14 UTC against:

- Suite: `316a62d3b33fa8038c900b4f2e1058b1c96f395e` (merged PR #1).
- gpui.mbt: `24bf42ca3bfb5dd3d2fe2b03271605dee99e13ba` (merged PR #72), version 0.7.2.
- Pinned Zed/GPUI: `d9afb21688e04f89d9e94d96d33eb530aef90886`, GPUI 0.2.2.

The execution checkouts were clean. The suite baseline pin remains unchanged;
the manifest maps this explicit candidate to baseline `f9f59fe0`. These are new
executions, not historical native results or build-only qualification.

| Retained execution | Pass | Mismatch | Unverified |
| --- | ---: | ---: | ---: |
| `native-merged-positive` | 2 | 0 | 0 |
| `native-merged-negative` | 1 | 1 | 0 |

The native window case reports content size 256×192, then 320×224 after resize,
and handle liveness changes from true to false after removal in both backends.
The GPU case retains the complete 512×384 RGBA8 frame at scale 2 and compares
the three requested logical sample points: black, opaque red, black. The
positive case has identical sample values from both independently executed
implementations.

The negative control actually paints the MoonBit rectangle blue. Window
lifecycle still passes, while GPU comparison reports differences at
`observation.samples[1][0]` (255 versus 0) and `[1][2]` (0 versus 255). It exits
with status 1 as expected. This is an executed comparator control, not an
implementation regression. No genuine regression was found in this slice.

| Execution | Implementation | PID | Started / finished UTC |
| --- | --- | ---: | --- |
| Positive | Upstream | 86326 | 21:39:41.614696 / 21:39:42.894529 |
| Positive | MoonBit | 86333 | 21:39:43.216654 / 21:39:44.131588 |
| Negative | Upstream | 86478 | 21:40:04.734692 / 21:40:05.569455 |
| Negative | MoonBit | 86481 | 21:40:05.863660 / 21:40:06.735650 |

All four child executions returned 0 without timeouts. Both probes and the
MoonBit native runtime/foreground guard were successfully built before launch.
Only isolated owned fixtures ran, self-closing with conditional focus
restoration; no existing application or service was terminated. The installed
October MoonBit SDK/core, Rust 1.98.1 and Xcode command-line tools were used;
no installation or security-setting change was performed.

## Reproduce and audit

Check out the exact source revisions above and use a compatible installed
MoonBit SDK/core. Keep upstream read-only and set an isolated `CARGO_HOME`.
In a coordinated graphical session:

```sh
python3 run_native.py --upstream-source /path/to/zed \
  --moonbit-source /path/to/gpui.mbt \
  --candidate-revision 24bf42ca3bfb5dd3d2fe2b03271605dee99e13ba \
  --output _build/native-merged-positive
python3 run_native.py --upstream-source /path/to/zed \
  --moonbit-source /path/to/gpui.mbt \
  --candidate-revision 24bf42ca3bfb5dd3d2fe2b03271605dee99e13ba \
  --negative-control --output _build/native-merged-negative
python3 tests/test_native_evidence.py --evidence _build/native-merged-positive
```

The real-evidence adversarial checks pass all 19 tests, including missing or
tampered readbacks, runtime/guard artifacts, process identities and owned-child
timeout cleanup. Direct recomputation matches both stored comparisons.
[The machine-readable index](results/native-merged-macos-arm64-20261014.json)
records the platform, pins, source trees, toolchains, process commands and
timestamps, observation values and artifact hashes.

Preserve the complete result directories to audit execution. The committed
index alone cannot establish passes. This closes the two native cases for the
exact merged candidate on this Apple Silicon macOS 26.5.2 host. It does not
qualify IME, physical input, close-request events, desktop placement, text
rendering, antialiased edges, other machines or general GPUI compatibility.
The earlier historical and build-only results retain their original scopes.
