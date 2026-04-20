# Ghidra Notes for LEZAC.EXE

Ghidra 12.0.4 imports `LEZAC.EXE` as:

- Loader: `Old-style DOS Executable (MZ)`
- Language: `x86:LE:16:Real Mode`
- Entry: `1000:7783`
- Header size: `0x770`

The executable is a Borland/Turbo Pascal DOS program. The original on-disk far
segment references are relocated by the MZ loader. For example, the on-disk call
bytes targeting `082d:0000` are relocated by Ghidra into memory at
`182d:0000`.

## Confirmed Routines

| Address | Name | Notes |
| --- | --- | --- |
| `1000:0c33` | level loader | Opens/seeks in `LIVELS.SCH`, reads the level header, allocates level buffers, reads compressed layers and entity blocks. |
| `1000:0faa` | level loader wrapper | Sets up stack frame and calls `1000:0c33`. |
| `182d:0000` | `rle3_decode` | Decodes the two `LIVELS.SCH` compressed layers from 3-byte run commands. |
| `1000:2efd` | new game state | Opens `LIVELS.SCH`, initializes player state, lives/energy flags, and level globals. |
| `1000:3358` | remove actor slot | Compacts 0x26-byte actor records and adjusts ordering in other active lists. |
| `1000:3587` | update camera | Computes tile-aligned scroll offsets from player coordinates and level dimensions. |
| `1000:370e` | tile fragmentation/collapse | Marks damaged tiles and queues 0x0b-byte falling/debris records. |
| `1000:1091` | keyboard IRQ handler | Reads port `0x60` and tracks scancodes for both players. |
| `1000:26e8` | startup/input setup | Sends keyboard typematic commands, saves `INT 09h`/`INT 1Ch`, installs handlers, and allocates runtime buffers. |
| `1000:6053` | entity update candidate | Updates object animation, positions, controls, and collision/object behavior. |
| `18ac:00f4` | transparent blit/object draw | Copies sprite pixels with zero treated as transparent. Palette index `0xff` is visible. |

Ghidra decompilation is not very useful for the Pascal code because of 16-bit
segmented pointers and runtime helper calls, but disassembly was useful enough
to confirm the file and RLE formats used by this port.

## Level RLE

The routine at `182d:0000` takes source and destination far pointers plus a
target output length. It does not use the compressed byte count directly; the
record length is used by the caller to advance in the level file.

Each command is:

```text
u8 command
u8 first_value
u8 second_value
```

The high nibble of `command`, plus one, is the first run length. The low nibble,
plus one, is the second run length. The Pascal routine writes each run with an
inclusive loop and then advances by the nominal run length, so adjacent runs
overwrite one byte at the boundary. The C++ port preserves this compatibility
quirk.

## Confirmed Data Files

- `BOMPAL.PAL` is exactly 768 bytes: 256 VGA RGB values using 6-bit channels.
- `SFONLEF.ZBG` starts with a 768-byte palette and then PCX-style RLE bytes
  for a 321x388 indexed background.
- `CARO.CAR` starts with a big-endian 16-bit tile count, followed by raw 8x8
  indexed tiles.
- `FONTS.SPR`, `PROVA.SPR`, and `BOMOMIMK.SPR` start with an 8-bit sprite
  count. Each sprite then has 8-bit width, 8-bit height, and raw indexed pixels.
  `FONTS.SPR` stores large `A-Z`, compact `A-Z`, compact `0-9`, then period,
  colon, semicolon, comma, exclamation, and apostrophe/accent glyphs.
- `RECS.DAT` starts with an 8-bit record count. Each record is a little-endian
  32-bit score, an 8-bit reached level, and an 8-byte name padded with `:`.
- `PROEFS.SON` starts with a little-endian 16-bit record size. The shipped file
  uses 130-byte records and contains six fixed-size records. The bytes are now
  loaded, dumpable, and approximately synthesized by the SDL port, but the
  exact playback field semantics are still unresolved.
- `GRAN.MST` has no observed header in the shipped file. It is seven fixed-size
  57-byte records, likely aligned with the seven shipped levels, but the field
  semantics are still unresolved.

## Level Entity Blocks

After the two compressed `LIVELS.SCH` layers and two extra words, the level
loader reads three counted fixed-size blocks:

