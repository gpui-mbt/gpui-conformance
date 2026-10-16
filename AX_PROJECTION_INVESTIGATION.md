# AXWindow association investigation, 2026-10-15

## Status and available evidence

The cause of the external application-element alias is **undetermined**.
AX association and semantic AX remain **unverified**. This follow-up runs on
Linux x86_64; it does not have a connected macOS execution environment.
No new live AX observation, native window run, GPU comparison, or lock-state
experiment is claimed here.

PR [#11](https://github.com/gpui-mbt/gpui-conformance/pull/11), merged after
[#10](https://github.com/gpui-mbt/gpui-conformance/pull/10), already investigated
local versus external AX identity and private accessory bundles. The existing
[diagnostic note](AX_DIAGNOSTIC_RESULTS.md) and
[execution index](results/native-ax-diagnostic-macos-arm64-20261015.json) report:

| Layer | Recorded fact | What it establishes |
| --- | --- | --- |
| WindowServer | Owned PID, process start, executable and window number bind successfully | A real owned window exists; this alone does not establish AX identity |
| Host AppKit objects | `NSApp.accessibilityWindows` contains the actual owned `GPUIWindow` / `NSWindow`, role `AXWindow`, nonce title | Local getters expose the intended object; external publication is not proven |
| External observer | `AXWindows` entries compare `CFEqual` to the application element; role `AXApplication`, application title; trust true and queried errors zero | The observer receives an application alias instead of a matching AXWindow |
| Bundle experiment | Measured runtime bundle identity succeeds after the separate Accessory startup fix; alias persists | Bundle identity alone did not resolve the AX failure |
| Session control | The existing note reports on-console and an explicit screen-locked marker | A possible environmental variable; no unlocked comparison establishes causation |

Raw executable, ready, observer and acknowledgment artifacts from those Mac
runs are not present in this checkout. Their recorded findings are attributed
to PR #11; the committed summary cannot independently replay or establish a
fresh pass. Earlier result files are preserved unchanged.

## Host and observer comparison

The inspected host sources are gpui.mbt
[`71da96d9`](https://github.com/gpui-mbt/gpui.mbt/blob/71da96d9f8eaed89f42937d4edcd3eb2122cfb54/platform/macos/native.m)
and pinned upstream GPUI
[`d9afb216`](https://github.com/zed-industries/zed/blob/d9afb21688e04f89d9e94d96d33eb530aef90886/crates/gpui_macos/src/window.rs).
MoonBit creates a normal `NSWindow` and finishes AppKit launch. Upstream builds
`GPUIWindow` as an `NSWindow` subclass. The inspected window/application sources
do not replace `AXWindows` with the application object. MoonBit's separate
`platform/macos/accessibility.m` projects a button below its view; it does not
replace the application's windows list.

The suite's common owned-fixture helper obtains local AppKit objects directly.
The external observer creates one application AX reference for the verified
target PID, obtains `kAXWindowsAttribute`, then examines each returned reference.
It does not recreate the application reference inside the candidate loop or
substitute it for the returned window. There is no source-level explanation
yet for why the AX projection aliases the application.

One independent scope bug was confirmed: the old observer read candidate
title/role before checking the result of `AXUIElementGetPid`. The corrected
helper requires successful ownership verification before title, role, or
attribute-name queries, in both acquisition paths. This closes foreign-element
reads; it is **not** presented as the cause or fix of the application alias.
Application-equal candidates are also explicitly rejected, even if their
reported title/role resemble a window. Retained pass validation rejects an
explicit application-alias marker.

## Added diagnostics and their interpretation

The existing explicit `--observe-visible --ax-diagnostics` mode now adds:

| New evidence | Purpose and limitation |
| --- | --- |
| `ready.json`: `local_ax.window_is_accessibility_element`, `window_parent_is_application`, `unignored_is_owned_window`, `unignored_is_application`, `unignored_role` | Distinguish a local AXWindow role from an unignored, externally publishable object; these getters still do not prove external publication |
| `observer.stdout`: `ax_indexed_windows` | Compare `AXUIElementCopyAttributeValue` with count plus `AXUIElementCopyAttributeValues` on the same verified application reference; retain errors, counts, ownership, alias and per-index equality |
| `observer.stdout`: `ax_session_before` / `ax_session_after` | Retain only current-session availability, on-console/login booleans and an optional screen-lock marker; no user names or session IDs |

`CGSSessionScreenIsLocked` is an undocumented advisory dictionary key, not a
supported unlock-state API. Absent or non-boolean values are JSON null, not
false. Even a reported false marker cannot prove that AX is usable. Session
fields never alter qualification. The indexed route is diagnostic only and
cannot supply a fallback pass. Empty, failed or oversized queries are retained
as such; unqueried errors are null. The 16-element cap, three-second observer
timeout, five-second fixture checkpoint and fifteen-second child deadline are
unchanged; additional diagnostic calls may time out and remain unverified.

No system-wide AX root, hit-test, desktop enumeration, capture, activation,
AX action, permission prompt, signing change or TCC modification is added.

## Remaining hypotheses and next observations

1. **Ignored/publication mapping:** if the local unignored ancestor is the
   application, investigate the host's accessibility-element/parent contract.
   If it is the owned window while both external retrieval paths alias the
   application, local role/title alone cannot explain the external mapping.
2. **Session or common AppKit bridge behavior:** compare fresh retained runs in
   a session the user has made normally available, using the same source and
   observer. This tool must not unlock, activate another app, or change access.
   A minimal, separately owned AppKit window control would further distinguish
   framework-specific behavior from a shared export/client/session issue.
3. **Retrieval-path or initialization behavior:** compare both APIs' references
   and errors during the same checkpoint. Agreement narrows the hypothesis;
   disagreement does not by itself identify the faulty side or qualify a pass.

Re-run only from committed sources on an authorized Apple Silicon Mac, retaining
the entire new output directory and the current WindowServer/AX association:

```sh
python3 run_native.py --upstream-source /path/to/pinned-zed \
  --moonbit-source /path/to/clean-engine --candidate-revision FULL_ENGINE_SHA \
  --observe-visible --ax-diagnostics --bundle-fixtures \
  --output _build/ax-projection-followup
python3 tests/test_bundle_evidence.py --evidence _build/ax-projection-followup
```

`FULL_ENGINE_SHA` must identify the clean engine checkout containing the
Accessory startup correction, such as the previously measured
`fb0d9c74bb6b5afe29b20e532baedee7327151e6`. Use a fresh output for each attempt.
Do not replace the existing `unverified` AX status with a local-getter result,
an indexed-query result alone, or CI mock results.

## Validation scope

The portable commands cover 53 tests (15 portable, 13 image, 8 fixture and 17
observer contract tests). They passed on this Linux checkout. The new macOS CI
job compiles the production observer/helper and runs the actual candidate and
indexed-query helpers with mocked reads. Its dictionaries replace AX references;
it creates no windows and queries no application. CI success qualifies those
guards and compilation only. A live external AXWindow association is unrun.

API contracts: Apple's documentation for
[`kAXWindowsAttribute`](https://developer.apple.com/documentation/applicationservices/kaxwindowsattribute),
[`AXUIElementGetPid`](https://developer.apple.com/documentation/applicationservices/1460337-axuielementgetpid),
[`AXUIElementCopyAttributeValues`](https://developer.apple.com/documentation/applicationservices/1462060-axuielementcopyattributevalues),
[`NSAccessibilityUnignoredAncestor`](https://developer.apple.com/documentation/appkit/nsaccessibility-swift.struct/unignoredancestor(of:)),
and [`CGSessionCopyCurrentDictionary`](https://developer.apple.com/documentation/coregraphics/cgsessioncopycurrentdictionary()).
