# Original Player Start Locator

## Recovered Behavior

The unchanged near Pascal helper at game `056B..0625`, called by the waiting
prepass at `7D20`, clears actor byte `+02` (idle), scans portal records in
increasing order, and places the actor's visual at the first record whose
marker shares a bit with the caller's low-byte mask. The portal key is not
read. If there is no match, both visual coordinate words become 17. Motion,
fraction, animation and other actor/visual bytes remain untouched.

The prior App helper required both `key == 0` and exact marker equality. It
also retained the previous coordinates when reentry had no match, and invented
a neighbor-of-P1 fallback for P2 initialization. A new actual-App regression
failed before the production correction: `player start reentry mismatch case 0`.

`gameplay/player_start.hpp` now owns the non-copying locator rule. The App's
shared `placePlayerAtStart` applies its coordinates and idle reset for initial
placement, expiry/reentry and the older respawn helper. No teleport-destination
logic, motion initialization, inventory minima, or life-count rule changed.

## Resumable CPU Operation

`core::PlayerStartOperation` implements the complete original helper and its
CRT `0920:04DF` stack-check call one instruction at a time. Snapshots contain
registers, outcome and dispatch count; portal/actor/visual storage stays with
the caller's bus. Zero budget and completed operations are inert. Resuming
from snapshots is checked with dispatch grants 1, 2, 17 and 4096.

Two independent finalized oracle runs are byte-identical. They execute the
MZ-relocated original under the pinned Unicorn 2.1.4 library, with no patched
instructions, stubbed calls, interrupts or hardware I/O. Observed runs are
compared with runs lacking instruction/write hooks across the complete 1 MiB
memory and all 14 register fields. All 43,552 original code bytes remain
unchanged. The ordered write stream independently reconstructs complete final
memory before its compact projection is accepted.

The corpus has 1,043 cases, 59,867 register states and 14,053 writes. It covers
all 256 marker-byte values for both player masks with zero/nonzero keys,
empty/missing markers, first-match ordering, combined markers, coordinate word
extremes and three original CRT stack-error exits. Controlled portal counts
are zero through three; arbitrary adjacent allocation/table aliases are not
claimed. The C++ CPU replay makes 97,877 boundary comparisons over 4,172 runs,
matches full memory and ordered writes, and compares all endpoint flags.
Undefined arithmetic flags are excluded only at intermediate trace boundaries.

## Live App And Guardrails

The frozen App projection authenticates before any seeding. It checks 1,040
cases through the same placement method called by `resetLevel`, then through
the real `updatePlayerReentryPrepass` expiry path. It preserves nonzero motion
and fractional state across reentry and verifies the idle reset. This is a
controlled startup-placement stage, not 1,040 complete startup observations.

Five compiled mutations are detected: filtering by key, exact marker matching,
wrong missing-marker coordinates, skipping the idle write and wrong Pascal
return cleanup. Fixture checks reject altered/missing original assets,
producers and compact projections, and preserve existing export targets.
Eleven actual-App corruption controls must fail before replay. Real Linux and
native Windows Git cold checkouts preserve the frozen bytes; removing the
family protection reproduces CRLF conversion in the manifest controls.

Native MSVC C++latest `/W4 /WX /O2` passes the complete CPU replay. Native
Windows Python passes four provenance tests and explicitly skips the actual-App
test, since no native App is supplied. Linux GCC C++23 strict builds and the
ASan/UBSan CPU replay pass without warning suppression. The unrelated existing
App `snprintf` warning remains visible in the Release build.

All 14 selected CTests pass, including the six new locator checks, source and
cold-checkout guardrails, the original state-2 prepass, three boss reentry
replays and the natural-campaign replay/guard. This is focused validation, not
a full local suite or native Windows actual-App build. Full CI and exact-head
external review remain merge gates.

Validation commands:

```sh
python3 -S -B tools/check_player_start_fixture.py --out /dev/shm/player-start.bin
./build/lezac_player_start_test /dev/shm/player-start.bin .
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-player-start-original tests/fixtures/player_start/app.bin
ctest --test-dir build --output-on-failure -R 'player_start_'
```

## Evidence Limits

Compact CPU projection SHA-256:
`d7c5f53dc2c17de126f3ce918c9be5a85eb66a9ac1ae4eb663aea6f709dad35a`.
The manifest pins both producer sources, the unchanged original executable,
the actually mapped Unicorn library and both compact projections. No complete
RAM image or screenshot is published by this change.

The instruction operation is not yet connected to the App's clock/IRQ owner.
The complete waiting prepass still includes HUD, reserve drawing, screen clear
and end-run callees requiring separate composition. Controlled function and
placement-stage proof is not natural full-game or seven-level campaign proof.
The existing seeded level-7 fire/reentry replay still matches 758,784 indexed
pixels over 16 views, but that is neither natural boss victory nor fresh
original RGB/DAC evidence. Whole-game frame fidelity remains open.
