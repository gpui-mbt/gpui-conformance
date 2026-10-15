# External AXWindow investigation, 2026-10-15

## Status and evidence boundary

External AX compatibility remains **unverified**. This investigation ran on
Linux, without a Mac connection. No GUI, AX IPC, activation, permission change,
unlock or historical raw-artifact replay was performed. Existing success and
failure observations below are repository records, not fresh executions. The
historical `_build/` receipts are absent from this checkout. Native GPU and
headless results do not substitute for external AX observations.

Sources inspected: gpui-conformance main
`cdd3cdadf605346ed2b90a59d461697582b8751c`, gpui.mbt main
`71da96d9f8eaed89f42937d4edcd3eb2122cfb54`, and the historical commits below.
Open PRs were checked before implementation: conformance #14 and gpui.mbt #82
are ecosystem documents; #40/#45 are separate IME work. This change adds an
isolated control and does not edit either engine or the existing GPU runner.

## Revision comparison

| Recorded source/attempt | Observation | What it establishes |
| --- | --- | --- |
| Button `4ab16de6dae5ad73712e3e69b639994e2135dc05` | ActRun and adapter tests passed; external final-source AX was still blocked/unrun | Local projection tests alone did not qualify external AX |
| Button post-unlock-fix-v2/v3, documented by `21a50cedffc73df0bcc20f3b49b769cbcedc6874` | Exact app identity appeared after 627.9/522.7 ms; independent client found Button and performed two AXPress operations | Historical bounded success; the records here do not bind the retained runtime binary to a new final SHA |
| Button `99f4b91da65b9c0269f26815f20542c77250115d` | Exact app identity after 620.1 ms, then AXWindows unavailable; baseline `45e651a` reportedly reproduced it | Registration readiness was insufficient to establish AXWindow readiness |
| Button baseline `50dfcc53adba5e034e44d8300b84577ca7300c2e` | Exact app identity after eight observations; AXWindows unavailable | Failure predates the next semantic freshness correction |
| Button `cda2d8ee32f07fd75e20b7ac28c0dfb0fd73ed2d` / integrated `4120ace270ede77759e264f8015ba61eb9f48c9c` | Freshness/session tests passed; external AX unrun | No later external success is established |
| Conformance suite `167a3f9e4e35e2751fd512738a9b5f656c14c912`, engine `fb0d9c74bb6b5afe29b20e532baedee7327151e6` | Own NSApp returns the actual AXWindow; external AXWindows returns an AXApplication equal to the app element; bundle identities match | Bundle identity alone did not fix the projection; this is not the same observation as a missing AXWindows attribute |

`git diff 21a50ce 99f4b91 -- tests/native/macos_button_ax_client.m
script/build_macos_button.sh` is empty. The Button client, discovery deadlines,
bundle structure and launch method are unchanged across those commits. The
production host adds scroll routing and test clipboard isolation. The AX
adapter adds focused-element notification routing, without replacing
NSApplication.accessibilityWindows or NSWindow registration. These changes
remain candidates for a later controlled bisect; static inspection does not
prove them causal or harmless. The actual successful binary/source receipt is
needed before calling this an exact successful-SHA bisect.

## AppKit and client comparison

| Dimension | Conformance | Button | Implication |
| --- | --- | --- | --- |
| App hierarchy | Native NSApplication, upstream GPUIWindow or MoonBit NSWindow; local AXWindow confirmed | Same MoonBit NSWindow; GPView child is a revocable NSAccessibilityElement with AXButton role, title, parent and window | Failure is already above Button child semantics |
| Registration | Both NSApp.windows and NSApp.accessibilityWindows identify the owned window | Adapter finds its window through NSApp.windows and GPWindow token | Replacing the app/window AX hierarchy lacks evidence |
| Activation policy | Accessory, non-key, inactive; orderBack | Regular; existing host uses makeKeyAndOrderFront and activateIgnoringOtherApps | Running the current Button --all harness would activate its app; it was not run here |
| Bundle | Flat and private LSUIElement=true APPL bundles; unique ID and measured runtime identity | APPL bundle, NSPrincipalClass=NSApplication, no LSUIElement; unique test ID | Packaging already tested without resolving the common symptom |
| Launch | Exact retained executable via owned Popen | Exact bundle executable via owned shell child | Neither test uses LaunchServices open; this is not the source of their historical difference by itself |
| Publication wait | 250 ms settle, then one observer process | Identity polling and repeated AX traversal under one 15 s discovery budget | Early publication can be separated from persistent failure; extending a sleep is not a demonstrated fix |
| Checkpoint event service | NSRunLoop.runUntilDate while waiting for observer acknowledgment | Host nextEventMatchingMask/sendEvent/updateWindows | This is a shared conformance-side difference affecting both engines; test independently |
| External query | AXUIElementCreateApplication(owned PID), CopyAttributeValue(AXWindows), strict role/title/PID/bounds | Same per-app API; bounded descendant traversal; system-wide fallback only after a valid per-app array | Conformance has no system-wide fallback; this control keeps lookup strictly per-owned-app |

