# Falling-Debris Subsystem (`1000:370E` seeder, `1000:45FA` update loop)

This is an instruction-level map of the shipped routines, checked directly in
`LEZAC.EXE` (MZ image base `0x0770`; every file offset below is
`ghidra_addr + 0x770`). The per-record arithmetic was additionally lockstepped
against the live level-2 measurement
(`tests/fixtures/debris_measurement_original_level2.txt`, 201-tick raw capture)
— each rule below is marked **CONFIRMED-bytes**, **CONFIRMED-bytes+capture**,
or **INFERRED**. Anything the capture window never exercised is flagged
**disassembly-only** in the last section.

Function ranges:

| Routine | Ghidra | File | Role |
| --- | --- | --- | --- |
| seeder | `370E..3A53` | `0x3E7E..0x41C3` | seed one debris record (W>0x3FFF) or one collapse record (W<=0x3FFF) |
| x-matcher | `3A7E..3B17` | `0x41EE..0x4287` | find record carrying word DS:2074, return its vx in DS:661E |
| y-matcher | `3B18..3BB1` | `0x4288..0x4321` | same, returns vy |
| x-blend | `3BB2..3D45` | `0x4322..0x44B5` | impact velocity merge, x component (contains the `3D2D` staging write) |
| y-blend | `3D46..3ED9` | `0x44B6..0x4649` | impact velocity merge, y component |
| integrator | `3EDA..3F26` | `0x464A..0x4696` | sub-accumulator step; produces DS:2090 |
| update fn | `45FA..4D3B` | `0x4D6A..0x54AB` | loop 1 (spark/effect records) then loop 2 (debris records) |
| spark remove | `452A..458C` | `0x4C9A..0x4CFC` | removes a loop-1 slot, decrements DS:2076 |
| debris remove | `458D..45F9` | `0x4CFD..0x4D69` | removes a loop-2 slot, decrements DS:207E |
| sound latch | `165A..167D` | `0x1DCA..0x1DED` | latches DS:2074/DS:799F into DS:78C0/DS:799E; **no RNG** |

RNG is Turbo Pascal `Random(L)` at `0920:13A8`
(`RandSeed = RandSeed*0x08088405 + 1; result = (RandSeed>>16) mod L`).

## Memory Model (Recovered Fields)

Globals:

- `DS:C204` — tile-map width (stride). `DS:C1E0` — far ptr, object byte plane.
  `DS:6612` — far ptr, word plane. `DS:C1FE` — segment of the object byte
  plane (loop reads push it as a segment).
- `DS:207E` — debris record high-water index. Init `0xC7` at `2BA9`
  (`c7 06 7e 20 c7 00`, file `0x3319`). Incremented **before** the record
  address is formed, so the first debris record of a level is **slot 200
  (0xC8)**; cap `0x640` = 1600 (`3753`, file `0x3EC3`) → 1401 usable slots.
- `DS:2093` — debris record array base; slot k lives at `DS:2093 + 0x0B*k`.
  `DS:207C` holds `0x209E` (= slot 1), set at `293D/2940` (`b8 9e 20 / a3 7c 20`,
  file `0x30AD`); the removal helper indexes from it with `(k-1)*0x0B`.
- `DS:2076` — loop-1 (spark/explosion-effect) record count, same 11-byte array,
  slots 1..198 (seeder cap `0xC6` at `403B`). Init 0 at `2BB4`.
- `DS:2080` — collapse record count (array base `DS:6611`, stride `0x0F`,
  cap `0xFA`=250 at `396D`). Init 0 at `2BAF`. Collapse fields the debris
  subsystem touches: `+4` flagged word, `+6/+7` vx/vy bytes,
  `+0xE` weight byte = 2 × matched-cell count (written at `3A3D..3A42`).
- `DS:78D2/78D3/78D4/78D5` — the working "lane": vx, x-subaccumulator, vy,
  y-subaccumulator of the record currently being updated (all signed bytes).
- `DS:2090` — this tick's movement delta in tile-index units
  (±1 for x, ±width for y, possibly both).
