# Level-7 boss head brain (`1000:5CB0`) — reimplementation spec

Complete reverse-engineering of the boss head per-frame update, captured so the
port's head can be translated instruction-faithfully and diffed frame-by-frame
against the original (now feasible because the RNG is bit-exact — see
`--debug-turbo-random`). Actor fields are `ss:[di+...]` relative to the actor
record passed in `[bp+4]`; negative offsets are the head's extended state.

## Inputs / globals
- `DS:0xc204 = 140` — the fixed-point velocity-integration step used to walk the
  candidate position through the tile grid for collision.
- `DS:0xc1e0` (far pointer) — the level tile map; `es:[di+offset]` reads tiles.
- `DS:0x78c2` — head state/mode counter that gates the RNG steering branch.
- `DS:0x661e` — per-frame count of destructible (`0x75`) tiles the head overlaps.
- `DS:0x2072` / `DS:0x2074` / `DS:0x799f` — scratch for the damage/effect path.
- RNG: `0x920:0x13a8` = Turbo Pascal `Random(L)` (see the RNG recovery entry).

## Per-frame algorithm
1. **Load speed.** `al = [di+0x0e]` split into hi/lo scan bytes (`[bp-1]`,`[bp-2]`).
2. **Horizontal collision scan.** Integrate a candidate X (`pos += vel*0xc204`
   stepped `[bp-a]` times), index the tile map, and test tiles:
   - `0x4c` ("L", left wall) → set left flag `ss:[di-0x22]=1` (also `[di-0x23]`).
   - `0x52` ("R", right wall) → set right flag `ss:[di-0x21]=1` (also `[di-0x24]`).
   - `0x01` → solid.
3. **Destructible scan.** Walking the same grid, tile `0x75` ("u") increments
   `DS:0x661e` and records the overlap position into `DS:0x2072`.
4. **RNG steering** (gated on `DS:0x78c2`): `Random(0x1d)`; when the state check
   `cmp ax,0x46` (70) passes, set `DS:0x2074=0x69`, `DS:0x799f=4`, `call 0x1dca`
   (effect/sound). When the dwell timer `ss:[di-0x4] <= 0`, pick a new dwell
   `ss:[di-0xc] = Random(n) + 0x96` (≥150 frames) and a new velocity
   `ss:[di-0xe] = 0xff6a - Random(n)` (randomized leftward speed).
5. **Vertical physics.** Gravity accumulates `ss:[di-0xe] += 0x40` per airborne
   frame; on a floor/ceiling hit the velocity is reflected (`neg`, `*2`,
   `- 0x12c` for the bounce impulse) and clamped.
6. **Damage application.** If `DS:0x661e > 0` (head overlaps destructible tiles),
   double the count (`shl`), compare to the tile's remaining strength
   `es:[di+0x24]`, decrement the head/target HP `es:[di+0x02]` when exceeded, and
   subtract the consumed strength from `es:[di+0x24]`. HP reaching `0xff`
   triggers the segment/phase transition (death-chain entry).

## Verification plan (lockstep harness)
1. Seed the original `RandSeed` (`DS:0x1afe`, 4 bytes) to a known value and
   freeze the player at a fixed tile; capture the head's `x,y,velocity` each
   frame from the `DS:0x1BAE` actor table for N frames.
2. Seed the port's `randomSeed_` identically, place the player identically, and
   run the reimplemented head for N frames.
3. Assert zero per-frame divergence in `x,y,velocity`. Repeat per segment link
   and then per enemy behavior.

This spec plus the bit-exact RNG reduces the remaining work to a mechanical
translation of the above into the port's boss-head update, verified by the
harness rather than inferred statically.
