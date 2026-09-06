# Shared Visual Order

## Result

The production renderer now composites the two player slots first, then
non-player actors in the stable shared order recovered in PR #220. Effects,
bombs, monsters and rewards no longer have a hardcoded type-based depth.
Existing sprite selection, transparency, collision-to-visual Y offsets,
camera clipping and shake row-copy handling are retained.

Two original render-boundary captures contain 40 views each: full-width
312x152 and split-width 152x152. All 80 views match the corrected renderer,
covering 2,821,120 pixels with zero differences after palette normalization.
The pre-fix full-width replay has 1,618 differing pixels, including 122 in
the four-type `mixed_forward` checkpoint. Reversing each of the six actor
type pairs produces distinct original pixels, so the probes discriminate
actual layering rather than merely passing with non-overlapping sprites.

These are explicitly seeded visual scenes. They do not prove natural-route,
whole-screen HUD, actual VGA color, right-view gameplay or whole-game parity.
The split capture initializes two-player mode to obtain its 160-byte buffer
pitch, then isolates the left render pass. P2 overlap probes deliberately
retain the second sprite in that view, not the complete two-player update.

## Static Mapping

The sprite renderer is in module 08AC, file base 0x9230. File 0x9437
(08AC:0207) reads the visual count DS:C496. BX starts at zero at 0x9445,
then advances by eight at 0x9513, decrementing the count and looping to
0x9447. Thus DS:C21E + slot*8 is composited in increasing slot order after
the tile plane. Slot 0 is P1; slot 1 is reserved for P2.

Visual records contain X/Y, width/height and the sprite-data offset. The
unclipped 0x94ff..0x9508 and clipped 0x95dc..0x95e5 loops skip pixel index
zero; every other pixel replaces previously drawn content. Sprite data is
read through DS:C1FA and written to the DS:C212 buffer at base DS:C214,
with pitch DS:C1EC. The signed clipping branches precede those loops.

The C++ renderer consumes `sharedActorEntries()` in the same relative order.
Typed drawing helpers accept an identity filter so sprite/hotspot logic is
not duplicated. Directly seeded legacy diagnostics receive identities before
drawing; production actors already receive them at construction. A converted
actor retains its existing identity, and stable deletion does not reorder
survivors. The existing row-carry rendering pass uses the same ordered list.

## Capture Provenance

Original executable SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

`tools/capture_original_visual_order.py` runs a temporary original-game copy
under the existing private Xvfb/DOSBox seeder. Surface output, no scaler,
frameskip zero and fixed 6000 CPU cycles are used. The startup/intro/level-start
waits are 10/8/5 seconds. Menu key `1` initializes the full-width run and `2`
initializes the split run. No original executable or shipped asset is patched
on disk.

Seventeen instruction windows are checked statically and in child memory.
Register/FLAGS-preserving polling trampolines stop at main CS:7A13 before
camera/rendering and CS:7A57 after presentation, before the actor pass.
Actual CS=01a2, DS=0c44, SS=18b3; the after-render ES is a000. Helper constants
01ed/0c8f remain relative to the adjusted host-memory base, not the sampled
registers. Saved register pairs and consecutive frame numbers are recorded.

The initial 60x33 byte map, 60,000-byte backdrop and all 368 sprite-descriptor
bytes are captured. Each case restores the map, disables spawners/non-player
updates and seeds only the visual array plus camera/shake inputs. Map bytes,
visual records and frame count must remain unchanged across the render
boundary. P1 is normally at (247,135); overlap pairs are offset (40,-20)
from P1, while player/actor probes overlap at P1's position. Other cases
place sprites partially outside the left/right/top/bottom/corner bounds or
exercise shake 7 across all eight fine-X phases.

The first attempt put an inactive zero-size P2 descriptor inside the view
and timed out before the first after-render checkpoint. The original inner
blitter does not have a general zero-width guard. The successful probes
instead park the inactive placeholder at signed coordinates (-1,-1), where
the original bounds checks discard it. No failed-attempt fixture is promoted.

