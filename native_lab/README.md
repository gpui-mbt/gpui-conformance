# Linux native side-by-side lab (X11 host)

Status: experimental native comparison; NOT a replacement for run_native.py.
The existing nonactivating macOS AppKit/Metal runner is untouched.

## Native architecture and limitations

A single Python launcher builds the pinned gpui.rs Rust executable and the pinned
gpui.mbt MoonBit executable independently. Both use native host APIs, distinct
processes, the same checked-in native_scenarios.json, the same 256 x 192 logical
content viewport and a requested scale of 1. The Rust process uses the gpui.rs
X11 backend. The MoonBit process uses the real gpui.mbt Ubuntu Wayland/EGL
host; an owned Weston x11-backend output represents it as the second X11
top-level window. **The MoonBit backend is not X11.** This dependency is
explicit in comparison.json and must not be called X11 backend conformance.

This is an interactive two-window experiment, not an embedded single-process
widget, mirror screenshot, virtual simulation, headless GPUI render, or source
for new Zed examples. A local X11 WM that implements EWMH is required.
Windows are identified by *owned child PIDs*, not by matching an arbitrary
window title. Weston is bound to its own XDG_RUNTIME_DIR/Wayland socket.
The launcher can only terminate its own child process groups.

A real GPU-backed compositor and window are used, but GL/EGL on CI can be
software-rendered by Mesa llvmpipe. A screenshot and a FrameCompleted
callback establish native presentation; they do not prove use of a physical
GPU, equal GPU implementations, compositor color management, accessibility
or physical input correctness. macOS and direct-Wayland modes are out of
scope and deliberately separated.

## Run from pinned source checkouts

Expected host: Linux X11 session with Openbox/another EWMH window manager;
Python 3.12+, Pillow, ImageMagick import, wmctrl, xdotool, xwininfo, Weston (including
x11-backend and kiosk-shell modules), Rust toolchain 1.98.1, MoonBit native,
Wayland/EGL/GLES development headers and C toolchain. The launch needs
working Mesa Vulkan/WGPU for gpui.rs and EGL/GLES for gpui.mbt.

The copied gpui.mbt tree generates system-specific Wayland protocol C/H
stubs with its own `scripts/prepare_ubuntu.sh` before native compilation.
The four generated file digests and script stdout/stderr are retained; this
step does not modify the checked-out source.

Checkout the SHAs from the repository pins.json. Both source trees must be
committed and clean, at the declared package versions. The runner archives
the MoonBit tree into a disposable build tree and builds the Rust adapter
outside the upstream tree; no source changes are applied.

    python3 native_lab/launcher.py \
      --upstream-source /path/to/zed \
      --moonbit-source /path/to/gpui.mbt \
      --output _build/native-lab-run --online

Default Cargo mode is offline. Pass --online when dependencies have not yet
been cached. The Linux/X11 adapter resolves its target-specific dependency graph
from the copied native probe lockfile and retains rust-resolved-Cargo.lock plus
its digest. A resolved lock is therefore evidence, not yet a committed
cross-platform dependency pin. For build-only checks:

    python3 native_lab/launcher.py --build-only --output _build/native-lab-build

For an interactive desktop observation, use --interactive. Close the UI or
interrupt the launcher to stop owned processes. Controlled resize is then
marked unverified.

To prove the comparator rejects a real changed rendering, use
--negative-control; the MoonBit adapter then paints the rectangle blue
instead of the fixture red. Expect exit 1 and pixel mismatch after a
successful live capture. This deliberately does not change fixture inputs.

## What comparison.json proves

The report retains pinned source identities, SHA-256 of the fixture input,
executable digests, independent build commands/logs, each owned PID,
run-token-bound native event lines, X11 top-level IDs, initial placement,
captured upstream.png/moonbit.png and their SHA-256 digests. It derives the
three interior sample colors directly from actual screenshot bytes. Both
implementations are checked against the shared fixture AND against each
other, with full-frame RGB difference counts for diagnosis (edge
antialiasing can legitimately vary by renderer). A first-frame callback
is required from each actual native executable before capturing pixels.
Build timing, launcher-observed first-frame timing, native events and
window resize requests/results are separately reported.

Exit 0 / pass requires two matching observed rendered fixtures and
corresponding native resize events. Exit 1 / mismatch means observed pixels
are inconsistent with the shared fixture or one another. Exit 2 /
unverified covers missing display, child/window identification, failed
build/launch, missing screenshot, incorrect or missing resize event,
build-only, or interrupted manual mode. One passing contract test is
never silently promoted into runtime evidence. The runner has no
unverified->pass fallback.

The controlled resize requests 320 x 224 on both top-level windows.
Wayland's own size negotiation may not mirror the Weston X11 outer window;
when either native app does not report this size the resize is explicitly
UNVERIFIED, not a claim of parity. Weston X11 surface and Rust native
client may also differ by window decorations; the actual captured
viewport dimensions are checked and failure is retained. No input
automation or accessibility claim is made.

## Portable tests and actual native GPU checks

    python3 -m unittest discover -s tests -p 'test_native_lab.py' -v

These test contracts with synthetic fixture **images**, not native
execution. In particular the negative control, mismatched capture
dimensions, absent GPU event, wrong run token and build-only result
are tested. The optional Linux action additionally attempts to build
both pinned engines, run Xvfb + Openbox + Weston, capture real frames
and upload comparison.json plus build/runtime logs. CI marks a missing
native observation UNVERIFIED; a green portable job is not a GPU pass.
Do not mark this native slice verified until its own real run is pass.

## Next qualifications (separate PRs)

1. Direct gpui.mbt X11 host backend, or an explicitly comparable
   direct-Wayland paired mode, with the same renderer/scale evidence.
2. Native close/resize/keyboard and pointer event qualification with
   window-to-PID ownership, stable traces and negative controls.
3. macOS interactive NSWindow pair using its own launcher/observer,
   without changing the existing nonactivating macOS diagnostic runner.

If the real observations reveal discrepancies, file a focused gpui.mbt
issue/PR with the retained scenario JSON, frame hashes and actual native
event traces. Never repin the gpui.rs oracle to make a failing pair pass.
