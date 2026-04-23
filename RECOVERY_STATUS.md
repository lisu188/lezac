# Recovery Status

Last reviewed: 2026-04-23
Branch: `codex/autoplayer-harness`
Baseline: `1705ebd` / `origin/main`

## Completed This Iteration

- Added a deterministic `--debug-autoplayer level1_bomb_route` command.
- Refactored the game update path so the autoplayer can drive the same movement
  helpers with injected controls instead of relying on live keyboard state.
- Changed `--capture-frame-sequence level1_bomb_route <out-dir>` to reach tile
  `(24,22)` through the autoplayer route instead of teleporting the player.
- Added CTest coverage for the autoplayer route and kept the frame-sequence
  capture coverage on the same scenario.
- Updated `AGENTS.md`, README, and recovery docs with the autoplayer/frame
  inspection workflow.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --debug-autoplayer level1_bomb_route` passed with route length `55`, start
  `(104,168)`, final `(186,168)`, and bomb tile `(24,22)`.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --capture-frame-sequence level1_bomb_route /tmp/lezac-autoplayer-frames`
  passed and wrote seven PPM frames plus `manifest.txt`.
- `tools/capture_cpp_frames.sh ./build/lezac_cpp
  /tmp/lezac-autoplayer-frames-wrapper` passed.
- `./build/lezac_cpp --debug-passable-objects` passed with
  `level1_route_clear=1`.
- `ctest --test-dir build --output-on-failure` passed: 56/56.
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
- Interpret captured state-2 frame-table bytes and confirm the visual
  consumption path before wiring live dead-player rendering.
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
  active-player accounting edge cases, and live dead-player visual playback
  from original frame bytes.
- Exact two-player panel artwork and full death/reentry presentation.
- Exact sprite frame tables for impact/death/reward frames remain unresolved.
- `GRAN.MST` field semantics remain unknown; consolidation only locks file
  shape and raw/json byte preservation.

## Next Planned Target

Run paired original/C++ frame captures for the autoplayer-aligned level-1 route,
then prioritize the largest visual diffs around bomb-object explosion,
collapse/debris playback, and player/death frame-table consumption.
