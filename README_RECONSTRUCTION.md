# Larax & Zaco C++ Reconstruction

This directory now contains a C++17/SDL2 source reconstruction of
`LEZAC.EXE`, the DOS shareware game released as "Larax & Zaco" 1.0 in 1996.

This is not a mechanical C decompiler output. The original is a 16-bit
Borland/Turbo Pascal MZ executable, so the port is written as maintainable C++
from Ghidra-assisted disassembly, original strings, original docs, and the
companion data files.

## Build

```sh
cmake -S . -B build
cmake --build build
```

Run from this directory so the converted JSON resources are found:

```sh
./build/lezac_cpp
```

Validate every decoded original data file without opening a window:

```sh
./build/lezac_cpp --validate
```

Smoke-test SDL window creation and menu/control handling:

```sh
./build/lezac_cpp --smoke-ui 3
./build/lezac_cpp --smoke-controls
```

Run the configured validation, debug, and UI smoke tests:

```sh
ctest --test-dir build --output-on-failure
```

Export the decoded background as an indexed-color PPM preview:

```sh
./build/lezac_cpp --export-background /tmp/sfonlef.ppm
```

Dump the current bomb inventory model and export sprite contact sheets:

```sh
./build/lezac_cpp --debug-bombs
./build/lezac_cpp --debug-bonuses
./build/lezac_cpp --debug-fixed
./build/lezac_cpp --debug-sounds
./build/lezac_cpp --debug-sound-render
./build/lezac_cpp --debug-sound-cursor-segments
./build/lezac_cpp --debug-son-raw-roundtrip
./build/lezac_cpp --debug-sound-priority-latch
./build/lezac_cpp --debug-sound-selector-map
./build/lezac_cpp --debug-record-update /tmp/records_test.dat
./build/lezac_cpp --debug-record-name-entry /tmp/records_name_test.dat
./build/lezac_cpp --debug-record-save-failure /tmp/missing-record-dir/records.dat
./build/lezac_cpp --debug-end-flow-records /tmp/end_flow_records.dat
./build/lezac_cpp --debug-gran
./build/lezac_cpp --debug-levels
./build/lezac_cpp --debug-level-raw-roundtrip
./build/lezac_cpp --debug-sprite-transparency
./build/lezac_cpp --debug-word-layer
./build/lezac_cpp --debug-spawners
./build/lezac_cpp --debug-explosions
./build/lezac_cpp --debug-damage-queues
./build/lezac_cpp --debug-monster-slots
./build/lezac_cpp --debug-monster-blast-damage
./build/lezac_cpp --debug-bomb-fuse
./build/lezac_cpp --debug-passable-objects
./build/lezac_cpp --debug-trigger-accounting
./build/lezac_cpp --debug-trigger-sound
./build/lezac_cpp --debug-portal-sound
./build/lezac_cpp --debug-portal-cooldowns
./build/lezac_cpp --debug-collision-pushout
./build/lezac_cpp --export-sprites BOMOMIMK.SPR /tmp/bomomimk.ppm
```

## Implemented

- VGA palette loading from `BOMPAL.PAL` and `SFONLEF.ZBG`.
- `SFONLEF.ZBG` PCX-style RLE background decoding as a 321x388 image.
- `CARO.CAR` 132-tile 8x8 tile bank loading.
- `FONTS.SPR`, `PROVA.SPR`, and `BOMOMIMK.SPR` sprite-bank loading.
- Text rendering from the original `FONTS.SPR` glyph sprites.
- `RECS.DAT` high-score parsing as score, reached level, and colon-padded
  8-byte player name.
- `PROEFS.SON` parsing as a fixed-size sound-effect bank and `GRAN.MST`
  parsing as seven fixed-size opaque records.
- `LIVELS.SCH` seven-level parsing with the Ghidra-confirmed 3-byte level RLE,
  decoded word layer, monster spawner records, portal/start records, and tile
  trigger rules.
- A playable one-player reconstruction loop using original maps and graphics:
  movement, jumping, objective collection, bomb placement, tile destruction,
  score, start positions, teleports, tile triggers, monster spawning, basic
  behavior-specific monster movement/damage, documented monster reward drops,
  spawner live-slot return after monster death animation removal,
  bomb-power damage against monster hit points,
  four-slot bomb inventory/switching, original bomb actor sprites, player
  animation, active structure hazard damage, bomb blast player damage,
  post-hit damage cooldown, level progression, and records/menu display.
- Menu subpages for info, instructions, and records, plus original-documented
  background and one-player playfield-width controls.
- A first playable two-player reconstruction pass with separate start markers,
  separate controls, split camera views, a central objective panel, per-player
  bomb inventories/HUD/score state, zero-life player-out handling, shared
  objectives, player-2 bomb placement through the `N` fire key, and queued
  per-player high-score prompts at end of run.
- High-score table serialization back to the converted `RECS.DAT.json` resource
  format, name entry for new records with original-evidence letters/space,
  Backspace, and Enter handling, and validation coverage that writes only to
  temporary test files.
- Game-over and completed-game end states using strings recovered from
  `1000:1b14..1d42`, with final-level completion entering the completed-game
  path instead of wrapping directly into level 1.
- `PROEFS.SON` payload bytes are preserved as the original 130 six-byte
  playback steps. Non-direct sound synthesis now advances by the recovered
  `DS:78c0` cursor, honors the `0x7530` stop sentinel, and applies the
  gate/period bytes used by `1000:0fbe..1088`. Bomb explosion requests use the
  recovered direct-sweep cursors and the original `1000:165a` priority latch,
  bomb-object destruction queues the recovered priority-`3` object cue, portal
  transfer queues cursor `0x001a` at priority `4`, tile-trigger activation
  queues cursor `0x0027` at priority `6`, and bonus pickup audio queues cursor
  `0x0008` at priority `5`.

## Still Approximate

- Monster spawners now create active enemies with original-style 8.8 motion, but
  behavior-specific AI and collision remain implemented hypotheses pending
  deeper reconstruction of the actor update routine around `1000:6053`.
- PC speaker sound effects now use a recovered request/priority latch,
  direct-sweep path for bomb explosions, and six-byte cursor stepping for
  `PROEFS.SON`, but bytes `+4..+5` in each sound step and many non-explosion
  callsite-to-event mappings remain unresolved.
- Two-player split-screen is playable with independent bomb inventories, scores,
  and record prompts, but exact original panel artwork and reentry presentation
  remain approximate.
- High scores are persisted with original-evidence name-entry keys
  (letters/space, Backspace, Enter), but exact cursor drawing, typematic repeat,
  and name-entry presentation remain approximate.
- Bomb fuse timing, 2x2 footprint, player blast damage, monster hit-point
  blast damage, visual
  selectors, actor sprite indices, and word-layer damage gating now follow the
  `1000:414a`/`1000:370e`/expiration analysis. Active collapse/debris records
  now drain player energy with a short post-hit cooldown, but exact sprite
  playback and per-frame damage timing remain simplified.

See [docs/GHIDRA_NOTES.md](docs/GHIDRA_NOTES.md) for addresses and disassembly
anchors used in the reconstruction.
