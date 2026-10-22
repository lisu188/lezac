# Original Player Post-Return Work

## Scope

PlayerPostOperation recovers the actual player-return continuation at 1000:7F5C
through the boundary before 8044. It executes health subtraction and mirroring,
the 568A health bar, 30A3 life-loss helper, 11B0 score formatter, 1287 rolling
digits, 1239 score drawing, and their real nested calls. Existing sound,
animation, stack-check and font-copy operations execute their original
instructions on the same TimerIrqBus and SS; they are not call stubs.

The separate ScoreDivide entry executes the signed 32-bit Pascal RTL helper
1920:0945..09B0, including its 33-step RCL/subtract loop, sign corrections,
stacked flags, actual far return and zero-divisor runtime-error path. It is not
replaced by host division. RETF completion takes precedence over a return IP of
8044; that address is also a legitimate standalone-helper return.

Caller completion preserves entry SS/SP/BP. Standalone division restores BP/SS
and advances SP by four. Runtime errors stop before 1920:00E2. CPU checkpoints
own continuation metadata only, with no private guest stack, RAM reconciliation
or later-state injection. Only the actual 30D0..30D8 map scan may retain a
temporary non-DGROUP DS. Nested, masked and terminal IRQ delivery is rejected.

The original's health arithmetic wraps at one byte. Values above 200 trigger
life loss; behavior 2 skips damage subtraction. The life-loss scan leaves its
objective count in DS:2074, not the actor's reset health value. A zero scan CX
means 65,536 LOOP iterations, and DF affects both map scanning and HUD copies.
Score formatting stores at most eight computed target digits; rolling and
drawing retain the original nine-word record layout and player-two offset.

This is a CPU recovery layer, not production-App integration or a whole frame.
The main App still uses its existing gameplay implementations.

## Original Evidence

Two independent final captures, B and C, execute unchanged relocated LEZAC.EXE
using Unicorn 2.1.4. Compressed projections, manifests and checkpoint catalogs
are exactly byte-identical. The executable and all 14 producer modules
are authenticated before and after capture, including the actual mapped native
Unicorn library.

| Item | Value |
| --- | --- |
| Cases | 3,102 |
| Caller / standalone-divide returns / runtime errors | 2,422 / 600 / 80 |
| Whole actor-to-post paths / whole life-loss paths | 50 / 32 |
| Actual player CALLs / inactive-P1 prefix skips | 24 / 12 |
| Life-loss / score-format / font paths | 502 / 246 / 434 |
| Signed-divide paths | 902 |
| Register states / ordered writes | 4,177,177 / 373,395 |
| VGA writes | 243,192 |
| Raw / compressed projection bytes | 31,367,046 / 4,640,672 |
| Raw SHA-256 | d6fdd8dbd98d3fd6a3b839f796a8e40485b1a8dfc7c61990d7bc83f94fdef6b8 |
| Compressed SHA-256 | 47cd96262c0e37523d72b92107ea5123e6a00762541d90a1b4962b2001e254fc |
| Manifest SHA-256 | bc8b93e1949fda472f00e7e0064046421fe09aff0da0811e64abc9ce627abed1 |
| Checkpoint catalog SHA-256 | b7e361044e92826c05afafefb2dbf47dfb1a568f75ec06469a8a5e9f63c657ce |

Executable SHA-256:
7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec.
Mapped Unicorn library SHA-256:
ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c.
Final producer SHA-256:
298ba3bc6c858c52828334ea8171be7f86bb5a4770dd1a2a8ce806bb6575520b.

The controlled profiles cover all 256 health bytes with damage 0/1/255 for
both players, behavior-2 exclusion, mirrors, both direction flags, dirty states,
signed score boundaries, glyph wrapping, objective-count overflow, zero/one/
64/65,535 map lengths, stack faults and signed numerator/divisor boundaries.
Whole-call profiles include real caller selection, score-carry pickups, weapon
paths, animation copies, terrain interaction and flame-induced life loss.
Observed instruction addresses, not family names alone, determine path counts.
Whole cases are seeded only before the actor entry or real caller; no state is
injected at the post-player boundary.
The final original trace union reaches all 303 explicit instruction labels in
PlayerPostOperation, excluding callees delegated to existing recovered owners.

