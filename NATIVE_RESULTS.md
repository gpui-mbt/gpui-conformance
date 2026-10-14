# Native macOS qualification — 2026-10-14

Executed suite `e3d02517376da2373cbd00b8848cc5210d3814a2` on macOS 26.5.2 /
arm64. All sources and the suite were committed and clean. Upstream remains
`d9afb21688e04f89d9e94d96d33eb530aef90886` (GPUI 0.2.2); baseline gpui.mbt is
`f9f59fe074da3858ca82fe1d5fadd84cd17f0438` (0.7.2), and the separately committed
candidate is `e271a28864adb467c4523444affc965bffd1986e` (0.7.2).

| Native execution | Pass | Mismatch | Unverified |
| --- | ---: | ---: | ---: |
| Baseline | 2 | 0 | 0 |
| Fixed candidate | 2 | 0 | 0 |
| Candidate with actual blue-rectangle GPU control | 1 | 1 | 0 |

The native corpus in `native_scenarios.json` has two bounded cases. Both
frameworks create an actual owned AppKit window with 256×192 logical content,
resize it to 320×224 and remove it. The observed live handle becomes unavailable
after removal. Origin is normalized to content coordinates; desktop position,
close-request events and user input are not measured.

Both real Metal readbacks are 512×384 pixels at backing scale 2. The requested
logical samples (8,8), (40,40), (120,100) read opaque black, red and black. The
comparator checks those samples against each complete retained RGBA8 buffer.
The upstream path is the real `gpui_platform` MacPlatform and native Metal
`Window::render_to_image` from the completed scene; it does not present its
hidden window. MoonBit presents its own drawable and copies its completed
window-bound GPU frame. Pixel samples, rather than all pixels or edge quality,
form the conformance contract.

The GPU negative control really renders MoonBit's rectangle blue. It produces
differences at `observation.samples[1][0]` (255 vs 0) and `[1][2]` (0 vs 255),
while window lifecycle remains passing. This is executed divergence, not a
fabricated expected trace. It is marked as a negative control in its manifest.

Fourteen native evidence checks pass, including missing/short readbacks,
sample/readback disagreement, missing/tampered runtime library, absent native
mode, unexpected case IDs, mismatched/reversed input cases, and owned-child
timeout cleanup even when its restoration callback fails. The existing 31
headless comparator checks remain passing. Independent review approved the
code and rechecked clean execution evidence without launching another GUI.

Machine-readable manifests, comparisons, commands/PIDs, version/source identities
and hashes are indexed in
[results/native-macos-arm64-20261014.json](results/native-macos-arm64-20261014.json).
Full local artifacts are `_build/native-baseline-final`,
`_build/native-candidate-final` and `_build/native-negative-final`. Missing full
artifacts cannot establish a pass. No publication, Gatekeeper exception,
security setting, credential access or existing-app/service termination occurred.

Together with the eight executed [headless cases](RESULTS.md), the original
baseline has 8 measured passes and 2 pointer mismatches, while the fixed
candidate has 10 measured passes and no mismatches. IME composition remains
unsupported. Historical headless output retains its native placeholders as
unverified; this separate native corpus adds real qualification without
overwriting or reclassifying old evidence.
