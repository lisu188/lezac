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

## Parent Integration Hold

The local integration preserves both published parents and incorporates the
ActorUpdate borrowed-SS fix 5375ce6 plus player-post integration 7bacbb5.
Original producer, manifest and compressed projection bytes are unchanged.
The full corpus passes in the Debug build, strict native MSVC and GCC
ASan/UBSan. The native integration run took 155.23 seconds, preserved every
protected core/fixture hash, and produced executable SHA-256
7125c5f7d4ed58e6806a863ba1e573f4eff2b47d10597cfed8568bce8d9d6889.

Optimized GCC replay is not consistently passing. The first authenticated
positive baseline failed at case 123, row 1021, with CX 0200 instead of 0000.
A six-run stress test of that unchanged binary passed five runs but failed
one with an invalid nested actor-entry ID-toggle profile. A later positive
baseline also failed a contact-profile ownership guard. A debugger run caught
the actor-entry exception inside the nested precontact registers visitor.
These failures remain unexplained; later successful runs do not clear them.
Failed reports, binary, stress logs and debugger evidence are retained in RAM.
This integration is not merge-ready. Draft publication is limited to obtaining
independent hosted validation and review; neither a later local pass nor green
hosted checks alone dispose of these unexplained failures.

The stronger ActorUpdate guard makes the outer child-caller-SS mutation
equivalent: both its positive baseline and mutated complete replay pass,
while malformed snapshots are still rejected by the child invariant. It has
been replaced with a timer data-ownership fault and two explicit interrupted
snapshot controls. The new unit passes 38 rejection/three phase controls;
the updated mutation run remains pending because its positive baseline
encountered the unstable profile failure above. No guest logic was changed.

Fresh review of player-post head 7bacbb5 separately reported P1 finding
discussion_r4331157814: standalone running/divide/IRQ checkpoints can retain
a foreign live SS. A focused probe confirms one foreign-stack write before
rejection. That parent finding must be repaired before this integration can
advance, independently of the optimized-replay investigation.

## Remaining Work

Compose the frame prefix, these actor passes, transient queues, frame completion
and shared frame/work clock, then integrate the recovered instruction owners
with production memory and the live App. Natural original/C++ routes, aligned
rendered frames, pixel timing, physical input and owner visual acceptance remain
separate obligations. Runtime-error and divide-fault handler presentation also
remains outside this boundary. This does not establish whole-frame or whole-game
fidelity. Fresh exact-head external review and hosted checks remain merge gates.
The ActorUpdate running borrowed-SS finding was fixed in 5375ce6 and received
a clean exact-head review. The optimized integration failures above remain
open; this layer's matching-SS guards do not dispose of a standalone parent's
malformed-checkpoint API finding. See the newer parent dispositions below.

## October 22 Integration

Parent #456 merged as 7dc743b, with a tree identical to its tested and reviewed
5375ce6 head. This branch preserves that history and player-post head abb3ca8.
The standalone player-post SS finding is fixed by unconditional live-stack
validation, including active IRQ checkpoints. Subsequent review findings about
RETF error classification and nested-return false completion are fixed in
f36a112 and abb3ca8. The latter retains all seven original-backed nested return
destinations, including the initializer's 06B6 return; an earlier candidate
omitting 06B6 failed the original corpus and its failed evidence is retained.
Player-post's current-head external review is clean; hosted checks are pending.
These parent fixes do not explain or clear the separate pass instability.

On this integrated source, the unit passes 38 snapshot rejection and three
positive phase controls. GCC Debug full replay, eight CLI rejection controls
and fixture-retention tests pass. Strict native MSVC /std:c++latest /W4 /WX /O2
build, unit and complete original replay also pass in 24.06 seconds, with every
protected core, original and fixture hash unchanged. Native executable SHA-256:
969b339400e1c7399a09c19b8c5b38a6224545616e5f8e1fe7e97285bee34b3c.
This native run did not regenerate CLI or cold-checkout evidence.

An additional bounded affinity diagnostic ran the retained previously failing
optimized binary once on each allowed CPU 0..7. All eight complete replays
passed and the executable, fixture, MZ and runtime-library hashes were
preserved. This is historical-binary diagnostic evidence, not current-source
validation or a diagnosis of the intermittent failure.