The observed run records registers and ordered writes. Its independent control
uses only address-filtered stop/phase hooks, without register or write tracing.
Both executions agree on all endpoint register/flag columns and complete one-MiB
memory. Ordered writes reconstruct every changed byte. All 43,552 relocated
code bytes remain unchanged. No instruction patches, call stubs, hardware I/O
or delivered IRQs occur in this baseline corpus.

The frozen fixture publishes compact initial differences, delta register traces
and ordered writes, not full RAM dumps or screenshots. The producer and raw
failed captures remain separately available in RAM. Bounded decompression and
SHA-256 authentication precede normal replay; the standalone C++ input checks
also pin exact lengths and FNV fingerprints, without calling FNV cryptographic.

## Capture Boundary Repair

Capture A stopped at 1000:8044 when player one was inactive, before player two's
actual call. The required real-call/post-return guard rejected case 2404. That
failed run, its exact producer, initial/endpoint RAM and partial corpus are
retained; agreement between the observed and control runs did not make that
incorrect boundary valid.

The final producer follows the actual phase: a whole-caller run may pass the
prefix 8044 only until it has observed the real 7F5C actor-return continuation.
The C++ replay similarly lets FrameActorEntryOperation select player two before
composing ActorUpdateOperation and PlayerPostOperation. All 12 such prefix
skips are now exercised. Whole-actor tile cells are restored in the initial
seed after adding the life-scan plane, preserving actual pickup/flame routes.
Neither correction changes instructions or guest state after execution starts.

## Validation

GCC and native MSVC each pass 27,918 replay executions across instruction budgets
1/17/4096 and copy limits 1/2/all, with snapshot restoration after every grant.
They compare 12,846,218 register/control boundaries and 35,810,295 post-player
dispatches, all ordered writes, complete final memory, outcomes and endpoint
flags. As in adjacent recovery tests, intermediate arithmetic flags masked by
0x08D5 are excluded; all other intermediate flags and all endpoint flags compare.
String-transfer and dispatched-instruction accounting are checked independently.

Fourteen computed C++ IRQ controls cover the caller, damage/life call, temporary
map DS, health bar, score format/division/scroll/draw/font and final call. Two
interruptions occur after exactly one transfer of a partial byte/word REP.
Each IRQ dispatches 36 handler instructions, restores the CPU and advances the
BIOS tick from 100 to 101; alternate grants and restored snapshots agree on
complete memory and ordered writes. These 504 instructions are computed
continuation controls, not an observed original IRQ schedule or frame-clock proof.

Seventeen invalid checkpoint controls, wrong entry, masked IRQ, zero budget,
terminal no-work and two actual RETF boundary controls pass. Twenty separately
compiled faults are rejected by normal unit/original assertions: caller SP,
library DS ownership, health subtraction, life scratch, zero map length, map/
health direction, signed division, iteration count, zero divisor, digit limit,
player-two layout, RETF precedence, dispatch/IRQ/copy/font accounting, terminal
dispatch and restored caller corruption. All mutants compile; production and
test hashes remain unchanged.

Strict native MSVC /std:c++latest /W4 /WX build, unit, full replay, eight CLI
rejection controls, two fixture tests, and Windows autocrlf cold checkout pass.
The cold checkout covers 28 families, 91 files and 28 CRLF negative controls.
Native executable SHA-256:
ac33de2803b4033ed929cc842dde3675d8b0abf8c453d1b1dd63bbc90395272c.
Strict GCC C++23 ASan/UBSan unit and full-corpus replays also pass.
Source guardrails pass 20 controls with 167 mapped sources.

