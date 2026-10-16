# Coupled Pacing Device Clock

## Recovered Behavior

`PacingDeviceClock` composes the existing pinned PIC work clock with the
timing-relevant effects of VGA PART callbacks. It predicts the original pacing
fragment's CPU budgets, queue evolution, millisecond grants and IRQ0 eligibility
across nonzero CRT.Delay. This removes the observed-IRQ-position input required
by the earlier full-pacing CPU-only proof for the validated device profile.

The generic PIC work clock still stops at foreign callbacks. Explicit callback
consume/schedule/remove APIs allow the composed owner to apply recovered device
effects, retaining stable equal-deadline insertion and event-service lag.
VGA vertical callbacks schedule the original vertical, latch, panning, retrace
and draw-part events; PART callbacks advance line/part counters and either
reschedule or end updating. VGA retrace does not create the EGA-only IRQ9.
The observed idle keyboard and silent mixer have no queue/IRQ effect; their
actual ticker identities and initial no-input/no-channel conditions are checked.

## Original Evidence

The new read-only observer classifies events by direct original function pointer
equality. It records the fields that drive scheduling and the actual ticker list,
without materializing lazy flags, pausing the guest, seeding clocks or changing
game state. Original CPU core source and callback bodies are unchanged; appended
getters and their generated patch are source/host-hash bound.

Two silent, naturally entered level-one captures completed:

| Run | States | IRQ Entry State | CPU Projection SHA-256 |
| --- | ---: | ---: | --- |
| r1 | 72,386 | 35,738 | b45dfbb0cdc67113abe0e83ff07225cd333f44492485014b4391a9c94f93d517 |
| r2 | 60,408 | 18,675 | 46e00ceabf48def2ba06c0d3a3ae929758ad997919165c782dc74c66ea8c2728 |

Both begin before a VGA vertical callback and execute PART rescheduling. They
observe the latch/panning/retrace events being scheduled, but those three
callbacks are not executed inside these windows. Their clock effects have
focused source-derived unit coverage, not additional natural runtime coverage.

The C++ replay checks all 132,794 states twice, including snapshot restoration:
265,588 CPU, stack, shared memory, ordered I/O, PIC/PIT/queue and device-state
comparisons. Both IRQs are computed from initial clock/device state, giving four
predictions across the two restore modes. No later CPU flags, memory, clock
snapshots or observed IRQ positions are used as driving inputs. Natural CPU
flags are compared under observed control mask `0x700`, not full arithmetic flags.

All ten raw RAM checkpoints independently match 43,552 relocated original code
bytes and retained PNG hashes. Raw RAM and screenshots remain local. Frozen
fixture validation reports `raw_ram_files_verified=0` and `execution_proof=0`;
the raw verification and C++ execution proofs are separate validation steps.

## Validation

- 38 focused CTests passed, including the older clock/display/interrupt proofs.
- Native MSVC `/W4 /WX` compilation, coupled replay and older proofs passed.
- Four fixture test methods passed on Linux and Windows, including 60 changed/
  missing-source/output-preservation controls, five frozen-file corruptions and
  three truncated/extra-terminal/missing-dispatch controls.
- Five coupling controls show observed IRQ positions are unused by coupled replay,
  while the observed-IRQ mode consumes them, and reject changed later CPU,
  device and budget observations.
- Twelve unrecovered profile inputs are rejected by the device-clock constructor.
- Four behavioral faults were detected: PART deadline, latch deadline, line progress
  and double CPU dispatch after a callback.

Changing the callback reentry boolean while already in the Queue phase is
equivalent because that parameter is consumed only in Predecode. The passing
mutation is retained locally and excluded from the detected-fault count.

## Acceptance Boundary

This is a fixed-6000 normal-core, VGA/PART, zero-frame-skip, idle-keyboard,
zero-mixer-channel timing proof. Other graphics modes, active keyboard/repeat
events, other IRQ handlers, enabled audio channels and arbitrary host capture
profiles remain incomplete. No production App cadence integration, HUD/key
handling after `79E8`, complete frame sequence, pixel alignment, natural wall-clock
fidelity or whole-game completion is claimed. Full local App/full-suite validation
was not rerun above the disk guard. All new validation and captures were RAM-only.
