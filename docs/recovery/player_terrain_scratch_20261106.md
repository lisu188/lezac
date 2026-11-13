# Player Terrain Shared Scratch

The player terrain query now owns the same shared outputs as original
`1000:6F90..7015`: result WORD `DS:2072`, cursor WORD `DS:2074`, and signed
damage BYTE `DS:661E`. These are not exclusively allocation or sound state.
The original caller passes cutoff 2, the query clears its result and damage,
then scans top-left, top-right, bottom-right and bottom-left. Solid glyphs
`1..0x4C` damage only the first two cells; flames `0x75` damage all four and
replace the result with the last flame cell. A no-flame query leaves zero,
not an earlier constructor result or monster query's flame cell.

For a nonzero last flame cell, `3A56` searches the flame bank backward and
replaces the cell cursor with a one-based record index. The highest matching
record supplies impulse and mass damage. Cell zero remains the caller's
no-lookup sentinel even if its glyph is a flame. Scratch is committed before
the health write. Scratch cursor writes do not request or play a sound.
Existing health and impulse arithmetic are unchanged.

## Original Evidence

REA 6.7.0 and Ghidra 12.1.4 on WSL verified every byte of three complete
instruction windows against the immutable 52,384-byte MZ. Independent MZ
loading/relocation verification found no relocations in these windows.
The original SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The target remained unchanged and the REA session closed successfully.

| Window (End Exclusive) | Bytes | SHA-256 |
| --- | ---: | --- |
| `6F90..7015` | 133 | `cdb8f7fedc11841d76d50334fca3aca297bb130cab0d6a82c81c3a648eae48bf` |
| `56B6..5715` | 95 | `63d7907e48d39e81ad5b4a102321d93f02a8c4535b77837a3a59dc9bb418cfc1` |
| `3A56..3A7E` | 40 | `3f516c58abd1bf068ae983a379e9fa17300471679b59d6b473f39fc32eab82a0` |

Unchanged original instructions execute 8,242 seeded cases at width 60:
8,192 glyph/mask/player combinations, 48 mass cases and two zero-cell cases.
Observed and unobserved execution agree on complete 1 MiB memory and
registers. The ordered writes reconstruct the complete output and agree
with the independently modeled expected memory, including stack writes.
No interrupt or hardware behavior is injected. A second width-140 original
corpus executes the same 8,242 profiles with the same checks; only the
width-60 corpus is the matching input for the App diagnostic below.

The original engine is pinned Unicorn 2.1.4. Its actual loaded library
mapping and SHA-256 are checked, rather than relying on a package version:
`ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c`.
Selected complete initial/final memories and receipts are compressed
privately. No raw original code, RAM, DS slices or screenshots are added here.

## Actual-App Regression

`--debug-player-terrain-scratch` uses shipped level 1's width 60, seeds the
terrain and duplicate flame records, and invokes the actual owner for both
players. All 256 glyphs cross all 16 footprint masks. Six mass values cross
four masks; two cases exercise the zero-cell sentinel. Health-byte fixtures
vary across the input space. A read-only health observer checks that all
three scratch outputs exist before the health write. The test also checks
impulse, unchanged unrelated actor/visual/link storage and zero sound
request attempts. The legacy actor adapter is disabled.

An optional output path emits 8,242 input/output records. Native GCC and
MSVC outputs each match the original width-60 stream in full length,
SHA-256 and byte equality: 140,122 bytes, SHA-256
`331b416229e1e34d7cbf4e79e5afd57b16be5f36f16fde9140482befa044d2c5`.
The record stream covers selected inputs, shared outputs, health and impulse;
it is not a comparison of a complete C++ 1 MiB address space.

The pre-fix actual App fails the scratch-before-health check. Three separately
compiled App faults are rejected: omitted result clear, omitted damage-byte
writes and lowest rather than highest duplicate flame lookup. An unchanged
App passes with the same O0 compiler settings. The first comparison attempt
used original width 140 against App width 60: 48 records differed only in
bottom-row result-cell addresses. That input mismatch and its outputs remain
retained; matching-width recapture corrected the validation configuration,
not production arithmetic. An earlier diagnostic-only namespace build error
and pre-fix source/binary are retained too.

Both full native App builds pass. Focused validation includes 43 Linux
CTests, 13 Windows validation commands, an overlapping 26-test Linux
player/render selection with nine renderer mutations, five strict MSVC
ownership-unit commands, original marker/writeback checks and source guards.
Hosted full CI is a separate lane and must not be inferred from these checks.

## Ordinary Combat Comparison

Both native ports replay the full 18,700-tick ordinary-startup route without
later gameplay-state injections. In retained level-4 window 18500..18700,
all 201 complete RGB frames and 402 paired gameplay boundaries match the
original. All 31 actor rows and 33 visual rows remain byte-equal, including
inactive tails and the visual guard: 579,684 bytes per platform.

All four captured scalar bytes now match at every boundary too: actor count,
visual count and shared result, totaling 1,608 bytes per platform. The prior
20 differing shared-result bytes at 12 boundaries are gone. An independent
direct-DS verifier checks complete pools without masks and rejects 1,446
single-byte payload corruptions per platform. Link row 0 still differs by
4,020 bytes across the window; that unmasked residual is not treated as a
pass at this checkpoint. The later `link_alias_ownership_20261106.md` repair
closes those link-row differences in the same bounded window. Pixel equality
already held before these shared-state repairs.

The first comparison adapter accidentally selected the retained pre-fix
health captures through an unchanged filename prefix. Its zero-difference
assertion failed; it did not pass the delivery gate. That failed comparison
and adapter are retained. Correcting the binding selected the new captures,
and independent proof pins their executable and storage hashes explicitly.

## Remaining Scope

This recovers owners of three represented shared fields. It does not create
a unified DS address space or claim all physical scratch globals are owned.
Unmatched flame glyphs without a corresponding record, out-of-bounds and
segment-wrapped map accesses and full active two-player physical state require
further original-backed work. Player 1's separate raw record is subsequently
covered in `player_record_ownership_20261106.md`. Link row 0's
subsequent ownership work is documented separately; full-frame stability,
whole campaign and level-7 boss completion,
wall-clock/physical-input timing and owner acceptance remain open. Broad
full-frame, whole-storage and whole-game fidelity flags stay false.
