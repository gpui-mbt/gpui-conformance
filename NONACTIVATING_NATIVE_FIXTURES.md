# Nonactivating native fixtures

The native runner now starts both probes as accessory applications with one
hidden, unfocused window. Rust uses the pinned GPUI public
`WindowingRequest::Headless` startup option; on macOS this selects accessory
activation policy while still permitting native windows. MoonBit requires
`Host::start_background()`, a distinct native operation that older libraries
reject. It never falls back to foreground startup.

Both adapters report their own PID, titled-window count, native window number,
visibility, key-window state, application-active state and activation policy
after creation, GPU readback, resize and destruction. The comparator requires
the execution PID, one stable window identity, hidden/inactive states and
accessory policy throughout. It retains and hashes the helper and its build
logs. Removing either side of the new protocol does not qualify its output.
Historical evidence without this protocol retains its original classification.

The runner builds both probes before launching either, gives each child a
fresh challenge, and kills only that owned child after 15 seconds. It does not
restore or activate another application. A failed native operation reports its
framework code, operation and backend in the retained process output. Build-only and
failed/timeout runs remain unverified.

This default mode is internal AppKit/Metal execution evidence. It does not establish
accessibility, WindowServer observation, physical input delivery or visible
desktop behavior. No permission prompt, security-setting change, external
window capture or input injection is part of this protocol. The separate explicit
`--observe-visible` mode is described in [OBSERVER_READY_PROTOCOL.md](OBSERVER_READY_PROTOCOL.md).

Run with a committed engine revision that provides background startup:

```sh
python3 run_native.py --moonbit-source /path/to/engine \
  --candidate-revision FULL_COMMIT_SHA --output _build/fresh-native-run
```

Add `--negative-control` for a real blue-versus-red GPU divergence, or
`--build-only` to compile without executing native fixtures. Use fresh output
directories and the pinned toolchain described in the repository README.
