# Frame Comparison Harness

The frame comparison workflow has four parts:

1. `--capture-frame-sequence <scenario> <out-dir>` in the C++ port emits
   deterministic 320x200 PPM frames plus a manifest. It uses dummy SDL cleanly,
   so it is suitable for CTest and headless runs. Current built-in capture
   scenarios are `level1_bomb_route`, `monster_bomb_reward`,
   `monster_spawner_behavior4_level2`, `monster_spawner_behavior4_level3`, and
   `monster_behavior4_target_selection`.
2. `tools/capture_original_dosbox_frames.sh <out-dir> [asset-dir] [scenario]`
   is a best-effort original-game capture driver for the original semantic
   `level1_bomb_route` and a start/armed smoke capture for
   `monster_bomb_reward`. It copies original assets to a temporary directory,
   runs `LEZAC.EXE` in DOSBox under Xvfb, drives the window with `xdotool`, asks
   DOSBox to save screenshots with Ctrl-F5, renames screenshots to semantic
   labels where possible, and writes a manifest. Before launching DOSBox, it runs
   `tools/preflight_original_evidence_environment.py --require-frame-capture
   --probe-wsl --require-wsl-bash-on-windows`, writes
   `environment_preflight.log`, and records the preflight command/result in the
   manifest. On Windows this preserves blockers such as
   `wsl_bash_reason=no_default_distro` before any screenshot automation is
   attempted. The monster-bomb path intentionally stops at the
   keyboard-reproducible armed-bomb checkpoint and does not automate an
   original monster kill.
3. `tools/capture_original_monster_sprite_consumption_procmem.py` is the
   focused original-runtime source for the level-1 kind-1 kill. It requires a
   caller-created temporary asset copy, always re-executes invisibly under a
   private `xvfb-run -a`, drives real XTEST controls, and takes one complete
   64 KiB data-segment snapshot per `DS:0x78C2` tick. It emits raw tick rows, a
   completion manifest, and headless checkpoint PNGs. The normalized checked-in
   evidence is
   `tests/fixtures/monster_sprite_consumption_original_level1.txt`.
4. `tools/frame_compare.py <left> <right> [--diff out.ppm]` compares paired
   frames and reports exact and thresholded pixel-difference metrics.

`tools/compare_original_cpp_frames.sh <out-dir> [asset-dir] [scenario]` wraps
the deterministic C++ capture, legacy DOSBox screenshot driver, and paired
comparison. It does not invoke the focused process-memory monster-kill capture.
It writes C++ frames, DOSBox-original frames, PPM diffs,
`frame_compare_summary.txt`, and a manifest under the requested output
directory. Use a temporary path such as `/tmp/lezac-frame-compare-*`; the
helper intentionally keeps generated original evidence outside the repository.

The wrapper keeps the bundle reviewable even when the original DOSBox leg
fails. It records the capture process output in `original_capture_driver.log`,
adds `original_capture_exit`, `original_capture_manifest`,
`original_capture_log`, `original_environment_preflight_log`, and
`compare_exit` to the top-level manifest, writes missing-original lines to
`frame_compare_summary.txt`, prints `frame_compare_bundle=error`, and then
returns nonzero. This lets WSL/DOSBox blockers remain visible without treating
the comparison as successful.

Use `tools/summarize_frame_compare_bundle.py <bundle-or-manifest>` to turn a
bundle into one triage line. It reports frame counts, missing original labels,
compare errors, maximum pixel-difference metrics, original preflight state,
`wsl_bash_reason`, and `promotion_ready`. Add `--require-promotion-ready` when
a follow-up script should fail unless the original capture completed, every C++
checkpoint had a paired original frame, and all frame comparisons were clean.

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
025_monster_bomb_last_pre_fatal.ppm
030_monster_bomb_death.ppm
040_monster_bomb_corpse_midpoint.ppm
050_monster_bomb_corpse_last.ppm
060_monster_bomb_reward_visible.ppm
070_monster_bomb_reward_collected.ppm

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

Every sequence begins with the shared `000_menu` capture before scenario
dispatch. The `monster_bomb_reward` branch then adds eight frames, so its
summary reports nine frames total:

| Label | Deterministic C++ checkpoint |
| --- | --- |
| `010_monster_bomb_start` | Level 1 started. |
| `020_monster_bomb_armed` | Bomb armed with the seeded kind-1 target on sprite `44`, matching the original frame-257 checkpoint identity. |
| `025_monster_bomb_last_pre_fatal` | Same target on sprite `43`, the authoritative last pre-fatal sprite after the original `44x4,43x2` run. |
| `030_monster_bomb_death` | Production damage enters kind `0x0c`, state 2, corpse sprite `47`, timer 120; no reward exists yet and `impact_equals_death=1`. |
| `040_monster_bomb_corpse_midpoint` | Corpse sprite `47` at timer 60. |
| `050_monster_bomb_corpse_last` | Final corpse sprite `47` frame at timer 1. |
| `060_monster_bomb_reward_visible` | The next update removes the corpse and creates delayed Present sprite `61`; score is unchanged. |
| `070_monster_bomb_reward_collected` | Collection removes the Present and adds 2000 points. |

