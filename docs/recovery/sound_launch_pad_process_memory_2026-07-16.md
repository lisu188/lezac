# Launch-pad sound and marker recovery (2026-07-16)

## Result

Original callsite `1000:6924` is the sound request for the down-activated
launch pad. It writes cursor `0x0035`, priority `5`, and calls the shared latch
at `1000:165A`. The same branch gives the player vertical velocity `-2000`,
compared with `-848` for a normal jump, then creates a short-lived mode-5 actor
with frame `0x5B`, kind `0x0B`, timer `5`, and vertical velocity `-200`.

The C++ reconstruction now implements this path, including the original
Up+Down cancellation, overhead-collision rejection, Arrow Down / `C` controls,
sound request, and invisible marker lifetime. The adjacent portal path is also
behind the same Down gate, so portal activation now requires Down.

## Static executable evidence

The MZ image base is file offset `0x0770`.

- Keyboard IRQ code at `1000:10A5` maps scan codes `2C,2D,32,31,2E` to
  `Z,X,M,N,C` and input bytes `DS:1B79,1B7A,1B78,1B7B,1B7C`. Thus `C` is the
  second player's Down control; cursor scan code `50` supplies player-1 Down.
- `1000:68C5` adds Up (`DS:1B82`) and Down (`DS:1B86`) and clears both when
  their sum is two.
- `1000:68E2` requires Down. Tile `0x45` then calls the portal helper at
  `1000:5999`.
- Tile `0x27` at `1000:6912` requires the overhead flag `[BP-22]` to be zero.
- `1000:691F` stores `0xF830` (`-2000`) as player vertical velocity.
- `1000:6924..692F` writes `DS:2074=0x0035`, `DS:799F=5`, and calls
  `1000:165A`.
- `1000:6932..694D` passes player X+4, Y+13, velocity `(0,-200)`, frame
  `0x5B`, kind `0x0B`, timer `5`, and mode `5` to `1000:2F9F`.
- The mode-5 update at `1000:65A2` decrements actor byte `+2` on alternating
  `DS:78C2` ticks and removes the actor at zero.

`tools/check_sound_launch_pad_context.py` locks these bytes and call targets.

## Shipped level and tile evidence

`LIVELS.SCH` contains seven tile-`0x27` centers: four in level 6 and three in
level 7. Every center has tile `0x25` on the left and `0x28` on the right; the
rendered CARO art forms the bright central pad inside the repeated
`25 27 28 25/26` floor fixture.

The checked centers are:

```text
level 6: (105,42) (133,43) (37,53) (58,56)
level 7: (38,43)  (56,43)  (98,43)
```

## Runtime visual-table probe

The process-memory helper was extended to include `DS:C480..C4BF`. A natural
weapon-switch route was reused because the animation table is global after
level startup; this probe does not claim that level 1 reaches the launch pad.

```text
wsl.exe -d Ubuntu -e env \
  LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM=1 \
  LEZAC_SOUND_CALLSITE_APPROVE_RUNTIME_INSTRUMENTATION=1 \
  LEZAC_SOUND_CALLSITE_ROUTE_STEPS=z+x:1.50 \
  LEZAC_SOUND_CALLSITE_RUNTIME_FREEZE_BEFORE_ROUTE=1 \
  bash tools/capture_original_sound_callsite_procmem.sh \
  /tmp/lezac-visual-row-5b-20260716 . \
  actor_update_runtime_cursor_0024_sound
```

The temporary-copy run froze at runtime `01ED:6844` with `DS=0C8F`. Frame
table base `DS:C322 + 4 * 0x5B` gives `DS:C48E`, whose four bytes were zero:

```text
0C8F:C480  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
0C8F:C490  00 00 00 00 00 00 00 00 08 00 4d 30 00 00 00 00
```

`BOMOMIMK.SPR` contains 91 sprites (`0..0x5A`), so frame `0x5B` is the first
post-bank sentinel. The normalized table-only evidence is
`tests/fixtures/dosbox/launch_pad_visual_table_original.txt` and intentionally
keeps `visual_claim=0`.

## C++ validation

`--debug-autoplayer launch_pad_route` uses a real level-6 pad and verifies the
blocked-overhead path, Up+Down cancellation, impulse ratio, `0x0035/p5` pump,
marker fields, alternating five-count lifetime, and three nonblank rendered
states. `--capture-frame-sequence launch_pad_route` records five frames. The
inspected manifest showed:

```text
ready:    p1_y=320 foot_tile=39 markers=0
fired:    p1_y=314 sound=0x0035/5 marker_frame=91 marker_timer=4
airborne: p1_y=294 marker_timer=2
expired:  p1_y=276 markers=0
```

The marker is deliberately not drawn because the original table row is the
all-zero sentinel. Final inspection of `010_level6_launch_pad_ready`,
`020_level6_launch_pad_fired`, and `030_level6_launch_pad_airborne` confirmed
the player rising from the real `25/27/28` fixture with no marker pixels or
monster interference. Their hashes are `0x7d6431c67db20820`,
`0xd85346cbc938b76d`, and `0xda44258cc5a6e7b9`; every gameplay checkpoint
reports `monsters=0`.
