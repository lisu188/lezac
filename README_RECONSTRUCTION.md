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

Dump deterministic C++ frames for comparison against original DOSBox captures:

```sh
./build/lezac_cpp --debug-autoplayer level1_bomb_route
./build/lezac_cpp --capture-frame-sequence level1_bomb_route /tmp/lezac-cpp-frames
./build/lezac_cpp --capture-frame-sequence monster_spawner_behavior4_level2 /tmp/lezac-cpp-b4-level2
./build/lezac_cpp --capture-frame-sequence monster_spawner_behavior4_level3 /tmp/lezac-cpp-b4-level3
./build/lezac_cpp --capture-frame-sequence monster_behavior4_target_selection /tmp/lezac-cpp-b4-target
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-frames level1_bomb_route
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
./build/lezac_cpp --debug-son-step-fields
./build/lezac_cpp --debug-sound-priority-latch
./build/lezac_cpp --debug-sound-selector-map
./build/lezac_cpp --debug-player-damage-sound
./build/lezac_cpp --debug-original-damage-counters
./build/lezac_cpp --debug-level1-frame-inspection
./build/lezac_cpp --debug-autoplayer level1_bomb_route
./build/lezac_cpp --debug-autoplayer death_reentry
./build/lezac_cpp --debug-autoplayer death_visuals
./build/lezac_cpp --debug-autoplayer level_transition
./build/lezac_cpp --debug-autoplayer portal_weapon_route
./build/lezac_cpp --debug-autoplayer records_flow
./build/lezac_cpp --debug-autoplayer monster_bomb_reward
./build/lezac_cpp --debug-autoplayer monster_behavior3_multihit
./build/lezac_cpp --debug-autoplayer monster_behavior4_chase
./build/lezac_cpp --debug-autoplayer monster_spawner_cycle
./build/lezac_cpp --debug-autoplayer monster_spawner_behavior4_level2
./build/lezac_cpp --debug-autoplayer monster_spawner_behavior4_level3
./build/lezac_cpp --debug-autoplayer monster_behavior4_target_selection
./build/lezac_cpp --debug-autoplayer collapse_playback_route
./build/lezac_cpp --debug-autoplayer two_player_route
./build/lezac_cpp --debug-autoplayer two_player_progression
./build/lezac_cpp --debug-player-state2-death-fields
./build/lezac_cpp --debug-original-state2-return-model
./build/lezac_cpp --debug-original-state2-animation-init
./build/lezac_cpp --debug-original-state2-animation-advance
./build/lezac_cpp --debug-state2-runtime-frame-oracle tests/fixtures/dosbox/state2_runtime_frame_oracle_synthetic.txt
./build/lezac_cpp --debug-state2-runtime-frame-oracle tests/fixtures/dosbox/state2_runtime_frame_oracle_original.txt
./build/lezac_cpp --debug-explosion-playback-oracle tests/fixtures/dosbox/explosion_playback_oracle_synthetic.txt
./build/lezac_cpp --debug-original-state2-effect-placement
./build/lezac_cpp --debug-player-state2-return-active
./build/lezac_cpp --debug-record-update /tmp/records_test.dat
./build/lezac_cpp --debug-record-name-entry /tmp/records_name_test.dat
./build/lezac_cpp --debug-record-save-failure /tmp/missing-record-dir/records.dat
./build/lezac_cpp --debug-end-flow-records /tmp/end_flow_records.dat
./build/lezac_cpp --debug-gran
./build/lezac_cpp --debug-gran-raw-roundtrip
./build/lezac_cpp --debug-levels
./build/lezac_cpp --debug-level-raw-roundtrip
./build/lezac_cpp --debug-sprite-transparency
./build/lezac_cpp --debug-sprite-raw-roundtrip
./build/lezac_cpp --debug-sprite-blit-contract
./build/lezac_cpp --debug-word-layer
./build/lezac_cpp --debug-spawners
./build/lezac_cpp --debug-explosions
./build/lezac_cpp --debug-damage-queues
./build/lezac_cpp --debug-monster-slots
./build/lezac_cpp --debug-monster-motion-model
./build/lezac_cpp --debug-monster-blast-damage
./build/lezac_cpp --debug-bomb-fuse
./build/lezac_cpp --debug-passable-objects
./build/lezac_cpp --debug-trigger-accounting
./build/lezac_cpp --debug-trigger-sound
./build/lezac_cpp --debug-portal-sound
./build/lezac_cpp --debug-portal-cooldowns
./build/lezac_cpp --debug-collision-pushout
./build/lezac_cpp --capture-frame-sequence level1_bomb_route /tmp/lezac-cpp-frames
./build/lezac_cpp --capture-frame-sequence monster_spawner_behavior4_level2 /tmp/lezac-cpp-b4-level2
./build/lezac_cpp --capture-frame-sequence monster_spawner_behavior4_level3 /tmp/lezac-cpp-b4-level3
./build/lezac_cpp --capture-frame-sequence monster_behavior4_target_selection /tmp/lezac-cpp-b4-target
./build/lezac_cpp --export-sprites BOMOMIMK.SPR /tmp/bomomimk.ppm
```