- `DS:2074` — multi-purpose parameter word: matcher input/output slot, and the
  sound-cursor argument to `165A`. `DS:799F` — sound priority argument.
- `DS:79C8` — seeder result flag: 1 = record created, 0 = capacity full.
- `DS:78C2` — global tick counter (used by the shatter dice).
- `DS:2078`, `DS:655C+2i`, `DS:6598+2i`, `DS:65D4+2i` — blend-helper staging:
  count, per-entry word, per-entry 2*index, per-entry result tag.

Debris record layout (11 bytes) — **CONFIRMED-bytes+capture** (the L2 trace
reproduces +4/+5/+6/+7/+8/+9/+A exactly; see "Capture lockstep" below):

| Off | Type | Meaning | Written at (seed) |
| --- | --- | --- | --- |
| +0 | u16 | tile index (pos = y*width + x) | `3798` |
| +2 | u16 | flagged word `W \| 0x8000` | `37E3` |
| +4 | s8 | vx (sub-units/tick; **128 sub-units = 1 tile**) | `37A1` (arg 2) |
| +5 | s8 | vy | `37AB` (arg 3) |
| +6 | s8 | x sub-accumulator | `37C5` = 0 |
| +7 | s8 | y sub-accumulator | `37CD` = 0 |
| +8 | u8 | rest counter (loop 2); lifetime countdown (loop 1) | `37D5` = 0 |
| +9 | u8 | tile code (glyph carried; copied from `objectByte[pos]`) | `37BE` |
| +A | u8 | aux; loop 2 sets bit 7 = "cascade spawned" | `37EA` = 0 |

## Frame-Level Order

`45FA` is called **once per game tick** from the dispatcher at `804E..805D`
(file `0x87BE..0x87CD`), gated on
`DS:2076 > 0 || DS:207E >= 0xC8`; immediately after it, the collapse updater
`5102` runs iff `DS:2080 > 0` (`8060/8067`). Inside `45FA`:

1. **Loop 1** (`4608..492C`): slots `DS:2076` down to 1 (**descending**;
   `[bp-2]` init at `4608`, `dec` at `4929`, back edge `492C e9 df fc`).
   These are the explosion-spark/effect records. Out of scope here except for
   one interplay: a loop-1 record writes **`0xFF`** into a cell when it moves
   onto a cell whose word matches a debris record and its own `+A` countdown
   is positive (`47CB 80 bd 9d 20 00` / `47D2 26 c6 05 ff`, file
   `0x4F3B/0x4F42`), or when the destination byte is `0x66` with word
   `> 0x7FFF` (`46A6..46AF`). The debris loop treats `0xFF` as
   "consume this fragment" (step 4 below).
2. **Loop 2** (`492F..4D37`): the debris loop. `[bp-2] = 0xC8` (`493F`,
   after the emptiness gate `4934 81 3e 7e 20 c8 00`, file `0x50A4`);
   iterate **ascending** while `[bp-2] <= DS:207E`, and the bound is
   **re-read live** every iteration (`4947 3b 06 7e 20`) — a record seeded
   mid-frame by a cascade IS updated later in the same frame
   (**CONFIRMED-bytes+capture**: L2 frame 404, record 201 seeded by record
   200's cascade already shows vy=4, rest=1 at the same tick's sample).
   Back edge `4D37 e9 0a fc` → `4944`.

## Seeder `370E` — Exact Flow

Pascal args (pushed left-to-right): `[bp+0xC]` = tile index, `[bp+0xA]` = vx,
`[bp+0x8]` = vy, `[bp+4]` = far ptr to an out byte. Reads
`W = wordPlane[index]` (`3727`).

1. `3735..373D`: if `W & 0x8000` → return (already in flight). Out byte
   untouched.
2. `3742 81 7e ee ff 3f / 3747 77 03` (file `0x3EB2`): if `W > 0x3FFF` →
   **debris branch**; else → collapse branch.
