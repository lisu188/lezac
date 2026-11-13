# Native Tile-damage Evidence

`native-captures.tar.gz` is 382,489 bytes, SHA256
`3ef5af26bdf845df47a9d2ec664116b235627473d3aa8ff983e897a20c3983cd`.
All 33 members were round-tripped and compared byte-for-byte. The manifest
pins every other member by byte extent and SHA256.

The archive retains both complete 1,312-case original runs and stdout logs,
five observer/support/checker snapshots, both extraction-checker versions,
the executed staging, replay and archive drivers, and actual negative and
positive production receipts bound to clean app source commits and binary
hashes. All native hooks and scratch were restored; both owned children
closed; audio was dummy. Capture asset hashes bind the shipped originals.

`extraction/initial-extractor.py` is the first attempted checker: its allowed
changed-byte set omitted behavior byte +21 and therefore rejected the 96
observed fatal conversions. `extraction/successful-extractor.py` includes that
documented conversion and is the exact successful extraction version.
Both have pending fixture/archive hashes because they precede promotion.
`tools/check_monster_tile_damage_fixture.py` is the post-fixture-promotion
checker snapshot, before archive-hash promotion and the redundant static
sprite-table check. These versions are not claimed to be interchangeable.
The current checker independently validates the retained bytes and reproduces
the pinned fixture from both captures without executing archived scripts.

The negative receipt has 276 mismatching cases, all impacted kinds 5..8;
the positive receipt has none across 1,312 full updates. Original health is
actor byte +0x24, not +3. Complete raw actor and visual records are retained.
See `../../monster_tile_damage_runtime_2026-10-04.md` for field mapping and scope.

This is one-update, seeded behavior-4 evidence with shared actor profiles,
including fatal conversions. It is not natural-route, constructor, all-actor,
corpse-lifecycle, VGA/HUD or whole-game parity. No completion flag is promoted.