## Frame Comparison

The reconstruction can emit named 320x200 PPM frames and a `manifest.txt` for
deterministic gameplay scenarios. Current built-in frame exports cover
`level1_bomb_route`, `monster_spawner_behavior4_level2`,
`monster_spawner_behavior4_level3`, and
`monster_behavior4_target_selection`. The level-1 route sequence captures the
menu, level-1 start, the deterministic autoplayer reaching bomb tile `(24,22)`,
bomb placement, and three explosion/playback checkpoints. The behavior-4
sequences capture spawn/retarget checkpoints plus manifest metadata for player
state and first-monster position/velocity/behavior.

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer level1_bomb_route
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-frames level1_bomb_route
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-b4-level2 monster_spawner_behavior4_level2
```

Original-game captures are best-effort because DOSBox timing, focus, and
keyboard injection vary by environment. The current DOSBox screenshot driver is
still route-specific: it runs `LEZAC.EXE` from a temporary copy under
DOSBox/Xvfb, uses DOSBox's Ctrl-F5 screenshot command at matching level-1 route
checkpoints, renames the screenshots to the same semantic labels used by the
C++ route sequence, and writes `manifest.txt` and `original_capture.log` next
to the screenshots:

```sh
tools/capture_original_dosbox_frames.sh /tmp/lezac-original-frames .
```

Always inspect the resulting original frames before comparing them. If local
DOSBox input stays on the menu or misses a checkpoint, rerun with adjusted
`LEZAC_ORIGINAL_STARTUP_SECONDS`, `LEZAC_ORIGINAL_START_KEY`,
`LEZAC_ORIGINAL_START_TEXT`, or `LEZAC_ORIGINAL_ROUTE_RIGHT_SECONDS`.

Compare paired frames with:

```sh
tools/frame_compare.py \
  /tmp/lezac-cpp-frames/010_level1_start.ppm \
  /tmp/lezac-original-frames/<dosbox-screenshot>.png \
  --diff /tmp/lezac-frame-diff.ppm
