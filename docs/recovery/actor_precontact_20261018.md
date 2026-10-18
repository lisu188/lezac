# Actor Precontact And Continuous Frame Entry

## Recovered Execution

`ActorPrecontactOperation` recovers original `1000:615A..654E`, together with
the complete nested helpers `5872..5998` and `5A75..5AFC`. It preserves the live
actor frame, far-record pointer, parent-frame static link, register set and bus.
`FrameActorPrecontactOperation` composes it directly after the existing prefix,
boss links, caller selection and actor animation prologue. No memory/register
state is injected at a stage boundary.

The block copies the selected player's control context, reads coordinates and
velocities, subtracts the signed hotspot, prepares per-player target deltas,
applies boss link serials, handles hit/pickup contact and selects the original
Manhattan-distance target. It preserves original signed/unsigned arithmetic,
16-bit wrapping and tie behavior, including the signed absolute-value overflow
at -32768. It does not replace these with host-distance calculations.

The link helper retains the strict serial `> 128` inversion boundary, ordinary
link damping, locked-link coordinate replacement and parent-stack writes.
Pickup contact uses the real nested sprite-descriptor helper, original LCG
`Random(3)` instructions and original software LongInt multiplication. Both
players can traverse the same cached-kind contact path; there is no invented
single-claim rule in this operation.

`654E` is an explicit live-stack handoff before the next behavior gate. Actor
return, contact scanner, tile cache, subsequent behavior and post-actor frame
work are not executed by this change. The full-prefix `7903` constructor is
preserved, but tested here only for construction and zero-budget behavior.

## Original Corpus

Two independent final captures (`t241-b` and `t241-c`) are byte-identical.
Unchanged, structurally relocated `LEZAC.EXE` executes under pinned Unicorn
2.1.4. The actual mapped library, all three canonical assets and seven producer
sources are authenticated before and after generation. The sine table is
freshly created by original startup instructions, not host trigonometry.

| Item | Result |
| --- | --- |
| Total controlled cases | 3,158 |
| Continuous post-render prefix entries at 7A57 | 238 |
| Frame actor-caller entries at 7EBB | 796 |
| Direct actor entries at 6053, including the real prologue | 2,124 |
| Register states, including endpoints | 10,227,850 |
| Ordered writes | 1,421,524 |
| New game/helper instructions reached | All 505 |
| Original code bytes verified unchanged | 43,552 |
| Projection bytes | 357,410,634 |
| Compressed projection bytes | 19,678,832 |

All 14 endpoint registers/flags and complete 1 MiB memory agree between observed
and unobserved execution. Ordered writes independently reconstruct full final
memory. There are zero instruction patches, call stubs, delivered interrupts
or hardware I/O in these captures.

The final outcomes are 2,946 handoffs at `654E`, 107 transient-queue handoffs,
75 restarts, two end-run UI handoffs and 28 original runtime errors. The raw
profiles cover all behavior/kind/hotspot/serial byte values, both player states
and held-pickup gates, contact/tie boundaries, extreme signed coordinates and
velocities, link modes, far records, offset wrap, visual aliases and stack
failures. These include malformed raw states, not only naturally reachable play.

SHA-256 fingerprints:

- Manifest: `9fb4c12ac550653ac03a9aabc1bcdb0a943a8c9aa35826ba0359a1ea05619e60`
- Compressed projection: `f4abb0ee4f3a8d2f4649557796007f6c12826c32a59cacefa6bc2107e2890de8`
- Expanded projection: `9f2559365f9bdf107c18c879bbf45d748fa7f28d9071837faa999402f48a1525`

### Failed Initial Capture

Attempt `t241-a` reached case 3144, then rejected execution at `0000:645C`.
Its direct post-prologue setup admitted a low, already-wrapped stack without
executing the actor's entry stack check. The failed metadata and producer copy
are retained in RAM. The correction starts all the same 2,124 direct profiles
at the real `6053` entry, with caller arguments and the real prologue/stack probe.
No profiles were removed and no foreign-code guard was relaxed. The two final
captures use that stronger setup and retain the original runtime-error outcomes.