Apple documents [accessibilityWindows](https://developer.apple.com/documentation/appkit/nsaccessibility-c.protocol/accessibilitywindows)
as the app's windows, and [AXUIElementCreateApplication](https://developer.apple.com/documentation/applicationservices/1459374-axuielementcreateapplication)
as the top-level application object. A successful attribute return is not
evidence that its elements have the required role or identity.
[NSApplication](https://developer.apple.com/documentation/appkit/nsapplication)
owns window tracking and event distribution. These contracts motivate the
control; they do not identify the cause of the observed OS projection.

## Minimal regression control

`run_ax_regression.py` builds a stock AppKit NSWindow containing a stock NSButton,
with no GPUI, MoonBit, Metal, custom AX element, semantic action or GPU readback.
It uses the same external observer's PID/start/executable/window/title/bounds
checks. The ready record reuses the existing protocol's sequence field solely
for owned acknowledgment; no GPU frame is claimed. A distinct AXApplication
alias is rejected even if trust and AX error codes indicate success.

Only Accessory policy is tested. The window is placed behind others, ignores
mouse events, never becomes key, and the fixture aborts if it observes a
foreground-app change, active state or key/main-window ownership. Cleanup
kills/reaps only owned children. There is no permission request, signing change,
LaunchServices registration, system-wide lookup, screenshot, AXPress, keyboard
or pointer synthesis. The AppKit pump variant services application-defined
events, without keyboard/pointer dispatch; it is a narrow event-retrieval
experiment, not a complete replica of the Button host's NSEventMaskAny loop.

Run each cell from committed source on the same Apple Silicon session, using
a fresh output directory. The default is one bundle/runloop cell:

```sh
python3 run_ax_regression.py --packaging bundle --pump runloop --output _build/ax-control-bundle-runloop
python3 run_ax_regression.py --packaging bundle --pump appkit --output _build/ax-control-bundle-appkit
python3 run_ax_regression.py --packaging flat --pump runloop --output _build/ax-control-flat-runloop
python3 run_ax_regression.py --packaging flat --pump appkit --output _build/ax-control-flat-appkit
```

Each cell retains compile commands/logs, copied native sources and hashes,
executables, plist, local hierarchy and every external observer attempt. The
fixture has a five-second lifetime; the parent polls within 4.5 seconds with
individual observer children limited to 750 ms. Timeout/failed attempts remain
retained. A late match does not erase an initial alias. Exit 0 means only the
stock control's external window matched and the fixture exited normally;
exit 1 leaves it unverified; exit 77 means an unsupported host. The summary's
`gpui_ax_compatibility` remains `unverified` even on a stock-control pass.

| Result on the same session | Next discriminating check |
| --- | --- |
| Stock AppKit also returns its AXApplication | Investigate the external client/session/OS bridge before changing either engine hierarchy |
| Stock passes; conformance fails | Compare event service, owned window lifecycle and per-engine AX hierarchy with the retained stock response |
| Only AppKit pump passes, repeatedly | Event retrieval is implicated; repeat with identical source/packaging before modifying the shared checkpoint |
| Only later attempts pass | Publication timing is implicated; retain time-to-first-correct-window and initial responses before designing readiness retry |
| Only bundle or flat passes | Investigate measured bundle/runtime registration differences; do not relax exact identity checks |

The earlier screen-locked marker is a correlation, not a proven cause. The new
control does not infer lock status. Record the session state only when actually
observed. A user-controlled unlocked rerun can be compared with the retained
locked-session evidence; never unlock or change TCC automatically. Regular
policy and LaunchServices launch experiments remain unrun because the existing
paths can activate a window. The next engine acceptance still requires an
independent external client on the exact final source; stock-control success
cannot close Button issue 0024 or qualify GPUI AX semantics.

## Validation in this change

1. `python3 -m unittest discover -s tests -p 'test_ax_regression.py' -v`: **PASS**, 8 tests (synthetic identity rejection, real owned-child cleanup and Linux guard).
2. `python3 -m unittest discover -s tests -p 'test_*contracts.py' -v`: **PASS**, 52 existing contract tests.
3. `python3 -m py_compile run_ax_regression.py tests/test_ax_regression.py` and `git diff --check`: **PASS**.
4. `python3 run_ax_regression.py --output _build/ax-isolation-linux-guard`: exit **77**, native/AX **UNRUN**, summary **unverified**. See the committed [Linux guard receipt](results/ax-appkit-isolation-linux-20261015.json).
5. macOS compile, native control matrix, engine rerun, external Button AXPress and independent review: **UNRUN** locally. CI has a separate macOS compile-only job; it launches no fixture and makes no AX call. Its result must be checked on the published HEAD.
