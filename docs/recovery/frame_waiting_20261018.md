# Composed Two-Player Waiting Prepass

`FrameWaitingOperation` executes original `7C3D..7EBB` on the caller's bus,
composing the real ammunition (`326E`), reserve (`29DB`), rectangle (`07C5`)
and player-start (`056B`) operations. It retains Pascal call/return stack
writes, registers, ordered writes, REP limits, direction flags and resumable
snapshots. It does not bind this operation to the production instruction clock.

## Boundaries And Ownership

Normal completion stops before `7EBB`. The original call to `1B14` pushes its
real return address `7D0B` and reports an explicit end-run UI handoff; no UI call
is stubbed or treated as completed. Runtime stack errors hand off to
`0920:00E2`. The only unobserved instruction address in the outer window is
`7D0B`, which belongs to the return path from the unexecuted end-run UI.
The actor passes at `432A` and `6053`, and the waiting fallback after `7EBB`,
remain outside this operation.

IRQ ownership follows the active child. HUD and drawing operations own their
timer state, including a sprite's temporary source DS. The outer operation
owns interrupts during ordinary instructions and player-start execution, and
restores registers to that child after IRET. Conflicting snapshot owners are
rejected; zero and finished grants are inert.

An actual-App projection exposed a production ownership error: `7DB5` writes
each player's fire latch, gated by `DS:79CA`, to shared `DS:79A3` before a
successful reentry clears both latches. The production prepass now preserves
that order for both player slots, including the inactive second slot. The
existing `corpseRewardRoll_` owner is used; no second mirror is introduced.
The old App fails the first projected case, 128, on shared scratch; that record
is unchanged by the later inventory/weapon bridge correction.

The bridge initially read inventory one byte early. Cross-checking the older
54-case state-2 capture established bases `1B6C/1B70`. Production minima remain
`{100, 10, 2}` for slots zero through two; there is no inventory-minimum fix.
Original weapon values 1..4 and one-based descriptor rows are explicitly
translated to C++ zero-based enums. The ammunition dependency was independently
recaptured with the same corrected convention before the final waiting runs.

## Original Execution Evidence

The producer fingerprints the original EXE, CARO/SPR assets, its own source and
both imported helpers. It verifies the actual mapped pinned Unicorn 2.1.4
library, then rechecks canonical source bytes before export. No instruction
patches, stubbed calls, delivered interrupts or hardware I/O are used.

Each controlled case executes with instruction/write observers and again
without those observers, using the observed stop boundary. All 14 endpoint
registers and complete 1 MiB memory must match. Ordered writes independently
reconstruct final memory, and the 43,552-byte code image remains unchanged.
Two independent final captures have byte-identical manifests and gzip streams.

| Property | Value |
| --- | --- |
| Cases / normal / end-run / runtime error | 238 / 230 / 2 / 6 |
| Register observations / ordered writes | 291350 / 121856 |
| Executed addresses / outer-window addresses | 502 / 191 |
| Decoded / compressed bytes | 27514428 / 1640911 |
| Decoded SHA-256 | `f3ffe5f55d6da87086b11d26c0629fa5751da5defcd0f3fcdd5171c84e638542` |
| Compressed SHA-256 | `999814e916c2dca06eea36b97db4395864f57992e87a0e3c766103a7509b3093` |
| Manifest SHA-256 | `ca5582df8411f7a83e19d593465b180e88e548c288b3006cd57ff40d77ab8b19` |
| App bytes / SHA-256 | 4364 / `07946b266e968b92e78180f5f2e160eb37b256b6df53c534974101056f0242bd` |

The corpus covers mixed player/actor states, gate and latch values, timer and
reserve boundaries, simultaneous expiry, active ammunition HUDs, player-out
clears, stack errors, inventory minima and DF. It publishes controlled seeds,
register columns and ordered writes, not full RAM images or PNG captures.
The checker authenticates all dependencies, bounds decoding, independently
derives the App projection from the original trace, and preserves existing
different exports and symbolic links.

## Validation

The CPU regression checks 2,856 replays with grants 1/2/17/4096 crossed with REP
limits 1/2/65535, restoring snapshots after every grant. It compares 1,145,574
boundaries, 2,928,864 logical dispatches, 1,036,800 string transfers, full
endpoint memory and ordered writes. Intermediate control flags and all
endpoint flags are compared; intermediate arithmetic flags are not.

Five computed IRQ cases exercise outer, placement, reserve, sprite-bank and
rectangle ownership. These are C++ restoration checks, not captured original
interrupt schedules. Ten independently compiled mutants are rejected, with an
unchanged compiled control, authenticated input and preserved production source.

The actual App diagnostic checks 68 original-derived cases: 40 active HUD and
28 waiting/reentry cases, including 544 inventory bytes and 68 shared-byte
values. It checks reserves, timers, dirty bytes, global player state and fire
latches; it does not compare every coordinate or rendered App frame. Fourteen
corrupted App fixtures are rejected before assets/SDL are initialized.
Linux fixture tests pass all nine; native Windows Python passes seven with
explicit App-executable and symbolic-link skips. Strict native MSVC CPU replay
and GCC ASan/UBSan replay pass against the final corpus.

Four controlled original/C++ VGA-index endpoints match all 256,000 pixels.
Displayed HUD crops use the same shipped palette and nearest-neighbor scaling.
They are instruction-operation evidence, not natural gameplay screenshots or
live VGA/DAC timing proof. All local build/capture outputs remain in RAM and
all launched processes use dummy audio while C: exceeds its reserve threshold.

## Remaining Scope

This is bounded composed waiting-prepass recovery plus a production shared-byte
fix. End-run UI, the rest of the outer frame, production clock integration,
natural call timing, original IRQ schedules, live VGA/DAC behavior, a natural
boss victory, physical-input acceptance and whole-game parity remain unproved.
