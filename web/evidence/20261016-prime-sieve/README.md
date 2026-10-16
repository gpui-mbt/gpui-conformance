# Retained Prime sieve captures

These files are byte-for-byte copies from [browser CI run 38855611489](https://github.com/gpui-mbt/gpui-conformance/actions/runs/38855611489), artifact `browser-example-evidence` ID12026777653. ZIP SHA-256: `7ae05b0b691c113210c08bd005705c69db53ce0d93031f8cec6a3f4da00269c4`.

The source head is `faab43b9b9ee73fc8e1f0b6864b4cf9083c44877`, and CI built synthetic merge `a613f026400c2f23fdd599952843e75d713fe6fe`. Both have tree `6c957d303cb9a5ca74bce13aaaec2993f169375b`. These identify the original capture, not the later commit retaining it.

The unchanged upstream Rust/WASM and compiled MoonBit examples each actually counted all primes below 10,000,000 and rendered **664,579**. Both PNGs are complete 640×560 captures without resizing, cropping or retouching. The catalog asset is byte-identical to the MoonBit PNG. `captures.json` records the run, source blob, report/scene/OCR digests and both image digests/dimensions. `prime-sieve-moonbit-scene.json` retains all 12 contiguous computed chunks, application state and terminated worker-pool diagnostics. The upstream screenshot and raw OCR are retained together for inspection; OCR has imperfect transcription of decorative/non-result text.

The MoonBit capture used four workers and the Rust capture reports two background threads. Their elapsed times include different scheduling and are **not a performance ranking** or a render-startup benchmark. These images are previews; pixel equality, native parity, shaping, scheduler equivalence, keyboard accessibility and full 50M/100M execution remain unverified. The raw report's `raster_comparison` applies only to hello_world and must never be assigned to Prime sieve.
