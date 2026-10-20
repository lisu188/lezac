# Complete Original Actor Passes

## Boundary And Ownership

FrameActorPassOperation enters the original caller at 1000:7EBB. It composes
the optional 432A boss-link update, every actual nonplayer CALL at 7EE1,
the real player CALLs at 7F59, complete ActorUpdateOperation calls and each
PlayerPostOperation continuation. It follows the real 8044 loop back to select
player two, then stops before the 804E transient-queue instruction.

The other outcomes stop before restart at 77DC, before the Pascal runtime-error
handler at 1920:00E2, or at an observed CPU divide fault before handler delivery.
No original instruction is skipped by a host gameplay replacement.

All phases borrow one TimerIrqBus and the caller's live SS. No data plane,
stack, damage mailbox, scratch global or actor array is reset at a handoff.
Completed passes preserve the entry SS/SP/BP. The serializable variant owns
CPU continuation and accounting metadata, not guest gameplay memory.
Aggregate counters span all phase changes: dispatches, timer work/deliveries,
actor/nonplayer/player calls and returns, and post-player calls/returns.

Restoration checks the child profile, original entry kind, caller SS/SP/BP,
phase/counter relationships, child accounting and terminal outcome. A caller
phase may hold only the actual caller or boss-link child, not an unrelated frame
prefix or actor prologue. A post-player phase must have Caller entry semantics,
not the standalone signed-division profile. Returned or contradictory boss
children cannot masquerade as running caller work. Masked, nested and terminal
IRQs are rejected by the active owner.

This boundary is not a complete frame or production-App integration. It begins
after the frame prefix and ends before transient processing.

## Original Corpus

Two independent final captures A and B execute unchanged relocated LEZAC.EXE
under Unicorn 2.1.4. Their compressed projections, manifests and checkpoint
catalogs are exactly byte-identical. All 16 canonical inputs, the executable
and 15 producer modules, are authenticated before and after capture, together
with the actual mapped native Unicorn library.

| Item | Value |
| --- | --- |
| Controlled complete-pass cases | 876 |
| Actor CALLs / actual returns | 3,398 / 3,370 |
| Nonplayer / player CALLs | 2,244 / 1,154 |
| Post-player calls / returns | 1,152 / 1,152 |
| Cases reaching both players | 540 |
| Boss-link calls / inactive-player 8044 skips | 36 / 460 |
| Life-loss paths | 106 |
| Queues / restart / runtime-error / divide-fault outcomes | 806 / 30 / 22 / 18 |
| Register states / ordered writes | 3,360,464 / 590,096 |
| VGA writes | 142,464 |
| Raw / compressed projection bytes | 35,707,847 / 8,758,898 |
| Raw SHA-256 | 799531ca906973fc9f0b619855e42898aa5eb876b4086641cc6b637eb63a40d3 |
| Compressed SHA-256 | 956e37149058c02aeb3519af0448e0ce5f906a08cdc8a3b52144596ea59e4307 |
| Manifest SHA-256 | 42e18b01ee7d869fa2e1115b3a1334b8602375e190edb2affea43d2ad94a904d |
| Checkpoint catalog SHA-256 | a71da337ca2a5851396c783a140885752b7b198ff469520fda77e3bbce82a4be |

Executable SHA-256:
7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec.
Mapped Unicorn library SHA-256:
ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c.
Final producer SHA-256:
8108d33959531548966ce532fd797dbbbcae9e03087aaf6c8845aca23c027c4d.

The matrix covers player-state pairs 0/1/2/255, zero through 30 nonplayers,
behavior values 0..6, expiry/compaction, all 32 control combinations in paired
and complementary player banks, score/sign/dirty boundaries, health pairs,
direction flags, animation copies, two stack depths, stack faults, waiting
counter wrap/restart and zero-period divide faults. Boss modes use the actual
original sine initializer at 2714..2767, with its own complete-memory observer
control; there is no host sine substitution. Its 768-byte output SHA-256 is
466aea5bff071d610e66710d74d2ddecc79853ece03a4ae038113e83609e72d8.

Both player records, their visual IDs 0/1, positions, glyph bytes, controls,
map and nonplayer records are controlled initial data. This is not a natural
level or input route. Initial differences are compacted before execution;
there is no seeding at an actor return, between players or between nonplayers.

The traced run records registers and ordered writes. Its independent control
has only address-filtered terminal hooks, plus the same divide-fault/I/O guards.
Every endpoint register/flag column and complete one-MiB memory agree. Ordered
writes reconstruct all changed memory, and all 43,552 relocated code bytes
remain unchanged. No instruction patches, call stubs, hardware I/O, delivered
IRQs or later-state injection occur in the baseline corpus. Divide faults are
observed, but their handlers are not executed.

The published fixture contains compact initial differences, delta register
traces and ordered writes, not full RAM dumps or screenshots. Bounded
decompression and SHA-256 authentication precede normal replay. Standalone C++
also pins exact MZ/projection lengths and FNV fingerprints, without claiming
cryptographic strength for FNV.

## Cross-Actor Flow

A separate read-only original probe checks six frozen cases against their exact
endpoint registers and reconstructed complete final memory. In case 744, initial
health is 100/100 and both damage mailboxes are zero. After the first and second
nonplayer returns the mailboxes are 1/1 then 2/2; the third return leaves 2/2.
Player one's body leaves 3/3, and its real 7F75 subtraction produces health 97.
Player two's body leaves 4/4, and its subtraction produces health 96.

