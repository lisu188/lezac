# Ground Walker Ledge Recovery

This recovers the original ground-walker ledge rule. It does not assert complete
Level 2 progression, full actor-byte fidelity, physical input or whole-game
acceptance. All original, C++ and child processes use dummy audio.

## Continuous Original Evidence

An ordinary-input route continues the pinned natural Level 1/results/intro
handoff for 900 Level 2 frames, native frames 318 through 1217. It adds another
large bomb and reaches substantial collapse, 87 destroyed structures, energy
66 and two reserve lives. No objective is collected. One of the four objective
tiles is lost, leaving exactly three, the required number. This is a risky
route frontier, not a completed level or campaign.

The original stream is retained at
`/dev/shm/lezac-natural-level2-completion-original-20261001-v1`.
Its `extension.jsonl.gz` SHA256 is
`3a8c3079b44ddcc8431282fdcb5cbea304515b07484c38d6d7ba6c2e25805870`.
The ordinary prefix canonical hash remains
`18c029dcc107cf95b088a914cf60aa05fd30fbaf26501e3b2367ee91cd96ace8`.
Hooks were restored and original assets were unchanged. The observer's
normalized control-bank input and paused routine windows are not physical
keyboard timing or wall-clock fidelity.

The negative C++ replay has 20,000 differing RGB pixels across its last 55
frames, samples 845 through 899. The first visible mismatch is native frame
1163 / host tick 1588. Independently comparing all 1,800 previously mapped
boundaries still finds no differences: that projection covers player, map,
progress, score, inventory, RNG and selected palette entries, not monster
motion. A new independent projection of live kind-1 through kind-8 actors
finds the underlying motion mismatch at native frame 572 / sample 254, well
before the affected walker enters the viewport. This distinction matters:
camera-limited pixel checks can hide an off-screen behavioral error.

At that first post boundary the native walker continues right at VX=186,
X=400, fraction X=186. The negative port reverses at VX=-186, X=399,
fraction X=70. Its later two walkers remain near X=400 while the original
walkers traverse the roof, fall with the collapsing structure and separate.
No comparison result is promoted to a whole-game claim.

## Native Instruction Rule

Read-only `objdump` inspection of the pinned `LEZAC.EXE` establishes:

- `1000:655B` / file `0x6CCB` starts a cached 4x4 tile scan at
  `C=(X+4)>>3`, `R=Y>>3`, beginning at `(C-1,R-1)`.
- `DS:2054` and `DS:2057` are the two outer cells `(C-1,R+2)` and
  `(C+2,R+2)`, not arbitrary pixel probes inside the actor footprint.
- `1000:7203..727D` / file `0x7973..0x79ED` classifies each of those cells
  as supported only for tile bytes `1..0x52`, independently of word tags.
- Either missing outer cell requests facing reselection. If both are missing,
  the walker preserves horizontal direction. Otherwise it reverses only when
  moving toward the missing outer cell.

The port previously used `solidPixel(X-2 or X+15,Y+17)`, whose destruction and
passable-word predicates are unrelated to this native rule. Tagged structure
words therefore made a continuing roof appear unsupported. The repair uses
the cached cell coordinates and existing `solidTileBottom` predicate. The
landing Y mask remains within the same tile row, so these coordinates preserve
the scan made before integration. Player/general pixel collision is unchanged.

Sixteen synthetic model cases cover tagged floor cells, tile 1, the side-solid
and jump-through boundaries, missing cells on either side, both missing,
motion toward/away from gaps and non-supporting pickup/object bytes.
The old synthetic right-ledge fixture had its hole in column 6, under the
actor's interior; it now places the hole at the native outer column 7 while
preserving the asserted direction and final pose. The first focused batch
failed this fixture; only the subsequent fresh batch passed. This geometry
correction is not an assertion bypass.

## Compact Original Regression

`tests/fixtures/walker_ledge_original.bin` is 2,193 bytes, SHA256
`f2d40e15c0e9425e1c1f8cd11389b0fc0af4e614c2ad8cca4b6d875724b66269`,
FNV-1a64 `406056142da0e279`. It contains the entry actor/visual record, sprite
descriptors, unchanged local 18x4 map rectangle and 32 consecutive post-update
actor/visual records, native frames 572 through 603.

The isolated C++ probe seeds only the walker from that entry record, verifies
the local rectangle against the shipped Level 2 rather than replacing it, and
runs production `updateMonsters`. It compares pose, velocity, fractions,
identity, AI parameters, health, animation fields and visible descriptor.
Other actors, spawners, world passes and original global RNG are not replayed;
the isolated walker is required not to consume RNG. This is seeded regression
evidence derived from natural original play, not itself a natural campaign.

Size and fingerprint guards run before loading/SDL initialization or seeding.
Five negative cases (truncation, trailing data, altered frame, floor byte and
velocity) require failure before replay, preserve their diagnostics and keep
the source fixture immutable. They use only Python's standard library.

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-walker-ledge-original \
  tests/fixtures/walker_ledge_original.bin
```

## Validation And Retention

The corrected exploratory replay matches 900 native frames, all 57,600,000
RGB pixels and 1,800 mapped boundaries. The independent live-monster motion,
fraction, identity and AI projection also matches every boundary; neither
check asserts all actor fields. Stored DAC coverage remains 217 entries,
excluding the computed ramp, while all displayed RGB pixels are compared.
Eight focused CTests passed in 0.97 seconds, including the new original-backed
fixture and corruption guard. The Release rebuild retains only the unrelated
pre-existing debris diagnostic `snprintf` warning. Full exact-head platform
test/package gates remain required before merge.

Compact reports, route, extraction metadata and original/negative/corrected
screenshots are in `evidence/walker_ledge_2026-10-01/`. The copied extractor and
motion audit are captured source provenance, not supported commands from that
directory; their workspace-relative roots were retained byte-for-byte. The immutable observer and
controller sources are already preserved in the earlier pickup-landing evidence.

The negative C++ replay is losslessly retained as
`/dev/shm/lezac-natural-level2-completion-cpp-20261001-v1.tar.gz`, SHA256
`38a85e220be966e9ae113971c35eae38254075f7b51d2cb4e6ac26eafcfe95a7`.
Its 489,837,283 raw bytes were removed only after every file's size/hash matched
the retained archive and inactive/unchanged consumers were rechecked. Sibling
verification metadata retains the full inventory. Corrected and original
captures are also retained. RAM captures are volatile: preserve them before
any WSL restart. No source, assets, saves, branches, stashes or unique evidence
was deleted, and user-owned `AGENTS.md` is excluded from this batch.
