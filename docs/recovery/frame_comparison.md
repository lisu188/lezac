# Frame Comparison Harness

The frame comparison workflow has three parts:

1. `--capture-frame-sequence <scenario> <out-dir>` in the C++ port emits
   deterministic 320x200 PPM frames plus a manifest. It uses dummy SDL cleanly,
   so it is suitable for CTest and headless runs. Current built-in capture
   scenarios are `level1_bomb_route`, `monster_spawner_behavior4_level2`,
   `monster_spawner_behavior4_level3`, and
   `monster_behavior4_target_selection`.
2. `tools/capture_original_dosbox_frames.sh <out-dir> [asset-dir]` is a
   best-effort original-game capture driver for the original semantic
   `level1_bomb_route` only. It copies original assets to a temporary
   directory, runs `LEZAC.EXE` in DOSBox under Xvfb, drives the window with
   `xdotool`, asks DOSBox to save screenshots with Ctrl-F5, renames the
   screenshots to semantic labels matching the C++ level-1 route sequence, and
   writes a manifest.
3. `tools/frame_compare.py <left> <right> [--diff out.ppm]` compares paired
   frames and reports exact and thresholded pixel-difference metrics.

`tools/compare_original_cpp_frames.sh <out-dir> [asset-dir] [scenario]` wraps
those steps for the current evidence workflow. It writes C++ frames,
DOSBox-original frames, PPM diffs, `frame_compare_summary.txt`, and a manifest
under the requested output directory. Use a temporary path such as
`/tmp/lezac-frame-compare-*`; the helper intentionally keeps generated original
evidence outside the repository.

The current C++ sequences write these checkpoints:

```text
level1_bomb_route:
000_menu.ppm
010_level1_start.ppm
020_level1_tile24_aligned.ppm
030_level1_tile24_bomb.ppm
040_level1_tile24_explosion.ppm
050_level1_tile24_playback_4.ppm
060_level1_tile24_playback_12.ppm

monster_bomb_reward:
000_menu.ppm
010_monster_bomb_start.ppm
020_monster_bomb_armed.ppm
030_monster_bomb_death.ppm
040_monster_bomb_reward_collected.ppm

monster_spawner_behavior4_level2:
000_menu.ppm
010_level2_start.ppm
020_level2_behavior4_spawner_armed.ppm
030_level2_behavior4_spawned.ppm

monster_spawner_behavior4_level3:
000_menu.ppm
010_level3_start.ppm
020_level3_behavior4_spawner_armed.ppm
030_level3_behavior4_spawned.ppm

monster_behavior4_target_selection:
000_menu.ppm
010_level3_two_player_start.ppm
020_level3_behavior4_target_armed.ppm
030_level3_behavior4_target_p2.ppm
040_level3_behavior4_target_p1.ppm
050_level3_behavior4_target_p2_return.ppm

manifest.txt
```

The DOSBox capture driver attempts to write the same labels for
`level1_bomb_route` without the `.ppm` extension:

```text
000_menu.png
010_level1_start.png
020_level1_tile24_aligned.png
030_level1_tile24_bomb.png
040_level1_tile24_explosion.png
050_level1_tile24_playback_4.png
060_level1_tile24_playback_12.png
manifest.txt
original_capture.log
```

These scenarios can also be tested without writing frame files:

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer level1_bomb_route
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer monster_spawner_behavior4_level2
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer monster_spawner_behavior4_level3
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer monster_behavior4_target_selection
```

This is not yet a proof of original visual fidelity. The C++ frames are
deterministic current-port evidence, while the DOSBox driver is intentionally
best-effort because original timing, keyboard focus, and screenshot output can
vary. Local runs have produced correctly named DOSBox frames while keyboard
injection remained on the original menu, so every original capture must be
visually inspected before being used as oracle evidence. If needed, tune
`LEZAC_ORIGINAL_STARTUP_SECONDS`, `LEZAC_ORIGINAL_START_KEY`,
`LEZAC_ORIGINAL_START_TEXT`, or `LEZAC_ORIGINAL_ROUTE_RIGHT_SECONDS` and rerun.
For faithful reconstruction work, pair frames by semantic checkpoint and use
the diff metrics to guide targeted investigations. `manifest.txt` now records
player count/death flags and first-monster position/velocity/behavior for the
monster scenarios; `changed_pixels` is a within-frame non-uniformity count, not
a diff-vs-previous-frame metric.

Example:

```sh
cmake --build build
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-frames level1_bomb_route
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-b4-level2 monster_spawner_behavior4_level2
tools/capture_original_dosbox_frames.sh /tmp/lezac-original-frames .
tools/frame_compare.py \
  /tmp/lezac-cpp-frames/010_level1_start.ppm \
  /tmp/lezac-original-frames/<matching-original-frame>.png \
  --diff /tmp/lezac-start-diff.ppm

tools/compare_original_cpp_frames.sh /tmp/lezac-frame-compare .
```

`tools/frame_compare.py` has built-in PPM/PNM and uncompressed BMP readers. It
uses Pillow only as an optional fallback for formats such as DOSBox PNG
screenshots. If one frame is an integer-scaled version of the other, for
example DOSBox 640x400 output versus a 320x200 C++ PPM, the comparator
downscales the larger frame automatically before reporting metrics.

For the 2026-04-24 gameplay damage/collision/HUD pass, the comparison helper
successfully captured and paired the level-1 route under WSL/Xvfb. The C++
renderer is still approximate, so the pixel diffs are large; use the bundle as
semantic route evidence and visual inspection material, not as a pixel-perfect
acceptance gate for this slice.