These frames verify the current port's production damage, timer, renderer,
reward creation, and collection consumers. They do not promote exact original
reward physics or presentation: the original Present row has timer byte
`+2 = 100`, initial vertical velocity `-200`, and subsequent motion, while the
port's `BonusDrop` is static. The sequence therefore reports
`reward_motion_claim=0` and `visual_claim=0`.

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
environment_preflight.log
```

For `monster_bomb_reward`, the legacy DOSBox driver currently attempts only a
start/armed smoke capture:

```text
000_menu.png
010_monster_bomb_start.png
020_monster_bomb_armed.png
manifest.txt
original_capture.log
environment_preflight.log
```

Its manifest records `not_captured` placeholders, with reason
`legacy_driver_does_not_automate_original_kill_route`, for all remaining
current C++ labels:

```text
025_monster_bomb_last_pre_fatal
030_monster_bomb_death
040_monster_bomb_corpse_midpoint
050_monster_bomb_corpse_last
060_monster_bomb_reward_visible
070_monster_bomb_reward_collected
```

The `010` and `020` legacy screenshots are keyboard-route smoke evidence, not
the authoritative original kill sequence and not automatically promoted paired
frames. Missing original frames should remain visible in `frame_compare_summary.txt`
instead of being papered over.

## Focused Original Monster-Kill Evidence

The authoritative original trace is separate from the legacy frame-comparison
driver. `tools/capture_original_monster_sprite_consumption_procmem.py` runs
inside private Xvfb, uses a temporary copy of the original assets, waits for
the known first level-1 kind-1 spawn, and drives the kill and collection with
XTEST controls. Each sampled tick comes from one complete 64 KiB `DS` read, so
the actor, visual, RNG, and score rows are not torn.

Its complete capture contains five semantic checkpoints in four distinct
headless screenshots:

```text
pre_impact       frame 257  sprite 44
fatal_impact     frame 263  sprite 47
corpse_playback  frame 263  sprite 47 (same screenshot as fatal_impact)
reward_visible   frame 312  Present sprite 61
collection       frame 366  Present removed, score +2000
```

The intervening authoritative tick rows establish the full pre-fatal run
`44x4,43x2`, last pre-fatal sprite `43`, raw original corpse timer byte
`0x19` decrementing to 1 on its governed cadence across 49 sampled ticks, and
54 observed reward-visible ticks. The normalized fixture retains the
checkpoint PNG names and SHA-256 values:
`tests/fixtures/monster_sprite_consumption_original_level1.txt`.

Those original PNGs are headless observation artifacts, not direct
same-position pixel pairs for the deterministic C++ frames. Player input and
position are exogenous, the C++ corpse uses 120 engine frames, the port omits
the original transition-effect actors, and its Present is static rather than
matching the original timer/motion. Consequently the fixture and C++ harness
remain `visual_claim=0`; compare their semantic sprite/timer/reward checkpoints
side by side without treating the images as an exact pixel-fidelity promotion.

The 2026-07-28 validation captured the C++ sequence with dummy SDL and visually
inspected `020`/`025`/`030`/`040`/`050`/`060`/`070` beside the headless original
pre-impact, fatal/corpse, reward-visible, and collection PNGs. The expected
sprite-44/43 animation change, sprite-47 corpse persistence, Present appearance,
and collection disappearance were visible. World positions and surrounding
effects differed because the routes are exogenous and the limitations above
remain; no pixel-equality result or visual claim was promoted.

These scenarios can also be tested without writing frame files:

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer level1_bomb_route
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-autoplayer monster_bomb_reward
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
`LEZAC_ORIGINAL_START_TAPS`, `LEZAC_ORIGINAL_START_TEXT`,
`LEZAC_ORIGINAL_ROUTE_RIGHT_KEY`, `LEZAC_ORIGINAL_ROUTE_RIGHT_SECONDS`, or
`LEZAC_ORIGINAL_FIRE_KEY`/`LEZAC_ORIGINAL_FIRE_HOLD_SECONDS` and rerun.
Current defaults use the focused no-window `xdotool key` path with two `1`
taps, player-1 right on `x`, and a held player-1 fire on `n`, matching the
original embedded control text and local Xvfb/DOSBox observations.
For faithful reconstruction work, pair frames by semantic checkpoint and use
the diff metrics to guide targeted investigations. `manifest.txt` now records
player count/death flags and first-monster position/velocity/behavior for the
monster scenarios; `changed_pixels` is a within-frame non-uniformity count, not
a diff-vs-previous-frame metric.

Example:

```sh
cmake --build build
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-frames level1_bomb_route
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-monster monster_bomb_reward
tools/capture_cpp_frames.sh ./build/lezac_cpp /tmp/lezac-cpp-b4-level2 monster_spawner_behavior4_level2
tools/capture_original_dosbox_frames.sh /tmp/lezac-original-frames . level1_bomb_route
tools/frame_compare.py \
  /tmp/lezac-cpp-frames/010_level1_start.ppm \
  /tmp/lezac-original-frames/<matching-original-frame>.png \
  --diff /tmp/lezac-start-diff.ppm

