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
  ./build/lezac_cpp --capture-frame-sequence level1_bomb_route /tmp/lezac-cpp-frames
```

`--debug-autoplayer` performs frame inspection internally. The
`--capture-frame-sequence` command writes PPM frames plus `manifest.txt`; use
the manifest hashes and route metadata for CI/debug evidence, and inspect or
compare the images when working on presentation fidelity.

## Open Uncertainty

This locks the current C++ route and frame-harness behavior. Exact original
collision/passability around `1000:6053..777f` still needs DOSBox or debugger
evidence before the low-word passable-object rule can be called fully
original-faithful.