```

`tools/frame_compare.py` reads PPM/PNM and uncompressed BMP files without extra
dependencies. If Pillow is installed, it can also read DOSBox PNG screenshots.
When one frame is an integer-scaled version of the other, such as DOSBox
640x400 screenshots compared with 320x200 C++ frames, the larger frame is
downscaled automatically before metrics are computed.
For exact oracle work, compare semantic checkpoints rather than elapsed frame
numbers.

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
  Deterministic debug coverage exercises the current cell-aware passable-object
  classification, including the level-1 low-word object route, level-1
  autoplayer bomb route, death/reentry, record-entry, two-player movement/bomb
  checkpoints, frame-harness checkpoints, and player/monster collision pushout
  model.
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
  queues cursor `0x0027` at priority `6`, bonus pickup audio queues cursor
  `0x0008` at priority `5`, accepted player damage queues cursor `0x002d` at
  priority `4`, and player death/life-loss queues cursor `0x0056` at priority
  `5` while restoring the player energy byte to `100`. Live player damage now
  accumulates per-player damage bytes and drains them once per update pass,
  matching the recovered `DS:79e8`/`DS:79e9` model and original unsigned byte
  underflow death check rather than a modern one-hit cooldown gate. Manual
  reentry/restart still waits for the recovered state-2 `0x003c` countdown
  before returning a player to active control. The state-2 death/reentry
  animation initializer is now documented as the seven-byte `actor + 0x16`
  cursor populated by `1000:06ab`, and the
  actor update model locks the `1000:6053` counter, wrap, ping-pong, and
  mode-3 backup behavior. The runtime-frame oracle parses saved DOSBox debugger
  dumps for `DS:006a`, `DS:006c`, `DS:006d`, the `DS:c322..c324` frame table,
  and `DS:c21e` effect-entry words without making a visual claim, and reports
  each captured frame-table row in deterministic raw-byte form. A real temp-copy
  `dosbox-debug` capture stopped at runtime `01ED:7C89` now locks one original
  state-2 countdown sample: `DS=0C8F`, death cursor `0x45`, frame range
  `0x4a..0x4f`, and effect entry 0 position `0x0068,0x00a8`.
  `--debug-son-step-fields` exposes each recovered six-byte sound step as
  `period_word`, `gate_tick`, `period_ticks`, `unknown4`, and `unknown5` while
  keeping bytes `+4..+5` explicitly uninterpreted. The
  return-placement model tracks the `DS:c21e + 8 * actor[+0x01]` effect-entry
  descent and blocking checks. Explosion/debris/collapse diagnostics now lock
  the recovered dispatcher selector/state/sound-offset table, queued
  debris/collapse payload fields, and bomb-object passability/routing side
  effects without claiming exact original sprite playback.

## Still Approximate

- Monster spawners now create active enemies with original-style 8.8 motion, and
  debug coverage locks the current collision/passability model, but
  behavior-specific AI and exact original collision clearance remain implemented
  hypotheses pending deeper reconstruction of the actor update routine around
  `1000:6053`.
- PC speaker sound effects now use a recovered request/priority latch,
  direct-sweep path for bomb explosions, and six-byte cursor stepping for
  `PROEFS.SON`. Field diagnostics preserve bytes `+4..+5` as raw unknowns, and
  their semantic meaning plus many non-explosion callsite-to-event mappings
  remain unresolved.
- Two-player split-screen is playable with independent bomb inventories, scores,
  and record prompts, but exact original panel artwork and reentry presentation
  remain approximate.
- High scores are persisted with original-evidence name-entry keys
  (letters/space, Backspace, Enter), but exact cursor drawing, typematic repeat,
  and name-entry presentation remain approximate.
- Bomb fuse timing, 2x2 footprint, player blast damage, monster hit-point
  blast damage, visual selectors, actor sprite indices, word-layer damage
  gating, bomb-object passability after explosion, and queued debris/collapse
  metadata now follow the `1000:414a`/`1000:370e`/expiration analysis. Active
  collapse/debris records
  now queue into the same per-player damage counters as monster contact and
  bomb blasts, but exact sprite playback and delayed state-2 life-count
  decrement remain simplified. The `actor + 0x16` state-2 cursor, cursor
  advancement rules, and `DS:c21e` placement math are locked as deterministic
  models. The live renderer now has provisional state-2 visual playback keyed
  to the recovered `0x4a..0x4f` cursor range and tested by
  `--debug-autoplayer death_visuals`, but it still reports `visual_claim=0`
  because the original frame-table field interpretation is not fully mapped.

See [docs/GHIDRA_NOTES.md](docs/GHIDRA_NOTES.md) for addresses and disassembly
anchors used in the reconstruction.
