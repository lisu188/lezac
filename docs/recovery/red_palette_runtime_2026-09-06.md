# Runtime Red Palette

## Scope And Result

The red terrain discrepancy found during [tall-background recovery](tall_background_runtime_2026-09-06.md)
is caused by a six-entry VGA palette animation absent from C++. Two new
original captures now verify 244 fixed-scene frames, 55 palette updates and
11,571,456 rendered pixels using actual sampled DAC values. All 24 DOSBox
screenshot crops match their indexed-buffer/DAC previews exactly. C++ matches
both fixtures and all 24 screenshot crops, including the current palette, pending phase, five-frame gate,
16-bit frame rollover, and explicitly seeded byte-overflow cases.

This is palette and controlled-render evidence, not a natural route or
whole-game visual-parity claim. The map, skyline and sprite-0 visual entry
are explicit fixed inputs; other actors and spawners are disabled.

## Original Rule

Main CS:079D (file 0x0f0d..0f34) writes DAC entries 230..235 through ports
0x3c8/0x3c9. Each entry has green and blue zero. Starting with the pending
byte DS:79AD, it writes red, adds seven as a byte, and resets the next red
value to 20 when the signed byte is greater than 63. VGA stores only the
low six bits. The normal steady sequence cycles through 20,27,34,41,48,55,62.

Main CS:81CD (file 0x893d) checks unsigned word DS:78C2 modulo five. On zero,
CS:81DC calls the writer and then increments DS:79AD by seven as a byte,
resetting that pending phase to 20 when its unsigned value exceeds 63.
Thus the active DAC and the pending phase are different state. The C++
implementation preserves both the writer's signed comparison and the
pending phase's unsigned comparison instead of substituting a simple modulo.
The byte-250 seed verifies DAC masking and byte overflow to pending phase 1.

Palette updates occur after the original world draw and actor passes, but
before the completion gate. The C++ gameplay update now calls `updateRedPalette`
at that point relative to completion. The diagnostic renders the fixed
pre-actor scene using the resulting palette, matching the original displayed
buffer after the palette update.

The original frame word is reset at file 0x7f44 after a new-game selection.
Level advance jumps from 0x8a12 to 0x7f4c, past that reset; ordinary iteration
increments the word at 0x8073. C++ `beginLevelForPlay` now preserves the
gameplay counter across level changes and resets it for a menu-launched game.
The pending palette phase is not reset by the original new-game/level paths.
Its zero startup value plus all five-frame updates reconstructs the observed
natural initial phase and DAC on both level 1 and level 4; the replay does
not seed either from its first observation. Isolated `resetLevel` diagnostic
setup retains its existing local clock-reset semantics.

## Capture And Provenance

Executable SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The temporary DOSBox copies use private Xvfb displays, surface output,
frameskip zero, no scaler, and fixed 6000 CPU cycles. Menu key `1` and
startup/intro/level-start/results waits 10/8/5/10 seconds are used. Level 4
is reached through three original transitions with completion-counter
instrumentation, not a replaced level loader.

`tools/capture_original_red_palette.py` guards six instruction windows and
instruments main CS:7A13 (before rendering) and CS:81F6 (after the palette
gate). Captured runtime main CS/DS are 01a2/0c44; the tool's nominal
01ed/0c8f pair is relative to the seeder's adjusted host-memory base.
The trampoline saves/restores flags
and general registers, sets the VGA read index through port 0x3c7, and reads
all 768 DAC components through 0x3c9 into private scratch at CS:F800/FB00.
This changes the DAC read cursor, not its color values. The original writes
set their own write index. No executable or asset file is patched on disk.

Each sample records both register sets, frame, pending phase and full DAC
before/after. View pixels come from the original drawing-buffer segment
DS:C212 at DS:C214 plus fine scrolling, not C++ tile reconstruction. All
samples have the same indexed-view hash; the capture rejects a changed or
low-variation view. The original map and skyline are restored/held as inputs,
one sprite-0 visual is placed at a fixed coordinate, and lives/energy are
seeded to 99/100 to keep the render probe active.

| Case | Samples per fixture | Frame/phase treatment |
| --- | --- | --- |
| `continuous` | 71 | No frame or phase seed; ordinary five-frame updates |
| `frame_wrap` | 24 | Seed frame 65520 and phase 62; pass through 65535 and 0 |
| `zero_phase` | 16 | Seed frame 0 and phase 0; initial ramp arithmetic |
| `byte_wrap` | 11 | Seed frame 0 and phase 250; byte wrap and DAC masking |

No case seeds DAC colors. The first case reconstructs startup history from
phase zero; later cases preserve the preceding palette while applying the
explicit frame/phase seeds. Level-1 continuous frames are 127..197, with 27
palette writes across all cases. Level-4 continuous frames are 410..480,
with 28 writes across all cases. The word wrap correctly permits palette
writes on consecutive frames 65535 and 0.

Promoted fixtures, copied unchanged from `build-codex-tmp/red-palette1-v2.txt`
and `red-palette4-v2.txt`:

- `tests/fixtures/red_palette_level1_original.txt`:
  `82cdf7be2f6868830e001e0944dfcf833bbc0014c94c644e47bc1ea77917a5d0`
- `tests/fixtures/red_palette_level4_original.txt`:
  `cede678ae46c44f4a8050c46ce7bf012b393b9abcf430282d306fa25289471eb`

The first `v1` attempts sampled valid DAC state but incorrectly read VGA
pixels from ordinary emulated RAM, yielding black previews. Screenshot
inspection exposed that error. Those attempts were not promoted; the
corrected drawing-buffer path was rerun for both levels.

Example commands after copying assets into a fresh temporary directory:

```sh
python3 tools/capture_original_red_palette.py --level 4 \
  --run-dir /tmp/lezac-palette4-v2 \
  --out build-codex-tmp/red-palette4-v2.txt \
  --approve-procmem --approve-runtime-instrumentation
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-red-palette-original tests/fixtures/red_palette_level4_original.txt \
  build-codex-tmp/red-palette4-cpp-v1
```

## Tests And Limits

The original replay checks provenance, complete case coverage, consecutive
frames, register relationships, descriptors, pending phase, both red DAC
states, full six-bit DAC encoding and all rendered pixels. The fixture guard
pins normalized LF hashes, verifies indexed-view SHA-256 values, accepts
LF/CRLF, rejects truncation and 42 mutations, and checks no implicit PPM
writes. Optional output contains a 122-row CSV and 12 PPM checkpoints.

The full 466-test suite passed under Xvfb in 108.39 seconds, with log
`build-codex-tmp/red-palette-full-tests.log`. The fixture guard was then
expanded to include valid-but-wrong indexed pixels and non-red displayed
DAC bytes, exercising the complete image-comparison failure path. The expanded
42-mutation guard passed in a subsequent 28.90-second CTest run.

`--debug-red-palette-lifecycle` additionally drives actual gameplay updates
through the fifth-frame gate, pause/menu/intro holds, a level transition,
new-game clock reset, phase preservation and word rollover. These are C++
integration checks; fresh continuous original menu/pause/end-run captures
have not been added in this batch. The literal signed writer branch for
intermediate seeded values 128..248 is static-derived, not reached by the
promoted probes. Other dynamic palettes, unrestricted actor interactions,
natural world-render timing, HUD phases and skyline RNG alignment remain
outside this result. Whole-game completion and fidelity remain unproven.
