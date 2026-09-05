# Original Bomb Motion Recovery

The port previously kept placed bombs stationary. Original constructor and
per-update actor/visual records now establish the motion of all four player
weapons, including their distinct sprites and collision-height offsets.

## Original Instructions

Anchors use Ghidra segment `1000`; executable file offsets add `0x770`.
The executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

- `6C25..6C5B` passes the player's cached integer pixels to constructor
  `2F9F`. Launch velocity is signed `vx * 3 / 2` (truncate toward zero),
  `vy - 500`; the constructor clamps both to `+/-0x07FF` and clears fractions.
- The constructor uses sprite descriptor `weapon + 57`, corresponding to
  zero-based `BOMOMIMK.SPR` indices 57, 58, 59, 60. Their dimensions are
  8x8, 13x13, 16x16, 16x16. The former medium/large indices 59/60 were wrong.
- `6053` is the actor updater. The visual Y coordinate is normalized by
  subtracting actor `+0x14`, equal to `16 - sprite height`, before collision.
- `65DA..6640` selects four single-cell collision probes for kind `0x0D`
  (small bomb); other bombs use the standard two-cell edges. With
  `C=(x+4)>>3`, `R=normalizedY>>3`, the small probes are top `(C,R)`, bottom
  `(C,R+2)`, left `(C-1,R+1)`, right `(C+1,R+1)`. Side/top tiles are solid
  for values 1..0x4C, bottom for 1..0x52.
- Behavior 2 at `7018..7058` adds gravity `0x40` up to `0x07FF` when airborne
  or rising. Positive downward speed on a solid bottom becomes zero and Y
  snaps down to an 8-pixel boundary. Bottom contact also invokes `5B86`:
  absolute X speed below 43 becomes zero, otherwise subtract 42 toward zero.
- Common collision processing changes upward velocity to 1 at a ceiling;
  simultaneous left/right contact zeros X speed. A wall in the direction of
  motion changes X speed to `-vx/2`, then nudges X one pixel in that new
  direction (zero uses +1). Y then X integrate with the existing 8.8 helper,
  retaining fractional carry. Finally the sprite-height bias is restored.
- Motion precedes the countdown at `75A7`. Expiry dispatch uses the resulting
  visual position, not the constructor position.

The sprite-bank SHA-256 is
`08dfd0e59ba191c52af2529bdfa140fd15a57829f0c6c13bbb78e156769ac0d1`.
The capture resolves each constructed visual descriptor against live
`DS:C322`, independently checking the sprite index.

## Runtime Capture

The existing guarded bomb-fuse capture tool now also accepts real movement
input before N. For every weapon `1..4` and approach `none,left,right,jump`:

```sh
python3 tools/capture_original_bomb_fuses.py \
  --run-dir /tmp/lezac-bomb-motion-verified-20260905 \
  --out /tmp/lezac-bomb-motion-verified-20260905/weapon1_right.txt \
  --weapon 1 --parity 0 --approach right --approach-ticks 6 \
  --approve-procmem --approve-runtime-instrumentation
```

The run directory contains a temporary copy of shipped assets. Each invocation
owns its DOSBox process and private Xvfb display. XTEST uses Z/X/M for
left/right/jump, then N for fire, releasing both keys at the placement stop.
Initial arrow-key attempts produced zero velocity and were discarded. The
final tool rejects left/right/jump traces without the requested velocity sign.
The 16 promoted runs were captured sequentially into fresh output files.

Only weapon selection at `SS:BP-0x12` and optional one-frame placement-parity
adjustment are exogenous writes. No bomb position, velocity, fraction or timer
is seeded. Saved caller locals `BP-2C/-2E/-0C/-0E` provide the original player
X/Y/VX/VY input. Four register/FLAGS-preserving trampolines stop before seed
calculation, after construction, after countdown subtraction and at expiry.
Nine instruction windows are guarded; the actual motion code is unmodified.
See the [fuse capture notes](bomb_fuse_runtime_2026-09-05.md) for the
sequence-number handshake and calibrated process-memory addressing.

Runtime segments were `CS=01A2`, `DS=0C44`, `SS=18B3`. Constructor checkpoints
record `ES=0C44`, `BP=3FEE`, saved post-push `SP=3FA2`. Thus the placement
breakpoints are runtime `01A2:6C0A` and `01A2:6C5E`, while update/expiry stops
are `01A2:75B4` and `01A2:75CB`. The traces retain all six saved register words
at construction and expiry, not a guessed Ghidra-to-runtime segment mapping.