3. Debris branch (`374C..37F4`): out byte = 1 (`374F`, written **before** the
   cap check); if `DS:207E >= 0x640` → `DS:79C8 = 0`, return (`3753/37F6`).
   Else `inc DS:207E` (`375E`), then slot address
   `di = 0x0B * DS:207E + 0x2093` (`3783 6b 3e 7e 20 0b`, file `0x3EF3` —
   increment **before** the imul, hence first record = slot 200);
   `wordPlane[index] |= 0x8000` (`3770/3780`); fill the record per the table
   above; `DS:79C8 = 1` (`37EF`). The object byte at the cell is **not**
   touched at seed time (**CONFIRMED-bytes+capture**: the glyph stays put
   until the first move).
4. Collapse branch (`37FE..3A4D`): out byte = 0 (`382A`); grows a rectangle of
   equal-W cells, caps `DS:2080` at 250, fills a 15-byte record at
   `DS:6611 + 0x0F*k` (+4 = `W|0x8000`, +6/+7 = vx/vy args, +A = |vx|+|vy|,
   +8/+9/+C/+D = 0), XORs bit 15 onto every matching cell in the rectangle and
   stores 2×count at `+0xE` (`3A3D..3A42`); `DS:79C8 = 1`.
   **Disassembly-only** (never exercised in the L2 window).

No RNG anywhere in `370E`.

Seeding call sites relevant to debris:

- **Bomb consume** `6D49..6D65`: after `5AFD` consumes a bomb-object tile,
  iff `DS:661E == 1`: `370E(DS:C1E8 - width, 0, 0, &tmp)` —
  `6D57 2b 06 04 c2` (file `0x74C7`), two literal `6a 00` at `6D5C/6D5E`.
  **CONFIRMED-bytes** (zero initial velocity, seed = consumed − width).
- **Cascade on free move**, loop 2 (`4C08`, see step 7a).
- **Cascade after 0xFF consume**, loop 2 (`4A72`, see step 4).
- Loop 1 (`4751`), blend helpers (`3C23`/`3DB7`), effect spawner (`3FA1`) —
  adjacent systems.

## Loop 2 — Per-Record Tick, Exact Order

For slot `k = [bp-2]`, record `rec` at `DS:2093 + 0x0B*k`:

1. **Load** (`4950..49A1`): `pos ← rec+0` (`[bp-8]`); lanes
   `78D2 ← rec+4` (vx), `78D4 ← rec+5` (vy), `78D3 ← rec+6` (xsub),
   `78D5 ← rec+7` (ysub); `code ← rec+9` (`[bp-0x14]`);
   `fw ← rec+2` (`[bp-0xC]`, via `499D 8b 85 95 20`).

2. **Auto-shatter of fragile words** (`49A4..49C8`, file `0x5114..`):
   iff `fw > 0xFFBC` (unsigned; i.e. raw W in `0x7FBD..0x7FFF`) **and**
   `code <= 0x66`: `code = 0x76`, `rec+9 = 0x76` (`49B0/49B8`), request sound
   cursor `0x27` priority 5 (`49BD c7 06 74 20 27 00`, `49C3`, `call 165A`).
   Note: the stepper below then bumps it to `0x77` in this same tick, so this
   path never displays `0x76`. **Disassembly-only.**

3. **Frame stepper** (`49CB..4A18`, file `0x513B..0x5188`): iff
   `code >= 0x76`: unconditional `inc` of `code` and `rec+9`
   (`49D1 fe 46 ec` / `49D8` — dwell exactly 1 tick). If the incremented code
   `== 0x79` (`49DC`): terminal = `0x6B + Random(5)` iff `fw > 0xFFBC`
   (`49E8 6a 05`, `49EA call Random`, `49EF 05 6b 00`), else **`0xFF`**
   (`49F7`); stored to `rec+9` and `code` (`49FB..4A09`). Then stamp
   `objectByte[pos] = code` (`4A18 26 88 15`) — every tick while
   `code >= 0x76`. **Disassembly-only** (no shatter in the L2 window).