Case 720 starts at health 1/100. The same pending damage makes player one's
health wrap to 254 and enter the actual 30A3 life-loss helper, restoring that
record to 100 before player two's body runs. Player two then reaches health 96.
The probe injects no state and matches each frozen full-memory endpoint. These
are controlled colocated-actor observations, not a natural-gameplay claim.
They demonstrate why per-actor mailbox resets or copied/reconciled data planes
would change this uninterrupted execution.

## Validation

GCC and native strict MSVC each pass 7,884 replays across dispatch budgets
1/17/4096 and copy limits 1/2/all, restoring snapshots after every grant. They
compare 10,432,263 register/control boundaries and 29,521,980 aggregate
dispatches, all ordered writes, complete final memory, terminal outcomes and
all six call/return counters. As in adjacent recovery tests, intermediate
arithmetic flag bits masked by 0x08D5 are excluded; other intermediate flags and
all endpoint flags compare.

Nineteen computed IRQ controls cover caller entry, boss work, nonplayer calls/
returns, both player CALLs/entries/returns, temporary life-map DS, the caller
loop and final queue branch. Three occur after one transfer of a partial
byte/word REP. Each executes 36 handler instructions, restores the CPU and
advances the BIOS tick from 100 to 101. All 684 handler instructions, restored
snapshots, aggregate accounting, ordered writes and complete-memory continuation
forks agree across grants. These controls are not an original IRQ schedule,
real work-clock coupling or physical-input proof.

Thirty-six invalid snapshot cases, two valid phase profiles, wrong entry,
masked IRQ, zero budget and two terminal controls pass. All 28 separately
compiled faults are detected. The mutation runner first authenticates the
frozen fixture and compiles/runs a positive unit/full-corpus baseline with the
same options. Every mutant must compile and fail through ordinary assertions.
The root/test and all core source hashes, original producer inputs and fixture
bytes remain protected throughout.

Strict GCC C++23 ASan/UBSan unit and full-corpus runs pass. Native MSVC
/std:c++latest /W4 /WX build, unit, full replay, eight CLI rejection controls,
two fixture-retention tests and Windows autocrlf cold checkout pass. The cold
checkout covers 29 families, 94 files and 29 CRLF negative controls. Native
executable SHA-256:
aeef994abc88bb73abe2177a565612ca0fa17433e32e43b3b934b74d26c0fa68.
After the C++-only checkpoint fix, the same 94 cold-checkout input files and
29 CRLF controls were reverified byte-for-byte against the retained Windows
run; a redundant second checkout was not generated.

All 35 final focused CTests pass, including adjacent actor/player/nonplayer,
frame-prefix caller, animation, boss, HUD and reward-storage checks. The first
batch's discovery-time missing frame-actor-entry executable was built and its
unit rerun; the complete fixed-source batch then passed in 161.90 seconds. The earlier
Not Run log is retained. Source guardrails pass 20 controls with 168 mapped
sources. No tests, timeouts or production gameplay behavior were weakened.

Fresh silent live-App captures include six two-player target-selection frames,
four level-7 frames through tick 90, and the controlled eight-tick boss physical
probe. The latter retains 48 physical links with no coordinate or animation
byte mismatches; its RGB SHA-256 is
15e9811c9084c5065530269e8b8772b4bbdd55fd7c50403972c0bf967cf53e89.
The split-screen checkpoint RGB SHA-256 is
d5378614fc5817c5ba7c823a92cd265b3b2f3413636ddcc28296d1e6e99afdba;
the level-7 tick-90 checkpoint is
d9e4cad6f07ebe380e156735d8f847ca0a2a830d6da488e7b9f8747f7708b556.
These are existing-App regression captures, not use of FrameActorPassOperation
or original/C++ pixel alignment. The retained original boss screenshot is from
October 8, at a different tick/camera.

Generated validation remains RAM-only under the user's disk-pressure exception.
Only audited redundant checkout replicas were removed; their staged files,
synthetic Git metadata, passing reports and all original captures remain.

## Checkpoint Scope Repair

Self-review before publication reproduced five accepted invalid states: caller
snapshots pointing at life-loss, post-player, score-draw and frame-prefix code,
plus a running boss-link child already at 1920:00E2. The focused probe reports
accepted=5/rejected=0 on the earlier header, and the permanent new regression
fails there with "Pass admitted invalid snapshot".

Caller checkpoints now require the actual caller code intervals, and a running
boss child cannot already be at the runtime-error boundary. The identical probe
then reports accepted=0/rejected=5. All 36 snapshot controls, 28 compiled faults,
35 focused CTests, native validation and strict ASan/UBSan replays pass on the
fixed source. Original producer, manifest and compressed projection bytes are
unchanged.

## Remaining Work

Compose the frame prefix, these actor passes, transient queues, frame completion
and shared frame/work clock, then integrate the recovered instruction owners
with production memory and the live App. Natural original/C++ routes, aligned
rendered frames, pixel timing, physical input and owner visual acceptance remain
separate obligations. Runtime-error and divide-fault handler presentation also
remains outside this boundary. This does not establish whole-frame or whole-game
fidelity. Fresh exact-head external review and hosted checks remain merge gates.
The separately reported running borrowed-SS finding on parent PR #456 must
also be fixed before integration; this layer's own matching-SS guards do not
dispose of that standalone ActorUpdate API finding.
