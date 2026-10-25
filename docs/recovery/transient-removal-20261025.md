# Transient Record Removal Instructions

## Scope

`TransientRemovalOperation` recovers the original near-call helpers at
1000:452A (spark removal) and 1000:458D (falling-debris removal). These are
dependencies of the still-uncomposed 45FA updater between the actor-pass
804E boundary and the frame tail at 806A. They do not replace the App's
typed queue models and are not yet called by its live gameplay loop.

Both operations execute the original prologue, Pascal stack-space check,
physical REP MOVSB compaction and RET 4. Spark removal additionally shifts
the one-byte metadata bank at DS:78D6 and decrements DS:2076. Debris removal
conditionally decrements the caller's loop word through the actual SS:DI
parent-frame argument, then decrements DS:207E. No typed-vector erasure,
range clamp or synthetic return substitutes for the original instructions.

The record base comes from live DS:207C, each record occupies 11 bytes, and
copy direction follows DF. The original count decrement is retained even
when empty/out-of-range controlled inputs take the no-copy branch. In
particular, backward copies can overwrite the queue's own count; three
controlled cases execute a long subsequent metadata loop. Those outcomes
are preserved rather than rejected as inconvenient inputs.

## Resumption And Ownership

Dispatch and copy budgets are separate. A zero copy grant keeps the REP PC,
CX and memory unchanged; an excessive grant is rejected before writes.
Partial copies preserve SI, DI and CX for the next grant or timer delivery.
The established timer/BIOS machinery is borrowed without executing an actor
tail. The operation stops after the actual near return or at the original
runtime-error endpoint 1920:00E2, before error presentation.

Restoration validates the removal kind, exact supported foreground/library
instruction entries, DS/SS ownership, instruction-specific caller SP/BP,
timer ownership and necessary instruction/delivery bounds. Operand bytes
and cross-routine continuations are rejected. These structural invariants
do not authenticate arbitrary forged histories or an original IRQ schedule.

The unit checks 111 reached boundaries and rejects 1,110 malformed
snapshots. Ten computed IRQ checks cover both entries, far-call boundaries,
the shared stack checker, both leave instructions and both REP loops. The
latter are interrupted after exactly one byte. IRQ completion restores the
entire foreground register state and advances the BIOS clock once; alternate
dispatch budgets and serialized restoration then yield identical snapshots,
ordered writes and memory. These are computed IRQ controls, not recorded
natural interrupt timings.

## Original Oracle

The optional `tools/transient_removal_oracle.py` executes the unmodified
canonical MZ in Unicorn 2.1.4. It verifies the actual loaded library mapping
and SHA-256, original executable SHA-256 and unchanged code bytes. No
original calls are stubbed, no instructions patched, and no hardware I/O
or interrupts are allowed in the frozen original cases. All initial states
are explicit controlled inputs, not natural gameplay captures.

The 317 cases comprise 172 count/slot/direction/base combinations, 40
stack-floor/wrap/SS-alias cases and 105 caller-cursor cases. There are 305
normal returns and 12 original stack-error endpoints. Hooked and unhooked
executions agree on all fourteen registers and all 1 MiB of final memory.
Every observed write is ordered and reconstructs the entire final image.
The projection contains sparse input patches, register traces and writes,
not full guest RAM images. It also binds the canonical MZ by exact bytes.

The oracle observes 817,751 register states and 243,349 ordered writes,
covering 101 original instruction entries. Three cases exceeding 10,000
trace states retain entry/endpoint register states instead of all intermediate
rows; their complete ordered writes and final memory remain checked. All
other cases retain complete instruction-register traces. Arithmetic flags
are masked only during intermediate trace comparison; every endpoint flag
is compared exactly. This is not a claim of complete defined/undefined flag
authentication at every intermediate instruction.

The raw compact projection is 4,787,623 bytes, SHA-256
97fe6ba31431bf45ffffc3e8080fb34d4898a67157a092804b45ee15cdbb56c0.
Its deterministic gzip is 730,419 bytes, SHA-256
16097d94fa9ed20b69dbb47c533880d4511ee02a7ac21fe103aaeeab92f7f8f2.
The authenticated manifest pins every producer dependency and the declared
proof domain. Export failures preserve a failed report and existing output;
protected paths, hardlink aliases and report/export overlap are rejected.
The fixture family has byte-preserving Git attributes and participates in
the real autocrlf-enabled cold-checkout regression.

A second complete generation from fresh engines produces byte-identical
manifest and compressed projection files. The first attempt had exhausted
its 200,000-instruction allowance on the backward-copy/count-alias case;
that failure is retained separately. The complete producer uses a bounded
400,000-instruction allowance and does not omit that case.

## Validation

Strict optimized GCC C++23, native MSVC /std:c++latest /W4 /WX /O2, and GCC
ASan/UBSan pass the unit and all 2,853 original replays: three dispatch
budgets by three copy grants per case. They compare 136,490 selected
register/control boundaries, execute 7,111,917 C++ dispatches, and match
every original write and complete final memory. Each consumed grant ends
with snapshot reconstruction, including returned/error states.

All twelve compiled faults are detected after an authenticated passing unit
and original baseline. Faults cover record width, DF, missing copy writes,
metadata destination, both counts, parent-cursor update/condition, RET
cleanup, caller-frame ownership, exact instruction boundaries and timer
counter balance. Production sources and authenticated inputs are preserved.

Seven fixture-tool tests pass on Linux. Native Windows passes the same
checks with its hardlink test explicitly skipped because the RAM checkout
is accessed through WSL UNC, which does not support hardlink creation.
The Linux hardlink negative control passes; native-NTFS hosted validation
remains distinct from this local Windows result.

All eight selected CTests pass: the five new unit/original/fixture/mutation
registrations, actual cold checkout, source guardrails and Python compatibility.
The source inventory has 169 mapped files. The cold checkout covers all 30
families present on this main-based branch; the separate actor-pass family
on held PR #458 is not part of this branch or this count. Its future merge
must retain both families and rerun the expanded check.

All generated validation remains RAM-only under the existing disk-pressure
exception. Games and tests use dummy audio. No full RAM/core dumps or new
screenshots are generated by this non-rendering operation. The separate
intermittent actor-pass replay hold in PR #458 is neither explained nor
cleared by this work. Full 45FA/5102 instruction composition, actual-App
integration, natural routes and complete frame fidelity remain open.
