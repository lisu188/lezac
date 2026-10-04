# Active-Player Gravity Word Arithmetic

Two independent silent original captures each reproduce 32 seeded airborne
gravity boundaries: sixteen velocities on each real kind-0 P1/P2 record.
All 64 observations reproduce the pinned fixture byte-for-byte. This is bounded
airborne arithmetic, not bottom gating, landing, complete player motion, natural
trajectories, rendered parity or campaign completion.

## Original Order and Identity

The original executable SHA256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Its MZ image begins at file `0x0770`. Active gravity at `1000:6743..6753`
(exclusive end) is `8346f240817ef2ff077e05c746f2ff07`.
The addition of `0x40` to the VY word wraps before the signed `0x07FF`
comparison. Airborne `32704` becomes `-32768`, and `32767` becomes
`-32705`, for both players. The old wide C++ sum produced `2047`.
Signed minima, upward-to-zero and terminal boundaries are also covered.
The unchanged jump at `6753` proceeds to `6813`, where observations end
before input, friction, posture and fractional integration.

Physical menu input boots two-player level 1, followed by one unseeded update.
Records `DS:1B88/1BAE` are both kind 0, visual slots 0/1, hotspot 0 and raw
active behaviors 0/1. Both normalize to zero in the observed SS behavior local.
The fixture's last byte preserves raw actor behavior, not that local or kind.
Each case restores both original bootstrap records and changes only the selected
player's four motion words at +6: zero VX, selected VY, zero fractional carries.
All other actor bytes, including animation/drop words, are preserved.

The selected visual is placed at (336,99), with a distant active partner.
Terrain/word plane, clock and RNG are seeded test controls. Bottom is always
clear; overflow velocities are deliberately seeded, not naturally reached.
Stack-preserving hooks at `7EC5/6743/6813` are disabled for the bootstrap,
then select kind 0 and the actual `SS:BP+4` actor-parameter offset. Each
captured far pointer must equal the selected offset and captured DS. This avoids
confusing players after their behavior locals normalize. Same-call pairs retain
six registers and 58 SS-local bytes; only the VY word may change, with X/Y still
336/99. Instructions, relocations, support hashes, scratch extent and eleven
private asset copies are checked. All hooks/scratch restore and children close.

## Retained Evidence

[The native archive](evidence/active_player_gravity_20261004/native-captures.tar.gz)
is 50,761 bytes, SHA256
`2cbe32c9821386b790cb3b38cd5d94a353ee24383e730860739ce4be79db7995`.
It contains both complete capture directories and the exact executed portable
producer/checker. Capture JSON SHA256 values are:

- `capture-1/capture.json`:
  `bb57a1e9f34aa8eef6354ed0b399145a868e5dea23d5d1b71656dd5a14179883`.
- `capture-2/capture.json`:
  `bc1c982ad17c095185fc868d37aeb0dcd9cc2baa0b9a9e38c8f8a2a70c991f10`.
- Executed producer:
  `043bfbc6ddcfc1a3c5efec83470345a696fa2e6532457f95ece4c586a0a6eab5`.

Earlier RAM-only captures were lost when WSL scratch cleared. These are fresh
recaptures, not reconstructed old evidence. Original assets remain in the
repository and are identified by each native asset manifest.

[The fixture](../../tests/fixtures/active_player_gravity_word_original.bin) is
448 bytes, SHA256
`8a6d797055605ef34d8a16d89ba07cf65c4abb5236c90be97ee33e87b322cf5e`,
FNV1a64 `da78ead002469f09`. Header `LZAGv1` pins the executable and
sixteen instructions. Ordered twelve-byte `BBhhhhBB` rows contain index,
bottom, VY before/after, Y before/after, player 1/2 and raw behavior 0/1.

## Production Validation and Limits

`updatePlayerGravity()` now narrows the sum before signed min 2047. The rest
of the method is unchanged, including landing/posture/rebound. Its verbatim
body, with stubbed storage/posture, independently compiles as C++17 and matches
all 32 native outputs. Restoring wide addition, clamping before addition or
changing the terminal limit to 2048 must fail. Airborne-only cases cannot prove
bottom gating or landing; no mutant coverage is claimed for those paths.

The diagnostic separately checks 32 helper calls and 32 real P1/P2
`updateWithControls()` frames with an active partner: VY, unchanged X/VX/RNG,
active states and clock advancement. Helper Y stays unchanged; final caller
Y/fractions are not compared with a pre-integration native fixture. Validation
rejects all 448 byte mutations, truncation/trailing bytes and a changed EXE.
Production replay passes positively and rejects eighteen malformed fixtures.
The capture self-check launches no game.

All 33 focused local tests passed, including the four gravity suites,
death/reentry, two-player progression and controlled 3,200-update boss defeat.
Both full platform suites, both extracted-package checks and an exact-head
native recapture remain merge gates, not implied results of adding tests.
Native CI retains the existing 128 MiB output/512 MiB process allowances and
strict ten-percent reserve floors. All four existing OPEN items and global
completeness/fidelity flags remain unchanged.

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-active-player-gravity-word-evidence \
  tests/fixtures/active_player_gravity_word_original.bin
ctest --test-dir build -R '^active_player_gravity_' --output-on-failure
```

Stage fresh private copies of the eleven assets before native recapture:

```sh
env SDL_AUDIODRIVER=dummy python3 -B tools/capture_original_active_player_gravity.py \
  --run-dir /dev/shm/lezac-active-gravity-original \
  --out-dir /dev/shm/lezac-active-gravity-capture \
  --approve-procmem --approve-runtime-instrumentation
python3 -B tools/check_active_player_gravity_word_fixture.py \
  --capture /dev/shm/lezac-active-gravity-capture
```
