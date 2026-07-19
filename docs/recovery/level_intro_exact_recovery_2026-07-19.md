# Exact Level-Intro Recovery (2026-07-19)

## Result

The C++ port now reproduces the original per-level preparation screen and
shows it during real interactive level starts. The screen consists of a
randomized seven-color diagonal stripe pattern and the centered caption
`PREPARATI PER IL LIVELLO N`, revealed one character at a time.

The deterministic level-1 fixture is pixel-identical to the retained original
DOSBox capture. The C++ diagnostic also checks that gameplay does not update
during the intro, a skip key is consumed, and Escape returns to the menu.

## Original frame

The original frame came from the natural level-start checkpoint in:

```text
/tmp/lezac-sound-weapon-switch-latch-live-20260716-c/010_level_start.png
```

Its SHA-256 is:

```text
057cf113551f3a3ca370a2cce431ac2bae42aeee084468cb27f10bc66ccd34e6
```

The capture command and surrounding route are documented in
`docs/recovery/sound_weapon_switch_process_memory_2026-07-16.md`. An ignored
working copy was inspected as `build-codex-tmp/original-level-intro.png`; no
generated image is promoted as original evidence.

The indexed 320x200 frame contains:

| Palette index | RGB | Pixels |
| --- | --- | ---: |
| 1 | `0,0,170` | 360 |
| 31 | `255,255,255` | 620 |
| 176 | `69,73,65` | 9,013 |
| 177 | `81,85,69` | 8,975 |
| 178 | `93,97,73` | 8,973 |
| 179 | `105,109,77` | 9,043 |
| 180 | `117,125,85` | 8,976 |
| 181 | `130,138,89` | 9,034 |
| 182 | `142,150,93` | 9,006 |

The 980 blue/white pixels occupy `x=16..297`, `y=93..101`.

## Static recovery

`tools/ghidra/DumpLevelIntro.java` dumps the relevant ranges from the shipped
52,384-byte `LEZAC.EXE` (MZ image base `0x0770`):

- `1000:0139..01F9`: generate palette indices `176..182`.
- `1000:01FC..030A`: clear and generate the striped 320x200 background.
- `1000:2ADC`: level loader.
- `1000:2C01`: call the striped-background generator.
- `1000:2C49`: select localized caption data at `DS:088A + language*0x0D00`.
- `1000:2C6F`: call the text renderer at `1000:146A`.
- `1000:B2AA`: Pascal length byte `0x19`.
- `1000:B2AB`: lowercase text `preparati per il livello `.

The palette helper makes three `Random(20)` calls for RGB starts, then three
`Random(30)` calls for RGB deltas. For output index `i=0..6`, each VGA
component is:

```text
component[i] = start + delta*i/7
```

The background helper makes two `Random(80)+1` calls. Its recovered recurrence
for framebuffer index `i=0..63999` is:

```text
fraction += horizontal_step
if fraction > 100:
    fraction -= 100
    phase += 1

if i % 320 == 0:
    sine_index = floor(i*0.03) % 128
    wave = trunc(sin(sine_index*6.28/128)*8)
    fraction += vertical_step + wave
    if fraction > 100:
        fraction -= 100
        phase += 1

pixel[i] = palette[176 + phase%7]
```

The Real48 constant loaded at `1000:027D` decodes to `0.03`. The sine lookup
is the same 128-entry table used by the recovered level-7 boss links.

## Caption and timing

The original renderer centers fixed 11-pixel cells:

```text
x = 160 - string_length*11/2
```

For the 26-character level-1 caption this gives `x=17`. The small font sprites
use indices `26..51` for letters and `52..61` for digits. The blue shadow is
drawn at `(x-1,y-1)` with palette index 1, followed by the white glyph at
`(x,y)` with palette index 31; the main baseline origin is `y=94`.

The natural process-memory capture recorded:

```text
DS:78C0 = 82 00 00 00 05 40 42 00 00 00 02 00 10 00 51 00
```

Therefore the delay passed from `DS:78CE` is `0x0051`, or 81 ms, per
character. The renderer polls input during the delay. A key removes the
remaining delay and is consumed; Escape follows the original menu-abort path.

## Pixel proof

The captured pattern is reproduced by:

```text
horizontal_step = 37
vertical_step = 77
RGB starts = 17,18,16
RGB deltas = 21,23,9
```

Those values produce zero mismatches over all 63,020 non-caption pixels.
Using the recovered font geometry produces the remaining 980 pixels exactly.
The complete ARGB frame has:

```text
first_pixel = 0xff515545
changed_pixels = 55025
FNV-1a-style frame hash = 0x85e10db60f7e89f9
ImageMagick absolute-error pixel count = 0
```

Both original and C++ PNGs were visually inspected at native 320x200
resolution. The stripe boundaries, palette progression, caption position,
glyph shapes, and one-pixel shadow coincide.

## C++ integration

`beginLevelForPlay` wraps interactive menu starts, manual reloads, level
changes, and death restarts. It generates the pattern, resets the target
level, and activates the timed intro. While active:

- `update` and `updateWithControls` do not advance gameplay.
- `draw` renders the intro instead of menu/gameplay.
- a normal key ends and consumes the intro.
- Escape ends the intro and returns to the main menu.

The deterministic autoplayer and frame harness call `resetLevel` directly, so
existing routes remain immediate and reproducible. The live random draw
ranges and call order match the original; this evidence does not claim that
the port's shared pseudorandom generator has the same seed sequence as the
Turbo Pascal runtime.

## Validation

The exact diagnostic accepts an optional PPM output path:

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  /tmp/lezac-level-intro-build/lezac_cpp \
  --debug-level-intro /tmp/lezac-level-intro.ppm
```

Success output:

```text
level_intro=ok stripes=7 palette=176-182 exact_hash=0x85e10db60f7e89f9 exact_pixels=55025 caption_pixels=980 delay_ms=81 level_varies=1 live_flow=1 input_skip=1 escape_menu=1 frame_inspection=1
```

CTest `level_intro` pins that line. Focused validation also includes
`ui_controls_dummy`, `menu_frame_flow_dummy`,
`autoplayer_death_reentry_dummy`, and `autoplayer_level_transition_dummy`.
