# Behavior-4 Level-3 Runtime Motion

Captured 2026-08-10; replay and frame review completed 2026-09-05.

## Observation Method

Both runs used the original LEZAC.EXE in a temporary asset copy, a private
Xvfb display and DOSBox through `tools/seed_original_level.py`. The seeder
reached level 3 through the native result/reload flow by writing objective
counters. It did not replace actor or spawner tables. Once the shipped kind-2
behavior-4 actor appeared, the sampler collected 80 natural ticks, followed
by 80 ticks with player 1 deliberately repositioned near that actor.

Commands used after preparing the temporary asset copy:

```sh
python3 tools/capture_original_behavior4_lockstep.py \
  --run-dir /tmp/lezac-b4-level3-20260810-a \
  --out-dir /tmp/lezac-b4-lockstep-20260810-a \
  --approve-procmem --approve-runtime-instrumentation
python3 tools/capture_original_behavior4_lockstep.py \
  --run-dir /tmp/lezac-b4-level3-20260810-a \
  --out-dir /tmp/lezac-b4-lockstep-20260810-b \
  --near-dx 40 --near-dy 20 \
  --approve-procmem --approve-runtime-instrumentation
```

Each detected `DS:78C2` change triggers one 64 KiB `/proc/<pid>/mem` pread.
This minimizes cross-table skew but is not an atomic emulator stop. The
replay validates the relevant motion transitions, not whole-machine
coherence. Runtime DS `0c8f` is signature-derived. CS, ES, SS and IP were not
measured; these runs do not claim debugger breakpoint/register evidence.

The actor table is `DS:1BAE`, stride `0x26`; visual rows are `DS:C21E`, stride
8; RNG is `DS:1AFE`. Both fixtures follow actor slot 2, visual slot 3, kind 2,
behavior 4, source spawner 2 and hotspot 0. Raw actor bytes accompany every
decoded row. The sampler now always emits candidates requiring independent
review, even when sampling succeeds.

## Preserved Captures

Hashes below are SHA-256 of ASCII text with LF-normalized newlines.

| Fixture under `tests/fixtures` | Frames | Near offset | ai0 / ai1 / ai2 / hp |
| --- | --- | --- | --- |
| `behavior4_lockstep_original_level3_horizontal.txt` | 299..458 | 40,0 | 14 / 469 / 75 / 2 |
| `behavior4_lockstep_original_level3.txt` | 298..457 | 40,20 | 16 / 494 / 79 / 4 |

- Horizontal: `d5258bcc3464351324c257e72cb52666a0ca28e85ef9da3f74bb5a0d34ff9e4a`
- Diagonal: `d2bd2d27b298950ccb4ad40aeace8e543f3eed3c13b03f82ffdaf92e9cf77d59`

Each has 160 consecutive rows. The fixture guard checks both hashes, six
shipped executable windows and seven malformed-fixture rejection cases.

## Recovered Rules

- `1000:70D7` uses the global 16-bit frame modulo `ai0`. The previous row's
  frame determines the update producing the next row. New actors wait with
  zero velocity; no spawn-time steering draw is made.
- Strict Manhattan distance `< ai2` selects Euclidean-normalized homing.
  Conversion truncates toward zero: speed 494 at delta (40,20) yields
  (441,220), not (442,221).
- Far steering draws X, then Y, as `Random(2*ai1)-ai1`. Five target gates in
  each capture match the shared RNG exactly. Other actors/spawns also advance
  the global RNG: nine natural seed changes are not nine target retargets.
- The horizontal trace includes one off-gate top collision, frame 357->358,
  changing vy -416->1 while vx stays 402. All fractional carries persist.
- The static arm at `7062..70B9` reflects positive vy off strong bottom cells
  (tiles 1..0x4C), or zeroes it if top and strong bottom both contact, BEFORE
  steering. Common top/side response then precedes Y and X 8.8 integration.
  Behavior 4 gets neither gravity nor behavior-3 facing reselection.

The dedicated diagnostic replays all 159 transitions per fixture through
production `updateMonsters`, checking x/y, vx/vy and both fractions. It checks
production RNG at every isolated target gate and every unchanged-seed row;
off-gate global seed changes from other actors are excluded. Horizontal
homing contributes six gates and diagonal homing five.

Near-phase inputs are the coordinates actually injected after the previous
row: previous actor position plus `near_offset`. They are not the later
sampled player coordinates. Each transition is reinitialized from original
state, so this is bounded actor-motion replay, not whole-game lockstep.

## Frame Inspection

The three preserved original PNGs show the level-3 start and the two seeded
near-player views with visible kind-2 flyers. The C++ PNG shows the level-3
deterministic spawn/retarget checkpoint, including the player, flyer, terrain
and HUD. All four were inspected, with no blank or missing game surface.

- [Original level start](behavior4_2026-08-10/original-level3.png)
- [Original horizontal near phase](behavior4_2026-08-10/original-near.png)
- [Original diagonal near phase](behavior4_2026-08-10/original-near-diagonal.png)
- [C++ level-3 checkpoint](behavior4_2026-08-10/cpp-level3-spawned.png)

The C++ frame-harness manifest records hash `0x914f3b72fb5bc2ae`, actor
position (353,47), velocity (283,-200), behavior 4, hp 4, spawner 2, sprite 39
and player position (376,31). Its scenario has an explicitly seeded target
and uses actor-only updates while waiting for the shared retarget gate.
These screenshots are not synchronized original/C++ checkpoints and cannot
establish pixel parity or animation timing.

## Validation and Remaining Scope

```sh
cmake --build build -j 2
ctest --test-dir build --output-on-failure --timeout 120
ctest --test-dir build -R behavior4 --output-on-failure --timeout 120
```

Full suite: 403/403 passed. Focused behavior-4 suite after final replay
safeguards: 34/34 passed, including both original captures and deterministic
level-2, level-3 and two-player frame/autoplayer regressions.

`behavior4_motion_runtime_fixture` remains open. This evidence does not settle
two-player target selection, every kind/level, spawn RNG parameter generation,
full floor/side collision runtime coverage, damage or animation parity. The
floor/side implementation additionally uses pinned disassembly and synthetic
collision tests. `visual_claim=0` and `original_fidelity_claim=0` are unchanged.
