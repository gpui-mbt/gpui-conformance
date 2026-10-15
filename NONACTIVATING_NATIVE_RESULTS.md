# Native background-host execution on macOS arm64

The first qualified nonactivating run used suite
`2bfaed9` and engine `b78c058fa124286cfb5d59c4bbbb1801fc7b0b19`, against upstream
GPUI `d9afb21688e04f89d9e94d96d33eb530aef90886`. It ran on macOS 26.5.2,
Apple Silicon, with actual AppKit windows and Metal readback at scale 2.

| Execution | Native lifecycle | Native pixels | Exact full-frame comparison |
| --- | --- | --- | --- |
| Shared red scene | pass | pass | 0 / 196608 pixels differ |
| Actual MoonBit blue paint control | pass | mismatch | 12288 / 196608 pixels differ |

The lifecycle observations cover creation, initial content dimensions, resize
and stale logical-handle rejection after destruction. The pixel observations
are drawn from retained 512 × 384 RGBA GPU frames. Pinned vlmkit
`b6ff83bb5f357e4ea3225af717479c6be74b2328` independently analyzes those retained
frames; its normal zero exit code for changed JSON never overrides the exact
pixel mismatch. Image analysis does not rerun native code.

Every created/rendered/resized/closed snapshot binds to its actual child PID
and one stable native window identifier. Both probes reported accessory policy,
hidden windows, no key window, no application activation and no frontmost
fixture. Their subprocesses exited normally. No unrelated app was activated,
captured or sent input.

Two earlier diagnostic attempts remain unverified. Inside the command sandbox,
upstream encountered macOS service connection failures and timed out; MoonBit
returned `device_lost` during `start_background`. With normal host access both
frameworks completed, but the comparator rejected MoonBit's initially
string-encoded identity fields. The subsequent numeric serialization fix was
committed before the qualified run. These attempts are not relabeled passes.

Local retained evidence directories are `_build/native-hidden-{first,host,positive,negative}`
and `_build/images-hidden-{positive,negative}`. Raw manifests, independent
execution challenges, process timestamps, builds, binaries, libraries, helper
and logs are hashed. A standalone table or this document does not establish
conformance without those artifacts.

These results qualify the candidate revisions above. Earlier build-only and
historical native records retain their recorded classifications. External AX,
visible desktop behavior and physical input remain unverified; see
[the observer prerequisites](NATIVE_OBSERVER_PREREQUISITES.md).
