# Publication integration evidence

These runs verify the pointer fix after rebasing onto gpui.mbt main
`0bdda0fa181575cc2fb1310261bb7b4c004180bb`. The candidate is
`7dfc80843456a4b7dbf7aa99da87373b6cd8f5ab`; its six-file fix is unchanged from
the earlier measured `e271a28864adb467c4523444affc965bffd1986e` patch.
The original pinned baseline remains `f9f59fe074da3858ca82fe1d5fadd84cd17f0438`.

The suite execution revision was
`c6c06a88aa23509928a4bf26f9705e2d84b3f354`, with clean source checkouts.
The baseline used the September MoonBit toolchain; the rebased candidate used
the installed October toolchain required by its updated main. The adapter now
uses `@json.to_json`, available in both cores, with warnings denied in both
builds. No compiler or package was installed for this validation.

| Actual execution | Pass | Mismatch | Unsupported | Unverified |
| --- | ---: | ---: | ---: | ---: |
| Pinned baseline | 6 | 2 | 1 | 2 |
| Rebased pointer candidate | 8 | 0 | 1 | 2 |
| Baseline width perturbation negative control | 4 | 4 | 1 | 2 |

The candidate resolves the far-edge and zero-extent pointer differences.
The negative control performs real independent executions and changes a
measured MoonBit layout width before output; both layout cases become
mismatches. IME remains unsupported. Native window/pixel placeholders in this
headless corpus remain unverified.

The October candidate also completed the native runner's **build-only** path:
both executables, AppKit runtime and foreground guard were compiled and retained
under `_build/native-publication-build-only`; no native process was launched,
so both cases correctly remain unverified. Earlier real native positive and GPU
negative executions are separately documented in [NATIVE_RESULTS.md](NATIVE_RESULTS.md)
at their exact historical source revisions. This build-only run does not
extend those native claims to the rebased candidate.

[The machine-readable index](results/publication-macos-arm64-20261014.json)
contains metadata, observations and artifact hashes. It cannot establish a
pass without the complete local `_build/*-publication-final` directories,
including the independently built executables and raw process output.
Recompute each retained run with `python3 comparator.py <result-directory>`.
