# Original Monster Coordinate Writeback

## Health Attribution Correction

The later [full tile-damage recovery](monster_tile_damage_runtime_2026-10-04.md)
corrects the historical HP labels: compact byte +3 = 11 is not health.
The retained native health seed is actor +0x24 = 255. The old diagnostic used
HP 11 without exposing damage; it now uses HP 256 and checks unchanged health.
Historical fixtures, capture snapshots and receipts remain immutable.

Two independent silent original captures agree on 256 complete behavior-4
motion/writeback cases. Production `updateMonsters()` initially disagreed at
exactly the 112 positions outside its level-bound clamps; removing those two
clamps makes all 256 cases match. This does not establish whole-game fidelity.

## Original Observation

The actor-phase gate is `1000:7EC5`, the before-motion hook is `1000:7062`, and
the final hook is `1000:777F`, immediately before `LEAVE; RET 4`. Unlike the
preceding motion fixture's `741E` stop, this probe includes generic damage and
the actual visual/actor writeback at `7530`. It retains both decoded locals and
the raw 38-byte actor and 8-byte visual records after the stores.

The matrix is eight kinds (1..8), two positions `(448,240)` and `(24,24)`, and
every VX/VY combination from `{-32768,-256,0,32767}`: 256 cases. All use behavior
4, fractions 165/90, frame 421 (off the steering gate), AI values 14/271/75,
HP 11, hotspot zero and descriptor/animation 40..42. These are explicit shared
profiles, not assertions about each shipped constructor. Pre-motion terrain
and its word plane are empty; every observed edge flag is zero.

Examples from the actual original stores:

| Seed | VX/VY | Stored X/Y | Stored Fractions |
| --- | --- | --- | --- |
| 448,240 | 32767,32767 | 576,368 | 164,89 |
| 24,24 | -32768,-32768 | -104,-104 | 165,90 |
| 448,240 | -32768,-32768 | 320,112 | 165,90 |
| 24,24 | 32767,32767 | 152,152 | 164,89 |

The original does not replace these results with `[0,464]` / `[0,248]`. The
visual words agree with the final locals, and the complete actor records agree
with the seed except for the observed velocity/fraction stores and animation
counter advance to one. HP, kind, behavior and AI fields remain unchanged.

The observer reuses the existing flag/register/stack-preserving trampoline and
actor-pointer/behavior guard. It checks the original image, relocated runtime
windows and both affected far-call relocations before instrumentation. Only
explicit case boundaries seed inputs; no results or individual instructions
are overwritten. Each owned child is closed after verified hook/scratch
restoration. All launches, descendants, tests and replay use dummy audio.

## Production Correction

The diagnostic commit `ed1615e3b56a9f9a620ef9c2228932a4b2051a8e` retains the old
production clamps. Its new production replay fails at exactly the 112 fixture
rows whose native positions exceed those bounds; the other 144 match.

The correction removes only the two level-bound clamps after monster motion
integration. Terrain scans, gravity, steering, side/top responses, fractional
integration, animation, contact/damage order, corpse/timed paths and boss motion
helpers are otherwise unchanged. The common original writeback stores the
coordinates directly instead of applying a level rectangle at this point.

The fixed production replay checks all 256 X/Y, VX/VY, fractional bytes, RNG,
HP and animation-counter results, actor kind/behavior and unchanged visible
frame/cursor. Exactly 112 results remain outside the former bounds.

## Fixture And Retention

- Fixture size: 8,256 bytes, with a 64-byte header and 256 32-byte records.
- SHA256: `23008c501c6e0091d3033022d0e496a45db87ed45b4c10761913158b53708e45`.
- Production FNV1a64: `11797946e69036ce`.
- Record format: `<HBBhhhhBBHhhhhBBIBB`, covering index/kind/profile, seeded
  position/velocity/fractions/frame, observed position/velocity/fractions/RNG,
  and written HP/animation counter.
- Negative binary SHA256:
  `6601ec22f4fe5660586e30c344ef89faf320508cc9dbd00b46c103b51d592ded`.
- Initial corrected binary SHA256 (before the synthetic-fixture adjustment below):
  `c99367a9c2773db8c9bb9f90ee35bfa690e247411ec0364febcd0c3dd0f41c99`.

Both complete original captures and failed-before/fixed-after diagnostics are
retained in the [27-member, byte-verified archive](evidence/monster_writeback_20261004/README.md).
The positive build receipt identifies its source-file hash and the uncommitted
fix relative to the diagnostic commit, not an incorrectly claimed clean HEAD.
The initial two 16-case discovery probes remain in the separately retained
Git-notes capsule linked from PR #273; the expanded fixture supersedes neither
their raw evidence nor their limited original-only scope.

Six CTests check production replay, pinned fixture/instructions, every one of
8,256 single-byte fixture mutations, extent/original mutations, 18 malformed
production inputs, observer self-check and complete archive provenance. The
portable native workflow independently recaptures and validates the fixture.

The initial 135-test local run passed 134 checks and failed the synthetic
`monster_bomb_kill_live` scenario. Its seeded X=88 lay beyond the 12-tile room's
last fully supported actor column; the old clamp pulled it back over the bomb.
The diagnostic now seeds X on the bomb's own column (80). No production rule or
damage/timer/reward/RNG/frame expectation was weakened: it still kills at update
14, uses corpse sprite 47 for 50 ticks, collects the same reward for 2,000
points, and inspects 20 frames. The original-backed 256-case fixture is unchanged.
The complete 135-test focused suite then passed, including all six new gates
and existing actor/contact, walker/flyer, boss, capacity and frame-capture checks.

A fresh C++ extended boss replay independently matches 3,200 updates and all
15 native view crops (711,360 pixels), including defeat at sample 1714 and
cleanup at 1833. Its checkpoint 1599 reproduces the retained original/C++ PNGs
exactly at their integer 3x preview scale. The original is a retained controlled
capture, not a fresh DOSBox boss run or a natural campaign route. The first
preview audit incorrectly assumed native-size PNGs; inspecting the dimensions
resolved that format-assumption failure without changing any pixel comparator.

## Remaining Scope

These seeded one-update cases do not prove natural trajectories or spawning,
shipped profiles for all kinds, next-update out-of-map reads, coordinate-word
overflow, complete damage/animation behavior, all-level progression or global
visual parity. In particular, the C++ tile accessor's out-of-map behavior is not
established by these in-bounds pre-motion scans. No claim about it was added.

The correction affects the common post-motion clamp site; separate motion
helpers are unchanged. Existing controlled boss/campaign checks remain separate
evidence and must pass without weakening expectations. All four OPEN recovery
items and `original_fidelity_claim=0`, `visual_claim=0`, and
`port_functionally_complete=0` remain unchanged.
