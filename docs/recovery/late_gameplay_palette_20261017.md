# Late Gameplay Palette Presentation

## Defect And Production Change

The normal App paints and presents the pre-actor frame at the start of
`updateWithControls`. It then advances the HUD palette and the five-frame red
palette after actor updates. Before this change those writes only changed
`PresentationState`: the displayed RGB frame retained its earlier colors until
the next draw. The actual `tickAndPresent` regression fails on that source at
frame 1 with 72 stale HUD pixels.

The original ordering is independently recorded by the retained
[red-palette capture](red_palette_runtime_2026-09-06.md): world drawing precedes
the DAC writes at CS:81CD..81F6, which recolor the already-painted indexed VGA
buffer before the completion gate. This is not permission to redraw actors
using their later positions.

`Canvas::resolvePalette` now updates only indexed pixels, without changing
indices, ownership tags, direct-RGB pixels or the drawing clip. The production
`tickAndPresent` installs a separate palette-presentation callback. Gameplay
invokes it immediately after its late palette updates, before completion.
SDL receives the retained frame again only when its resolved colors changed.
Both callbacks are cleared on success and exception. Noninteractive update
helpers and the existing pre-actor presentation callback keep their semantics.

The original red-palette replay now paints with the before-DAC palette and
resolves that retained frame after the observed palette update. Frozen fixtures,
DAC expectations and all pixel comparisons are unchanged. The separate initial
RGB clear now also clears obsolete index ownership in this diagnostic.

## Validation

- Full Linux App and affected rendering test targets build.
- Eighteen focused CTests and 19 source-guardrail controls pass on the final
  source, with all 130 runtime sources still mapped.
- The real App's 80-frame regression preserves the pre-actor image and all
  index ownership, comparing 2,295,762 indexed and 2,824,238 direct-RGB pixels.
  It checks 2,296 HUD recolorings. A deliberately seeded retained-border index
  exercises 16 world-region recolorings; this is not natural red-terrain proof.
- Canvas controls cover all 256 indices, the full 64,000-pixel surface,
  idempotence, direct-RGB overwrites, clear ownership and preservation of clip.
- Both original red-palette fixtures pass: 244 samples and 11,571,456 RGB
  comparisons, including frame rollover and byte-overflow cases. The existing
  42 fixture mutation controls still pass.
- The Linux-only SDL observer reads the rendered output immediately before
  the real `SDL_RenderPresent`, verifies every 3x3 block, and compares the final
  64,000-pixel submission with the late-palette App frame. This is a controlled
  renderer submission check, not observation of monitor scanout or an original
  instruction clock.
- A compiling fault that resolves the palette but omits the late SDL submission
  passes the buffer regression and fails SDL readback with five stale pixels.
  Production sources remain unchanged by the fault injection.
- Native MSVC 14.44 `/std:c++latest /W4 /WX` compilation and the Canvas controls
  pass. The initial strict build exposed the existing integer-zero `std::fill`
  conversion warning; making that fill value explicitly `uint8_t{0}` preserves
  behavior and removes the warning. The failed log is retained locally.

## Visual Evidence And Limits

A fresh silent interactive C++ run uses canonical assets, physical `1` and
Return keys, no debug arguments, no gameplay seed and no legacy diagnostic actor
adapter. Five captures cover main menu, intro and early/middle/late level 1.
All have exact integer scaling and unchanged canonical/private assets. The
complete child environment is derived from an explicit HOME/PATH/LANG allowlist
plus the private Xvfb and silent SDL settings. Capture intentionally stops the
game after its last observation; process exit is not a clean-game-exit claim.

The fresh gameplay capture and the retained t216 original screenshot are shown
as comparable states, not synchronized frames. Their four red ammo-icon pixels
were previously different at identical coordinates; that unsynchronized pair
alone did not prove a geometry or palette defect. Likewise the blank inventory
panel in the deterministic immediate-start capture was absent from a natural
interactive start. Neither observation justifies changing sprite geometry.

The host accumulator, complete active keyboard/PIC/foreground owner-bus
integration, instruction-time rendering, natural frame synchronization,
campaign-wide parity, active audio and owner visual acceptance remain open.
Full native Windows App and the historical large decoded clock corpora were
not rerun under the storage guard. All new validation and screenshots are
silent and RAM-only. Raw RAM, PNG captures and local binaries are not published
by this PR. Whole-game completion and frame-level fidelity remain unproved.