- 30-byte records are monster spawners. The runtime loop around
  `1000:7a6b-7c2c` checks enabled/budget/live-count/cooldown fields and creates
  active 0x26-byte actor records. Observed monster kinds are `1`, `2`, `3`, `4`,
  `6`, and `9`. Spawned actors retain a source-spawner id so actor removal can
  return the live slot to the spawner, matching the behavior seen around
  `1000:74f9`.
  The last two bytes are split in runtime use: byte `0x1c` reloads the spawner
  cooldown and byte `0x1d` is passed to the actor animation initializer as a
  delay value.
- In the shipped level records, the normal monster kinds observed are `1`, `2`,
  `3`, and `4`. The executable uses lookup tables rather than the monster kind
  as a direct sprite index. The currently confirmed zero-based `BOMOMIMK.SPR`
  normal animation ranges are: player 1 `0..18`, player 2 `19..37`, kind 1
  left `43..44`, kind 1 right `45..46`, kind 2 `39..41`, kind 3 `49..51`, and
  kind 4 `53..55`. The adjacent frames `42`, `47`, `48`, `52`, and `56` are
  impact/extra frames from related tables, not ordinary looping frames.
- `LIVELS.SCH` contains 15 enabled monster spawner records across levels 1..6;
  level 7 has none. Their shipped monster-kind counts are kind 1: seven, kind
  2: two, kind 3: three, and kind 4: three. Behavior values are behavior 3:
  nine records and behavior 4: six records.
- Monster reward sprites follow `BOMOMIMK.SPR` indices `61..67`, matching the
  score table sequence found near executable file offset `0xb1c6`:
  present `61`/2000, first aid `62`/1000, hot dog `63`/1500, jolly cloud
  `64`/2000, yellow bomb box `65`/3000, green bomb box `66`/1000, and big
  diamond `67`/5000.

## Actor Movement Behaviors

The shipped spawners use actor behavior values `3` and `4`.

- Behavior `3` is a ground walker. The C++ reconstruction uses randomized actor
  parameter `ai0` as an 8.8 fixed-point horizontal speed magnitude, applies
  gravity, and flips direction/profile on wall or ledge collision.
- Behavior `4` is timed retarget/random movement. The reconstruction uses `ai0`
  as the retarget tick period, `ai1` as 8.8 fixed-point movement magnitude, and
  `ai2` as the Manhattan-distance threshold for chasing the player before
  falling back to random signed velocities. Each active actor carries its own
  countdown so actors spawned at different times do not retarget in lockstep.

These mappings follow the Ghidra analysis around `1000:70bc..7148` and
`1000:728c..731b`.

Active monsters now use the original-style signed 8.8 velocity fields and
fractional accumulator bytes. The integration helper mirrors the byte-carry
logic at `1000:73e5..741b`: add the low velocity byte to the fractional byte,
then add the signed high velocity byte plus carry to the integer position. This
preserves the original floor-style behavior for negative fractional velocities.

## Bomb Inventory

The original tracks four bomb counts rather than a single radius. New-game setup
initializes the single-player inventory to `200, 20, 6, 0`; the fourth, strongest
bomb type starts unavailable. Left+right together cycles to the next nonempty
weapon. Fire consumes one count from the selected weapon and then places a bomb
actor. Yellow bomb boxes replenish the normal set, while green bomb boxes
replenish/unlock the super set.

The reconstruction now models that inventory and switching. Bomb placement uses
the actor kind mapping `0x0d..0x10` and fuse values `20, 30, 40, 200` from
`1000:6bdf..6c59`; those values are countdown ticks, not blast radius.
Expiration processes the original-style 2x2 tile footprint:
`(x,y)`, `(x+1,y)`, `(x+1,y+1)`, `(x,y+1)`.

Only object tiles `0x67..0x72` are consumed directly by the bomb helper at
`1000:5afd`. When that helper enables physical damage, the reconstruction now
routes the tile above the footprint cell through a `1000:370e`-style word-layer
path: bit `0x8000` means already damaged, words `>0x3fff` enqueue one deferred
debris record, and lower words flood-fill a matching connected group and enqueue
a collapse record. The high-word 11-byte debris payload is represented with its
known fields; the lower-word collapse payload remains provisional until its
playback routines are fully mapped.

