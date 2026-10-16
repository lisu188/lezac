# Original PIC work-clock boundary

## Scope

This stage models the pinned DOSBox 0.74-3 normal-core work budget and PIC/PIT0
queue, then couples it to the recovered DOS GetTime and timer IRQ operations in
a deterministic test. It does not change the live App cadence or claim a
complete original game scheduler, wall-clock timing, or frame/pixel parity.

The source profile is fixed 6000 cycles, PIT0 count 65536/mode 3, vector 8,
normal non-special/non-auto-EOI PIC operation. Foreign device callbacks, other
eligible IRQs, and the trap decoder remain explicit unsupported boundaries.
Millisecond work grants do not implement other device ticker callbacks.

## Fresh Original Evidence

The completed `lezac-pic-clock-original-t201-r2` run uses unchanged original
LEZAC.EXE SHA256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The read-only host has SHA256
`5e177a945ed1a6821e633fafcbdd8b9a9573b87864f079b9238a65c2ab62678c`.
Its build record pins the baseline source, callback hook, and read-only PIC/PIT
exports. Configured build products were reused; this is not a clean reproducible
ELF build claim. The original CPU source is unchanged by the clock exports.

The producer was launched with:

```sh
python3 -B tools/pic_clock_probe/capture.py --run r2 \
  --repo /mnt/c/Users/andrz/git/LEZAC \
  --dosbox /dev/shm/lezac-pic-clock-host-t199-r2/dosbox-0.74-3/src/dosbox \
  --out /dev/shm/lezac-pic-clock-original-t201-r2 --observe-seconds 600
```

The retained complete recipe records the wrapper and emulator argv, clean
emulator environment, config, cwd, every checked xdotool command, all timed
ordinary keys, every frame-counter poll, and five screenshots/RAM checkpoint
identities. Audio is dummy, and DOSBox speaker/SB/MIDI devices are disabled.
The actual route was `1`, Return, then a 0.75-second ordinary `z` hold and idle.
No prompt-recovery key was needed in this successful run. The optional bounded
prompt route requires both a stalled counter and an exact previously inspected
screen identity; a stalled counter alone never triggers a key.

The original run terminated normally with `end`, child exit zero, and all
canonical assets unchanged. The 893527-byte trace has SHA256
`2d58f60f7bed1a69aac089b7d01078fae2fa3da4d148ab50c5513e0dda772612`.
Complete full-memory windows are calls 1, 2, and 48, totaling 1014 states.
Call 48 contains the natural IRQ0 entry at state 68, followed by 36 executed
IRQ instructions and a real DOS caller return. No memory/register/IRQ/clock
seeding, instruction patches, or process pauses were used.

The failed t199 r1 capture is retained separately and is not relabeled as
successful. Five r2 1-MiB RAM checkpoints were independently rehashed and their
43552 relocated original-code bytes compared before freezing this corpus.
RAM and screenshots were sampled non-atomically and are not a complete frame
sequence. Raw RAM/PNG files stay in RAM; the repository contains only compressed
trace and exact recipe metadata. Fixture checking authenticates those retained
identities, not unavailable raw RAM/PNG payloads.

## Coupled Regression

The test initializes the CPU, stack, sound bank/globals, BIOS/PSP bytes, and
clock from the first observed boundary of each call. Later trace states are
comparison outputs only. The recovered operations compute registers, flags,
stack writes, BIOS tick effects, I/O, EOI, and the next PIC eligibility decision.
The observed IRQ index is not used to deliver an interrupt in coupled mode.

The older clock-only research consumer incorrectly supplied the next observed
FLAGS value, already cleared by hardware IRQ delivery, to the eligibility check.
That failure remains recorded. Coupled mode uses the computed pre-delivery
FLAGS and does not import later observed flag values or IRQ decisions.

Both uninterrupted and per-instruction snapshot/restore replay pass: 2028 state
comparisons, one observed natural IRQ, predicted once in each replay mode. The
existing 21-call DOS/timer corpus still passes 13764 comparisons. Focused GCC and
native MSVC builds pass; this is not a full native App or full-suite validation.

Remaining boundaries include foreign device callbacks, other IRQ producers,
post-DOS caller execution, all millisecond ticker side effects, and integration
with the live foreground/frame scheduler. No FPS constant is changed here.
