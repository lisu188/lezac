# Original Reserve HUD Entry

The original near Pascal routine `29DB..2A3E` is now an accepted entry of
`core::FrameHudOperation`. It executes the real CRT stack check at `0920:04DF`
and the existing complete `1156..1173` opaque 8x8 blitter. The snapshot layout,
outer `79E8` entry and objective `3184` entry retain their existing contracts.

## Recovered Behavior

- The caller's word argument selects the player reserve byte at `DS:79E9+p`
  and horizontal destination word at `DS:79F2+p*2`.
- Three slots are always drawn. Slot numbers 1 through 3 use the filled glyph
  while the unsigned reserve byte is at least that number; remaining slots use
  the empty glyph. Counts above three do not add more slots.
- The empty glyph starts at `DS:[C208]`; the filled glyph starts at that offset
  plus `1CC0`, with 16-bit wrap. In the shipped CARO atlas these are tiles 0 and
  115. Every glyph byte is copied, including palette index zero.
- The destination begins at `x+F000`, with 16-bit wrap, and advances nine bytes
  after each slot. The original shared scratch words `2072` and `2074`, stack
  contents, `CWD`/`ADC` side effects and Pascal `RET 2` cleanup are retained.
- The blitter honors DF. The caller does not insert a synthetic `CLD`.

The live `HudPainter` previously painted up to six figures using a transparent
tile helper. The new production-renderer regression failed before the fix at
case 0, slot 0, row 0, column 0. The painter now draws three opaque filled/empty
slots at the existing column positions and `y=192`. Negative typed out-player
values remain blank. That legacy out-state policy is not claimed to be a new
original-backed call-timing implementation.

## Original Execution Evidence

`tools/reserve_hud_oracle.py` runs unchanged, MZ-relocated `LEZAC.EXE` instructions
using the repository's pinned Unicorn 2.1.4 Linux library. It verifies both the
actual mapped library hash and executable hash. It does not patch instructions,
stub calls, deliver interrupts, or emulate hardware I/O.

There are 756 controlled cases:

- Every reserve byte 0 through 255 for each player, using shipped CARO glyphs
  and a cleared destination band: 512 cases.
- Synthetic nonzero source/destination patterns across reserve, player, source
  offset wrap, destination wrap, scratch-source alias and DF boundaries: 240.
- Three real CRT stack-error handoffs and one exact passing floor boundary.

Each case is executed with instruction/write observers and again without those
observers. All 14 endpoint registers and the complete 1 MiB memory image must
match. Ordered writes must independently reconstruct the full final memory;
the 43,552-byte original code image must remain unchanged.

Two independent final captures produced byte-identical manifests and corpora:

| Property | Value |
| --- | --- |
| Cases / register observations / executed addresses | 756 / 241599 / 58 |
| Ordered writes / zero-CX REP observations | 104976 / 18072 |
| Decoded / compressed bytes | 8571482 / 604667 |
| Decoded SHA-256 | `dd71ccc1a6ce1dab41aecb865e473341cd0ebf01ab0669c44b499b69f6b334e5` |
| Compressed SHA-256 | `25ab689641056ac9a5fa449916df588ecb0184a3bf90688fafc78fe3a0ddfba5` |
| Manifest SHA-256 | `bd16b21a729eefa28d8d45786c409cf525c8c29181506f5c0861a64f106420f3` |

The compact fixture contains controlled seeds, original register observations
and ordered writes, not full RAM images or screenshots. The checker pins the
manifest, producer, shared oracle, original EXE and CARO asset. Its bounded
decoder and non-destructive export have corruption, source deletion, alias,
repeat-run and symbolic-link controls. The frozen fixture is protected from
Git text conversion and included in the cold-checkout regression.

## Replay And Rendering Checks

`tests/core/reserve_hud_test.cpp` compares the original trace, complete endpoint
registers/flags, full 1 MiB post-state and ordered writes. It uses instruction
grants 1, 2, 17 and 4096 and REP transfer limits 1, 2 and 4, restoring snapshots
between grants. All 9,072 configurations also verify zero/finished-budget
inertness. They make 914,802 boundary comparisons and 2,311,812 logical dispatches.

Unicorn observes individual REP transfers plus an additional zero-CX observation.
The C++ normal-core operation groups transfers by the caller's grant and advances
past the instruction on the last transfer. The test explicitly maps those raw
observations to that existing contract; it does not relabel Unicorn observations
as normal-core work credits. Intermediate arithmetic flags are excluded, while
control flags and all endpoint flags are compared.

The actual production HUD renderer is checked for all 512 shipped-glyph cases:
98,304 indexed glyph pixels and 110,592 pixels beyond the third slot. Optional
pixel dumps preserve twelve comparable original/C++ strip pairs. A displayed
pair at player 2, reserve 6 shows three figures in both versions under the same
shipped palette.

Six independently compiled faults cover reserve addressing, inclusive slot
selection, glyph offset, nine-byte stride, Pascal cleanup and DF handling. The
unchanged control must pass; every fault must compile and fail replay.

The candidate passed the Linux App and selected-test builds, 25 focused CTests
(including existing foreground/HUD, seeded boss and natural-campaign replays),
strict native MSVC `/std:c++latest /W4 /WX /O2` CPU replay, and the complete
ASan/UBSan CPU replay. Native fixture controls passed seven tests with the
symbolic-link test explicitly skipped because Windows denied link creation;
the Linux link controls passed. Native Windows Git cold checkout preserved all
four present families / fourteen files, with four demonstrated CRLF controls.

## Proof Limits

This recovers the complete reserve drawing callee and corrects its live glyph
painting. It does not complete `7C3D..7EBB`, the `326E` ammunition HUD, `07C5`
rectangle clearing, or transfer into the `1B14` end-run UI. It does not integrate
this call into the production instruction clock or prove natural call timing,
IRQ scheduling, live VGA/DAC timing, a natural boss victory, or whole-game parity.

Local outputs and dependency installation remain under WSL `/dev/shm` because
C: is above the repository reserve threshold. Native MSVC CPU replay is distinct
from a native Windows App build or physical-input acceptance.
