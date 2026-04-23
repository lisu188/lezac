# Frame Comparison Harness

The frame comparison workflow has three parts:

1. `--capture-frame-sequence level1_bomb_route <out-dir>` in the C++ port emits
   deterministic 320x200 PPM frames plus a manifest. It uses dummy SDL cleanly,
   so it is suitable for CTest and headless runs. The C++ sequence uses the
   deterministic level-1 autoplayer to reach tile `(24,22)` instead of
   teleporting the player to the checkpoint.
2. `tools/capture_original_dosbox_frames.sh <out-dir> [asset-dir]` is a
   best-effort original-game capture driver. It copies original assets to a
   temporary directory, runs `LEZAC.EXE` in DOSBox under Xvfb, drives the window
   with `xdotool`, and asks DOSBox to save screenshots with Ctrl-F5.
3. `tools/frame_compare.py <left> <right> [--diff out.ppm]` compares paired
   frames and reports exact and thresholded pixel-difference metrics.

The current C++ sequence writes these checkpoints:

```text
000_menu.ppm
010_level1_start.ppm
020_level1_tile24_aligned.ppm
030_level1_tile24_bomb.ppm
040_level1_tile24_explosion.ppm
050_level1_tile24_playback_4.ppm
060_level1_tile24_playback_12.ppm
manifest.txt
```

The route can also be tested without writing frame files:

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer level1_bomb_route
```

This is not yet a proof of original visual fidelity. The C++ frames are
deterministic current-port evidence, while the DOSBox driver is intentionally
best-effort because original timing, keyboard focus, and screenshot output can
vary. For faithful reconstruction work, pair frames by semantic checkpoint and
use the diff metrics to guide targeted investigations.

Example:

```sh
cmake --build build
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-frames
tools/capture_original_dosbox_frames.sh /tmp/lezac-original-frames .
tools/frame_compare.py \
  /tmp/lezac-cpp-frames/010_level1_start.ppm \
  /tmp/lezac-original-frames/<matching-original-frame>.png \
  --diff /tmp/lezac-start-diff.ppm
```

`tools/frame_compare.py` has built-in PPM/PNM and uncompressed BMP readers. It
uses Pillow only as an optional fallback for formats such as DOSBox PNG
screenshots. If one frame is an integer-scaled version of the other, for
example DOSBox 640x400 output versus a 320x200 C++ PPM, the comparator
downscales the larger frame automatically before reporting metrics.