The updated 28-fault mutation set passes again with parent abb3ca8, after an
authenticated passing unit/full-corpus baseline. All ten focused CTests pass
in 400.31 seconds, including both parent units, the player-post mutation-runner
failure-contract checks and source guardrails. Earlier 4f19bc4 mutation evidence
is retained separately. The new strict GCC C++23 ASan/UBSan unit and complete
latest-source replay pass with leak detection and halt-on-UB enabled. This
remains a successful bounded run, not a diagnosis of the intermittent failures.

A fresh silent existing-App boss-fight sequence records six 320x200 frames
through tick 220. The tick-180 frame hash is 0x8640228849cc6fff. The sequence
uses a direct level-7 reset and a fixed random seed, then movement/bomb controls;
it is not a natural route from level 1, physical-input proof, use of this new
core operation or an aligned comparison with the retained original screenshot.
All generated validation remains RAM-only; no game uses audible output.

## October 23 Caller Restoration Review

The completed external review of cb633d68f24370b75307295fcc0b45e1cc62020a
reported two caller-restoration gaps. A caller with one balanced player return
but no player-post call could skip the mandatory continuation. Operand bytes
such as 7EBC were also accepted by the caller's interval check and failed only
when dispatched. An independent compiled probe accepts both on the reviewed
source and rejects both after these changes, without any constructor bus effects.

Caller snapshots now require playerCalls == postCalls, including terminal and
interrupted caller states, and exact membership in the 50 supported caller
instruction addresses. The unit covers all 117 operand bytes in the previously
accepted intervals, all 50 supported boundaries and four skipped-post states.
It rejects 160 malformed snapshots overall. A fixture-tool test mechanically
checks the address catalog against the owning FrameActorEntry switch. The
compiled fault set adds removal of the post-balance guard and regression to
the old interval test, bringing the set to 30 faults.

Fresh strict optimized GCC, native MSVC /std:c++latest /W4 /WX /O2 and
GCC ASan/UBSan builds pass the unit and complete 7,884-replay original corpus:
10,432,263 control/register comparisons and complete final-memory checks.
All 30 compiled faults are detected after an authenticated passing unit and
full-original baseline, including both new guard regressions. Three fixture
tool tests pass on Linux; the new catalog test also passes on Windows.
The source ownership guard and diff whitespace check pass. Protected core,
canonical MZ and original fixture hashes are unchanged by validation.
The CLI and full cold-checkout suites were not rerun for this fix because
local RAM headroom cannot safely retain another complete export batch.

The branch integrates merged player-post main b590e6f without changing any
original producer or fixture bytes. These restoration fixes do not diagnose
or clear the intermittent optimized replay failures described above. The PR
must remain draft and held until that separate finding is explained and fixed,
with fresh current-head validation and external review. Hosted Windows checks
on the reviewed head also report AST-compatibility and retained-output-reserve
failures in existing harnesses; these are not passing validation or waivers.

## October 23 Boss And Nonplayer Return Review

Review of df2a633b747855bd75b238eec8507fc145275d39 found two further malformed
continuations. The broad boss-link ranges admitted operand bytes 1000:432C
and 1920:04E0; both constructed successfully and failed only at dispatch.
Caller PCs 7EE4 and 7EE8 were also accepted without any nonplayer call having
returned. An independent compiled probe accepts all four before this fix and
rejects all four afterward, with no constructor bus effects.

Boss-link restoration now uses exact supported dispatch entries: 196 game
instructions, 26 directly owned library instructions and 220 delegated
FrameDisplay library instructions. E2 remains a separate runtime-error endpoint
and is still rejected while running. The new catalog check binds these sets
to the numeric labels of both instruction owners. It is a supported-entry
check, not authentication of arbitrary forged RAM histories or an original
IRQ schedule. No original instruction owner or fixture bytes change.

Caller states at 7EE4/7EE8 now require a completed nonplayer call in addition
to the existing balanced call/return constraints. Unit positives at those PCs
carry matching counters. Eight rejection controls cover missing calls and
completed-player-only substitutions, both with and without an active IRQ.
Two further controls mutate the foreground PC of actual interrupted boss-call
and library-call states. The unit rejects 6,420 malformed snapshots, retaining
all 50 caller addresses and 443 boss boundaries including the error endpoint.