Actors are read at `DS:1BAE`, stride `0x26`, bounded by `DS:208D`. Motion fields
are signed VX/VY at `+6/+8`, fractional low bytes at `+0A/+0C`, height bias at
`+14`, and behavior 2 at `+15`. Actor `+1` selects the 8-byte visual row at
`DS:C21E` (X/Y words, width/height bytes, pixel-offset word).

For example, small/right constructs at frame 34 with player input
`109,168,448,0`, visual `6d00a8000808fc36`, VX/VY `672,-500`, zero fractions
and height bias 8. Frame 35 has X/Y `111,166`, VX/VY `672,-436`, fractions
`160,76`; frame 36 has `114,164`, `672,-372`, fractions `64,216`. The jump
route captures player VY `-464`, giving bomb launch VY `-964`.

## C++ Mapping And Coverage

`placeBombAt` seeds pixel coordinates and inherited velocity. Production
`updateBombs` moves live bombs before countdown/expiry, refreshes their blast
tile from the current pixels, and rendering uses the pixel position. Existing
tile-only explosion probes remain explicitly positioned test states; all
gameplay placements enable motion.

`--debug-bomb-motion-original tests/fixtures/bomb_motion_original [OUT]` resets
level 1 per case, seeds the captured player inputs, and calls the production
fire/placement and bomb update helpers. It compares all live motion states
against the original, with no trajectory fields injected into port bombs.
It does not replay the original player or monster input stream after fire.

- 16 constructors match their original pixel position, velocity, zero carry,
  height bias and sprite descriptor.
- 2,304 consecutive countdown samples match: 39/59/79/399 for each of four
  approaches. Of these, 2,288 still-live post-update states match X/Y, VX/VY
  and both fractional accumulators exactly. The original records contain
  five X-velocity sign reversals and 86 steps reducing absolute X speed by 42.
- All 16 expiry positions map the existing port explosion origin from the
  original's final visual pixels. This is not a full original blast-lane or
  explosion-rendering comparison; the removed actor's final velocities and
  fractional fields are not asserted.
- Pause preserves lifetime and logic frame. The separate eight-case fuse
  suite continues to cover both placement parities.
- The optional frame harness writes 64 armed/flight/last-live/expiry PPMs and
  a CSV manifest with bomb position, velocity, carry, timer and framebuffer
  hash. Expired rows record zero bomb count and no live actor state.

All 64 captured 320x200 C++ frames were checked for nonuniform RGB pixels.
The inspection sheet at `build-codex-tmp/bomb-motion-frames/inspection.png`
was viewed: small/right flight, medium/left flight, large/jump flight and
super/right last-live. The corresponding original DOSBox PNGs for all four
weapons were viewed; they show gameplay and the correct armed sprites, with
the jump case airborne. Camera/player timing differs between these screenshots;
no full-frame pixel parity is claimed. The final C++ frame hash is
`3e312fc8d2a8f211`.

The first full-suite run exposed an obsolete collapse-route assumption: its
moving small bomb no longer detonates at the drop point. Simply releasing
movement was also insufficient, because the small bomb lands atop the
one-way platform at tile origin `(24,20)`, above the bomb object `(24,22)`.
The route now walks to the same position and uses the actual weapon-switch
chord twice to select a stocked large bomb, releasing movement before fire.
Its 16px sprite/collision height leaves the throw below the platform. No
player teleport, bomb repositioning, timer shortening or collapse seeding is
used. The unchanged collapse assertions pass: two-cell group started,
23 subsequent playback frames, three inspected and distinct framebuffers.

Final validation: `cmake --build build -j2` succeeded. The full CTest run
covered 421 cases with no failures in 298.04 seconds: 420 passed under dummy
SDL and the intentionally skipped UI case passed separately under Xvfb in
4.12 seconds. `git diff --check` passed. The existing unrelated debris-debug
`snprintf` truncation warning remains unchanged.

## Remaining Boundaries

The 16 trajectories cover this level-1 geometry, not all levels, all possible
launch velocities or cross-game frame alignment. The constructor clamp is
instruction-backed but these six-frame approaches do not reach its extremes.
Bomb allocation capacity and repeated placement in one tile remain separate
fidelity questions; this change retains the port's existing placement gate.
Full blast-lane, damage and explosion visual parity remain separate work.
The overall game is not claimed fully reverse engineered by this recovery.