tools/compare_original_cpp_frames.sh /tmp/lezac-frame-compare .
# Legacy start/armed smoke bundle; expected to lack the kill-route originals.
tools/compare_original_cpp_frames.sh /tmp/lezac-frame-compare-monster . monster_bomb_reward
tools/summarize_frame_compare_bundle.py /tmp/lezac-frame-compare
tools/summarize_frame_compare_bundle.py /tmp/lezac-frame-compare --require-promotion-ready
```

State-2 dead-player visual work has a narrower comparison helper because the
current live renderer (`74..79`) and recovered row-byte-3 candidate renderer
(`67..72`) need to be compared side by side before promotion:

```sh
./build/lezac_cpp --capture-state2-visual-row-game-preview /tmp/lezac-cpp-state2-game-preview
tools/capture_original_state2_visual_frames.sh \
  /tmp/lezac-original-state2-visual . state2_death_table_consumption
tools/compare_state2_visual_row_game_previews.py \
  /tmp/lezac-state2-visual-compare ./build/lezac_cpp /tmp/lezac-original-state2-visual
tools/summarize_frame_compare_bundle.py /tmp/lezac-state2-visual-compare
```

The original capture helper writes a manifest and frame plan for
`state2_death_table_consumption`; set
`LEZAC_STATE2_VISUAL_FRAME_CAPTURE_DRY_RUN=1` to validate the workflow without
launching DOSBox. Live capture is intentionally labeled `debugger_seeded` until
the state-2 frames can be staged by debugger setup. The resulting original
directory should contain one original frame for each visual cursor, using names
such as `state2_game_4a.png`, `state2_original_4a.png`, or
`state2_game_current_4a.png` through `4f`; the C++ contrast preview writes
`state2_game_cursor_4a.ppm` through `4f`. The helper writes standard frame-compare
bundle artifacts with labels such as `state2_current_4a` and `state2_cursor_4a`,
so `tools/write_visual_claim_promotion_entry.py` can later select the proven
label once a promotion-ready original bundle exists.

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

The C++ frame manifest now also records the first debris, collapse, and
explosion-effect record fields per checkpoint. These fields are intended to sit
next to original-runtime oracle fixtures when the rendered pixels are too
approximate for direct acceptance. A 2026-04-25 WSL/Xvfb comparison run at
`/tmp/lezac-frame-compare-high-debris-20260425b` captured all seven level-1
labels. The original route visibly left the menu and reached the blast/playback
frames, while the C++ route still drew provisional damage blocks. The paired
pixel diffs remained large:

```text
040_level1_tile24_explosion exact_different_pixels=55975 mean_abs_delta=80.761042
050_level1_tile24_playback_4 exact_different_pixels=55974 mean_abs_delta=80.751745
060_level1_tile24_playback_12 exact_different_pixels=55473 mean_abs_delta=79.061042
```

The same C++ manifest records one collapse queue entry and no debris queue
entry for the level-1 blast:

```text
040_level1_tile24_explosion collapse0_xy=24,21 collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_flagged=0x8009 collapse0_forward=0 collapse0_reverse=0 collapse0_affected=4 collapse0_count=2 collapse0_timer=24 effect0_xy=24,22 effect0_visual=1 effect0_detail=117 effect0_timer=8 effect0_variant=5
050_level1_tile24_playback_4 collapse0_xy=24,21 collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_flagged=0x8009 collapse0_forward=0 collapse0_reverse=0 collapse0_affected=4 collapse0_count=2 collapse0_timer=20 effect0_xy=24,22 effect0_visual=1 effect0_detail=117 effect0_timer=4 effect0_variant=5
```

That queue state should be compared with the original high-debris lane fixtures:
the original post-call stops for the same collapse span preserve helper-written
lane bytes, including `collapse0_forward=0x00` and `collapse0_reverse=0x04`,
with helper input globals `DS:78D2=0xF7` and `DS:78D4=0xFC`. This is a concrete
frame-facing mismatch to investigate before replacing the provisional
`drawDamageQueues` renderer.
