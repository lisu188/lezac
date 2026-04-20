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

Run from this directory so the original asset files are found:

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

Run the configured validation and UI smoke tests:

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
./build/lezac_cpp --debug-fixed
./build/lezac_cpp --debug-sounds
./build/lezac_cpp --debug-sound-render
./build/lezac_cpp --debug-gran
./build/lezac_cpp --debug-levels
./build/lezac_cpp --debug-word-layer
./build/lezac_cpp --debug-spawners
./build/lezac_cpp --debug-explosions
./build/lezac_cpp --debug-damage-queues
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
  four-slot bomb inventory/switching, original bomb actor sprites, player
  animation, level progression, and records/menu display.
- Menu subpages for info, instructions, and records, plus original-documented
  background and one-player playfield-width controls.
- A first playable two-player reconstruction pass with separate start markers,
  separate controls, split camera views, a central objective panel, per-player
  bomb inventories/HUD state, shared objectives, and player-2 bomb placement
  through the `N` fire key.
- High-score table serialization back to the original `RECS.DAT` record format,
  name entry for new records, and validation coverage that writes only to
  temporary test files.
- `PROEFS.SON` records synthesize SDL-queued PC-speaker-style square-wave sound
  effects for core gameplay events, with headless render validation.

## Still Approximate

- Monster spawners now create active enemies with original-style 8.8 motion, but
  behavior-specific AI and monster collision/damage remain approximate pending
  deeper reconstruction of the actor update routine around `1000:6053`.
- PC speaker sound effects now play through an approximate square-wave
  sequencer; exact original timing and tone-field semantics remain unresolved.
- Two-player split-screen is playable with independent bomb inventories and a
  central objective panel, but exact original panel artwork, reentry/game-over
  flow, and scoring semantics remain approximate.
- High scores are persisted with name entry, but exact original record-entry
  presentation and keyboard editing semantics remain approximate.
- Bomb fuse timing, 2x2 footprint, actor sprite indices, visual selectors, and
  word-layer damage gating now follow the
  `1000:414a`/`1000:370e`/expiration analysis, but the exact sprite playback for
  explosion and collapse/debris animations is still simplified.

See [docs/GHIDRA_NOTES.md](docs/GHIDRA_NOTES.md) for addresses and disassembly
anchors used in the reconstruction.
