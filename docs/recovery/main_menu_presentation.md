# Original Main Menu Presentation

This recovery covers the title fade and seven main-menu rows in both languages.
It does not establish whole-game, help-page or natural wall-clock parity.

## Original code

The original executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Addresses below use the main code segment's offsets, as in Ghidra `1000:xxxx`.

- `2361` calls title loader `030b`, then localized page renderer `2226` with
  first and last page 8, initial y 77, no forced striped backdrop and the
  skip-remainder-on-key flag enabled. It drains pending keys before reading a
  new menu choice. `L` reloads the title and draws the other language.
- `030b` applies 64 palette factors, 0 through 63, at six-bit VGA precision.
  Each channel is `floor(channel * factor / 63)`. Palette index 10 stays at
  full intensity. The decoder copies the title at factor 0. `0480` calls
  `CRT.Delay(22)` after every factor, including the last. A queued key is
  consumed at factor 3 or later and selects factor 63, still with its delay.
- `2226` calls `146a` with a 9-pixel character cell, palette colors 6 through
  10, blue shadow 6, compact font and 10-pixel row pitch. Each row is centered
  at `160 - floor(length * 9 / 2)`, with first y 77. Shadows are offset (-1,-1).
- `146a` has five leading/trailing spaces and `length + 5` loop steps. Step 1
  is blank; step 2 reveals the first glyph in palette color 6. A five-color
  trail ages each glyph through 7, 8, 9 and 10, leaving the completed row white.
  A typing key completes the text and is consumed, including Escape.
- `247f` calibrates the text's delay word with `Round(8000 / elapsed
  hundredths)`, after measuring `CRT.Delay(1000)`. Captures observed delay words
  77 and 81 on separate launches. These are calibrated CRT loop parameters,
  not portable literal milliseconds. The C++ wall-clock model normalizes this
  to 80 ms per text step; the gated capture does not prove that conversion's
  exact realized timing on every host.

## Captured evidence

`tools/capture_original_main_menu.py` uses an owned DOSBox process, dummy audio
and a private Xvfb display. Its temporary resident 4096-byte DOS arena records
the natural startup clock and gates complete delay-call windows at `0480` and
`1611`. It does not set a seed, replace clock values or write gameplay state.
The only physical menu command is `L` after the settled Italian menu.

The sealed fixture contains 128 ordered fade observations, 313 ordered text
observations (158 Italian and 155 English), two unchanged natural RNG boundary
samples, and sixteen original screenshots converted losslessly to compressed
320x200 RGB PPMs. Identical frames share content-addressed files. The recorded
run restored all three hooks and its owned DOSBox exited with code 0.

The fade-zero screenshot is checked against the actual title's decoded
palette-index-10 pixel mask. It is legitimately black apart from those white
pixels; the general gameplay blank-frame guard remains unchanged. Earlier
incomplete probes remain separate and are not labeled successful.

`main_menu_original` checks the sealed provenance and compares all 1,024,000
pixels against the production `MenuRenderer`, with no tolerance. Fifteen
mutation checks reject altered timing scope, cleanup and text observations.
`main_menu_models` checks fade/text boundaries, consumed keys, language redraw,
game return and unsigned clock rollover. Static diagnostic views remain
explicitly settled; the ordinary SDL entry point starts the animation.

`main_menu_live_xvfb` drives the ordinary app with physical X11 keys and inspects
real window pixels against the original fixture. Startup proceeds without a
timing gate. Only the queued-key check briefly stops its owned child to place
both keys in the same SDL event batch. It checks both languages, consumed
selection/Escape skips, a fresh game selection, menu return and a fresh exit.
Its captures and failure diagnostics are retained by Linux CI.

## Ungated timing observation

`evidence/main_menu_natural_20260930.json` preserves a second, successful
observation with no fade or text-delay gates. The compressed observer snapshot
beside it is the exact source identified by the recorded SHA-256; it is an
archived one-off probe, not a production entry point. Both menus matched the
phase fixtures and retained the natural seed, with zero draws, one clock hook
restored and an owned-child exit code of 0.

The first fully white menu was seen at about 15.265 seconds after sampling began
for startup Italian, and 13.600 seconds for the English redraw. Startup includes
the original load/calibration work. First-glyph to fifth-glyph checkpoint
differences were about 315 ms and 295 ms respectively. Pixel matches sample
presentation, not the precise entry time of every CRT call; these observations
do not justify silently replacing the normalized timing with a host-specific
fitted constant.

The earlier probe sent `L` as soon as full pixels appeared and failed to switch
language: the final text delay had not finished, so `L` was consumed. That run
remains incomplete. The successful probe waits 200 ms before `L`; the normal
SDL test likewise waits beyond the modeled final delay before selecting a
language. The original's drawn frame and input-readiness boundary are distinct.

## Remaining scope

This menu recovery does not change the outstanding campaign, actor contact,
collapse, two-player or manual acceptance gaps. In particular, pixel equality
at these sixteen phases is not proof of full-game parity or exact unmodified
original wall-clock timing. Help, instructions and records typing/fades need
their own original observations and recovery.
