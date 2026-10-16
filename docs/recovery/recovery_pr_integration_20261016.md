# Recovery PR Integration

This integration starts from main `3f71afc8f46f4abfcf93552a35fc02f543ffdf33`,
which includes the reviewed CRT-delay PR #398. It preserves these original PR
heads as ancestors instead of replacing their histories with cherry-picks:

| PR | Original head | Scope |
| --- | --- | --- |
| #395 | `6d39c2c6dc803d797992afc6565b719000101dad` | Original CPU-work observations |
| #397 | `0f64c2c45c95226c1249e329486c56987620d97c` | Adaptive frame-pacing evidence |
| #400 | `ec3aa7dae988fb460c0df57c87fd24af8c1b344e` | Resumable DOS GetTime |
| #401 | `91a9c7802897cee777dcd0598aa81136f16e618e` | Recovered timer IRQ runtime |
| #402 | `f6618567649991c02667aa3538feef27354067a3` | Shared DOS/IRQ execution |

The #400 and #401 ancestry merges leave the preceding integrated tree unchanged.
Their existing source implementations were already included in #402. Remaining
registration conflicts retain both sides: CRT, renderer, pacing, DOS and IRQ
tests, ownership entries and fixture attributes remain present.

## Review Repair

The current-head #397 review found that the analyzer rejected the capture paths
documented in `tools/frame_pacing_probe/README.md`. Its source repository does
not have to live in RAM, and the pinned emulator executable does not have to
have a particular parent-directory name.

The analyzer now accepts canonical absolute source and emulator paths, including
spaces, while retaining the RAM-only output rule and exact relationships among
the producer command, emulator command, mount, working directory and environment.
Relative, non-normalized and control-character paths remain rejected. Host and
producer hashes, canonical assets, silent configuration, input events and trace
binding are unchanged. Positive recipe-relocation tests are analyzer controls,
not newly captured original-game evidence.

The first integration review also reproduced acceptance of altered host,
producer, executable, asset and guest-write claims by the CPU-work analyzer.
Those five counterexamples are now rejected before a recipe is marked verified.
The two original compact r3/r4 recipes remain immutable under canonical JSON
fingerprints; their missing fields are not fabricated. New complete producer
reports must satisfy the pinned hashes, all fourteen canonical assets, typed
read-only and scope flags, silent profile, source/launch relationships, private
display geometry, command/event/sample binding, and the trace module identity.

The retained full r3/r4 producer reports are included as independently pinned
metadata fixtures. They were recovered from the existing observations, not
newly acquired runs, and contain no raw RAM or image payloads. Existing trace
and compact-fixture bytes are unchanged. CLI rejection controls check both
failure without publication and preservation of existing reports.

The follow-up review found segment attribution and checkpoint-authentication
gaps. Every game marker now requires its original code segment and offset; CRT
entry/caller markers and both IRQ vectors have separate ownership checks. IRQ
return targets must lie in the linked code units or BIOS. The two CRT callers
are backed by the original far-call bytes at `1614` and `79e3`, both targeting
`084a:029c`. The host-exit row is terminal metadata, not an attributed instruction.

`capture_recipe_verified` now authenticates only the exact four retained recipe
identities. A new full producer report can satisfy the execution contract without
authenticating its checkpoint metadata. Such a report explicitly carries
`capture_execution_contract_valid=true`, `capture_recipe_verified=false`, and
`capture_checkpoint_metadata_authenticated=false`. The analyzer never claims
verification of raw checkpoint files, which are not supplied to it. Altering
saved scores, record bytes or RAM hashes cannot retain the old whole-recipe label.

The local full-suite attempt did not complete: long C++ campaign replay outputs
filled the 12 GiB RAM filesystem, causing subsequent writes to fail. Its partial
results and failure diagnostics are retained, and no full-suite pass is claimed.
Completed successful C++ frames were losslessly compressed with per-file hashes
and a restoration map; original captures and failed-route outputs were unchanged.
Bounded current-head tests are used locally; complete CI remains required.

## CI Headroom

The second Windows attempt for #395 completed every recorded step successfully,
including its full CTest step, but GitHub cancelled the overall job at the
90-minute job bound. The integrated Windows job has a 120-minute bound. No test
is removed, no assertion or per-test timeout is weakened, and the cancelled job
is not relabeled as successful. The combined head requires fresh validation.

## Boundaries

PR #243 is excluded. Its gameplay extraction has a live-tick diagnostic-copy
finding and substantial conflicts with subsequent recovery work. Merging its
stale implementation is not a substitute for repairing and validating it.

This integration does not establish natural frame-cadence fidelity, complete
BIOS/DOS ownership, synchronized pixel parity or whole-game completion. The
existing subsystem evidence limitations continue to apply.
