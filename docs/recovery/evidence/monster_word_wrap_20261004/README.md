# Native Signed-Coordinate Evidence

`native-captures.tar.gz` retains two complete silent 768-case original runs,
including every stack, actor and visual-table observation, bootstrap images,
restoration record and native stdout. Executed observer/helper/extractor
snapshots and failed-before/fixed-after production diagnostics are included.
All 29 archive members were roundtrip byte-checked.

- Archive size: 195,144 bytes.
- Archive SHA256: `c4b600194b41e778a4f17809926a452b93743b77b58f05d617fe49411abd9b7a`.
- Fixture: `tests/fixtures/monster_coordinate_word_wrap_original.bin`.
- Fixture size: 24,640 bytes.
- Fixture SHA256: `585361d717dcb81ade13503fce6fe043edd1af4c3e3bf2b8a72d02dce9fa4618`.
- Fixture FNV1a64: `3ee7b0987203d3cc`.
- Production command: `--debug-monster-coordinate-word-wrap FIXTURE`.
- Verification: `python3 -B tools/check_monster_word_wrap_fixture.py --archive`.

The checker snapshot was executed for fixture, mutation and native validation
after fixture promotion, before archive-hash promotion. It is not a byte-exact
snapshot of the initial extraction version: the fixture-hash pin and archive
bookkeeping changed afterward, without changes to extraction logic.
The current checker verifies all members and reproduces the
fixture independently from each capture. The negative production diagnostic
fails at exactly the 240 native wrapping cases; the corrected diagnostic
matches all 768 updates without weaker expectations.

These are explicit behavior-4 seeds with a shared descriptor/hotspot profile,
not shipped constructors or natural routes. Observed zero pre-motion edges at
out-of-map positions do not establish general out-of-map terrain semantics.
Boss motion, players, timed/corpse paths and global fidelity claims are unchanged.
