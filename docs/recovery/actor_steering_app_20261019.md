# Production Behavior-4 Steering Integration

## Production Change

`App::retargetMonster` now obtains homing velocities from
`core::actorSteeringVector8`. The typed boundary accepts signed component words
and the full unsigned speed word, executes the recovered original call site and
Real48 helper, checks its actual return to `1000:714F`, and returns the two signed
low-word velocity stores. Its implementation lives in `lezac_core`; `app.cpp`
does not include the CPU-operation headers.

The implementation uses an owned 4096-byte stack window and exposes only that
window, the original stack floor, and the speed input to the memory bus.
Unexpected memory or hardware access is rejected. Execution has a 65,536-step
reserve, well above the captured maximum of 4,718 states. No host floating-point
calculation supplies either velocity. Target selection, player admission,
distance/range gates, global tick gating and random wandering remain unchanged.
The existing behavior-4 lockstep diagnostic also compares the recovered result
with its independently stored original ticks.

## Evidence and Counterexample

This is a derived consumer of the authenticated original capture documented in
`actor_steering_20261019.md`, not a new original capture. Parent projection SHA-256:
`acc7c781d4fcf5d24e16ffdccefd13032830c1010b8453b30aefd1210f8ed334`.
The exporter verifies the original manifest, producer and executable pins before
extracting explicitly seeded inputs and actual observed output writes.

The compact output is reproducible and is exported during testing rather than
adding another binary fixture to Git:

| Item | Value |
| --- | --- |
| Typed vectors | 2,136 |
| Original live-caller rows | 64 |
| Admitted by the existing App homing gate | 2,097 |
| Excluded by that gate | 39 |
| Admitted original live-caller rows | 52 |
| Square-root-only cases excluded | 1,536 |
| Original runtime-error cases excluded | 10 |
| Far-reference alias cases excluded | 54 |
| Compact bytes | 34,220 |

Compact SHA-256:
`ee4722d4876bfd19dcb9aa7f314a24c6ae5d1f500c39dd8d3f907ecaa2c9236c`.
The exporter pins this exact output. The C++ diagnostic parser additionally
checks the complete input with the existing FNV-1a fingerprint helper, validates
the parent digest and requires the exact domain and gate counts. FNV is a
secondary corruption guard, not a cryptographic provenance claim; SHA-256
authentication occurs in the exporter and CLI guard.

Before changing production, the new actual-App probe found **320 mismatching
admitted cases**. It independently invokes `retargetMonster` and the shared-tick
`updateMonsterMotion` path. One ordinary-speed counterexample is original case
148: delta `(-257,0)`, speed `494`, old velocity `(-494,0)`, original `(-493,0)`.
The original divides the speed by the Real48 length before multiplying and
truncating, so replacing that sequence with host `hypot` is not equivalent even
without the old speed clamp. The old App source, executable, output and hashes
are retained as RAM-only failure evidence; none are uploaded in this PR.

Old App source SHA-256:
`3356f08d0bedc688b69fac238f5ab876c4d5545fb663c8e49e2219c9f355e742`.
Old App executable SHA-256:
`6301a4ba1ec3d62436890b42519fb1ff8ea49fb39e7f3bd240c0d51ff4d62193`.

After the production replacement, all 2,097 admitted cases match the original
writes through both actual callers. Every case also checks the off-gate and
zero-period paths and unchanged RNG. All 2,136 vectors match through the typed
API, including the 39 cases whose magnitude is outside the existing App gate.
Those 39 cases do not establish original gate fidelity. The typed API deliberately
does not expose aliased far-reference parameters or erroneous original stack
contexts; the retained resumable CPU operation and its original tests cover
those distinct interfaces.

## Validation

- Full Linux App build, typed boundary and actual App probe pass.
- Strict GCC C++23, native MSVC C++ latest `/W4 /WX /O2`, and ASan/UBSan each
  match all 2,136 original-derived vectors and five explicit original examples.
- Both original 160-tick behavior-4 locksteps pass, including all 318 actual
  `updateMonsters` transitions, RNG checks and the malformed-evidence guard.
- Existing behavior-4 chase, level-2/3 spawners, target selection and player-state
  autoplayer/frame tests pass. Fresh full-size frames are inspected under dummy
  SDL; these are controlled scenario captures, not natural campaign proof.
- Three extraction/authentication Python tests pass on Linux and native Windows,
  covering changed/unavailable producer and original inputs, failed-report and
  existing-export retention, output/input conflicts and seven parser controls.
- Both real Linux CLI consumers pass the canonical input and reject all seven
  altered inputs. Native MSVC's typed consumer passes the equivalent checks;
  a native MSVC App run is not claimed by that result.
- Six separately compiled boundary faults are detected, with baseline sources
  preserved. The first proposed input-swap variant did not compile under
  `-Werror` because it left a parameter unused; it is retained as a failed
  harness diagnostic, not counted as a detected runtime fault. The final
  component-sign faults compile and are detected by the original corpus.

The App build still emits the pre-existing `debugDebrisShatterPlayback`
`snprintf` truncation warning. This change does not modify or suppress it.
Full hosted Linux/Windows CI, packages and completed current-head review remain
required before merge. The parent frozen fixtures and producer bytes are
unchanged; no new cold-checkout family or binary asset is introduced.

## Remaining Fidelity Work

This numerical integration is not a reconstruction of the complete behavior-4
instruction path, target-selection domain, caller stack lifetime, interrupt
schedule, CPU work-clock coupling or full-frame continuation. The typed boundary
runs synchronously without delivering timer IRQs. The resumable original CPU
operation remains available for subsequent frame-level composition. Rendered
autoplayer frames and sampled original tick locksteps do not establish natural
routes, owner visual acceptance, frame timing or whole-game pixel parity.
