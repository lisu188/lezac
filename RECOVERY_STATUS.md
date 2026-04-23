# Recovery Status

Last reviewed: 2026-04-23
Branch: `codex/frame-comparison-harness`
Baseline: `20bb2ad` / `origin/main`

## Completed This Iteration

- Added `--capture-frame-sequence level1_bomb_route <out-dir>` to emit
  deterministic 320x200 C++ PPM frames plus a manifest for menu, level-1 start,
  tile `(24,22)` alignment, bomb placement, and explosion/playback checkpoints.
- Added `tools/capture_cpp_frames.sh` as a dummy-SDL wrapper for the C++ frame
  sequence.
- Added `tools/capture_original_dosbox_frames.sh` as a best-effort DOSBox/Xvfb
  capture driver that uses a temp copy of `LEZAC.EXE` assets and DOSBox Ctrl-F5
  screenshots at matching semantic checkpoints.
- Added `tools/frame_compare.py`, a no-required-dependency PPM/BMP comparator
  with optional Pillow fallback for DOSBox PNG screenshots, threshold metrics,
  and visual diff output.
- Added CTest coverage for the C++ capture command and the frame comparator's
  identical-frame fixture.

## Validation

- `cmake -S . -B build` passed.
- `cmake --build build` passed.
- `ctest --test-dir build --output-on-failure` passed: 55/55.
- `./build/lezac_cpp --validate` passed.
- `env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp
  --capture-frame-sequence level1_bomb_route /tmp/lezac-cpp-frames-test`
  passed and wrote seven PPM frames plus `manifest.txt`.
- `tools/capture_cpp_frames.sh ./build/lezac_cpp
  /tmp/lezac-cpp-frames-wrapper-test` passed.
- `timeout 20s tools/capture_original_dosbox_frames.sh
  /tmp/lezac-original-frames-test .` passed and produced six DOSBox PNG
  screenshots plus `original_capture.log`.
- `tools/frame_compare.py /tmp/lezac-cpp-frames-test/000_menu.ppm
  /tmp/lezac-original-frames-test/lezac_000.png --max-diff-pixels 64000
  --diff /tmp/lezac-menu-diff.ppm` passed, including automatic 640x400 to
  320x200 normalization.
- `git diff --check` passed.

## Remaining Top Gaps

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

Use the new frame harness to collect paired original/C++ level-1 checkpoints,
then prioritize the largest visual diffs around bomb-object explosion,
collapse/debris playback, and player/death frame-table consumption.
