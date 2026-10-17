# Gradient Stage A: unchanged Rust oracle and separate GPU diagnostic

## Status and scope

Source-only implementation, not an observed baseline yet. Rust/WASM compilation and real browser captures run only in CI. A draft review, exact independent source review, actual CI artifacts and independent original-artifact audit must precede any parity conclusion. No MoonBit candidate, core changes or live implemented catalog registration. Stage B architecture is unselected.

The unchanged oracle builds the exact `crates/gpui/examples/gradient.rs` blob `df1398fff58b637abf0c0b31934f6ad523d84a21` at Zed `5a5fbe79917971a4d52a96b6ddb04da198a5012e`, tree `990fb995914d51a546b20e5cf0382dafc105c299`. SHA256 is `620dbeccd4daa80f71cb1c67f1628508cb397e9aeb4b5a5d0abe0a2a45aad193`. The relocated package registers the original file path. It never edits the upstream source. Supporting original source bytes, font inputs, lock, package manifest, binary/loader/host and generated worker responses travel with the evidence. Separate `gradient-diagnostic` files build deliberately authored diagnostic inputs; their observations must never be attributed to the unchanged example.

## Frozen host profile, before any execution

DPR 1, 960×600 (wide) then 600×960 (tall), then 960×600 restoration. These are explicit browser host profiles, not upstream default window dimensions: the example supplies no fixed window bounds. Both retain the 16px root inset, 12px gaps, two solid rounded quads, 12 gradient rounded quads and one polygon. Each viewport receives initial sRGB, a real trusted click to Oklab, and a second click restoring sRGB. The pointer leaves the button after each click. Original complete PNG pairs must stabilize by identical decoded RGBA; every intermediate/failure capture remains available. The final resize must restore the original full wide image. CSS viewport, canvas rectangle/backing, DPR, trusted raw events, document identity and navigation count are retained.

Button targets come from the previously captured black button component, not an application API or synthetic click. The unchanged application has no test hooks. The independently reread artifact verifier checks row cardinalities, 15 colored components, unchanged solid regions, changed gradient interiors, full restoration, and source polygon geometry. Rounded-edge/glyph equivalence is unclaimed.

## Source facts and mathematical observations

`gradient-sources.json` freezes the original example and relevant implementation hashes. `ColorSpace` defaults to `Srgb`; the displayed label is `sRGB`. Source green is channel 0.5, not 1 and not 127/255. `Half` halves geometry; it is not f16. Raw angles 0/45/90/135/180/225/315/360 and authored stop values are retained. `linear_color_stop` does not sort or clamp them. Equal stops reach a shader division by zero before clamp; the CPU math reporter deliberately leaves exact-boundary semantics pending for genuine GPU observations.

The WGSL `hsla_to_rgba` returns the converted channels directly. The sRGB gradient prepares endpoints with `linear_to_srgba`, interpolates them and applies `srgba_to_linear`; Oklab uses its own forward/inverse matrices. The shader aspect-adjusts its direction, projects the point relative to the center and chooses the dominant axis for normalization. Source-math predictions preserve float alpha. These double-precision calculations are not a replacement for f32 shader execution. The report exposes original sampled bytes and mathematical predictions without a fitted tolerance or color-match pass. Colored-component bounds are visibly measured raster bounds, not instrumented layout bounds; white endpoints and antialiasing can omit edge pixels. Exact color conclusions remain pending source/artifact review and actual backend facts.

The polygon's X origin is 0.1×canvas width and deliberately omits `bounds.origin.x`. Its vertices occupy y+30..y+80, so tight bounds are 50 px high, not 80. WGPU path rasterization supplies `path.clipped_bounds()` to gradient normalization; clipping belongs in the separately authored diagnostic. The source oracle preserves the omission and geometry. Geometry checks allow only the explicit integer raster extent uncertainty (1 px origin/height, 2 px width), not an empirically tuned image tolerance.

## Backend limits and evidence integrity

The capture records Chromium graphics information and transparent browser-API observation wrappers. Successful WebGPU canvas configuration records the actual format; successful WebGL context creation records its returned renderer/version. `WgpuRenderer`, `navigator.gpu`, or an adapter request alone does not establish the selected backend. Missing or ambiguous facts stay pending. Wrappers forward the original receiver, arguments and return values and are themselves retained as suite inputs. Workers may limit API visibility; no backend is inferred to fill gaps.

This is browser/WGSL-bounded evidence. Metal has different transfer/dither logic and native parity is explicitly unclaimed. The verifier binds every retained source/runtime response/worker/input/PNG to the exact committed suite, manifest, route, session and operation. It rejects altered source, runtime, profile, input, capture bindings, missing executable bytes and malformed PNGs. Negative controls are synthetic corrupted-evidence sensitivity, not actual core mutants. No existing anchor/native evidence is altered.

## Execution

Workflow: `.github/workflows/gradient-oracle.yml`. It installs Pillow 12.0.0, Playwright 1.56.1, nightly-2026-10-14 and wasm-bindgen 0.2.129, builds only `--oracle-only --extra-example gradient`, captures, independently verifies and uploads originals even after failure. Diagnostic execution uses its separate workflow and artifact.

Local checks are limited to packaging, JS syntax/source math, synthetic event/provenance and PNG contract tests. The local environment's Pillow 12.3.0 cannot substitute for pinned 12.0.0; pinned decoder tests are skipped locally and required in CI. Neither local static checks nor a successful build establish observed GPU behavior.
