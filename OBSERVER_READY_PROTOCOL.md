# Owned native window observer

`run_native.py --observe-visible` is an explicit opt-in to a bounded observer
fixture. Default runs remain hidden. Both native adapters complete GPU readback
before entering the shared checkpoint. The checkpoint gives only its own sole
accessory window a nonce-bearing title and orders it behind other windows.
It never activates an application or requests a key window.

The ready record binds the execution nonce, PID, kernel process-start seconds
and microseconds, actual executable path, retained executable SHA-256, pinned
source revision, scenario SHA-256, frame sequence, native window ID, content
size and scale. Parent validation precedes observer execution. The observer
rechecks the kernel start/path identity before requesting metadata for exactly
that window ID; it does not enumerate or capture the desktop.

`AXIsProcessTrusted()` is read-only and never prompts. If existing trust is
available, the observer reads only that owned application's AX window list,
bounded to 16 windows, and requires exactly one window matching PID, nonce
title, AX role, position and size against the bound WindowServer window. If
trust or matching is absent, AX remains unverified even when WindowServer
binding succeeds. This qualifies a window identity observation only; semantic
node behavior, actions, physical input and post-action state are separate work.

Before primary observation, real negative controls use a stale process start,
invalid PID zero and invalid window ID zero. All fail before external window/AX
lookup. Foreign-window and wrong-nonce rejection are also covered by portable
contracts. No control selects another application's window.

The parent acknowledges only a valid owned observation using the same nonce,
PID, window ID and frame sequence. The checkpoint waits at most five seconds;
the runner has one 15-second monotonic budget per owned fixture, including
observer subprocesses. Completion, refusal and timeout close or terminate only
owned fixture processes. The comparator validates retained ready/observer/ack
artifacts, actual observer executions, build/binary hashes and negative controls
before accepting visible native evidence. It does not turn an unverified AX
observation into a pass.

No screen capture, physical input, permission request or security-setting change
is part of this mode. Use fresh output directories and coordinate any future
work that requires user interaction.
