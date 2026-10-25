# Shared Transient Motion Instructions

## Recovered Operation

`TransientMotionOperation` executes original 1000:3EDA..3F26, the leaf
routine called by both spark and falling-debris updates in 45FA. It reads
velocity/phase bytes DS:78D2..78D5 and the live width word DS:C204,
updates the movement-offset word DS:2090 and returns through the actual
near stack return. There is no call stub, copied App movement model or
synthetic caller endpoint.

Each axis adds its signed byte velocity to the signed byte phase. The
original branches on signed overflow, not carry. On overflow it subtracts
128 from the wrapped phase and adds the signed axis step to DS:2090:
plus/minus one horizontally, plus/minus the live width word vertically.
Both additions to the offset wrap as 16-bit words. NEG of width 8000
therefore retains that word, including the original flags. AL/AH writes
preserve the other half of AX at every instruction boundary.

The operation has independent dispatch budgeting and serialization after
any supported foreground instruction. The existing BIOS/timer machinery
handles explicitly delivered interrupts. Restoration checks all 27 exact
foreground entries, the owned caller CS/DS/SS/SP/BP, foreground/outcome profile,
timer bindings and necessary counter ordering. A nonzero copied-byte
history is rejected because this helper has no copy operation.

The unit reaches every instruction and rejects 324 malformed snapshots,
plus four invalid public entries. It computes an IRQ at every one of the
27 entries, verifies exact foreground register restoration and one BIOS
clock increment, then compares serialized continuation under different
budgets. Nested and masked delivery are rejected. These are computed IRQ
controls, not observations of natural original interrupt timing.

## Exhaustive Original Evidence

The optional `transient_motion_oracle.py` executes unmodified original MZ
instructions using the pinned Unicorn 2.1.4 library. Its actual mapped
library SHA-256 and the canonical MZ are verified. One engine records
instruction/write hooks and the other runs without code/write hooks; no
observed result is fed into the unhooked engine. Both are checked against complete
expected 1 MiB memory reconstructed from initial seeds and ordered writes.
Their final fourteen registers must agree exactly.

The engines are reused to keep exhaustive generation bounded. Between
cases all previous seed bytes are restored from the immutable relocated
image before the new seeds are installed. Every possible helper write is
inside those seeded words/bytes. Hooked execution rejects any other write,
and complete final-memory equality independently checks both engines, so
unobserved state cannot accumulate between cases. No full RAM image is
written into the frozen fixture or failure report.

The 132,928 controlled cases include:

- 65,536 horizontal velocity/phase pairs, covering all two-byte inputs.
- 65,536 vertical velocity/phase pairs, likewise exhaustive.
- 1,568 width/phase/sign/offset edge cases across eight widths, including
  zero, 8000 and FFFF.
- 256 coupled-axis cases, retaining horizontal-then-vertical updates to
  the same offset word.
- 32 stack-wrap, direction-flag and SS-equals-DS cases.

Every case retains all flags immediately after each byte addition, the
final registers and every ordered write. All instruction/register/flag
rows are additionally retained for 2,367 dense cases. Unlike instruction
families containing undefined MUL flags, these dense traces compare all
flags without an arithmetic mask. The original executes 2,459,904
instructions and 299,264 ordered writes. No calls are stubbed, instructions
patched, interrupts injected or hardware I/O allowed during generation.

The compact raw projection is 11,677,916 bytes, SHA-256
b9677d1e8e656749eafe639914f2acd612cf31de1b48c71227907bc2f383e996.
The deterministic gzip is 2,055,550 bytes, SHA-256
cf38a63c8dd15fbe5a43f1e42e821120acb833371a51cf932a54e59ba6318065.
A second complete generation from freshly initialized engines produces
byte-identical manifest and compressed projection. The manifest pins all
producer dependencies and scope; the checker bounds reads/decompression,
rejects changed inputs and output aliases, and preserves failed reports.
The original MZ is also bound by exact bytes inside the replay format.

## Replay Validation

Strict optimized GCC C++23, native MSVC /std:c++latest /W4 /WX /O2, and
GCC ASan/UBSan pass the unit and complete corpus. Three dispatch budgets
produce 398,784 replays and 7,379,712 C++ instruction dispatches. Validation
compares 62,082 complete dense register/flag boundaries, 265,856 addition
flag checkpoints, every ordered write and all final memory for every replay.
Each consumed grant is followed by snapshot reconstruction.

Native Windows fixture tests pass with the hardlink case explicitly skipped
because the RAM checkout is reached through WSL UNC. Native-NTFS hardlink
coverage remains distinct from this result. No Windows filesystem support
claim is inferred from an unsupported local operation.

All fourteen compiled faults are detected after an authenticated passing
unit/full-original baseline, without changing protected inputs. They cover
both signed branch decisions, horizontal step and vertical width/sign,
overflow/correction paths, phase write destination, half-register retention,
auxiliary flags, caller SP, exact instruction boundaries, timer balance
and foreign copy history.

All eight focused CTests pass: five new registrations plus source guardrails,
Python compatibility and actual autocrlf cold checkout. This main-based
branch has 169 mapped source files and 30 frozen fixture families. The
separate removal family on PR #461 and actor-pass family on held PR #458
are not present on this branch; integration must retain them and rerun the
expanded cold-checkout check. Seven Linux fixture tests pass, including
the hardlink negative control.

## Remaining Scope

This closes one real dependency of the transient updater; it does not yet
compose 45FA, 5102, the complete frame loop or live App execution. The
original inputs are controlled states, not natural route captures. The
structural snapshot checks do not authenticate arbitrary fabricated histories
or original interrupt schedules. No visual, physical-input or whole-game
fidelity claim is made. The separate intermittent actor-pass replay hold
on PR #458 remains unresolved.

Validation remains RAM-only under the disk-pressure exception and every
launched runtime uses dummy audio. This non-rendering change generates no
full RAM/core dumps or new screenshots.
