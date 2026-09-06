# Original Monster Impact And Bomb Damage

## Scope

Eleven seeded original level-1 cases match 143 continuous production C++
updates. They establish nonfatal impact presentation, animation-counter
wrap, animation recovery, repeated flame damage and two kind-1 fatal
transitions. Twelve nonfatal hits and 40 living impact states are compared.
This also corrects the spawner's conversion from the original zero-based
HP byte to the port's remaining-health integer.

A separate 50-checkpoint original observation refutes the port's immediate,
weapon-sized monster damage. That explosion model is NOT fixed by this batch.
Full-game completion and original-fidelity claims remain zero.

## Capture Provenance

```sh
python3 tools/capture_original_monster_damage.py \
  --run-dir /tmp/lezac-impact-v2 \
  --out build-codex-tmp/monster-impact-original-v2.txt \
  --approve-procmem --approve-runtime-instrumentation
python3 tools/capture_original_monster_damage.py --bomb-order \
  --run-dir /tmp/lezac-impact-bomb-v3 \
  --out build-codex-tmp/bomb-order-original-v3.txt \
  --approve-procmem --approve-runtime-instrumentation
```

Both commands ran copied shipped assets in a private Xvfb/DOSBox child,
using startup/intro/level waits of 10/8/5 seconds. Repository assets were
not modified. The existing guarded actor-pass trampolines at Ghidra
`7EC5` and `7EEA` stop before and after the pass, preserve registers/flags
and replay displaced instructions. Seventeen instruction windows are
verified. Actual hooks: `01A2:7EC5`, `01A2:7EEA`; captured CS=01A2,
DS=0C44, ES=0C44, SS=18B3, saved-SP=3FE4, BP=3FFE. Registers are stored
at each checkpoint as `a201440c440cb318e43ffe3f`.

Actor rows: DS:1BAE, stride 38; visuals: DS:C21E, stride 8;
descriptors: DS:C322, stride 4. DS:C1FE supplies the object-plane segment;
DS:6612/6614 supplies the word-plane far pointer. Captured CS calibrates
the physical pointers. Level 1 is 60x33; all 1,980 object cells are sampled
as deltas from the initial map. Both map planes are restored only at case
boundaries. Spawners are disabled and queues are cleared at each boundary.
Player visual position 240,168 and all initial actor states are exogenous.
No actor or map state is reseeded between samples within a case.

Fixture SHA-256 values (LF bytes):

- `tests/fixtures/monster_damage_original.txt`:
  `d78783bc81c545ebe26b8ef26d015e482cdce80a5affd8ed6dde13a4b48e9bd5`.
- `tests/fixtures/bomb_actor_order_original.txt`:
  `1ff0d80e5274d1e522b1203f079588e68a0629b24b835f7bb63ba643cbd3e7f0`.
