# Linux headless oracle results (2026-10-15)

The retained 104-case corpus produced **101 pass, 0 mismatch, 1 unsupported,
2 unverified** for the gpui.mbt candidate. The 101 measured cases are all
headless; the three remaining rows are native-only placeholders (IME is
unsupported, and native window/GPU observations are unverified). No Linux
native-window or GPU conformance is claimed.

Inputs and toolchains:

- Linux x86_64, kernel release `6.18.44`
- Zed GPUI `0.2.2`, commit `d9afb21688e04f89d9e94d96d33eb530aef90886`
- Rust `1.98.1` (`48a229cea`, 2026-09-01)
- gpui.mbt `0.7.2`, candidate commit `71da96d9f8eaed89f42937d4edcd3eb2122cfb54`
- MoonBit `0.1.20261012` (`748b63c`, 2026-10-12)
- Scenario artifact SHA-256: `5702d15ae947a7a5195a4e6b509f7ab21abf6f723ca04c21e93cfc27d1c19970`

The intentionally older gpui.mbt baseline `f9f59fe074da3858ca82fe1d5fadd84cd17f0438`
recorded 39 pass / 62 mismatch / 1 unsupported / 2 unverified. The separate
one-pixel negative control recorded 13 pass / 88 mismatch / 1 unsupported /
2 unverified. It changed the expected layout cases to mismatches and was
detected by the comparator. These counts are separate runs, not results from
the candidate itself.

## Rechecking retained evidence

Keep the complete result directory, since it contains the manifest, both
programs, raw logs, and scenario artifact. Run the original 11-case regression
check with:

```sh
python3 tests/test_comparator.py \
  --evidence /workspace/shared/gpui-conformance-linux-20261015/_build/linux-oracle-original-11-baseline-20261015
```

Run the expanded-corpus check with the explicit scenario corpus and summary:

```sh
python3 tests/test_comparator.py \
  --evidence /workspace/shared/gpui-conformance-linux-20261015/_build/linux-oracle-candidate-71da96d-20261015 \
  --corpus /workspace/shared/gpui-conformance-linux-20261015/_build/all-headless-scenarios.json \
  --expected-summary tests/linux-headless-101-summary.json
```

The checker requires the corpus and expected summary together, validates unique
well-formed case IDs and exact status keys/counts, and verifies that the
explicit corpus equals the scenario artifact retained with the run. The
runner's generated `comparison.json` is not used as a substitute for comparing
the retained executable/log evidence.

## Reproducing the candidate run

The following was run with isolated Rustup/Cargo homes and the pinned clean
source checkouts below. Cargo dependency resolution is locked; this environment
already had the dependencies cached, so no online resolution was needed.

```sh
export RUSTUP_HOME=/workspace/shared/rustup-linux-20261015/rustup-home
export CARGO_HOME=/workspace/shared/rustup-linux-20261015/cargo-home
export PATH="$CARGO_HOME/bin:/workspace/shared/dsh-toolchain-home/.moon/bin:$PATH"
python3 run.py \
  --upstream-source /workspace/shared/zed-gpui-oracle-d9afb216-20261015 \
  --moonbit-source /workspace/shared/gpui-mbt-candidate-71da96d-20261015 \
  --candidate-revision 71da96d9f8eaed89f42937d4edcd3eb2122cfb54 \
  --scenarios /workspace/shared/gpui-conformance-linux-20261015/_build/all-headless-scenarios.json \
  --output _build/linux-oracle-candidate-reproduction-v2
```

The command prints the status summary and comparison path. It exits `2` when
native-only rows remain unverified, as they do here. Existing evidence output
directories are never overwritten; choose a fresh `--output` path for a rerun.
