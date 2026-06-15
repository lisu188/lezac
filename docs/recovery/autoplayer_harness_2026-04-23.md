# 2026-04-23 Autoplayer Harness

## Implemented Slice

The C++ port now has a deterministic `level1_bomb_route` autoplayer. It starts
one-player level 1, moves from the original start marker `(104,168)` to the
bomb-object route checkpoint at bomb tile `(24,22)`, places the bomb through the
same `N` key event path used by live controls, advances the fuse, and requires
visible frame changes through route, bomb, and explosion checkpoints.

The frame-sequence harness now uses this autoplayer route instead of directly
teleporting the player to tile `(24,22)`. This makes the frame sequence a
gameplay reachability check as well as a visual capture tool.

Additional deterministic autoplayer scenarios now cover:

- `death_reentry`: starts one-player level 1, forces a lethal hit through the
  same damage helper used in play, verifies state-2 countdown blocks early
  reentry, then confirms reentry after `60` ticks restores active control with
  lives and energy updated.
- `death_visuals`: verifies the live state-2 visual cursor starts
  at recovered frame `0x4a`, advances to `0x4b` on the first update, reaches
  `0x4c` on the fifth update, and changes the rendered frame at each checked
  point. The command reports `visual_claim=0` until paired original frames are
  promoted. It pins live row-byte-3 sprites `67,68,69` against the old
  cursor-index sprites `74,75,76`.
- `level_transition`: completes level 1 through deterministic map-progress
  helpers, inspects the completion overlay, advances the normal update loop for
  `101` frames, and verifies level 2 is loaded.
- `portal_weapon_route`: starts from live one-player input, switches from small
  to medium bombs through the left+right weapon chord, places the medium bomb
  through the `N` key path, then drives the first decoded portal source through
  the normal update loop and checks the recovered portal sound/cooldown fields.
- `records_flow`: drives the high-score name-entry path into a temporary record
  file, enters `bot`, reloads the file, and verifies the records page displays
  the saved score without touching shipped `RECS.DAT`.
- `monster_bomb_reward`: places a bomb through `N`, detonates it against a
  deterministic live monster fixture, verifies the death/reward state, then
  collects the spawned bonus through the normal update loop.
- `monster_behavior3_multihit`: uses a synthetic grounded fixture to verify a
  live behavior-3 walker advances before taking damage, survives the first
  small-bomb hit, dies to the second medium-bomb hit, and yields a collectible
  reward.
- `monster_behavior4_chase`: uses a synthetic fixture to verify a live
  behavior-4 chaser advances toward the player before a medium bomb kills it.
- `monster_spawner_cycle`: uses the actual level-1 spawner to verify slot
  reservation on spawn, immediate slot return on death, and deterministic
  respawn after resetting the recovered spawner cooldown.
- `monster_spawner_behavior4_level2`: uses the actual level-2 behavior-4
  spawner, locks the decoded AI/hit-point fields into deterministic ranges,
  and verifies horizontal chase velocity through the live update loop.
- `monster_spawner_behavior4_level3`: uses the actual level-3 behavior-4
  spawner, locks the decoded AI/hit-point fields into deterministic ranges,
  and verifies diagonal chase velocity through the live update loop.
- `monster_behavior4_target_selection`: starts two-player mode on level 3 and
  verifies that a live behavior-4 spawner first targets the nearer player 2,
  retargets player 1 when player 2 is dead, and retargets player 2 again when
  player 1 is dead.
- `collapse_playback_route`: reaches level-1 bomb tile `(24,22)` through the
  route autoplayer, places the route bomb through `N`, verifies collapse queue
  creation, and checks the current `24`-frame playback lifetime.
- `two_player_route`: starts two-player mode, moves player 2 independently,
  places a player-2 bomb through the shared bomb helper, and verifies player 1
  did not move.
- `two_player_progression`: moves both players, kills and reenters player 2
  through the recovered state-2 gate, places a player-2 bomb after reentry, and
  verifies a player-2 objective pickup increments only player 2's score.

## Route Evidence

- Autoplayer route start: `p1_xy=104,168`.
- Autoplayer target: `p1_bomb_tile=24,22`.
- Current deterministic route length: `55` update frames.
- Captured route checkpoint: `020_level1_tile24_aligned.ppm`.
- Captured bomb checkpoint: `030_level1_tile24_bomb.ppm`.
- Captured explosion checkpoint: `040_level1_tile24_explosion.ppm`.

The route relies on the current cell-aware passable-object model. Portal tile
`0x45` and bomb-object tiles `0x67..0x72` are passable by tile id, and nonzero
undamaged low word-layer object cells are passable by cell metadata. High
word-layer floor/link markers remain solid unless their tile id is already a
known passable object.

## Verification Commands

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer level1_bomb_route

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer death_reentry

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer death_visuals

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer level_transition

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer portal_weapon_route

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer records_flow

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer monster_bomb_reward

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer monster_behavior3_multihit

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer monster_behavior4_chase

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer monster_spawner_cycle

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer monster_spawner_behavior4_level2

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer monster_spawner_behavior4_level3

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer monster_behavior4_target_selection

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer collapse_playback_route

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer two_player_route

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer two_player_progression

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --capture-frame-sequence level1_bomb_route /tmp/lezac-cpp-frames
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --capture-frame-sequence monster_spawner_behavior4_level2 /tmp/lezac-cpp-b4-level2
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --capture-frame-sequence monster_spawner_behavior4_level3 /tmp/lezac-cpp-b4-level3
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --capture-frame-sequence monster_behavior4_target_selection /tmp/lezac-cpp-b4-target
```

`--debug-autoplayer` performs frame inspection internally. The
`--capture-frame-sequence` command writes PPM frames plus `manifest.txt`; use
the manifest hashes and scenario metadata for CI/debug evidence, and inspect or
compare the images when working on presentation fidelity.

`tools/capture_original_dosbox_frames.sh /tmp/lezac-original-frames .` now tries
to produce the original `LEZAC.EXE` version of the same semantic level-1 route
labels and records timing/input settings in `manifest.txt`. This remains the
only automated original-side frame route. It is only an oracle after frame
inspection. Local Xvfb/xdotool runs showed the old `--window` key path could
remain on the menu, while the focused no-window path with two `1` taps reached
level 1. The route now defaults to the original player-1 controls (`x` for
right and `n` for fire) and records those settings in the manifest. Treat any
menu-stuck or no-bomb frame set as an automation limit, not as gameplay
evidence, and rerun with adjusted `LEZAC_ORIGINAL_*` settings when using
original frames for comparison.

## Open Uncertainty

This locks the current C++ route and frame-harness behavior. Exact original
collision/passability around `1000:6053..777f` still needs DOSBox or debugger
evidence before the low-word passable-object rule can be called fully
original-faithful. The death/reentry, provisional state-2 visual, records,
level-transition, and two-player autoplayer scenarios are regression coverage
for the current C++ behavior; exact presentation and edge-case timing still
need original runtime confirmation.