- Shipped EXE:
  `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

The first impact run seeded animation-set selectors +03/+04 as zero. A
later wall contact consequently selected the unrelated 93..100 range.
That run was rejected and recaptured with kind-1 selectors 1/2 and
kind-2/3/4 selectors 11/12/13, derived from DS:0058's table. A missing
temporary directory also caused a preflight failure, not a game failure.
The first corrected bomb comparison used opposite frame parities; the
promoted v3 capture deliberately starts both cases on odd frames.

## Impact Cases And Rules

Every case starts at visual X=336 with fractions X=9A, Y=4E, behavior 3,
mode-1 animation, counter equal to delay, and no source-spawner ownership.
Except the stationary repeated-hit case, motion starts airborne with VY=0.

| Cases | Kind | VX (8.8) | Delay | Raw HP | Visual Y |
| --- | --- | --- | --- | --- | --- |
| right_delay3 / left_delay3 | 1 | +2048 / -2048 | 3 | 31 | 98 |
| right_delay1 / right_delay4 / right_delay7 | 1 | +2048 | 1 / 4 / 7 | 31 | 98 |
| kind2 / kind3 / kind4 | 2 / 3 / 4 | +2048 | 3 | 31 | 98 |
| repeated_ground | 1 | 0 | 3 | 9 | 174 |
| fatal_air | 1 | +2048 | 3 | 0 | 98 |
| control_air | 1 | +2048 | 3 | 31 | 98 |

One glyph 75 is seeded inside the pre-motion 2x2 footprint, except for the
no-damage control. Fast motion naturally leaves that tile after one hit.
The ground case stays in the flame and dies on its fifth two-point hit.
The leftward case later reaches a wall and exercises facing reselection.

- Ghidra `745B..7483` selects the impact descriptor from
  `DS:[0077 + kind*2 + direction]`, using post-motion VX sign. The helper
  updates displayed sprite/hotspot without replacing the animation cursor.
- `7496..74A6` assigns the byte animation counter to `delay - 4`. The
  shared prologue increments that byte with wrap and advances only when
  the result exceeds the delay. C++ previously used an unbounded integer.
  Delay 3 rewinds to FF, wraps to zero next update, and holds the impact
  for five displayed states. Delay 1 instead rewinds to FD and exceeds
  the delay on its next increment, so its impact lasts one state. The
  delay-4/7 probes prevent replacing this arithmetic with a fixed hold.
- The living kind-1 impact sprites are 48 (right) and 47 (left), while
  kinds 2/3/4 use 42/52/56. The latter are now runtime-confirmed for
  nonfatal impact, not yet for their own full fatal/corpse lifecycles.
- At `74B5..74B9`, raw HP plus signed damage must be negative to kill.
  Raw zero remains alive until another hit. C++ therefore represents raw
  HP as `raw + 1` remaining health. Spawner `7BC2` stores the low byte of
  base-plus-random, so its C++ constructor now applies the byte conversion
  before adding one. The original RNG draw count/order is unchanged.
- The production damage helper applies the impact visual/counter before
  deciding survival or fatal conversion. Disabled animations do not tick.
  The previous corpse movement and phase-dependent death timer remain.

The replay initializes once per case and compares motion, both full fraction
words, kind/behavior, HP while living, timer, hotspot, all seven animation
bytes, displayed X/Y/descriptor, map deltas, actor count and RNG on every
update. Fatal raw HP is not compared to the port's zero remaining-health
sentinel. Four additional production-spawner/damage tests map raw bytes
0/1/2/255 to health 1/2/3/256 and verify survival at raw zero followed by
death below zero. These four boundary tests are byte-derived local tests,
not four extra original runtime captures.

## Explosion Model Refuted

The two bomb cases place a stationary kind-1 actor at 336,174, raw HP=31,
and a small bomb at 336,176, timer zero, behavior 2, hotspot 8. Visual slots
remain monster=2 and bomb=3. Only their shared actor ordering is swapped;
both cases start at odd frame parity with RNG=12345678 and restored terrain.
The bomb follows the original expiry routine, not a host-triggered blast.

Both target traces agree across 25 samples:

| Sample after expiry | Raw HP | Damage this update |
| --- | --- | --- |
| 0 | 31 | 0 |
| 1 | 31 | 0 |
| 2 | 27 | 4 |
| 3 | 21 | 6 |
| 4 | 19 | 2 |
| 5..24 | 19 | 0 |

The damage equals two for each glyph-75 cell in the stationary footprint
1302/1303/1362/1363. The bomb also converts to a fade and creates two moving
particles; four actors remain immediately after expiry. The current port's
single immediate `monsterDamageForBomb(Small) == 1` hit does not reproduce
these observations. Merely swapping `updateBombs` and `updateMonsters` cannot
supply the missing flame propagation and multi-update damage.

`check_bomb_actor_order_fixture.py` validates all 50 rows, map-based damage,
phase, actor bounds, target animation/descriptor agreement, and eight rejected
mutations. It explicitly reports `cpp_damage_claim=0`: it is an original
observation checker, not a passing C++ explosion replay. The legacy model is
now tracked as `bomb_direct_monster_damage` in the uncertainty inventory.

## Validation And Screenshots

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-monster-damage-original \
  tests/fixtures/monster_damage_original.txt build-codex-tmp/monster-impact-cpp-v2
python3 tools/check_death_transients_fixture.py --monster-damage --exe build/lezac_cpp
python3 tools/check_bomb_actor_order_fixture.py
```

The original replay initially failed on the first impact state. After the
fix, all 143 states and frames pass. LF/CRLF fixtures pass; missing completion
and a changed post-hit animation counter fail; default replay writes no frame
files. The spawner-cycle autoplayer now validates the zero-based HP mapping
and uses its existing synthetic blast path with a medium bomb to exercise
slot release. That route still does not claim original explosion damage.

Final CTest: 442 headless tests passed, one interactive test skipped, in
51.78 seconds. The separate interactive test passed in 3.69 seconds
(3.76 seconds total), covering all 443 tests across the two runs. Full log:
`build-codex-tmp/monster-impact-full-tests-passing.log`. The pre-existing
debris snprintf warning remains; a transient subsecond WSL clock-skew
warning during reconfiguration disappeared on the subsequent rebuild.

Original `monster-impact-original-v2_right_delay3_001.png` and C++
`monster-impact-cpp-v2/right_delay3_1.ppm` were inspected and shown together.
Both display the living impact sprite. DOSBox presents one actor pass behind
the stopped post-pass state, so the screenshots have a one-presentation-step
offset. Terrain/HUD differences remain. No pixel-parity claim is promoted.

## Next Recovery

Integrate the original live explosion-propagation records and their glyph-75
map writes, retirement, monster/player damage timing and bomb fade/particles.
Use the preserved ordered-bomb trace as an initial regression oracle, then
expand to all weapons and natural routes. Broader actor-pool ordering,
non-kind-1 fatal lifecycles, two-player interactions and death audio remain
open alongside the repository-wide completion work.
