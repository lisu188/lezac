# Level-7 Boss Head Routine (`1000:5CB0`)

This is an instruction-level static control-flow map of the shipped routine,
not yet a runtime-equivalence claim. The bytes were checked directly in
`LEZAC.EXE`: MZ image base `0x0770`, function file range
`0x6420..0x67C2`, and Ghidra range `1000:5CB0..604F`.

The routine is reached from the behavior-6 dispatch at `1000:6555`, identifying
it as the level-7 boss-head update rather than the generic contact scanner used
in older notes. The caller executes `push bp`, so callee `[BP+4]` is the caller
frame pointer. `SS:[caller_bp+4]` is the active actor far pointer; negative
offsets used by `1000:5CB0` are actor-update caller locals.

## Recovered Fields

- Actor word `+0x0E`: packed scan extents; low byte is width and high byte is
  height.
- Caller locals `-0x2E` and `-0x2C`: visual Y/X positions shifted right by
  three to produce tile coordinates.
- Caller local `-0x2A`: cached tile-map base index.
- Caller locals `-0x22`, `-0x21`, `-0x23`, `-0x24`: top, bottom, left, and
  right collision flags, respectively.
- Caller locals `-0x0E` and `-0x0C`: vertical and horizontal signed velocities,
  loaded from actor words `+0x08` and `+0x06`.
- Caller locals `-0x04`/`-0x06`: selected player's X/Y delta. Locals
  `-0x08`/`-0x0A` initially hold player 2's delta.
- `DS:C204 = 140`: tile-map row stride, not a velocity-integration step.
- `DS:C1E0`: far pointer to the level tile map.
- `DS:78C2`: global tick/state value used by the periodic RNG gate.
- `DS:661E`: overlap count for tile value `0x75`.
- `DS:2072`: last overlapping tile-map index.
- RNG `0920:13A8`: Turbo Pascal `Random(L)`, pinned by
  `--debug-turbo-random`.

## Exact Control Flow

1. Build the tile-map base index:

   ```text
   base = (caller[-0x2E] >> 3) * DS:C204 + (caller[-0x2C] >> 3)
   ```

2. Scan all four edges of the packed width/height rectangle:

   | Edge | Start | Step | Samples | Solid range | Flag |
   | --- | --- | --- | --- | --- | --- |
   | top | `base - stride` | `+1` | width | `1..0x4C` | `-0x22` |
   | bottom | `base + height*stride` | `+1` | width | `1..0x52` | `-0x21` |
   | left | `base - 1` | `+stride` | height | `1..0x4C` | `-0x23` |
   | right | `base + width` | `+stride` | height | `1..0x4C` | `-0x24` |

   The comparisons are inclusive ranges. Values `0x4C` and `0x52` are upper
   bounds, not the only colliding tile values.

3. Before the behavior dispatch, `1000:62F5..6346` computes each active
   player's X/Y delta from the actor. `1000:6500..654D` compares
   `abs(dx) + abs(dy)` and copies player 2's pair into `-0x04`/`-0x06` only
   when player 2 is strictly nearer; ties retain player 1.

4. At `1000:5E59`, divide `DS:78C2` by 29 and enter the stochastic branch only
   when the remainder is zero. Inside that branch:

   - `Random(100) > 70` and an even `DS:78C2` request cursor `0x69` at priority
     4 through the sound latch at `1000:165A`.
   - If caller delta `-0x04 > 0`, set horizontal velocity
     `-0x0C = Random(800) + 150`.
   - Otherwise set horizontal velocity `-0x0C = -150 - Random(800)`.
   - If the bottom collision flag is set, set
     vertical velocity `-0x0E = -300 - Random(1500)`.

5. Clear `DS:661E`, scan every row and every second column, count
   every tile equal to `0x75`, and retain the last matching index in `DS:2072`.
   If the count is nonzero, call `1000:3A56`. The returned/indexed state at
   `DS:[DS:2074 + 0x78D5]` conditionally doubles the count.

6. Compare the count with actor byte `+0x24`. A greater count decrements actor
   byte `+0x02`; the count is then subtracted from actor byte `+0x24`.
   The routine calls `1000:5A75` with selector `0x2F`. Actor byte `+0x02`
   reaching `0xFF` calls `1000:5BCC`.

7. Apply gravity and collision reflection:

   - When the bottom flag is clear, add `0x40` to vertical velocity `-0x0E`.
   - A top collision while velocity is negative, or a bottom collision while
     velocity is positive, replaces vertical velocity with
     `-(velocity / 2)`.
   - The equivalent left/right tests replace horizontal velocity `-0x0C` with
     `-(velocity / 2)`.

## Remaining Runtime Work

The static branch structure and constants above are pinned, but several
semantic labels still need live confirmation: ownership of actor bytes
`+0x02`/`+0x24`, the result contract of `1000:3A56`, and the phase transition
entered through `1000:5BCC`.

For lockstep validation, seed original `DS:1AFE` and port `randomSeed_`
identically, hold player/input state constant, and capture the boss position,
both velocities, four collision flags, actor bytes, and RNG seed every frame.
Promote exact trajectory and phase behavior only after those traces match.
