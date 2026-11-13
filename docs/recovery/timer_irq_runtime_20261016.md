# Timer IRQ Runtime

This change reconstructs the complete original INT1C routine, its real CRT
Sound/NoSound calls and the pinned DOSBox BIOS IRQ0 wrapper. Live SoundEngine
callbacks now execute the recovered INT1C instructions against the engine's
canonical latch and byte counters. Host-time scheduling remains unchanged.

## Original Scope

The original executable is SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
INT1C is game CS:0FBE..1090 (211 bytes), including prologue, locals, bank and
direct branches, epilogue and IRET. CRT Sound/NoSound are CS+084A:02C9..02FC.
The DOSBox 0.74-3 profile uses F000:FEA5..FEB6 for IRQ0. Its host callback
increments the 32-bit BIOS counter, decrements a nonzero floppy motor timer and
clears the low running-drive nibble without changing guest flags.

`TimerIrqOperation` advances normal-core instruction dispatches. It preserves
stack and memory access order, unsigned comparisons, byte counter wrapping,
defined arithmetic flags, real far calls, port commands and IRET masks. The
caller owns memory, device inputs, materialized entry flags, hardware interrupt
delivery and any cycle/PIC schedule. Unknown vectors or instructions fail
explicitly. This is a finite recovered routine, not a general x86 emulator.
Registers are the game's 16-bit projection plus defined EFLAGS bits, not a
complete 386 CPU context.

## Runtime Ownership

`SoundEngine::advanceSoundInterruptWorkOrdered()` supplies a private register
and stack context and maps the original data accesses directly onto the existing
latch/counter owner. It does not copy those outputs into a second persistent
guest-state mirror. Sound-bank reads use the existing payload and supported
extent. The pre-existing unsupported-bank exception boundary is retained;
unknown original allocator bytes are not synthesized.

The ordinary clocked playback path calls this method. The existing semantic
transition method remains an independent regression reference. Tone commands
and following NoSound commands remain ordered in the returned action. The
existing PCM/divisor application and speaker phase behavior remain unchanged.

Work counters count INT1C and CRT instructions only, not the BIOS wrapper,
hardware delivery or I/O cycle charges. An idle INT1C uses 24 dispatches. Idle
catch-up accounts that exact work analytically when the existing host-time
fast path skips inactive callbacks. The adapter derives the low speaker-enable
bits from existing speaker state; it does not model the live port-61 timer bit
or elapsed time inside an IRQ. Its private register/stack addresses are not a
claim about the App's original guest CPU context.

## Verification

The unchanged executable was run under Unicorn 2.1.4 with explicit controlled
register, memory and device inputs. No original calls were stubbed. All 130
shipped bank entries, direct/terminal sweeps, gate/period wrapping and six port
states produced 164 cases and 10,545 snapshots across all 98 INT1C/CRT instruction
boundaries. Continuous and restored native execution compare 21,090 states,
ordered byte writes, observed data/bank reads and ordered I/O.

A global Unicorn memory-read hook alters far returns in this installed version.
The failing attempt is retained locally. Restricting read hooks away from the
control stack produces identical registers, flags, stack, globals, writes and
I/O to a separate no-read-hook run. Control-stack reads are therefore not claimed
as observed bus events; stack contents and writes are compared at every boundary.

Two fresh, silent DOSBox captures use normal one-player startup. One retains the
idle route; the other adds ordinary `n` fire and `x` movement holds. No game,
clock, RNG or heap state is seeded, no process memory is written and no guest
instruction is patched. Their 24 complete IRQ windows contain 1,434 states;
native continuous/restored execution compares 2,868 states, the full observed
128-byte stack span, globals, BIOS bytes and ordered port commands. Port inputs
are taken from the original post-IN register value, not from expected outputs.
The observer retains CPU-cycle counters but native replay does not model their
schedule. Hardware delivery is already complete at each captured entry.

An early natural IRQ occurs before sound-bank initialization. Its observed
uninitialized bank bytes are preserved, including aliases with low memory.
They are not replaced with canonical bank data. Later active IRQs verify the
canonical bank payload. This startup ordering remains relevant to clock recovery.

The SoundEngine adapter additionally compares 13,858 cases against the existing
recovered transition, including every direct cursor and bank counter boundaries,
plus unsupported-bank failure state, live routing and analytical idle work.
The existing full transition matrix, PCM tests and actual-App clocked playback
checks remain required. All launches use dummy audio.

Default CI needs only C++23 and standard Python. Frozen CPU/stack observations
and exact recipes are published; full RAM and PNG captures stay local. The
fixture checkers accept only their pinned corpora, not arbitrary capture recipes.

## Reproduction

The configured observation baseline and optional Unicorn SDK already exist in
the current RAM workspace. No dependencies were installed for this change.
All output arguments below must name fresh RAM directories.

```sh
PYTHONPATH=/dev/shm/lezac-unicorn-sdk-t191/sdk python3 -B tools/capture_original_timer_irq.py --out /dev/shm/timer-original
PYTHONPATH=/dev/shm/lezac-unicorn-sdk-t191/sdk python3 -B tools/capture_original_timer_irq.py --memory-reads none --out /dev/shm/timer-original-control
python3 -B tools/timer_irq_probe/build.py --source /dev/shm/lezac-work-oracle-t190/dosbox-0.74-3 --out /dev/shm/timer-host
python3 -B tools/timer_irq_probe/capture.py --run r4 --route idle --repo "$PWD" --dosbox /dev/shm/timer-host/dosbox-0.74-3/src/dosbox --out /dev/shm/timer-natural-idle
python3 -B tools/timer_irq_probe/capture.py --run r5 --route fire --repo "$PWD" --dosbox /dev/shm/timer-host/dosbox-0.74-3/src/dosbox --out /dev/shm/timer-natural-fire
```

The host build pins nine baseline files and replaces only the existing normal
core's read-only observer header. Configured build products are copied; this is
not a clean reproducible ELF build. Canonical original assets are pinned before
launch and checked again at shutdown. Actual producer finalizers are tested for
deleted/unreadable assets, absent/incomplete traces and nonzero child exits.

## Unfinished Gates

BIOS/DOS clock ownership, CRT and complete frame-work scheduling, pending keyboard
IRQs, corrupted target execution, synchronized frame streams, campaign and
level-7 boss parity, physical audio fidelity and owner visual acceptance remain
unfinished. The live governor still uses host time. This change does not claim
whole-game completion, natural clock equivalence or frame-perfect App parity.
