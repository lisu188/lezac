# Interruptible DOS Time

`InterruptibleDosTimeOperation` composes the recovered DOS GetTime service and
the full BIOS IRQ0 / LEZAC INT1C / CRT speaker operation. They share one external
memory bus, including BIOS `0040:006C`, the original stack, PSP saved stack and
sound globals. The DOS service samples that counter once. An IRQ in its DOS
overhead loop advances the same counter without changing the already sampled
time result.

Hardware delivery writes FLAGS, CS and IP in their original order and clears
IF/TF. The original BIOS wrapper and game ISR then execute instruction by
instruction, and their IRETs restore the interrupted DOS context. No reference
register, clock, PSP or stack output is copied into computed state. A snapshot
can suspend and restore either operation. Masked, nested and post-return timer
delivery is rejected before changing CPU or memory.

The input registers are the existing 16-bit projection with materialized flags,
not a complete 386 context. The caller supplies an eligible IRQ boundary; the
class does not recover PIC pending/in-service state, interrupt shadows, cycle
charges, timer phase or elapsed time inside the IRQ. Instruction work is not
elapsed time. The live App governor and startup-clock owner are not replaced by
this class yet.

## Original Evidence

The exact original executable is SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The pinned DOSBox profile and recovered routines are those of the DOS-time and
timer-IRQ changes. This integration retains both complete fixture contracts and
the live SoundEngine timer-instruction route.

The retained t196/r2 GetTime call 2 has 361 instructions and a returned state:
325 DOS instructions and 36 IRQ instructions. The previous DOS-only comparison
excluded the IRQ. The composed replay now executes every instruction and
compares all observed registers, defined flags, BIOS counter, PSP saved stack,
ordered port output and stack bytes whose initial inputs or computed writes are
known. No counter update is injected between states.

That older window did not observe the complete stack below entry SP, disk bytes
or sound globals. Its idle sound branch constrains the active byte to zero;
the disk bytes are explicitly scripted zero inputs, not claimed observations.
Unobserved stack contents are never read or compared as known data. This is not
full-memory natural IRQ proof.

Two fresh, silent, normal-startup captures each contain ten complete DOS calls.
They observe a fixed 128-byte stack, ten sound-global bytes, initial 780-byte bank
span, BIOS counter/motor/drive bytes, PSP, vectors and every instruction. Neither
contains a nested timer IRQ. They are full-memory non-interrupted controls, not
replacements for the interrupted window. A third fresh control capture is
retained locally and is not published in the frozen corpus.

Together the frozen corpus has 21 windows and 6,882 states. Continuous and
per-instruction restored execution compare 13,764 states. The 325 controlled
boundary tests additionally deliver IRQ0 before each possible DOS instruction,
check BIOS counter wrapping, motor/drive effects, one-time clock sampling and
work accounting. Wrapped-stack, repeated-IRQ, active-direct-sound and masked-IRQ
controls exercise the same composed operation. These controlled tests do not
establish the original natural IRQ schedule.

## Capture And Retention

`tools/dos_timer_probe/` extends the read-only DOS observer with fixed-stack,
sound and BIOS memory observations. It never writes guest registers or memory,
patches guest instructions, seeds a clock/RNG/heap or pauses the process.
The host DOS callback hooks are observation only. The configured host build
copies existing products and is not a clean reproducible ELF build.

All fourteen canonical assets are checked before output creation and again at
shutdown. Deleted, renamed and unreadable assets persist a failed report.
Default CI uses standard Python and C++23; the checker accepts only the exact
pinned frozen corpus, not arbitrary capture recipes. Full RAM and PNG captures
remain RAM-only under the repository disk restriction and are not published.

```sh
python3 -B tools/dos_timer_probe/build.py --source /dev/shm/lezac-work-oracle-t190/dosbox-0.74-3 --out /dev/shm/dos-timer-host
python3 -B tools/dos_timer_probe/capture.py --run r1 --repo "$PWD" --dosbox /dev/shm/dos-timer-host/dosbox-0.74-3/src/dosbox --out /dev/shm/dos-timer-original
```

## Remaining Work

A fresh natural interrupted DOS window with the complete observed memory is
still needed. Production App clock ownership, original PIC/CPU scheduling,
CRT/frame-work composition, pending keyboard IRQs, corrupted target execution,
synchronized frame streams, campaign/level-7 boss parity, physical audio
fidelity and owner visual acceptance remain unfinished. This change does not
claim whole-game completion or frame-perfect App parity.
