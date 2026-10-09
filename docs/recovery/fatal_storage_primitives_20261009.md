# Fatal Storage Primitives

This is unpublished preparatory work for live generic-monster write-through,
not a claim that the App already uses these new primitives.

## Recovered Writes

`ActorSlots::applyMonsterImpact` writes the visible descriptor, signed
hotspot byte and byte-wrapped animation counter rewind. The impact does not
replace the active animation cursor or backup.

`ActorSlots::applyMonsterDamage` adds the signed damage byte to unsigned
stored HP. A negative result writes kind 12, timer 25, behavior 2 and mode 0,
while retaining stored HP, source, motion, fractions, backup and opaque bytes.
A nonnegative result writes the resulting HP byte.

`MonsterSpawnerStorage::release` leaves dummy source 0 untouched and increments
the selected raw availability byte with wrapping. Its nine-record state
preserves the captured window, including dummy and inactive rows; this is
not a claim that all eight non-dummy rows are shipped active spawners.

`queryMonsterTileDamage` preserves the native top-left, top-right,
bottom-right, bottom-left visitation order. Generic kinds 1..8 use damage
unit 1 for body glyphs and 2 for flame glyph `0x75`. The result includes the
footprint cursor and last flame cell, corresponding to shared globals
`DS:2074` and `DS:2072`; the signed delta corresponds to `DS:661E`.

`DS:2072` is not exclusively an allocation-success flag, and `DS:2074` is
not exclusively a sound request cursor. Both change during the damage
query without a sound request. Live integration must observe request
attempts separately instead of requiring the shared cursor to stay fixed.

## Bounded Compiled Proof

The probe consumes retained native instruction-phase states from the two
independent T96 executions. It compares complete 1,864-byte states after
impact and damage, covering 960 impacts, 768 fatal entries and 192 nonfatal
hits. All 3,578,880 compared bytes match, with no masks. Native nonfatal
impact-only states are derived from the observed post-damage phase by
restoring only the prior stored-HP byte; the T96 independent validator
separately verifies this exact partial-write rule.

The query probe also matches all 1,536 native generic-query results for
`DS:2072`, `DS:2074` and `DS:661E`, including queries with no impact.
Twenty-three compiled production-header mutants are rejected. ASan/UBSan
and the source ownership guard pass.

Derived raw fixture SHA-256 values:

- Partial states, 5,374,092 bytes:
  `7ce72e88f3a37f9ed7a0e53c3ddff59b64af552a4ba6dcbb864046d6d5c57816`.
- Query cases, 17,352 bytes:
  `d62624d48a325faff6fb7e6bc2e0536417fe38b5e2ff8ad57f112f0bad52b589`.

The existing raw-level parser reads seven shipped levels with spawner counts
`1,2,3,2,3,4,0`: 15 total and maximum 4. This is a resource-parser audit,
not proof of natural constructor execution or original runtime ownership.

The first validation run passed native comparisons, all compiled controls
and sanitizers, then failed because the two new headers were absent from
`tools/source_ownership.json`. That run is retained. The corrected inventory
passes the complete rerun without changing the native comparisons.

## Required Follow-Up

Connect the primitives to the App's live animation, damage, conversion and
spawner paths. Bind natural constructor HP/source/AI/animation fields and
the continuing motion writeback. Represent shared scratch writes without
submitting sound requests. Update the sound regression to observe request
attempts, while preserving its boss-chain test.

Then add the complete fatal-entry protocol, check in its pinned fixtures,
register focused CTests, and compare all 6,441,984 full-update App bytes
against the original stream on Linux and Windows. Keep the batch private
until this combined path is ready for exact-head CI and external review.

No full-App fatal-entry, natural route, complete actor/spawner owner,
rendered pixels, sound ISR or whole-game completion claim is made here.