Commands after copying shipped assets into the named temporary directories:

```sh
python3 tools/capture_original_visual_order.py \
  --run-dir /tmp/lezac-visual-order2 \
  --out build-codex-tmp/visual-order-single-v2.txt \
  --approve-procmem --approve-runtime-instrumentation
python3 tools/capture_original_visual_order.py --split-view \
  --run-dir /tmp/lezac-visual-order-split1 \
  --out build-codex-tmp/visual-order-split-v1.txt \
  --approve-procmem --approve-runtime-instrumentation
```

Promoted unchanged captures, normalized LF SHA-256:

- `tests/fixtures/visual_order_single_original.txt`:
  `9246ffa78c6a1769f4135e9366aa7a43f9a981786480d4e2192b1ea636fd6a6d`.
- `tests/fixtures/visual_order_split_original.txt`:
  `3a24807c699371aee1504d332405351337364ee9dfa78fb75ff4210d108fb0aa`.

## Validation And Inspection

The C++ replay validates scene/visual consistency, sprite descriptors,
camera globals, frame continuity, provenance and complete case coverage,
then compares all view pixels against the captured indexed pixels mapped
through the existing normalized palette. Original skyline data is explicit
input; independently regenerated gradient bands are also checked. The guard
separately recomputes all 80 indexed SHA-256 digests in Python.

Six new CTests cover both replays, both offline capture contracts and one
fixture guard per viewport mode. Each guard accepts LF/CRLF, rejects two
truncations and 49 mutations, and checks for unrequested frame output. A
coherent mutation reverses both actor labels and visual rows while retaining
the original pixels, ensuring the renderer must actually use the layer order.
Other mutations cover pixels, position, count, descriptors, camera, registers,
coverage and malformed records. The six focused tests pass in 31.98 seconds.
The existing 474 tests pass in 119.70 seconds; log:
`build-codex-tmp/visual-order-baseline-tests.log`.
All 480 tests in the expanded suite, including interactive Xvfb checks,
pass in 106.36 seconds; log: `build-codex-tmp/visual-order-full-tests.log`.

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-visual-order-original tests/fixtures/visual_order_single_original.txt \
  build-codex-tmp/visual-order-single-cpp-v1
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/lezac_cpp \
  --debug-visual-order-original tests/fixtures/visual_order_split_original.txt \
  build-codex-tmp/visual-order-split-cpp-v1
```

Original normalized frame-buffer previews and live DOSBox screenshots are
exported at eight checkpoints per mode. C++ exports every view and a manifest
with frame, pitch, visual count, shake, differing-pixel count and frame hash.
The original and pre-fix `mixed_forward` previews were inspected and shown to
the user, followed by the matching corrected C++ preview. The matching
split-width `two_players_mixed` pair was also inspected and shown. Color-normalized
frame-buffer previews, not the separately captured DAC presentation, support
the zero-pixel comparison.

## Open Launch-Marker Evidence

The `last_sprite_control` independently confirms that one-based sprite 91
(0x5b), at DS:C48E, is a real 12x10 sprite with descriptor `0c0a994d` in the
current original captures. The older
`tests/fixtures/dosbox/launch_pad_visual_table_original.txt` reports zero
bytes there and calls it a sentinel. That earlier invisibility conclusion
is contradicted by these guarded register-aware captures and must not be
treated as established original behavior.

Static launch code at main CS:694D passes 0x5b to the shared constructor,
whose descriptor lookup indexes DS:C322 directly. A fresh actual launch
capture is still needed to confirm the constructed row, motion/lifetime,
placement and capacity-failure behavior. The port's currently invisible
launch-marker rendering is not fixed by this ordering batch. This is a
known remaining fidelity defect to investigate, not proof from the old
source-context test. Broader live boss/player interactions, natural routes,
HUD timing and collision edge cases remain incomplete.