4. **0xFF consume** (`4A1B..4A75`, file `0x518B..0x51E5`): iff
   `objectByte[pos] == 0xFF` (`4A23`): `objectByte[pos] = 0` (`4A31`);
   remove slot via `458D(k)` (`4A39`); `wordPlane[pos] = 0` (`4A49`);
   then a **cascade check above**: if `wordPlane[pos - width] > 0` (`4A5B`,
   the only guard — `370E` itself rejects bit-15/`<=0x3FFF` words) →
   `370E(pos - width, 0, 0, &tmp)` (`4A61..4A72`). Jump to step 10.
   **CONFIRMED-bytes+capture**: both L2 fragments died through this path
   (counts 201→200 at frame 405 and 200→199 at frame 416) after loop-1 blast
   effects wrote `0xFF` into (26,38); the loop-1 attribution of the writer is
   INFERRED (mechanism byte-cited, writer not sampled).

5. **Integrate** (`4A78..4A8B`): `DS:2090 = 0`; resting flag `[bp-0x15] = 0`;
   `call 3EDA`; if `DS:2090 == 0` → resting flag = 1.

   `3EDA` exact semantics (file `0x464A..0x4696`), x axis then y axis:

   ```text
   step(v, sub, unit):            # unit = +1/-1 (x), +width/-width (y)
     unit = (v < 0) ? -unit : +unit          # 3EE4/3F0B sign of v
     sub  = sub + v   (8-bit signed add)     # 3EEB / 3F11
     if signed-overflow:                     # 3EED jno / 3F13 jno
         sub -= 0x80                         # 3EEF / 3F15
         DS:2090 += unit                     # 3EF2..3EF8 / 3F18..3F1E
     store sub                               # 3EFC / 3F22
   ```

   i.e. a signed-byte accumulator with a 128-sub-unit tile threshold; both
   axes can step in one tick (diagonal delta). `v == 0` can never overflow →
   never steps. **CONFIRMED-bytes+capture**: with vy = 4n the capture shows
   ysub = 2n(n−1) mod 128 and a `+width` step exactly when the sum crosses
   128 (frames 404, 412, 415).

6. **Support / gravity / friction / landing-shatter** (`4A93..4B32`):
   read `objectByte[pos + width]` (`4A93..4A9D 26 80 3d 00`, file `0x5203`).

   - **Unsupported** (below == 0): iff `vy < 0x7B` (signed `4AA3
     80 3e d4 78 7b / 4AA8 7d 05`, file `0x5213`) → `vy += 4`
     (`4AAA 80 06 d4 78 04`). Note the attainable maximum from a 0-start is
     **0x7C** (…,0x78,0x7C; 0x7C ≥ 0x7B stops), not 0x7B — the prior claim's
     "capped 0x7B" is the compare constant only. Then `rec+8 = 0`
     (`4AAF/4AB3 c6 85 9b 20 00` — rest counter reset). Skip to step 7.
     **CONFIRMED-bytes+capture** (vy ladder 4,8,…,0x30 in the trace).
   - **Supported** (below != 0):
     - iff resting flag == 0 (the integrator produced a step this tick,
       `4ABA`): horizontal friction `4AC0..4AE2`: if `|vx| < 1` → `vx = 0`;
       elif `vx > 0` → `vx--`; else `vx++`. **Disassembly-only.**
     - **landing-shatter gate** `4AE6..4B32` (file `0x5256..0x52A2`): iff
       `vy > 0` (`4AE6`) **and** `vy > 0x3C` (`4AED`) **and** `code > 0x66`
       (`4AF4`) **and** `(DS:78C2 + k) mod 6 > 2` (`4AFA..4B0B`, an unsigned
       `div 6`, remainder test `> 2` — no RNG): `objectByte[pos] = 0x76`
       (`4B16 26 c6 05 76`, file `0x5286`), `rec+9 = 0x76` (`4B1E`),
       `code = 0x76` (`4B23`), request sound cursor `0x21` priority 2
       (`4B27 c6 06 9f 79 02`, `4B2C c7 06 74 20 21 00`, `call 165A`).
       **Disassembly-only.**

