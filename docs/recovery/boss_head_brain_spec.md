# Level-7 Boss Head Routine (`1000:5CB0`)

This is an instruction-level static control-flow map of the shipped routine,
not yet a runtime-equivalence claim. The bytes were checked directly in
`LEZAC.EXE`: MZ image base `0x0770`, function file range
`0x6420..0x67C2`, and Ghidra range `1000:5CB0..604F`.

The routine is reached from the behavior-6 dispatch at `1000:6555`, identifying
it as the level-7 boss-head update rather than the generic contact scanner used
in older notes. `[BP+4]` is a near pointer to the boss state. Its `SS:[arg+4]`
field is a far pointer to the associated target record.

## Recovered Fields

- Target word `+0x0E`: packed scan extents; low byte is width and high byte is
  height.
- Boss words `-0x2E` and `-0x2C`: position inputs shifted right by three to
  produce tile coordinates.
- Boss word `-0x2A`: cached tile-map base index.
- Boss bytes `-0x22`, `-0x21`, `-0x23`, `-0x24`: top, bottom, left, and right
  collision flags, respectively.
- Boss words `-0x0E` and `-0x0C`: vertical and horizontal signed velocities.
- Boss word `-0x04`: sign predicate used when choosing a new horizontal
  velocity.
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
   base = (boss[-0x2E] >> 3) * DS:C204 + (boss[-0x2C] >> 3)
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

3. At `1000:5E59`, divide `DS:78C2` by 29 and enter the stochastic branch only
   when the remainder is zero. Inside that branch:

   - `Random(100) > 70` and an even `DS:78C2` request cursor `0x69` at priority
     4 through `1000:1DCA`.
   - If `boss[-0x04] > 0`, set
     `boss[-0x0C] = Random(800) + 150`.
   - Otherwise set `boss[-0x0C] = -150 - Random(800)`.
   - If the bottom collision flag is set, set
     `boss[-0x0E] = -300 - Random(1500)`.

4. Clear `DS:661E`, scan the occupied rectangle in two-unit increments, count
   every tile equal to `0x75`, and retain the last matching index in `DS:2072`.
   If the count is nonzero, call `1000:41C6`. The returned/indexed state at
   `DS:[DS:2074 + 0x78D5]` conditionally doubles the count.

5. Compare the count with target byte `+0x24`. A greater count decrements
   target byte `+0x02`; the count is then subtracted from target byte `+0x24`.
   The routine calls `1000:61E5` with selector `0x2F`. Target byte `+0x02`
   reaching `0xFF` calls `1000:633C`.

6. Apply gravity and collision reflection:

   - When the bottom flag is clear, add `0x40` to vertical velocity `-0x0E`.
   - A top collision while velocity is negative, or a bottom collision while
     velocity is positive, replaces vertical velocity with
     `-(velocity / 2)`.
   - The equivalent left/right tests replace horizontal velocity `-0x0C` with
     `-(velocity / 2)`.

## Remaining Runtime Work

The static branch structure and constants above are pinned, but several
semantic labels still need live confirmation: ownership of target bytes
`+0x02`/`+0x24`, the result contract of `1000:41C6`, and the phase transition
entered through `1000:633C`.

For lockstep validation, seed original `DS:1AFE` and port `randomSeed_`
identically, hold player/input state constant, and capture the boss position,
both velocities, four collision flags, target bytes, and RNG seed every frame.
Promote exact trajectory and phase behavior only after those traces match.
