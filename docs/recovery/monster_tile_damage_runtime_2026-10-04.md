# Full Monster Tile-damage Writeback

## Original Observation

Two independent silent original captures agree on 1,312 full behavior-4
updates of kinds 1..8, ending at the actual `1000:777F` return. They retain
raw stack locals, the complete 38-byte actor and eight-byte visual records,
instruction windows, terrain hashes, bootstrap images and restoration proof.
Actor records and terrain are explicitly seeded at each case boundary.
Shared animation/AI profiles are borrowed, not natural shipped constructors.

The first 1,024 cases cover eight kinds, eight glyph boundaries
(`0`, `1`, `0x4C`, `0x4D`, `0x52`, `0x53`, `0x75`, `0xFF`) and all 16 subsets
of the four interior footprint cells. Another 192 cases cross 32 pixels in
one update: 96 put damage only under the pre-motion footprint, and 96 put it
only under the post-motion footprint. Ninety-six low-health cases establish
fatal conversion, both velocity signs and the stationary discriminator.
All observed side/top/bottom flags are zero; this is embedding damage rather
than terrain-edge reflection. There are 552 impacts and 96 fatal conversions.

The native helper `1000:56B6` sums one damage per solid `1..0x4C` cell and two
per flame `0x75` cell; the other sampled glyphs contribute none. Its caller
uses the pre-motion footprint. Impact changes the displayed descriptor while
preserving the animation cursor, sets the byte counter to `delay - 4 = 255`
and changes the hotspot before visual-coordinate writeback. Fatal conversion
changes kind to 12, behavior to 2, timer to 25 and animation mode to zero.
This observation ends at that conversion, not the subsequent corpse lifecycle.

## Production Correction

The full production diagnostic first failed exactly 276 impact/conversion
cases for kinds 5..8. The C++ table contained only kinds 0..4 and selected
the kind-0 fallback for the remaining kinds. The shipped data at image
`0xAA97` (DGROUP `DS:0x77`) and the live descriptor writes independently agree
on these file-sprite entries:

| Kind | vx <= 0 | vx > 0 |
| --- | --- | --- |
| 1 | 47 | 48 |
| 2 | 42 | 42 |
| 3 | 52 | 52 |
| 4 | 56 | 56 |
| 5 | 0 | 1 |
| 6 | 10 | 10 |
| 7 | 11 | 11 |
| 8 | 12 | 12 |

Extending that existing table makes all 1,312 real `updateMonsters()` calls
match motion, fractions, RNG, actual health, hotspot, animation fields,
fatal conversion and the full visual descriptor. No damage formula, terrain
rule, motion rule or constructor was changed. Negative source commit is
`ee4ee0908bfa99b75f4ed1f32c37cf67e2d321cf`; corrected replay source is
`d7c3cd13ff4ab8c665d1cae0898e9e51fa38332f`.

## Earlier Health Attribution

The older coordinate/writeback compact records preserve actor byte `+3`
as their penultimate field. That byte is **not health**; the original health
byte is `+0x24`, represented in C++ as `hp - 1`. Their archived raw actors
seed `+0x24 = 255`. Earlier diagnostics seeded C++ HP 11 and incorrectly
compared it to byte `+3 = 11`, although those blank-terrain cases never dealt
damage. Their immutable fixtures and raw evidence remain unchanged. Those
diagnostics now seed HP 256 and verify that it remains unchanged, consistent
with the complete archived raw actor records. Their historical compact
field is not reinterpreted as health. The new fixture retains all 38 bytes.

## Fixture and Scope

`tests/fixtures/monster_tile_damage_original.bin` has a 64-byte original/window
header and 1,312 80-byte records (20 seed bytes, 14 motion/RNG bytes, 38 actor
bytes, eight visual bytes). Total size is 105,024 bytes; SHA256 is
`8417f07de35ddd512032ee8eccfadccd36be386776f0e6770f01bd05ec30d7b1`.
The production FNV guard is `de39ea57d77e51de`. Six CTests cover the actual
caller, fixture, all single-byte mutations, malformed production inputs,
retained raw evidence and observer self-check. Fresh original CI re-extracts
the complete records. See `evidence/monster_tile_damage_20261004/README.md`.

Natural constructors, nonzero initial hotspots, other behaviors, simultaneous
actors/players, repeated damage and complete campaign trajectories remain
outside this fixture. The actor-contact and behavior-4 items stay OPEN;
`port_functionally_complete=0`, `original_fidelity_claim=0` and `visual_claim=0`.