7. **Move** (`4B35..4CB5`): iff `DS:2090 != 0` (`4B35`; else resting flag = 1
   at `4CB5` and skip to step 8): `dest = pos + DS:2090` (`[bp-0xA]`,
   `4B3F..4B50`); read `db = objectByte[dest]` (`4B5B`).

   a. **Free move** (`db == 0`, `4B61..4C1D`): `rec+8 = 0` (`4B6E`);
      `objectByte[dest] = code` (`4B7E 26 88 15`, file `0x52EE`);
      `objectByte[pos] = 0` (`4B89`); `wordPlane[dest] = fw` (`4B9B 26 89 15`,
      file `0x530B` — the flagged word travels verbatim);
      `wordPlane[pos] = 0` (`4BAB`); `rec+0 = dest` (`4BB5`).
      **Cascade** (`4BB9..4C19`, file `0x5329..0x5389`): iff
      `DS:2090 != -width` (the move was not straight up, `4BB9..4BD3`) and
      `0 < wordPlane[pos_old - width] < 0x8000` (`4BE4..4BF5`):
      `370E(pos_old - width, 0, 0, &tmp)` (`4C08 e8 03 eb`, file `0x5378`),
      then `rec+A |= 0x80` (`4C0B..4C19`; set even if the seeder hit the cap —
      no `79C8` check). A word in `1..0x3FFF` above spawns a **collapse**
      record through the same call. **CONFIRMED-bytes+capture** (frame 404:
      move 3726→3826, record 201 born at 3626 carrying `0xC009`/code `0x69`,
      record 200 aux = 0x80; frame 412: record 201's own move spawned nothing
      because the vacated cell's word was already zeroed — aux stayed 0).

   b. **Blocked move** (`db != 0`, `4C20..4CAC`): resting flag = 1 (`4C20`).
      **Bounce**, iff `vy > 0` (`4C24`): `vx += Random(0x1E) - 15`
      (`4C2B 6a 1e`, file `0x539B`; `4C41 2d 0f 00`); request sound cursor
      `0xEA61 + Random(8)` priority 1 (`4C4A 6a 08` at file `0x53BA`,
      `4C51 05 61 ea`, `4C57`, `call 165A`); `vy = 0`
      (`4C5F c6 06 d4 78 00`, file `0x53CF`).
      **Velocity merge** (`4C64..4CAC`): read `w = wordPlane[dest]` (`4C6F`);
      iff `w > 0` (`4C75`): `DS:2078 = 1`; `DS:659A = 2*dest`;
      `DS:655E = w`; `call 3BB2(count=1, var @DS:78D2)` (`4C8F..4C96`);
      then `DS:655E = w | 0x8000`; `call 3D46(count=1, var @DS:78D4)`
      (`4C99..4CA9`). Else (`w == 0`): `vx = 0` (`4CAE`).
      **Confirmed in seeded original collisions**, including bounce before
      blending and new-target seeding; see
      [the 2026-09-05 capture](debris_impact_runtime_2026-09-05.md).
      The older natural movement window did not contain an impact.

8. **Lane write-back** (`4CB9..4CEB`): `rec+5 ← 78D4`, `rec+6 ← 78D3`,
   `rec+7 ← 78D5`, `rec+4 ← 78D2` (that memory order; no semantic effect).

9. **Rest counter / retirement** (`4CEF..4D31`): iff resting flag != 0:
   `rec+8++` (`4CF8`). Iff `rec+8 == 0x64` — an **equality** test, exactly
   100 (`4CFF 26 80 7d 08 64`, file `0x546F`): retire —
   `wordPlane[rec+0] &= 0x7FFF` (`4D17 25 ff 7f` / `4D2A 26 89 15`, files
   `0x5487/0x549A`; the glyph stays stamped, the word keeps its raw value
   with the flag cleared), then remove via `458D(k)` (`4D31 e8 59 f8`).
   Note the order interplay with step 6: an unsupported fragment that did not
   step has `rec+8` reset to 0 at `4AB3` **before** the `4CF8` increment, so
   it samples as 1, never 0 (**CONFIRMED-bytes+capture**, the rest=0/1
   pattern in the trace). **Retirement completing is disassembly-only** (the
   capture's fragments died at ~3 rest ticks via step 4).

10. `inc [bp-2]` (`4D34`), loop while `[bp-2] <= DS:207E` (`4944..494B`).

## Removal Helper `458D`

Args: `[bp+6]` = slot k, `[bp+4]` = caller BP (caller does `push k; push bp`).

- Iff `k < DS:207E` (`4597..45AC`): `memmove` of `(DS:207E - k) * 11` bytes
  from slot k+1 down onto slot k (`45B0..45CE`; `di = [DS:207C] + (k-1)*0x0B`
  with `[DS:207C] = 0x209E`, so dest = `DS:2093 + 0x0B*k`; `si = di + 0x0B`;
  `rep movsb`).
- Iff the caller's loop counter `SS:[caller_bp-2] >= k`: decrement it
  (`45D0..45EE`) — so after the loop's own `inc`, the record shifted into
  slot k is processed next.
- `dec DS:207E` (`45F2`).

**CONFIRMED-bytes+capture** (both removals shifted record 201's bytes into
slot 200 intact).

The loop-1 twin `452A` is identical in shape but counts `DS:2076`, and
additionally shifts the per-slot byte array at `DS:78D6+` (`457A..4583`).

## Impact Velocity Merge `3BB2` / `3D46` (called only from step 7b)

Twin routines; `3BB2` = x component (matcher `3A7E`, writes debris `rec+4` /
collapse `+6`), `3D46` = y component (matcher `3B18`, writes debris `rec+5` /
collapse `+7`). Args: `[bp+8]` = weight of the caller's own value (always 1
here), `[bp+4]` = far ptr to the lane byte. **No RNG in either, nor in the
matchers.** Flow (x variant; y identical with the alternate offsets):

1. `weight = count`; 32-bit `acc = *v * count` (`3BC0..3BDC`).
2. For `i = 1..DS:2078` (=1): `W_i = [DS:655C + 2i]` (`3BFD`).
   - bit 15 **clear** (`3C0C`): the destination is not in flight →
     `370E([DS:6598+2i] >> 1, 0, 0, &created)` (`3C23`). If `DS:79C8 == 0`
     → bail out (return **without** writing the lane byte, `3C2D`).
     If `created == 0` (collapse): tag `[DS:65D4+2i] = DS:2080` (`3C3E`) and
     `weight += collapse[+0xE]` (`3C42..3C50`); else (debris): tag
     `= DS:207E + 0x4E20` (`3C55 a1 7e 20 / 3C58 05 20 4e`, files
     `0x43C5/0x43C8`), `weight += 1` (`3C64`) — the new record's velocity is
     0 and contributes nothing to `acc`.
   - bit 15 **set**: `DS:2074 = W_i`; `call 3A7E` (`3C6F`) — scans debris
     slots newest-first (`cx = DS:207E - 0xC7`, `3AEF 81 e9 c7 00`) for
     `rec+2 == W_i` when `(W_i & 0x7FFF) > 0x3FFF`, else collapse records
     newest-first for `+4 == W_i`; a hit sets `DS:2074 = slot`
     (`3B0D a3 74 20`, file `0x427D`) and `DS:661E = rec+4` (vx). Back in
     `3BB2`: the `> 0x3FFF` re-test is applied to the **reloaded** `W_i`
     (`3C72..3C7B`), then tag `= DS:2074 + 0x4E20` and contrib 1 (debris) or
     tag `= DS:2074` and contrib `collapse[+0xE]`;
     `acc += contrib * DS:661E`, `weight += contrib` (`3C98..3CC6`).
3. `result = acc / weight` (signed long divide `0920:945` at `3CE3`).
4. Second pass over the tags: tag `< 0x4E20` → `collapse[0x0F*tag + 6]
   = result` (`3D1B`); else → `debris[0x0B*(tag-0x4E20) + 4] = result`
   (`3D2D 88 95 97 20`, file `0x449D` — this is the `3D2D` staging write of
   the forward-writeback item; **that item stays open**, see scope notes).
5. Write `result` through the var pointer → lane byte (`3D3F`).

The single-target (`DS:2078 = 1`, caller weight 1) path is now exercised
end to end by seeded original loop-2 collisions and replayed through the
production C++ mover. This includes both record classes, unsigned collapse
weights, negative truncation, newest-match selection and seeding a new
target. General multi-target helper calls and a complete natural bomb-route
collision replay remain outside that evidence. See
[the capture and validation notes](debris_impact_runtime_2026-09-05.md).

## RNG Draw Sites (lockstep order)

Within one `45FA` tick, loop-2 records draw in ascending slot order; per
record, in this order and only under these conditions:

| # | Site | File | Draw | Condition |
| --- | --- | --- | --- | --- |
| 1 | `49EA` | `0x515A` | `Random(5)` | stepper reached 0x79 **and** fw > 0xFFBC |
| 2 | `4C2D` | `0x539D` | `Random(0x1E)` | blocked move **and** vy > 0 |
| 3 | `4C4C` | `0x53BC` | `Random(8)` | immediately after #2 (same guard) |

Nothing else in loop 2, the seeder, the matchers, the blend helpers, `165A`,
or `458D` draws. The shatter dice is `(DS:78C2 + slot) mod 6`, not RNG.
Loop 1 (which runs first in the frame) can draw via its `414A` effect calls,
and the bomb-blast frame itself draws `Random(0xC8)` per consumed cell when
`DS:2072 > 0 && DS:208E < 0x0E` (`6DBA`, file `0x752A`) — both outside this
spec's loop but in the same RandSeed stream; a lockstep harness must pin the
seed at the first debris tick, not at the blast.

## Bomb Placement → Consumed Block (settled)

From `655B..6582` (file `0x6CCB..0x6CF2`), with `[bp-0x2C]` = bomb visual X,
`[bp-0x2E]` = bomb visual Y:

```text
base    = ((py >> 3) - 1) * width + (((px + 4) >> 3) - 1)     ; 655F..6582
DS:C1E8 = base + width                                        ; 6CB8..6CBF (file 0x7428..0x742F)
walk    : +1, +1, +width, -1                                  ; 6CD9, 6CEE, 6D06, 6D1B
```

So the consumed 2×2 block's top-left tile is `((px+4)>>3, py>>3)`, and after
the four iterations `DS:C1E8` rests at `base + 2*width + 1`. The capture pins
this: player pixel (200,308) → base = 3724, post-frame `DS:C1E8` = 3925 =
`3724 + 201`, exactly as measured (`pre_bomb_block_index=3925`).
**CONFIRMED-bytes+capture** for the arithmetic; the identification of the
bomb actor's visual (px,py) with the player's pixel position at drop is
**INFERRED** from this single consistent point (the formula windows are
px∈[196,203], py∈[304,311] and the player sat at (200,308)).
The port maps placement as `tx=(px+6)/8, ty=(py+12)/8` (`app.cpp`
`placeBombAt`) with block top-left `(tx,ty)` (`explosionTilesFor`); on the
captured point that yields row 40 vs the original's row 38 — flag for the
implementer, but note the two engines' player-Y pixel conventions have not
been proven identical, so this is a suspected, not proven, divergence.

Seeding on consume: per consumed cell, `5AFD` runs; iff `DS:661E == 1`,
`370E(DS:C1E8 - width, 0, 0, &tmp)` (`6D49..6D65`). The L2 blast consumed
(25,38),(26,38),(26,39),(25,39) and seeded exactly one record, at (26,37) —
the crate column cell above (26,38).

## Capture Lockstep (what the 201-tick L2 window proves)

Closed-form check reproduced by the trace with zero deviations over frames
403..416: seeded `vx=vy=xsub=ysub=0`; per unsupported tick
`ysub += vy; vy += 4` (integrator before gravity, so
`vy = 4n`, `ysub ≡ 2n(n-1) mod 128` with a `+width` move on each signed
overflow); moves at n=9 for both fragments (ysub 112+32→144); free moves
carried code and flagged word verbatim and zeroed the vacated cell; the
cascade fired exactly once per fragment history (aux 0x80 on record 200 only);
the cascade child was updated in its birth frame; both fragments were consumed
by the `0xFF` path with correct shift-down of the survivor; slots above
`DS:207E` retain stale bytes (dead memory, not cleared).

## Prior-Claim Scorecard

Confirmed as previously cited: seeder index base/increment-before-imul/cap;
zero-velocity bomb seed at `6D57/6D5C/6D5E`; gravity gate `4A9D` and
constants `4AA3/4AAA`; cascade window `4BD5..4C08`; stamp pair `4B7E/4B9B`;
impact `4C2B/4C4A/4C51/4C5F`; stepper `49CB..4A18` dwell 1; shatter gate
`4AE6..4B0B` with cursor `0x21` prio 2; retirement `4CFF/4D17/4D2A/4D31`;
loop bounds `4934`/`492C`/`4D37`; the "mover is a debris record, not a
spark" refutation.

Corrected here:

1. "capped 0x7B" → the compare constant is 0x7B; the attainable terminal vy
   from a zero start is **0x7C**.
2. "A resting fragment stamps `objectByte`/`wordPlane`" → `4B7E/4B9B` are the
   **moving** fragment's destination stamps, executed on every free move; the
   vacated cell is cleared at `4B89/4BAB`. Resting writes nothing.
3. The terminal-frame choice (`0x6B+Random(5)` vs `0xFF`) is decided by
   `flagged word > 0xFFBC`, previously unattributed.
4. New, previously unreported: the fragile-word auto-shatter `49A4..49C8`
   (cursor `0x27` prio 5); the post-`0xFF` cascade site `4A4C..4A72` (guard
   `w > 0` only); `rec+A |= 0x80` after a cascade (`4C0B..4C19`); the
   `0xFF`-consume removal path `4A1B..4A75` and its loop-1 interplay; the
   blocked-move velocity merge `4C64..4CA9` into `3BB2/3D46`; the exact
   integrator (`3EDA`, 128-sub-unit signed-overflow accumulator); the
   live-bound loop condition (`4947` re-reads `DS:207E`).

## Scope Honesty

- This spec does **not** close `natural_forward_debris_writeback_3d2d`: the
  `3D2D` staging write is intra-frame and the tick-locked capture cannot see
  it. The blend-helper description above is static.
- **Disassembly-only** (never exercised in the ORIGINAL 201-tick L2 window):
  the auto-shatter path, the fragile terminal choice, the bounce (all three
  RNG sites), the collapse branch of the seeder, horizontal friction,
  multi-bounce trajectories.
- **Since exercised** by the deeper level-2 captures
  (`tools/capture_original_debris_shatter_procmem.py`,
  `tools/capture_original_natural_forward_debris_procmem.py`, ~3900 ticks
  each, bombing the sites with the deepest free fall):
  - the LANDING-shatter path and the `0x76→0x77→0x78→terminal` playback, at
    ONE GLYPH PER TICK, with the non-fragile `0xFF` terminal
    (`tests/fixtures/debris_shatter_playback_original_level2.txt`);
  - the `3D2D` velocity merge, as three pure vx overwrites
    (`tests/fixtures/natural_forward_debris_writeback_original_level2.txt`);
  - the record removal that follows the `0xFF` consume path.
- **CORRECTED**: there is no "100-tick retirement". `4CFF cmp rest,0x64` is a
  SATURATION guard. The original's rest counter stops at 100 -- never observed
  above it across ~7800 sampled ticks in two captures -- bit `0x8000` is never
  cleared on that path, and the record is not removed; the longest observed run
  is 3359 consecutive ticks at `rest == 100`. An earlier revision of this port
  read the compare as a retirement trigger and removed the record after exactly
  100 resting ticks. The port now saturates and keeps the record, and the only
  removal on any path is the `0xFF` consume route. Guarded by
  `debris_motion_live` (free-runs 800 ticks and asserts the counter never
  passes the ceiling, that fragments survive at it, and that their cells keep
  bit `0x8000`) and by `debris_shatter_playback` (`port_saturates=1`).
- The bomb-actor-position = player-position link is a single-point inference;
  a second capture at a different pixel phase would pin it.
- Loop 1's internals (effect codes, `414A`, TP-real spark seeding at `3FA6`)
  are mapped only to the depth needed for the `0xFF` interplay.
