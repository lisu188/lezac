# Standalone runtime packaging

## Reproduced failure

The Windows release artifact built from `df8ee717e55feea377d6fc2276bede7c1bb38abd`
contains `lezac_cpp.exe`, `SDL2.dll`, and the 20 original/JSON resources, but no
MinGW C++ runtime DLLs. Its executable imports `libgcc_s_seh-1.dll` and
`libstdc++-6.dll` in addition to SDL2 and Windows system libraries.

Launching this extracted package on Windows without MinGW installed exits
with `3221225781` (`0xC0000135`) before application output. This is a loader
failure, not a rendered-frame mismatch. The previous install smoke test
inherited the compiler's PATH and did not prove standalone deployment.

The new isolated-package check also rejects the old archive with this exact
loader status. Its failure and empty validation log are retained under
`/dev/shm/lezac-package-negative-evidence-20260930/lezac-startup-rng-55lv1x89`.
Earlier original captures, fixtures, and CI evidence are unchanged.

## Installation change

MinGW Windows installations now inspect the executable's recursive PE import
closure with CMake's install-time `file(GET_RUNTIME_DEPENDENCIES)`. The scanner
uses the configured objdump, compiler directory, and SDL runtime search hints.
It excludes API-set imports and files under the actual Windows system root,
and rejects unresolved or conflicting DLLs instead of producing a partial
bundle. Non-system dependencies are installed beside the executable.

This uses the existing CMake 3.16 API, not static-linking changes or a hardcoded
list of GCC DLL names. Non-MinGW SDL installation behavior is unchanged.
Reference: https://cmake.org/cmake/help/v3.16/command/file.html#handling-runtime-binaries

## Independent package verification

The install smoke test uses a fresh prefix on every invocation so stale DLLs
cannot fill a missing dependency. Windows child PATH contains only SystemRoot
and its System32 directory. Installation still runs with the configured tools;
only the validation child loses compiler paths. No existing install evidence
is recursively removed.

Both release jobs extract the actual tar/zip into a fresh runner-temporary
directory and run:

```text
python tools/test_startup_rng.py --isolated-package --exe <extracted-executable> --out package-startup-checks
```

This mode uses the extracted executable's directory as its working directory,
validates all 20 packaged assets, runs `--validate`, and compares the original
clock's intro/first-present pixels and backdrop bytes against the pinned DOS
capture. A separate natural-clock run checks the production seed boundaries.
Original binary assets must be byte-identical; JSON values must match through
the strict parser, allowing checkout newline differences. Both source and
package SHA-256 values are recorded. The child cannot inherit JSON-asset mode,
compiler PATH, LD_LIBRARY_PATH, or LD_PRELOAD. Audio and video are forced dummy.

Success and failure manifests/logs are uploaded even when the comparison
fails. Success includes executable identity, working directory, child PATH,
asset checksums, and `whole_game_parity=false`. Unit checks reject missing or
changed assets, inherited compiler paths, and audible audio settings.

## Validation at submission

- Eight Python checks passed against the fully extracted earlier Linux package
  (`c76a426`), including 128,000 exact RGB pixels and 60,000 backdrop bytes.
  Its production sources match the startup recovery head; this validates the
  new checker, not a newly built Windows bundle.
- Selecting an executable-only Linux scratch extraction first failed for a
  missing resource. A later initial byte-hash comparison failed on JSON newline
  differences. Both failures were retained; neither was relabeled a pass.
- Local Windows self-tests passed seven checks with the native executable case
  explicitly skipped when no executable was supplied.
- Silent-launcher policy, 19 source-guardrail cases, diff whitespace checks, and
  RAM-backed Linux CMake configuration passed.
- Fresh Windows dependency closure, isolated native Windows rendering, and full
  Linux/Windows suites remain CI acceptance requirements for this change.

No gameplay, original assets, original fixture pins, or incomplete physical
reentry evidence was changed. Standalone packaging does not establish full
campaign fidelity, physical input parity, or whole-game completion.
