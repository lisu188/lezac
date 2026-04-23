# 2026-04-23 Autoplayer Harness

## Implemented Slice

The C++ port now has a deterministic `level1_bomb_route` autoplayer. It starts
one-player level 1, moves from the original start marker `(104,168)` to the
bomb-object route checkpoint at bomb tile `(24,22)`, places a bomb with the same
placement helper used by controls, advances the fuse, and requires visible frame
changes through route, bomb, and explosion checkpoints.

The frame-sequence harness now uses this autoplayer route instead of directly
teleporting the player to tile `(24,22)`. This makes the frame sequence a
gameplay reachability check as well as a visual capture tool.

Additional deterministic autoplayer scenarios now cover:

- `death_reentry`: starts one-player level 1, forces a lethal hit through the
  same damage helper used in play, verifies state-2 countdown blocks early
  reentry, then confirms reentry after `60` ticks restores active control with
  lives and energy updated.
- `records_flow`: drives the high-score name-entry path into a temporary record
  file, enters `bot`, reloads the file, and verifies the records page displays
  the saved score without touching shipped `RECS.DAT`.
- `two_player_route`: starts two-player mode, moves player 2 independently,
  places a player-2 bomb through the shared bomb helper, and verifies player 1
  did not move.

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
  ./build/lezac_cpp --debug-autoplayer records_flow

env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer two_player_route

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
original-faithful. The death/reentry, records, and two-player autoplayer
scenarios are regression coverage for the current C++ behavior; their exact
presentation and edge-case timing still need original runtime confirmation.