## C++ Comparison

All nine instruction/string grant combinations (1/17/4096 instructions and
1/2/65535 transfer bytes) pass, with snapshot reconstruction after every grant.
There are 28,422 replays, 32,378,298 register/control comparisons and 91,599,084
dispatched instructions. Every ordered write, complete final memory and all
endpoint flags agree. Intermediate arithmetic flags are excluded from trace
comparison; control flags are checked and the grant-1 lane visits every modeled
boundary. Zero-budget and finished calls are inert.

Strict GCC C++23 (`-Wall -Wextra -Werror -pedantic`) and native MSVC C++ latest
(`/W4 /WX /O2`) pass the complete corpus. Entry ownership, masked IRQ delivery
and full-prefix zero-budget construction are separately checked.

The complete ASan/UBSan replay also passes. Ten compiled faults are detected:
wrong player controls, unsigned hotspot, wrong contact boundary, wrong target
tie, wrong inverse-link sign, wrong serial boundary, ignored locked-link mode,
skipped pickup RNG, wrong nested-helper return and lost IRQ flags. The original
production/test source bytes remain unchanged during these controls.

All 26 tests in the focused entry/prefix/link/animation/fixture/source-guardrail
CTest batch pass. Fixture damage/missing-input/alias/retention controls also pass
under native Windows Python. Native Git cold checkout preserves all 57 files
across 17 families and detects all 17 CRLF controls.

## Computed IRQ Scope

Fourteen computed timer checks cover prefix, links, caller, prologue, precontact,
both nested helpers and RNG. They require exact immediate register restoration,
36 timer instructions, one delivery, BDA tick 100 -> 101 and unchanged physical
actors/far actors/VGA during the handler. Nested and finished delivery is rejected.
From the resulting post-IRQ state, grant-1 and grant-17/snapshot continuation agree
over complete snapshots, ordered writes and all 1 MiB memory.

One selected interrupt changes the later register endpoint relative to the
no-interrupt original fixture. The initial neutral-endpoint assertion rejected
this case. The actor leaves inactive-player distance Y locals uninitialized;
an earlier IRQ can change their backing stack bytes before the prologue reserves
the frame. Later code reads them. The correct context check is at IRQ return,
not an assumption that all subsequent stack-dependent results are neutral.
This sensitivity is retained and counted as `irq_register_sensitive=1`.

A separate diagnostic binds the effect to case 6, with both player states zero
and future actor BP `3FDC`. At the `6053` IRQ boundary, stack words `SS:3FD6`
and `SS:3FD2` change from `9073`/`1CFF` to `001D`/`1AA2`, matching the BIOS
wrapper's saved AX/DS locations. Immediate CPU context is restored exactly.
Later AX/CX are `178D`/`3212` rather than the no-IRQ `1CFF`/`346F`.
The original inactive-player branches at `6310`/`634B` initialize only X distance;
the later distance comparison reads the untouched Y words. These stack bytes
therefore cannot be treated as disposable padding in full-frame IRQ work.

These checks exercise computed context/restoration and resumability. They are
not a new independent original-CPU IRQ-injection corpus, natural interrupt
schedule, work-clock calibration or real-time/full-frame timing proof. The
unchanged-original corpus above delivers no interrupts.

## Remaining Boundary

The production App does not yet consume this composed CPU operation. There is
no new natural DOSBox route, visible runtime, physical input, full raw frame,
whole-game parity, endurance or release acceptance claim. Only compressed
projections and compact metadata are published, not full RAM dumps or screenshots.
All generated local artifacts remain RAM-only while C: exceeds the disk reserve.

The next execution target is the behavior gate at `654E`, its `5CB0` contact
scanner path and the following tile-cache/behavior branches, preserving this
same caller-owned frame and bus.
