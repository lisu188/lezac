# Dying-Player Gravity Word Arithmetic

Two independent silent original-game captures each record 64 seeded P1/P2
behavior-2 gravity/landing boundaries: both actual kind-0 player records, bottom
contact clear/set, and sixteen signed input velocities. All 128 observations
agree with independent execution of the unchanged original instructions.
This proves bounded gravity arithmetic, not natural death, full player motion,
animation/countdown lifecycle, input, rendered parity or campaign completion.

## Original Order

The shipped executable SHA256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Its MZ image starts at file `0x0770`. Behavior-2 gate `1000:7018` is
`3c02753f`; gravity/landing is `1000:701C..704E`, exclusive end:

```text
807edf007406837ef2007d128346f240817ef2ff077e05c746f2ff07eb14
837ef2007e0e31c08946f28b46d225f8ff8946d2
```

Clear bottom contact or negative VY receives a word addition of `0x40` at
`7028`, wrapping before the signed `0x07FF` comparison. Supported positive VY
becomes zero and Y is masked by `0xFFF8`; supported zero holds. For both players,
airborne `32704` becomes `-32768` and `32767` becomes `-32705`. The old wide C++
addition returned `2047`. Four wrap cases and twenty supported positive landings
are covered, alongside signed minimum, upward-to-zero and terminal boundaries.
All boundary velocities/terrain were deliberately seeded, not naturally reached.

## Capture Provenance

The original boots two-player level 1 by physical menu input, then completes one
unseeded tick. The preserved player records are `DS:1B88` and `DS:1BAE`, both
kind 0 with visual slots 0/1, hotspot 0 and active behaviors 0/1. Kind 1 is a
walker, not P2. Each captured `SS:BP+4` actor far pointer equals the selected
real player address and captured DS; labels alone do not establish identity.

Each case restores both bootstrap records, changing only the selected player's
behavior to 2 and six motion/timer words at `+6`: VX zero, selected VY,
zero fractional carries, zero drop word, timer 100. Kind, visual, hotspot,
animation and all other actor bytes remain exactly as bootstrapped. Selected
visual coordinates are `(336,99)` and the other player remains active/distant.
Terrain is empty or bottom `0x52` at `(42,14)/(43,14)`; clock/RNG are seeded.
This is not an observation of a natural death constructor or countdown.

Owned-child stack-preserving hooks are `7EC5`, `701C` and `704E`; gravity hooks
accept only kind 0/behavior 2. Executable bytes, relocations, support hashes,
runtime segments and the existing bounded scratch extent are checked. Each
same-call pre/post pair retains 58 SS-local bytes, six registers and the real
actor pointer. Only VY/Y local words may differ. All three hooks and scratch
were restored, children closed, and eleven privately copied assets hash-checked.

Retained RAM-only evidence:

- `/dev/shm/lezac-dying-player-gravity-original-20261003-v40-a/capture.json`, SHA256
  `8d2dc08bcdcdfd9b8d526d06d672f86a1ffe41e98edfb412d2c2669e054fd695`.
- `/dev/shm/lezac-dying-player-gravity-original-20261003-v40-b/capture.json`, SHA256
  `b01aa659d0a2845068a95cd5f19b4fa81e32f84850d3b086e8d6bc1c500d93a6`.
- Native producer SHA256
  `a5289d82185c0a4420d8ebe98c6f968beb41f6ef473bb8dd12e7f2f6b188a0ad`.
- Extraction receipt SHA256
  `bbd29c663ca4b5aeddbb9d0ca84e1ffb7a5c44fc9a7adab57bff5ee36eed2264`.

The portable producer differs only in its repository-root derivation. Both runs
derive identical 866-byte
[`dying_player_gravity_word_original.bin`](../../tests/fixtures/dying_player_gravity_word_original.bin),
SHA256 `4b8dc06d452b766c8477557dd26cdb64b03978ecc08ec6c357a94899d7d6ebc3`,
FNV1a64 `0a6c54dd68bd46b1`. Header `LZDGv1` pins the executable and 50 original
instruction bytes. Each ordered 12-byte row (`BBhhhhBB`) records index, bottom,
VY before/after, Y before/after, player identity 1/2 and behavior 2, not kind 1/2.

## Production Validation

`updateDyingPlayerMotion()` narrows acceleration to a signed word before signed
min 2047. The rest of that production method is byte-identical to its baseline:
landing, floor friction, collision response, fractional integration, grounded
state and velocity mirrors are unchanged. Active-player and other actor motion
paths are not modified.

The verbatim gravity prefix is independently compiled as C++17 against all 64
original outputs. Restoring wide addition, ungating gravity and removing the
landing snap must fail. This uses stubbed storage/edges, not a full executable.
The production diagnostic separately exercises 64 complete helper calls and 64
real P1/P2 `updateWithControls()` caller updates, with an active partner to prevent
shared fallback. It enters death through `beginPlayerDeath()` then seeds
non-expiring timers; those timers are test controls, not native lifecycle parity.
VY, supported landing Y and unchanged RNG are checked. Nonzero-VY final Y and
fractions are not compared to native observations ending before integration.

Fixture checks reject all 866 single-byte mutations, truncation/trailing bytes
and a changed executable. Production replay must pass positively and reject
18 malformed fixtures. The no-launch capture self-check verifies instructions.
A separate path-scoped native CI job recaptures all 64 cases with unchanged
128 MiB output/512 MiB process allowances and strict 10-percent floors. Both
full platform suites, both extracted-package checks and exact-head native CI
remain merge gates; adding these tests does not itself report them as passing.

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-dying-player-gravity-word-evidence \
  tests/fixtures/dying_player_gravity_word_original.bin
ctest --test-dir build -R '^dying_player_gravity_' --output-on-failure
```

For recapture, stage fresh private copies of the eleven original assets first,
then use fresh output paths:

```sh
env SDL_AUDIODRIVER=dummy python3 tools/capture_original_dying_player_gravity.py \
  --run-dir /dev/shm/lezac-dying-player-gravity-copy \
  --out-dir /dev/shm/lezac-dying-player-gravity-capture \
  --approve-procmem --approve-runtime-instrumentation
```

## Remaining Scope

All four original-fidelity items remain OPEN. Natural dying-player trajectories,
timers/animation/reentry, friction/response/integration parity, full replay and
VGA/HUD/input/audio fidelity are not promoted by these seeded observations.
The original bootstrap screenshot was inspected/shown before any case seeding;
it is not a frame-aligned C++ comparison. No full-replay scope or reserve was
weakened. `port_functionally_complete=0` and `original_fidelity_claim=0` remain.
