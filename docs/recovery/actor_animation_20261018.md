# Resumable Shared Actor Animation

## Scope

`ActorAnimationOperation` reconstructs the original shared actor updater's
`1000:6053..615A` prologue, including the real `1920:04DF` stack check and
`1920:090E` byte-copy callee. Both player and non-player callers enter this
same code. `BehaviorDispatch` is an explicit suspension before `615A`, with
the original stack frame still live, not a completed actor tick or near return.

The operation uses caller-owned memory. It preserves far-record addressing,
16-bit offset wrap, descriptor-word selection, cursor counter overflow, signed
step extension, ping-pong reversal and mode-3 seven-byte backup restoration.
The real copy routine borrows DS, clears DF, performs interruptible `REP MOVSB`,
restores DS and executes `RETF 10`. Instruction budget zero and finished states
are inert; zero copy credit suspends the guest at REP without changing guest
registers or memory. Every copied byte is accounted separately from dispatches.

This is a required portion of the remaining actor-update recovery. It is not
yet composed with the `7903..7EBB` frame prefix or integrated into the App.
The existing semantic animation paths and their original-backed tests remain
unchanged. No link update, actor behavior or completed frame is inferred from
this prologue result.

## Original Evidence

Canonical `LEZAC.EXE` SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

The new producer executes unchanged original instructions under Unicorn 2.1.4,
verifies the actual mapped native library, checks its pinned digest and rejects
loader overrides. It also authenticates its own source, the shared register
helper and the original executable before and after generation. Captures C and
D independently produce identical manifests and compressed corpora. Earlier
A/B captures predate the added write-owner restriction and are not the frozen
provenance source; their instruction projection is byte-identical.

The 1,011 controlled cases cover all 256 animation mode bytes, all 256 counter
bytes, all 256 signed-step encodings, delayed/equal/overflow counter boundaries,
frame wrap, six visual indexes, DS and remote actor records, both player record
positions, 72 wrapping-record cases and three actual stack-error handoffs.
The descriptor table and records are declared controlled RAM, not natural
allocator state or proof that arbitrary visual indexes are reachable in play.

Every observed/unobserved endpoint agrees over all 14 registers and complete
1 MiB memory. Ordered writes reconstruct complete final memory and are bounded
to the stack, active cursor and selected visual descriptor word. All 43,552
loaded code bytes remain unchanged. No instruction patch, stub, forced IRQ,
guest interrupt or hardware I/O is used. The projection contains 71,759 register
checkpoints, 14,347 writes and 1,897 transferred string bytes. The producer
removes 271 Unicorn-only zero-CX REP callback stops, not executed guest copies.

Frozen raw projection: 2,354,311 bytes, SHA-256
`a7eb6324226bc44b35d69cb928283c53b6b954ef9cc845f846bf8b674ef09494`.
Compressed projection: 108,065 bytes, SHA-256
`4cbdba02f71130c9960dbe1d3a877841816ff2ad7a598eaab7aa3139efcc727a`.
Frozen manifest SHA-256:
`924a90a31810300368480f4025ce7c7ac30540548c957ad132a83d5778c2af2a`.

All raw captures, expanded fixtures, builds and mutation diagnostics remain
RAM-only under the disk guard. Only the compact controlled projection,
manifest, source and tests are published; no full RAM dump is published.

## Validation

The C++ replay runs every case four ways: instruction-by-instruction with
one-byte copy grants, two-byte grants, zero/full grants, and full grants.
Snapshots are resumed after every advance. All 4,044 replays agree on ordered
writes, complete reconstructed memory, endpoint registers and all endpoint
flags. The 71,759 intermediate checkpoints compare every non-arithmetic
register/control flag; intermediate arithmetic flags are not claimed exact.

The same original outputs also check the existing shared production
`gameplay::ActorAnimation::advance` model for all 1,008 non-error cases. All
7,056 active cursor bytes, advance decisions and selected descriptor words
match independently reconstructed original memory. This is shared production
model coverage, not execution through the actual App or physical record owners.

Strict GCC C++23, GCC ASan/UBSan and native MSVC C++latest `/W4 /WX /O2` pass
the unit and original replay, including the shared production model comparison.
The CMake suite registers the unit and original replay, bounded authenticated
fixture export, corrupted/missing-input and output-retention controls, compiled
fault controls and the existing cold-checkout/source guards. The new binary
family disables text conversion in actual autocrlf-enabled checkouts.
All seven focused CTests pass. Native Windows fixture controls and the real
Windows Git cold checkout pass with 13 families, 45 files and 13 CRLF negative
controls. This is not a full local App build or complete local CTest run.

The compiled mutations target disabled-mode gating, delay equality, signed
steps, backup length, DF clearing, eager REP copies, descriptor destination and
DS restoration. A first mutation attempt stopped on an incorrect harness
match-count expectation; it is retained and not counted as a passing fault
run. The corrected harness must compile every mutant and require an original
replay failure while preserving production and test sources.

## Remaining Work

Full `6053..777F` behavior dispatch, the `432A` link routine including original
Real arithmetic, caller/IRQ composition after `7EBB`, the remaining queue passes,
instruction-clock integration in the interactive App and whole-game equivalence
remain unproven. There is no natural capture, original timer-IRQ delivery,
production App integration, visual/DAC or full-frame completion claim here.
Current-head external review and full CI remain required before merge.
