# Software Real48 Frame Display Recovery

This stage recovers the next original block after the elapsed-time store:
game:7966..799A, including its software Real48 calls. The live App loop and
gameplay remain unchanged. Full frame scheduling, foreign device callbacks,
wall-clock fidelity and synchronized original/port frames remain unproved.

## Original Calculation And Execution

The original converts unsigned words DS:78C6 and DS:78C8 to software Real48,
divides the second by the first, multiplies by the exact Real48 constant 100,
truncates to a signed 32-bit integer, and stores its low byte at DS:79B5.
This is not replaced with host floating-point arithmetic or a final-value-only
ratio. The operation retains every executed instruction, registers, near/far
calls, the control stack, branches and materialized CPU flags.

The recovered entry points in the library segment, game+0920, are 0F0F
(integer conversion), 0F01 (division), 0EFB (multiply), and 0F13 (truncation).
The multiplication covers the caller's fixed exact-100 operand, not arbitrary
Real48 products. The generic multiply branch is intentionally unrecovered and
rejected if reached. A zero denominator follows the actual original branch to
runtime error code 200 and stops before the error-reporting subsystem at
library:00E2. This phase does not claim to translate that subsystem.

`FramePacingCalculationOperation` composes the already-recovered DOS service,
elapsed store and new display calculation from computed state on one memory
bus. It does not reopen or reseed a completed preceding phase. PIC eligibility
remains independent; timer IRQs execute their original recovered instructions.

## Controlled Original Evidence

Unicorn 2.1.4 executes unchanged original instructions for 256 boundary input
pairs. The corrected corpus contains 148357 states, 29..743 instructions per
case, and sixteen original zero-denominator error handoffs. C++ passes 296714
state comparisons across uninterrupted and per-instruction snapshot/restore
modes, including all registers, architecturally defined flags, the complete
fixed 128-byte stack window, four operand bytes and the stored display byte.

Every unsigned 16-bit numerator is also executed for denominators 1, 66 and
65535: 196608 original endpoints. C++ matches complete final registers and
flags, stack and display memory. Denominator 66 is observed in the natural
checkpoints of this profile. These seeded cases do not claim natural gameplay
or exhaustive coverage of all 2^32 numerator/denominator pairs.

Pinned DOSBox materializes shift AF as one and explicitly sets MUL ZF while
preserving materialized SF/PF/AF. These otherwise undefined details are encoded
from the pinned source. Unicorn intermediate comparisons exclude undefined
bits; final endpoint flags are compared in full. No original calls inside the
declared phase are stubbed, and no original instructions are patched.

Two observer hazards were independently isolated and retained as diagnostics:

- A global Unicorn memory-read hook alters far returns. No-read-hook and
  write-only controls agree on the complete 653-instruction nonzero-ratio case.
- Adding/removing instruction hooks between cases leaves cached hook-free
  translations. The superseded corpus reported zero-instruction cases and is
  not accepted for instruction-level validation. The corrected producer keeps
  an observer permanently installed on one engine and uses a separate never-
  observed engine. Every detailed trace is nonempty, begins at game:7966, and
  agrees with its independent unobserved endpoint. Exhaustive endpoint hashes
  are unchanged across this correction.

## Interrupts And Regression Coverage

All 654 boundaries of the 653-instruction nonzero-ratio case are tested with a
real recovered timer IRQ, including after the store before unrecovered feedback.
Registers and output memory match the uninterrupted result; BIOS tick, motor
and drive effects are retained, the handler executes 36 instructions, and all
per-instruction snapshots restore. Nested and masked interrupts are rejected.

The entire DOS-to-display composition also passes all 1008 instruction boundaries
of a 1007-instruction nonzero-ratio case with the recovered IRQ executed. The
BIOS clock is sampled once: only an IRQ before the DOS callback changes the
sampled time. Registers, elapsed/display memory, BIOS and PSP effects, work
accounting and per-instruction snapshot restore are checked end to end.

GCC C++23 and native Windows MSVC pass these boundary tests, the detailed corpus,
all exhaustive endpoints, four oracle-fixture tests, six natural-control fixture
tests and five route-policy tests. Ten new focused CTests pass. The existing five
clock CTests also pass after sharing the
coupled replay harness with the composed operation. The earlier 1492 natural
elapsed comparisons and 6750 controlled elapsed comparisons remain passing.

Six isolated faults are detected: corrupt far-call context, missing division
quotient carry, missing Real48 rounding, wrong display store, corrupt IRQ restore,
and replacement of a computed phase-handoff register. Two earlier SBB-to-SUB
mutations are retained as equivalent in this unsigned-word domain, not counted
as detected faults: the lower mantissa/remainder words and incoming borrows are
zero. Source guardrails pass nineteen controls with 118 mapped sources.

## Natural Capture Status

The first silent read-only run timed out after its 600-second search without
the interrupted-window target. It nevertheless supplies a complete call-6
control through game:799A: 442 states, comprising 325 DOS instructions, 29 elapsed
instructions, 87 software-display instructions and the terminal state. The
composed C++ operation and independent PIC clock pass all 884 comparisons on
GCC and native MSVC. No IRQ is observed or predicted in that control, and its
capture status remains failed with `complete_target_capture_claim=false`.

All eight RAM/PNG checkpoints and 43552 relocated code bytes per checkpoint
were independently verified. Raw RGB/RAM/CPU samples are not atomic. The exact
terminal trace hash is
`6b43591e3be9c064ff94a2918738784429f755336f88195a7d621fd499ea9a10`.
The separate second run also reached its 600-second bound without the target,
exited normally and retained its terminal trace. Its call-6 control likewise has
442 states and no IRQ. The two controls pass 1768 coupled comparisons on GCC and
native MSVC. All sixteen RAM/PNG checkpoints and original relocated code bytes
were independently verified. The second terminal trace hash is
`4697ea8c9f1ce525ee9b52ee35914dad906e97149064773e0b2269671243e9ab`.
Both failed targets remain failed in the frozen recipes; tests reject attempts
to promote their status, passed flag or target-completed flag. The frozen
checker authenticates the exact trace/recipe identities and all capture, route,
contract and observer sources. Frozen CI reports zero raw RAM files verified.

Thus a naturally interrupted complete DOS-to-display window is still missing.
Controlled IRQ coverage and earlier interrupted DOS-to-elapsed captures do not
fill that evidence gap. No original RAM or PNG payloads are published; only
compact traces, controlled oracle projections and exact recipes are retained
as repository fixtures.

The observation host reuses configured DOSBox 0.74-3 products, with normal core,
fixed 6000 cycles and all sound devices disabled. Its SHA-256 is
`794ba39dd57a0358049cd980c172ec5e91e8a921a114711ecd2e16525f77b0d1`.
The capture binds all four observer source hashes, records every ordinary input,
and performs no guest writes, process pauses, instruction patches or clock/RNG/
heap/gameplay seeding. Local outputs and failed attempts remain RAM-only under
the user's disk-pressure exception. Full local App/suite validation is not
claimed; current-head external review and fresh full CI remain merge gates.