All 33 compiled faults pass their authenticated positive-baseline gate and are
detected, including separate game/library catalog removals and the nonplayer
return guard removal. The existing running-boss-error guard fault remains
effective. Four fixture-tool tests pass on Linux; both catalog tests pass on
Windows. All eight CLI rejection controls pass on both platforms.

Fresh strict optimized GCC, native MSVC /std:c++latest /W4 /WX /O2 and
GCC ASan/UBSan builds pass the unit and complete 7,884-replay original corpus,
with 10,432,263 register/control comparisons and complete final-memory checks.
All protected source/original/fixture hashes remain unchanged during these
runs. Full cold-checkout validation was not regenerated for this guard-only
change; its fixture and attribute bytes are unchanged and hosted validation
remains required. The separate intermittent optimized replay hold remains open.

## October 23 Ordered Actor History Review

Review of 09cce3a1b07e11c92d068b066896f83141f40643 identified balanced but
unreachable histories: active boss links with completed actor calls, and
nonplayer-return PCs 7EE4/7EE8 with completed player/post calls. An independent
compiled probe accepts both reported cases and six related cases before the
fix, then rejects all eight afterward without constructor bus effects.

The boss phase now requires zero actor calls. Existing counter bounds and
balances consequently require zero actor returns, nonplayer/player calls and
post calls/returns too. Caller entry through 7EC5 cannot carry actor history;
the pre-player caller phase through 7F34 and the 77DC restart endpoint cannot
carry player history. An active nonplayer update likewise cannot contain a
completed player call. These checks do not authenticate arbitrary RAM or a
historical IRQ schedule, and no original instruction body or fixture changes.

The new tests add 1,335 boss-history controls across all 443 supported
boundaries, including the checked error endpoint and two actually interrupted
boss states; 153 caller-history controls include both nonplayer-return PCs,
ordinary/interrupted callers and the restart endpoint. One active-nonplayer
control brings the additional rejection count to 1,489 and the unit total to
7,909. Positive cases retain all 50 caller entries, all 443 boss boundaries,
the actual interrupted boss states, a completed player at 8044 and a restart
with completed nonplayer work. The latter guards against accidentally treating
77DC as a pre-loop PC merely because its numeric address is below 7EC5.

The compiled fault set contains four new guard-removal faults, for 37 total.
Fresh strict optimized GCC passes the unit and all 7,884 original replays,
including full final-memory checks and 10,432,263 register/control comparisons.
Four fixture-tool tests, the 20-case source guard and all six Python
compatibility tests pass. Native, sanitizer, mutation and current-head hosted
validation remain separate gates; these results do not clear the intermittent
optimized replay hold.

The completed follow-up runs detect all 37 compiled faults after a passing
authenticated unit/full-original baseline. Fresh strict native MSVC and
GCC ASan/UBSan builds also pass the expanded unit and all 7,884 original
replays; both instruction-catalog tests pass on Windows. Protected source,
canonical MZ and fixture hashes are preserved during validation. The focused
integration audit retains every existing CTest and adds exactly the six
actor-pass registrations, retaining both cold-checkout families. Full CLI and
cold-checkout artifact batches were not regenerated for this guard-only fix;
the unchanged fixture/attribute data and existing checks do not replace fresh
current-head hosted validation or clear the separate stability hold.

The branch integrates main 13a70b9, retaining both tail and actor-pass CMake,
source ownership and cold-checkout registrations. A merge of the published
09cce3a ancestry preserves its history without changing the integrated tree.
The old Windows job failed exactly the two boss AST checks and one retained
compression-reserve check addressed by merged PR #460; it is not a passing
check on this new tree and must be rerun.

## October 23 First-Player Entry Follow-Up

Review of 6a6221e2870a7f53a36136efee3618cc6df336b1 identified one further
boundary: 7F3A is reached only after the initial player-slot write at 7F34;
subsequent iterations return to 7F3C instead. A compiled reviewed-head probe
accepts a balanced completed-player history at 7F3A. Extending the zero-player
history guard through 7F3A rejects that state, while retaining the zero-history
positive at the same instruction entry. Four new ordinary/interrupted controls
raise caller-history controls to 157 and total rejected snapshots to 7,913.
The permanent 38th compiled fault restores the old 7F34 cutoff and is detected
by the unit, independently of complete guard removal.

