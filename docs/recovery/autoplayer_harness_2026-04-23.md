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
- `death_visuals`: verifies the live provisional state-2 visual cursor starts
  at recovered frame `0x4a`, advances to `0x4b` on the first update, reaches
  `0x4c` on the fifth update, and changes the rendered frame at each checked
  point. The command reports `visual_claim=0` until the original frame-table
  fields are fully interpreted.
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
  ./build/lezac_cpp --debug-autoplayer collapse_playback_route

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer two_player_route

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer two_player_progression

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --capture-frame-sequence level1_bomb_route /tmp/lezac-cpp-frames
```

`--debug-autoplayer` performs frame inspection internally. The
`--capture-frame-sequence` command writes PPM frames plus `manifest.txt`; use
the manifest hashes and route metadata for CI/debug evidence, and inspect or
compare the images when working on presentation fidelity.

`tools/capture_original_dosbox_frames.sh /tmp/lezac-original-frames .` now tries
to produce the original `LEZAC.EXE` version of the same semantic level-1 route
labels and records timing/input settings in `manifest.txt`. This is only an
oracle after frame inspection. In local Xvfb/xdotool runs the script produced
named DOSBox screenshots, but the injected menu key did not reliably enter
gameplay, so the frames stayed on the menu. Treat that as an automation limit,
not as gameplay evidence, and rerun with adjusted `LEZAC_ORIGINAL_*` settings
when using original frames for comparison.

## Open Uncertainty

This locks the current C++ route and frame-harness behavior. Exact original
collision/passability around `1000:6053..777f` still needs DOSBox or debugger
evidence before the low-word passable-object rule can be called fully
original-faithful. The death/reentry, provisional state-2 visual, records,
level-transition, and two-player autoplayer scenarios are regression coverage
for the current C++ behavior; exact presentation and edge-case timing still
need original runtime confirmation.
