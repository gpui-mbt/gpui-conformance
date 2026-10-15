# Browser side-by-side lab (experimental)

Static GitHub Pages shell for previewing **real** gpui.rs (Rust/WASM) and gpui.mbt (MoonBit/JS) applications in two same-sized frames.

## Status

- Implemented: two labeled frames, editable URLs, reload, independent links, responsive layout, explicit UNVERIFIED status, fixture picker that rejects unimplemented shared tests.
- Not implemented: bundled upstream Web/WASM binary, mirrored shared UI fixture, deterministic synchronized interactions, visual diff, metrics, retained artifacts, pass/fail evaluation.
- This is NOT a conformance result. The existing CLI/native/headless harness and pins.json remain unchanged.
- Default MoonBit URL is the already-published Weekboard; upstream URL is intentionally blank. The apps are **not equivalent**.
- Some targets reject framing with CSP `frame-ancestors` or `X-Frame-Options`. The target app might require COOP/COEP or workers; serving the same origin is preferable.

## Local preview

```sh
python3 -m http.server 8080 -d web
```

Open http://localhost:8080. Supply both HTTPS URLs, or `?rust=https%3A%2F%2F...&moon=https%3A%2F%2F...`.

## Build/hosting follow-up

1. Create a **single shared fixture spec** consumed by gpui.rs Web and gpui.mbt Web (start with fixed row/gap and an opaque rectangle). Do not pretend Weekboard and the upstream hello gallery are matched fixtures.
2. Pin a compatible upstream GPUI Web revision separately from the existing native pin if necessary, build the `gpui_web` hello/fixture with Rust + Trunk, and build the MoonBit fixture with its JS backend. Bundle both under `web/rust/` and `web/moonbit/` on the **same origin**. Update the default URLs only once both are genuine fixture builds.
3. Replay deterministic pointer/keyboard sequences and record per-runtime event traces and screenshots. Compare with documented tolerances and retain evidence; status becomes PASS/FAIL only when evidence is actually verified.
4. Use workflow_dispatch on the dedicated branch for a deliberate Pages deployment. GitHub repository Pages source must be configured for GitHub Actions by a maintainer. Deploying this branch can replace the site's current published content: do not dispatch before approving that change.

Source boundaries: upstream Zed is read-only and never modified. Existing `run.py`, native fixtures, and validated results remain unchanged.
