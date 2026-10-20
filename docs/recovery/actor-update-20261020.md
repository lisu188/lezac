# Complete Original Actor Update

## Scope

ActorUpdateOperation composes the real 1000:6053 actor entry, animation prologue,
precontact/contact work, tile dispatch, player motion or nonplayer motion/expiry,
common terrain response, integration and the actual near RET 4 at 7780. It stops
before the caller's next instruction. Runtime errors stop at 1920:00E2; divide
faults stop before handler delivery.

Every phase borrows the same TimerIrqBus and live SS. There is no private guest
stack reset, later-state injection, data-plane snapshot/reconciliation or host
floating-point replacement. The serializable variant owns CPU continuation
metadata, not gameplay memory. Shared CPU state is retained across player,
terrain and finish handoffs. One aggregate dispatch/IRQ count spans all phases.

The constructor admits the actual 6053 call boundary. Returned state must retain
the entry SS/BP and restore SP by six bytes (near return plus four argument
bytes). Terminal outcomes must agree with the active child's actual outcome.
Nested/masked/terminal IRQ admissions are rejected. Caller selection is exercised
separately in the replay driver with the existing original caller operation.

This is not production-App integration. Player post-return work at 7F5C..8044,
including health, life-loss and HUD callees, remains outside this boundary.

## Original Corpus

The final C and D captures execute unchanged, relocated LEZAC.EXE with Unicorn
2.1.4. Their compressed streams, manifests and checkpoint metadata are exactly
byte-identical. The actual mapped native library and all 14 canonical inputs
(the executable plus 13 producer modules) are authenticated before and after.

| Item | Value |
| --- | --- |
| Cases | 7,188 |
| Actual returns / runtime errors / divide faults | 7,180 / 6 / 2 |
| Actual player / nonplayer CALLs | 28 / 74 |
| Player paths / expiry paths / animation-copy paths | 7,056 / 12 / 8 |
| Register states | 7,723,202 |
| Ordered writes | 1,411,439 |
| Raw projection bytes | 124,154,658 |
| Compressed projection bytes | 31,111,439 |
| Raw SHA-256 | fedc341828e10038ea6a6ee1ce5d1b7f79fec708c6ba41c49140c0911db11ccf |
| Compressed SHA-256 | 48c1ecebdf056802eb5b8e50b743a098d9263c4fde6fe37beda1341e6ab38ea4 |
| Manifest SHA-256 | a7272561204fc501123429871b8a7c9e72dc3f68ede7493bf0f1184b7416f9ed |

Original executable SHA-256:
7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec.
Actual native Unicorn library SHA-256:
ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c.
Final producer SHA-256:
1b2b747ed19bc641032a7d331cda9ee0fdd18329f3aafef3d3102befba30971f.

The player cases retain the earlier motion matrix's controls, word velocities,
pickup/weapon/animation bytes, score-overflow and stack/direction profiles, now
entered through the actual prologue. Existing complete nonplayer profiles and
explicit expiry/runtime/divide cases cover the other routes. Initial data/stack
are controlled, not natural gameplay. Observed instruction addresses, not profile
labels alone, determine the coverage counts.

Every successful original return executes 7780 and restores caller SS/SP/BP.
Actual caller cases execute the original CALL at 7F59 or 7EE1. Observed and
unobserved runs match complete one-MiB memory and all 14 recorded register/flag
columns at the endpoint. Ordered writes reconstruct all changed memory. All
43,552 relocated original code bytes remain unchanged. No instructions are
patched, calls stubbed, hardware I/O performed, IRQs delivered or later states
injected in the baseline original corpus.

The fixture publishes compact initial differences, delta register traces and
ordered writes, not full RAM dumps. Cryptographic authentication and bounded
decompression precede normal replay. Standalone C++ also checks exact projection
and MZ lengths/FNV fingerprints; it does not claim cryptographic strength for FNV.

## Copy-Boundary Gap

The first two independent 7,180-case captures were identical and their complete
execution comparisons reached the final C++ coverage guard, but none executed
the animation Move at 1920:091F. The partial-copy IRQ requirement therefore failed.
That run is not treated as a passing complete regression.

Eight additional initial states expire a mode-3 animation frame timer for both
players, both initial direction flags and direct/actual-caller entries. Each
reaches the actual seven-byte Move. Both final captures were regenerated and the
original producer now requires all eight copy paths. No intermediate state is
edited and the IRQ coverage assertion is unchanged. Earlier captures, their
exact producer and failure evidence are retained in RAM.

## Validation

The final GCC and native MSVC replays each pass 64,692 executions across budgets
1/17/4096 and copy limits 1/2/all, restoring snapshots after each grant. Each
checks 24,607,971 register/control boundaries and 69,429,546 aggregate dispatches.
All ordered writes, complete final memory, outcomes and endpoint flags match.
Intermediate arithmetic flag bits 0x08D5 follow the parent comparator's exclusion;
other intermediate flags and all endpoint flags are compared.

Eleven computed C++ IRQ boundaries cover prologue, contact, tile dispatch,
player/nonplayer motion, expiry, terrain, integration, the real RET and one
actual partial copy. They dispatch 396 handler instructions and restore CPU
state while advancing the BIOS tick from 100 to 101. Alternate-grant/snapshot
forks agree. These are computed continuation controls, not an original IRQ
schedule or work-clock coupling proof.

Fourteen invalid snapshot controls, wrong entry, masked IRQ, zero-budget and
terminal no-work controls pass. A focused self-review case rejects a runtime
outcome paired with a child that actually reports Returned.

Completed local checks include native MSVC /std:c++latest /W4 /WX build, unit,
full replay, eight CLI controls, fixture rejection tests and Windows cold
checkout; GCC full replay, strict GCC C++23 ASan/UBSan unit/full-corpus runs,
Linux fixture tests and Linux cold checkout. Both cold-checkout runs cover
27 families, 88 files and 27 CRLF negative controls. Native validation preserves
all protected source/fixture hashes and produces executable SHA-256
7ad73dfd4bace46e185064f7cc0b1e2096836d3771b679b5c11a8cdeb0cb0037.

All 37 focused CTests pass, including adjacent player/nonplayer, animation,
boss, reward, writeback and ledge regressions. All 14 separately compiled faults
are rejected through normal assertions: caller SS/SP/BP, skipped player terrain,
bypassed player/expiry phases, skipped integration, dispatch/IRQ accounting,
IRQ delivery, terminal dispatch, snapshot caller corruption, and runtime/divide
outcome classification. Every mutant compiles successfully and the production
header/test hashes remain unchanged. Source guardrails pass 20 controls with
166 mapped sources.

A fresh silent live-App two-player target-selection capture produces six
320x200 frames. The inspected checkpoint's RGB SHA-256 remains
d5378614fc5817c5ba7c823a92cd265b3b2f3413636ddcc28296d1e6e99afdba.
This is existing-renderer regression evidence, not use of the new core.
All local builds, raw traces and captures remain RAM-only under the user's
disk-pressure exception; speaker output stays disabled.

## Remaining Work

Recover player post-return health/life/HUD instructions and their real callees.
Then compose the full nonplayer and player passes with transient queues,
production memory owners and the shared frame/work clock. Natural original/C++
routes, aligned rendered frames, pixel timing, physical input and owner visual
acceptance remain distinct obligations. This change does not establish whole-game
or whole-frame fidelity. Current-head hosted CI and external review remain
mandatory before merge.
