# Owned AX identity and accessory bundle diagnosis

Follow-up: [external AX comparison and stock AppKit regression control](AX_COMPARISON_INVESTIGATION.md).
The control separates hierarchy, packaging, event retrieval and publication
timing without activating the existing regular-policy Button fixture. Native
control execution remains unrun; external AX compatibility stays unverified.

The bounded diagnostic distinguishes the local AppKit accessibility object
from the external AX projection. On this Apple Silicon macOS 26.5.2 host,
each fixture's own `NSApp.accessibilityWindows` contains its actual window
(`GPUIWindow` upstream, `NSWindow` MoonBit), with role `AXWindow` and the nonce
title. The external `AXWindows` result is instead `CFEqual` to the application
element itself: role `AXApplication`, application title, and the application
attribute-name set. AX trust is true and the queried attributes return error 0.
Strict role/title/PID/bounds matching continues to reject it. No semantic AX
pass is claimed.

| Actual run | Suite | Engine | Native paired result |
| --- | --- | --- | --- |
| Flat diagnostic | `17958befac5e1d3380d4bcac838b7df58fadeb85` | `d6afa474a20679725607f68b390f8a5dd8cd5b42` | 2 pass; AX unverified |
| Private bundle diagnostic | `167a3f9e4e35e2751fd512738a9b5f656c14c912` | `d6afa474a20679725607f68b390f8a5dd8cd5b42` | 2 unverified; MoonBit startup rejected before window creation |
| Bundled correction | `167a3f9e4e35e2751fd512738a9b5f656c14c912` | `fb0d9c74bb6b5afe29b20e532baedee7327151e6` | 2 pass; AX unverified |
| Real blue rectangle control | `167a3f9e4e35e2751fd512738a9b5f656c14c912` | `fb0d9c74bb6b5afe29b20e532baedee7327151e6` | 1 lifecycle pass, 1 GPU mismatch; AX unverified |

Upstream remains read-only at
`d9afb21688e04f89d9e94d96d33eb530aef90886` (GPUI 0.2.2). The pinned MoonBit
baseline remains unchanged; the engine correction uses explicit candidate
mapping. The [machine-readable index](results/native-ax-diagnostic-macos-arm64-20261015.json)
retains full manifests and comparisons. An index without its raw artifacts
cannot establish a pass.

The `.app` experiment retains the exact executable and `Info.plist`, including
a nonce-distinct ID and `LSUIElement=true`. `NSBundle.mainBundle` must report
the expected ID and bundle path, and the owned `NSRunningApplication` the same
ID. Launch uses
the exact executable through owned `Popen`; it does not install/register the
bundle or invoke `open`, activate a window, alter signing/security, or prompt
for permission. Relocatable replay binds the absolute execution command to
the retained relative executable layout and retains strict observer argv.

The failed baseline exposed a separate engine gap. A windowless AppKit control
measured initial Accessory policy, a false return from setting the same policy,
and final Accessory policy. The previous guard rejected this valid starting
state. The separate engine correction skips the redundant setter when policy
is already Accessory, while still requiring setter success for a needed
transition and always checking final policy. Six inert tests cover accepted,
refused, ineffective and changing policy observations. They are safety branch
tests, not framework executions.

The corrected native pair completes lifecycle, both runtime bundle identities,
owned WindowServer binding, three actual invalid-identity controls per
implementation, and nonce/PID/window/frame acknowledgments. Full 512×384
RGBA8 readbacks at scale 2 match at all 196608 pixels. The real control changes
12288 pixels from red to blue, detected by exact comparison and pinned vlmkit
diagnostics. An intermediate image-analysis attempt while source was changing
correctly remains unverified; a separate clean-source analysis detects the
mismatch. GPU readback is not a desktop screenshot.

Fresh headless executions at suite `167a3f9e` and engine `fb0d9c74` preserve
101 passes, 1 unsupported IME case and 2 unverified native placeholders. Their
controls preserve 13 unchanged passes and detect all 88 intended mismatches.
The current comparator replays all twelve retained corpora unchanged.

The current-session read-only control reports on-console and an explicit
screen-locked marker. External input remains unrun. This measurement does not
establish why the external AX projection resolves to the application element;
bundle identity alone did not fix it. Local accessibility getters do not
substitute for an external semantic observer. No unrelated application/window
was selected or captured, and no input or permission request was sent.

Reproduce from committed source with an engine containing the correction:

```sh
python3 run_native.py --moonbit-source /path/to/engine \
  --candidate-revision FULL_SHA --observe-visible --ax-diagnostics \
  --bundle-fixtures --output _build/bundled-positive
# Repeat with a fresh output and --negative-control for real blue GPU paint.
python3 tests/test_bundle_evidence.py --evidence _build/bundled-positive
```

The 40 real bundle replay/tamper checks and 51 portable guards launch no GUI
fixtures. Missing plist/packaging, rehashed wrong policy/ID/type, unread or
foreign runtime identity, wrong executable paths and extra arguments fail
closed. Diagnostic fields do not relax the five-second checkpoint or
fifteen-second parent budget. Actual evidence is retained under
`_build/ax-{element-diagnostic,bundle-diagnostic,bundle-fixed-positive,bundle-fixed-negative}`,
`_build/ax-policy-control`, `_build/accessory-regression*` and the image-analysis
directories. Preserve failed and unverified attempts alongside successful runs.