Fresh strict optimized GCC, native MSVC and GCC ASan/UBSan builds pass the
expanded unit and all 7,884 original replays, with the same 10,432,263
register/control comparisons and full final-memory checks. All 38 compiled
faults are detected after the authenticated positive baseline. Four Linux
fixture tests, both Windows instruction catalogs and the 20-case source guard
pass. Validation preserves protected source, canonical MZ and fixture hashes.
Full CLI/cold-checkout artifact batches were not regenerated for this narrow
guard follow-up; fresh current-head hosted validation and review are required.

Separately, 15 complete historical-binary runs with pre-throw hardware
breakpoints and no preload hook did not reproduce the intermittent failure.
They do not clear the hold. A synthetic host-snapshot mutation calibrates the
intended pre-throw branch and its padding-masked comparison. Inspection of the
earlier retained core shows that executable code pages were omitted, so that
core cannot authenticate the live code bytes. A new bounded RAM-only capture
supplement is calibrated separately: 688,128 live executable bytes match the
unchanged historical ELF exactly under the synthetic fault. This is capture
mechanism validation, not reproduction or diagnosis of the historical failure.
Raw core, stack and executable-byte captures remain local and unpublished.

## October 23 Second-Player History Follow-Up

Review of 856dd2611fbd25466e091211ae1a4ad8be21afed found that 7F3C still
accepted two completed player/post calls. The original second-slot setup
through 7F59 can have at most one completed player call; the 804B backward
jump has the same limit. All states now cap total player calls at two.
Independent compiled probes reproduce acceptance of the reported 7F3C state,
the related 804B state and a three-player-call caller before this fix; all
three are rejected afterward without constructor bus effects.

Twenty-two ordinary/interrupted controls cover every supported setup PC and
804B, retaining matching one-call positives. Five controls check the total
cap in ordinary/interrupted callers, a terminal caller, an active actor and
an active post continuation. A completed-two-player terminal remains admitted.
The unit now rejects 7,940 malformed snapshots. Two new guard-removal faults
bring the compiled fault set to 40; all are detected after a passing
authenticated unit/full-original baseline.

No nonplayer-call cap is inferred from byte-sized DS:208D: ActorExpiry's
65C6 instruction rewinds DS:2082 after compaction. A bound needs a separate
proof accounting for callee writes and spawning, not just the caller's byte
comparison. The independently probed 256-call state remains admitted by this
structural validator; this is not evidence that its complete RAM history is
reachable. No original instruction body, producer or frozen fixture changes.

Fresh strict optimized GCC, native MSVC and GCC ASan/UBSan builds pass the
expanded unit and all 7,884 original replays, including 10,432,263 control/
register comparisons and complete final-memory checks. Four Linux fixture
tests, both Windows instruction catalogs, source guard and whitespace checks
pass. Protected inputs remain unchanged during validation. Full CLI and
cold-checkout artifact batches were not regenerated for this guard-only
follow-up; current-head hosted checks and review remain required.

The separate stability hold remains open. A parent-process hardware debugger
has been calibrated with a synthetic host-snapshot fault: it starts the
historical executable without a preload hook or GDB, stops before the throw,
captures registers/stack and byte-identical owned executable text, then hands
the stopped child to GDB as its same parent and resumes it through the expected
failure. This validates the new capture mechanism, not a historical failure
reproduction. All such diagnostic data stays local in RAM.

## October 25 Caller Stack And Timer Review

Review of e5c8caf66c0b1a28c3f3e37da011dadb86a7de49 found caller BP/SP
ownership and impossible aggregate timer histories. A separately compiled
probe accepts all six reported/related counterexamples on that head and
rejects all six after this fix, without constructor bus effects.

