# DOS Time Observation

This recovery-only host observes the original executable. The production C++
operation is `src/core/dos_time.hpp`; the App does not call it yet.

## Scope

The selected profile is the configured 64-bit DOSBox 0.74-3 normal core, fixed
6000 cycles. It is not a generic DOS or physical BIOS specification. INT 21h
AH=2Ch reads the BIOS counter once, saves SS:SP-18 in PSP:002Eh, and returns
through CB_INT21's 320-iteration LOOP and IRET. Entry is the FE38 callback
instruction after STI; executing INT, STI and interrupt scheduling are outside
this operation. The six recovered instruction boundaries consume 325 normal-core
dispatches in total. Dispatch counts are not hardware cycles or milliseconds.

The counter is multiplied by five as an unsigned 32-bit value before widening
to 64-bit Bitu. Hundredths use the pinned 59659 divisor and integer truncation.
There is no extra 24-hour normalization. IRET restores the low flags mask and
the configured ID-toggle mask. Arithmetic flags are unclaimed before IRET:
the observer does not materialize DOSBox lazy flags.

## Reproduction

All outputs below must be new directories in `/dev/shm`. The source directory
must be the configured, source-pinned observation baseline. The build checks
seven input hashes, applies the tracked DOS callback patch, and preserves its
logs. It copies configured build products; this is not a clean reproducible ELF
build. No guest instruction patches or guest memory/register writes are added.

```sh
python3 -B tools/dos_time_probe/build.py --source /dev/shm/pinned-dosbox-source --out /dev/shm/dos-time-host
python3 -B tools/dos_time_probe/capture.py --run r3 --repo "$PWD" --dosbox /dev/shm/dos-time-host/dosbox-0.74-3/src/dosbox --out /dev/shm/dos-time-r3
python3 -S -B tools/check_dos_time_fixture.py --projection /dev/shm/dos-time-projection.bin
./build/lezac_dos_time_test /dev/shm/dos-time-projection.bin
```

Captures use a private Xvfb display, dummy SDL audio, disabled mixer/speaker/MIDI,
and ordinary one-player start keys. The complete command/environment/input
recipe is retained. Original assets are pinned before launch and checked again
at shutdown. Full RAM and PNG files remain local; the committed corpus contains
only compressed CPU/stack rows, their recipes and a manifest.

The frozen checker accepts only the exact pinned corpus. Its trace parser is
not a standalone validator for arbitrary capture recipes. A new corpus requires
review of its raw evidence, exact recipes, host/source pins and manifest update.

## Current Evidence

On 2026-10-16, two captures identified the original at MZ entry 0:7783, before
startup time calls. Each observed nine completed DOS time calls; the first eight
were traced instruction by instruction. An earlier capture identified the game
later at 0:01FC and contains four additional fully traced calls. The frozen
corpus therefore has 22 completed calls, 20 full windows and 6,520 DOS component
states including returns. Two replay modes (continuous and snapshot restoration
after every instruction) compare 13,040 native states, all registers, only
defined flags, PSP stack state and the known stack span. The bus asserts one
clock read, one PSP dword write, one stack word write and four stack word reads.
No expected register or owned-memory output is injected during replay.

One earlier call contains 36 timer-interrupt instructions and a BIOS counter
increment while the DOS return loop is suspended. Those raw rows remain in the
corpus. The C++ test replays only the 325 DOS instructions and checks that its
interface state still matches after the interruption. It does not execute the
IRQ instructions, reconstruct their memory writes, or reproduce their timing.
The time already sampled by DOS remains unchanged when the external BIOS input
advances. The initial 64-byte stack window covers all reads and writes of the
DOS component; only 58 bytes of that original window overlap the returned SP.
Unobserved stack-tail bytes are not claimed.

The optional exhaustive arithmetic check extracts the exact expression from
the hash-pinned DOS source and compiles it with only a memory-read shim:

```sh
python3 -B tools/dos_time_probe/exhaustive_clock.py --source /dev/shm/pinned-dosbox-source/src/dos/dos.cpp --out /dev/shm/dos-time-expression
```

All 4,294,967,296 uint32 inputs matched using GCC 13.3.0 on the current Linux
host (39.35 seconds for comparison). This is source-expression equivalence,
not a complete handler or guest CPU replay. Eight targeted mutants were rejected
by constexpr or native regressions. Default CI needs only C++23 and standard
Python; it does not rebuild DOSBox or run the exhaustive check.

Live App clock/IRQ ownership, work-budget scheduling, synchronized frame streams,
campaign and level-7 boss parity, audio fidelity and owner visual acceptance are
still separate unfinished gates.
