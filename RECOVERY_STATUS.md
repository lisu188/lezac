# Recovery Status

Last reviewed: 2026-04-23
Branch: `codex/autoplayer-harness`
Baseline: `1705ebd` / `origin/main`

## Completed This Iteration

- Added a deterministic `--debug-autoplayer level1_bomb_route` command.
- Extended `--debug-autoplayer` with `death_reentry`, `records_flow`, and
  `two_player_route` scenarios so state-2 reentry, record-entry saving, and
  player-2 movement/bomb controls are covered without live input.
- Added `death_visuals`, `level_transition`, and `two_player_progression`
  autoplayer scenarios. These lock provisional state-2 visual cursor playback,
  level-1 completion into level 2, player-2 death/reentry, post-reentry bombs,
  and player-2 scoring.
- Added provisional live state-2 rendering keyed to the recovered `0x4a..0x4f`
  cursor range. It is intentionally documented as `visual_claim=0` until the
  original `DS:c322` frame-table fields are fully interpreted.
- Refactored the game update path so the autoplayer can drive the same movement
  helpers with injected controls instead of relying on live keyboard state.
- Changed `--capture-frame-sequence level1_bomb_route <out-dir>` to reach tile
  `(24,22)` through the autoplayer route instead of teleporting the player.
- Changed the level-1 bomb route autoplayer and frame-sequence capture to place
  the route bomb through the actual `N` key event path instead of calling the
  placement helper directly.
- Added CTest coverage for all autoplayer scenarios and kept the frame-sequence
  capture coverage on the level-1 route.
- Expanded `tools/capture_original_dosbox_frames.sh` so original DOSBox
  screenshots are renamed to the C++ semantic labels and accompanied by a
  manifest with input/timing settings.
- Updated `AGENTS.md`, README, and recovery docs with the autoplayer, original
  DOSBox capture, and frame-inspection workflows.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer level1_bomb_route` passed with route length `55`, start
  `(104,168)`, final `(186,168)`, bomb tile `(24,22)`, and route bomb
  placement through the `N` key event path.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer death_reentry` passed with state-2 countdown `60`, lives
  `2`, energy `100`, and reentry confirmed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer death_visuals` passed with state-2 visual frames
  `0x4a -> 0x4b -> 0x4c` and `visual_claim=0`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer level_transition` passed with level-1 completion after
  `101` transition frames and level 2 loaded.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer records_flow` passed with temporary record score
  `999999`, level `3`, and name `bot`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer two_player_route` passed with player-2 movement and one
  player-2 bomb placed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer two_player_progression` passed with player-2 reentry,
  player-2 bomb placement, and player-2 score `1000`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --capture-frame-sequence level1_bomb_route /tmp/lezac-autoplayer-frames`
  passed and wrote seven PPM frames plus `manifest.txt`; route bomb placement
  also uses the `N` key event path.
- `tools/capture_cpp_frames.sh ./build/lezac_cpp
  /tmp/lezac-autoplayer-frames-wrapper` passed.
- `bash -n tools/capture_original_dosbox_frames.sh` passed. A local DOSBox run
  produced correctly named screenshots and manifest entries, but visual
  inspection showed xdotool input remained on the original menu; these captures
  are automation diagnostics until rerun with working menu input.
- `./build/lezac_cpp --debug-passable-objects` passed with
  `level1_route_clear=1`.
- `ctest --test-dir build --output-on-failure` passed: 62/62.
- `./build/lezac_cpp --validate` passed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --smoke-controls` passed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-level1-frame-inspection` passed.
- Frame inspection performed on generated checkpoints
  `020_level1_tile24_aligned` and `040_level1_tile24_explosion` after converting
  temporary PPM files to PNG for local viewing.
- `git diff --check` passed.

## Remaining Top Gaps

- Confirm the low-word passable-object route and level-1 bomb-route timing
  against original `LEZAC.EXE` with DOSBox frame inspection or debugger/runtime
  evidence.
- Make DOSBox original capture input reliable enough to leave the menu in this
  environment, then compare the named original frames against the C++ sequence.
- Interpret captured state-2 frame-table bytes and confirm the exact visual
  consumption path for the provisional live dead-player renderer.
- Exact explosion/debris/collapse sprite playback around `1000:3a56..4d3b`
  remains blocked on live debugger bytes from an explosion event.
- Semantic meaning of `PROEFS.SON` bytes `+4..+5` remains unknown; current
  diagnostics preserve them as raw fields only.
- Many non-explosion sound callsites still need exact cursor/priority mapping.
- Exact actor update behavior around `1000:6053..777f`, especially original
  contact flags, passability thresholds, tile snapping, behavior-3 ledge/wall
  handling, and behavior-4 collision response.
- The probable contact scanner around `1000:5cb0..604f` needs naming,
  cross-reference mapping, and runtime confirmation before the C++ clearance
  model can be called original-faithful.
- Exact state-2 life-count decrement, `DS:79b9` fallback behavior,
  active-player accounting edge cases, and exact dead-player visual playback
  from original frame bytes.
- Exact two-player panel artwork and full death/reentry presentation.
- Exact sprite frame tables for impact/death/reward frames remain unresolved.
- `GRAN.MST` field semantics remain unknown; consolidation only locks file
  shape and raw/json byte preservation.

## Next Planned Target

Run paired original/C++ frame captures for the autoplayer-aligned level-1 route,
then prioritize the largest visual diffs around bomb-object explosion,
collapse/debris playback, and player/death frame-table consumption.