Caller restoration now checks foreground SS and BP against the owned caller
frame, including a caller suspended by an IRQ. SP must equal callerSp except
at the argument-push boundaries: 7EE0/7F58 require callerSp-2, and 7EE1/7F59
require callerSp-4, with 16-bit wrap. All 50 supported caller PCs have positive
ordinary/interrupted controls and BP, SS and both SP-direction rejection
controls. An additional active-IRQ SS control protects the outer stack guard;
15 positive cases cover SP values 0, 1 and 65535 across five caller entries.

Timer accounting now rejects work or an active IRQ without a delivery, and
deliveries exceeding instructions plus the single possible newly active IRQ.
Nine new controls cover callers, actor/post children, terminal snapshots,
immediate delivery and the uint64 limit. These are necessary ordering bounds,
not authentication of an arbitrary forged interrupt schedule or RAM history.
No original instruction owner, producer or frozen fixture bytes change.

The unit rejects 8,350 malformed snapshots, including 401 caller-stack and
nine timer-history controls. All 45 compiled faults are detected after the
authenticated passing unit/full-original baseline, including five new guard
removals. A preliminary mutation run was intentionally interrupted to add the
active-IRQ SS control; only the complete rerun is counted as passing.

Fresh strict optimized GCC, strict native MSVC /std:c++latest /W4 /WX /O2,
and GCC ASan/UBSan builds pass the unit and all 7,884 original replays across
876 cases: 10,432,263 register/control comparisons and complete final-memory
checks. All four fixture tests and eight CLI controls pass on both Linux and
Windows. The 20-case source guard passes. Fresh core.autocrlf=true cold
checkout validation covers all 30 frozen families and 98 files, including
30 CRLF negative controls; this is not an export-validation sweep of all
30 families. Protected inputs remain unchanged during validation.

The Release App and four focused core executables build successfully; all
nine selected CTests pass, including the CMake-owned complete actor-pass
original replay and fixture rejection tests. App compilation retains an
unrelated format-truncation warning in debugDebrisShatterPlayback; this is
not a warning-free App claim. A new silent boss_level7_fight sequence captures
six frames through tick 220. Tick 180 retains hash 0x8640228849cc6fff, with
the boss and one bomb visible. This is the existing seeded App path, not a
natural level-1 route, the new actor-pass integration or aligned original
pixel-parity evidence. No raw capture is added to this change.

The separately explained intermittent optimized replay hold remains open.
These fixes do not establish actual-App integration or full-frame fidelity.
Current-head hosted checks and completed external review remain required.

## October 25 Diagnostic Retention Boundary

The earlier WSL RAM filesystem did not survive until this session. Its raw
debugger traces, executable copies and core are no longer available locally;
earlier references above describe historical observations, not retained files
that can now be reinspected. No replacement full core or guest RAM dump was
generated. New diagnostics remain RAM-only and bounded to 16 MiB per campaign.

The historical executable was reconstructed using the same GCC 13.3.0 and
published source: e5c8caf as the base, with frame_actor_pass.hpp,
player_post.hpp and frame_actor_pass_test.cpp from eacb54ff8770f24e6f08ebfd7bd79ef43ee18636.
The 905,632-byte result has SHA-256
b1c719393f987cd2a98090055c8cc06d5d71589090599a36f32c4d2fd5da47f6,
matching the previously recorded historical ELF hash. The lost old file was
not available for a fresh direct byte comparison. The canonical original MZ
and regenerated 35,707,847-byte replay fixture retain their recorded hashes.

A software-breakpoint capture was calibrated using a deliberately mutated
host snapshot. Before reading code it removes the breakpoints, then verifies
all 688,128 owned executable bytes against the rebuilt ELF. The compact
capture includes registers, an 8 KiB stack slice, maps and owned code bytes,
not a full process core. Calibration is synthetic mechanism validation only.
Six subsequent complete historical-hash ELF replays hit no watched failure
branch and exited successfully; they neither reproduce nor explain the
intermittent failure and do not clear its hold. Raw diagnostics are unpublished.

Original code at 804E..806A confirms the remaining frame-loop bridge: 45FA
is called when word DS:2076 is nonzero or DS:207E is at least 200; 5102 is
called when word DS:2080 is nonzero. The actor pass stops before this bridge,
and FrameTail begins after it. This is a recorded composition gap, not newly
implemented or validated queue behavior.