The broader selected Debug CTest batch passes 51 of 52 checks. The remaining
reward_lifecycle_fixture reaches its unchanged 30-second subprocess timeout;
the standalone Debug reward replay passes in 58.05 seconds. The same unmodified
fixture checker passes with the freshly built Release App, including LF/CRLF,
truncation and velocity-mutation controls. No App/gameplay source or timeout
was changed. The Debug failure log is retained; this is not reported as an
all-green Debug batch.

A fresh silent level-7 App boss probe still passes eight ticks and 48 physical
links with no coordinate or animation-byte mismatches. Its inspected 320x200
post-probe RGB SHA-256 is
15e9811c9084c5065530269e8b8772b4bbdd55fd7c50403972c0bf967cf53e89.
This controlled damage/camera probe is existing-renderer regression evidence,
not natural gameplay, original pixel comparison or use of PlayerPostOperation.

All builds and raw captures remain RAM-only under the user's disk-pressure
exception. Canonical source, original assets, captures and Git metadata remain
preserved. Only audited redundant cold-checkout replicas were removed; their
staged source/fixture bytes, synthetic Git metadata and passing reports remain.

## Parent Stack-Ownership Integration

The integration retains published player-post head 135d09b and incorporates
the parent ActorUpdate fix 5375ce6 without changing player-post C++, tests,
producer or frozen fixture bytes. The parent now rejects foreign borrowed
stacks before guest work. All eight newly selected CTests pass in 176.92
seconds, including the complete player-post replay, eight CLI controls,
fixture-retention checks, all 20 compiled mutations, the parent unit and
source guardrails. A fresh strict native MSVC build, unit and complete replay
also pass; all protected core and fixture hashes remain unchanged. The new
native executable SHA-256 is
a822498a728d7c2b642a539f22ddc30d2594531f8b05a18aef2101e22b7f609d.
Its validation took 22.20 seconds. This does not claim a new cold checkout or
production-App integration. Fresh exact-head review and hosted CI remain gates.

## Live Stack Review Fix

P1 finding discussion_r4331157814 on published head
7bacbb52977c097a052ccc1ded59e048a62dd045 identified endpoint-only SS validation
for the standalone player-post API. A ScoreDivide checkpoint at 1920:0945
with callerSs 7000 and live SS 7001 was accepted; its first instruction wrote
through the foreign stack. The probe reports rejected=0/writes=1/
foreign_stack_writes=1 before the fix. The permanent new unit regression
also fails against that old header.

Validation now requires registers().ss==callerSs for every restored state,
including the active timer's live SS. The identical probe reports
rejected=1/writes=0/foreign_stack_writes=0. Four additional controls reject
a corrupt promised SS, corrupt running live SS, corrupt ScoreDivide SS and
corrupt IRQ SS before guest work. All 21 snapshot rejection controls pass.
A twenty-first compiled fault restores the old endpoint-only comparison and
is detected by the new assertion.

All seven selected CTests pass in 186.92 seconds, including the complete
original replay, fixture-retention controls, all 21 compiled mutations,
parent ActorUpdate unit and source guardrails. GCC C++23 ASan/UBSan unit and
complete replay pass. Fresh strict native MSVC /std:c++latest /W4 /WX build,
unit and all 27,918 replays pass with every protected core/fixture hash
preserved. The native run took 25.28 seconds and produced executable SHA-256
2268dbe190abdf1cb4e61a7076f82747f761020dea4e12b677530721c3896758.
No original producer, manifest, compressed projection or guest instruction
changed. CLI and cold-checkout coverage above is prior unchanged-protocol
evidence, not a fresh run for this fix. Hosted CI and a new exact-head review
remain required. The separate unpublished full-pass integration's unstable
optimized replay is retained outside this player-post branch.

## Remaining Work

Compose the complete player and nonplayer passes, transient queues, production
memory owners and shared frame/work clock, then integrate the recovered owners
into the live App. Natural original/C++ routes, aligned rendered frames, pixel
timing, physical input and owner visual acceptance remain separate obligations.
This bounded corpus does not establish whole-game or whole-frame fidelity.
Hosted checks and fresh exact-head external review remain merge gates.
