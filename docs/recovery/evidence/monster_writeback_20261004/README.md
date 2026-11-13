# Native Coordinate-Writeback Evidence

`native-captures.tar.gz` retains both complete silent 256-case original captures,
all raw stack/actor/visual bytes, bootstrap images, restoration records, native
stdout, executed observer/shared-helper snapshots, and failed-before/fixed-after
production diagnostics. Every one of its 27 members was roundtrip byte-checked.

- Size: 101,690 bytes.
- SHA256: `6050b6ec10ff7323aa642e1afd674db52088d28f97f321cb407409e6030b355e`.
- Fixture: `tests/fixtures/monster_coordinate_writeback_original.bin`.
- Fixture SHA256: `23008c501c6e0091d3033022d0e496a45db87ed45b4c10761913158b53708e45`.
- Production diagnostic: `--debug-monster-coordinate-writeback FIXTURE`.
- Archive check: `python3 -B tools/check_monster_writeback_fixture.py --archive`.

The extractor snapshot predates addition of the archive check; its extraction,
native validation and pinned-fixture logic are retained as executed. The current
repository checker verifies the whole archive and every internal manifest entry.
The negative diagnostic has 112 mismatches, precisely the original positions
outside the removed level clamp. The positive diagnostic has 256 matches.

These seeded shared actor profiles do not establish natural spawning, complete
campaigns, next-update out-of-map behavior, signed-coordinate overflow or global
visual/actor fidelity. Bootstrap screenshots are not seeded-case parity images.