Bomb actor expiration at `1000:75f1..75fb` calls the dispatcher at `1000:414a`
with a selector derived from the actor kind. The selector branches are `1..4`;
the dispatcher then sets state/sound selectors `4..7` and record offsets
`0xea74`, `0xea7e`, `0xea88`, and `0xeace`. The visible parameter packs
reference sprite/effect ids `0x84..0x89` and seed per-variant bytes
`8/5`, `9/5`, `9/3`, and `0x3a/0x0a` alongside a fixed detail byte `0x75`.
The C++ reconstruction carries these selector/state/offset fields in a typed
explosion effect and renders a simplified local effect until the exact playback
routines are fully mapped.

The high-word debris branch in `1000:370e` writes an 11-byte record at
`0x2093 + 0x0b * count`: word tile index, word `word | 0x8000`, byte argument
pair, three zero bytes, one lookup byte from `[0xc1e0 + tileIndex]`, and a final
zero byte. Any reconstruction-only lifetime is separate from that payload.

The playback helpers at `1000:3a7e` and `1000:3b18` are forward/reverse lookup
passes. They split damaged words on bit `0x8000` and threshold `0x4000`, then
load the forward byte from collapse/debris record offsets `+6`/`+4` and the
reverse byte from offsets `+7`/`+5`. The collapse passes at `1000:3bb2` and
`1000:3d46` write those lanes back through `0x6617`/`0x2097` and
`0x6618`/`0x2098`, using `0x4e20` as the high-half spill marker.

## Level Embedded Records

- The two words immediately after the decoded tile and word layers are preserved
  as unresolved `fieldA`/`fieldB` values. In the shipped levels their pairs are:
  level 1 `0x4005`/`0x0042`, level 2 `0x401e`/`0x0189`, level 3
  `0x4036`/`0x02e3`, level 4 `0x403c`/`0x01b3`, level 5 `0x4066`/`0x03dc`,
  level 6 `0x409f`/`0x0aa4`, and level 7 `0x4041`/`0x014a`.
  The second word exactly matches the count of nonzero low word-layer cells
  (`word < 0x4000`) in each shipped level, so the C++ port now treats it as the
  original physical-damage progress denominator. Destruction completion advances
  when low-word collapse groups are damaged, not when visible tile ids or
  trigger rewrites change. The low 14 bits of the first word are
  close to, but do not always equal, the high-word cell count; its exact meaning
  remains unresolved. It also does not match high-word unique counts or
  connected-component counts in the shipped levels.
- 7-byte records are start and teleport destinations: `u16 key`, `u16 x`,
  `u16 y`, `u8 marker`. Key `0` records with marker `1` and `2` are player
  starts. Tile `0x45` uses the word-layer key to select a nonzero destination.
- 14-byte records are tile-trigger rewrite rules: `u16 range_first`,
  `u16 range_last`, `u16 trigger_key`, four source tile ids, and four
  replacement tile ids. Tile `0x72` passes its word-layer key to the trigger
  matcher. The scan masks level word-layer values with `0x7fff` before applying
  the word range.

## Raw Level Roundtrip

`--debug-level-raw-roundtrip` parses original `LIVELS.SCH` directly and compares
the result with `src/LIVELS.SCH.json`. This locks the current file-format
understanding to the shipped binary asset: seven levels, 47,700 decoded cells,
15 spawners, 21 portals, and three trigger rules. Confirmed level file offsets
are `0`, `1242`, `4923`, `10984`, `15225`, `21546`, and `36128`.

## Record Entry Evidence

Manual byte/disassembly inspection of `1000:1845..1ad4` shows the high-score
name-entry path accepts `A..Z` plus space, stores typed letters by applying
`or 0x20`, handles Backspace as `0x08`, commits on Enter `0x0d`, and stores the
eight-byte name with colon padding. The C++ port follows those input rules while
retaining `Esc` as a reconstruction-only cancel path so failed or accidental
entries can be abandoned from the SDL menu.

## Code Mapping

- Level JSON loading: `loadLevels`; raw binary validation: `loadRawLevels`.
- Pascal-compatible level RLE: `decodeLevelRle3`.
- Actor 8.8 integration: `integrateAxis8_8`.
- Bomb expiration and physical damage: `explode`, `queueTileDamage`,
  `damageMonstersInExplosion`.
- High-score load/save/name entry: `loadRecords`, `saveRecords`,
  `handleNameEntryKey`, `finalizePendingRecord`.
- Debug surface: command dispatch in `main`.
